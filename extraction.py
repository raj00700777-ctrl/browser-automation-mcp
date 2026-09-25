"""
Raj Browser MCP - Advanced Extraction Engine

Purpose:
    Extract structured information from the active browser page.

Compatibility:
    Existing function names are preserved so server.py, planner.py,
    browser.py and other modules can continue using the same interface.
"""

from browser import browser


# ============================================================
# INTERNAL HELPERS
# ============================================================

async def _get_page():
    page = await browser.get_page()

    if page is None:
        raise RuntimeError("No active browser page available.")

    return page


async def _safe_title(page):
    try:
        return await page.title()
    except Exception:
        return ""


async def _safe_body_text(page, limit=30000):
    try:
        text = await page.locator("body").inner_text()
        return text[:limit]
    except Exception:
        return ""


async def _safe_count(locator):
    try:
        return await locator.count()
    except Exception:
        return 0


async def _page_info(page):
    return {
        "url": page.url,
        "title": await _safe_title(page),
    }


# ============================================================
# PAGE TEXT
# ============================================================

async def read_page():
    """
    Read visible page text.
    """

    page = await _get_page()

    text = await _safe_body_text(page, 30000)
    info = await _page_info(page)

    return {
        "success": True,
        "url": info["url"],
        "title": info["title"],
        "text": text,
        "text_length": len(text),
    }


# ============================================================
# HEADINGS
# ============================================================

async def get_headings():
    """
    Extract all semantic headings.
    """

    page = await _get_page()

    items = await page.locator(
        "h1, h2, h3, h4, h5, h6"
    ).evaluate_all(
        """els => els.map(e => ({
            tag: e.tagName.toLowerCase(),
            text: (e.innerText || e.textContent || '').trim(),
            id: e.id || '',
            aria: e.getAttribute('aria-label') || ''
        })).filter(x => x.text)"""
    )

    return {
        "success": True,
        "count": len(items),
        "headings": items,
    }


# ============================================================
# LINKS
# ============================================================

async def get_links(limit=500):
    """
    Extract links with useful metadata.
    """

    page = await _get_page()

    try:
        limit = max(1, int(limit))
    except Exception:
        limit = 500

    items = await page.locator("a").evaluate_all(
        """(els, limit) => els.map(e => ({
            text: (e.innerText || e.textContent || '').trim(),
            href: e.href || '',
            target: e.target || '',
            rel: e.rel || '',
            aria: e.getAttribute('aria-label') || '',
            title: e.getAttribute('title') || ''
        }))
        .filter(x =>
            x.text ||
            x.href ||
            x.aria ||
            x.title
        )
        .slice(0, limit)""",
        limit,
    )

    return {
        "success": True,
        "count": len(items),
        "links": items,
    }


# ============================================================
# BUTTONS
# ============================================================

async def get_buttons():
    """
    Extract buttons and button-like controls.
    """

    page = await _get_page()

    items = await page.locator(
        "button, input[type=button], input[type=submit], "
        "[role=button]"
    ).evaluate_all(
        """els => els.map(e => ({
            text: (e.innerText || e.textContent || e.value || '').trim(),
            type: e.type || '',
            aria: e.getAttribute('aria-label') || '',
            title: e.getAttribute('title') || '',
            disabled: !!e.disabled
        }))
        .filter(x =>
            x.text ||
            x.aria ||
            x.title
        )
        .slice(0, 300)"""
    )

    return {
        "success": True,
        "count": len(items),
        "buttons": items,
    }


# ============================================================
# INPUTS
# ============================================================

async def get_inputs():
    """
    Extract text fields, search fields, selects and textareas.
    """

    page = await _get_page()

    items = await page.locator(
        "input, textarea, select"
    ).evaluate_all(
        """els => els.map(e => ({
            tag: e.tagName.toLowerCase(),
            type: e.type || '',
            name: e.name || '',
            id: e.id || '',
            placeholder: e.placeholder || '',
            value: e.value || '',
            aria: e.getAttribute('aria-label') || '',
            role: e.getAttribute('role') || '',
            autocomplete: e.getAttribute('autocomplete') || '',
            disabled: !!e.disabled
        }))"""
    )

    return {
        "success": True,
        "count": len(items),
        "inputs": items,
    }


# ============================================================
# FORMS
# ============================================================

