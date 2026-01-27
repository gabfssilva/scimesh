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

from .combinators import And, Field, Not, Or, Query, YearRange

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
    r"(TITLE-ABS-KEY|TITLE-ABS|TITLE|ABS|KEY|AUTHOR|AUTH|DOI|ALL|FULL|PUBYEAR|AND NOT|AND|OR|>=|<=|[()><=]|\d+|\"[^\"]*\"|[^\s()><=]+)"
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

        if token in FIELD_MAP:
            return self.parse_field()

        # Plain text without field specifier: treat as title + abstract search
        return self.parse_plain_text()

    def parse_field(self) -> Query:
        field_name = self.consume()
        self.expect("(")

        # Collect value tokens until closing paren
        value_parts: list[str] = []
        depth = 1
        while depth > 0:
            t = self.consume()
            if t == "(":
                depth += 1
                value_parts.append(t)
            elif t == ")":
                depth -= 1
                if depth > 0:
                    value_parts.append(t)
            else:
                value_parts.append(t)

        value = " ".join(value_parts)
        fields = FIELD_MAP[field_name]

        if len(fields) == 1:
            return Field(fields[0], value)
        else:
            # Multiple fields: OR them together
            result = Field(fields[0], value)
            for f in fields[1:]:
                result = Or(result, Field(f, value))
            return result

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
