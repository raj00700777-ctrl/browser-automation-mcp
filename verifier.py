"""
Raj Browser MCP — Action Verifier
Verify that an action produced the expected result.
"""

import asyncio
from browser import browser

_VALID_CHECKS = {"url", "title", "element", "text"}


async def verify_action(check_type: str, expected: str, timeout: int = 10000):
    # Early validation
    if check_type not in _VALID_CHECKS:
        return {
            "success": False,
            "error": f"Invalid check_type: '{check_type}'. Must be one of: {', '.join(sorted(_VALID_CHECKS))}",
        }

    if not expected or not isinstance(expected, str):
        return {
            "success": False,
            "error": "expected must be a non-empty string",
        }

    try:
        page = await browser.get_page()
        start = asyncio.get_event_loop().time()

        while True:
            if check_type == "url":
                if expected in page.url or page.url == expected:
                    return {"success": True, "check": "url", "expected": expected, "actual": page.url, "matched": True}
            elif check_type == "title":
                title = await page.title()
                if expected in title or title == expected:
                    return {"success": True, "check": "title", "expected": expected, "actual": title, "matched": True}
            elif check_type == "element":
                count = await page.locator(expected).count()
                if count > 0:
                    return {"success": True, "check": "element", "expected": expected, "found": count, "matched": True}
            elif check_type == "text":
                body = await page.locator("body").inner_text()
                if expected in body:
                    return {"success": True, "check": "text", "expected": expected, "matched": True}

            if (asyncio.get_event_loop().time() - start) * 1000 > timeout:
                actual = page.url
                if check_type == "title":
                    actual = await page.title()
                elif check_type == "text":
                    actual = (await page.locator("body").inner_text())[:200]
                return {"success": False, "check": check_type, "expected": expected, "actual": actual, "matched": False, "error": "Timeout"}

            await asyncio.sleep(0.5)
    except Exception as e:
        return {"success": False, "error": str(e)}