async def get_forms():
    """
    Extract forms and their controls.
    """

    page = await _get_page()

    items = await page.locator("form").evaluate_all(
        """forms => forms.map(f => ({
            action: f.action || '',
            method: (f.method || 'get').toLowerCase(),
            id: f.id || '',
            name: f.name || '',
            text: (f.innerText || '').trim().slice(0, 5000),
            controls: [...f.querySelectorAll(
                'input, textarea, select, button'
            )].map(e => ({
                tag: e.tagName.toLowerCase(),
                type: e.type || '',
                name: e.name || '',
                placeholder: e.placeholder || '',
                aria: e.getAttribute('aria-label') || ''
            })).slice(0, 100)
        }))"""
    )

    return {
        "success": True,
        "count": len(items),
        "forms": items,
    }


# ============================================================
# GENERIC TEXT EXTRACTION
# ============================================================

async def extract_text(selector: str):
    """
    Extract text from any CSS selector.
    """

    page = await _get_page()

    if not isinstance(selector, str) or not selector.strip():
        return {
            "success": False,
            "error": "Selector cannot be empty",
        }

    locator = page.locator(selector)
    count = await locator.count()

    if count == 0:
        return {
            "success": False,
            "error": "Element not found",
            "selector": selector,
        }

    texts = await locator.all_inner_texts()

    return {
        "success": True,
        "selector": selector,
        "count": len(texts),
        "text": texts,
    }


# ============================================================
# FIND TEXT
# ============================================================

async def find_text(text: str):
    """
    Find visible text on the current page.
    """

    page = await _get_page()

    if not isinstance(text, str) or not text.strip():
        return {
            "success": False,
            "error": "Text cannot be empty",
        }

    locator = page.get_by_text(text, exact=False)
    count = await locator.count()

    return {
        "success": True,
        "text": text,
        "matches": count,
    }


# ============================================================
# TABLES
# ============================================================

async def extract_tables():
    """
    Extract HTML tables as structured rows.
    """

    page = await _get_page()

    tables = await page.locator("table").evaluate_all(
        """tables => tables.map((table, tableIndex) => {
            const rows = [...table.querySelectorAll('tr')];

            return {
                index: tableIndex,
                caption: table.querySelector('caption')
                    ? table.querySelector('caption').innerText.trim()
                    : '',
                rows: rows.map(row =>
                    [...row.querySelectorAll('th, td')]
                        .map(cell => (cell.innerText || '').trim())
                ).filter(row => row.length > 0)
            };
        })"""
    )

    return {
        "success": True,
        "count": len(tables),
        "tables": tables,
    }


# ============================================================
# IMAGES
# ============================================================

async def extract_images(limit=500):
    """
    Extract image URLs and metadata.
    """

    page = await _get_page()

    try:
        limit = max(1, int(limit))
    except Exception:
        limit = 500

    images = await page.locator("img").evaluate_all(
        """(imgs, limit) => imgs.map(img => ({
            src: img.currentSrc || img.src || '',
            alt: img.alt || '',
            title: img.title || '',
            width: img.naturalWidth || img.width || 0,
            height: img.naturalHeight || img.height || 0,
            loading: img.loading || ''
        }))
        .filter(x => x.src)
        .slice(0, limit)""",
        limit,
    )

    return {
        "success": True,
        "count": len(images),
        "images": images,
    }


# ============================================================
# VIDEOS
# ============================================================

async def extract_videos(limit=200):
    """
    Extract native video elements and video-like links.
    """

    page = await _get_page()

    try:
        limit = max(1, int(limit))
    except Exception:
        limit = 200

    native_videos = await page.locator(
        "video"
    ).evaluate_all(
        """(videos, limit) => videos.map(v => ({
            src: v.currentSrc || v.src || '',
            poster: v.poster || '',
            width: v.videoWidth || v.width || 0,
            height: v.videoHeight || v.height || 0,
            duration: Number.isFinite(v.duration)
                ? v.duration
                : null
        })).slice(0, limit)""",
        limit,
    )

    video_links = await page.locator("a").evaluate_all(
        """(links, limit) => links.map(a => ({
            text: (a.innerText || a.textContent || '').trim(),
            href: a.href || ''
        }))
        .filter(x =>
            x.href &&
            (
                x.href.includes('youtube.com/watch') ||
                x.href.includes('youtu.be/') ||
                x.href.includes('/video/') ||
                x.href.includes('/videos/')
            )
        )
        .slice(0, limit)""",
        limit,
    )

    return {
        "success": True,
        "native_video_count": len(native_videos),
        "native_videos": native_videos,
        "video_link_count": len(video_links),
        "video_links": video_links,
    }


