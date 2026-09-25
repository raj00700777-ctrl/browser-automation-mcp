# ============================================================
# RAJ BROWSER MCP V4
# ============================================================

import os
import sys
import asyncio
import traceback
from typing import List, Union


# ============================================================
# WINDOWS UTF-8 FIX
# ============================================================

os.environ["PYTHONUTF8"] = "1"
os.environ["PYTHONIOENCODING"] = "utf-8"

try:
    sys.stdout.reconfigure(
        encoding="utf-8",
        errors="replace",
    )
except Exception:
    pass

try:
    sys.stderr.reconfigure(
        encoding="utf-8",
        errors="replace",
    )
except Exception:
    pass


# ============================================================
# MCP
# ============================================================

from mcp.server import MCPServer


# ============================================================
# BROWSER
# ============================================================

from browser import browser


# ============================================================
# NAVIGATION
# ============================================================

from navigation import (
    open_url,
    google_search,
    site_search,
    open_site,
    go_back,
    go_forward,
    refresh,
    wait_for_navigation,
    wait_for_url,
    current_page,
    detect_site,
    is_current_url,
    navigation_status,
    verify_url,
)


# ============================================================
# INTERACTION
# ============================================================

from interaction import (
    click_element,
    type_text,
    press_key,
    scroll_page,
    hover_element,
    select_option,
    wait_for_element,
)


# ============================================================
# VISION
# ============================================================

from vision import (
    screenshot,
    viewport_screenshot,
    page_state,
)


# ============================================================
# EXTRACTION
# ============================================================

from extraction import (
    read_page,
    get_headings,
    get_links,
    get_buttons,
    get_inputs,
    get_forms,
    extract_text,
    find_text,
    extract_tables,
    extract_images,
    analyze_page,
    search_results,
    page_source,
    extract_videos,
    extract_articles,
    extract_search_inputs,
    get_metadata,
)


# ============================================================
# TABS
# ============================================================

from tabs import (
    list_tabs,
    new_tab,
    switch_tab,
    close_tab,
    current_tab,
    tab_exists,
    tab_count,
)


# ============================================================
# RESEARCH
# ============================================================

from research import (
    research_topic,
    collect_open_pages,
    research_summary,
    deep_research,
)


# ============================================================
# WORKFLOWS
# ============================================================

from workflows import (
    save_workflow,
    load_workflow,
    list_workflows,
    delete_workflow,
    workflow_exists as _workflow_exists,
)


# ============================================================
# SAFETY
# ============================================================

from safety import (
    safety_check,
    is_safe,
    requires_confirmation,
    is_blocked,
)


# ============================================================
# RECOVERY
# ============================================================

from recovery import (
    RecoveryEngine,
)


# ============================================================
# PLANNER
# ============================================================

from planner import (
    create_planner,
)

# ============================================================
# NEW FEATURE MODULES
# ============================================================

from finder import find_element
from verifier import verify_action
from downloads import (
    browser_download as _browser_download,
    browser_wait_download as _browser_wait_download,
    browser_list_downloads as _browser_list_downloads,
    browser_download_status as _browser_download_status,
    browser_clear_downloads as _browser_clear_downloads,
)
from storage import (
    get_cookies,
    set_cookies,
    clear_cookies,
    get_local_storage,
    set_local_storage,
    clear_local_storage,
    get_session_storage,
    clear_session_storage,
    clear_all_storage,
)
from network import (
    network_start_monitoring,
    network_stop_monitoring,
    network_get_log,
    network_get_failures,
    network_clear_log,
    network_wait_for_idle,
    network_block_urls,
    network_mock_response,
    network_unblock_urls,
)
from console import (
    console_start_monitoring,
    console_stop_monitoring,
    console_get_logs,
    console_get_errors,
    console_clear,
    console_has_errors,
)
from snapshot import dom_snapshot, interactive_snapshot
from accessibility import (
    browser_snapshot,
    resolve_ref,
    click_ref,
    type_ref,
    hover_ref,
)
from dialogs import (
    dialog_start_handling,
    dialog_stop_handling,
    dialog_get_pending,
    dialog_accept,
    dialog_dismiss,
    dialog_get_log,
    dialog_clear_log,
)
from file_ops import (
    upload_file,
    upload_file_ref,
    clear_file_input,
    drag_and_drop,
    drag_and_drop_manual,
    drag_and_drop_ref,
)
from js_exec import (
    execute_js,
    execute_js_on_element,
    execute_js_on_ref,
)
from frames import (
    list_frames,
    frame_click,
    frame_type,
    frame_hover,
    frame_get_text,
    frame_extract_links,
)
from human import (
    human_move_mouse,
    human_click,
    human_type,
    human_scroll,
    human_scroll_to_element,
    human_idle,
)
from device import (
    list_device_presets,
    emulate_device,
    reset_device_emulation,
    set_viewport,
    set_geolocation,
    clear_geolocation,
    throttle_network,
    reset_network_throttle,
    export_pdf,
)
from history import (
    log_action,
    get_history,
    get_last_action,
    clear_history,
    get_statistics,
)
from codegen import (
    get_recordable_actions,
    generate_playwright_code,
    export_codegen_script,
)
from site_memory import (
    smart_find,
    remember_selector,
    recall_selector,
    record_outcome,
    list_known_domains,
    get_domain_memory,
    forget_domain,
    forget_selector,
)
from swarm import (
    swarm_extract,
    swarm_check,
    swarm_screenshot,
)
from timeline import (
    timeline_start,
    timeline_get_mutations,
    timeline_clear_mutations,
    timeline_checkpoint,
    timeline_list_checkpoints,
    timeline_clear_checkpoints,
    timeline_diff,
)
from site_diagnose import diagnose_site
from memoize import (
    list_fastpaths,
    review_fastpath,
    approve_fastpath,
    reject_fastpath,
)
from form_intelligence import (
    analyze_form,
    fill_form_from_profile,
    get_supported_purposes,
)
from readability import extract_readable_content
from vision import element_screenshot, multi_element_screenshot
from performance import (
    get_performance_metrics,
    get_resource_timing,
    get_slow_resources,
    get_runtime_metrics,
)



# ============================================================
# MCP SERVER
# ============================================================

mcp = MCPServer(
    "Raj Browser MCP"
)


# ============================================================
# RECOVERY ENGINE
# ============================================================

recovery = RecoveryEngine(
    browser=browser,
    max_retries=3,
    base_delay=0.75,
)


# ============================================================
# BROWSER
# ============================================================

