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


def has_fulltext(query: Query) -> bool:
    """Check if query contains a fulltext field.

    Args:
        query: The query AST to check.

    Returns:
        True if the query contains a Field with field="fulltext".
    """
    match query:
        case Field(field="fulltext"):
            return True
        case And(left=l, right=r) | Or(left=l, right=r):
            return has_fulltext(l) or has_fulltext(r)
        case Not(operand=o):
            return has_fulltext(o)
        case _:
            return False


def extract_fulltext_term(query: Query) -> str | None:
    """Extract the fulltext search term from query.

    Args:
        query: The query AST to extract from.

    Returns:
        The fulltext search term if found, None otherwise.
    """
    match query:
        case Field(field="fulltext", value=v):
            return v
        case And(left=l, right=r) | Or(left=l, right=r):
            return extract_fulltext_term(l) or extract_fulltext_term(r)
        case Not(operand=o):
            return extract_fulltext_term(o)
        case _:
            return None


def remove_fulltext(query: Query) -> Query | None:
    """Remove fulltext field from query, returning the remaining query.

    Args:
        query: The query AST to transform.

    Returns:
        The query without fulltext fields, or None if nothing remains.
    """
    match query:
        case Field(field="fulltext"):
            return None
        case Field():
            return query
        case And(left=l, right=r):
            new_left = remove_fulltext(l)
            new_right = remove_fulltext(r)
            if new_left is None and new_right is None:
                return None
            if new_left is None:
                return new_right
            if new_right is None:
                return new_left
            return And(new_left, new_right)
        case Or(left=l, right=r):
            new_left = remove_fulltext(l)
            new_right = remove_fulltext(r)
            if new_left is None and new_right is None:
                return None
            if new_left is None:
                return new_right
            if new_right is None:
                return new_left
            return Or(new_left, new_right)
        case Not(operand=o):
            new_operand = remove_fulltext(o)
            if new_operand is None:
                return None
            return Not(new_operand)
        case _:
            return query
