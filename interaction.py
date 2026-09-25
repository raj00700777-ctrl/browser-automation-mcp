import asyncio
import random
from typing import Optional, Union

from browser import browser


# ============================================================
# PAGE ACCESS
# ============================================================

async def _get_page():
    """
    Return the currently active Playwright page.

    Compatibility requirement:
    browser.py must continue exposing:
        await browser.get_page()
    """
    page = await browser.get_page()

    if page is None:
        raise RuntimeError("No active browser page available.")

    return page


# ============================================================
# HUMAN-LIKE TIMING
# ============================================================

async def _human_delay(
    min_ms: int = 150,
    max_ms: int = 450,
):
    """
    Small randomized delay between browser actions.

    This is not a security mechanism.
    It simply prevents every action from occurring at exactly
    the same interval.
    """
    min_ms = max(0, int(min_ms))
    max_ms = max(min_ms, int(max_ms))

    await asyncio.sleep(
        random.uniform(min_ms, max_ms) / 1000
    )


# ============================================================
# LOCATOR HELPERS
# ============================================================

def _normalize_timeout(timeout: int) -> int:
    return max(100, int(timeout))


def _locator(page, selector: str):
    if not isinstance(selector, str) or not selector.strip():
        raise ValueError("Selector cannot be empty.")

    return page.locator(selector).first


async def _ensure_visible(
    locator,
    timeout: int = 10000,
):
    """
    Wait for an element and scroll it into view.
    """
    timeout = _normalize_timeout(timeout)

    await locator.wait_for(
        state="visible",
        timeout=timeout,
    )

    try:
        await locator.scroll_into_view_if_needed(
            timeout=timeout
        )
    except TypeError:
        # Older Playwright versions may not accept timeout here.
        await locator.scroll_into_view_if_needed()


# ============================================================
# CLICK
# ============================================================

async def click_element(
    selector: str,
    timeout: int = 10000,
    force: bool = False,
):
    page = await _get_page()
    locator = _locator(page, selector)

    await _ensure_visible(
        locator,
        timeout=timeout,
    )

    await _human_delay()

    await locator.click(
        timeout=_normalize_timeout(timeout),
        force=bool(force),
    )

    await _human_delay(200, 600)

    return {
        "success": True,
        "action": "click",
        "selector": selector,
        "url": page.url,
    }


# ============================================================
# DOUBLE CLICK
# ============================================================

async def double_click_element(
    selector: str,
    timeout: int = 10000,
):
    page = await _get_page()
    locator = _locator(page, selector)

    await _ensure_visible(
        locator,
        timeout=timeout,
    )

    await _human_delay()

    await locator.dblclick(
        timeout=_normalize_timeout(timeout),
    )

    await _human_delay(200, 600)

    return {
        "success": True,
        "action": "double_click",
        "selector": selector,
        "url": page.url,
    }


# ============================================================
# TYPE TEXT
# ============================================================

async def type_text(
    selector: str,
    text: str,
    clear: bool = True,
    delay_min_ms: int = 20,
    delay_max_ms: int = 80,
    timeout: int = 10000,
):
    page = await _get_page()
    locator = _locator(page, selector)

    await _ensure_visible(
        locator,
        timeout=timeout,
    )

    await locator.click(
        timeout=_normalize_timeout(timeout),
    )

    await _human_delay()

    if clear:
        await locator.fill("")

    text = str(text)

    delay_min_ms = max(0, int(delay_min_ms))
    delay_max_ms = max(
        delay_min_ms,
        int(delay_max_ms),
    )

    for char in text:
        await locator.type(
            char,
            delay=random.randint(
                delay_min_ms,
                delay_max_ms,
            ),
        )

    return {
        "success": True,
        "action": "type",
        "selector": selector,
        "text_length": len(text),
    }


# ============================================================
# FAST TYPE
# ============================================================

async def fill_text(
    selector: str,
    text: str,
    timeout: int = 10000,
):
    """
    Fast text insertion.

    Unlike type_text(), this does not simulate individual
    keystrokes.
    """
    page = await _get_page()
    locator = _locator(page, selector)

    await _ensure_visible(
        locator,
        timeout=timeout,
    )

    await locator.fill(
        str(text),
        timeout=_normalize_timeout(timeout),
    )

    return {
        "success": True,
        "action": "fill",
        "selector": selector,
        "text_length": len(str(text)),
    }


# ============================================================
# PRESS KEY
# ============================================================

async def press_key(
    selector: str,
    key: str,
    timeout: int = 10000,
):
    page = await _get_page()
    locator = _locator(page, selector)

    await _ensure_visible(
        locator,
        timeout=timeout,
    )

    await locator.press(
        key,
        timeout=_normalize_timeout(timeout),
    )

    await _human_delay(200, 500)

    return {
        "success": True,
        "action": "press",
        "selector": selector,
        "key": key,
        "url": page.url,
    }


# ============================================================
# PRESS KEY ON PAGE
# ============================================================

async def press_page_key(
    key: str,
):
    page = await _get_page()

    await page.keyboard.press(key)

    await _human_delay(200, 500)

    return {
        "success": True,
        "action": "page_press",
        "key": key,
        "url": page.url,
    }


# ============================================================
# SCROLL
# ============================================================