@mcp.tool()
async def browser_start():

    try:

        await browser.start()

        # Production safety: auto-accept native dialogs by default
        # so a stray alert()/confirm() on any page never hangs
        # automation. Can be overridden anytime via
        # browser_dialog_start(mode="manual"/"dismiss").
        try:
            await dialog_start_handling(mode="accept")
        except Exception:
            pass

        return {
            "success": True,
            "message": "Raj Browser started",
        }

    except Exception as e:

        return {
            "success": False,
            "error": str(e),
        }


@mcp.tool()
async def browser_close():

    try:

        await browser.close()

        return {
            "success": True,
            "message": "Browser closed",
        }

    except Exception as e:

        return {
            "success": False,
            "error": str(e),
        }


@mcp.tool()
async def browser_status():

    try:

        pages = await browser.get_pages()

        result_pages = []

        for i, page in enumerate(
            pages
        ):

            try:
                title = await page.title()
            except Exception:
                title = ""

            result_pages.append(
                {
                    "index": i,
                    "title": title,
                    "url": page.url,
                }
            )

        return {
            "success": True,
            "running": (
                browser.context
                is not None
            ),
            "tabs": len(pages),
            "pages": result_pages,
        }

    except Exception as e:

        return {
            "success": False,
            "error": str(e),
        }


# ============================================================
# NAVIGATION
# ============================================================

@mcp.tool()
async def navigate(
    url: str,
):
    return await open_url(url)


@mcp.tool()
async def search_google(
    query: str,
):
    return await google_search(
        query
    )


@mcp.tool()
async def search_site(
    site: str,
    query: str,
):
    return await site_search(site, query)


@mcp.tool()
async def open_website(
    site: str,
):
    return await open_site(site)


@mcp.tool()
async def browser_current_page():
    return await current_page()


@mcp.tool()
async def browser_detect_site():
    return await detect_site()


@mcp.tool()
async def browser_navigation_status():
    return await navigation_status()


@mcp.tool()
async def browser_verify_url(
    expected_url: str,
):
    return await verify_url(
        expected_url,
    )


@mcp.tool()
async def back():
    return await go_back()


@mcp.tool()
async def forward():
    return await go_forward()


@mcp.tool()
async def refresh_page():
    return await refresh()


@mcp.tool()
async def wait(
    seconds: float = 2,
):
    return await wait_for_navigation(
        seconds
    )


# ============================================================
# INTERACTION
# ============================================================

@mcp.tool()
async def browser_click(
    selector: str,
):
    return await click_element(
        selector
    )


@mcp.tool()
async def browser_type(
    selector: str,
    text: str,
):
    return await type_text(
        selector,
        text,
    )


@mcp.tool()
async def browser_press(
    selector: str,
    key: str,
):
    return await press_key(
        selector,
        key,
    )


@mcp.tool()
async def browser_scroll(
    amount: int = 700,
):
    return await scroll_page(
        amount
    )


@mcp.tool()
async def browser_hover(
    selector: str,
):
    return await hover_element(
        selector
    )


@mcp.tool()
async def browser_select(
    selector: str,
    value: str,
):
    return await select_option(
        selector,
        value,
    )


@mcp.tool()
async def browser_wait_for(
    selector: str,
):
    return await wait_for_element(
        selector
    )


# ============================================================
# PAGE OBSERVATION
# ============================================================

@mcp.tool()
async def browser_observe():
    return await analyze_page()


@mcp.tool()
async def browser_read():
    return await read_page()


@mcp.tool()
async def browser_state():
    return await page_state()


@mcp.tool()
async def browser_find_text(
    text: str,
):
    return await find_text(
        text
    )


# ============================================================
# PAGE STRUCTURE
# ============================================================

@mcp.tool()
async def browser_headings():
    return await get_headings()


@mcp.tool()
async def browser_links():
    return await get_links()


@mcp.tool()
async def browser_buttons():
    return await get_buttons()


@mcp.tool()
async def browser_inputs():
    return await get_inputs()


@mcp.tool()
async def browser_forms():
    return await get_forms()


@mcp.tool()
async def browser_search_results():
    return await search_results()


# ============================================================
# EXTRACTION
# ============================================================

@mcp.tool()
async def browser_extract(
    selector: str,
):
    return await extract_text(
        selector
    )


@mcp.tool()
async def browser_extract_tables():
    return await extract_tables()


@mcp.tool()
async def browser_extract_images():
    return await extract_images()


@mcp.tool()
async def browser_source():
    return await page_source()


# ============================================================
# VISION
# ============================================================

@mcp.tool()
async def browser_screenshot(
    path: str = None,
):
    return await screenshot(
        path
    )


@mcp.tool()
async def browser_viewport_screenshot():
    return await viewport_screenshot()


# ============================================================
# TABS
# ============================================================

@mcp.tool()
async def browser_tabs():
    return await list_tabs()


@mcp.tool()
async def browser_new_tab(
    url: str = "",
):
    return await new_tab(
        url
    )


@mcp.tool()
async def browser_switch_tab(
    index: int,
):
    return await switch_tab(
        index
    )


@mcp.tool()
async def browser_close_tab(
    index: int,
):
    return await close_tab(
        index
    )


@mcp.tool()
async def browser_current_tab():
    return await current_tab()


# ============================================================
# RESEARCH
# ============================================================

@mcp.tool()
async def browser_research(
    topic: str,
):
    return await research_topic(
        topic
    )


@mcp.tool()
async def browser_collect_research():
    return await collect_open_pages()


@mcp.tool()
async def browser_deep_research(topic: str, tab_count: int = 3, timeout: int = 20000):
    """
    Open `tab_count` REAL, VISIBLE browser tabs -- each a genuine
    article/page that actually discusses `topic` in detail (found
    via a real Google search, filtered to real content links, not
    search-engine/ad URLs), scrolled to and centered on the exact
    section where the topic is mentioned, with that section's text
    extracted. Unlike browser_research (which opens search-RESULT
    pages), this follows through to the actual content.
    """
    return await deep_research(topic, tab_count=tab_count, timeout=timeout)


# ============================================================
# WORKFLOWS
# ============================================================

@mcp.tool()
async def workflow_save(
    name: str,
    steps: list,
):
    return save_workflow(
        name,
        steps,
    )


@mcp.tool()
async def workflow_load(
    name: str,
):
    return load_workflow(
        name
    )


@mcp.tool()
async def workflow_list():
    return list_workflows()


# ============================================================
# SAFETY
# ============================================================

