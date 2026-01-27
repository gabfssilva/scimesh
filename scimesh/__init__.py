# scimesh/__init__.py
"""scimesh - A scientific literature search library."""

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
from scimesh.search import OnError, search, take

__all__ = [
    # Query combinators
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
    # Models
    "Paper",
    "Author",
    "SearchResult",
    # Search
    "search",
    "take",
    "OnError",
]
