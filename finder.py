"""
Raj Browser MCP — Smart Element Finder
Natural language description → CSS selector candidates
"""

from browser import browser


async def find_element(description: str):
    """Find element using natural language description."""
    try:
        page = await browser.get_page()
        desc = description.lower().strip()
        candidates = []
        seen_selectors = set()

        # Try to find by common patterns
        if any(w in desc for w in ["button", "click", "submit", "ok", "done", "save", "login", "sign"]):
            buttons = await page.query_selector_all(
                "button, [role='button'], input[type='submit'], a.btn, .button, [type='submit']"
            )
            for btn in buttons:
                text = await btn.inner_text() or await btn.get_attribute("value") or ""
                if any(w in text.lower() for w in desc.split()):
                    selector = await _get_selector(btn)
                    if selector and selector not in seen_selectors:
                        seen_selectors.add(selector)
                        candidates.append({"type": "button", "text": text.strip()[:100], "selector": selector})

        if any(w in desc for w in ["input", "field", "box", "search", "text", "email", "password", "type"]):
            inputs = await page.query_selector_all(
                "input, textarea, select, [contenteditable='true']"
            )
            for inp in inputs:
                placeholder = await inp.get_attribute("placeholder") or ""
                name = await inp.get_attribute("name") or ""
                label = await inp.get_attribute("aria-label") or ""
                if any(w in (placeholder + name + label).lower() for w in desc.split()):
                    selector = await _get_selector(inp)
                    if selector and selector not in seen_selectors:
                        seen_selectors.add(selector)
                        candidates.append({"type": "input", "placeholder": placeholder, "selector": selector})

        if any(w in desc for w in ["link", "href", "navigate", "go to", "open"]):
            links = await page.query_selector_all("a")
            for link in links:
                text = await link.inner_text() or ""
                href = await link.get_attribute("href") or ""
                if any(w in (text + href).lower() for w in desc.split()):
                    selector = await _get_selector(link)
                    if selector and selector not in seen_selectors:
                        seen_selectors.add(selector)
                        candidates.append({"type": "link", "text": text.strip()[:100], "href": href, "selector": selector})

        # Fallback: search visible text in common interactive tags only (NOT *)
        if not candidates:
            fallback_tags = "a, button, input, textarea, select, [role='button'], [role='link'], label, h1, h2, h3, h4, h5, h6"
            elements = await page.query_selector_all(fallback_tags)
            for el in elements:
                text = await el.inner_text() or ""
                if len(text) > 0 and any(w in text.lower() for w in desc.split()[:3]):
                    selector = await _get_selector(el)
                    if selector and selector not in seen_selectors:
                        seen_selectors.add(selector)
                        tag = await el.evaluate("el => el.tagName.toLowerCase()")
                        candidates.append({"type": tag, "text": text.strip()[:100], "selector": selector})
                        if len(candidates) >= 10:
                            break

        return {
            "success": True,
            "description": description,
            "candidates": candidates[:5],
            "count": len(candidates),
            "best_match": candidates[0] if candidates else None,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


async def _get_selector(element):
    """Generate a best-effort unique CSS selector for an element."""
    try:
        # Try ID first (most unique)
        el_id = await element.get_attribute("id")
        if el_id:
            # Check if ID is actually unique on page
            return f"#{el_id}"

        # Try name attribute
        name = await element.get_attribute("name")
        if name:
            return f"[name='{name}']"

        # Try aria-label
        aria = await element.get_attribute("aria-label")
        if aria:
            return f"[aria-label='{aria}']"

        # Try placeholder
        placeholder = await element.get_attribute("placeholder")
        if placeholder:
            return f"[placeholder='{placeholder}']"

        # Try class — but only if it looks semantic (not utility classes)
        classes = await element.get_attribute("class")
        if classes:
            cls_list = classes.split()
            # Prefer semantic class names over utility classes
            semantic = [c for c in cls_list if len(c) > 4 and not c.startswith(("bg-", "text-", "p-", "m-", "w-", "h-", "flex", "grid", "block", "inline"))]
            if semantic:
                return f".{semantic[0]}"
            # Fallback to first class if nothing semantic found
            return f".{cls_list[0]}"

        # Fallback: tag name
        tag = await element.evaluate("el => el.tagName.toLowerCase()")
        return tag
    except:
        return None