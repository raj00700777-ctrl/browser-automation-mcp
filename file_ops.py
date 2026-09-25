"""
Raj Browser MCP — File Upload + Drag & Drop

File upload uses Playwright's native set_input_files (works for
both visible <input type="file"> and ones hidden behind a styled
button, which is how most real sites build upload UI).

Drag & drop ships two strategies:
  - drag_and_drop(): Playwright's built-in drag_to(), which fires
    real native mouse events. Works for the vast majority of
    sites (HTML5 native DnD + most JS drag libraries).
  - drag_and_drop_manual(): a manual mouse-down / move / mouse-up
    sequence with intermediate steps, for the handful of drag
    libraries that specifically need real incremental mousemove
    events rather than a single drag_to() call.
"""

from typing import List, Union

from browser import browser


# ============================================================
# PAGE ACCESS (same conventions as interaction.py)
# ============================================================

async def _get_page():
    page = await browser.get_page()

    if page is None:
        raise RuntimeError("No active browser page available.")

    return page


def _normalize_timeout(timeout: int) -> int:
    return max(100, int(timeout))


def _locator(page, selector: str):
    if not isinstance(selector, str) or not selector.strip():
        raise ValueError("Selector cannot be empty.")

    return page.locator(selector).first


async def _ensure_visible(locator, timeout: int = 10000):
    timeout = _normalize_timeout(timeout)
    await locator.wait_for(state="attached", timeout=timeout)


# ============================================================
# FILE UPLOAD
# ============================================================

async def upload_file(
    selector: str,
    file_paths: Union[str, List[str]],
    timeout: int = 10000,
):
    """
    Upload one or more local files to an <input type="file">
    matched by `selector`. Works even if the input is visually
    hidden (common styled-button upload UIs), since
    set_input_files does not require the element to be visible.
    """
    try:
        page = await _get_page()
        locator = _locator(page, selector)

        await _ensure_visible(locator, timeout=timeout)

        paths = [file_paths] if isinstance(file_paths, str) else list(file_paths)

        await locator.set_input_files(paths, timeout=_normalize_timeout(timeout))

        return {
            "success": True,
            "action": "upload_file",
            "selector": selector,
            "files": paths,
        }

    except Exception as error:
        return {
            "success": False,
            "action": "upload_file",
            "selector": selector,
            "error": str(error),
        }


async def upload_file_ref(
    ref: str,
    file_paths: Union[str, List[str]],
    timeout: int = 10000,
):
    """Same as upload_file(), but targets an accessibility ref (see accessibility.py)."""
    import accessibility

    check = await accessibility.resolve_ref(ref)
    if not check.get("success"):
        return check

    result = await upload_file(check["selector"], file_paths, timeout=timeout)
    result["ref"] = ref
    return result


async def clear_file_input(selector: str, timeout: int = 10000):
    """Clear a file input (uploads nothing, resets the field)."""
    try:
        page = await _get_page()
        locator = _locator(page, selector)

        await locator.set_input_files([], timeout=_normalize_timeout(timeout))

        return {"success": True, "action": "clear_file_input", "selector": selector}

    except Exception as error:
        return {
            "success": False,
            "action": "clear_file_input",
            "selector": selector,
            "error": str(error),
        }


# ============================================================
# DRAG AND DROP
# ============================================================

async def drag_and_drop(
    source_selector: str,
    target_selector: str,
    timeout: int = 10000,
):
    """
    Drag an element onto another using Playwright's native
    drag_to(). Handles HTML5 drag-and-drop and most JS drag
    libraries in one call.
    """
    try:
        page = await _get_page()

        source = _locator(page, source_selector)
        target = _locator(page, target_selector)

        await _ensure_visible(source, timeout=timeout)
        await _ensure_visible(target, timeout=timeout)

        await source.drag_to(target, timeout=_normalize_timeout(timeout))

        return {
            "success": True,
            "action": "drag_and_drop",
            "source": source_selector,
            "target": target_selector,
        }

    except Exception as error:
        return {
            "success": False,
            "action": "drag_and_drop",
            "source": source_selector,
            "target": target_selector,
            "error": str(error),
        }


async def drag_and_drop_manual(
    source_selector: str,
    target_selector: str,
    steps: int = 15,
    timeout: int = 10000,
):
    """
    Manual mouse-down / incremental-move / mouse-up drag.
    Use this if drag_and_drop() doesn't register on a site whose
    drag library listens for real incremental mousemove events
    rather than a single synthetic drag gesture.
    """
    try:
        page = await _get_page()

        source = _locator(page, source_selector)
        target = _locator(page, target_selector)

        await _ensure_visible(source, timeout=timeout)
        await _ensure_visible(target, timeout=timeout)

        source_box = await source.bounding_box()
        target_box = await target.bounding_box()

        if not source_box or not target_box:
            return {
                "success": False,
                "action": "drag_and_drop_manual",
                "error": "Could not compute bounding box for source or target.",
            }

        sx = source_box["x"] + source_box["width"] / 2
        sy = source_box["y"] + source_box["height"] / 2
        tx = target_box["x"] + target_box["width"] / 2
        ty = target_box["y"] + target_box["height"] / 2

        await page.mouse.move(sx, sy)
        await page.mouse.down()

        steps = max(2, int(steps))
        for i in range(1, steps + 1):
            ix = sx + (tx - sx) * (i / steps)
            iy = sy + (ty - sy) * (i / steps)
            await page.mouse.move(ix, iy)

        await page.mouse.up()

        return {
            "success": True,
            "action": "drag_and_drop_manual",
            "source": source_selector,
            "target": target_selector,
        }

    except Exception as error:
        return {
            "success": False,
            "action": "drag_and_drop_manual",
            "source": source_selector,
            "target": target_selector,
            "error": str(error),
        }


async def drag_and_drop_ref(source_ref: str, target_ref: str, timeout: int = 10000):
    """Same as drag_and_drop(), but targets accessibility refs (see accessibility.py)."""
    import accessibility

    source_check = await accessibility.resolve_ref(source_ref)
    if not source_check.get("success"):
        return source_check

    target_check = await accessibility.resolve_ref(target_ref)
    if not target_check.get("success"):
        return target_check

    result = await drag_and_drop(
        source_check["selector"],
        target_check["selector"],
        timeout=timeout,
    )
    result["source_ref"] = source_ref
    result["target_ref"] = target_ref
    return result


# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    "upload_file",
    "upload_file_ref",
    "clear_file_input",
    "drag_and_drop",
    "drag_and_drop_manual",
    "drag_and_drop_ref",
]
