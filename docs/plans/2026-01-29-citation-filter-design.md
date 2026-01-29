# Citation Count Filter Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add citation count filtering to scimesh queries via string DSL (`CITEDBY >= 100`) and Python DSL (`citations(100)`).

**Architecture:** New `CitationRange` AST node similar to `YearRange`. Providers with native support (OpenAlex, Semantic Scholar) translate to API parameters. Others filter client-side in the generator pipeline.

**Tech Stack:** Python 3.12+, dataclasses, async generators, httpx

---

## Task 1: Add CitationRange to AST

**Files:**
- Modify: `scimesh/query/combinators.py`
- Test: `tests/test_combinators.py`

**Step 1: Write the failing test for CitationRange**

Add to `tests/test_combinators.py`:

```python
from scimesh.query.combinators import (
    CitationRange,
    citations,
    extract_citation_range,
    remove_citation_range,
)


def test_citations_min_only():
    q = citations(100)
    assert isinstance(q, CitationRange)
    assert q.min == 100
    assert q.max is None


def test_citations_min_and_max():
    q = citations(100, 500)
    assert isinstance(q, CitationRange)
    assert q.min == 100
    assert q.max == 500


def test_citations_max_only():
    q = citations(max=200)
    assert isinstance(q, CitationRange)
    assert q.min is None
    assert q.max == 200


def test_citations_keyword_min():
    q = citations(min=50)
    assert isinstance(q, CitationRange)
    assert q.min == 50
    assert q.max is None
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_combinators.py::test_citations_min_only -v`
Expected: FAIL with ImportError

**Step 3: Implement CitationRange and citations()**

Add to `scimesh/query/combinators.py` after `YearRange`:

```python
@dataclass(frozen=True, slots=True)
class CitationRange(Query):
    """Citation count filter."""

    min: int | None = None
    max: int | None = None


def citations(min: int | None = None, /, max: int | None = None) -> CitationRange:
    """Filter by citation count range.

    Args:
        min: Minimum citation count (inclusive).
        max: Maximum citation count (inclusive).

    Examples:
        citations(100)           # min=100
        citations(100, 500)      # min=100, max=500
        citations(min=50)        # explicit min
        citations(max=200)       # max only
    """
    return CitationRange(min, max)
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_combinators.py::test_citations_min_only tests/test_combinators.py::test_citations_min_and_max tests/test_combinators.py::test_citations_max_only tests/test_combinators.py::test_citations_keyword_min -v`
Expected: PASS

**Step 5: Commit**

```bash
git add scimesh/query/combinators.py tests/test_combinators.py
git commit -m "feat(query): add CitationRange AST node and citations() factory"
```

---

## Task 2: Add helper functions for CitationRange

**Files:**
- Modify: `scimesh/query/combinators.py`
- Test: `tests/test_combinators.py`

**Step 1: Write failing tests for helpers**

Add to `tests/test_combinators.py`:

```python
def test_extract_citation_range_simple():
    q = citations(100)
    assert extract_citation_range(q) == CitationRange(min=100)


def test_extract_citation_range_in_and():
    q = title("transformer") & citations(50)
    result = extract_citation_range(q)
    assert result == CitationRange(min=50)


def test_extract_citation_range_none():
    q = title("bert") & author("google")
    assert extract_citation_range(q) is None


def test_remove_citation_range_simple():
    assert remove_citation_range(citations(100)) is None


def test_remove_citation_range_preserves_other():
    q = title("transformer")
    assert remove_citation_range(q) == q


def test_remove_citation_range_from_and():
    q = title("transformer") & citations(100)
    result = remove_citation_range(q)
    assert result == title("transformer")


def test_remove_citation_range_nested():
    q = (title("bert") & citations(50)) & author("google")
    result = remove_citation_range(q)
    assert result == And(title("bert"), author("google"))
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_combinators.py::test_extract_citation_range_simple -v`
Expected: FAIL with ImportError

**Step 3: Implement helper functions**

Add to `scimesh/query/combinators.py`:

```python
def extract_citation_range(query: Query) -> CitationRange | None:
    """Extract CitationRange from query if present.

    Args:
        query: The query AST to check.

    Returns:
        CitationRange if found, None otherwise.
    """
    match query:
        case CitationRange() as cr:
            return cr
        case And(left=l, right=r) | Or(left=l, right=r):
            return extract_citation_range(l) or extract_citation_range(r)
        case Not(operand=o):
            return extract_citation_range(o)
        case _:
            return None


def remove_citation_range(query: Query) -> Query | None:
    """Remove CitationRange from query, returning the remaining query.

    Args:
        query: The query AST to transform.

    Returns:
        The query without CitationRange, or None if nothing remains.
    """
    match query:
        case CitationRange():
            return None
        case Field():
            return query
        case YearRange():
            return query
        case And(left=l, right=r):
            new_left = remove_citation_range(l)
            new_right = remove_citation_range(r)
            if new_left is None and new_right is None:
                return None
            if new_left is None:
                return new_right
            if new_right is None:
                return new_left
            return And(new_left, new_right)
        case Or(left=l, right=r):
            new_left = remove_citation_range(l)
            new_right = remove_citation_range(r)
            if new_left is None and new_right is None:
                return None
            if new_left is None:
                return new_right
            if new_right is None:
                return new_left
            return Or(new_left, new_right)
        case Not(operand=o):
            new_operand = remove_citation_range(o)
            if new_operand is None:
                return None
            return Not(new_operand)
        case _:
            return query
```

**Step 4: Run all helper tests**

Run: `uv run pytest tests/test_combinators.py -k citation -v`
Expected: PASS

**Step 5: Commit**

```bash
git add scimesh/query/combinators.py tests/test_combinators.py
git commit -m "feat(query): add extract_citation_range and remove_citation_range helpers"
```

---

## Task 3: Add CITEDBY/CITATIONS to parser

**Files:**
- Modify: `scimesh/query/parser.py`
- Test: `tests/test_parser.py`

**Step 1: Write failing tests for parser**

Add to `tests/test_parser.py`:

```python
from scimesh.query.combinators import CitationRange


def test_parse_citedby_equals():
    q = parse("CITEDBY = 100")
    assert q == CitationRange(min=100, max=100)


def test_parse_citedby_greater():
    q = parse("CITEDBY > 50")
    assert q == CitationRange(min=51, max=None)


def test_parse_citedby_greater_equal():
    q = parse("CITEDBY >= 100")
    assert q == CitationRange(min=100, max=None)


def test_parse_citedby_less():
    q = parse("CITEDBY < 100")
    assert q == CitationRange(min=None, max=99)


def test_parse_citedby_less_equal():
    q = parse("CITEDBY <= 100")
    assert q == CitationRange(min=None, max=100)


def test_parse_citations_alias():
    """CITATIONS should work as alias for CITEDBY."""
    q = parse("CITATIONS >= 50")
    assert q == CitationRange(min=50, max=None)


def test_parse_citedby_with_title():
    q = parse("TITLE(deep learning) AND CITEDBY >= 100")
    assert isinstance(q, And)
    assert q.left == Field("title", "deep learning")
    assert q.right == CitationRange(min=100, max=None)


def test_parse_citedby_with_pubyear():
    q = parse("TITLE(ml) AND PUBYEAR > 2020 AND CITEDBY >= 50")
    assert isinstance(q, And)
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_parser.py::test_parse_citedby_equals -v`
Expected: FAIL with SyntaxError

**Step 3: Implement parser changes**

Modify `scimesh/query/parser.py`:

1. Add import:
```python
from .combinators import And, CitationRange, Field, Not, Or, Query, YearRange
```

2. Update TOKEN_PATTERN to include CITEDBY|CITATIONS:
```python
TOKEN_PATTERN = re.compile(
    r"(TITLE-ABS-KEY|TITLE-ABS|TITLE|ABS|KEY|AUTHOR|AUTH|DOI|ALL|FULL|PUBYEAR|CITEDBY|CITATIONS|AND NOT|AND|OR|>=|<=|[()><=]|\d+|\"[^\"]*\"|[^\s()><=]+)"
)
```

3. Update `parse_primary()` to handle CITEDBY/CITATIONS:
```python
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
```

4. Add `parse_citedby()` method:
```python
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
```

**Step 4: Run all parser tests**