# ============================================================
# ARTICLE / CONTENT CARDS
# ============================================================

async def extract_articles(limit=200):
    """
    Extract semantic article elements and common content cards.
    """

    page = await _get_page()

    try:
        limit = max(1, int(limit))
    except Exception:
        limit = 200

    articles = await page.locator(
        "article, [role=article]"
    ).evaluate_all(
        """(els, limit) => els.map((e, index) => ({
            index,
            tag: e.tagName.toLowerCase(),
            text: (e.innerText || e.textContent || '').trim().slice(0, 5000),
            links: [...e.querySelectorAll('a')].map(a => ({
                text: (a.innerText || a.textContent || '').trim(),
                href: a.href || ''
            })).filter(x => x.text || x.href).slice(0, 30),
            headings: [...e.querySelectorAll(
                'h1, h2, h3, h4, h5, h6'
            )].map(h => ({
                tag: h.tagName.toLowerCase(),
                text: (h.innerText || '').trim()
            })).filter(x => x.text).slice(0, 20)
        }))
        .filter(x => x.text)
        .slice(0, limit)""",
        limit,
    )

    return {
        "success": True,
        "count": len(articles),
        "articles": articles,
    }


# ============================================================
# SEARCH-LIKE ELEMENTS
# ============================================================

async def extract_search_inputs():
    """
    Find inputs that appear to be search fields.
    """

    page = await _get_page()

    items = await page.locator(
        "input, textarea, [contenteditable=true]"
    ).evaluate_all(
        """els => els.map(e => {
            const text = (
                e.placeholder ||
                e.getAttribute('aria-label') ||
                e.name ||
                e.id ||
                ''
            ).toLowerCase();

            const role = (
                e.getAttribute('role') || ''
            ).toLowerCase();

            const type = (
                e.type || ''
            ).toLowerCase();

            const isSearch =
                type === 'search' ||
                role === 'searchbox' ||
                text.includes('search') ||
                text.includes('query') ||
                text.includes('find');

            return {
                tag: e.tagName.toLowerCase(),
                type: e.type || '',
                name: e.name || '',
                id: e.id || '',
                placeholder: e.placeholder || '',
                aria: e.getAttribute('aria-label') || '',
                value: e.value || '',
                is_search_candidate: isSearch
            };
        }).filter(x => x.is_search_candidate)"""
    )

    return {
        "success": True,
        "count": len(items),
        "search_inputs": items,
    }


# ============================================================
# SEMANTIC RESULT EXTRACTION
# ============================================================

