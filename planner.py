import re
import time
from urllib.parse import quote_plus, urlparse, parse_qs


class BrowserPlanner:
    """
    Generic browser-agent planner.

    Public API is intentionally compatible with the existing server.py:
        BrowserPlanner(...)
        create_planner(...)
        create_plan(goal)
        await execute_goal(goal)

    Design goals:
    - Never route an explicit site search to Google by accident.
    - Treat tool success and goal success as different things.
    - Verify the real browser state before returning goal_completed=True.
    - Prefer current-page/site context over a generic search engine.
    - Keep website-specific logic limited to evidence such as YouTube video URLs.
    - Use optional tools when the server exposes them; fail honestly when a
      required capability is unavailable instead of pretending success.
    """

    MAX_REPLANS = 3

    def __init__(self, browser, recovery, safety_check, tools):
        self.browser = browser
        self.recovery = recovery
        self.safety_check = safety_check
        self.tools = tools or {}

    # ========================================================
    # BASIC HELPERS
    # ========================================================

    def _normalize(self, text):
        return " ".join(str(text).strip().lower().split())

    def _tool(self, name):
        return self.tools.get(name)

    def _has_tool(self, name):
        return callable(self._tool(name))

    def _unwrap(self, value):
        if isinstance(value, dict) and "result" in value:
            return value["result"]
        return value

    async def _safe_action(self, action):
        try:
            result = self.safety_check(action)
            if hasattr(result, "__await__"):
                result = await result
            return result
        except Exception as error:
            return {"success": False, "error": f"Safety check failed: {error}"}

    def _extract_selector_arg(self, args, kwargs):
        """Best-effort: pull whatever looks like a CSS selector out of a tool call's args/kwargs."""
        if isinstance(kwargs.get("selector"), str):
            return kwargs["selector"]
        for a in args:
            if isinstance(a, str) and (a.startswith(".") or a.startswith("#") or "[" in a or " " not in a):
                return a
        return None

    async def _capture_semantic_info(self, selector):
        """
        Best-effort: look up the role + accessible name of whatever
        `selector` currently points to, so codegen.py can later embed
        a self-healing fallback (find-by-role+name) alongside the raw
        selector -- if a site redesign breaks the frozen selector,
        the replay script can still recognize "the thing that used
        to be a button called Sign in" instead of failing outright.
        """
        if not selector:
            return None
        try:
            page = await self.browser.get_page()
            info = await page.evaluate(
                """(sel) => {
                    const el = document.querySelector(sel);
                    if (!el) return null;
                    const role = el.getAttribute('role') ||
                        ({A:'link', BUTTON:'button', INPUT:'textbox', TEXTAREA:'textbox', SELECT:'combobox'}[el.tagName] || 'generic');
                    const name = (el.getAttribute('aria-label') || el.innerText || el.value || el.placeholder || '').trim().slice(0, 80);
                    return { role, name };
                }""",
                selector,
            )
            return info
        except Exception:
            return None

    # Read-only internal state-observation calls (used by
    # _current_state()/_goal_state() for bookkeeping) -- these have
    # no side effects and no replay value, so they're excluded from
    # history/codegen entirely rather than showing up as meaningless
    # "[unmapped action] current_page(...)" noise in generated scripts.
    _INTERNAL_OBSERVATION_TOOLS = {"current_page", "navigation_status", "current_tab"}

    async def _run(self, tool_name, *args, **kwargs):
        tool = self._tool(tool_name)
        if tool is None:
            return {
                "success": False,
                "error": f"Planner tool '{tool_name}' is unavailable.",
                "tool": tool_name,
            }
        try:
            result = self.recovery.execute(
                tool,
                *args,
                operation_name=tool_name,
                **kwargs,
            )
            if hasattr(result, "__await__"):
                result = await result

            # Auto-record every action the planner actually performs,
            # so browser_agent() runs can later be replayed/exported
            # as a standalone script via codegen.py -- without needing
            # a manual browser_log_action() call after each step.
            # Internal state-observation calls are excluded (see
            # _INTERNAL_OBSERVATION_TOOLS above).
            if tool_name not in self._INTERNAL_OBSERVATION_TOOLS:
                try:
                    import history

                    selector = self._extract_selector_arg(args, kwargs)
                    semantic = await self._capture_semantic_info(selector) if selector else None

                    history.log_action(
                        tool_name,
                        {
                            "args": args,
                            "kwargs": kwargs,
                            "success": result.get("success") if isinstance(result, dict) else None,
                            "semantic": semantic,
                        },
                    )
                except Exception:
                    pass

            return result
        except Exception as error:
            return {"success": False, "error": str(error), "tool": tool_name}

    def _extract_url(self, goal):
        match = re.search(r"https?://[^\s,<>]+", str(goal), re.I)
        if not match:
            return None
        return match.group(0).rstrip(".,!?;)")

    def _domain_from_url(self, url):
        if not isinstance(url, str) or not url.strip():
            return ""
        try:
            parsed = urlparse(url if "://" in url else "https://" + url)
            host = (parsed.hostname or "").lower()
            if host.startswith("www."):
                host = host[4:]
            return host
        except Exception:
            return ""

    def _same_domain(self, url, expected):
        current = self._domain_from_url(url)
        expected = self._domain_from_url(expected) if "://" in str(expected) else str(expected).lower().strip()
        expected = expected.removeprefix("www.")
        if not current or not expected:
            return False
        return current == expected or current.endswith("." + expected)

    # ========================================================
    # SITE / TARGET DETECTION
    # ========================================================

    def _extract_explicit_site(self, goal):
        text = self._normalize(goal)

        # Explicit URL is the strongest target signal.
        url = self._extract_url(goal)
        if url:
            return self._domain_from_url(url)

        # Generic phrases. This is intentionally not a fixed website list.
        patterns = [
            r"\b(?:on|from|in|using|through|via)\s+([a-z0-9][a-z0-9.-]{1,80})(?:\s|$|,|;)",
            r"\b(?:open|visit|go to|navigate to)\s+([a-z0-9][a-z0-9.-]{1,80})(?:\s|$|,|;)",
        ]
        ignored = {
            "the", "a", "an", "this", "that", "my", "current",
            "page", "site", "website", "browser", "search", "for",
        }
        for pattern in patterns:
            match = re.search(pattern, text, re.I)
            if not match:
                continue
            token = match.group(1).strip(" .")
            if token in ignored:
                continue
            if token in {"google", "youtube", "bing", "duckduckgo"}:
                return token + ".com" if token != "youtube" else "youtube.com"
            if "." in token:
                return token
            # Keep a site name as a symbolic target. open_site/site_search can
            # resolve it if the server exposes those capabilities.
            return token
        return None

    def _current_domain(self, state=None):
        if isinstance(state, dict):
            return self._domain_from_url(state.get("url", ""))
        return ""

    def _is_youtube_goal(self, goal):
        text = self._normalize(goal)
        return bool(re.search(r"\b(?:youtube|youtube\.com|yt)\b", text))

    def _is_google_goal(self, goal):
        text = self._normalize(goal)
        return bool(re.search(r"\b(?:google|google\.com)\b", text))

    # ========================================================
    # INTENT DETECTION
    # ========================================================

    def _wants_search(self, goal):
        return bool(re.search(r"\b(search|look up|find)\b", self._normalize(goal)))

    def _wants_open(self, goal):
        return bool(re.search(r"\b(open|visit|go to|navigate to)\b", self._normalize(goal)))

    def _wants_click(self, goal):
        return bool(re.search(r"\b(click|press|select|choose|tap)\b", self._normalize(goal)))

    def _wants_type(self, goal):
        return bool(re.search(r"\b(type|enter|write|fill)\b", self._normalize(goal)))

    def _wants_play(self, goal):
        return bool(re.search(r"\b(play|start playing|listen to)\b", self._normalize(goal)))

    def _wants_read(self, goal):
        return bool(re.search(r"\b(read|summarize|understand)\b", self._normalize(goal)))

    def _wants_screenshot(self, goal):
        text = self._normalize(goal)
        return "screenshot" in text or "screen shot" in text or "capture the screen" in text

    def _wants_latest(self, goal):
        text = self._normalize(goal)
        return any(x in text for x in ("latest", "newest", "most recent", "recent"))

    def _wants_video(self, goal):
        text = self._normalize(goal)
        return any(x in text for x in ("video", "watch", "play video", "open video"))

    # ========================================================
    # QUERY EXTRACTION
    # ========================================================

    def _extract_search_query(self, goal):
        text = str(goal).strip()
        patterns = [
            r"(?:search|search for|look up|find)\s+(?:on|in|using|via)\s+[a-z0-9.-]+\s+(?:for\s+)?[\"“']([^\"”']+)[\"”']",
            r"(?:search|search for|look up|find)\s+(?:on|in|using|via)\s+[a-z0-9.-]+\s+(?:for\s+)?(.+?)(?=\s*(?:,|;|\band then\b|\bthen\b|\band\s+(?:open|inspect|extract|show|take|click|find|get|play)\b)|$)",
            r"(?:search|search for|look up|find)\s+(?:for\s+)?[\"“']([^\"”']+)[\"”']",
            r"(?:search|search for|look up|find)\s+(?:for\s+)?(.+?)(?=\s*(?:,|;|\band then\b|\bthen\b|\band\s+(?:open|inspect|extract|show|take|click|find|get|play)\b)|$)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.I)
            if not match:
                continue
            query = re.sub(r"^[\"“']+|[\"”']+$", "", match.group(1).strip())
            query = re.sub(r"\s+", " ", query).strip()
            if query:
                return query
        return None

    # ========================================================
    # STATE OBSERVATION
    # ========================================================

    async def _current_state(self):
        candidates = ("current_page", "navigation_status", "current_tab")
        for name in candidates:
            if not self._has_tool(name):
                continue
            result = await self._run(name)
            data = self._unwrap(result)
            if isinstance(data, dict) and data.get("success") is False:
                continue
            if isinstance(data, dict):
                url = data.get("url") or data.get("current_url") or ""
                title = data.get("title") or ""
                if url or title:
                    return {"success": True, "url": url, "title": title, "raw": data}

        try:
            if self.browser is not None:
                page = await self.browser.get_page()
                if page is not None:
                    try:
                        title = await page.title()
                    except Exception:
                        title = ""
                    return {"success": True, "url": page.url, "title": title, "raw": {}}
        except Exception as error:
            return {"success": False, "error": str(error)}
        return {"success": False, "error": "Unable to inspect current browser state."}

    async def _observe(self):
        if self._has_tool("observe"):
            return await self._run("observe")
        return await self._current_state()

    # ========================================================
    # EVIDENCE HELPERS
    # ========================================================

    def _flatten_text(self, value):
        parts = []
        def walk(item):
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                for v in item.values():
                    walk(v)
            elif isinstance(item, (list, tuple)):
                for v in item:
                    walk(v)
        walk(value)
        return " ".join(parts)

    def _query_evidence(self, query, state, result_data=None):
        if not query:
            return False
        corpus = self._normalize(
            f"{state.get('url', '')} {state.get('title', '')} {self._flatten_text(result_data)}"
        )
        words = [w for w in self._normalize(query).split() if len(w) > 2]
        if not words:
            return False
        # Require every meaningful query word, not just one or two.
        return all(word in corpus for word in words)

    def _extract_urls(self, value):
        found = []
        def walk(item):
            if isinstance(item, str):
                for url in re.findall(r"https?://[^\s\"'<>]+", item, re.I):
                    url = url.rstrip(".,!?;)")
                    if url not in found:
                        found.append(url)
            elif isinstance(item, dict):
                for v in item.values():
                    walk(v)
            elif isinstance(item, (list, tuple)):
                for v in item:
                    walk(v)
        walk(value)
        return found

    def _is_video_url(self, url):
        if not isinstance(url, str):
            return False
        low = url.lower()
        return "youtube.com/watch" in low or "youtu.be/" in low

    # ========================================================
    # SEARCH EXECUTION
    # ========================================================

    async def _adaptive_search(self, query, target_domain=None):
        """Search in the requested/current site; Google is fallback only when no site is specified."""
        state = await self._current_state()
        current_domain = self._domain_from_url(state.get("url", "")) if state.get("success") else ""
        target = target_domain or current_domain

        # Explicit site/current-site search has priority over Google.
        if target:
            if self._has_tool("site_search"):
                return await self._run("site_search", target, query)

            if self._has_tool("open_site") and target.count(".") == 0:
                opened = await self._run("open_site", target)
                if isinstance(opened, dict) and opened.get("success") is False:
                    return opened
                if self._has_tool("site_search"):
                    return await self._run("site_search", target, query)

            # If already on the correct domain, an interaction-capable server
            # can perform an on-page search. We never silently substitute Google.
            if current_domain and self._same_domain(current_domain, target):
                for name in ("search_current_site", "search_page", "fill_search", "type_and_search"):
                    if self._has_tool(name):
                        return await self._run(name, query)

            return {
                "success": False,
                "error": "Site-specific search is required, but no site-search or page-interaction tool is available.",
                "target_domain": target,
                "query": query,
            }

        if self._has_tool("google_search"):
            return await self._run("google_search", query)

        if self._has_tool("search"):
            return await self._run("search", query)

        return {"success": False, "error": "No search tool is available.", "query": query}

    # ========================================================
    # PLAN CREATION
    # ========================================================

    def create_plan(self, goal):
        if not isinstance(goal, str) or not goal.strip():
            return {"success": False, "error": "Goal must be a non-empty string."}

        normalized = self._normalize(goal)
        plan = []
        url = self._extract_url(goal)
        target = self._extract_explicit_site(goal)
        query = self._extract_search_query(goal)

        # Explicit URL is always first and authoritative.
        if url:
            plan.append({
                "tool": "navigate",
                "args": [url],
                "description": f"Open {url}",
                "goal_role": "navigation",
                "expected_domain": self._domain_from_url(url),
            })

        # Open-site request. Prefer a dedicated resolver if available.
        if self._wants_open(goal) and not url and target:
            if self._has_tool("open_site"):
                plan.append({
                    "tool": "open_site",
                    "args": [target],
                    "description": f"Open {target}",
                    "goal_role": "navigation",
                    "expected_domain": target,
                })
            elif target in {"google.com", "youtube.com"}:
                plan.append({
                    "tool": "navigate",
                    "args": [f"https://{target}"],
                    "description": f"Open {target}",
                    "goal_role": "navigation",
                    "expected_domain": target,
                })
            elif "." in target:
                plan.append({
                    "tool": "navigate",
                    "args": [f"https://{target}"],
                    "description": f"Open {target}",
                    "goal_role": "navigation",
                    "expected_domain": target,
                })

        # Search is always adaptive. This is the key fix: explicit site context
        # can NEVER fall through to google_search.
        if query:
            plan.append({
                "tool": "__adaptive_search__",
                "args": [query],
                "description": f"Search for '{query}' in the correct browser/site context",
                "goal_role": "search",
                "target_domain": target,
            })

        # Observe when explicitly requested, and also before a video selection.
        if self._wants_video(goal) and target and self._is_youtube_goal(goal):
            plan.append({
                "tool": "__observe__",
                "args": [],
                "description": "Inspect the current page before selecting a video",
                "goal_role": "observe",
            })

        if re.search(r"\b(?:inspect|observe|analy[sz]e)\b", normalized):
            plan.append({
                "tool": "__observe__",
                "args": [],
                "description": "Inspect the current browser page",
                "goal_role": "observe",
            })

        if self._wants_read(goal):
            if self._has_tool("read"):
                plan.append({"tool": "read", "args": [], "description": "Read current page content", "goal_role": "read"})
            else:
                plan.append({"tool": "__observe__", "args": [], "description": "Observe current page content", "goal_role": "read"})

        if "search results" in normalized or "extract results" in normalized or "show results" in normalized:
            if self._has_tool("search_results"):
                plan.append({"tool": "search_results", "args": [], "description": "Extract search results", "goal_role": "extract_results"})

        if "headings" in normalized and self._has_tool("headings"):
            plan.append({"tool": "headings", "args": [], "description": "Extract page headings", "goal_role": "headings"})

        if "links" in normalized and self._has_tool("links"):
            plan.append({"tool": "links", "args": [], "description": "Extract page links", "goal_role": "links"})

        if self._wants_screenshot(goal) and self._has_tool("screenshot"):
            plan.append({"tool": "screenshot", "args": [], "description": "Capture current viewport", "goal_role": "screenshot"})

        # Video opening is handled only after search/observation.
        if self._is_youtube_goal(goal) and self._wants_video(goal):
            plan.append({
                "tool": "__select_and_open_video__",
                "args": [],
                "description": "Select and open a YouTube video from actual extracted page evidence",
                "goal_role": "video_open",
            })

        if not plan:
            return {
                "success": False,
                "error": "I could not build a safe plan from the goal.",
            }

        return {
            "success": True,
            "steps": plan,
            "target_domain": target,
            "query": query,
        }

    # ========================================================
    # VIDEO WORKFLOW
    # ========================================================

    async def _select_and_open_video(self, goal, previous_results):
        candidates = []
        for result in previous_results:
            for url in self._extract_urls(result):
                if self._is_video_url(url) and url not in candidates:
                    candidates.append(url)

        if not candidates and self._has_tool("search_results"):
            extracted = await self._run("search_results")
            if isinstance(extracted, dict) and extracted.get("success") is False:
                return extracted
            for url in self._extract_urls(extracted):
                if self._is_video_url(url) and url not in candidates:
                    candidates.append(url)

        if not candidates:
            return {
                "success": False,
                "error": "No verified YouTube video URL was found in current-page evidence.",
            }

        selected = next((u for u in candidates if "/watch" in u.lower()), candidates[0])
        safety = await self._safe_action(f"Open selected browser result: {selected}")
        if isinstance(safety, dict) and (safety.get("blocked") is True or safety.get("allowed") is False):
            return {"success": False, "blocked": True, "reason": safety, "selected_url": selected}

        if not self._has_tool("navigate"):
            return {"success": False, "error": "Navigation tool is unavailable.", "selected_url": selected}

        execution = await self._run("navigate", selected)
        if isinstance(execution, dict) and execution.get("success") is False:
            return {"success": False, "error": execution, "selected_url": selected}
        return {"success": True, "selected_url": selected, "candidate_count": len(candidates), "result": execution}

    async def _verify_video_opened(self, expected_domain="youtube.com"):
        state = await self._current_state()
        if not state.get("success"):
            return {"verified": False, "reason": "Browser state unavailable."}
        url = state.get("url", "")
        return {
            "verified": self._is_video_url(url) and self._same_domain(url, expected_domain),
            "url": url,
            "title": state.get("title", ""),
        }

    # ========================================================
    # GOAL VERIFICATION
    # ========================================================

    async def _goal_state(self, goal, target_domain=None):
        state = await self._current_state()
        if not state.get("success"):
            return {"completed": False, "reason": "Browser state unavailable."}

        url = state.get("url", "")
        title = state.get("title", "")
        current_domain = self._domain_from_url(url)
        expected = target_domain

        # Explicit destination is mandatory evidence.
        if expected:
            expected_domain = self._domain_from_url(expected) if "." in str(expected) else str(expected)
            if "." in expected_domain and not self._same_domain(url, expected_domain):
                return {
                    "completed": False,
                    "reason": "Expected destination domain was not reached.",
                    "expected_domain": expected_domain,
                    "current_domain": current_domain,
                    "url": url,
                    "title": title,
                }

        query = self._extract_search_query(goal)
        if query:
            # For explicit-site searches, domain and query are both required.
            if expected and "." in str(expected):
                if not self._same_domain(url, expected):
                    return {"completed": False, "reason": "Search is on the wrong domain.", "url": url, "title": title}

            # Query evidence must come from the actual state/page, not merely
            # the fact that a generic search-results tool returned something.
            observed = None
            if self._has_tool("observe"):
                observed = self._unwrap(await self._run("observe"))
            if not self._query_evidence(query, state, observed):
                return {
                    "completed": False,
                    "reason": "Search query could not be verified in the current page state.",
                    "query": query,
                    "url": url,
                    "title": title,
                }

        if self._is_youtube_goal(goal) and self._wants_video(goal):
            verification = await self._verify_video_opened()
            if not verification.get("verified"):
                return {
                    "completed": False,
                    "reason": "Requested YouTube video is not open.",
                    "verification": verification,
                }

        if self._wants_screenshot(goal):
            screenshot_done = any(
                name in {"screenshot", "__screenshot__"}
                for name in getattr(self, "_executed_tools", [])
            )
            if not screenshot_done:
                return {"completed": False, "reason": "Screenshot action was not executed."}

        # Open-only goals need a real URL.
        if self._wants_open(goal) and not query and not self._wants_video(goal):
            return {"completed": bool(url), "url": url, "title": title}

        # A goal containing interaction verbs cannot be declared complete just
        # because a tool returned successfully. Require an explicit verifier or
        # a changed/targeted browser state.
        if self._wants_click(goal) or self._wants_type(goal) or self._wants_play(goal):
            if self._has_tool("verify_goal"):
                result = self._unwrap(await self._run("verify_goal", goal))
                if isinstance(result, dict) and result.get("verified") is True:
                    return {"completed": True, "reason": "Explicit goal verifier confirmed the action.", "url": url, "title": title}
            return {
                "completed": False,
                "reason": "Interaction goal requires explicit post-action verification.",
                "url": url,
                "title": title,
            }

        return {"completed": True, "reason": "All applicable completion predicates passed.", "url": url, "title": title}

    # ========================================================
    # EXECUTION
    # ========================================================

    async def _try_fastpath(self, goal, domain):
        """
        Attempt to replay a human-approved fast-path for this exact
        goal. Returns None if none exists/approved (caller should
        just run the full planner as normal). Returns a result dict
        if a fast-path WAS attempted -- whether it succeeded or had
        to abort partway (in which case the caller falls back to
        the full planner for the whole goal).
        """
        try:
            import memoize
        except Exception:
            return None

        entry = memoize.get_approved_fastpath(domain, goal)
        if entry is None:
            return None

        # Derive the CORRECT target domain from the goal text itself
        # (the same way the normal, non-fastpath flow does via
        # create_plan) rather than from wherever the browser happens
        # to be sitting right now -- for "navigate to X" goals the
        # browser is, by definition, somewhere OTHER than X before
        # the goal runs, so using the pre-run domain here would make
        # the final verification fail even on a perfectly successful
        # replay.
        plan_for_domain = self.create_plan(goal)
        verification_domain = plan_for_domain.get("target_domain") or domain

        results = []
        for index, step in enumerate(entry["steps"], 1):
            execution = await self._run(step["tool"], *step.get("args", []), **step.get("kwargs", {}))
            results.append({"step": index, "tool": step["tool"], "result": execution})

            # Failure mode #2/#3 guard: abort the ENTIRE fast-path the
            # instant any step doesn't succeed -- never continue on a
            # page state the recorded steps didn't anticipate.
            if isinstance(execution, dict) and execution.get("success") is False:
                memoize.record_fastpath_result(domain, goal, success=False)
                return {
                    "fastpath_attempted": True,
                    "fastpath_succeeded": False,
                    "aborted_at_step": index,
                    "results": results,
                }

        # Even a fully-successful replay still has to pass the SAME
        # final goal-state check a normal run would -- "every step
        # succeeded" is not the same as "the goal is actually done".
        verification = await self._goal_state(goal, target_domain=verification_domain)
        succeeded = bool(verification.get("completed"))
        memoize.record_fastpath_result(domain, goal, success=succeeded)

        return {
            "fastpath_attempted": True,
            "fastpath_succeeded": succeeded,
            "verification": verification,
            "results": results,
        }

    async def execute_goal(self, goal):
        if not isinstance(goal, str) or not goal.strip():
            return {"success": False, "goal_completed": False, "error": "Goal cannot be empty."}

        # ---- Fast-path attempt (only if a human has approved one for
        # this EXACT goal+domain -- see memoize.py for the full design) ----
        pre_state = await self._current_state()
        pre_domain = self._domain_from_url(pre_state.get("url", "")) if pre_state.get("success") else ""

        fastpath_outcome = await self._try_fastpath(goal, pre_domain)
        if fastpath_outcome is not None and fastpath_outcome["fastpath_succeeded"]:
            return {
                "success": True,
                "goal_completed": True,
                "goal": goal,
                "used_fastpath": True,
                "steps_executed": len(fastpath_outcome["results"]),
                "verification": fastpath_outcome["verification"],
                "results": fastpath_outcome["results"],
            }
        # If fastpath_outcome is not None but failed, fall through to the
        # FULL planner below for the entire goal -- never resume partway
        # through a fast-path that just proved unreliable this time.

        run_start_time = time.time()

        plan_result = self.create_plan(goal)
        if not plan_result.get("success"):
            return {**plan_result, "goal_completed": False}

        steps = plan_result["steps"]
        target_domain = plan_result.get("target_domain")
        results = []
        self._executed_tools = []

        for index, step in enumerate(steps, 1):
            tool_name = step["tool"]

            if tool_name == "__adaptive_search__":
                query = step.get("args", [None])[0]
                execution = await self._adaptive_search(query, step.get("target_domain"))
            elif tool_name == "__observe__":
                execution = await self._observe()
            elif tool_name == "__select_and_open_video__":
                execution = await self._select_and_open_video(goal, results)
                if execution.get("success"):
                    verification = await self._verify_video_opened()
                    results.append({
                        "step": index,
                        "tool": "verify_video_opened",
                        "description": "Verify requested video page",
                        "result": verification,
                    })
                    if not verification.get("verified"):
                        return {
                            "success": False,
                            "goal_completed": False,
                            "step": index,
                            "failed_tool": "verify_video_opened",
                            "error": "Video navigation could not be verified.",
                            "results": results,
                        }
                else:
                    return {
                        "success": False,
                        "goal_completed": False,
                        "step": index,
                        "failed_tool": tool_name,
                        "error": execution,
                        "results": results,
                    }
            else:
                safety = await self._safe_action(f"Browser planner step: {step.get('description', tool_name)}")
                if isinstance(safety, dict):
                    if safety.get("blocked") is True or safety.get("allowed") is False:
                        return {"success": False, "goal_completed": False, "blocked": True, "step": index, "reason": safety, "results": results}
                    if safety.get("success") is False and "safe" not in safety and "allowed" not in safety:
                        return {"success": False, "goal_completed": False, "step": index, "error": safety, "results": results}
                execution = await self._run(tool_name, *step.get("args", []))

            self._executed_tools.append(tool_name)

            if isinstance(execution, dict) and execution.get("success") is False:
                return {
                    "success": False,
                    "goal_completed": False,
                    "step": index,
                    "failed_tool": tool_name,
                    "error": execution,
                    "results": results,
                }

            results.append({
                "step": index,
                "tool": tool_name,
                "description": step.get("description", ""),
                "result": execution,
            })

        verification = await self._goal_state(goal, target_domain=target_domain)
        if not verification.get("completed"):
            return {
                "success": False,
                "goal_completed": False,
                "goal": goal,
                "steps_planned": len(steps),
                "steps_executed": len(results),
                "verification": verification,
                "results": results,
            }

        await self._save_fastpath_candidate(goal, target_domain, run_start_time)

        # Log a special history entry recording what the FINAL
        # verification actually confirmed -- codegen.py turns this
        # into a real `assert` in generated scripts, so replayed
        # automation checks it actually worked, not just that every
        # step ran without an exception.
        try:
            import history
            history.log_action("__assert_goal_state__", {
                "args": [], "kwargs": {},
                "semantic": {
                    "expected_domain": target_domain,
                    "final_url": verification.get("url"),
                },
            })
        except Exception:
            pass

        return {
            "success": True,
            "goal_completed": True,
            "goal": goal,
            "steps_planned": len(steps),
            "steps_executed": len(results),
            "verification": verification,
            "results": results,
        }

    async def _save_fastpath_candidate(self, goal, target_domain, run_start_time):
        """
        After a clean, fully-verified full-planner run, save the
        exact sequence of real tool calls as a fast-path CANDIDATE
        -- never auto-approved (see memoize.py's failure mode #4).
        Pulled from history.py's auto-log rather than `results`
        directly, since history already carries the semantic
        role+name metadata codegen.py/self-healing rely on.
        """
        try:
            import memoize
            import history
            from datetime import datetime

            domain = target_domain or self._domain_from_url((await self._current_state()).get("url", ""))
            if not domain:
                return

            recent = history.get_history(limit=200).get("history", [])
            run_start_dt = datetime.fromtimestamp(run_start_time)

            def _after_run_start(entry):
                try:
                    return datetime.fromisoformat(entry.get("timestamp", "")) >= run_start_dt
                except Exception:
                    return False

            steps = [
                {
                    "tool": entry["action"],
                    "args": entry.get("details", {}).get("args", []),
                    "kwargs": entry.get("details", {}).get("kwargs", {}),
                    "semantic": entry.get("details", {}).get("semantic"),
                }
                for entry in recent
                if _after_run_start(entry)
            ]
            # Fallback if timestamp parsing ever fails unexpectedly for some
            # entries -- best-effort, never crashes the real result over a
            # memoization bookkeeping detail.
            if not steps and recent:
                steps = [
                    {
                        "tool": entry["action"],
                        "args": entry.get("details", {}).get("args", []),
                        "kwargs": entry.get("details", {}).get("kwargs", {}),
                        "semantic": entry.get("details", {}).get("semantic"),
                    }
                    for entry in recent[-10:]
                ]

            if steps:
                memoize.save_candidate(domain, goal, steps)
        except Exception:
            pass   # memoization bookkeeping must never break a real, successful run


def create_planner(browser, recovery, safety_check, tools):
    return BrowserPlanner(
        browser=browser,
        recovery=recovery,
        safety_check=safety_check,
        tools=tools,
    )


__all__ = ["BrowserPlanner", "create_planner"]