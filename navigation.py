from urllib.parse import quote
from browser import browser


# ============================================================
# CONFIG
# ============================================================

DEFAULT_TIMEOUT = 30000


# ============================================================
# INTERNAL HELPERS
# ============================================================

async def _get_page():
    page = await browser.get_page()

    if page is None:
        raise RuntimeError("No active browser page available.")

    return page


async def _page_info(page):
    try:
        title = await page.title()
    except Exception:
        title = ""

    return {
        "url": page.url,
        "title": title,
    }


def _clean_url(url: str) -> str:
    if not isinstance(url, str):
        raise TypeError("URL must be a string.")

    url = url.strip()

    if not url:
        raise ValueError("URL cannot be empty.")

    return url


def _normalize_site(site: str) -> str:
    return str(site).strip().lower()


# ============================================================
# OPEN URL
# ============================================================

async def open_url(
    url: str,
    timeout: int = DEFAULT_TIMEOUT,
):
    """
    Open an arbitrary URL.
    """

    page = await _get_page()

    url = _clean_url(url)

    await page.goto(
        url,
        wait_until="domcontentloaded",
        timeout=int(timeout),
    )

    info = await _page_info(page)

    return {
        "success": True,
        "action": "navigate",
        "url": info["url"],
        "title": info["title"],
    }


# ============================================================
# GOOGLE SEARCH
# ============================================================

async def google_search(
    query: str,
    timeout: int = DEFAULT_TIMEOUT,
):
    """
    Google-only search.

    This function intentionally performs a Google search.
    Site-specific searches belong to site_search().
    """

    page = await _get_page()

    if not isinstance(query, str):
        raise TypeError("Search query must be a string.")

    query = query.strip()

    if not query:
        raise ValueError("Search query cannot be empty.")

    url = (
        "https://www.google.com/search?q="
        + quote(query)
    )

    await page.goto(
        url,
        wait_until="domcontentloaded",
        timeout=int(timeout),
    )

    info = await _page_info(page)

    return {
        "success": True,
        "action": "google_search",
        "query": query,
        "url": info["url"],
        "title": info["title"],
    }


# ============================================================
# SITE SEARCH
# ============================================================

async def site_search(
    site: str,
    query: str,
    timeout: int = DEFAULT_TIMEOUT,
):
    """
    Perform a search on a supported website.

    IMPORTANT:
    This does NOT silently redirect every search to Google.
    """

    page = await _get_page()

    site = _normalize_site(site)

    if not isinstance(query, str):
        raise TypeError("Search query must be a string.")

    query = query.strip()

    if not query:
        raise ValueError("Search query cannot be empty.")

    encoded = quote(query)

    if site in (
        "google",
        "google.com",
    ):
        url = (
            "https://www.google.com/search?q="
            + encoded
        )

    elif site in (
        "youtube",
        "youtube.com",
    ):
        url = (
            "https://www.youtube.com/results?search_query="
            + encoded
        )

    elif site in (
        "bing",
        "bing.com",
    ):
        url = (
            "https://www.bing.com/search?q="
            + encoded
        )

    elif site in (
        "duckduckgo",
        "duckduckgo.com",
        "ddg",
    ):
        url = (
            "https://duckduckgo.com/?q="
            + encoded
        )

    elif site in (
        "github",
        "github.com",
    ):
        url = (
            "https://github.com/search?q="
            + encoded
        )

    elif site in (
        "reddit",
        "reddit.com",
    ):
        url = (
            "https://www.reddit.com/search/?q="
            + encoded
        )

    elif site in (
        "wikipedia",
        "wikipedia.org",
    ):
        url = (
            "https://en.wikipedia.org/w/index.php?search="
            + encoded
        )

    else:
        return {
            "success": False,
            "action": "site_search",
            "error": (
                f"Unsupported search site: {site}"
            ),
            "site": site,
            "query": query,
            "supported_sites": [
                "google",
                "youtube",
                "bing",
                "duckduckgo",
                "github",
                "reddit",
                "wikipedia",
            ],
        }

    await page.goto(
        url,
        wait_until="domcontentloaded",
        timeout=int(timeout),
    )

    info = await _page_info(page)

    return {
        "success": True,
        "action": "site_search",
        "site": site,
        "query": query,
        "url": info["url"],
        "title": info["title"],
    }


# ============================================================
# OPEN COMMON SITE
# ============================================================

async def open_site(
    site: str,
    timeout: int = DEFAULT_TIMEOUT,
):
    """
    Open a known website by name.

    This is only a convenience mapping.
    The planner is not restricted to these websites.
    """

    site = _normalize_site(site)

    sites = {
        "google": "https://www.google.com",
        "google.com": "https://www.google.com",
        "youtube": "https://www.youtube.com",
        "youtube.com": "https://www.youtube.com",
        "bing": "https://www.bing.com",
        "bing.com": "https://www.bing.com",
        "duckduckgo": "https://duckduckgo.com",
        "duckduckgo.com": "https://duckduckgo.com",
        "github": "https://github.com",
        "github.com": "https://github.com",
        "reddit": "https://www.reddit.com",
        "reddit.com": "https://www.reddit.com",
        "wikipedia": "https://www.wikipedia.org",
        "wikipedia.org": "https://www.wikipedia.org",
        "amazon": "https://www.amazon.com",
        "amazon.com": "https://www.amazon.com",
    }

    if site not in sites:
        return {
            "success": False,
            "action": "open_site",
            "error": f"Unknown site: {site}",
            "supported_sites": sorted(
                sites.keys()
            ),
        }

    result = await open_url(
        sites[site],
        timeout=timeout,
    )

    if isinstance(result, dict):
        result["action"] = "open_site"
        result["site"] = site

    return result


# ============================================================
# BACK
# ============================================================

