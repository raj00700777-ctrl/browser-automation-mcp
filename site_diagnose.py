"""
Raj Browser MCP — Site Diagnosis (scam/phishing/legitimacy check)

One call that answers "is this website safe, and why" -- built
from exactly the manual investigation steps used to flag
nyxowin.com: form/field inspection, third-party tracker analysis,
fabricated-stat detection, gambling/crypto keyword scanning, SSL
check, and link analysis, combined into one weighted risk score
WITH the reasoning behind it (never a black-box number -- every
flag says exactly why it fired, so this stays a learning tool,
not just a verdict machine).

Runs in its OWN isolated tab (like swarm.py) so checking a
suspicious site never touches whatever the user is currently
doing in their main tab.
"""

import re
import time

from browser import browser


# ============================================================
# KNOWN TRACKER / AD-PIXEL DOMAINS
# ============================================================
# Not inherently malicious on their own (huge numbers of
# legitimate sites use these) -- but a heavy ad-tracking funnel
# combined with other red flags (fabricated stats, gambling
# content, no license info) is a classic scam-site distribution
# pattern, so this is one signal among several, not a standalone
# verdict.

_KNOWN_TRACKERS = {
    "connect.facebook.net": "Facebook/Meta Pixel",
    "static.ads-twitter.com": "Twitter/X Ads Pixel",
    "analytics.tiktok.com": "TikTok Pixel",
    "googletagmanager.com": "Google Tag Manager",
    "googlesyndication.com": "Google Ads",
    "doubleclick.net": "Google/DoubleClick Ads",
    "google-analytics.com": "Google Analytics",
    "bat.bing.com": "Microsoft/Bing Ads",
    "static.cloudflareinsights.com": "Cloudflare Analytics (benign)",
}


# ============================================================
# SUSPICIOUS LANGUAGE PATTERNS
# ============================================================

_UNREALISTIC_STAT_PATTERN = re.compile(
    r"(\$\s?\d+(\.\d+)?\s?[BMK]\+?|\d+(\.\d+)?\s?[MK]\+?\s?(players|users|registered|paid))",
    re.IGNORECASE,
)

_GAMBLING_CRYPTO_KEYWORDS = [
    "crypto casino", "bitcoin casino", "blockchain casino", "provably fair",
    "connect wallet", "web3 casino", "no kyc", "instant withdrawal",
    "casino", "jackpot", "vip club", "deposit bonus", "welcome bonus",
]

_URGENCY_KEYWORDS = [
    "act now", "limited time", "hurry", "don't miss", "last chance",
    "exclusive offer", "guaranteed", "risk free", "100% safe", "double your",
]

_LICENSE_KEYWORDS = [
    "license number", "licensed by", "malta gaming authority", "curacao",
    "gambling commission", "regulated by",
]


def _score_body_text(text: str):
    text_lower = text.lower()

    stat_matches = _UNREALISTIC_STAT_PATTERN.findall(text)
    gambling_hits = [k for k in _GAMBLING_CRYPTO_KEYWORDS if k in text_lower]
    urgency_hits = [k for k in _URGENCY_KEYWORDS if k in text_lower]
    has_license_mention = any(k in text_lower for k in _LICENSE_KEYWORDS)

    return {
        "unrealistic_stat_count": len(stat_matches),
        "gambling_crypto_keywords_found": gambling_hits,
        "urgency_keywords_found": urgency_hits,
        "mentions_license_or_regulator": has_license_mention,
    }


# ============================================================
# CLAIMED FOUNDING/OPERATING YEAR (for the contradiction check)
# ============================================================

_FOUNDING_YEAR_PATTERN = re.compile(
    r"(?:since|established(?:\s+in)?|founded(?:\s+in)?|operating\s+since|serving\s+since)\s+(19|20)\d{2}",
    re.IGNORECASE,
)


def _extract_claimed_year(text: str):
    match = _FOUNDING_YEAR_PATTERN.search(text)
    if not match:
        return None
    year_match = re.search(r"(19|20)\d{2}", match.group(0))
    return int(year_match.group(0)) if year_match else None


