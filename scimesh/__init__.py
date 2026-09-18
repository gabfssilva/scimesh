"""scimesh - A scientific literature search library."""

from scimesh.api import Fetch, Scimesh
from scimesh.cache import Cache, normalize_key
from scimesh.exceptions import (
    DownloadError,
    ParseError,
    ProviderError,
    SciMeshError,
)
from scimesh.models import Author, Paper, SearchResult
from scimesh.query import (
    And,
    Field,
    Not,
    Or,
    Query,
    YearRange,
    abstract,
    author,
    citations,
    doi,
    fulltext,
    keyword,
    parse,
    title,
    year,
)
from scimesh.search import OnError, collect_search, search

__all__ = [
    "And",
    "Author",
    "Cache",
    "DownloadError",
    "Fetch",
    "Field",
    "Not",
    "OnError",
    "Or",
    "Paper",
    "ParseError",
    "ProviderError",
    "Query",
    "SciMeshError",
    "Scimesh",
    "SearchResult",
    "YearRange",
    "abstract",
    "author",
    "citations",
    "collect_search",
    "doi",
    "fulltext",
    "keyword",
    "normalize_key",
    "parse",
    "search",
    "title",
    "year",
]
