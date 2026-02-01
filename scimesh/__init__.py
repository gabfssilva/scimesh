"""scimesh - A scientific literature search library."""

from scimesh.exceptions import (
    CacheError,
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
    doi,
    fulltext,
    keyword,
    parse,
    title,
    year,
)
from scimesh.search import OnError, collect_search, search

__all__ = [
    "SciMeshError",
    "ProviderError",
    "DownloadError",
    "ParseError",
    "CacheError",
    "Query",
    "Field",
    "And",
    "Or",
    "Not",
    "YearRange",
    "title",
    "abstract",
    "author",
    "keyword",
    "doi",
    "fulltext",
    "year",
    "parse",
    "Paper",
    "Author",
    "SearchResult",
    "search",
    "collect_search",
    "OnError",
]
