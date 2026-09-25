"""
Raj Browser MCP — Human-Like Interaction Engine

Most browser automation tools move the mouse in a straight line
at constant speed and type at a perfectly uniform interval --
both are extremely easy fingerprints for bot-detection systems
(Cloudflare, DataDome, PerimeterX, reCAPTCHA v3 risk scoring,
etc.) to flag, because no real human moves or types that way.

This module replaces "teleport to element and click dead-center"
/ "type every character at 50ms" with behaviour modeled on how
people actually use a mouse and keyboard:

MOUSE
  - cubic-bezier curved paths (not straight lines)
  - ease-in / ease-out speed profile (slow-fast-slow, not constant)
  - random overshoot-and-correct on ~25% of movements
  - small per-point jitter/noise along the path
  - click lands on a randomized point inside the element
    (never exactly center, never exactly the same offset twice)
  - variable mouse-down hold duration
  - short "hover before commit" pause, like a person double
    checking they're over the right thing
  - persistent last-known mouse position across calls, so the
    NEXT movement starts from where the mouse actually is
    instead of teleporting in from nowhere

KEYBOARD
  - per-character delay drawn from a profile (fast / average /
    slow / hunt_and_peck / mobile_thumb), not a fixed constant
  - extra hesitation after spaces and punctuation (word boundaries)
  - a short "reading the field" pause before typing starts
  - optional realistic typos: a nearby QWERTY key is pressed,
    held briefly, backspaced, then corrected -- exactly like a
    real mis-type, at a low configurable rate (default 3%)
  - human-like "select all + backspace" clearing instead of an
    instant value wipe

SCROLLING
  - incremental wheel ticks with variable delta and pauses
    instead of one instant jump, with occasional "reading pause"
    partway through -- mirrors how people actually scroll a feed

IDLE
  - human_idle() -- tiny random mouse micro-movements + pause,
    for use between actions so the cursor is never perfectly
    frozen for long stretches (another common bot signature)

Everything here builds on top of the existing interaction.py
conventions (browser.get_page(), try/except -> {"success": ...}
dicts) and is purely additive -- it does not replace or modify
the original click_element / type_text functions, so nothing
that already works changes behaviour unless you explicitly call
these new human_* functions instead.
"""

import asyncio
import math
import random
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


def _normalize_timeout(timeout: int) -> int:
    return max(100, int(timeout))


def _locator(page, selector: str):
    if not isinstance(selector, str) or not selector.strip():
        raise ValueError("Selector cannot be empty.")

    return page.locator(selector).first


async def _resolve_selector(ref_or_selector: str, is_ref: bool):
    if not is_ref:
        return {"success": True, "selector": ref_or_selector}

    import accessibility
    return await accessibility.resolve_ref(ref_or_selector)


# ============================================================
# PERSISTENT MOUSE STATE
# ============================================================
#
# Playwright doesn't expose a getter for the current cursor
# position, so we track our own best estimate. This is what lets
# consecutive human_click() calls move FROM the last real position
# TO the next target, instead of every click starting from (0, 0).

_last_mouse_pos = None   # (x, y) or None until first move


async def _get_viewport(page):
    size = page.viewport_size
    if size:
        return size["width"], size["height"]

    try:
        dims = await page.evaluate("() => ({w: window.innerWidth, h: window.innerHeight})")
        return dims["w"], dims["h"]
    except Exception:
        return 1280, 800


async def _current_mouse_pos(page):
    global _last_mouse_pos

    if _last_mouse_pos is not None:
        return _last_mouse_pos

    w, h = await _get_viewport(page)
    # First-ever movement: assume mouse rests somewhere plausible,
    # not the (0, 0) corner every bot starts from.
    start = (
        random.uniform(w * 0.3, w * 0.7),
        random.uniform(h * 0.3, h * 0.7),
    )
    _last_mouse_pos = start
    return start


# ============================================================
# BEZIER CURVE MOUSE MOVEMENT
# ============================================================

def _cubic_bezier(t, p0, p1, p2, p3):
    x = (
        (1 - t) ** 3 * p0[0]
        + 3 * (1 - t) ** 2 * t * p1[0]
        + 3 * (1 - t) * t ** 2 * p2[0]
        + t ** 3 * p3[0]
    )
    y = (
        (1 - t) ** 3 * p0[1]
        + 3 * (1 - t) ** 2 * t * p1[1]
        + 3 * (1 - t) * t ** 2 * p2[1]
        + t ** 3 * p3[1]
    )
    return x, y


def _ease_in_out(t):
    # Smoothstep: slow start, fast middle, slow finish.
    return t * t * (3 - 2 * t)


