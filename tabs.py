from browser import browser


# ============================================================
# CONFIG
# ============================================================

DEFAULT_TITLE = ""
DEFAULT_URL = ""


# ============================================================
# INTERNAL HELPERS
# ============================================================

async def _get_pages():
    """
    Safely retrieve currently available browser pages.
    """

    pages = await browser.get_pages()

    if pages is None:
        return []

    return list(pages)


async def _page_info(page, index=None):
    """
    Safely collect metadata from a page.
    """

    try:
        url = page.url
    except Exception:
        url = DEFAULT_URL

    try:
        title = await page.title()
    except Exception:
        title = DEFAULT_TITLE

    try:
        closed = page.is_closed()
    except Exception:
        closed = False

    result = {
        "url": url,
        "title": title,
        "closed": closed,
    }

    if index is not None:
        result["index"] = index

    return result


def _valid_index(index, pages):
    """
    Validate a tab index.
    """

    try:
        index = int(index)
    except (TypeError, ValueError):
        return False

    return 0 <= index < len(pages)


# ============================================================
# LIST TABS
# ============================================================

async def list_tabs():
    """
    Return metadata for every currently open browser tab.
    """

    try:
        pages = await _get_pages()

    except Exception as error:
        return {
            "success": False,
            "count": 0,
            "tabs": [],
            "error": str(error),
        }

    tabs = []

    for index, page in enumerate(pages):

        try:
            info = await _page_info(
                page,
                index=index,
            )

            tabs.append(info)

        except Exception as error:

            tabs.append({
                "index": index,
                "url": DEFAULT_URL,
                "title": DEFAULT_TITLE,
                "closed": True,
                "error": str(error),
            })

    return {
        "success": True,
        "count": len(tabs),
        "tabs": tabs,
    }


# ============================================================
# NEW TAB
# ============================================================

async def new_tab(url: str = ""):
    """
    Create a new browser tab.

    Existing API preserved:
        new_tab(url="")
    """

    if url is None:
        url = ""

    if not isinstance(url, str):
        return {
            "success": False,
            "error": "Tab URL must be a string.",
        }

    url = url.strip()

    try:

        page = await browser.new_page(
            url if url else None
        )

        pages = await _get_pages()

        try:
            index = pages.index(page)
        except ValueError:
            index = len(pages) - 1

        info = await _page_info(
            page,
            index=index,
        )

        # Follow this new tab with dialog handling if it was
        # active on whichever tab was open before (see dialogs.py)
        try:
            import dialogs
            await dialogs.reattach_if_active()
        except Exception:
            pass

        return {
            "success": True,
            "action": "new_tab",
            **info,
        }

    except Exception as error:

        return {
            "success": False,
            "action": "new_tab",
            "error": str(error),
        }


# ============================================================
# SWITCH TAB
# ============================================================

async def switch_tab(index: int):
    """
    Bring a specific tab to the foreground.
    """

    try:
        pages = await _get_pages()

    except Exception as error:
        return {
            "success": False,
            "error": str(error),
        }

    if not _valid_index(index, pages):

        return {
            "success": False,
            "error": f"Invalid tab index: {index}",
            "available_tabs": len(pages),
        }

    index = int(index)
    page = pages[index]

    try:

        if page.is_closed():

            return {
                "success": False,
                "error": f"Tab {index} is already closed.",
                "index": index,
            }

    except Exception:
        pass

    try:

        await page.bring_to_front()

        browser.set_active_page(page)

        # Follow the newly-active tab with dialog handling if it
        # was active on whichever tab we just switched away from.
        try:
            import dialogs
            await dialogs.reattach_if_active()
        except Exception:
            pass

        info = await _page_info(
            page,
            index=index,
        )

        return {
            "success": True,
            "action": "switch_tab",
            **info,
        }

    except Exception as error:

        return {
            "success": False,
            "action": "switch_tab",
            "index": index,
            "error": str(error),
        }


# ============================================================
# CLOSE TAB
# ============================================================

async def close_tab(index: int):
    """
    Close a browser tab safely.

    The active tab is not specially protected here; the caller
    decides whether closing it is appropriate.
    """

    try:
        pages = await _get_pages()

    except Exception as error:
        return {
            "success": False,
            "error": str(error),
        }

    if not _valid_index(index, pages):

        return {
            "success": False,
            "error": f"Invalid tab index: {index}",
            "available_tabs": len(pages),
        }

    index = int(index)
    page = pages[index]

    try:

        if page.is_closed():

            return {
                "success": False,
                "error": f"Tab {index} is already closed.",
                "closed_index": index,
            }

    except Exception:
        pass

    try:

        await page.close()

        remaining = await _get_pages()

        return {
            "success": True,
            "action": "close_tab",
            "closed_index": index,
            "remaining_tabs": len(remaining),
        }

    except Exception as error:

        return {
            "success": False,
            "action": "close_tab",
            "closed_index": index,
            "error": str(error),
        }


# ============================================================
# CURRENT TAB
# ============================================================

async def current_tab():
    """
    Return information about the currently active browser page.
    """

    try:

        page = await browser.get_page()

        if page is None:

            return {
                "success": False,
                "index": -1,
                "error": "No active browser page.",
            }

        pages = await _get_pages()

        try:
            index = pages.index(page)
        except ValueError:
            index = -1

        info = await _page_info(
            page,
            index=index,
        )

        return {
            "success": True,
            "action": "current_tab",
            **info,
        }

    except Exception as error:

        return {
            "success": False,
            "index": -1,
            "error": str(error),
        }


# ============================================================
# TAB EXISTS
# ============================================================

async def tab_exists(index: int):
    """
    Check whether a tab index currently exists.
    """

    try:
        pages = await _get_pages()

    except Exception as error:

        return {
            "success": False,
            "exists": False,
            "error": str(error),
        }

    exists = _valid_index(
        index,
        pages,
    )

    return {
        "success": True,
        "exists": exists,
        "index": index,
        "count": len(pages),
    }


# ============================================================
# TAB COUNT
# ============================================================

async def tab_count():
    """
    Return the current number of browser tabs.
    """

    try:
        pages = await _get_pages()

        return {
            "success": True,
            "count": len(pages),
        }

    except Exception as error:

        return {
            "success": False,
            "count": 0,
            "error": str(error),
        }


# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    "list_tabs",
    "new_tab",
    "switch_tab",
    "close_tab",
    "current_tab",
    "tab_exists",
    "tab_count",
]