@mcp.tool()
async def check_action_safety(
    action: str,
):
    return safety_check(action)


@mcp.tool()
async def check_is_safe(action: str):
    return is_safe(action)


@mcp.tool()
async def check_requires_confirmation(action: str):
    return requires_confirmation(action)


@mcp.tool()
async def check_is_blocked(action: str):
    return is_blocked(action)


@mcp.tool()
async def workflow_delete(name: str):
    return delete_workflow(name)


@mcp.tool()
async def workflow_exists(name: str):
    return _workflow_exists(name)




# ============================================================
# SMART ELEMENT FINDER
# ============================================================

@mcp.tool()
async def browser_find_element(description: str):
    """Find an element using natural language description."""
    return await find_element(description)


# ============================================================
# ACTION VERIFIER
# ============================================================

@mcp.tool()
async def browser_verify_action(check_type: str, expected: str, timeout: int = 10000):
    """Verify that an action produced the expected result (url | title | element | text)."""
    return await verify_action(check_type, expected, timeout)


# ============================================================
# DOWNLOADS
# ============================================================

@mcp.tool()
async def browser_download(url: str, filename: str = None, timeout: int = 60000):
    """Trigger a file download from a URL and track it."""
    return await _browser_download(url, filename, timeout)


@mcp.tool()
async def browser_wait_download(filename_pattern: str = None, timeout: int = 60000):
    """Wait for a download to complete. Optionally match by filename pattern."""
    return await _browser_wait_download(filename_pattern, timeout)


@mcp.tool()
async def browser_list_downloads():
    """List all tracked downloads with their status."""
    return await _browser_list_downloads()


@mcp.tool()
async def browser_download_status(filename: str):
    """Get the status of a specific tracked download."""
    return await _browser_download_status(filename)


@mcp.tool()
async def browser_clear_downloads():
    """Clear the download tracking list."""
    return await _browser_clear_downloads()


# ============================================================
# STORAGE (Cookies + localStorage + sessionStorage)
# ============================================================

@mcp.tool()
async def browser_get_cookies(urls: list = None):
    """Get cookies for the current context. Optionally filter by URLs."""
    return await get_cookies(urls)


@mcp.tool()
async def browser_set_cookies(cookies: list):
    """Set cookies in the browser context. Pass a list of cookie dicts."""
    return await set_cookies(cookies)


@mcp.tool()
async def browser_clear_cookies():
    """Clear all cookies for the current browser context."""
    return await clear_cookies()


@mcp.tool()
async def browser_get_local_storage():
    """Get all items from localStorage of the current page."""
    return await get_local_storage()


@mcp.tool()
async def browser_set_local_storage(key: str, value: str):
    """Set a key-value pair in localStorage of the current page."""
    return await set_local_storage(key, value)


@mcp.tool()
async def browser_clear_local_storage():
    """Clear all items from localStorage of the current page."""
    return await clear_local_storage()


@mcp.tool()
async def browser_get_session_storage():
    """Get all items from sessionStorage of the current page."""
    return await get_session_storage()


@mcp.tool()
async def browser_clear_session_storage():
    """Clear all items from sessionStorage of the current page."""
    return await clear_session_storage()


@mcp.tool()
async def browser_clear_all_storage():
    """Clear cookies, localStorage, and sessionStorage in one go."""
    return await clear_all_storage()


# ============================================================
# NETWORK MONITORING
# ============================================================

@mcp.tool()
async def browser_network_start():
    """Start monitoring network requests and responses."""
    return await network_start_monitoring()


@mcp.tool()
async def browser_network_stop():
    """Stop monitoring network requests/responses and detach listeners."""
    return await network_stop_monitoring()


@mcp.tool()
async def browser_network_log():
    """Get the captured network log since monitoring started."""
    return await network_get_log()


@mcp.tool()
async def browser_network_failures():
    """Get only failed network requests from the captured log."""
    return await network_get_failures()


@mcp.tool()
async def browser_network_clear():
    """Clear the network monitoring log."""
    return await network_clear_log()


@mcp.tool()
async def browser_network_wait_idle(timeout: int = 30000):
    """Wait until network becomes idle (no requests for 500ms)."""
    return await network_wait_for_idle(timeout)


@mcp.tool()
async def browser_network_block(patterns: Union[str, List[str]]):
    """Block URL glob pattern(s) (e.g. '**/*.png', '**/ads/**') -- matching requests are aborted."""
    return await network_block_urls(patterns)


@mcp.tool()
async def browser_network_mock(
    pattern: str, status: int = 200, body: str = "", content_type: str = "application/json", headers: dict = None
):
    """Mock every request matching a URL glob pattern with a fixed response."""
    return await network_mock_response(pattern, status=status, body=body, content_type=content_type, headers=headers)


@mcp.tool()
async def browser_network_unblock(patterns: Union[str, List[str]] = None):
    """Remove active block/mock routes. Omit patterns to remove all."""
    return await network_unblock_urls(patterns)


# ============================================================
# CONSOLE MONITORING
# ============================================================

@mcp.tool()
async def browser_console_start():
    """Start monitoring browser console logs and JS errors (native, navigation-persistent)."""
    return await console_start_monitoring()


@mcp.tool()
async def browser_console_stop():
    """Stop console monitoring and detach listeners."""
    return await console_stop_monitoring()


@mcp.tool()
async def browser_console_logs(level: str = None, limit: int = 200):
    """
    Get captured console messages (log/info/warning/error/debug).
    Optionally filter by level, e.g. level="warning".
    """
    return await console_get_logs(level=level, limit=limit)


@mcp.tool()
async def browser_console_errors(limit: int = 200):
    """Get console.error() calls AND uncaught exceptions/unhandled rejections, combined."""
    return await console_get_errors(limit=limit)


@mcp.tool()
async def browser_console_clear():
    """Clear the captured console log buffer."""
    return await console_clear()


@mcp.tool()
async def browser_console_has_errors():
    """Quick check: returns True if any console errors were captured."""
    return await console_has_errors()


# ============================================================
# DOM SNAPSHOT
# ============================================================

@mcp.tool()
async def browser_dom_snapshot():
    """Get a full DOM snapshot of the current page as a structured tree."""
    return await dom_snapshot()


@mcp.tool()
async def browser_interactive_snapshot():
    """Get a flat list of all interactive elements with selectors and coordinates."""
    return await interactive_snapshot()


# ============================================================
# ACCESSIBILITY SNAPSHOT (REF-BASED, HUMAN-LIKE)
# ============================================================