async def search_results(limit=100):
    """
    Extract likely search-result items.

    Important:
        This does NOT blindly treat every <a> as a search result.

    It looks for:
        - semantic result containers
        - article/result roles
        - common result classes
        - links with meaningful surrounding text

    It also returns a fallback link list when no semantic result
    containers are found.
    """

    page = await _get_page()

    try:
        limit = max(1, int(limit))
    except Exception:
        limit = 100

    # --------------------------------------------------------
    # Tier 1: strict, known-good semantic result containers.
    # This alone covers Google, YouTube (ytd-video-renderer etc.),
    # and most standard result/article/listitem markup, without
    # any wildcard matching -- so ad wrappers, player overlays,
    # and share-dialog elements that merely CONTAIN the word
    # "video" or "result" in a class name never get pulled in
    # here.
    # --------------------------------------------------------

    STRICT_SELECTOR = """
        [role="article"],
        [role="listitem"],
        article,
        .g,
        .tF2Cxc,
        .MjjYud,
        .result,
        .search-result,
        .search-result-item,
        .result-item,
        .product,
        .video-card,
        ytd-video-renderer,
        ytd-playlist-renderer,
        ytd-channel-renderer,
        ytd-rich-item-renderer,
        ytd-compact-video-renderer
    """

    # Tier 2: broad wildcard match -- only used if tier 1 finds
    # nothing at all, since these patterns are loose enough to
    # also catch non-result UI (ad slots, video-player chrome,
    # share panels) on some sites.
    WILDCARD_SELECTOR = """
        [class*="video"],
        [class*="result"]
    """

    EXTRACT_JS = """(els, limit) => {
            const seen = new Set();
            const output = [];

            // Elements that are clearly UI chrome, not a result,
            // even when they matched the wildcard tier.
            const NOISE_HINTS = [
                'share', 'unmute', 'mute', 'playbutton', 'play-button',
                'overlay', 'skeleton', 'shimmer', 'spinner', 'tooltip',
                'ad-slot', 'adslot', 'promoted', 'sponsor',
            ];

            function looksLikeNoise(e) {
                const cls = (e.className || '').toString().toLowerCase();
                return NOISE_HINTS.some(hint => cls.includes(hint));
            }

            for (const e of els) {
                if (looksLikeNoise(e)) {
                    continue;
                }

                const text = (
                    e.innerText ||
                    e.textContent ||
                    ''
                ).trim();

                const links = [...e.querySelectorAll('a')]
                    .map(a => ({
                        text: (
                            a.innerText ||
                            a.textContent ||
                            ''
                        ).trim(),
                        href: a.href || ''
                    }))
                    .filter(x => x.text || x.href)
                    .slice(0, 20);

                if (!text || links.length === 0) {
                    continue;
                }

                const primary = links.find(
                    x => x.href && x.text
                ) || links[0];

                const key = (
                    primary.href +
                    '|' +
                    primary.text
                );

                if (seen.has(key)) {
                    continue;
                }

                seen.add(key);

                output.push({
                    title: primary.text,
                    href: primary.href,
                    text: text.slice(0, 5000),
                    links
                });

                if (output.length >= limit) {
                    break;
                }
            }

            return output;
        }"""

    result_containers = await page.locator(STRICT_SELECTOR).evaluate_all(
        EXTRACT_JS, limit,
    )

    if not result_containers:
        result_containers = await page.locator(WILDCARD_SELECTOR).evaluate_all(
            EXTRACT_JS, limit,
        )

    # --------------------------------------------------------
    # Fallback: meaningful links
    # --------------------------------------------------------

    if not result_containers:
        fallback = await page.locator("a").evaluate_all(
            """(els, limit) => {
                const seen = new Set();
                const output = [];

                for (const a of els) {
                    const text = (
                        a.innerText ||
                        a.textContent ||
                        ''
                    ).trim();

                    const href = a.href || '';

                    if (!text || !href) {
                        continue;
                    }

                    if (
                        href.startsWith('javascript:') ||
                        href.startsWith('#')
                    ) {
                        continue;
                    }

                    const key = href + '|' + text;

                    if (seen.has(key)) {
                        continue;
                    }

                    seen.add(key);

                    output.push({
                        title: text,
                        href,
                        text
                    });

                    if (output.length >= limit) {
                        break;
                    }
                }

                return output;
            }""",
            limit,
        )

        result_containers = fallback

    info = await _page_info(page)

    return {
        "success": True,
        "url": info["url"],
        "title": info["title"],
        "count": len(result_containers),
        "results": result_containers,
    }


# ============================================================
# PAGE METADATA
# ============================================================

async def get_metadata():
    """
    Extract useful document metadata.
    """

    page = await _get_page()

    metadata = await page.locator("head").evaluate(
        """head => ({
            title: document.title || '',
            description:
                document.querySelector(
                    'meta[name="description"]'
                )?.content || '',
            keywords:
                document.querySelector(
                    'meta[name="keywords"]'
                )?.content || '',
            canonical:
                document.querySelector(
                    'link[rel="canonical"]'
                )?.href || '',
            og_title:
                document.querySelector(
                    'meta[property="og:title"]'
                )?.content || '',
            og_description:
                document.querySelector(
                    'meta[property="og:description"]'
                )?.content || '',
            og_image:
                document.querySelector(
                    'meta[property="og:image"]'
                )?.content || '',
            og_url:
                document.querySelector(
                    'meta[property="og:url"]'
                )?.content || '',
            language:
                document.documentElement.lang || ''
        })"""
    )

    return {
        "success": True,
        "url": page.url,
        "metadata": metadata,
    }


# ============================================================
# PAGE ANALYSIS
# ============================================================

