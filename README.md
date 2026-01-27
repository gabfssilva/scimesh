# scimesh

A Python library for systematic literature search across multiple academic databases.

Search arXiv, OpenAlex, and Scopus with a unified API. Export to BibTeX, RIS, CSV, or JSON. Download PDFs via Open Access (Unpaywall).

## Features

- **Multi-provider search** - arXiv, OpenAlex, Scopus (parallel queries)
- **Scopus-style query syntax** - `TITLE(transformers) AND AUTHOR(Vaswani)`
- **Programmatic query API** - Compose queries with Python operators (`&`, `|`, `~`)
- **Export formats** - BibTeX, RIS, CSV, JSON
- **PDF download** - Open Access via Unpaywall (Sci-Hub opt-in)
- **Async streaming** - Results arrive as they're found
- **Automatic deduplication** - By DOI or title+year across providers

## Installation

```bash
pip install scimesh
```

With uv:

```bash
uv add scimesh
```

## Quick Start

### CLI

```bash
# Search arXiv and OpenAlex (default providers)
scimesh search "TITLE(transformer) AND AUTHOR(Vaswani)"

# Export to BibTeX
scimesh search "TITLE(BERT)" -f bibtex -o papers.bib

# Download PDFs from search results
scimesh search "TITLE(attention)" -f json | scimesh download -o ./pdfs
```

### Python API

```python
import asyncio
from scimesh import search, title, author, year
from scimesh.providers import Arxiv, OpenAlex

async def main():
    query = title("transformer") & author("Vaswani") & year(2017, 2023)

    result = await search(
        query,
        providers=[Arxiv(), OpenAlex()],
        max_results=100,
    )

    for paper in result.papers:
        print(f"{paper.title} ({paper.year})")

asyncio.run(main())
```

---

## Query Syntax

### Scopus-Style Strings

The library parses Scopus-compatible query strings automatically.

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
| `ALL(...)` | Full text search | `ALL(protein folding)` |

**Year Operators:**

| Operator | Description | Example |
|----------|-------------|---------|
| `PUBYEAR = 2023` | Exact year | Papers from 2023 |
| `PUBYEAR > 2020` | After year | Papers from 2021+ |
| `PUBYEAR < 2020` | Before year | Papers until 2019 |
| `PUBYEAR >= 2020` | From year | Papers from 2020+ |
| `PUBYEAR <= 2023` | Until year | Papers until 2023 |

**Logical Operators:**

| Operator | Description | Example |
|----------|-------------|---------|
| `AND` | Both conditions | `TITLE(BERT) AND AUTHOR(Google)` |
| `OR` | Either condition | `TITLE(GPT) OR TITLE(BERT)` |
| `AND NOT` | Exclude condition | `TITLE(neural) AND NOT AUTHOR(Smith)` |
| `(...)` | Grouping | `(TITLE(A) OR TITLE(B)) AND AUTHOR(C)` |

**Examples:**

```bash
# Basic title search
scimesh search "TITLE(transformer)"

# Author + title
scimesh search "TITLE(attention is all you need) AND AUTHOR(Vaswani)"

# Multiple terms with OR
scimesh search "TITLE(GPT-4) OR TITLE(GPT-3) OR TITLE(ChatGPT)"

# Exclusion
scimesh search "TITLE(machine learning) AND NOT AUTHOR(Smith)"

# Year range
scimesh search "TITLE(BERT) AND PUBYEAR > 2018 AND PUBYEAR < 2022"

# Complex nested query
scimesh search "(TITLE(transformer) OR TITLE(attention)) AND AUTHOR(Google) AND PUBYEAR >= 2017"

# Search across title, abstract, and keywords
scimesh search "TITLE-ABS-KEY(reinforcement learning) AND PUBYEAR = 2023"

# Full text search
scimesh search "ALL(CRISPR gene editing)"
```

### Programmatic Query API

Build queries with Python operators for type safety and composability.

**Field Builders:**

```python
from scimesh import title, abstract, author, keyword, doi, fulltext, year

# Single field queries
q = title("transformer architecture")
q = author("Yoshua Bengio")
q = abstract("self-attention mechanism")
q = keyword("natural language processing")
q = doi("10.1038/nature14539")
q = fulltext("protein structure prediction")
```

