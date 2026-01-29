# scimesh/query/parser.py
"""
Scopus query syntax parser.

Supports:
- TITLE(x), ABS(x), KEY(x), TITLE-ABS(x), TITLE-ABS-KEY(x)
- AUTHOR(x), AUTH(x)
- DOI(x)
- ALL(x), FULL(x) - fulltext
- PUBYEAR = 2020, PUBYEAR > 2020, PUBYEAR < 2020
- AND, OR, AND NOT
- Parentheses for grouping
"""

import re

from .combinators import And, CitationRange, Field, Not, Or, Query, YearRange

# Maps Scopus field names to internal field(s)
FIELD_MAP: dict[str, list[str]] = {
    "TITLE": ["title"],
    "ABS": ["abstract"],
    "KEY": ["keyword"],
    "TITLE-ABS": ["title", "abstract"],
    "TITLE-ABS-KEY": ["title", "abstract", "keyword"],
    "AUTHOR": ["author"],
    "AUTH": ["author"],
    "DOI": ["doi"],
    "ALL": ["fulltext"],
    "FULL": ["fulltext"],
}

# Token patterns
TOKEN_PATTERN = re.compile(
    r"(TITLE-ABS-KEY|TITLE-ABS|TITLE|ABS|KEY|AUTHOR|AUTH|DOI|ALL|FULL|PUBYEAR|CITEDBY|CITATIONS|AND NOT|AND|OR|>=|<=|[()><=]|\d+|\"[^\"]*\"|[^\s()><=]+)"
)


def tokenize(query: str) -> list[str]:
    """Tokenize a Scopus query string."""
    tokens = TOKEN_PATTERN.findall(query)
    return [t.strip('"') for t in tokens if t.strip()]


class Parser:
    """Recursive descent parser for Scopus syntax."""

    def __init__(self, tokens: list[str]):
        self.tokens = tokens
        self.pos = 0

    def peek(self) -> str | None:
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return None

    def consume(self) -> str:
        token = self.tokens[self.pos]
        self.pos += 1
        return token

    def expect(self, expected: str) -> None:
        token = self.consume()
        if token != expected:
            raise SyntaxError(f"Expected '{expected}', got '{token}'")

    def parse(self) -> Query:
        return self.parse_or()

    def parse_or(self) -> Query:
        left = self.parse_and()
        while self.peek() == "OR":
            self.consume()
            right = self.parse_and()
            left = Or(left, right)
        return left

    def parse_and(self) -> Query:
        left = self.parse_unary()
        while self.peek() in ("AND", "AND NOT"):
            op = self.consume()
            right = self.parse_unary()
            if op == "AND NOT":
                left = And(left, Not(right))
            else:
                left = And(left, right)
        return left

    def parse_unary(self) -> Query:
        return self.parse_primary()

    def parse_primary(self) -> Query:
        token = self.peek()

        if token is None:
            raise SyntaxError("Unexpected end of query")

        if token == "(":
            self.consume()
            expr = self.parse_or()
            self.expect(")")
            return expr

        if token == "PUBYEAR":
            return self.parse_pubyear()

        if token in ("CITEDBY", "CITATIONS"):
            return self.parse_citedby()

        if token in FIELD_MAP:
            return self.parse_field()

        # Plain text without field specifier: treat as title + abstract search
        return self.parse_plain_text()

    def parse_field(self) -> Query:
        field_name = self.consume()
        self.expect("(")

        # Parse content inside field specifier, which may contain OR/AND
        content = self._parse_field_content()
        self.expect(")")

        fields = FIELD_MAP[field_name]
        return self._apply_fields_to_content(content, fields)

    def _parse_field_content(self) -> Query:
        """Parse content inside a field specifier (may contain OR)."""
        return self._parse_field_content_or()

    def _parse_field_content_or(self) -> Query:
        """Parse OR expressions inside field content."""
        left = self._parse_field_content_primary()
        while self.peek() == "OR":
            self.consume()
            right = self._parse_field_content_primary()
            left = Or(left, right)
        return left

    def _parse_field_content_primary(self) -> Query:
        """Parse a primary term or grouped expression inside field content."""
        token = self.peek()

        if token == "(":
            # Nested parentheses inside field content
            self.consume()
            expr = self._parse_field_content_or()
            self.expect(")")
            return expr

        # Collect consecutive terms (not OR, not closing paren)
        # This handles multi-word terms like: TITLE(machine learning)
        terms: list[str] = []
        while self.peek() not in (None, "OR", ")"):
            terms.append(self.consume())

        if not terms:
            raise SyntaxError(f"Expected term in field content, got: {token}")

        # Use a placeholder field that will be replaced
        return Field("_raw", " ".join(terms))

    def _apply_fields_to_content(self, content: Query, fields: list[str]) -> Query:
        """Apply field names to a content query with _raw placeholders."""
        match content:
            case Field(field="_raw", value=v):
                if len(fields) == 1:
                    return Field(fields[0], v)
                else:
                    # Multiple fields: OR them together
                    result = Field(fields[0], v)
                    for f in fields[1:]:
                        result = Or(result, Field(f, v))
                    return result
            case Or(left=l, right=r):
                return Or(
                    self._apply_fields_to_content(l, fields),
                    self._apply_fields_to_content(r, fields),
                )
            case And(left=l, right=r):
                return And(
                    self._apply_fields_to_content(l, fields),
                    self._apply_fields_to_content(r, fields),
                )
            case _:
                return content

    def parse_pubyear(self) -> Query:
        self.consume()  # PUBYEAR
        op = self.consume()  # =, >, <
        year_val = int(self.consume())

        if op == "=":
            return YearRange(start=year_val, end=year_val)
        elif op == ">":
            return YearRange(start=year_val + 1, end=None)
        elif op == "<":
            return YearRange(start=None, end=year_val - 1)
        elif op == ">=":
            return YearRange(start=year_val, end=None)
        elif op == "<=":
            return YearRange(start=None, end=year_val)
        else:
            raise SyntaxError(f"Unknown PUBYEAR operator: {op}")

    def parse_citedby(self) -> Query:
        self.consume()  # CITEDBY or CITATIONS
        op = self.consume()  # =, >, <, >=, <=
        count_val = int(self.consume())

        if op == "=":
            return CitationRange(min=count_val, max=count_val)
        elif op == ">":
            return CitationRange(min=count_val + 1, max=None)
        elif op == "<":
            return CitationRange(min=None, max=count_val - 1)
        elif op == ">=":
            return CitationRange(min=count_val, max=None)
        elif op == "<=":
            return CitationRange(min=None, max=count_val)
        else:
            raise SyntaxError(f"Unknown CITEDBY operator: {op}")

    def parse_plain_text(self) -> Query:
        """Parse plain text without field specifier as title + abstract search."""
        # Collect consecutive text tokens (not operators or special tokens)
        text_parts: list[str] = []
        while self.peek() is not None:
            token = self.peek()
            # Stop at operators, parentheses, or field names
            if token in ("AND", "AND NOT", "OR", "(", ")", "PUBYEAR") or token in FIELD_MAP:
                break
            text_parts.append(self.consume())

        if not text_parts:
            raise SyntaxError("Expected text")

        value = " ".join(text_parts)
        # Search in both title and abstract (like TITLE-ABS)
        return Or(Field("title", value), Field("abstract", value))


def parse(query: str) -> Query:
    """Parse a Scopus query string into a Query AST."""
    tokens = tokenize(query)
    parser = Parser(tokens)
    result = parser.parse()
    return result
