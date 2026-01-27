# scimesh/query/combinators.py
from dataclasses import dataclass


@dataclass(frozen=True)
class Query:
    """Base AST node for search queries."""

    def __and__(self, other: "Query") -> "And":
        return And(self, other)

    def __or__(self, other: "Query") -> "Or":
        return Or(self, other)

    def __invert__(self) -> "Not":
        return Not(self)


@dataclass(frozen=True)
class Field(Query):
    """Field match: field=value."""

    field: str
    value: str


@dataclass(frozen=True)
class And(Query):
    """Logical AND of two queries."""

    left: Query
    right: Query


@dataclass(frozen=True)
class Or(Query):
    """Logical OR of two queries."""

    left: Query
    right: Query


@dataclass(frozen=True)
class Not(Query):
    """Logical NOT of a query."""

    operand: Query


@dataclass(frozen=True)
class YearRange(Query):
    """Year range filter."""

    start: int | None = None
    end: int | None = None


# Factory functions (public API)
def title(value: str) -> Field:
    return Field("title", value)


def abstract(value: str) -> Field:
    return Field("abstract", value)


def author(value: str) -> Field:
    return Field("author", value)


def keyword(value: str) -> Field:
    return Field("keyword", value)


def doi(value: str) -> Field:
    return Field("doi", value)


def fulltext(value: str) -> Field:
    return Field("fulltext", value)


def year(start: int | None = None, end: int | None = None) -> YearRange:
    return YearRange(start, end)
