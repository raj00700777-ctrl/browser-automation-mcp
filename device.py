"""
Raj Browser MCP — Device Emulation + Geolocation + Network
Throttling + PDF Export

Since browser.py connects to an ALREADY-RUNNING Chrome via CDP
(rather than launching a fresh isolated context per test), device
emulation here is done at the CDP level directly on the live
page -- Emulation.setDeviceMetricsOverride / setUserAgentOverride
-- instead of Playwright's new_context(**device) helper, which
would spin up a separate window with its own cookies/session and
lose whatever the user was already logged into. This way the
SAME page, SAME cookies, SAME login state just starts reporting
itself as an iPhone / Pixel / iPad without disturbing anything.

Includes:
  - a curated set of real device presets (viewport, DPR, UA,
    touch, mobile flag)
  - plain viewport resize (no device spoofing, just a resize)
  - geolocation override (with permission granting)
  - network condition throttling (offline / slow-3g / fast-3g /
    4g / no throttle) via CDP Network.emulateNetworkConditions
  - full-featured PDF export (page.pdf) with all the knobs:
    format, orientation, margins, header/footer templates, print
    background, scale, page ranges
"""

import os
import time

from browser import browser


# ============================================================
# PAGE ACCESS
# ============================================================

async def _get_page():
    page = await browser.get_page()

    if page is None:
        raise RuntimeError("No active browser page available.")

    return page


async def _cdp_session(page):
    return await page.context.new_cdp_session(page)


# ============================================================
# DEVICE PRESETS
# ============================================================

DEVICE_PRESETS = {
    "iphone_15": {
        "width": 393, "height": 852, "device_scale_factor": 3, "is_mobile": True, "has_touch": True,
        "user_agent": (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
        ),
    },
    "iphone_se": {
        "width": 375, "height": 667, "device_scale_factor": 2, "is_mobile": True, "has_touch": True,
        "user_agent": (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
        ),
    },
    "pixel_7": {
        "width": 412, "height": 915, "device_scale_factor": 2.6, "is_mobile": True, "has_touch": True,
        "user_agent": (
            "Mozilla/5.0 (Linux; Android 14; Pixel 7) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/125.0.0.0 Mobile Safari/537.36"
        ),
    },
    "galaxy_s21": {
        "width": 360, "height": 800, "device_scale_factor": 3, "is_mobile": True, "has_touch": True,
        "user_agent": (
            "Mozilla/5.0 (Linux; Android 14; SM-G991B) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/125.0.0.0 Mobile Safari/537.36"
        ),
    },
    "ipad_pro": {
        "width": 1024, "height": 1366, "device_scale_factor": 2, "is_mobile": True, "has_touch": True,
        "user_agent": (
            "Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
            "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
        ),
    },
    "desktop_1080p": {
        "width": 1920, "height": 1080, "device_scale_factor": 1, "is_mobile": False, "has_touch": False,
        "user_agent": None,
    },
    "desktop_4k": {
        "width": 3840, "height": 2160, "device_scale_factor": 2, "is_mobile": False, "has_touch": False,
        "user_agent": None,
    },
}

_default_metrics = None  # stashed so reset_device_emulation() can restore it


async def list_device_presets():
    return {"success": True, "presets": list(DEVICE_PRESETS.keys())}


async def emulate_device(preset: str):
    """
    Make the CURRENT page (same cookies, same login state) report
    itself as the given device -- viewport, pixel ratio, touch
    support, mobile flag, and user agent all switch at once.
    """
    global _default_metrics

    if preset not in DEVICE_PRESETS:
        return {
            "success": False,
            "error": f"Unknown preset '{preset}'. Choose from {list(DEVICE_PRESETS)}.",
        }

    try:
        page = await _get_page()
        spec = DEVICE_PRESETS[preset]

        if _default_metrics is None:
            current = page.viewport_size or {"width": 1280, "height": 800}
            _default_metrics = {"width": current["width"], "height": current["height"]}

        cdp = await _cdp_session(page)

        await cdp.send("Emulation.setDeviceMetricsOverride", {
            "width": spec["width"],
            "height": spec["height"],
            "deviceScaleFactor": spec["device_scale_factor"],
            "mobile": spec["is_mobile"],
            "screenOrientation": (
                {"angle": 0, "type": "portraitPrimary"} if spec["is_mobile"] else None
            ) or {"angle": 0, "type": "landscapePrimary"},
        })

        await cdp.send("Emulation.setTouchEmulationEnabled", {"enabled": spec["has_touch"]})

        if spec["user_agent"]:
            await cdp.send("Emulation.setUserAgentOverride", {"userAgent": spec["user_agent"]})

        try:
            await page.set_viewport_size({"width": spec["width"], "height": spec["height"]})
        except Exception:
            pass

        return {
            "success": True,
            "action": "emulate_device",
            "preset": preset,
            "width": spec["width"],
            "height": spec["height"],
            "is_mobile": spec["is_mobile"],
        }

    except Exception as error:
        return {"success": False, "action": "emulate_device", "error": str(error)}


async def reset_device_emulation():
    """Clear device emulation and restore the page to a normal desktop viewport."""
    try:
        page = await _get_page()
        cdp = await _cdp_session(page)

        await cdp.send("Emulation.clearDeviceMetricsOverride")
        await cdp.send("Emulation.setTouchEmulationEnabled", {"enabled": False})
        await cdp.send("Emulation.setUserAgentOverride", {"userAgent": ""})

        restore = _default_metrics or {"width": 1280, "height": 800}
        try:
            await page.set_viewport_size(restore)
        except Exception:
            pass

        return {"success": True, "action": "reset_device_emulation"}

    except Exception as error:
        return {"success": False, "action": "reset_device_emulation", "error": str(error)}


