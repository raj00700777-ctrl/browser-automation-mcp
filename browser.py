import asyncio
import sys
import subprocess
import urllib.request
import os
import shutil

from playwright.async_api import async_playwright


# ============================================================
# CONFIG
# ============================================================

def _detect_chrome_path():
    """
    Cross-platform Chrome auto-detection. Checked in order:
      1. RAJ_MCP_CHROME_PATH env var (explicit override, for
         non-standard install locations on any OS)
      2. Common per-OS install locations
      3. PATH lookup (google-chrome / chromium etc.)
    Returns None if nothing is found -- launch_chrome() raises a
    clear, actionable error at that point rather than here, so
    importing this module never fails just because Chrome isn't
    installed yet.
    """
    override = os.environ.get("RAJ_MCP_CHROME_PATH")
    if override and os.path.exists(override):
        return override

    candidates = []

    if sys.platform == "win32":
        local_app_data = os.environ.get("LOCALAPPDATA", "")
        candidates += [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.join(local_app_data, "Google", "Chrome", "Application", "chrome.exe") if local_app_data else None,
        ]
    elif sys.platform == "darwin":
        candidates += [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            os.path.expanduser("~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
        ]
    else:  # Linux and other POSIX
        for name in ("google-chrome", "google-chrome-stable", "chromium-browser", "chromium"):
            found = shutil.which(name)
            if found:
                candidates.append(found)

    for path in candidates:
        if path and os.path.exists(path):
            return path

    return None


CHROME_PATH = _detect_chrome_path()

DEBUG_PORT = 9222
DEBUG_URL = f"http://127.0.0.1:{DEBUG_PORT}"

# Dedicated automation profile. Defaults to a folder INSIDE the
# project (not a hardcoded C:\ path) so this works no matter where
# the project is cloned/copied to, on any OS -- but can be pointed
# at an existing profile (e.g. one with logins already saved) via
# the RAJ_MCP_CHROME_PROFILE env var.
AUTOMATION_PROFILE = os.environ.get("RAJ_MCP_CHROME_PROFILE") or os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "chrome_profile"
)


# ============================================================
# BROWSER MANAGER
# ============================================================

