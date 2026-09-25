from urllib.parse import quote
from browser import browser


# ============================================================
# CONFIGURATION
# ============================================================

DEFAULT_TIMEOUT = 15000
MAX_TEXT_LENGTH = 12000
MAX_SOURCES = 8


# ============================================================
# RESEARCH SOURCES
# ============================================================

def _build_sources(topic: str):
    """
    Build a diverse set of research sources.

    The URLs are intentionally explicit so the research layer
    does not accidentally route every request through Google.
    """

    encoded = quote(topic)

    return [
        {
            "name": "Google",
            "url": (
                "https://www.google.com/search?q="
                + encoded
            ),
            "type": "web",
        },
        {
            "name": "Wikipedia",
            "url": (
                "https://en.wikipedia.org/wiki/"
                "Special:Search?search="
                + encoded
            ),
            "type": "reference",
        },
        {
            "name": "Google Scholar",
            "url": (
                "https://scholar.google.com/scholar?q="
                + encoded
            ),
            "type": "academic",
        },
        {
            "name": "Google News",
            "url": (
                "https://www.google.com/search?"
                "tbm=nws&q="
                + encoded
            ),
            "type": "news",
        },
    ]


# ============================================================
# SAFE PAGE INFO
# ============================================================

async def _page_info(page):
    """
    Safely collect basic page information.
    """

    try:
        title = await page.title()
    except Exception:
        title = ""

    return {
        "url": page.url,
        "title": title,
    }


# ============================================================
# PAGE TEXT
# ============================================================

async def _extract_page_text(
    page,
    max_length=MAX_TEXT_LENGTH,
):
    """
    Extract visible body text without allowing one broken
    page to break the complete research workflow.
    """

    try:

        text = await page.locator(
            "body"
        ).inner_text(
            timeout=DEFAULT_TIMEOUT
        )

        if not isinstance(text, str):
            return ""

        text = text.strip()

        return text[:max_length]

    except Exception:
        return ""


# ============================================================
# RESEARCH TOPIC
# ============================================================

async def research_topic(topic: str):
    """
    Multi-source research workflow.

    Opens multiple independent research sources and returns
    structured information about each source.

    Existing API preserved:
        research_topic(topic)
    """

    if not isinstance(topic, str):
        return {
            "success": False,
            "error": "Research topic must be a string.",
        }

    topic = topic.strip()

    if not topic:
        return {
            "success": False,
            "error": "Research topic cannot be empty.",
        }

    sources = _build_sources(topic)

    created = []
    successful = 0
    failed = 0

    for source in sources[:MAX_SOURCES]:

        name = source["name"]
        url = source["url"]

        try:

            page = await browser.new_page(url)

            info = await _page_info(page)

            text = await _extract_page_text(page)

            created.append({
                "source": name,
                "type": source["type"],
                "success": True,
                "url": info["url"],
                "title": info["title"],
                "text": text,
            })

            successful += 1

        except Exception as error:

            failed += 1

            created.append({
                "source": name,
                "type": source["type"],
                "success": False,
                "url": url,
                "title": "",
                "error": str(error),
            })

    return {
        "success": successful > 0,
        "topic": topic,
        "sources_requested": len(sources),
        "sources_opened": successful,
        "sources_failed": failed,
        "pages": created,
    }


# ============================================================
# COLLECT OPEN PAGES
# ============================================================

async def collect_open_pages():
    """
    Collect information from all currently open browser tabs.

    Existing API preserved:
        collect_open_pages()
    """

    try:
        pages = await browser.get_pages()

    except Exception as error:

        return {
            "success": False,
            "count": 0,
            "pages": [],
            "error": str(error),
        }

    results = []

    for index, page in enumerate(pages):

        try:

            info = await _page_info(page)

            text = await _extract_page_text(page)

            results.append({
                "index": index,
                "success": True,
                "title": info["title"],
                "url": info["url"],
                "text": text,
            })

        except Exception as error:

            try:
                current_url = page.url
            except Exception:
                current_url = ""

            results.append({
                "index": index,
                "success": False,
                "url": current_url,
                "title": "",
                "text": "",
                "error": str(error),
            })

    successful = sum(
        1
        for item in results
        if item.get("success") is True
    )

    return {
        "success": True,
        "count": len(results),
        "successful_pages": successful,
        "failed_pages": len(results) - successful,
        "pages": results,
    }


# ============================================================
# RESEARCH SUMMARY
# ============================================================

async def research_summary(topic: str):
    """
    Run research and return a compact structured summary.

    This is an additional helper; existing APIs remain intact.
    """

    result = await research_topic(topic)

    if not result.get("success"):
        return result

    summaries = []

    for page in result.get("pages", []):

        if not page.get("success"):
            continue

        summaries.append({
            "source": page.get("source"),
            "type": page.get("type"),
            "title": page.get("title"),
            "url": page.get("url"),
            "text_preview": page.get(
                "text",
                "",
            )[:3000],
        })

    return {
        "success": True,
        "topic": result.get("topic"),
        "sources": summaries,
        "source_count": len(summaries),
    }


