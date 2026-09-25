"""
Raj Browser MCP — Smart Content Extraction (Readability-style, and beyond)

Strips ads, nav, banners, and boilerplate to leave the actual
article/content -- using the classic Readability text-density
heuristic (score = text_length - link_text_length, penalize
nav/ad/footer-like class names, boost article/content-like ones)
PLUS extras most "readability" implementations skip:

  - transparency: reports exactly which elements were stripped
    and why, and a confidence score for the extraction itself
    (not just "here's some text, trust me")
  - structured headings hierarchy (not just flat text)
  - images WITH alt text, scoped to the extracted article only
  - estimated reading time
"""

import re

from browser import browser


async def _get_page():
    page = await browser.get_page()
    if page is None:
        raise RuntimeError("No active browser page available.")
    return page


_EXTRACT_JS = r"""
() => {
    const NOISE_PATTERN = /nav|footer|header|sidebar|advert|banner|comment|social|share|cookie|popup|menu|masthead|subscribe|newsletter|promo/i;
    const CONTENT_PATTERN = /article|content|main|post|story|entry/i;

    function textDensityScore(el) {
        const text = (el.innerText || '').trim();
        if (text.length < 80) return -1;

        const linkText = Array.from(el.querySelectorAll('a'))
            .map(a => (a.innerText || '').trim())
            .join('').length;

        let score = text.length - linkText * 1.5;

        const signature = ((el.className || '') + ' ' + (el.id || '')).toLowerCase();
        if (NOISE_PATTERN.test(signature)) score -= 500;
        if (CONTENT_PATTERN.test(signature)) score += 300;
        if (el.tagName === 'ARTICLE') score += 400;

        // Paragraph density is a strong real-content signal.
        const paragraphCount = el.querySelectorAll('p').length;
        score += paragraphCount * 20;

        return score;
    }

    const candidates = Array.from(document.querySelectorAll('article, main, div, section'));
    let best = null, bestScore = -Infinity, secondScore = -Infinity;

    for (const el of candidates) {
        const score = textDensityScore(el);
        if (score > bestScore) {
            secondScore = bestScore;
            bestScore = score;
            best = el;
        } else if (score > secondScore) {
            secondScore = score;
        }
    }

    if (!best || bestScore <= 0) {
        return { found: false };
    }

    // Confidence: reflects absolute evidence that this is real
    // content (paragraph density, text volume) -- NOT a comparison
    // against the runner-up, since a legitimately content-heavy
    // page (e.g. Wikipedia, with a large infobox/TOC alongside the
    // article) can have a second-best candidate that's ALSO
    // genuinely substantial, which would make a margin-based score
    // misleadingly low even when the winning extraction is correct.
    const confidence = Math.max(0, Math.min(1, bestScore / 2500));

    // Strip noise elements WITHIN the winning container before
    // reading its text, and count/collect what got removed for
    // transparency.
    const clone = best.cloneNode(true);
    const removedTags = ['script', 'style', 'iframe', 'noscript'];
    let removedCount = 0;
    const removedSelectors = [];

    clone.querySelectorAll(removedTags.join(',')).forEach(e => { e.remove(); removedCount++; });
    clone.querySelectorAll('*').forEach(e => {
        const sig = ((e.className || '') + ' ' + (e.id || '')).toString().toLowerCase();
        if (NOISE_PATTERN.test(sig)) {
            removedSelectors.push(e.tagName.toLowerCase() + (e.className ? '.' + String(e.className).split(' ')[0] : ''));
            e.remove();
            removedCount++;
        }
    });

    const headings = Array.from(best.querySelectorAll('h1, h2, h3, h4, h5, h6')).map(h => ({
        level: parseInt(h.tagName[1]),
        text: (h.innerText || '').trim(),
    })).filter(h => h.text);

    const images = Array.from(best.querySelectorAll('img')).map(img => ({
        src: img.src, alt: img.alt || null,
    })).filter(img => img.src).slice(0, 30);

    const title = document.querySelector('h1')?.innerText?.trim()
        || document.title || null;

    const mainText = (clone.innerText || '').trim();
    const wordCount = mainText.split(/\s+/).filter(Boolean).length;

    return {
        found: true,
        title,
        main_text: mainText.slice(0, 20000),
        headings,
        images,
        word_count: wordCount,
        confidence: Math.round(confidence * 100) / 100,
        removed_element_count: removedCount,
        removed_samples: removedSelectors.slice(0, 10),
        container_tag: best.tagName.toLowerCase(),
    };
}
"""


async def extract_readable_content():
    """
    Extract the actual article/content from the current page,
    stripping ads/nav/banners/boilerplate -- with a confidence
    score and a transparent report of exactly what was removed
    (not a black-box "here's some text").
    """
    try:
        page = await _get_page()
        result = await page.evaluate(_EXTRACT_JS)

        if not result.get("found"):
            return {"success": False, "error": "No confident main-content region found on this page."}

        reading_time_min = max(1, round(result["word_count"] / 220))

        return {
            "success": True,
            "action": "extract_readable_content",
            "url": page.url,
            "title": result["title"],
            "text": result["main_text"],
            "word_count": result["word_count"],
            "estimated_reading_time_minutes": reading_time_min,
            "headings": result["headings"],
            "images": result["images"],
            "confidence": result["confidence"],
            "noise_removed": {
                "element_count": result["removed_element_count"],
                "samples": result["removed_samples"],
            },
        }

    except Exception as error:
        return {"success": False, "error": str(error)}


__all__ = ["extract_readable_content"]