def _build_curve_points(start, end, steps):
    sx, sy = start
    ex, ey = end

    dx, dy = ex - sx, ey - sy
    distance = math.hypot(dx, dy)

    if distance < 1:
        return [end]

    # Perpendicular unit vector, used to bow the path outward
    # like a real hand-arc instead of a ruler-straight line.
    perp_x, perp_y = -dy / distance, dx / distance
    bow = distance * random.uniform(0.08, 0.25) * random.choice([1, -1])

    ctrl1 = (
        sx + dx * 0.33 + perp_x * bow * random.uniform(0.6, 1.0),
        sy + dy * 0.33 + perp_y * bow * random.uniform(0.6, 1.0),
    )
    ctrl2 = (
        sx + dx * 0.66 + perp_x * bow * random.uniform(0.3, 0.7),
        sy + dy * 0.66 + perp_y * bow * random.uniform(0.3, 0.7),
    )

    points = []
    for i in range(steps + 1):
        t = i / steps
        te = _ease_in_out(t)
        x, y = _cubic_bezier(te, start, ctrl1, ctrl2, end)

        # Tiny per-point jitter, but never on the final point --
        # that one must land exactly on target.
        if 0 < i < steps:
            x += random.uniform(-1.2, 1.2)
            y += random.uniform(-1.2, 1.2)

        points.append((x, y))

    return points


async def human_move_mouse(x: float, y: float, duration_ms: int = None):
    """
    Move the mouse to (x, y) along a curved, variable-speed path
    instead of teleporting there in one jump.
    """
    try:
        page = await _get_page()
        start = await _current_mouse_pos(page)
        end = (x, y)

        distance = math.hypot(end[0] - start[0], end[1] - start[1])
        steps = max(8, min(40, int(distance / 12)))

        if duration_ms is None:
            # Roughly proportional to distance, with human variance.
            duration_ms = max(120, min(900, distance * random.uniform(1.4, 2.4)))

        per_step_delay = (duration_ms / 1000) / steps

        # ~25% chance of a slight overshoot then correction, like a
        # real hand that slightly over-swings and settles back.
        overshoot = random.random() < 0.25
        target = end
        if overshoot:
            ox = end[0] + random.uniform(-18, 18)
            oy = end[1] + random.uniform(-18, 18)
            target = (ox, oy)

        for px, py in _build_curve_points(start, target, steps):
            await page.mouse.move(px, py)
            await asyncio.sleep(max(0.001, per_step_delay * random.uniform(0.7, 1.3)))

        if overshoot:
            correction_steps = random.randint(3, 6)
            for px, py in _build_curve_points(target, end, correction_steps):
                await page.mouse.move(px, py)
                await asyncio.sleep(random.uniform(0.01, 0.03))

        global _last_mouse_pos
        _last_mouse_pos = end

        return {"success": True, "action": "human_move_mouse", "x": end[0], "y": end[1]}

    except Exception as error:
        return {"success": False, "action": "human_move_mouse", "error": str(error)}


# ============================================================
# HUMAN CLICK
# ============================================================

async def _target_point_in_box(box):
    # Random point inside the element, biased toward the middle
    # but never dead-center and never on the very edge.
    x = box["x"] + box["width"] * random.uniform(0.3, 0.7)
    y = box["y"] + box["height"] * random.uniform(0.3, 0.7)
    return x, y


async def human_click(
    selector: str = None,
    ref: str = None,
    timeout: int = 10000,
    double: bool = False,
    button: str = "left",
):
    """
    Click an element like a human would: curved mouse approach,
    a brief hover-and-check pause, a randomized landing point
    inside the element (not dead-center), and a variable
    mouse-down hold duration.

    Target with either selector= or ref= (an accessibility ref
    from accessibility.browser_snapshot()).
    """
    try:
        if ref:
            resolved = await _resolve_selector(ref, is_ref=True)
            if not resolved.get("success"):
                return resolved
            selector = resolved["selector"]

        page = await _get_page()
        locator = _locator(page, selector)

        timeout_ms = _normalize_timeout(timeout)
        await locator.wait_for(state="visible", timeout=timeout_ms)

        try:
            await locator.scroll_into_view_if_needed(timeout=timeout_ms)
        except TypeError:
            await locator.scroll_into_view_if_needed()

        box = await locator.bounding_box()
        if not box:
            return {
                "success": False,
                "action": "human_click",
                "selector": selector,
                "error": "Could not compute bounding box (element not rendered).",
            }

        target = await _target_point_in_box(box)
        await human_move_mouse(target[0], target[1])

        # Brief "am I over the right thing" pause before committing.
        await asyncio.sleep(random.uniform(0.05, 0.18))

        hold_ms = random.uniform(35, 130)

        await page.mouse.down(button=button)
        await asyncio.sleep(hold_ms / 1000)
        await page.mouse.up(button=button)

        if double:
            await asyncio.sleep(random.uniform(0.04, 0.09))
            await page.mouse.down(button=button)
            await asyncio.sleep(random.uniform(0.03, 0.08))
            await page.mouse.up(button=button)

        return {
            "success": True,
            "action": "human_click",
            "selector": selector,
            "x": target[0],
            "y": target[1],
            "double": double,
        }

    except Exception as error:
        return {
            "success": False,
            "action": "human_click",
            "selector": selector,
            "error": str(error),
        }