class BrowserManager:

    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None
        self.chrome_process = None
        self.lock = asyncio.Lock()
        self._active_page = None


    # ========================================================
    # CHECK CHROME DEBUG PORT
    # ========================================================

    def debug_chrome_running(self):

        try:
            with urllib.request.urlopen(
                f"{DEBUG_URL}/json/version",
                timeout=1
            ) as response:

                return response.status == 200

        except Exception:
            return False


    # ========================================================
    # START CHROME AUTOMATICALLY
    # ========================================================

    def launch_chrome(self):

        if not CHROME_PATH or not os.path.exists(CHROME_PATH):
            raise FileNotFoundError(
                "Could not find a Chrome/Chromium installation automatically. "
                "Install Google Chrome, or set the RAJ_MCP_CHROME_PATH environment "
                "variable to the full path of your chrome/chromium executable."
            )

        os.makedirs(
            AUTOMATION_PROFILE,
            exist_ok=True
        )

        command = [
            CHROME_PATH,

            f"--remote-debugging-port={DEBUG_PORT}",

            f"--user-data-dir={AUTOMATION_PROFILE}",

            "--start-maximized",

            "--disable-notifications",

            "--no-first-run",

            "--no-default-browser-check",
        ]

        print("Starting Chrome automatically...", flush=True, file=sys.stderr)

        # CREATE_NEW_PROCESS_GROUP is a Windows-only subprocess flag --
        # referencing it at all on Mac/Linux raises AttributeError, so
        # it's only included in the kwargs on Windows. start_new_session
        # is the POSIX equivalent (detaches into its own process group).
        popen_kwargs = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
        if sys.platform == "win32":
            popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            popen_kwargs["start_new_session"] = True

        self.chrome_process = subprocess.Popen(command, **popen_kwargs)


    # ========================================================
    # WAIT FOR DEBUG PORT
    # ========================================================

    async def wait_for_debug_chrome(
        self,
        timeout=30
    ):

        for _ in range(timeout * 2):

            if self.debug_chrome_running():

                print("âœ… Chrome Debug Port 9222 is ready.", flush=True, file=sys.stderr)

                return True

            await asyncio.sleep(0.5)

        return False


    # ========================================================
    # ENSURE CHROME
    # ========================================================

    async def ensure_chrome(self):

        # Already running
        if self.debug_chrome_running():

            print("ðŸŒ Existing Debug Chrome detected.", flush=True, file=sys.stderr)

            return True


        # Not running â†’ start automatically
        print("ðŸŒ Debug Chrome not running.", flush=True, file=sys.stderr)

        self.launch_chrome()

        ready = await self.wait_for_debug_chrome()

        if not ready:

            raise RuntimeError(
                "Chrome started but debugging port 9222 "
                "did not become available."
            )

        return True


    # ========================================================
    # START / CONNECT
    # ========================================================

    async def start(self):

        async with self.lock:

            # Existing connection
            if (
                self.browser is not None
                and self.context is not None
                and self.browser.is_connected()
            ):

                return self.context


            # Reset stale connection
            self.browser = None
            self.context = None


            # Make sure Chrome exists
            await self.ensure_chrome()


            # Start Playwright
            if self.playwright is None:

                self.playwright = (
                    await async_playwright().start()
                )


            # Connect to Chrome
            print("ðŸ”Œ Connecting to Chrome...", flush=True, file=sys.stderr)

            try:

                self.browser = (
                    await self.playwright
                    .chromium
                    .connect_over_cdp(
                        DEBUG_URL
                    )
                )

            except Exception as e:

                self.browser = None

                raise RuntimeError(
                    f"Could not connect to Chrome:\n{e}"
                )


            # Check contexts
            if not self.browser.contexts:

                raise RuntimeError(
                    "Chrome connected but no browser "
                    "context was found."
                )


            self.context = self.browser.contexts[0]


            # Find usable pages
            pages = [
                page
                for page in self.context.pages
                if not page.is_closed()
            ]


            # No page â†’ create one
            if not pages:

                print("ðŸ“„ No tab found. Creating Google tab...", flush=True, file=sys.stderr)

                page = await self.context.new_page()

                try:

                    await page.goto(
                        "https://www.google.com",
                        wait_until="domcontentloaded",
                        timeout=30000
                    )

                except Exception:
                    pass

            else:

                page = pages[-1]

                try:
                    await page.bring_to_front()
                except Exception:
                    pass


            print("âœ… Raj Browser connected successfully.", flush=True, file=sys.stderr)

            return self.context


    # ========================================================
    # GET CURRENT PAGE
    # ========================================================

    async def get_page(self):

        context = await self.start()

        # Respect explicitly switched active tab
        if (
            self._active_page is not None
            and not self._active_page.is_closed()
            and self._active_page in context.pages
        ):
            try:
                await self._active_page.bring_to_front()
            except Exception:
                pass
            return self._active_page

        pages = [
            page
            for page in context.pages
            if not page.is_closed()
        ]

        if pages:
            page = pages[-1]
            try:
                await page.bring_to_front()
            except Exception:
                pass
            return page


        # Create new page if none exists

        page = await context.new_page()

        try:

            await page.goto(
                "https://www.google.com",
                wait_until="domcontentloaded",
                timeout=30000
            )

        except Exception:
            pass

        return page


    # ========================================================
    # NEW TAB
    # ========================================================

    async def new_page(self, url=None):

        context = await self.start()

        page = await context.new_page()


        if url:

            try:

                await page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=30000
                )

            except Exception as e:

                print(
                    f"âš ï¸ Navigation warning: {e}",
                    flush=True,
                    file=sys.stderr,
                )


        try:
            await page.bring_to_front()
        except Exception:
            pass


        return page


    # ========================================================
    # GET ALL PAGES
    # ========================================================

    def set_active_page(self, page):
        self._active_page = page

    async def get_pages(self):

        context = await self.start()

        return [
            page
            for page in context.pages
            if not page.is_closed()
        ]


    # ========================================================
    # STATUS
    # ========================================================

    async def status(self):

        try:

            context = await self.start()

            pages = await self.get_pages()

            page_data = []


            for index, page in enumerate(pages):

                try:
                    title = await page.title()
                except Exception:
                    title = ""


                page_data.append({
                    "index": index,
                    "title": title,
                    "url": page.url,
                })


            return {
                "success": True,

                "connected": (
                    self.browser is not None
                    and self.browser.is_connected()
                ),

                "debug_port": DEBUG_PORT,

                "tabs": len(pages),

                "pages": page_data,
            }


        except Exception as e:

            return {
                "success": False,
                "error": str(e),
            }


    # ========================================================
    # CLOSE
    # ========================================================

    async def close(self):

        print("ðŸ”Œ Closing Raj Browser connection...", flush=True, file=sys.stderr)


        # IMPORTANT:
        # We DON'T close external Chrome here.
        # We only disconnect Playwright.

        if self.playwright:

            try:
                await self.playwright.stop()

            except Exception:
                pass


        self.playwright = None
        self.browser = None
        self.context = None


# ============================================================
# GLOBAL INSTANCE
# ============================================================

browser = BrowserManager()