async def go_back(
    timeout: int = DEFAULT_TIMEOUT,
):
    page = await _get_page()

    response = await page.go_back(
        wait_until="domcontentloaded",
        timeout=int(timeout),
    )

    info = await _page_info(page)

    return {
        "success": True,
        "action": "back",
        "navigation_occurred": response is not None,
        "url": info["url"],
        "title": info["title"],
    }


# ============================================================
# FORWARD
# ============================================================

async def go_forward(
    timeout: int = DEFAULT_TIMEOUT,
):
    page = await _get_page()

    response = await page.go_forward(
        wait_until="domcontentloaded",
        timeout=int(timeout),
    )

    info = await _page_info(page)

    return {
        "success": True,
        "action": "forward",
        "navigation_occurred": response is not None,
        "url": info["url"],
        "title": info["title"],
    }


# ============================================================
# REFRESH
# ============================================================

async def refresh(
    timeout: int = DEFAULT_TIMEOUT,
):
    page = await _get_page()

    response = await page.reload(
        wait_until="domcontentloaded",
        timeout=int(timeout),
    )

    info = await _page_info(page)

    return {
        "success": True,
        "action": "refresh",
        "reloaded": response is not None,
        "url": info["url"],
        "title": info["title"],
    }


# ============================================================
# WAIT
# ============================================================

async def wait_for_navigation(
    seconds: float = 2,
):
    page = await _get_page()

    seconds = max(
        0.0,
        float(seconds),
    )

    await page.wait_for_timeout(
        int(seconds * 1000)
    )

    info = await _page_info(page)

    return {
        "success": True,
        "action": "wait",
        "waited_seconds": seconds,
        "url": info["url"],
        "title": info["title"],
    }


# ============================================================
# WAIT FOR URL
# ============================================================

async def wait_for_url(
    url_pattern: str,
    timeout: int = DEFAULT_TIMEOUT,
):
    page = await _get_page()

    if (
        not isinstance(url_pattern, str)
        or not url_pattern.strip()
    ):
        raise ValueError(
            "URL pattern cannot be empty."
        )

    await page.wait_for_url(
        url_pattern,
        timeout=int(timeout),
    )

    info = await _page_info(page)

    return {
        "success": True,
        "action": "wait_for_url",
        "pattern": url_pattern,
        "url": info["url"],
        "title": info["title"],
    }


# ============================================================
# CURRENT PAGE
# ============================================================

async def current_page():
    page = await _get_page()

    info = await _page_info(page)

    return {
        "success": True,
        "action": "current_page",
        "url": info["url"],
        "title": info["title"],
    }


# ============================================================
# NAVIGATION STATUS
# ============================================================

async def navigation_status():
    """
    Return the current browser navigation state.
    """

    try:
        page = await _get_page()
        info = await _page_info(page)

        return {
            "success": True,
            "action": "navigation_status",
            "url": info["url"],
            "title": info["title"],
        }

    except Exception as error:
        return {
            "success": False,
            "action": "navigation_status",
            "url": "",
            "title": "",
            "error": str(error),
        }


# ============================================================
# SITE DETECTION
# ============================================================

async def detect_site():
    """
    Detect the current website from the active URL.
    """

    page = await _get_page()

    url = page.url.lower()

    if "youtube.com" in url:
        site = "youtube"

    elif "google.com" in url:
        site = "google"

    elif "bing.com" in url:
        site = "bing"

    elif "duckduckgo.com" in url:
        site = "duckduckgo"

    elif "github.com" in url:
        site = "github"

    elif "reddit.com" in url:
        site = "reddit"

    elif "wikipedia.org" in url:
        site = "wikipedia"

    elif "amazon." in url:
        site = "amazon"

    else:
        site = "unknown"

    info = await _page_info(page)

    return {
        "success": True,
        "action": "detect_site",
        "site": site,
        "url": info["url"],
        "title": info["title"],
    }


# ============================================================
# URL CHECK
# ============================================================

async def is_current_url(
    expected_url: str,
):
    """
    Check whether the current URL exactly matches
    the expected URL after removing trailing slashes.
    """

    page = await _get_page()

    expected_url = _clean_url(
        expected_url
    )

    current = page.url

    return {
        "success": True,
        "matches": (
            current.rstrip("/")
            == expected_url.rstrip("/")
        ),
        "current_url": current,
        "expected_url": expected_url,
    }


# ============================================================
# URL VERIFICATION
# ============================================================

async def verify_url(
    expected_url: str,
):
    """
    Verify the current browser URL.

    Uses is_current_url() as the single source
    of truth for URL comparison.
    """

    try:
        if not isinstance(
            expected_url,
            str,
        ):
            return {
                "success": False,
                "verified": False,
                "url": "",
                "expected_url": expected_url,
                "error": (
                    "Expected URL must be a string."
                ),
            }

        expected_url = expected_url.strip()

        if not expected_url:
            return {
                "success": False,
                "verified": False,
                "url": "",
                "expected_url": "",
                "error": (
                    "Expected URL cannot be empty."
                ),
            }

        result = await is_current_url(
            expected_url
        )

        return {
            "success": True,
            "verified": bool(
                result.get(
                    "matches",
                    False,
                )
            ),
            "url": result.get(
                "current_url",
                "",
            ),
            "expected_url": result.get(
                "expected_url",
                expected_url,
            ),
        }

    except Exception as error:
        return {
            "success": False,
            "verified": False,
            "url": "",
            "expected_url": expected_url,
            "error": str(error),
        }


# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    "open_url",
    "google_search",
    "site_search",
    "open_site",
    "go_back",
    "go_forward",
    "refresh",
    "wait_for_navigation",
    "wait_for_url",
    "current_page",
    "navigation_status",
    "detect_site",
    "is_current_url",
    "verify_url",
]