Run: `uv run pytest tests/test_parser.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add scimesh/query/parser.py tests/test_parser.py
git commit -m "feat(parser): add CITEDBY/CITATIONS operators to query DSL"
```

---

## Task 4: Add citation filter to OpenAlex provider

**Files:**
- Modify: `scimesh/providers/openalex.py`
- Test: `tests/test_openalex.py`

**Step 1: Write failing test**

Add to `tests/test_openalex.py`:

```python
from scimesh.query.combinators import citations, title


def test_openalex_citation_filter_min():
    """Test that CitationRange with min translates to filter."""
    provider = OpenAlex()
    query = title("transformer") & citations(100)
    search_str, filter_str = provider._build_params(query)
    assert "cited_by_count:>=100" in filter_str


def test_openalex_citation_filter_max():
    """Test that CitationRange with max translates to filter."""
    provider = OpenAlex()
    query = title("transformer") & citations(max=500)
    search_str, filter_str = provider._build_params(query)
    assert "cited_by_count:<=500" in filter_str


def test_openalex_citation_filter_range():
    """Test that CitationRange with min and max translates to filters."""
    provider = OpenAlex()
    query = title("transformer") & citations(100, 500)
    search_str, filter_str = provider._build_params(query)
    assert "cited_by_count:>=100" in filter_str
    assert "cited_by_count:<=500" in filter_str
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_openalex.py::test_openalex_citation_filter_min -v`
Expected: FAIL

**Step 3: Implement OpenAlex citation filter**

Modify `scimesh/providers/openalex.py`:

1. Update import:
```python
from scimesh.query.combinators import And, CitationRange, Field, Not, Or, Query, YearRange
```

2. Add CitationRange handling to `_collect_filters()`:
```python
def _collect_filters(self, query: Query, filters: list[str]) -> None:
    """Collect filter parameters from query."""
    match query:
        case Field(field="fulltext", value=v):
            filters.append(f"fulltext.search:{v}")
        case Field(field="author", value=v):
            filters.append(f"raw_author_name.search:{v}")
        case Field(field="doi", value=v):
            filters.append(f"doi:{v}")
        case And(left=l, right=r) | Or(left=l, right=r):
            self._collect_filters(l, filters)
            self._collect_filters(r, filters)
        case Not(operand=o):
            neg_filters: list[str] = []
            self._collect_filters(o, neg_filters)
            for f in neg_filters:
                filters.append(f"!{f}")
        case YearRange(start=s, end=e):
            if s and e:
                if s == e:
                    filters.append(f"publication_year:{s}")
                else:
                    filters.append(f"publication_year:{s}-{e}")
            elif s:
                filters.append(f"publication_year:>{s - 1}")
            elif e:
                filters.append(f"publication_year:<{e + 1}")
        case CitationRange(min=min_val, max=max_val):
            if min_val is not None:
                filters.append(f"cited_by_count:>={min_val}")
            if max_val is not None:
                filters.append(f"cited_by_count:<={max_val}")
        case _:
            pass  # title, abstract, keyword handled as search terms
```

**Step 4: Run tests**

Run: `uv run pytest tests/test_openalex.py -k citation -v`
Expected: PASS

**Step 5: Commit**

```bash
git add scimesh/providers/openalex.py tests/test_openalex.py
git commit -m "feat(openalex): add native citation count filter support"
```

---

## Task 5: Add citation filter to Semantic Scholar provider

**Files:**
- Modify: `scimesh/providers/semantic_scholar.py`
- Test: `tests/test_semantic_scholar.py`

**Step 1: Write failing test**

Add to `tests/test_semantic_scholar.py`:

```python
from scimesh.query.combinators import citations, title


def test_semantic_scholar_citation_filter_min():
    """Test that CitationRange min translates to minCitationCount param."""
    provider = SemanticScholar()
    query = title("transformer") & citations(100)
    query_str, year_start, year_end, min_citations = provider._translate_query(query)
    assert min_citations == 100
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_semantic_scholar.py::test_semantic_scholar_citation_filter_min -v`
Expected: FAIL (returns 3 values, not 4)

**Step 3: Implement Semantic Scholar citation filter**

Modify `scimesh/providers/semantic_scholar.py`:

