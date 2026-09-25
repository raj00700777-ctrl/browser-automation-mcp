"""
Raj Browser MCP — Cookie / localStorage / sessionStorage Manager
"""

from browser import browser


async def get_cookies(urls: list = None):
    try:
        context = browser.context
        if context is None:
            return {"success": False, "error": "No browser context"}
        cookies = await context.cookies(urls)
        return {"success": True, "cookies": cookies, "count": len(cookies)}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def set_cookies(cookies: list):
    try:
        context = browser.context
        if context is None:
            return {"success": False, "error": "No browser context"}
        await context.add_cookies(cookies)
        return {"success": True, "message": f"Set {len(cookies)} cookies"}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def clear_cookies():
    try:
        context = browser.context
        if context is None:
            return {"success": False, "error": "No browser context"}
        await context.clear_cookies()
        return {"success": True, "message": "Cookies cleared"}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def get_local_storage():
    try:
        page = await browser.get_page()
        data = await page.evaluate("() => Object.entries(localStorage)")
        return {"success": True, "storage": {k: v for k, v in data}, "count": len(data)}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def set_local_storage(key: str, value: str):
    try:
        page = await browser.get_page()
        await page.evaluate("([k, v]) => localStorage.setItem(k, v)", [key, value])
        return {"success": True, "key": key, "value": value}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def clear_local_storage():
    try:
        page = await browser.get_page()
        await page.evaluate("() => localStorage.clear()")
        return {"success": True, "message": "localStorage cleared"}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def get_session_storage():
    try:
        page = await browser.get_page()
        data = await page.evaluate("() => Object.entries(sessionStorage)")
        return {"success": True, "storage": {k: v for k, v in data}, "count": len(data)}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def clear_session_storage():
    try:
        page = await browser.get_page()
        await page.evaluate("() => sessionStorage.clear()")
        return {"success": True, "message": "sessionStorage cleared"}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def clear_all_storage():
    try:
        await clear_cookies()
        await clear_local_storage()
        await clear_session_storage()
        return {"success": True, "message": "All storage cleared (cookies + localStorage + sessionStorage)"}
    except Exception as e:
        return {"success": False, "error": str(e)}