from .arxiv import Arxiv
from .base import Provider
from .openalex import OpenAlex
from .scopus import Scopus
from .semantic_scholar import SemanticScholar

REGISTRY: dict[str, type[Provider]] = {
    "arxiv": Arxiv,
    "openalex": OpenAlex,
    "scopus": Scopus,
    "semantic_scholar": SemanticScholar,
}


def create(name: str) -> Provider:
    """Instantiate a provider by name.

    Raises:
        ValueError: If the name is not a known provider.
    """
    if name not in REGISTRY:
        raise ValueError(f"Unknown provider: {name}. Available: {', '.join(REGISTRY)}")
    return REGISTRY[name]()


__all__ = [
    "Arxiv",
    "OpenAlex",
    "Provider",
    "REGISTRY",
    "Scopus",
    "SemanticScholar",
    "create",
]