# ============================================================
# HUMAN TYPING
# ============================================================

# Per-keystroke delay ranges (ms), tuned to roughly match real
# typing-speed distributions for each persona.
_TYPING_PROFILES = {
    "fast": (35, 90),
    "average": (70, 180),
    "slow": (150, 320),
    "hunt_and_peck": (220, 480),
    "mobile_thumb": (110, 260),
}

# A tiny QWERTY adjacency map, enough to make simulated typos
# look like real fat-finger mistakes rather than random noise.
_QWERTY_NEIGHBORS = {
    "a": "sqwz", "b": "vghn", "c": "xdfv", "d": "serfcx", "e": "wsdr",
    "f": "drtgvc", "g": "ftyhbv", "h": "gyujnb", "i": "ujko", "j": "huikmn",
    "k": "jiolm", "l": "kop", "m": "njk", "n": "bhjm", "o": "iklp",
    "p": "ol", "q": "wa", "r": "edft", "s": "awedxz", "t": "rfgy",
    "u": "yhji", "v": "cfgb", "w": "qeas", "x": "zsdc", "y": "tghu",
    "z": "asx",
}


def _typo_char(ch):
    lower = ch.lower()
    neighbors = _QWERTY_NEIGHBORS.get(lower)
    if not neighbors:
        return None

    wrong = random.choice(neighbors)
    return wrong.upper() if ch.isupper() else wrong


