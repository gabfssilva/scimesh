# scimesh/exceptions.py
"""Custom exception hierarchy for scimesh."""


class SciMeshError(Exception):
    """Base exception for all scimesh errors."""


class ProviderError(SciMeshError):
    """Error from a search provider (API errors, rate limits, etc.)."""

    def __init__(self, provider: str, message: str, cause: Exception | None = None) -> None:
        super().__init__(f"{provider}: {message}")
        self.provider = provider
        self.cause = cause
        if cause:
            self.__cause__ = cause


class DownloadError(SciMeshError):
    """Error during paper download."""

    def __init__(self, doi: str, message: str, cause: Exception | None = None) -> None:
        super().__init__(f"Failed to download {doi}: {message}")
        self.doi = doi
        self.cause = cause
        if cause:
            self.__cause__ = cause


class ParseError(SciMeshError):
    """Error parsing a query string."""

    def __init__(self, message: str, position: int | None = None) -> None:
        if position is not None:
            super().__init__(f"{message} at position {position}")
        else:
            super().__init__(message)
        self.position = position


class CacheError(SciMeshError):
    """Error with PDF cache operations."""


__all__ = [
    "SciMeshError",
    "ProviderError",
    "DownloadError",
    "ParseError",
    "CacheError",
]