# ============================================================
# DEEP RESEARCH -- real content pages, not search-result pages
# ============================================================
#
# research_topic() above opens SEARCH pages (google.com/search?q=...).
# This opens the actual ARTICLES those searches point to -- real,
# visible tabs, each scrolled to and centered on the exact spot
# where the topic is actually discussed, not just the homepage.

# Google's own domains and common ad/tracking hosts that show up in
# search results but aren't real content -- filtered out so every
# opened tab is a genuine source.
_NON_CONTENT_DOMAINS = (
    "google.com", "google.co", "googleadservices.com", "googlesyndication.com",
    "doubleclick.net", "gstatic.com", "youtube.com/ads",
)

_FIND_AND_SCROLL_JS = """(keywords) => {
    const lowerKeywords = keywords.map(k => k.toLowerCase()).filter(k => k.length > 2);

    function textOf(el) {
        return (el.innerText || el.textContent || '');
    }

    // Prefer actual content blocks (paragraphs, list items, article
    // bodies) over nav/header/footer chrome.
    const candidates = Array.from(document.querySelectorAll('p, li, blockquote, article, section, div'));

    let best = null;
    let bestScore = 0;

    for (const el of candidates) {
        const text = textOf(el);
        if (!text || text.length < 40 || text.length > 4000) continue;

        const lower = text.toLowerCase();
        let score = 0;
        for (const k of lowerKeywords) {
            if (lower.includes(k)) score++;
        }
        if (score > bestScore) {
            bestScore = score;
            best = el;
        }
    }

    if (!best) {
        return { found: false };
    }

    best.scrollIntoView({ block: 'center', behavior: 'instant' });

    // Grab a bit of surrounding context (parent), not just the
    // single matched element, for a more readable excerpt.
    const context = best.parentElement ? textOf(best.parentElement) : textOf(best);

    return {
        found: true,
        matched_text: textOf(best).slice(0, 1500),
        context: context.slice(0, 2500),
    };
}"""


def _is_content_url(url: str) -> bool:
    if not url or not url.startswith("http"):
        return False
    return not any(domain in url for domain in _NON_CONTENT_DOMAINS)


async def _get_organic_results(page, limit: int):
    """Pull real article links (title + href) from a loaded Google results page."""
    try:
        raw = await page.locator("a:has(h3)").evaluate_all(
            """els => els.map(e => ({
                title: (e.querySelector('h3')?.innerText || '').trim(),
                href: e.href || ''
            }))"""
        )
    except Exception:
        raw = []

    seen = set()
    results = []
    for item in raw:
        href = item.get("href", "")
        if not _is_content_url(href) or href in seen:
            continue
        seen.add(href)
        results.append({"title": item.get("title") or href, "url": href})
        if len(results) >= limit:
            break

    return results


async def deep_research(topic: str, tab_count: int = 3, timeout: int = 20000):
    """
    Open `tab_count` REAL, VISIBLE tabs -- each a genuine article/
    page that actually discusses `topic` in detail, scrolled to
    and centered on the exact section where it's mentioned.
    Unlike research_topic() (which opens search-RESULT pages),
    this follows through to the real content itself.
    """
    if not isinstance(topic, str) or not topic.strip():
        return {"success": False, "error": "Research topic must be a non-empty string."}

    tab_count = max(1, min(int(tab_count), 8))
    topic = topic.strip()
    keywords = [w for w in topic.split() if len(w) > 2][:6] or [topic]

    try:
        search_page = await browser.new_page(
            "https://www.google.com/search?q=" + quote(topic)
        )
    except Exception as error:
        return {"success": False, "error": f"Could not perform search: {error}"}

    candidates = await _get_organic_results(search_page, limit=tab_count * 2)

    if not candidates:
        return {
            "success": False,
            "error": "No real content links found in search results (page structure may have changed).",
            "topic": topic,
        }

    # The search tab itself becomes the FIRST result tab (no need to
    # open yet another tab for it) -- everything else opens fresh.
    chosen = candidates[:tab_count]

    opened = []
    for index, candidate in enumerate(chosen):
        try:
            if index == 0:
                page = search_page
                await page.goto(candidate["url"], wait_until="domcontentloaded", timeout=timeout)
            else:
                page = await browser.new_page(candidate["url"])
                try:
                    await page.wait_for_load_state("domcontentloaded", timeout=timeout)
                except Exception:
                    pass

            try:
                await page.wait_for_timeout(800)
                match = await page.evaluate(_FIND_AND_SCROLL_JS, keywords)
            except Exception:
                match = {"found": False}

            title = await page.title()

            opened.append({
                "success": True,
                "url": page.url,
                "title": title,
                "requested_url": candidate["url"],
                "topic_found_on_page": match.get("found", False),
                "matched_excerpt": match.get("context") or match.get("matched_text"),
            })

        except Exception as error:
            opened.append({
                "success": False,
                "requested_url": candidate.get("url"),
                "title": candidate.get("title"),
                "error": str(error),
            })

    successful = sum(1 for o in opened if o.get("success"))

    return {
        "success": successful > 0,
        "topic": topic,
        "tabs_requested": tab_count,
        "tabs_opened": successful,
        "tabs_failed": len(opened) - successful,
        "results": opened,
    }


# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    "research_topic",
    "collect_open_pages",
    "research_summary",
    "deep_research",
]