async def human_type(
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
    Type text like a human: variable per-character delay, extra
    hesitation at word boundaries, a short "reading the field"
    pause before starting, human-like clearing (select-all +
    backspace instead of an instant wipe), and low-rate realistic
    typos that get noticed and corrected mid-word.

    profile: "fast" | "average" | "slow" | "hunt_and_peck" | "mobile_thumb"
    typo_rate: probability (0-1) per alphabetic character of a
    simulated typo-then-correct. Set to 0 for sensitive fields
    (passwords, OTPs) where a stray extra keystroke matters.
    """
    try:
        if profile not in _TYPING_PROFILES:
            return {
                "success": False,
                "action": "human_type",
                "error": f"Unknown profile '{profile}'. Choose from {list(_TYPING_PROFILES)}.",
            }

        if ref:
            resolved = await _resolve_selector(ref, is_ref=True)
            if not resolved.get("success"):
                return resolved
            selector = resolved["selector"]

        page = await _get_page()
        locator = _locator(page, selector)
        timeout_ms = _normalize_timeout(timeout)

        await locator.wait_for(state="visible", timeout=timeout_ms)

        if click_first:
            box = await locator.bounding_box()
            if box:
                target = await _target_point_in_box(box)
                await human_move_mouse(target[0], target[1])
                await asyncio.sleep(random.uniform(0.05, 0.15))
                await page.mouse.down()
                await asyncio.sleep(random.uniform(0.03, 0.09))
                await page.mouse.up()
            else:
                await locator.click(timeout=timeout_ms)
        else:
            await locator.focus(timeout=timeout_ms)

        if pre_delay:
            # A person glances at the field before typing.
            await asyncio.sleep(random.uniform(0.2, 0.9))

        if clear:
            await page.keyboard.press("Control+A")
            await asyncio.sleep(random.uniform(0.04, 0.1))
            await page.keyboard.press("Backspace")
            await asyncio.sleep(random.uniform(0.05, 0.15))

        low, high = _TYPING_PROFILES[profile]
        typo_count = 0

        for ch in text:
            if ch.isalpha() and random.random() < typo_rate:
                wrong = _typo_char(ch)
                if wrong:
                    typo_count += 1
                    await page.keyboard.type(wrong, delay=0)
                    await asyncio.sleep(random.uniform(low, high) / 1000)
                    # A beat where the "human" notices the mistake.
                    await asyncio.sleep(random.uniform(0.08, 0.25))
                    await page.keyboard.press("Backspace")
                    await asyncio.sleep(random.uniform(0.05, 0.15))

            await page.keyboard.type(ch, delay=0)

            delay = random.uniform(low, high)
            if ch in " .,!?\n":
                delay += random.uniform(60, 220)   # word/sentence boundary hesitation

            await asyncio.sleep(delay / 1000)

        return {
            "success": True,
            "action": "human_type",
            "selector": selector,
            "profile": profile,
            "characters": len(text),
            "simulated_typos": typo_count,
        }

    except Exception as error:
        return {
            "success": False,
            "action": "human_type",
            "selector": selector,
            "error": str(error),
        }


# ============================================================
# HUMAN SCROLLING
# ============================================================

async def human_scroll(
    direction: str = "down",
    amount: int = None,
    reading_pause: bool = True,
):
    """
    Scroll the page in small incremental wheel ticks with
    variable delta and pauses, instead of one instant jump --
    with an optional mid-scroll "reading pause" partway through,
    the way a person stops to read something before continuing.
    """
    try:
        if direction not in ("up", "down"):
            return {"success": False, "error": 'direction must be "up" or "down".'}

        page = await _get_page()

        total = amount if amount is not None else random.randint(300, 900)
        sign = 1 if direction == "down" else -1

        remaining = total
        reading_pause_done = not reading_pause
        reading_pause_after = total * random.uniform(0.35, 0.65)
        scrolled_so_far = 0

        while remaining > 0:
            tick = min(remaining, random.randint(60, 160))
            await page.mouse.wheel(0, sign * tick)
            remaining -= tick
            scrolled_so_far += tick

            await asyncio.sleep(random.uniform(0.03, 0.11))

            if not reading_pause_done and scrolled_so_far >= reading_pause_after:
                await asyncio.sleep(random.uniform(0.4, 1.3))
                reading_pause_done = True

        return {
            "success": True,
            "action": "human_scroll",
            "direction": direction,
            "amount": total,
        }

    except Exception as error:
        return {"success": False, "action": "human_scroll", "error": str(error)}


async def human_scroll_to_element(selector: str = None, ref: str = None, timeout: int = 10000):
    """
    Scroll a specific element into view using the same
    incremental, paused scrolling as human_scroll(), instead of
    Playwright's instant scroll_into_view_if_needed().
    """
    try:
        if ref:
            resolved = await _resolve_selector(ref, is_ref=True)
            if not resolved.get("success"):
                return resolved
            selector = resolved["selector"]

        page = await _get_page()
        locator = _locator(page, selector)
        timeout_ms = _normalize_timeout(timeout)

        await locator.wait_for(state="attached", timeout=timeout_ms)

        box = await locator.bounding_box()
        viewport_h = (await _get_viewport(page))[1]

        if box is None:
            await locator.scroll_into_view_if_needed(timeout=timeout_ms)
            return {"success": True, "action": "human_scroll_to_element", "selector": selector, "method": "fallback"}

        # Roughly how far the element is from a comfortable
        # on-screen position; scroll that much, in human ticks.
        offset = box["y"] - viewport_h * 0.4
        direction = "down" if offset > 0 else "up"

        await human_scroll(direction=direction, amount=int(abs(offset)))

        return {"success": True, "action": "human_scroll_to_element", "selector": selector}

    except Exception as error:
        return {"success": False, "action": "human_scroll_to_element", "error": str(error)}


# ============================================================
# IDLE / PRESENCE MICRO-MOVEMENTS
# ============================================================

async def human_idle(min_ms: int = 300, max_ms: int = 1200):
    """
    Small random mouse jitter + pause, meant to be called between
    actions so the cursor is never perfectly frozen for long
    stretches -- a static cursor across many seconds is itself an
    automation signature on some detection systems.
    """
    try:
        page = await _get_page()
        pos = await _current_mouse_pos(page)

        jitters = random.randint(1, 3)
        for _ in range(jitters):
            nx = pos[0] + random.uniform(-25, 25)
            ny = pos[1] + random.uniform(-25, 25)
            await page.mouse.move(nx, ny)
            pos = (nx, ny)
            await asyncio.sleep(random.uniform(0.05, 0.2))

        global _last_mouse_pos
        _last_mouse_pos = pos

        await asyncio.sleep(random.uniform(min_ms, max_ms) / 1000)

        return {"success": True, "action": "human_idle"}

    except Exception as error:
        return {"success": False, "action": "human_idle", "error": str(error)}


# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    "human_move_mouse",
    "human_click",
    "human_type",
    "human_scroll",
    "human_scroll_to_element",
    "human_idle",
]
