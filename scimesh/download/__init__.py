from scimesh.download.base import Downloader, start_downloaders
from scimesh.download.host_concurrency import HostSemaphores
from scimesh.download.openaccess import OpenAccessDownloader
from scimesh.download.scihub import SciHubDownloader

try:
    from scimesh.download.playwright import PlaywrightConfig, PlaywrightDownloader

    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PlaywrightConfig = None  # type: ignore[misc,assignment]
    PlaywrightDownloader = None  # type: ignore[misc,assignment]
    PLAYWRIGHT_AVAILABLE = False


def parse_host_concurrency(value: str | None) -> tuple[dict[str, int] | None, int | None]:
    """Parse host concurrency string into dict and/or default.

    Args:
        value: Either an integer string ("3") for default limit, or
            per-host config like "arxiv.org=2,api.unpaywall.org=3".
            Can also combine: "3,arxiv.org=2" (default 3, arxiv 2).

    Returns:
        Tuple of (per-host limits dict, default limit).
    """
    if not value:
        return None, None

    try:
        return None, int(value)
    except ValueError:
        pass

    result: dict[str, int] = {}
    default: int | None = None
    for part in value.split(","):
        part = part.strip()
        if "=" in part:
            host, limit = part.split("=", 1)
            try:
                result[host.strip()] = int(limit.strip())
            except ValueError:
                pass
        else:
            try:
                default = int(part)
            except ValueError:
                pass

    return (result if result else None), default


def create_downloaders(
    host_concurrency: str | None = None,
    use_scihub: bool = False,
) -> list[Downloader]:
    """Downloaders to try in order: Open Access, Playwright, optionally Sci-Hub."""
    host_limits, default_limit = parse_host_concurrency(host_concurrency)
    host_semaphores = None
    if host_limits or default_limit:
        host_semaphores = HostSemaphores(host_limits, default=default_limit)

    downloaders: list[Downloader] = [OpenAccessDownloader(host_semaphores=host_semaphores)]
    if PLAYWRIGHT_AVAILABLE and PlaywrightDownloader is not None:
        downloaders.append(PlaywrightDownloader(host_semaphores=host_semaphores))
    if use_scihub:
        downloaders.append(SciHubDownloader(host_semaphores=host_semaphores))

    return downloaders


__all__ = [
    "Downloader",
    "HostSemaphores",
    "OpenAccessDownloader",
    "PLAYWRIGHT_AVAILABLE",
    "PlaywrightConfig",
    "PlaywrightDownloader",
    "SciHubDownloader",
    "create_downloaders",
    "parse_host_concurrency",
    "start_downloaders",
]