1. Update import:
```python
from scimesh.query.combinators import And, CitationRange, Field, Not, Or, Query, YearRange, has_fulltext
```

2. Update `_translate_query()` to return min_citations:
```python
def _translate_query(self, query: Query) -> tuple[str, int | None, int | None, int | None]:
    """Convert Query AST to Semantic Scholar query string, year range, and min citations.

    Returns (query_string, year_start, year_end, min_citations).
    Semantic Scholar uses a simple query string with optional year and citation filters.
    """
    terms: list[str] = []
    year_start: int | None = None
    year_end: int | None = None
    min_citations: int | None = None

    year_start, year_end, min_citations = self._collect_terms(query, terms)
    return (" ".join(terms), year_start, year_end, min_citations)
```

3. Update `_collect_terms()` to handle CitationRange:
```python
def _collect_terms(self, query: Query, terms: list[str]) -> tuple[int | None, int | None, int | None]:
    """Recursively collect search terms, year range, and min citations from query AST.

    Returns (year_start, year_end, min_citations).
    """
    year_start: int | None = None
    year_end: int | None = None
    min_citations: int | None = None

    match query:
        # ... existing cases ...
        case CitationRange(min=min_val):
            min_citations = min_val
        case And(left=l, right=r):
            ys1, ye1, mc1 = self._collect_terms(l, terms)
            ys2, ye2, mc2 = self._collect_terms(r, terms)
            year_start = ys1 or ys2
            year_end = ye1 or ye2
            min_citations = mc1 or mc2
        case Or(left=l, right=r):
            # ... update to collect min_citations ...
        case Not(operand=o):
            ys, ye, mc = self._collect_terms(o, neg_terms)
            # ...
        case YearRange(start=s, end=e):
            year_start = s
            year_end = e

    return year_start, year_end, min_citations
```

4. Update `_search_api()` to use minCitationCount:
```python
async def _search_api(self, query: Query) -> AsyncIterator[Paper]:
    # ...
    query_str, year_start, year_end, min_citations = self._translate_query(query)

    params: dict[str, str | int] = {
        "query": query_str,
        "limit": 100,
        "fields": API_FIELDS,
    }

    if min_citations is not None:
        params["minCitationCount"] = min_citations

    # ... rest of method ...
```

