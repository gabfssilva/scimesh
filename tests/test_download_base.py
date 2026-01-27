# tests/test_download_base.py
import pytest

from scimesh.download import Downloader


def test_downloader_is_abstract():
    """Test that Downloader cannot be instantiated directly."""
    with pytest.raises(TypeError):
        Downloader()  # type: ignore[abstract]


def test_downloader_requires_download_method():
    """Test that subclass must implement download method."""

    class IncompleteDownloader(Downloader):
        name = "incomplete"

    with pytest.raises(TypeError):
        IncompleteDownloader()  # type: ignore[abstract]