**Year Filters:**

```python
from scimesh import year

q = year(2020, 2024)      # Range: 2020-2024 inclusive
q = year(start=2020)      # From 2020 onwards
q = year(end=2023)        # Until 2023
q = year(2023, 2023)      # Exact year 2023
```

**Combining with Operators:**

```python
from scimesh import title, author, year

# AND: both conditions must match
q = title("BERT") & author("Google")

# OR: either condition matches
q = title("GPT-3") | title("GPT-4")

# NOT: exclude matches
q = title("neural networks") & ~author("Smith")

# Complex combinations
q = (
    (title("transformer") | title("attention"))
    & author("Vaswani")
    & year(2017, 2023)
    & ~keyword("computer vision")
)
```

**Full Example:**

```python
import asyncio
from scimesh import search, title, author, year
from scimesh.providers import Arxiv, OpenAlex, Scopus

async def main():
    # Build query programmatically
    query = title("large language model") & year(2022, 2024)

    # Or use string syntax (equivalent)
    query = "TITLE(large language model) AND PUBYEAR >= 2022"

    result = await search(
        query,
        providers=[Arxiv(), OpenAlex()],
        max_results=50,
    )

    print(f"Found {len(result.papers)} papers")

    # Export to BibTeX
    from scimesh.export import get_exporter
    get_exporter("bibtex").export(result, "papers.bib")

asyncio.run(main())
```

**Streaming Mode:**

```python
# Process papers as they arrive from providers
async for paper in search(query, providers, stream=True):
    print(f"Found: {paper.title}")
```

---

## CLI Reference

### `scimesh search`

```bash
scimesh search <query> [OPTIONS]
```

| Flag | Description | Default |
|------|-------------|---------|
| `-p, --provider` | Providers: arxiv, openalex, scopus | arxiv, openalex |
| `-n, --max` | Max results per provider | 100 |
| `-t, --total` | Max total results across all providers | - |
| `-f, --format` | Output: tree, csv, json, bibtex, ris | tree |
| `-o, --output` | Output file path | stdout |
| `--on-error` | Error handling: fail, warn, ignore | warn |
| `--no-dedupe` | Disable deduplication | false |

### `scimesh download`

```bash
scimesh download [DOI] [OPTIONS]
```

| Flag | Description | Default |
|------|-------------|---------|
| `-f, --from` | File with DOIs (one per line) | - |
| `-o, --output` | Output directory | current dir |
| `--scihub` | Enable Sci-Hub fallback (see disclaimer) | false |

**Examples:**

```bash
# Single DOI (Open Access only)
scimesh download "10.1038/nature14539" -o ./pdfs

# With Sci-Hub fallback enabled
scimesh download "10.1038/nature14539" -o ./pdfs --scihub

# From file
scimesh download -f dois.txt -o ./pdfs

# From search results (piped JSON)
scimesh search "TITLE(attention)" -f json | scimesh download -o ./pdfs
```

Requires `UNPAYWALL_EMAIL` env var for Open Access.

> **Disclaimer**: Sci-Hub is disabled by default. The `--scihub` flag enables it as a fallback when Open Access sources fail. Sci-Hub may violate copyright laws in your jurisdiction. Use at your own discretion and risk.

---

## Providers

| Provider | API Key | Notes |
|----------|---------|-------|
| arXiv | No | Preprints |
| OpenAlex | No | 61M+ papers, largest open database |
| Scopus | `SCOPUS_API_KEY` | Requires institutional access |

```python
from scimesh.providers import Arxiv, OpenAlex, Scopus

providers = [
    Arxiv(),
    OpenAlex(mailto="you@example.com"),  # Optional, for polite pool
    Scopus(),  # Uses SCOPUS_API_KEY env var
]
```

---

## Local Development

```bash
git clone https://github.com/gabfssilva/scimesh
cd scimesh
uv sync

# Run CLI
uv run scimesh search "TITLE(transformer)"

# Install as tool
uv tool install --reinstall .

# Tests
uv run pytest
```

## License

MIT
