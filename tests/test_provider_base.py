# tests/test_provider_base.py
import pytest

from scimesh.providers.base import Provider


def test_provider_is_abstract():
    with pytest.raises(TypeError):
        Provider()  # type: ignore[abstract]
