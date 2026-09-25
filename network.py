"""
Raj Browser MCP — Network Request/Response Monitoring
"""

from browser import browser

_network_log = []
_request_handler = None
_response_handler = None
_monitored_page = None


def _detach_existing_listeners():
    global _request_handler, _response_handler, _monitored_page
    if _monitored_page is not None and not _monitored_page.is_closed():
        try:
            if _request_handler is not None:
                _monitored_page.remove_listener("request", _request_handler)
            if _response_handler is not None:
                _monitored_page.remove_listener("response", _response_handler)
        except Exception:
            pass
    _request_handler = None
    _response_handler = None
    _monitored_page = None


async def network_start_monitoring():
    try:
        page = await browser.get_page()

        # Remove any previously attached listeners (avoids duplicate log entries)
        _detach_existing_listeners()

        _network_log.clear()

        async def _on_request(request):
            _network_log.append({
                "type": "request",
                "url": request.url,
                "method": request.method,
                "headers": dict(request.headers),
            })

        async def _on_response(response):
            _network_log.append({
                "type": "response",
                "url": response.url,
                "status": response.status,
                "headers": dict(response.headers),
            })

        global _request_handler, _response_handler, _monitored_page
        _request_handler = _on_request
        _response_handler = _on_response
        _monitored_page = page

        page.on("request", _request_handler)
        page.on("response", _response_handler)

        return {"success": True, "message": "Network monitoring started"}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def network_stop_monitoring():
    try:
        _detach_existing_listeners()
        return {"success": True, "message": "Network monitoring stopped"}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def network_get_log():
    return {"success": True, "log": _network_log, "count": len(_network_log)}


async def network_get_failures():
    failures = [e for e in _network_log if e.get("type") == "response" and (e.get("status") or 0) >= 400]
    return {"success": True, "failures": failures, "count": len(failures)}


async def network_clear_log():
    _network_log.clear()
    return {"success": True, "message": "Network log cleared"}


async def network_wait_for_idle(timeout: int = 30000):
    try:
        page = await browser.get_page()
        await page.wait_for_load_state("networkidle", timeout=timeout)
        return {"success": True, "message": "Network idle reached"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ============================================================
# REQUEST BLOCKING / MOCKING
# ============================================================
#
# Uses Playwright's page.route(), which intercepts matching
# requests before they hit the network. Each active route is
# tracked by its glob pattern so it can be precisely removed
# later without disturbing other routes.

_active_routes = {}   # pattern -> handler


async def network_block_urls(patterns):
    """
    Block one or more URL glob patterns (e.g. "**/*.png",
    "**/ads/**", "**/analytics.js"). Matching requests are
    aborted before they reach the network.
    """
    try:
        page = await browser.get_page()
        patterns = [patterns] if isinstance(patterns, str) else list(patterns)

        blocked = []
        for pattern in patterns:
            if pattern in _active_routes:
                continue

            async def _handler(route, request):
                await route.abort()

            await page.route(pattern, _handler)
            _active_routes[pattern] = _handler
            blocked.append(pattern)

        return {"success": True, "action": "network_block_urls", "blocked": blocked}

    except Exception as e:
        return {"success": False, "error": str(e)}


async def network_mock_response(
    pattern: str,
    status: int = 200,
    body: str = "",
    content_type: str = "application/json",
    headers: dict = None,
):
    """
    Mock every request matching a URL glob pattern with a fixed
    response instead of letting it hit the real network. Useful
    for testing UI states (errors, empty lists, slow APIs) without
    needing the real backend to cooperate.
    """
    try:
        page = await browser.get_page()

        if pattern in _active_routes:
            await network_unblock_urls([pattern])

        async def _handler(route, request):
            await route.fulfill(
                status=status,
                body=body,
                content_type=content_type,
                headers=headers or {},
            )

        await page.route(pattern, _handler)
        _active_routes[pattern] = _handler

        return {
            "success": True,
            "action": "network_mock_response",
            "pattern": pattern,
            "status": status,
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


async def network_unblock_urls(patterns=None):
    """
    Remove active block/mock routes. If patterns is omitted, every
    active route is removed.
    """
    try:
        page = await browser.get_page()
        targets = list(_active_routes.keys()) if patterns is None else (
            [patterns] if isinstance(patterns, str) else list(patterns)
        )

        removed = []
        for pattern in targets:
            handler = _active_routes.get(pattern)
            if handler is None:
                continue
            try:
                await page.unroute(pattern, handler)
            except Exception:
                pass
            del _active_routes[pattern]
            removed.append(pattern)

        return {"success": True, "action": "network_unblock_urls", "removed": removed}

    except Exception as e:
        return {"success": False, "error": str(e)}


__all__ = [
    "network_start_monitoring",
    "network_stop_monitoring",
    "network_get_log",
    "network_get_failures",
    "network_clear_log",
    "network_wait_for_idle",
    "network_block_urls",
    "network_mock_response",
    "network_unblock_urls",
]