@mcp.tool()
async def browser_a11y_snapshot():
    """
    Build a ref-based accessibility tree of the current page (role,
    name, state for every meaningful element). Each element gets a
    stable ref like "e12" that can be passed to browser_click_ref /
    browser_type_ref instead of a fragile CSS selector.
    """
    return await browser_snapshot()


@mcp.tool()
async def browser_click_ref(ref: str, timeout: int = 10000, force: bool = False):
    """Click an element by its accessibility ref (from browser_a11y_snapshot)."""
    return await click_ref(ref, timeout=timeout, force=force)


@mcp.tool()
async def browser_type_ref(ref: str, text: str, clear: bool = True, timeout: int = 10000):
    """Type text into an element by its accessibility ref."""
    return await type_ref(ref, text, clear=clear, timeout=timeout)


@mcp.tool()
async def browser_hover_ref(ref: str, timeout: int = 10000):
    """Hover an element by its accessibility ref."""
    return await hover_ref(ref, timeout=timeout)


# ============================================================
# DIALOG HANDLING (alert / confirm / prompt / beforeunload)
# ============================================================

@mcp.tool()
async def browser_dialog_start(mode: str = "accept", auto_timeout: int = 20):
    """
    Start handling native JS dialogs (alert/confirm/prompt).
    mode: "accept" (default, auto-OK), "dismiss" (auto-cancel),
    or "manual" (you resolve each one via browser_dialog_accept /
    browser_dialog_dismiss; auto-dismissed after auto_timeout
    seconds if left unresolved so the page can never hang forever).
    """
    return await dialog_start_handling(mode=mode, auto_timeout=auto_timeout)


@mcp.tool()
async def browser_dialog_stop():
    """Stop dialog handling and detach the listener."""
    return await dialog_stop_handling()


@mcp.tool()
async def browser_dialog_pending():
    """Get info about the currently open (unresolved) manual-mode dialog, if any."""
    return await dialog_get_pending()


@mcp.tool()
async def browser_dialog_accept(prompt_text: str = None):
    """Accept the pending manual-mode dialog, optionally supplying prompt text."""
    return await dialog_accept(prompt_text=prompt_text)


@mcp.tool()
async def browser_dialog_dismiss():
    """Dismiss (cancel) the pending manual-mode dialog."""
    return await dialog_dismiss()


@mcp.tool()
async def browser_dialog_log(limit: int = 50):
    """Get the history of dialogs that have appeared on the page."""
    return await dialog_get_log(limit=limit)


@mcp.tool()
async def browser_dialog_clear_log():
    """Clear the dialog history."""
    return await dialog_clear_log()


# ============================================================
# FILE UPLOAD + DRAG & DROP
# ============================================================

@mcp.tool()
async def browser_upload_file(selector: str, file_paths, timeout: int = 10000):
    """Upload one or more local files to a file input (works even if visually hidden)."""
    return await upload_file(selector, file_paths, timeout=timeout)


@mcp.tool()
async def browser_upload_file_ref(ref: str, file_paths, timeout: int = 10000):
    """Upload files to a file input targeted by accessibility ref."""
    return await upload_file_ref(ref, file_paths, timeout=timeout)


@mcp.tool()
async def browser_clear_file_input(selector: str, timeout: int = 10000):
    """Clear a file input field."""
    return await clear_file_input(selector, timeout=timeout)


@mcp.tool()
async def browser_drag_and_drop(source_selector: str, target_selector: str, timeout: int = 10000):
    """Drag source element onto target element (native Playwright drag_to)."""
    return await drag_and_drop(source_selector, target_selector, timeout=timeout)


@mcp.tool()
async def browser_drag_and_drop_manual(
    source_selector: str, target_selector: str, steps: int = 15, timeout: int = 10000
):
    """Drag source onto target with a manual incremental mouse path (for stubborn drag libraries)."""
    return await drag_and_drop_manual(source_selector, target_selector, steps=steps, timeout=timeout)


@mcp.tool()
async def browser_drag_and_drop_ref(source_ref: str, target_ref: str, timeout: int = 10000):
    """Drag source onto target, both targeted by accessibility ref."""
    return await drag_and_drop_ref(source_ref, target_ref, timeout=timeout)


# ============================================================
# GENERIC JAVASCRIPT EXECUTION
# ============================================================

@mcp.tool()
async def browser_execute_js(script: str, arg=None, timeout: int = 10000):
    """
    Run arbitrary JavaScript in the page context. script should be
    a JS function like "() => document.title" or "(x) => x * 2".
    Pass arg to feed a single value into the function form.
    """
    return await execute_js(script, arg=arg, timeout=timeout)


@mcp.tool()
async def browser_execute_js_on_element(selector: str, script: str, timeout: int = 10000):
    """Run JS with a specific element bound as the argument, e.g. "(el) => el.href"."""
    return await execute_js_on_element(selector, script, timeout=timeout)


@mcp.tool()
async def browser_execute_js_on_ref(ref: str, script: str, timeout: int = 10000):
    """Run JS with an accessibility-ref-targeted element bound as the argument."""
    return await execute_js_on_ref(ref, script, timeout=timeout)


# ============================================================
# IFRAME / FRAME SUPPORT
# ============================================================

@mcp.tool()
async def browser_list_frames():
    """List all frames on the page (main + iframes) with URL, name, and a suggested selector."""
    return await list_frames()


@mcp.tool()
async def browser_frame_click(iframe_selector: str, inner_selector: str, timeout: int = 10000):
    """Click an element inside an iframe. iframe_selector targets the <iframe> tag itself."""
    return await frame_click(iframe_selector, inner_selector, timeout=timeout)


@mcp.tool()
async def browser_frame_type(
    iframe_selector: str, inner_selector: str, text: str, clear: bool = True, timeout: int = 10000
):
    """Type text into an element inside an iframe."""
    return await frame_type(iframe_selector, inner_selector, text, clear=clear, timeout=timeout)


@mcp.tool()
async def browser_frame_hover(iframe_selector: str, inner_selector: str, timeout: int = 10000):
    """Hover an element inside an iframe."""
    return await frame_hover(iframe_selector, inner_selector, timeout=timeout)


@mcp.tool()
async def browser_frame_get_text(iframe_selector: str, inner_selector: str = "body", timeout: int = 10000):
    """Get visible text from inside an iframe."""
    return await frame_get_text(iframe_selector, inner_selector, timeout=timeout)


