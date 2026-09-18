# scimesh

[![PyPI version](https://img.shields.io/pypi/v/scimesh)](https://pypi.org/project/scimesh/)
[![Python](https://img.shields.io/pypi/pyversions/scimesh)](https://pypi.org/project/scimesh/)
[![CI](https://github.com/gabfssilva/scimesh/actions/workflows/ci.yml/badge.svg)](https://github.com/gabfssilva/scimesh/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A Python library for searching scientific papers across academic databases.

Search arXiv, OpenAlex, Scopus and Semantic Scholar through one API, fetch PDFs and text, and cache every fetch: repeating a search reads from SQLite instead of the network, and no paper is downloaded or extracted twice. Export to BibTeX, RIS, CSV or JSON.

## Features

- **Multi-provider search** - arXiv, OpenAlex, Scopus, Semantic Scholar, queried in parallel
- **Scopus-style query syntax** - `TITLE(transformers) AND AUTHOR(Vaswani)`
- **Programmatic query API** - compose queries with Python operators (`&`, `|`, `~`)
- **One cache** - API responses, PDFs, extracted text and failed downloads in `~/.scimesh`
- **PDF download** - Open Access via Unpaywall, Sci-Hub opt-in
- **Text extraction** - PDFs to markdown, extracted once and reused
- **Citation graph** - papers citing or cited by a paper
- **Export formats** - BibTeX, RIS, CSV, JSON
- **Async streaming** - results arrive as they are found
- **Automatic deduplication** - by DOI, or title and year, across providers

## Installation

Run without installing:

```bash
uvx scimesh search "TITLE(transformer)"
```

Install as a CLI tool:

```bash
uv tool install scimesh
```

Add to a project:

```bash
uv add scimesh
```

## Quick Start

### CLI

```bash
# Search (OpenAlex by default)
scimesh search "TITLE(transformer) AND AUTHOR(Vaswani)"

# Several providers
scimesh search "TITLE(BERT)" -p arxiv,openalex,semantic_scholar

# Export to BibTeX
scimesh search "TITLE(BERT)" -f bibtex -o papers.bib

# Download PDFs from search results
scimesh search "TITLE(attention)" -f json | scimesh download -o ./pdfs

# One paper by DOI
scimesh get "10.1038/nature14539"

# Papers citing a paper
scimesh citations "10.1038/nature14539" --direction in

# Paper text as markdown
scimesh text "10.1038/nature14539" -o paper.md

# Search the text of papers already cached
scimesh cache search "attention mechanism"
```

### Python API

```python
import asyncio
from scimesh import Scimesh

async def main():
    async with Scimesh(["arxiv", "openalex"]) as sm:
        async for paper in sm.search("TITLE(transformer) AND PUBYEAR > 2020"):
            print(f"{paper.title} ({paper.year}) - {paper.citations_count} citations")

        paper = await sm.get("10.1038/nature14539")
        text = await sm.text("10.1038/nature14539")

asyncio.run(main())
```

---

## Query Syntax

### Scopus-Style Strings

The library parses Scopus-compatible query strings automatically.

**Plain Text Search:**

Searching without a field specifier looks in both title and abstract:

```bash
scimesh search "transformers"                       # same as TITLE-ABS(transformers)
scimesh search "attention mechanism"
scimesh search "deep learning AND PUBYEAR > 2020"
```

**Field Operators:**

| Operator | Description | Example |
|----------|-------------|---------|
| `TITLE(...)` | Search in title | `TITLE(transformer)` |
| `ABS(...)` | Search in abstract | `ABS(attention mechanism)` |
| `KEY(...)` | Search in keywords | `KEY(machine learning)` |
| `TITLE-ABS(...)` | Title OR abstract | `TITLE-ABS(neural network)` |
| `TITLE-ABS-KEY(...)` | Title OR abstract OR keywords | `TITLE-ABS-KEY(deep learning)` |
| `AUTHOR(...)` | Search by author | `AUTHOR(Vaswani)` |
| `AUTH(...)` | Alias for AUTHOR | `AUTH(Hinton)` |
| `DOI(...)` | Search by DOI | `DOI(10.1038/nature14539)` |
| `ALL(...)` | Widest search the provider offers | `ALL(protein folding)` |

**Year Operators:**

| Operator | Description | Example |
|----------|-------------|---------|
| `PUBYEAR = 2023` | Exact year | Papers from 2023 |
| `PUBYEAR > 2020` | After year | Papers from 2021+ |
| `PUBYEAR < 2020` | Before year | Papers until 2019 |
| `PUBYEAR >= 2020` | From year | Papers from 2020+ |
| `PUBYEAR <= 2023` | Until year | Papers until 2023 |

**Citation Operators:**

| Operator | Description | Example |
|----------|-------------|---------|
| `CITEDBY >= 100` | Min citations | Papers with 100+ citations |
| `CITEDBY <= 500` | Max citations | Papers with at most 500 citations |
| `CITEDBY > 50` | More than | Papers with more than 50 citations |
| `CITEDBY < 1000` | Less than | Papers with fewer than 1000 citations |
| `CITEDBY = 0` | Exact count | Papers with no citations |
| `CITATIONS >= 100` | Alias for CITEDBY | Same as `CITEDBY >= 100` |

> **Note**: OpenAlex filters citations natively. Semantic Scholar supports a native minimum only. Other providers filter client-side, which is slower for large result sets.

**Logical Operators:**

| Operator | Description | Example |
|----------|-------------|---------|
| `AND` | Both conditions | `TITLE(BERT) AND AUTHOR(Google)` |
| `OR` | Either condition | `TITLE(GPT) OR TITLE(BERT)` |
| `AND NOT` | Exclude condition | `TITLE(neural) AND NOT AUTHOR(Smith)` |
| `(...)` | Grouping | `(TITLE(A) OR TITLE(B)) AND AUTHOR(C)` |

**Examples:**

```bash
scimesh search "TITLE(attention is all you need) AND AUTHOR(Vaswani)"
scimesh search "TITLE(GPT-4) OR TITLE(GPT-3) OR TITLE(ChatGPT)"
scimesh search "TITLE(machine learning) AND NOT AUTHOR(Smith)"
scimesh search "TITLE(BERT) AND PUBYEAR > 2018 AND PUBYEAR < 2022"
scimesh search "(TITLE(transformer) OR TITLE(attention)) AND AUTHOR(Google) AND PUBYEAR >= 2017"
scimesh search "TITLE-ABS-KEY(reinforcement learning) AND PUBYEAR = 2023"
scimesh search "TITLE(BERT) AND CITEDBY >= 100"
```

### What `ALL()` means

`ALL(...)` asks each provider for the widest search it offers, so its reach differs per provider:

| Provider | Translates to | Covers |
|----------|---------------|--------|
| arXiv | `all:"term"` | title, abstract, authors, comments |
| Scopus | `ALL(term)` | every indexed field, including references |
| OpenAlex | `fulltext.search:term` | full text where OpenAlex has it |
| Semantic Scholar | the `query` parameter | title and abstract |

None of them guarantee the text of the PDF. To search text you have extracted yourself, use `scimesh cache search`, which reads the local cache and returns the same results every time.

### Programmatic Query API

Build queries with Python operators for type safety and composability.

```python
from scimesh import title, abstract, author, keyword, doi, fulltext, year, citations

q = title("transformer architecture")
q = author("Yoshua Bengio")
q = abstract("self-attention mechanism")
q = doi("10.1038/nature14539")

q = year(2020, 2024)      # range, inclusive
q = year(start=2020)      # from 2020 onwards
q = citations(100)        # at least 100 citations
q = citations(100, 1000)  # between 100 and 1000

# AND, OR and NOT
q = title("BERT") & author("Google")
q = title("GPT-3") | title("GPT-4")
q = title("neural networks") & ~author("Smith")

q = (
    (title("transformer") | title("attention"))
    & author("Vaswani")
    & year(2017, 2023)
    & ~keyword("computer vision")
)
```

---

## Python API

Everything goes through `Scimesh`, which owns the providers, the downloaders and the cache.

```python
from scimesh import Scimesh

async with Scimesh(["openalex", "semantic_scholar"]) as sm:
    async for paper in sm.search("TITLE(transformer)"):
        ...

    paper = await sm.get("10.1038/nature14539")

    async for citing in sm.citations("10.1038/nature14539", direction="in", max_results=50):
        ...

    path = await sm.pdf("10.1038/nature14539")   # cache, else download, then cache
    text = await sm.text("10.1038/nature14539")  # cache, else extract, then cache

    async for fetch in sm.fetch_many(dois, concurrency=5, extract=True):
        print(fetch.key, fetch.source, fetch.error)

    keys = sm.search_text("attention mechanism")  # FTS5 over cached text
```

| Argument | Description | Default |
|----------|-------------|---------|
| `providers` | Names or `Provider` instances | `("openalex",)` |
| `cache` | A `Cache` instance to share | one at `~/.scimesh` |
| `scihub` | Enable the Sci-Hub fallback | `False` |
| `host_concurrency` | `"3"` or `"arxiv.org=2,api.unpaywall.org=3"` | none |
| `on_error` | `fail`, `warn` or `ignore` when a provider fails | `warn` |
| `dedupe` | Deduplicate across providers | `True` |
| `failure_ttl` | How long a failed download is remembered | 7 days |
| `response_ttl` | How long a cached API response stays usable | 1 day |
| `refresh` | Ignore cached responses, but still store new ones | `False` |

Providers can also be used directly:

```python
from scimesh.providers import Arxiv, OpenAlex

async with Scimesh([Arxiv(), OpenAlex(mailto="you@example.com")]) as sm:
    ...
```

---

## CLI Reference

### `scimesh search`

```bash
scimesh search <query> [OPTIONS]
```

| Flag | Description | Default |
|------|-------------|---------|
| `-p, --provider` | Providers, comma-separated or repeated | openalex |
| `-n, --max` | Maximum total results | 100 |
| `-f, --format` | tree, csv, json, bibtex, ris | tree |
| `-o, --output` | Output file | stdout |
| `--on-error` | fail, warn, ignore | warn |
| `--no-dedupe` | Disable deduplication | false |
| `--refresh` | Ignore cached API responses | false |
| `--log-level` | debug, info, warning, error | - |

Tree output streams to a terminal; piping switches to JSON.

### `scimesh get`

```bash
scimesh get <paper_id> [OPTIONS]
```

Fetches one paper by DOI or provider id from every provider that supports it, and merges the answers: the longest abstract, the longest author list, the highest citation count.

| Flag | Description | Default |
|------|-------------|---------|
| `-p, --provider` | Providers to query | openalex, semantic_scholar |
| `-f, --format` | tree, csv, json, bibtex, ris | tree |
| `-o, --output` | Output file | stdout |
| `--refresh` | Ignore cached API responses | false |

### `scimesh citations`

```bash
scimesh citations <paper_id> [OPTIONS]
```

| Flag | Description | Default |
|------|-------------|---------|
| `-d, --direction` | `in` (citing it), `out` (cited by it), `both` | both |
| `-p, --provider` | Providers to query | openalex |
| `-n, --max` | Maximum results | 100 |
| `-f, --format` | tree, csv, json, bibtex, ris | tree |
| `-o, --output` | Output file | stdout |
| `--refresh` | Ignore cached API responses | false |

### `scimesh download`

```bash
scimesh download [DOI] [OPTIONS]
```

Papers come from the positional argument, `--from`, or JSON piped on stdin. Each one is downloaded once, cached, and copied into the output directory.

| Flag | Description | Default |
|------|-------------|---------|
| `-f, --from` | File with DOIs, one per line | - |
| `-o, --output` | Output directory | current dir |
| `--extract` | Also extract and cache the text | false |
| `--concurrency` | Concurrent downloads | 5 |
| `--scihub` | Enable the Sci-Hub fallback | false |
| `--host-concurrency` | `3` or `arxiv.org=2,api.unpaywall.org=3` | - |

Open Access downloads need `UNPAYWALL_EMAIL`.

> **Disclaimer**: Sci-Hub is off by default. `--scihub` adds it as a last resort when Open Access fails. It may violate copyright law in your jurisdiction. Use at your own discretion and risk.

### `scimesh text`

```bash
scimesh text <paper_id> [OPTIONS]
```

Prints the paper as markdown. The PDF is downloaded if needed, the text extracted once, and both are cached.

| Flag | Description | Default |
|------|-------------|---------|
| `-o, --output` | Output file | stdout |
| `--scihub` | Enable the Sci-Hub fallback | false |
| `--host-concurrency` | Concurrency limit for downloads | - |

### `scimesh cache`

```bash
scimesh cache stats            # what the cache holds
scimesh cache search <term>    # FTS5 query over cached text
scimesh cache gc               # drop dangling rows and files, expire stale responses
scimesh cache clear            # remove everything
```

---

## Cache

One SQLite database plus the PDF files:

```
~/.scimesh/
├── cache.db                  # API responses, documents, text, FTS5 index, failures
└── files/
    └── <sha256>.pdf
```

Everything in it is re-fetchable, so deleting the directory costs time, never work. Set `SCIMESH_HOME` to put it somewhere else.

- **API responses** are cached per URL for a day, so repeating a search, a `get` or a citation walk costs nothing. Pagination caches page by page, so asking for fewer results does not poison the entry. Only `200` responses are stored: a provider that failed is retried, not remembered. `--refresh` ignores what is stored and replaces it.
- **PDFs** are content-addressed, so the same file arriving under two DOIs is stored once.
- **Text** is extracted with `pymupdf4llm` and stored with the extractor version, so upgrading the extractor re-extracts instead of serving stale output.
- **Failures** are remembered for 7 days, so a paywalled paper is not retried on every run.
- **TTL applies to responses and failures only.** A DOI resolves to the same PDF forever, and cached text is invalidated by the extractor version instead.
- **Writes** go to the file first and the row second, so an interrupted download leaves at most an unreferenced file, which `cache gc` collects.
- **Keys** are normalized DOIs. arXiv ids collapse onto their DOI (`1706.03762` and `arxiv:1706.03762` both become `10.48550/arxiv.1706.03762`); papers without a DOI keep a prefixed provider id.

```python
from scimesh import Cache

with Cache() as cache:
    cache.pdf("10.1038/nature14539")           # Path | None
    cache.text("10.1038/nature14539")          # str | None
    cache.search("attention mechanism")        # list of keys, FTS5 syntax
    cache.response(url)                        # (body, content_type) | None
    cache.stats()
```

---

## Providers

| Provider | API Key | Notes |
|----------|---------|-------|
| arXiv | No | Preprints |
| OpenAlex | No | 61M+ papers, largest open database. `OPENALEX_MAILTO` joins the polite pool, which has a higher rate limit |
| Scopus | `SCOPUS_API_KEY` | Requires institutional access |
| Semantic Scholar | `SEMANTIC_SCHOLAR_API_KEY` (optional) | 200M+ papers, citation graph |

| Provider | search | get | citations | citation filter |
|----------|--------|-----|-----------|-----------------|
| arXiv | Yes | Yes | No | Client-side* |
| OpenAlex | Yes | Yes | Yes (in/out) | Native |
| Scopus | Yes | Yes | Yes (in only) | Client-side |
| Semantic Scholar | Yes | Yes | Yes (in/out) | Native (min), client-side (max) |

*arXiv does not report citation counts, so citation filters return nothing there.

---

## Local Development

```bash
git clone https://github.com/gabfssilva/scimesh
cd scimesh
uv sync

uv run scimesh search "TITLE(transformer)"
uv tool install --reinstall .

uv run pytest                      # unit tests
uv run pytest tests/integration    # hits the real APIs
```

## License

MIT