5. Add client-side filter for max citations (API doesn't support it):
```python
# In _search_api, after parsing paper:
citation_range = extract_citation_range(query)
if citation_range and citation_range.max is not None:
    if paper.citations_count is None or paper.citations_count > citation_range.max:
        continue
```

**Step 4: Run tests**

Run: `uv run pytest tests/test_semantic_scholar.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add scimesh/providers/semantic_scholar.py tests/test_semantic_scholar.py
git commit -m "feat(semantic_scholar): add citation filter (native min, client-side max)"
```

---

## Task 6: Add client-side citation filter to Scopus

**Files:**
- Modify: `scimesh/providers/scopus.py`
- Test: `tests/test_scopus.py`

**Step 1: Write failing test**

Add to `tests/test_scopus.py`:

```python
from scimesh.query.combinators import citations, title, CitationRange, extract_citation_range, remove_citation_range


def test_scopus_removes_citation_from_query():
    """Scopus should remove CitationRange from query (handled client-side)."""
    provider = Scopus()
    query = title("transformer") & citations(100)
    # The translated query should not contain citation info
    query_str = provider._translate_query(remove_citation_range(query))
    assert "CITEDBY" not in query_str
    assert "100" not in query_str
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_scopus.py::test_scopus_removes_citation_from_query -v`
Expected: FAIL (or error if CitationRange not handled)

**Step 3: Implement Scopus client-side filter**

Modify `scimesh/providers/scopus.py`:

1. Update imports:
```python
from scimesh.query.combinators import (
    And, CitationRange, Field, Not, Or, Query, YearRange,
    extract_citation_range, remove_citation_range
)
```

2. Update `_translate_query()` to handle CitationRange:
```python
def _translate_query(self, query: Query) -> str:
    """Convert Query AST to Scopus query syntax."""
    match query:
        # ... existing cases ...
        case CitationRange():
            return ""  # Handled client-side
        case _:
            raise ValueError(f"Unsupported query node: {query}")
```

3. Update `search()` to filter client-side:
```python
async def search(self, query: Query) -> AsyncIterator[Paper]:
    """Search Scopus and yield papers."""
    if self._client is None:
        raise RuntimeError("Provider not initialized. Use 'async with provider:'")

    if not self._api_key:
        raise ValueError("Scopus requires an API key. Set SCOPUS_API_KEY or pass api_key=")

    # Extract citation filter before translating query
    citation_filter = extract_citation_range(query)
    query_without_citations = remove_citation_range(query)

    if query_without_citations is None:
        return

    query_str = self._translate_query(query_without_citations)
    logger.debug("Translated query: %s", query_str)

    # ... existing API call code ...

    for entry in results:
        paper = self._parse_entry(entry)
        if paper:
            # Apply client-side citation filter
            if citation_filter:
                if paper.citations_count is None:
                    continue
                if citation_filter.min is not None and paper.citations_count < citation_filter.min:
                    continue
                if citation_filter.max is not None and paper.citations_count > citation_filter.max:
                    continue
            yield paper
```

**Step 4: Run tests**

Run: `uv run pytest tests/test_scopus.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add scimesh/providers/scopus.py tests/test_scopus.py
git commit -m "feat(scopus): add client-side citation filter"
```

---

## Task 7: Add client-side citation filter to CrossRef

**Files:**
- Modify: `scimesh/providers/crossref.py`
- Test: `tests/test_crossref.py`

**Step 1: Write failing test**

Add to `tests/test_crossref.py`:

```python
from scimesh.query.combinators import citations, title, remove_citation_range


def test_crossref_removes_citation_from_query():
    """CrossRef should remove CitationRange from query (handled client-side)."""
    provider = CrossRef()
    query = title("transformer") & citations(100)
    query_terms, filters = provider._build_params(remove_citation_range(query))
    assert "100" not in query_terms
    assert all("citation" not in f.lower() for f in filters)
```

**Step 2: Run test to verify behavior**

Run: `uv run pytest tests/test_crossref.py::test_crossref_removes_citation_from_query -v`

**Step 3: Implement CrossRef client-side filter**

Modify `scimesh/providers/crossref.py`:

1. Update imports:
```python
from scimesh.query.combinators import (
    And, CitationRange, Field, Not, Or, Query, YearRange, has_fulltext,
    extract_citation_range, remove_citation_range
)
```

2. Update `_collect_params()` to handle CitationRange:
```python
def _collect_params(self, query: Query, query_terms: list[str], filters: list[str]) -> None:
    """Recursively collect query terms and filters from query AST."""
    match query:
        # ... existing cases ...
        case CitationRange():
            pass  # Handled client-side
```

3. Update `_search_api()` to filter client-side:
```python
async def _search_api(self, query: Query) -> AsyncIterator[Paper]:
    """Execute the actual CrossRef API search."""
    if self._client is None:
        raise RuntimeError("Provider not initialized. Use 'async with provider:'")

    # Extract citation filter
    citation_filter = extract_citation_range(query)
    query_without_citations = remove_citation_range(query)

    if query_without_citations is None:
        return

    query_terms, filters = self._build_params(query_without_citations)
    # ... rest of API call ...

    for item in items:
        paper = self._parse_item(item)
        if paper:
            # Apply client-side citation filter
            if citation_filter:
                if paper.citations_count is None:
                    continue
                if citation_filter.min is not None and paper.citations_count < citation_filter.min:
                    continue
                if citation_filter.max is not None and paper.citations_count > citation_filter.max:
                    continue
            yield paper
```

**Step 4: Run tests**

Run: `uv run pytest tests/test_crossref.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add scimesh/providers/crossref.py tests/test_crossref.py
git commit -m "feat(crossref): add client-side citation filter"
```

---

## Task 8: Add client-side citation filter to arXiv

**Files:**
- Modify: `scimesh/providers/arxiv.py`
- Test: `tests/test_arxiv.py`

**Step 1: Write failing test**

Add to `tests/test_arxiv.py`:

```python
from scimesh.query.combinators import citations, title, remove_citation_range


def test_arxiv_removes_citation_from_query():
    """arXiv should remove CitationRange from query (handled client-side, but arXiv has no citation data)."""
    provider = Arxiv()
    query = title("transformer") & citations(100)
    query_without_citations = remove_citation_range(query)
    query_str = provider._translate_query(query_without_citations)
    assert "100" not in query_str
```

**Step 2: Run test to verify behavior**

Run: `uv run pytest tests/test_arxiv.py::test_arxiv_removes_citation_from_query -v`

**Step 3: Implement arXiv client-side filter**

Modify `scimesh/providers/arxiv.py`:

1. Update imports:
```python
from scimesh.query.combinators import (
    And, CitationRange, Field, Not, Or, Query, YearRange,
    extract_citation_range, remove_citation_range
)
```

2. Update `_translate_query()` to handle CitationRange:
```python
def _translate_query(self, query: Query) -> str:
    """Convert Query AST to arXiv search syntax."""
    match query:
        # ... existing cases ...
        case CitationRange():
            return ""  # arXiv doesn't have citation data
        case _:
            raise ValueError(f"Unsupported query node: {query}")
```

3. Update `search()` to filter client-side (note: arXiv papers have no citation data, so all will be filtered out if citation filter is used alone):
```python
async def search(self, query: Query) -> AsyncIterator[Paper]:
    """Search arXiv and yield papers."""
    if self._client is None:
        raise RuntimeError("Provider not initialized. Use 'async with provider:'")

    # Extract citation filter
    citation_filter = extract_citation_range(query)
    query_without_citations = remove_citation_range(query)

    if query_without_citations is None:
        logger.warning("arXiv does not provide citation data; citation-only queries return no results")
        return

    query_str = self._translate_query(query_without_citations)
    # ... rest of search ...

    for entry in root.findall(f"{ATOM_NS}entry"):
        paper = self._parse_entry(entry)
        if paper and self._matches_year_filter(paper, year_filter):
            # Apply client-side citation filter
            # Note: arXiv papers have citations_count=None, so they'll be filtered out
            if citation_filter:
                if paper.citations_count is None:
                    continue
                if citation_filter.min is not None and paper.citations_count < citation_filter.min:
                    continue
                if citation_filter.max is not None and paper.citations_count > citation_filter.max:
                    continue
            yield paper
```

**Step 4: Run tests**

Run: `uv run pytest tests/test_arxiv.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add scimesh/providers/arxiv.py tests/test_arxiv.py
git commit -m "feat(arxiv): add client-side citation filter (warns that arXiv has no citation data)"
```

---

## Task 9: Export new symbols and run full test suite

**Files:**
- Modify: `scimesh/__init__.py`
- Modify: `scimesh/query/__init__.py` (if exists)

**Step 1: Update exports**

Check if `scimesh/query/__init__.py` exists and update exports:

```python
from scimesh.query.combinators import (
    And,
    CitationRange,
    Field,
    Not,
    Or,
    Query,
    YearRange,
    abstract,
    author,
    citations,
    doi,
    extract_citation_range,
    extract_fulltext_term,
    fulltext,
    has_fulltext,
    keyword,
    remove_citation_range,
    remove_fulltext,
    title,
    year,
)
```

**Step 2: Run full test suite**

Run: `uv run pytest -v`
Expected: All tests PASS

**Step 3: Run linter**

Run: `uv run ruff check scimesh tests`
Expected: No errors

**Step 4: Run type checker**

Run: `uv run pyright scimesh`
Expected: No errors

**Step 5: Final commit**

```bash
git add scimesh/
git commit -m "feat: complete citation filter implementation across all providers"
```

---

## Summary

After completing all tasks, the following capabilities are available:

**String DSL:**
```
TITLE(deep learning) AND CITEDBY >= 100
TITLE(ml) AND PUBYEAR > 2020 AND CITATIONS > 50
```

**Python DSL:**
```python
from scimesh.query import title, citations, year

query = title("deep learning") & citations(100) & year(2020)
```

**Provider support:**
- OpenAlex: Native `filter=cited_by_count:>=N`
- Semantic Scholar: Native `minCitationCount=N`, client-side max
- Scopus: Client-side filter
- CrossRef: Client-side filter
- arXiv: Client-side filter (but arXiv has no citation data)