@mcp.tool()
async def browser_frame_extract_links(iframe_selector: str):
    """Extract all links from inside an iframe."""
    return await frame_extract_links(iframe_selector)


# ============================================================
# HUMAN-LIKE INTERACTION (bot-detection resistant)
# ============================================================

@mcp.tool()
async def browser_human_move_mouse(x: float, y: float, duration_ms: int = None):
    """Move the mouse to (x, y) along a curved, variable-speed path instead of teleporting."""
    return await human_move_mouse(x, y, duration_ms=duration_ms)


@mcp.tool()
async def browser_human_click(
    selector: str = None, ref: str = None, timeout: int = 10000, double: bool = False, button: str = "left"
):
    """
    Click like a human: curved mouse approach, randomized landing
    point inside the element, hover-check pause, variable hold
    duration. Target with selector= or ref= (accessibility ref).
    """
    return await human_click(selector=selector, ref=ref, timeout=timeout, double=double, button=button)


@mcp.tool()
async def browser_human_type(
    selector: str = None,
    ref: str = None,
    text: str = "",
    profile: str = "average",
    typo_rate: float = 0.03,
    clear: bool = True,
    click_first: bool = True,
    pre_delay: bool = True,
    timeout: int = 10000,
):
    """
    Type like a human: variable per-character delay by profile
    ("fast"/"average"/"slow"/"hunt_and_peck"/"mobile_thumb"),
    word-boundary hesitation, and low-rate realistic typo-then-
    correct simulation. Set typo_rate=0 for passwords/OTP fields.
    """
    return await human_type(
        selector=selector, ref=ref, text=text, profile=profile, typo_rate=typo_rate,
        clear=clear, click_first=click_first, pre_delay=pre_delay, timeout=timeout,
    )


@mcp.tool()
async def browser_human_scroll(direction: str = "down", amount: int = None, reading_pause: bool = True):
    """Scroll in incremental human-like ticks with an optional mid-scroll reading pause."""
    return await human_scroll(direction=direction, amount=amount, reading_pause=reading_pause)


@mcp.tool()
async def browser_human_scroll_to_element(selector: str = None, ref: str = None, timeout: int = 10000):
    """Scroll a specific element into view using incremental human-like scrolling."""
    return await human_scroll_to_element(selector=selector, ref=ref, timeout=timeout)


@mcp.tool()
async def browser_human_idle(min_ms: int = 300, max_ms: int = 1200):
    """Small random mouse jitter + pause, so the cursor is never frozen for long stretches."""
    return await human_idle(min_ms=min_ms, max_ms=max_ms)


# ============================================================
# DEVICE EMULATION / GEOLOCATION / NETWORK THROTTLE / PDF
# ============================================================

@mcp.tool()
async def browser_list_device_presets():
    """List available device emulation presets (iPhone, Pixel, iPad, desktop, etc.)."""
    return await list_device_presets()


@mcp.tool()
async def browser_emulate_device(preset: str):
    """
    Make the current page report itself as a real device (viewport,
    pixel ratio, touch, user agent) -- same cookies/login preserved.
    Use browser_list_device_presets() to see available presets.
    """
    return await emulate_device(preset)


@mcp.tool()
async def browser_reset_device_emulation():
    """Clear device emulation and restore normal desktop viewport."""
    return await reset_device_emulation()


@mcp.tool()
async def browser_set_viewport(width: int, height: int):
    """Plain viewport resize -- no device/UA spoofing."""
    return await set_viewport(width, height)


@mcp.tool()
async def browser_set_geolocation(latitude: float, longitude: float, accuracy: float = 50):
    """Override the page's reported GPS location."""
    return await set_geolocation(latitude, longitude, accuracy=accuracy)


@mcp.tool()
async def browser_clear_geolocation():
    """Clear geolocation override and permissions."""
    return await clear_geolocation()


@mcp.tool()
async def browser_throttle_network(profile: str = "fast_3g"):
    """Simulate network conditions: 'offline' | 'slow_3g' | 'fast_3g' | '4g' | 'no_throttle'."""
    return await throttle_network(profile)


@mcp.tool()
async def browser_reset_network_throttle():
    """Remove network throttling."""
    return await reset_network_throttle()


@mcp.tool()
async def browser_export_pdf(
    path: str = None,
    format: str = "A4",
    landscape: bool = False,
    print_background: bool = True,
    scale: float = 1.0,
    page_ranges: str = "",
    display_header_footer: bool = False,
    header_template: str = "",
    footer_template: str = "",
):
    """Export the current page as a PDF with full print options."""
    return await export_pdf(
        path=path, format=format, landscape=landscape, print_background=print_background,
        scale=scale, page_ranges=page_ranges, display_header_footer=display_header_footer,
        header_template=header_template, footer_template=footer_template,
    )


# ============================================================
# HISTORY / ACTION LOGGING
# ============================================================

@mcp.tool()
async def browser_log_action(action: str, details: dict = None):
    """Manually log an action into the history for tracking/debugging."""
    return log_action(action, details)


@mcp.tool()
async def browser_get_history(limit: int = 100):
    """Get the recent action history with timestamps."""
    return get_history(limit)


@mcp.tool()
async def browser_last_action():
    """Get the most recently logged action."""
    return get_last_action()


@mcp.tool()
async def browser_clear_history():
    """Clear the action history log."""
    return clear_history()


@mcp.tool()
async def browser_statistics():
    """Get statistics about actions performed (counts by category)."""
    return get_statistics()


# ============================================================
# CODEGEN (recorded history -> standalone Playwright script)
# ============================================================

@mcp.tool()
async def browser_codegen_supported_actions():
    """List which recorded action names codegen can translate into Playwright code."""
    return await get_recordable_actions()


@mcp.tool()
async def browser_codegen_generate(limit: int = 500):
    """Generate a standalone Playwright Python script from the recorded action history."""
    return await generate_playwright_code(limit=limit)


@mcp.tool()
async def browser_codegen_export(path: str = None, limit: int = 500):
    """Generate the script and save it to a .py file (defaults under output/codegen/)."""
    return await export_codegen_script(path=path, limit=limit)


# ============================================================
# SELF-IMPROVING SITE MEMORY
# ============================================================

@mcp.tool()
async def browser_smart_find(key: str, description: str, domain: str = None, timeout: int = 10000):
    """
    Find an element using persistent per-domain memory first, then
    fall back to natural-language discovery (finder.py) and learn
    the result for next time. key is a short label like
    "search_box" or "login_button" to remember it by; description
    is the natural-language fallback used the first time (or if
    the site changed and the remembered selector no longer works).
    """
    return await smart_find(key, description, domain=domain, timeout=timeout)


