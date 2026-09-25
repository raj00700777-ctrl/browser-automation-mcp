"""
Raj Browser MCP — Execution / Performance Profiling

Uses the browser's own Navigation Timing + Resource Timing APIs
(no external tooling needed) to answer "why did this page load
slowly" precisely: exact millisecond breakdown of DNS/TCP/TLS/
TTFB/DOM-processing, plus every resource loaded, sorted by how
long it took, so the slowest script/image/API-call is obvious
at a glance -- not just "the page felt slow".

Also taps CDP's Performance domain directly (JS heap size, layout
count, style-recalc count) for JS-execution-cost signals that the
Navigation/Resource Timing APIs alone don't expose.
"""

from browser import browser


async def _get_page():
    page = await browser.get_page()
    if page is None:
        raise RuntimeError("No active browser page available.")
    return page


_NAV_TIMING_JS = """() => {
    const nav = performance.getEntriesByType('navigation')[0];
    if (!nav) return null;
    return {
        dns_ms: nav.domainLookupEnd - nav.domainLookupStart,
        tcp_ms: nav.connectEnd - nav.connectStart,
        tls_ms: nav.secureConnectionStart > 0 ? (nav.connectEnd - nav.secureConnectionStart) : 0,
        ttfb_ms: nav.responseStart - nav.requestStart,
        download_ms: nav.responseEnd - nav.responseStart,
        dom_processing_ms: nav.domComplete - nav.responseEnd,
        dom_content_loaded_ms: nav.domContentLoadedEventEnd - nav.startTime,
        full_load_ms: nav.loadEventEnd - nav.startTime,
        redirect_count: nav.redirectCount,
        transfer_size_bytes: nav.transferSize || 0,
    };
}"""

_RESOURCE_TIMING_JS = """(limit) => {
    return performance.getEntriesByType('resource')
        .map(r => ({
            name: r.name,
            initiator_type: r.initiatorType,
            duration_ms: Math.round(r.duration),
            transfer_size_bytes: r.transferSize || 0,
            start_ms: Math.round(r.startTime),
        }))
        .sort((a, b) => b.duration_ms - a.duration_ms)
        .slice(0, limit);
}"""


async def get_performance_metrics():
    """
    Navigation Timing breakdown for the current page's load: DNS,
    TCP, TLS, time-to-first-byte, download, DOM-processing, and
    full load time in milliseconds -- exactly where the time went.
    """
    try:
        page = await _get_page()
        timing = await page.evaluate(_NAV_TIMING_JS)

        if timing is None:
            return {"success": False, "error": "No navigation timing data available (page may not have finished loading)."}

        return {"success": True, "action": "get_performance_metrics", "url": page.url, "timing": timing}

    except Exception as error:
        return {"success": False, "error": str(error)}


async def get_resource_timing(limit: int = 20):
    """Every resource the current page loaded (scripts, images, XHR, fonts...), sorted slowest-first."""
    try:
        page = await _get_page()
        resources = await page.evaluate(_RESOURCE_TIMING_JS, limit)

        return {
            "success": True,
            "action": "get_resource_timing",
            "count": len(resources),
            "resources": resources,
        }

    except Exception as error:
        return {"success": False, "error": str(error)}


async def get_slow_resources(threshold_ms: int = 500, limit: int = 20):
    """Just the resources that took longer than threshold_ms -- the actual bottlenecks."""
    try:
        all_resources = await get_resource_timing(limit=200)
        if not all_resources.get("success"):
            return all_resources

        slow = [r for r in all_resources["resources"] if r["duration_ms"] >= threshold_ms][:limit]

        return {
            "success": True,
            "action": "get_slow_resources",
            "threshold_ms": threshold_ms,
            "count": len(slow),
            "resources": slow,
        }

    except Exception as error:
        return {"success": False, "error": str(error)}


async def get_runtime_metrics():
    """
    CDP-level runtime metrics (JS heap size, DOM node count, layout
    count, style recalc count) -- signals for JS-execution cost that
    Navigation/Resource Timing alone don't expose.
    """
    try:
        page = await _get_page()
        cdp = await page.context.new_cdp_session(page)

        await cdp.send("Performance.enable")
        result = await cdp.send("Performance.getMetrics")

        metrics = {m["name"]: m["value"] for m in result.get("metrics", [])}

        return {
            "success": True,
            "action": "get_runtime_metrics",
            "js_heap_used_bytes": metrics.get("JSHeapUsedSize"),
            "js_heap_total_bytes": metrics.get("JSHeapTotalSize"),
            "dom_nodes": metrics.get("Nodes"),
            "layout_count": metrics.get("LayoutCount"),
            "style_recalc_count": metrics.get("RecalcStyleCount"),
            "raw_metrics": metrics,
        }

    except Exception as error:
        return {"success": False, "error": str(error)}


__all__ = [
    "get_performance_metrics",
    "get_resource_timing",
    "get_slow_resources",
    "get_runtime_metrics",
]
