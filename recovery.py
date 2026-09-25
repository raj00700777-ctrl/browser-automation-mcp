import asyncio
import sys
import inspect
import time
import traceback


class RecoveryEngine:
    """
    Reliability layer for Raj Browser MCP.

    Responsibilities:
    - Retry failed browser operations
    - Detect transient browser/CDP failures
    - Reconnect browser when possible
    - Exponential backoff
    - Detect false-success operation results
    - Preserve attempt history
    - Provide structured recovery information
    - Remain compatible with planner.py/server.py
    """

    def __init__(
        self,
        browser,
        max_retries=3,
        base_delay=0.75,
    ):
        self.browser = browser
        self.max_retries = max(
            0,
            int(max_retries),
        )
        self.base_delay = max(
            0.1,
            float(base_delay),
        )

        self.max_delay = 8.0

        self.last_operation = None
        self.last_result = None
        self.last_error = None
        self.last_attempts = 0

    # ========================================================
    # LOGGING
    # ========================================================

    def _log(self, message):
        try:
            print(
                f"[Raj Recovery] {message}",
                flush=True,
                file=sys.stderr,
            )
        except Exception:
            pass

    # ========================================================
    # ERROR CLASSIFICATION
    # ========================================================

    def _is_transient_error(self, error):
        """
        Decide whether an exception is likely temporary.

        Examples:
        - timeout
        - CDP disconnect
        - browser/page closed
        - websocket failure
        - navigation interruption
        """

        text = str(error).lower()

        transient_keywords = (
            "timeout",
            "timed out",
            "target closed",
            "page closed",
            "browser closed",
            "browser has been closed",
            "connection closed",
            "connection reset",
            "connection refused",
            "connection error",
            "disconnected",
            "not connected",
            "session closed",
            "websocket",
            "cdp",
            "protocol error",
            "execution context was destroyed",
            "navigation interrupted",
            "net::err_",
            "temporarily unavailable",
            "transport closed",
            "socket closed",
            "socket hang up",
            "channel closed",
        )

        return any(
            keyword in text
            for keyword in transient_keywords
        )

    # ========================================================
    # RESULT INSPECTION
    # ========================================================

    def _result_contains_failure(self, value):
        """
        Detect explicit failure information inside a nested
        operation result.

        Example:

            {
                "success": True,
                "result": {
                    "success": False,
                    "error": "page closed"
                }
            }

        should NOT be treated as successful.
        """

        if isinstance(value, dict):

            if value.get("success") is False:
                return True

            for key, child in value.items():

                if key in (
                    "error",
                    "exception",
                    "failure",
                ):
                    if child:
                        return True

                if isinstance(
                    child,
                    (dict, list, tuple),
                ):
                    if self._result_contains_failure(
                        child
                    ):
                        return True

        elif isinstance(value, (list, tuple)):

            for child in value:

                if self._result_contains_failure(
                    child
                ):
                    return True

        return False

    def _result_error_message(self, value):
        """
        Extract a useful error message from a nested
        operation result.
        """

        if isinstance(value, dict):

            for key in (
                "error",
                "exception",
                "failure",
                "message",
            ):
                message = value.get(key)

                if message:
                    return str(message)

            for child in value.values():

                if isinstance(
                    child,
                    (dict, list, tuple),
                ):
                    found = self._result_error_message(
                        child
                    )

                    if found:
                        return found

        elif isinstance(value, (list, tuple)):

            for child in value:

                found = self._result_error_message(
                    child
                )

                if found:
                    return found

        return None

    def _validate_result(self, result):
        """
        Validate an operation's returned value.

        This deliberately avoids assuming that an empty list
        is always an error because some legitimate extraction
        operations can return zero results.

        We only reject explicit failure states.
        """

        if result is None:
            return False, "Operation returned None."

        if self._result_contains_failure(result):

            message = self._result_error_message(
                result
            )

            return (
                False,
                message
                or "Operation returned an explicit failure.",
            )

        return True, None

    # ========================================================
    # BROWSER CONNECTION STATE
    # ========================================================

    def _browser_connected(self):
        """
        Safely inspect browser connection state without
        assuming every browser implementation exposes the
        same attributes.
        """

        if self.browser is None:
            return True

        try:
            browser_object = getattr(
                self.browser,
                "browser",
                None,
            )

            context = getattr(
                self.browser,
                "context",
                None,
            )

            if browser_object is None:
                return False

            if context is None:
                return False

            is_connected = getattr(
                browser_object,
                "is_connected",
                None,
            )

            if callable(is_connected):

                try:
                    return bool(
                        is_connected()
                    )
                except Exception:
                    return False

            return True

        except Exception:
            return False

    # ========================================================
    # BROWSER RECONNECT
    # ========================================================

    async def reconnect(self):
        """
        Try to reconnect to the existing Chrome/CDP session.

        The method intentionally keeps the existing public
        interface because planner.py/server.py already use it.
        """

        self._log(
            "Attempting browser recovery..."
        )

        if self.browser is None:

            self._log(
                "No browser object available."
            )

            return False

        try:

            start = getattr(
                self.browser,
                "start",
                None,
            )

            if not callable(start):

                self._log(
                    "Browser does not expose start()."
                )

                return False

            result = start()

            if inspect.isawaitable(result):
                await result

            connected = self._browser_connected()

            if connected:

                self._log(
                    "Browser connection recovered."
                )

                return True

            # Some browser implementations don't expose
            # enough state for _browser_connected() to confirm.
            # If start() completed without exception, consider
            # the reconnect successful.
            self._log(
                "Browser start completed."
            )

            return True

        except asyncio.CancelledError:
            raise

        except Exception as error:

            self._log(
                "Browser recovery failed: "
                + str(error)
            )

            return False

    # ========================================================
    # DELAY / BACKOFF
    # ========================================================

    async def _delay(self, attempt):
        """
        Exponential backoff:

            attempt 1 -> base_delay
            attempt 2 -> 2 * base_delay
            attempt 3 -> 4 * base_delay

        Capped to max_delay.
        """

        exponent = max(
            0,
            int(attempt) - 1,
        )

        delay = (
            self.base_delay
            * (2 ** exponent)
        )

        delay = min(
            delay,
            self.max_delay,
        )

        self._log(
            f"Waiting {delay:.2f}s before retry..."
        )

        await asyncio.sleep(delay)

    # ========================================================
    # OPERATION EXECUTION
    # ========================================================

    async def execute(
        self,
        operation,
        *args,
        operation_name="operation",
        **kwargs,
    ):
        """
        Execute an async browser operation with recovery.

        Public return format remains compatible:

            {
                "success": True,
                "result": ...,
                "attempt": 1,
            }

        or:

            {
                "success": False,
                "operation": "...",
                "error": "...",
                "attempts": ...,
            }
        """

        self.last_operation = operation_name
        self.last_result = None
        self.last_error = None
        self.last_attempts = 0

        if not callable(operation):

            return {
                "success": False,
                "operation": operation_name,
                "error": (
                    f"Operation '{operation_name}' "
                    "is not callable."
                ),
                "attempts": 0,
            }

        total_attempts = (
            self.max_retries + 1
        )

        last_error = None
        attempt_history = []

        for attempt in range(
            1,
            total_attempts + 1,
        ):

            self.last_attempts = attempt

            try:

                # ------------------------------------------------
                # CONNECTION CHECK
                # ------------------------------------------------

                if not self._browser_connected():

                    self._log(
                        "Browser connection appears "
                        "unavailable."
                    )

                    recovered = await self.reconnect()

                    if not recovered:

                        raise RuntimeError(
                            "Browser connection unavailable "
                            "and recovery failed."
                        )

                # ------------------------------------------------
                # EXECUTE OPERATION
                # ------------------------------------------------

                started = time.monotonic()

                result = operation(
                    *args,
                    **kwargs,
                )

                if inspect.isawaitable(result):
                    result = await result

                duration = (
                    time.monotonic()
                    - started
                )

                # ------------------------------------------------
                # RESULT VALIDATION
                # ------------------------------------------------

                valid, validation_error = (
                    self._validate_result(
                        result
                    )
                )

                if not valid:

                    error = RuntimeError(
                        validation_error
                        or "Operation result failed validation."
                    )

                    last_error = error

                    attempt_history.append(
                        {
                            "attempt": attempt,
                            "success": False,
                            "error": str(error),
                            "duration": round(
                                duration,
                                3,
                            ),
                            "reason": "invalid_result",
                        }
                    )

                    self._log(
                        f"{operation_name} returned "
                        f"an invalid result "
                        f"(attempt "
                        f"{attempt}/{total_attempts}): "
                        f"{error}"
                    )

                    # If the returned failure itself looks
                    # transient, reconnect and retry.
                    if (
                        self._is_transient_error(
                            error
                        )
                        and attempt < total_attempts
                    ):

                        await self._delay(
                            attempt
                        )

                        await self.reconnect()

                        continue

                    # Explicit failure without a transient
                    # reason should not be blindly retried.
                    break

                # ------------------------------------------------
                # SUCCESS
                # ------------------------------------------------

                self.last_result = result
                self.last_error = None

                attempt_history.append(
                    {
                        "attempt": attempt,
                        "success": True,
                        "duration": round(
                            duration,
                            3,
                        ),
                    }
                )

                return {
                    "success": True,
                    "result": result,
                    "attempt": attempt,
                    "attempts": attempt,
                    "operation": operation_name,
                    "recovered": attempt > 1,
                    "history": attempt_history,
                }

            # ----------------------------------------------------
            # CANCELLATION
            # ----------------------------------------------------

            except asyncio.CancelledError:
                raise

            # ----------------------------------------------------
            # OPERATION ERROR
            # ----------------------------------------------------

            except Exception as error:

                last_error = error
                self.last_error = error

                transient = (
                    self._is_transient_error(
                        error
                    )
                )

                attempt_history.append(
                    {
                        "attempt": attempt,
                        "success": False,
                        "error": str(error),
                        "transient": transient,
                        "traceback": traceback.format_exc(
                            limit=3
                        ),
                    }
                )

                self._log(
                    f"{operation_name} failed "
                    f"(attempt "
                    f"{attempt}/{total_attempts}): "
                    f"{error}"
                )

                # Non-transient errors should not be
                # blindly retried.
                if not transient:
                    break

                # No attempts remaining.
                if attempt >= total_attempts:
                    break

                # Backoff.
                await self._delay(
                    attempt
                )

                # Reconnect before retry.
                await self.reconnect()

        # ========================================================
        # FINAL FAILURE
        # ========================================================

        self.last_result = None

        # Best-effort auto-checkpoint (screenshot + HTML + recent
        # mutation log) right at the moment recovery has fully
        # given up -- so debugging a failure later means looking
        # at exactly what the page looked like, instead of just
        # an error string. Never allowed to affect the real
        # error path if it itself fails.
        try:
            import timeline
            asyncio.ensure_future(
                timeline.timeline_auto_checkpoint(operation_name)
            )
        except Exception:
            pass

        return {
            "success": False,
            "operation": operation_name,
            "error": (
                str(last_error)
                if last_error is not None
                else "Unknown operation failure."
            ),
            "attempts": self.last_attempts,
            "history": attempt_history,
        }

    # ========================================================
    # SIMPLE RETRY HELPER
    # ========================================================

    async def retry(
        self,
        operation,
        *args,
        retries=None,
        operation_name="operation",
        **kwargs,
    ):
        """
        Convenience retry interface.

        Existing behavior preserved.
        """

        old_retries = self.max_retries

        if retries is not None:

            self.max_retries = max(
                0,
                int(retries),
            )

        try:

            return await self.execute(
                operation,
                *args,
                operation_name=operation_name,
                **kwargs,
            )

        finally:

            self.max_retries = old_retries

    # ========================================================
    # STATUS
    # ========================================================

    def status(self):
        """
        Return the latest recovery state.

        Useful for debugging and future MCP diagnostics.
        """

        return {
            "operation": self.last_operation,
            "attempts": self.last_attempts,
            "has_result": (
                self.last_result is not None
            ),
            "last_error": (
                str(self.last_error)
                if self.last_error is not None
                else None
            ),
            "max_retries": self.max_retries,
            "base_delay": self.base_delay,
            "max_delay": self.max_delay,
        }


__all__ = [
    "RecoveryEngine",
]