@mcp.tool()
async def browser_memory_remember(domain: str, key: str, selector: str, role: str = None, name: str = None):
    """Manually save a selector into site memory for domain+key."""
    return await remember_selector(domain, key, selector, role=role, name=name)


@mcp.tool()
async def browser_memory_recall(domain: str, key: str):
    """Look up a remembered selector for domain+key (without verifying it on a live page)."""
    return await recall_selector(domain, key)


@mcp.tool()
async def browser_memory_record_outcome(domain: str, key: str, success: bool):
    """Report whether a remembered/discovered selector actually worked, so memory can self-correct over time."""
    return await record_outcome(domain, key, success)


@mcp.tool()
async def browser_memory_list_domains():
    """List every domain the MCP has learned selectors for."""
    return await list_known_domains()


@mcp.tool()
async def browser_memory_get_domain(domain: str):
    """Get everything remembered for a specific domain."""
    return await get_domain_memory(domain)


@mcp.tool()
async def browser_memory_forget_domain(domain: str):
    """Forget everything remembered for a domain."""
    return await forget_domain(domain)


@mcp.tool()
async def browser_memory_forget_key(domain: str, key: str):
    """Forget one specific remembered selector for a domain."""
    return await forget_selector(domain, key)

# ============================================================
# SWARM MODE (parallel multi-tab execution)
# ============================================================

@mcp.tool()
async def browser_swarm_extract(
    urls: List[str], mode: str = "text", custom_script: str = None, max_concurrency: int = 5,
    timeout: int = 20000, text_limit: int = 3000,
):
    """
    Open every URL in its own tab in parallel and extract from
    each. mode: "text" | "title_url" | "links" | "custom_js"
    (custom_script required for custom_js, e.g. "() => document.title").
    """
    return await swarm_extract(
        urls, mode=mode, custom_script=custom_script, max_concurrency=max_concurrency,
        timeout=timeout, text_limit=text_limit,
    )


@mcp.tool()
async def browser_swarm_check(
    urls: List[str], text_contains: str = None, selector_exists: str = None,
    max_concurrency: int = 5, timeout: int = 20000,
):
    """Fast parallel yes/no check across many URLs (e.g. which pages say 'In Stock')."""
    return await swarm_check(
        urls, text_contains=text_contains, selector_exists=selector_exists,
        max_concurrency=max_concurrency, timeout=timeout,
    )


@mcp.tool()
async def browser_swarm_screenshot(urls: List[str], max_concurrency: int = 5, timeout: int = 20000, full_page: bool = False):
    """Open every URL in parallel and screenshot each."""
    return await swarm_screenshot(urls, max_concurrency=max_concurrency, timeout=timeout, full_page=full_page)


# ============================================================
# TIME-TRAVEL DOM DEBUGGING
# ============================================================

@mcp.tool()
async def browser_timeline_start():
    """Start the always-on DOM mutation timeline (navigation-persistent)."""
    return await timeline_start()


@mcp.tool()
async def browser_timeline_mutations(since: float = None, limit: int = 200):
    """Get the recorded DOM mutation log, optionally only entries after a unix timestamp."""
    return await timeline_get_mutations(since=since, limit=limit)


@mcp.tool()
async def browser_timeline_clear_mutations():
    """Clear the recorded DOM mutation log."""
    return await timeline_clear_mutations()


@mcp.tool()
async def browser_timeline_checkpoint(label: str = None):
    """Save a full checkpoint (screenshot + HTML) of the page right now, for later diffing."""
    return await timeline_checkpoint(label=label)


@mcp.tool()
async def browser_timeline_list_checkpoints(limit: int = 100):
    """List saved checkpoints (most recent last)."""
    return await timeline_list_checkpoints(limit=limit)


@mcp.tool()
async def browser_timeline_clear_checkpoints():
    """Delete all saved checkpoints and their files."""
    return await timeline_clear_checkpoints()


@mcp.tool()
async def browser_timeline_diff(index_a: int, index_b: int, max_lines: int = 80):
    """
    Diff two checkpoints by position in browser_timeline_list_checkpoints()
    (-1/-2 = the two most recent). Returns a readable content diff plus
    every mutation event recorded between the two checkpoint timestamps.
    """
    return await timeline_diff(index_a, index_b, max_lines=max_lines)


# ============================================================
# SITE DIAGNOSIS (scam / phishing / legitimacy check)
# ============================================================

@mcp.tool()
async def browser_diagnose_site(url: str = None, use_current_page: bool = False):
    """
    Full legitimacy scan of a website: inspects forms and sensitive
    fields (password/card/OTP), third-party ad-trackers, fabricated-stat
    and gambling/urgency language, SSL, wallet-connect code, and link
    domains -- returns a risk_score (0-100), risk_level (low/medium/high),
    and a plain-English `reasons` list explaining exactly what triggered
    the score. Opens the URL in its own isolated tab by default (doesn't
    touch whatever's open in the main tab); set use_current_page=True to
    scan whatever's currently loaded instead.
    """
    return await diagnose_site(url=url, use_current_page=use_current_page)


# ============================================================
# TASK MEMOIZATION (safe fast-path replay for repeated goals)
# ============================================================

@mcp.tool()
async def browser_fastpath_list():
    """List all fast-path candidates/approved entries for browser_agent goals (domain, goal, approved, use count)."""
    return {"success": True, "fastpaths": list_fastpaths()}


@mcp.tool()
async def browser_fastpath_review(domain: str, goal: str):
    """
    Show the exact compiled steps for a fast-path candidate before
    approving it -- review this before calling browser_fastpath_approve.
    """
    return review_fastpath(domain, goal)


@mcp.tool()
async def browser_fastpath_approve(domain: str, goal: str):
    """
    Approve a fast-path candidate so future browser_agent() calls with
    this EXACT goal on this domain skip full planning and replay the
    compiled steps directly (much faster). Review it first with
    browser_fastpath_review -- nothing is ever auto-approved.
    """
    return approve_fastpath(domain, goal)


@mcp.tool()
async def browser_fastpath_reject(domain: str, goal: str):
    """Delete a fast-path candidate/approved entry."""
    return reject_fastpath(domain, goal)


# ============================================================
# SEMANTIC FORM INTELLIGENCE
# ============================================================