async def analyze_page():
    """
    High-level structured analysis of the current page.
    """

    page = await _get_page()

    info = await _page_info(page)

    headings = await page.locator(
        "h1, h2, h3, h4, h5, h6"
    ).evaluate_all(
        """els => els.map(e => ({
            tag: e.tagName.toLowerCase(),
            text: (e.innerText || e.textContent || '').trim()
        })).filter(x => x.text).slice(0, 150)"""
    )

    buttons = await page.locator(
        "button, [role=button], input[type=submit], input[type=button]"
    ).evaluate_all(
        """els => els.map(e => ({
            text: (
                e.innerText ||
                e.textContent ||
                e.value ||
                ''
            ).trim(),
            aria: e.getAttribute('aria-label') || '',
            title: e.getAttribute('title') || '',
            disabled: !!e.disabled
        }))
        .filter(x => x.text || x.aria || x.title)
        .slice(0, 300)"""
    )

    links = await page.locator("a").evaluate_all(
        """els => els.map(e => ({
            text: (
                e.innerText ||
                e.textContent ||
                ''
            ).trim(),
            href: e.href || '',
            aria: e.getAttribute('aria-label') || ''
        }))
        .filter(x => x.text || x.href || x.aria)
        .slice(0, 500)"""
    )

    inputs = await page.locator(
        "input, textarea, select"
    ).evaluate_all(
        """els => els.map(e => ({
            tag: e.tagName.toLowerCase(),
            type: e.type || '',
            name: e.name || '',
            id: e.id || '',
            placeholder: e.placeholder || '',
            aria: e.getAttribute('aria-label') || '',
            value: e.value || ''
        }))"""
    )

    body_text = await _safe_body_text(page, 30000)

    return {
        "success": True,
        "url": info["url"],
        "title": info["title"],
        "headings": headings,
        "heading_count": len(headings),
        "buttons": buttons,
        "button_count": len(buttons),
        "links": links,
        "link_count": len(links),
        "inputs": inputs,
        "input_count": len(inputs),
        "visible_text": body_text,
        "visible_text_length": len(body_text),
    }


# ============================================================
# PAGE STATE
# ============================================================

async def page_state():
    """
    Compact state snapshot useful for planner/agent decisions.
    """

    page = await _get_page()

    info = await _page_info(page)

    body_text = await _safe_body_text(page, 12000)

    heading_count = await _safe_count(
        page.locator("h1, h2, h3, h4, h5, h6")
    )

    link_count = await _safe_count(
        page.locator("a")
    )

    input_count = await _safe_count(
        page.locator("input, textarea, select")
    )

    button_count = await _safe_count(
        page.locator(
            "button, [role=button], "
            "input[type=submit], input[type=button]"
        )
    )

    return {
        "success": True,
        "url": info["url"],
        "title": info["title"],
        "heading_count": heading_count,
        "link_count": link_count,
        "input_count": input_count,
        "button_count": button_count,
        "visible_text_preview": body_text[:5000],
    }


# ============================================================
# PAGE SOURCE
# ============================================================

async def page_source():
    """
    Return current page HTML.
    """

    page = await _get_page()

    html = await page.content()

    return {
        "success": True,
        "url": page.url,
        "html": html[:100000],
        "html_length": len(html),
        "truncated": len(html) > 100000,
    }


# ============================================================
# ELEMENT EXISTENCE
# ============================================================

async def element_exists(selector: str):
    """
    Check whether a CSS selector exists.
    """

    page = await _get_page()

    if not isinstance(selector, str) or not selector.strip():
        return {
            "success": False,
            "error": "Selector cannot be empty",
        }

    locator = page.locator(selector)
    count = await locator.count()

    return {
        "success": True,
        "selector": selector,
        "exists": count > 0,
        "count": count,
    }


# ============================================================
# ATTRIBUTE EXTRACTION
# ============================================================

async def get_attribute(
    selector: str,
    attribute: str,
):
    """
    Extract an attribute from the first matching element.
    """

    page = await _get_page()

    if not selector or not attribute:
        return {
            "success": False,
            "error": "Selector and attribute are required",
        }

    locator = page.locator(selector)
    count = await locator.count()

    if count == 0:
        return {
            "success": False,
            "error": "Element not found",
            "selector": selector,
        }

    value = await locator.first.get_attribute(attribute)

    return {
        "success": True,
        "selector": selector,
        "attribute": attribute,
        "value": value,
    }


# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    "read_page",
    "get_headings",
    "get_links",
    "get_buttons",
    "get_inputs",
    "get_forms",
    "extract_text",
    "find_text",
    "extract_tables",
    "extract_images",
    "extract_videos",
    "extract_articles",
    "extract_search_inputs",
    "search_results",
    "get_metadata",
    "analyze_page",
    "page_state",
    "page_source",
    "element_exists",
    "get_attribute",
]