async def set_viewport(width: int, height: int):
    """Plain viewport resize -- no device/UA spoofing, just changes the window size."""
    try:
        page = await _get_page()
        await page.set_viewport_size({"width": int(width), "height": int(height)})
        return {"success": True, "action": "set_viewport", "width": width, "height": height}
    except Exception as error:
        return {"success": False, "action": "set_viewport", "error": str(error)}


# ============================================================
# GEOLOCATION
# ============================================================

async def set_geolocation(latitude: float, longitude: float, accuracy: float = 50):
    """Override the page's reported GPS location (grants geolocation permission automatically)."""
    try:
        page = await _get_page()

        try:
            await page.context.grant_permissions(["geolocation"])
        except Exception:
            pass

        await page.context.set_geolocation({
            "latitude": float(latitude),
            "longitude": float(longitude),
            "accuracy": float(accuracy),
        })

        return {
            "success": True,
            "action": "set_geolocation",
            "latitude": latitude,
            "longitude": longitude,
        }

    except Exception as error:
        return {"success": False, "action": "set_geolocation", "error": str(error)}


async def clear_geolocation():
    try:
        page = await _get_page()
        await page.context.clear_permissions()
        return {"success": True, "action": "clear_geolocation"}
    except Exception as error:
        return {"success": False, "action": "clear_geolocation", "error": str(error)}


# ============================================================
# NETWORK THROTTLING
# ============================================================

_NETWORK_PROFILES = {
    "offline": {"offline": True, "downloadThroughput": 0, "uploadThroughput": 0, "latency": 0},
    "slow_3g": {"offline": False, "downloadThroughput": 50 * 1024 / 8, "uploadThroughput": 50 * 1024 / 8, "latency": 400},
    "fast_3g": {"offline": False, "downloadThroughput": 180 * 1024 / 8, "uploadThroughput": 84 * 1024 / 8, "latency": 150},
    "4g": {"offline": False, "downloadThroughput": 4 * 1024 * 1024 / 8, "uploadThroughput": 3 * 1024 * 1024 / 8, "latency": 60},
    "no_throttle": {"offline": False, "downloadThroughput": -1, "uploadThroughput": -1, "latency": 0},
}


async def throttle_network(profile: str = "fast_3g"):
    """
    Simulate slower network conditions to test how the page
    behaves on real-world connections.
    profile: "offline" | "slow_3g" | "fast_3g" | "4g" | "no_throttle"
    """
    if profile not in _NETWORK_PROFILES:
        return {
            "success": False,
            "error": f"Unknown profile '{profile}'. Choose from {list(_NETWORK_PROFILES)}.",
        }

    try:
        page = await _get_page()
        cdp = await _cdp_session(page)

        spec = _NETWORK_PROFILES[profile]
        await cdp.send("Network.emulateNetworkConditions", spec)

        return {"success": True, "action": "throttle_network", "profile": profile}

    except Exception as error:
        return {"success": False, "action": "throttle_network", "error": str(error)}


async def reset_network_throttle():
    return await throttle_network("no_throttle")


# ============================================================
# PDF EXPORT
# ============================================================

async def export_pdf(
    path: str = None,
    format: str = "A4",
    landscape: bool = False,
    print_background: bool = True,
    scale: float = 1.0,
    margin_top: str = "0.4in",
    margin_bottom: str = "0.4in",
    margin_left: str = "0.4in",
    margin_right: str = "0.4in",
    page_ranges: str = "",
    header_template: str = "",
    footer_template: str = "",
    display_header_footer: bool = False,
):
    """
    Export the current page as a PDF.

    Note: Chrome's PDF printing (page.pdf()) requires the
    connected browser to be running in headless (or the newer
    "headless=new") mode -- if Raj's Chrome is running headed
    (a visible window), Chrome will reject this with a clear
    "Page.printToPDF is only available in headless mode" style
    error, which is surfaced as-is rather than silently failing.

    path: where to save the PDF. If omitted, saves under
    D:\\new headless\\output\\pdf\\ with a timestamped filename.
    """
    try:
        page = await _get_page()

        if not path:
            out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output", "pdf")
            os.makedirs(out_dir, exist_ok=True)
            path = os.path.join(out_dir, f"page_{int(time.time())}.pdf")
        else:
            os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)

        await page.pdf(
            path=path,
            format=format,
            landscape=landscape,
            print_background=print_background,
            scale=scale,
            margin={
                "top": margin_top,
                "bottom": margin_bottom,
                "left": margin_left,
                "right": margin_right,
            },
            page_ranges=page_ranges or None,
            display_header_footer=display_header_footer,
            header_template=header_template,
            footer_template=footer_template,
        )

        return {
            "success": True,
            "action": "export_pdf",
            "path": path,
        }

    except Exception as error:
        message = str(error)
        if "headless" in message.lower() or "printtopdf" in message.lower():
            message += (
                " -- PDF export needs Chrome running in headless mode. "
                "This connected Chrome session may be running headed (visible window)."
            )
        return {"success": False, "action": "export_pdf", "error": message}


# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    "list_device_presets",
    "emulate_device",
    "reset_device_emulation",
    "set_viewport",
    "set_geolocation",
    "clear_geolocation",
    "throttle_network",
    "reset_network_throttle",
    "export_pdf",
]