@mcp.tool()
async def browser_analyze_form(selector: str = None):
    """
    Scan a form (or the whole page if selector is omitted) and
    identify what each field is actually asking for -- using its
    label, aria attributes, placeholder, AND (for badly-marked-up
    forms with no real <label>) the nearest preceding text in the
    DOM. Returns each field's detected purpose (e.g. "aadhar_number",
    "father_name", "email") and a confidence score, without filling
    anything. Call browser_get_form_purposes() to see the full
    taxonomy of recognized purposes.
    """
    return await analyze_form(selector=selector)


@mcp.tool()
async def browser_fill_form_from_profile(
    profile: dict, selector: str = None, use_human_typing: bool = True, dry_run: bool = False
):
    """
    Analyze a form and auto-fill every field it can confidently
    match against `profile` (dict keyed by purpose, e.g.
    {"full_name": "...", "aadhar_number": "...", "email": "..."}).
    OTP/CAPTCHA/confirm-password fields and anything not confidently
    identified are always left alone and reported separately, never
    guessed. Set dry_run=True to preview what would be filled
    without actually typing anything -- recommended before trusting
    this on a real government/scholarship form.
    """
    return await fill_form_from_profile(profile, selector=selector, use_human_typing=use_human_typing, dry_run=dry_run)


@mcp.tool()
async def browser_get_form_purposes():
    """List every field-purpose category browser_analyze_form/browser_fill_form_from_profile can recognize."""
    return await get_supported_purposes()


# ============================================================
# SMART CONTENT EXTRACTION (ad/nav/boilerplate stripping)
# ============================================================

@mcp.tool()
async def browser_extract_readable_content():
    """
    Extract the actual article/content from the current page,
    stripping ads/nav/banners/boilerplate using text-density
    scoring -- returns clean text, headings hierarchy, images,
    word count, estimated reading time, a confidence score, and
    a transparent report of exactly what was removed and why.
    """
    return await extract_readable_content()


# ============================================================
# ELEMENT-SPECIFIC SCREENSHOTS
# ============================================================

@mcp.tool()
async def browser_element_screenshot(
    selector: str, path: str = None, padding: int = 0, highlight: bool = False, timeout: int = 10000
):
    """
    Screenshot just one element (e.g. a single chart or table),
    not the whole page. padding expands the crop by N pixels on
    every side. highlight=True draws a temporary red outline
    around the element before capturing.
    """
    return await element_screenshot(selector, path=path, padding=padding, highlight=highlight, timeout=timeout)


@mcp.tool()
async def browser_multi_element_screenshot(selectors: List[str], padding: int = 0, timeout: int = 10000):
    """Screenshot several named elements in one call (e.g. every chart on a dashboard)."""
    return await multi_element_screenshot(selectors, padding=padding, timeout=timeout)


# ============================================================
# EXECUTION / PERFORMANCE PROFILING
# ============================================================

@mcp.tool()
async def browser_performance_metrics():
    """Navigation Timing breakdown (DNS/TCP/TLS/TTFB/download/DOM-processing/full-load, in ms) for the current page."""
    return await get_performance_metrics()


@mcp.tool()
async def browser_resource_timing(limit: int = 20):
    """Every resource the current page loaded, sorted slowest-first."""
    return await get_resource_timing(limit=limit)


@mcp.tool()
async def browser_slow_resources(threshold_ms: int = 500, limit: int = 20):
    """Just the resources that took longer than threshold_ms to load -- the actual bottlenecks."""
    return await get_slow_resources(threshold_ms=threshold_ms, limit=limit)


@mcp.tool()
async def browser_runtime_metrics():
    """CDP-level runtime metrics: JS heap size, DOM node count, layout count, style recalc count."""
    return await get_runtime_metrics()

# ============================================================
# AGENT PLANNER
# ============================================================


@mcp.tool()
async def browser_extract_videos():
    return await extract_videos()


@mcp.tool()
async def browser_extract_articles():
    return await extract_articles()


@mcp.tool()
async def browser_extract_search_inputs():
    return await extract_search_inputs()


@mcp.tool()
async def browser_metadata():
    return await get_metadata()


@mcp.tool()
async def browser_tab_exists(index: int):
    return await tab_exists(index)


@mcp.tool()
async def browser_tab_count():
    return await tab_count()


@mcp.tool()
async def browser_research_summary(topic: str):
    return await research_summary(topic)


