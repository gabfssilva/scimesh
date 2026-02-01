"""Playwright-based downloader for protected open access PDFs."""

from __future__ import annotations

import base64
import logging
import os
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Self
from urllib.parse import urlparse

from scimesh.download.base import Downloader

if TYPE_CHECKING:
    from playwright.async_api import Browser, BrowserContext, Page

    from scimesh.download.host_concurrency import HostSemaphores

logger = logging.getLogger(__name__)

try:
    from playwright.async_api import async_playwright

    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    async_playwright = None  # type: ignore[assignment]


def _env_bool(key: str, default: bool) -> bool:
    value = os.getenv(key)
    if value is None:
        return default
    return value.lower() in ("true", "1", "yes")


def _env_int(key: str, default: int) -> int:
    value = os.getenv(key)
    if value is None:
        return default
    return int(value)


def _env_tuple(key: str) -> tuple[str, ...]:
    value = os.getenv(key)
    if not value:
        return ()
    return tuple(arg.strip() for arg in value.split(",") if arg.strip())


@dataclass(frozen=True)
class PlaywrightConfig:
    """Configuration for PlaywrightDownloader.

    All settings can be overridden via environment variables with
    the prefix SCIMESH_PLAYWRIGHT_.
    """

    browser: str = field(default_factory=lambda: os.getenv("SCIMESH_PLAYWRIGHT_BROWSER", "chrome"))
    headless: bool = field(default_factory=lambda: _env_bool("SCIMESH_PLAYWRIGHT_HEADLESS", True))
    timeout: int = field(default_factory=lambda: _env_int("SCIMESH_PLAYWRIGHT_TIMEOUT", 30))
    proxy: str | None = field(default_factory=lambda: os.getenv("SCIMESH_PLAYWRIGHT_PROXY"))
    user_agent: str | None = field(
        default_factory=lambda: os.getenv("SCIMESH_PLAYWRIGHT_USER_AGENT")
    )
    locale: str | None = field(default_factory=lambda: os.getenv("SCIMESH_PLAYWRIGHT_LOCALE"))
    viewport_width: int = field(
        default_factory=lambda: _env_int("SCIMESH_PLAYWRIGHT_VIEWPORT_WIDTH", 1920)
    )
    viewport_height: int = field(
        default_factory=lambda: _env_int("SCIMESH_PLAYWRIGHT_VIEWPORT_HEIGHT", 1080)
    )
    browser_args: tuple[str, ...] = field(
        default_factory=lambda: _env_tuple("SCIMESH_PLAYWRIGHT_BROWSER_ARGS")
    )
    stealth: bool = field(default_factory=lambda: _env_bool("SCIMESH_PLAYWRIGHT_STEALTH", True))

    @property
    def effective_args(self) -> tuple[str, ...]:
        """Browser args with stealth defaults applied."""
        args = list(self.browser_args)
        if self.stealth:
            stealth_arg = "--disable-blink-features=AutomationControlled"
            if stealth_arg not in args:
                args.append(stealth_arg)
        return tuple(args)

    @property
    def effective_user_agent(self) -> str:
        """User agent with stealth default if not specified."""
        if self.user_agent:
            return self.user_agent
        if self.stealth:
            return (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        return ""

    @property
    def is_system_browser(self) -> bool:
        """Whether using a system-installed browser (no playwright install needed)."""
        return self.browser in ("chrome", "msedge", "chrome-beta", "msedge-beta")


class PlaywrightDownloader(Downloader):
    """Downloader that uses headless browser to bypass CDN protections.

    Some open access publishers (like MDPI) use CDN protections (Akamai, Cloudflare)
    that block direct HTTP requests. This downloader navigates to the article page
    first (to get cookies/session), then uses fetch() inside the browser context
    to download the PDF.

    Configuration can be done via PlaywrightConfig or environment variables.
    """

    name = "playwright"

    def __init__(
        self,
        config: PlaywrightConfig | None = None,
        host_semaphores: HostSemaphores | None = None,
    ):
        super().__init__(host_semaphores=host_semaphores)
        self.email = os.environ.get("UNPAYWALL_EMAIL")
        self.config = config or PlaywrightConfig()
        self._playwright: Any = None
        self._browser: Browser | None = None
        self._available = PLAYWRIGHT_AVAILABLE and bool(self.email)

        if not PLAYWRIGHT_AVAILABLE:
            logger.debug("  [Playwright] Not available: playwright not installed")
        elif not self.email:
            logger.debug("  [Playwright] Not available: UNPAYWALL_EMAIL not set")

    async def __aenter__(self) -> Self:
        await super().__aenter__()
        if self._available:
            self._playwright = await async_playwright().start()  # type: ignore[misc]
            self._browser = await self._launch_browser()
        return self

    async def _launch_browser(self) -> Browser:
        """Launch browser based on config."""
        cfg = self.config
        launch_kwargs: dict[str, Any] = {
            "headless": cfg.headless,
            "args": list(cfg.effective_args),
        }

        if cfg.proxy:
            launch_kwargs["proxy"] = {"server": cfg.proxy}

        if cfg.is_system_browser:
            launch_kwargs["channel"] = cfg.browser
            return await self._playwright.chromium.launch(**launch_kwargs)

        browser_type = cfg.browser
        if browser_type in ("chromium", "chrome"):
            return await self._playwright.chromium.launch(**launch_kwargs)
        elif browser_type == "firefox":
            return await self._playwright.firefox.launch(**launch_kwargs)
        elif browser_type == "webkit":
            return await self._playwright.webkit.launch(**launch_kwargs)
        else:
            raise ValueError(f"Unknown browser: {browser_type}")

    async def _create_context(self) -> BrowserContext:
        """Create browser context with config applied."""
        cfg = self.config
        context_kwargs: dict[str, Any] = {
            "viewport": {"width": cfg.viewport_width, "height": cfg.viewport_height},
        }

        if cfg.effective_user_agent:
            context_kwargs["user_agent"] = cfg.effective_user_agent

        if cfg.locale:
            context_kwargs["locale"] = cfg.locale

        context = await self._browser.new_context(**context_kwargs)  # type: ignore[union-attr]

        if cfg.stealth:
            await context.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
            )

        return context

    async def __aexit__(self, *_: object) -> None:
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
        await super().__aexit__(*_)

    def _unpaywall_url(self, doi: str) -> str:
        return f"https://api.unpaywall.org/v2/{doi}?email={self.email}"

    def _get_landing_page(self, pdf_url: str) -> str:
        """Extract landing page URL from PDF URL."""
        parsed = urlparse(pdf_url)
        path = parsed.path
        if path.endswith("/pdf"):
            path = path[:-4]
        elif "/pdf?" in pdf_url:
            path = path.replace("/pdf", "")
        return f"{parsed.scheme}://{parsed.netloc}{path}"

    async def _fetch_pdf_in_browser(self, page: Page, pdf_url: str) -> bytes | None:
        """Use browser's fetch() to download PDF with full context."""
        try:
            b64_content = await page.evaluate(f'''async () => {{
                try {{
                    const response = await fetch("{pdf_url}");
                    if (!response.ok) return null;
                    const blob = await response.blob();
                    return new Promise((resolve) => {{
                        const reader = new FileReader();
                        reader.onloadend = () => resolve(reader.result.split(',')[1]);
                        reader.onerror = () => resolve(null);
                        reader.readAsDataURL(blob);
                    }});
                }} catch (e) {{
                    return null;
                }}
            }}''')

            if b64_content:
                pdf_bytes = base64.b64decode(b64_content)
                if pdf_bytes[:4] == b"%PDF":
                    return pdf_bytes
                logger.debug("  [Playwright] Downloaded content is not a PDF")
            return None
        except Exception as e:
            logger.debug("  [Playwright] fetch() failed: %s", e)
            return None

    async def download(self, doi: str) -> bytes | None:
        if not self._available:
            return None

        if self._client is None or self._browser is None:
            raise RuntimeError("Downloader must be used as async context manager")

        logger.info("  [Playwright] Trying DOI: %s", doi)

        try:
            response = await self._client.get(self._unpaywall_url(doi))
            if response.status_code != 200:
                logger.debug("  [Playwright] Unpaywall returned %s", response.status_code)
                return None

            data = response.json()
            oa_locations = data.get("oa_locations", [])

            for location in oa_locations:
                pdf_url = location.get("url_for_pdf")
                if not pdf_url:
                    continue

                landing_url = self._get_landing_page(pdf_url)
                logger.debug("  [Playwright] Landing: %s", landing_url)
                logger.debug("  [Playwright] PDF URL: %s", pdf_url)

                context = await self._create_context()
                page = await context.new_page()
                try:
                    timeout_ms = self.config.timeout * 1000
                    await page.goto(landing_url, wait_until="networkidle", timeout=timeout_ms)
                    pdf_bytes = await self._fetch_pdf_in_browser(page, pdf_url)
                    if pdf_bytes:
                        logger.info("  [Playwright] Success for %s", doi)
                        return pdf_bytes
                except Exception as e:
                    logger.debug("  [Playwright] Page navigation failed: %s", e)
                finally:
                    await page.close()
                    await context.close()

        except Exception as e:
            logger.debug("  [Playwright] Error: %s", e)

        logger.info("  [Playwright] All locations failed for: %s", doi)
        return None