async def scroll_page(
    amount: int = 700,
    x: int = 0,
):
    page = await _get_page()

    amount = int(amount)
    x = int(x)

    await page.mouse.wheel(
        x,
        amount,
    )

    await _human_delay(300, 700)

    return {
        "success": True,
        "action": "scroll",
        "amount": amount,
        "x": x,
        "url": page.url,
    }


# ============================================================
# SCROLL TO ELEMENT
# ============================================================

async def scroll_to_element(
    selector: str,
    timeout: int = 10000,
):
    page = await _get_page()
    locator = _locator(page, selector)

    await _ensure_visible(
        locator,
        timeout=timeout,
    )

    return {
        "success": True,
        "action": "scroll_to_element",
        "selector": selector,
        "url": page.url,
    }


# ============================================================
# HOVER
# ============================================================

async def hover_element(
    selector: str,
    timeout: int = 10000,
):
    page = await _get_page()
    locator = _locator(page, selector)

    await _ensure_visible(
        locator,
        timeout=timeout,
    )

    await locator.hover(
        timeout=_normalize_timeout(timeout),
    )

    await _human_delay(200, 500)

    return {
        "success": True,
        "action": "hover",
        "selector": selector,
        "url": page.url,
    }


# ============================================================
# SELECT OPTION
# ============================================================

async def select_option(
    selector: str,
    value: Union[str, list],
    timeout: int = 10000,
):
    page = await _get_page()
    locator = _locator(page, selector)

    await _ensure_visible(
        locator,
        timeout=timeout,
    )

    result = await locator.select_option(
        value=value,
        timeout=_normalize_timeout(timeout),
    )

    await _human_delay(200, 500)

    return {
        "success": True,
        "action": "select",
        "selector": selector,
        "value": value,
        "selected": result,
    }


# ============================================================
# WAIT FOR ELEMENT
# ============================================================

async def wait_for_element(
    selector: str,
    timeout: int = 10000,
):
    page = await _get_page()
    locator = _locator(page, selector)

    await locator.wait_for(
        state="visible",
        timeout=_normalize_timeout(timeout),
    )

    return {
        "success": True,
        "action": "wait_for_element",
        "selector": selector,
    }


# ============================================================
# WAIT FOR STATE
# ============================================================

async def wait_for_state(
    selector: str,
    state: str = "visible",
    timeout: int = 10000,
):
    """
    Generic Playwright locator-state wait.

    Supported states depend on Playwright:
        attached
        detached
        visible
        hidden
    """
    page = await _get_page()
    locator = _locator(page, selector)

    await locator.wait_for(
        state=state,
        timeout=_normalize_timeout(timeout),
    )

    return {
        "success": True,
        "action": "wait_for_state",
        "selector": selector,
        "state": state,
    }


# ============================================================
# GET ELEMENT TEXT
# ============================================================

async def get_element_text(
    selector: str,
    timeout: int = 10000,
):
    page = await _get_page()
    locator = _locator(page, selector)

    await _ensure_visible(
        locator,
        timeout=timeout,
    )

    text = await locator.inner_text()

    return {
        "success": True,
        "action": "get_text",
        "selector": selector,
        "text": text,
    }


# ============================================================
# GET ATTRIBUTE
# ============================================================

async def get_attribute(
    selector: str,
    attribute: str,
    timeout: int = 10000,
):
    page = await _get_page()
    locator = _locator(page, selector)

    await _ensure_visible(
        locator,
        timeout=timeout,
    )

    value = await locator.get_attribute(
        attribute
    )

    return {
        "success": True,
        "action": "get_attribute",
        "selector": selector,
        "attribute": attribute,
        "value": value,
    }


# ============================================================
# CHECK ELEMENT
# ============================================================

async def element_exists(
    selector: str,
):
    page = await _get_page()

    if not isinstance(selector, str) or not selector.strip():
        return {
            "success": False,
            "error": "Selector cannot be empty.",
        }

    try:
        count = await page.locator(selector).count()

        return {
            "success": True,
            "action": "element_exists",
            "selector": selector,
            "exists": count > 0,
            "count": count,
        }

    except Exception as error:
        return {
            "success": False,
            "action": "element_exists",
            "selector": selector,
            "error": str(error),
        }


# ============================================================
# FOCUS ELEMENT
# ============================================================

async def focus_element(
    selector: str,
    timeout: int = 10000,
):
    page = await _get_page()
    locator = _locator(page, selector)

    await _ensure_visible(
        locator,
        timeout=timeout,
    )

    await locator.focus(
        timeout=_normalize_timeout(timeout)
    )

    return {
        "success": True,
        "action": "focus",
        "selector": selector,
    }


# ============================================================
# CLEAR ELEMENT
# ============================================================

async def clear_element(
    selector: str,
    timeout: int = 10000,
):
    page = await _get_page()
    locator = _locator(page, selector)

    await _ensure_visible(
        locator,
        timeout=timeout,
    )

    await locator.fill("")

    return {
        "success": True,
        "action": "clear",
        "selector": selector,
    }


# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    "_get_page",
    "_human_delay",
    "click_element",
    "double_click_element",
    "type_text",
    "fill_text",
    "press_key",
    "press_page_key",
    "scroll_page",
    "scroll_to_element",
    "hover_element",
    "select_option",
    "wait_for_element",
    "wait_for_state",
    "get_element_text",
    "get_attribute",
    "element_exists",
    "focus_element",
    "clear_element",
]