planner_tools = {
    "browser_start": browser_start,

    # Navigation
    "navigate": navigate,
    "google_search": search_google,
    "site_search": search_site,
    "open_site": open_website,
    "back": back,
    "forward": forward,
    "refresh": refresh_page,
    "wait": wait,
    "wait_for_url": wait_for_url,
    "current_page": browser_current_page,
    "detect_site": browser_detect_site,
    "navigation_status": browser_navigation_status,
    "verify_url": browser_verify_url,

    # Observation
    "observe": browser_observe,
    "read": browser_read,
    "page_state": browser_state,
    "find_text": browser_find_text,
    "headings": browser_headings,
    "links": browser_links,
    "buttons": browser_buttons,
    "inputs": browser_inputs,
    "forms": browser_forms,

    # Extraction
    "search_results": browser_search_results,
    "extract": browser_extract,
    "extract_tables": browser_extract_tables,
    "extract_images": browser_extract_images,
    "extract_videos": browser_extract_videos,
    "extract_articles": browser_extract_articles,
    "extract_search_inputs": browser_extract_search_inputs,
    "get_metadata": browser_metadata,
    "source": browser_source,

    # Vision
    "screenshot": browser_viewport_screenshot,

    # Tabs
    "list_tabs": browser_tabs,
    "new_tab": browser_new_tab,
    "switch_tab": browser_switch_tab,
    "close_tab": browser_close_tab,
    "current_tab": browser_current_tab,
    "tab_exists": browser_tab_exists,
    "tab_count": browser_tab_count,

    # Research
    "research": browser_research,
    "collect_research": browser_collect_research,
    "research_summary": browser_research_summary,
    "deep_research": browser_deep_research,

    # New features
    "find_element": browser_find_element,
    "verify_action": browser_verify_action,
    "download": browser_download,
    "wait_download": browser_wait_download,
    "list_downloads": browser_list_downloads,
    "get_cookies": browser_get_cookies,
    "set_cookies": browser_set_cookies,
    "clear_cookies": browser_clear_cookies,
    "get_local_storage": browser_get_local_storage,
    "set_local_storage": browser_set_local_storage,
    "clear_local_storage": browser_clear_local_storage,
    "get_session_storage": browser_get_session_storage,
    "clear_session_storage": browser_clear_session_storage,
    "clear_all_storage": browser_clear_all_storage,
    "network_start": browser_network_start,
    "network_log": browser_network_log,
    "network_failures": browser_network_failures,
    "network_clear": browser_network_clear,
    "network_wait_idle": browser_network_wait_idle,
    "network_block": browser_network_block,
    "network_mock": browser_network_mock,
    "network_unblock": browser_network_unblock,
    "console_start": browser_console_start,
    "console_stop": browser_console_stop,
    "console_logs": browser_console_logs,
    "console_errors": browser_console_errors,
    "console_clear": browser_console_clear,
    "console_has_errors": browser_console_has_errors,
    "dom_snapshot": browser_dom_snapshot,
    "interactive_snapshot": browser_interactive_snapshot,
    "a11y_snapshot": browser_a11y_snapshot,
    "click_ref": browser_click_ref,
    "type_ref": browser_type_ref,
    "hover_ref": browser_hover_ref,
    "dialog_start": browser_dialog_start,
    "dialog_stop": browser_dialog_stop,
    "dialog_pending": browser_dialog_pending,
    "dialog_accept": browser_dialog_accept,
    "dialog_dismiss": browser_dialog_dismiss,
    "upload_file": browser_upload_file,
    "upload_file_ref": browser_upload_file_ref,
    "clear_file_input": browser_clear_file_input,
    "drag_and_drop": browser_drag_and_drop,
    "drag_and_drop_manual": browser_drag_and_drop_manual,
    "drag_and_drop_ref": browser_drag_and_drop_ref,
    "execute_js": browser_execute_js,
    "execute_js_on_element": browser_execute_js_on_element,
    "execute_js_on_ref": browser_execute_js_on_ref,
    "list_frames": browser_list_frames,
    "frame_click": browser_frame_click,
    "frame_type": browser_frame_type,
    "frame_hover": browser_frame_hover,
    "frame_get_text": browser_frame_get_text,
    "frame_extract_links": browser_frame_extract_links,
    "human_move_mouse": browser_human_move_mouse,
    "human_click": browser_human_click,
    "human_type": browser_human_type,
    "human_scroll": browser_human_scroll,
    "human_scroll_to_element": browser_human_scroll_to_element,
    "human_idle": browser_human_idle,
    "list_device_presets": browser_list_device_presets,
    "emulate_device": browser_emulate_device,
    "reset_device_emulation": browser_reset_device_emulation,
    "set_viewport": browser_set_viewport,
    "set_geolocation": browser_set_geolocation,
    "clear_geolocation": browser_clear_geolocation,
    "throttle_network": browser_throttle_network,
    "reset_network_throttle": browser_reset_network_throttle,
    "export_pdf": browser_export_pdf,
    "codegen_generate": browser_codegen_generate,
    "codegen_export": browser_codegen_export,
    "smart_find": browser_smart_find,
    "memory_remember": browser_memory_remember,
    "memory_recall": browser_memory_recall,
    "memory_record_outcome": browser_memory_record_outcome,
    "memory_list_domains": browser_memory_list_domains,
    "memory_get_domain": browser_memory_get_domain,
    "memory_forget_domain": browser_memory_forget_domain,
    "memory_forget_key": browser_memory_forget_key,
    "analyze_form": browser_analyze_form,
    "fill_form_from_profile": browser_fill_form_from_profile,
    "get_form_purposes": browser_get_form_purposes,
    "extract_readable_content": browser_extract_readable_content,
    "element_screenshot": browser_element_screenshot,
    "multi_element_screenshot": browser_multi_element_screenshot,
    "performance_metrics": browser_performance_metrics,
    "resource_timing": browser_resource_timing,
    "slow_resources": browser_slow_resources,
    "runtime_metrics": browser_runtime_metrics,
    "swarm_extract": browser_swarm_extract,
    "swarm_check": browser_swarm_check,
    "swarm_screenshot": browser_swarm_screenshot,
    "timeline_start": browser_timeline_start,
    "timeline_mutations": browser_timeline_mutations,
    "timeline_checkpoint": browser_timeline_checkpoint,
    "timeline_list_checkpoints": browser_timeline_list_checkpoints,
    "timeline_diff": browser_timeline_diff,
    "diagnose_site": browser_diagnose_site,
    "log_action": browser_log_action,
    "get_history": browser_get_history,
    "last_action": browser_last_action,
    "clear_history": browser_clear_history,
    "statistics": browser_statistics,
}


planner = create_planner(
    browser=browser,
    recovery=recovery,
    safety_check=safety_check,
    tools=planner_tools,
)


@mcp.tool()
async def browser_agent(
    goal: str,
):

    try:

        return await planner.execute_goal(
            goal
        )

    except Exception as e:

        return {
            "success": False,
            "error": str(e),
        }


# ============================================================
# MAIN
# ============================================================

async def main():

    print(
        "Raj Browser MCP v4 started",
        file=sys.stderr,
    )

    print(
        "Debug Chrome / CDP mode enabled",
        file=sys.stderr,
    )

    print(
        "Browser observation enabled",
        file=sys.stderr,
    )

    print(
        "Vision tools enabled",
        file=sys.stderr,
    )

    print(
        "Browser interaction enabled",
        file=sys.stderr,
    )

    print(
        "Multi-tab engine enabled",
        file=sys.stderr,
    )

    print(
        "Research engine enabled",
        file=sys.stderr,
    )

    print(
        "Extraction engine enabled",
        file=sys.stderr,
    )

    print(
        "Safety layer enabled",
        file=sys.stderr,
    )

    print(
        "Recovery engine enabled",
        file=sys.stderr,
    )

    print(
        "Agent planner enabled",
        file=sys.stderr,
    )

    print(
        "Smart element finder enabled",
        file=sys.stderr,
    )

    print(
        "Action verifier enabled",
        file=sys.stderr,
    )

    print(
        "Download manager enabled",
        file=sys.stderr,
    )

    print(
        "Cookie/storage manager enabled",
        file=sys.stderr,
    )

    print(
        "Network monitor enabled",
        file=sys.stderr,
    )

    print(
        "Console monitor enabled",
        file=sys.stderr,
    )

    print(
        "DOM snapshot enabled",
        file=sys.stderr,
    )

    print(
        "Action history enabled",
        file=sys.stderr,
    )

    try:

        await mcp.run_stdio_async()

    except Exception:

        traceback.print_exc(
            file=sys.stderr
        )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    asyncio.run(main())
