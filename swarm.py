"""
Raj Browser MCP — Swarm Mode (Parallel Multi-Tab Execution)

Every other module in this MCP works through browser.get_page(),
which returns ONE shared "active" tab -- correct for normal
step-by-step automation, but wrong for this: if 5 tasks all call
get_page() at once they'd all fight over the same tab.

Swarm functions instead open their OWN dedicated page per task
directly via browser.context.new_page(), run genuinely
concurrently (asyncio.gather + a concurrency semaphore so you
don't accidentally open 50 tabs at once and choke the machine),
and close each tab when done -- all without touching the shared
"active page" the rest of the MCP is using, so a swarm job never
interferes with whatever single-page automation is happening
elsewhere in the same session.

Three built-in operations, chosen to cover the actual common
"do the same thing across N URLs" use cases:

  swarm_extract()    -- pull text / links / a custom JS result
                         from every URL
  swarm_check()      -- fast yes/no check across many URLs
                         (e.g. "does this page say In Stock?")
  swarm_screenshot()  -- screenshot every URL

All three return one combined report: per-URL results plus a
short summary, so a single glance answers "how'd it go".
"""

import asyncio
import os
import time

from browser import browser


# ============================================================
# CONCURRENCY-SAFE PER-TASK PAGE HANDLING
# ============================================================

async def _ensure_started():
    await browser.start()
    if browser.context is None:
        raise RuntimeError("Browser context is not available even after start().")


async def _open_and_goto(url: str, timeout: int):
    page = await browser.context.new_page()
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=timeout)
        return page, None
    except Exception as error:
        try:
            await page.close()
        except Exception:
            pass
        return None, str(error)


def _summarize(results):
    ok = sum(1 for r in results if r.get("success"))
    return {
        "total": len(results),
        "succeeded": ok,
        "failed": len(results) - ok,
    }


# ============================================================
# SWARM EXTRACT
# ============================================================

async def swarm_extract(
    urls,
    mode: str = "text",
    custom_script: str = None,
    max_concurrency: int = 5,
    timeout: int = 20000,
    text_limit: int = 3000,
):
    """
    Open every URL in its own tab, in parallel (capped by
    max_concurrency), and extract something from each.

    mode:
        "text"        - visible body text (truncated to text_limit)
        "title_url"   - just the final title/URL (fast, e.g. to
                         resolve a batch of redirects)
        "links"       - every link on the page
        "custom_js"   - run custom_script (a JS function like
                         "() => document.title") on each page and
                         collect the return value
    """
    if mode == "custom_js" and not custom_script:
        return {"success": False, "error": "mode='custom_js' requires custom_script."}

    try:
        await _ensure_started()
    except Exception as error:
        return {"success": False, "error": str(error)}

    semaphore = asyncio.Semaphore(max(1, int(max_concurrency)))

    async def _task(url):
        async with semaphore:
            page, error = await _open_and_goto(url, timeout)
            if page is None:
                return {"url": url, "success": False, "error": error}

            try:
                if mode == "text":
                    text = await page.inner_text("body")
                    data = text[:text_limit]

                elif mode == "title_url":
                    data = {"title": await page.title(), "final_url": page.url}

                elif mode == "links":
                    data = await page.locator("a[href]").evaluate_all(
                        "els => els.map(e => ({text: (e.innerText||'').trim(), href: e.href}))"
                    )

                elif mode == "custom_js":
                    data = await page.evaluate(custom_script)

                else:
                    return {"url": url, "success": False, "error": f"Unknown mode '{mode}'."}

                return {"url": url, "success": True, "final_url": page.url, "data": data}

            except Exception as error:
                return {"url": url, "success": False, "error": str(error)}

            finally:
                try:
                    await page.close()
                except Exception:
                    pass

    results = await asyncio.gather(*[_task(u) for u in urls])

    return {
        "success": True,
        "action": "swarm_extract",
        "mode": mode,
        "summary": _summarize(results),
        "results": results,
    }


# ============================================================
# SWARM CHECK (fast yes/no across many URLs)
# ============================================================

async def swarm_check(
    urls,
    text_contains: str = None,
    selector_exists: str = None,
    max_concurrency: int = 5,
    timeout: int = 20000,
):
    """
    Quick parallel check across many URLs -- e.g. "which of these
    10 product pages currently say 'In Stock'?" or "which of
    these pages have a #buy-now button?". At least one of
    text_contains / selector_exists is required.
    """
    if not text_contains and not selector_exists:
        return {
            "success": False,
            "error": "Provide text_contains and/or selector_exists to check for.",
        }

    try:
        await _ensure_started()
    except Exception as error:
        return {"success": False, "error": str(error)}

    semaphore = asyncio.Semaphore(max(1, int(max_concurrency)))

    async def _task(url):
        async with semaphore:
            page, error = await _open_and_goto(url, timeout)
            if page is None:
                return {"url": url, "success": False, "error": error}

            try:
                matched_text = None
                matched_selector = None

                if text_contains:
                    body_text = await page.inner_text("body")
                    matched_text = text_contains.lower() in body_text.lower()

                if selector_exists:
                    matched_selector = await page.locator(selector_exists).count() > 0

                overall = True
                if text_contains is not None:
                    overall = overall and bool(matched_text)
                if selector_exists is not None:
                    overall = overall and bool(matched_selector)

                return {
                    "url": url,
                    "success": True,
                    "matched": overall,
                    "text_contains_found": matched_text,
                    "selector_exists_found": matched_selector,
                }

            except Exception as error:
                return {"url": url, "success": False, "error": str(error)}

            finally:
                try:
                    await page.close()
                except Exception:
                    pass

    results = await asyncio.gather(*[_task(u) for u in urls])
    matched_count = sum(1 for r in results if r.get("matched"))

    return {
        "success": True,
        "action": "swarm_check",
        "summary": {**_summarize(results), "matched": matched_count},
        "results": results,
    }


# ============================================================
# SWARM SCREENSHOT
# ============================================================

async def swarm_screenshot(
    urls,
    max_concurrency: int = 5,
    timeout: int = 20000,
    full_page: bool = False,
):
    """Open every URL in parallel and take a screenshot of each."""
    try:
        await _ensure_started()
    except Exception as error:
        return {"success": False, "error": str(error)}

    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output", "swarm_screenshots")
    os.makedirs(out_dir, exist_ok=True)

    semaphore = asyncio.Semaphore(max(1, int(max_concurrency)))

    async def _task(index, url):
        async with semaphore:
            page, error = await _open_and_goto(url, timeout)
            if page is None:
                return {"url": url, "success": False, "error": error}

            try:
                path = os.path.join(out_dir, f"swarm_{int(time.time())}_{index}.png")
                await page.screenshot(path=path, full_page=full_page)
                return {"url": url, "success": True, "path": path}

            except Exception as error:
                return {"url": url, "success": False, "error": str(error)}

            finally:
                try:
                    await page.close()
                except Exception:
                    pass

    results = await asyncio.gather(*[_task(i, u) for i, u in enumerate(urls)])

    return {
        "success": True,
        "action": "swarm_screenshot",
        "summary": _summarize(results),
        "results": results,
    }


# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    "swarm_extract",
    "swarm_check",
    "swarm_screenshot",
]