# ============================================================
# EXTERNAL VERIFICATION -- the part no scraping tool bothers with
# ============================================================
#
# These three checks use the browser ITSELF to fetch independently
# verifiable facts about the domain, rather than trusting anything
# the page says about itself:
#
#   1. RDAP (modern WHOIS) -- when was this domain actually
#      registered? A site claiming "est. 2017" whose domain was
#      registered last month is caught red-handed.
#   2. TLS certificate issue date -- a second, independent
#      timestamp that's very hard to fake to match a false
#      "we've been around for years" story.
#   3. Wayback Machine -- when did the public internet archive
#      first see this domain? A real long-running site almost
#      always has years of snapshots; a brand-new scam funnel has
#      none, or only very recent ones.
#
# None of these need an API key -- rdap.org and archive.org both
# expose free public JSON endpoints.

def _domain_from_url(url: str) -> str:
    from urllib.parse import urlparse
    host = (urlparse(url).hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    return host


async def _fetch_json_via_browser(page, url: str):
    """Navigate the SAME automation browser to a JSON API endpoint and parse the response."""
    try:
        response = await page.goto(url, wait_until="domcontentloaded", timeout=10000)
        if response is None or not response.ok:
            return None
        body_text = await page.evaluate("() => document.body.innerText || document.body.textContent")
        import json as _json
        return _json.loads(body_text)
    except Exception:
        return None


async def _check_domain_age_rdap(context, domain: str):
    """Look up the real registration date via RDAP (modern WHOIS), no API key needed."""
    try:
        page = await context.new_page()
        try:
            data = await _fetch_json_via_browser(page, f"https://rdap.org/domain/{domain}")
            if not data:
                return {"available": False}

            events = data.get("events", [])
            reg_event = next((e for e in events if e.get("eventAction") == "registration"), None)
            if not reg_event:
                return {"available": False}

            reg_date = reg_event.get("eventDate")
            reg_year = int(reg_date[:4]) if reg_date else None
            age_days = None
            if reg_date:
                try:
                    from datetime import datetime, timezone
                    reg_dt = datetime.fromisoformat(reg_date.replace("Z", "+00:00"))
                    age_days = (datetime.now(timezone.utc) - reg_dt).days
                except Exception:
                    pass

            return {
                "available": True,
                "registration_date": reg_date,
                "registration_year": reg_year,
                "age_days": age_days,
                "registrar": (data.get("entities") or [{}])[0].get("handle") if data.get("entities") else None,
            }
        finally:
            await page.close()
    except Exception:
        return {"available": False}


async def _check_wayback_earliest(context, domain: str):
    """Find the earliest snapshot the Internet Archive has of this domain."""
    try:
        page = await context.new_page()
        try:
            cdx_url = (
                f"http://web.archive.org/cdx/search/cdx?url={domain}"
                f"&output=json&limit=1&fl=timestamp&sort=ascending"
            )
            data = await _fetch_json_via_browser(page, cdx_url)
            if not data or len(data) < 2:
                return {"available": True, "has_snapshots": False}

            timestamp = data[1][0]  # row 0 is the header ["timestamp"]
            year = int(timestamp[:4])
            from datetime import datetime, timezone
            first_seen = datetime.strptime(timestamp[:8], "%Y%m%d").replace(tzinfo=timezone.utc)
            age_days = (datetime.now(timezone.utc) - first_seen).days

            return {
                "available": True,
                "has_snapshots": True,
                "first_seen_year": year,
                "first_seen_date": timestamp[:8],
                "age_days": age_days,
            }
        finally:
            await page.close()
    except Exception:
        return {"available": False}


async def _get_ssl_cert_info(response):
    """
    Pull the TLS certificate's validity window from the Response
    object Playwright returned for the page's own navigation --
    a second, independent timestamp on top of RDAP that's very
    hard to fake to match a false "operating since 20XX" story.
    """
    try:
        if response is None:
            return {"available": False}
        details = await response.security_details()
        if not details:
            return {"available": False}

        valid_from = details.get("validFrom")  # unix timestamp (seconds)
        age_days = None
        if valid_from:
            from datetime import datetime, timezone
            issued = datetime.fromtimestamp(valid_from, tz=timezone.utc)
            age_days = (datetime.now(timezone.utc) - issued).days

        return {
            "available": True,
            "issuer": details.get("issuer"),
            "protocol": details.get("protocol"),
            "cert_age_days": age_days,
        }
    except Exception:
        return {"available": False}


# ============================================================
# PAGE ACCESS (isolated tab, doesn't touch the active page)
# ============================================================

async def _ensure_started():
    await browser.start()
    if browser.context is None:
        raise RuntimeError("Browser context is not available even after start().")


_DIAGNOSTIC_JS = """() => {
    const forms = Array.from(document.querySelectorAll('form')).map(f => ({
        action: f.action, method: f.method,
        inputCount: f.querySelectorAll('input, select, textarea').length,
    }));

    const allInputs = Array.from(document.querySelectorAll('input'));
    const passwordFieldCount = allInputs.filter(i => i.type === 'password').length;
    const paymentLikeFieldCount = allInputs.filter(i =>
        /card|cvv|cvc|expiry|routing|iban|swift/i.test((i.name||'') + (i.placeholder||'') + (i.id||''))
    ).length;
    const otpLikeFieldCount = allInputs.filter(i =>
        /otp|verification.?code|2fa/i.test((i.name||'') + (i.placeholder||'') + (i.id||''))
    ).length;

    const scripts = Array.from(document.querySelectorAll('script[src]')).map(s => s.src);
    const scriptDomains = [...new Set(scripts.map(s => {
        try { return new URL(s).hostname; } catch(e) { return null; }
    }).filter(Boolean))];

    const links = Array.from(document.querySelectorAll('a[href]'));
    const linkDomains = [...new Set(links.map(a => {
        try { return new URL(a.href).hostname; } catch(e) { return null; }
    }).filter(Boolean))];

    return {
        title: document.title,
        metaDescription: document.querySelector('meta[name="description"]')?.content || null,
        forms, formCount: forms.length,
        passwordFieldCount, paymentLikeFieldCount, otpLikeFieldCount,
        scriptDomains,
        iframeCount: document.querySelectorAll('iframe').length,
        metaRefresh: document.querySelector('meta[http-equiv="refresh"]')?.content || null,
        bodyText: (document.body.innerText || '').slice(0, 4000),
        linkCount: links.length,
        externalLinkDomainCount: linkDomains.length,
        hasWalletConnect: /connect.?wallet|web3|metamask/i.test(document.body.innerHTML.slice(0, 20000)),
    };
}"""


# ============================================================
# MAIN DIAGNOSIS
# ============================================================

async def diagnose_site(url: str = None, use_current_page: bool = False):
    """
    Full diagnostic scan of a website: forms/sensitive-field
    inspection, third-party tracker analysis, fabricated-stat and
    gambling/urgency language detection, SSL, and link analysis --
    combined into a risk score WITH the reasoning behind it.

    url: site to check. Opens its own isolated tab by default so
         this never disturbs whatever's happening in the main tab.
    use_current_page: if True, inspect the currently active page
         instead of opening url in a new tab (url is ignored then).
    """
    try:
        await _ensure_started()

        opened_own_tab = False
        response = None
        if use_current_page:
            page = await browser.get_page()
            target_url = page.url
        else:
            if not url:
                return {"success": False, "error": "Provide url=, or set use_current_page=True."}
            page = await browser.context.new_page()
            opened_own_tab = True
            try:
                response = await page.goto(url, wait_until="domcontentloaded", timeout=20000)
                # Modern SPAs (React/Next.js etc.) render most real
                # content AFTER the initial DOM load via client-side
                # hydration -- scanning too early can miss forms,
                # links, and body text entirely. Give it a moment.
                try:
                    await page.wait_for_load_state("networkidle", timeout=5000)
                except Exception:
                    pass
                await page.wait_for_timeout(1500)
            except Exception as error:
                await page.close()
                return {"success": False, "error": f"Could not load {url}: {error}"}
            target_url = url

        try:
            data = await page.evaluate(_DIAGNOSTIC_JS)
            final_url = page.url
            is_https = final_url.startswith("https://")
            ssl_info = await _get_ssl_cert_info(response) if response else {"available": False}
        finally:
            if opened_own_tab:
                await page.close()

        # ---- External, independently-verifiable checks ----
        # These use the browser to look up facts NO amount of
        # scanning the page's own HTML can reveal or fake.
        domain = _domain_from_url(final_url)
        rdap_info = await _check_domain_age_rdap(browser.context, domain) if domain else {"available": False}
        wayback_info = await _check_wayback_earliest(browser.context, domain) if domain else {"available": False}

        # ---- Score assembly ----
        reasons = []
        score = 0  # 0 = totally clean signal set, higher = riskier

        trackers_found = [
            {"domain": d, "service": _KNOWN_TRACKERS[d]}
            for d in data["scriptDomains"] if d in _KNOWN_TRACKERS
        ]
        unknown_external_scripts = [
            d for d in data["scriptDomains"]
            if d not in _KNOWN_TRACKERS and d not in final_url
        ]

        full_text = f"{data['title'] or ''} {data['metaDescription'] or ''} {data['bodyText']}"
        text_analysis = _score_body_text(full_text)
        claimed_year = _extract_claimed_year(full_text)

        # ---- THE CONTRADICTION CHECK ----
        # This is the part no keyword scanner or generic scraper
        # does: cross-referencing what the site SAYS about its own
        # history against independently verifiable facts.
        if claimed_year and rdap_info.get("available") and rdap_info.get("registration_year"):
            actual_year = rdap_info["registration_year"]
            if actual_year > claimed_year + 1:
                score += 40
                reasons.append(
                    f"CONTRADICTION: page claims to be operating since {claimed_year}, but the domain "
                    f"was only registered in {actual_year} (verified via RDAP/WHOIS) -- "
                    f"{actual_year - claimed_year} years after the claimed founding date. This is a "
                    f"hard, independently-verifiable fact, not a guess."
                )

        if claimed_year and wayback_info.get("available") and wayback_info.get("has_snapshots"):
            first_seen = wayback_info["first_seen_year"]
            if first_seen > claimed_year + 1:
                score += 15
                reasons.append(
                    f"The Wayback Machine's earliest snapshot of this domain is from {first_seen}, "
                    f"contradicting the claimed founding year of {claimed_year}."
                )
        elif claimed_year and wayback_info.get("available") and not wayback_info.get("has_snapshots"):
            score += 10
            reasons.append(
                f"Site claims to be operating since {claimed_year}, but the Internet Archive has "
                f"NO snapshots of this domain at all -- unusual for a genuinely long-running site."
            )

        if rdap_info.get("available") and rdap_info.get("age_days") is not None:
            if rdap_info["age_days"] < 90:
                score += 20
                reasons.append(
                    f"Domain was registered only {rdap_info['age_days']} days ago -- very new domains "
                    f"are disproportionately used for short-lived scam campaigns."
                )

        if ssl_info.get("available") and ssl_info.get("cert_age_days") is not None:
            if ssl_info["cert_age_days"] < 30 and claimed_year and claimed_year < 2024:
                score += 10
                reasons.append(
                    f"TLS certificate was issued only {ssl_info['cert_age_days']} days ago, which is "
                    f"unremarkable on its own, but sits oddly next to a claimed founding year of "
                    f"{claimed_year} (long-running sites usually have a renewal history, not a brand-new cert)."
                )

        if not is_https:
            score += 25
            reasons.append("Site is not served over HTTPS -- any data entered is unencrypted in transit.")

        if data["passwordFieldCount"] > 0 and not is_https:
            score += 20
            reasons.append("A password field exists on a non-HTTPS page -- credentials would be sent in plaintext.")

        if data["paymentLikeFieldCount"] > 0:
            score += 15
            reasons.append(f"Found {data['paymentLikeFieldCount']} field(s) that look like payment/card inputs.")

        if text_analysis["unrealistic_stat_count"] >= 2:
            score += 20
            reasons.append(
                f"Found {text_analysis['unrealistic_stat_count']} unrealistically large/round stat claims "
                f"(e.g. '$32.5B+ paid out') -- a common credibility-inflation tactic on fake sites."
            )

        if text_analysis["gambling_crypto_keywords_found"]:
            score += 15
            reasons.append(
                f"Gambling/crypto-casino language detected: {', '.join(text_analysis['gambling_crypto_keywords_found'][:5])}."
            )

        if text_analysis["gambling_crypto_keywords_found"] and not text_analysis["mentions_license_or_regulator"]:
            score += 20
            reasons.append(
                "Gambling/crypto content found with NO visible license or regulator mention -- "
                "legitimate gambling platforms are required to display this clearly."
            )

        if text_analysis["urgency_keywords_found"]:
            score += 10
            reasons.append(
                f"High-pressure/urgency language detected: {', '.join(text_analysis['urgency_keywords_found'][:5])}."
            )

        if data["hasWalletConnect"] and text_analysis["gambling_crypto_keywords_found"]:
            score += 10
            reasons.append("Crypto-wallet-connect functionality combined with gambling content -- common scam-funnel pattern.")

        if data["linkCount"] == 0 and len(data["bodyText"]) > 200:
            score += 5
            reasons.append(
                "Page has substantial text content but ZERO links -- unusual for a real site "
                "(navigation/footer links are typically present). May indicate incomplete JS "
                "rendering was captured, or the page deliberately avoids normal <a> navigation."
            )

        if len(trackers_found) >= 2:
            score += 5
            reasons.append(
                f"Multiple ad-tracking pixels loaded ({', '.join(t['service'] for t in trackers_found)}) -- "
                f"suggests traffic is driven by paid social ads, a common scam-site distribution model "
                f"(also used by many legitimate e-commerce sites, so this alone is weak evidence)."
            )

        if unknown_external_scripts:
            reasons.append(
                f"Loads scripts from {len(unknown_external_scripts)} unrecognized external domain(s): "
                f"{', '.join(unknown_external_scripts[:5])}."
            )

        if data["formCount"] == 0 and (data["passwordFieldCount"] or data["paymentLikeFieldCount"]):
            reasons.append(
                "Sensitive-looking fields exist but aren't inside a real <form> -- may be JS-rendered "
                "dynamically (common in modern apps, but also makes automated form analysis less reliable)."
            )

        score = min(100, score)
        if score >= 50:
            risk_level = "high"
        elif score >= 25:
            risk_level = "medium"
        else:
            risk_level = "low"

        if not reasons:
            reasons.append("No red flags detected by this scan -- this does NOT guarantee legitimacy, only that none of the checked signals fired.")

        return {
            "success": True,
            "action": "diagnose_site",
            "url": target_url,
            "final_url": final_url,
            "title": data["title"],
            "meta_description": data["metaDescription"],
            "https": is_https,
            "risk_score": score,
            "risk_level": risk_level,
            "reasons": reasons,
            "domain_verification": {
                "domain": domain,
                "claimed_founding_year": claimed_year,
                "rdap_registration": rdap_info,
                "ssl_certificate": ssl_info,
                "wayback_machine": wayback_info,
            },
            "details": {
                "form_count": data["formCount"],
                "password_field_count": data["passwordFieldCount"],
                "payment_like_field_count": data["paymentLikeFieldCount"],
                "otp_like_field_count": data["otpLikeFieldCount"],
                "iframe_count": data["iframeCount"],
                "meta_refresh_redirect": data["metaRefresh"],
                "known_trackers": trackers_found,
                "unknown_external_script_domains": unknown_external_scripts,
                "link_count": data["linkCount"],
                "external_link_domain_count": data["externalLinkDomainCount"],
                "has_wallet_connect_code": data["hasWalletConnect"],
                "unrealistic_stat_count": text_analysis["unrealistic_stat_count"],
                "gambling_crypto_keywords_found": text_analysis["gambling_crypto_keywords_found"],
                "urgency_keywords_found": text_analysis["urgency_keywords_found"],
                "mentions_license_or_regulator": text_analysis["mentions_license_or_regulator"],
            },
            "note": (
                "Includes independently-verified domain age (RDAP/WHOIS), TLS certificate age, and "
                "Internet Archive history where available -- these are checked automatically via "
                "public, key-free lookups and are cross-referenced against any founding-year claim "
                "the page itself makes. Treat a 'high' score as a strong warning, and a 'low' score "
                "as 'no red flags found', not a guarantee of legitimacy."
            ),
        }

    except Exception as error:
        return {"success": False, "error": str(error)}


# ============================================================
# EXPORTS
# ============================================================

__all__ = ["diagnose_site"]
