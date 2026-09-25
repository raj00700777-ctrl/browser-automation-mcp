"""
Raj Browser MCP — File Download Tracking
"""

import os
import fnmatch
import asyncio
from browser import browser

_downloads = []


async def browser_download(url: str, filename: str = None, timeout: int = 60000):
    try:
        page = await browser.get_page()
        async with page.expect_download(timeout=timeout) as download_info:
            await page.goto(url, wait_until="domcontentloaded", timeout=timeout)
        download = await download_info.value
        actual_filename = filename or download.suggested_filename
        path = await download.path()
        entry = {
            "url": url,
            "filename": actual_filename,
            "path": str(path),
            "status": "completed",
            "size": os.path.getsize(path) if os.path.exists(path) else 0,
        }
        _downloads.append(entry)
        return {"success": True, "download": entry}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def browser_wait_download(filename_pattern: str = None, timeout: int = 60000):
    try:
        start = asyncio.get_event_loop().time()
        while True:
            for d in _downloads:
                if filename_pattern is None or fnmatch.fnmatch(d["filename"], filename_pattern):
                    if d["status"] == "completed":
                        return {"success": True, "download": d}
            if (asyncio.get_event_loop().time() - start) * 1000 > timeout:
                return {"success": False, "error": "Download timeout"}
            await asyncio.sleep(0.5)
    except Exception as e:
        return {"success": False, "error": str(e)}


async def browser_list_downloads():
    return {"success": True, "downloads": _downloads, "count": len(_downloads)}


async def browser_download_status(filename: str):
    for d in _downloads:
        if d["filename"] == filename:
            return {"success": True, "download": d}
    return {"success": False, "error": f"Download '{filename}' not found"}


async def browser_clear_downloads():
    _downloads.clear()
    return {"success": True, "message": "Downloads cleared"}