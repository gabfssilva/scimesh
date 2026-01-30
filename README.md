# scimesh

[![PyPI version](https://img.shields.io/pypi/v/scimesh)](https://pypi.org/project/scimesh/)
[![Python](https://img.shields.io/pypi/pyversions/scimesh)](https://pypi.org/project/scimesh/)
[![CI](https://github.com/gabfssilva/scimesh/actions/workflows/ci.yml/badge.svg)](https://github.com/gabfssilva/scimesh/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A Python library for systematic literature search across multiple academic databases.

Search arXiv, OpenAlex, Scopus, Semantic Scholar, and CrossRef with a unified API. Export to BibTeX, RIS, CSV, JSON, or Vault. Download PDFs via Open Access (Unpaywall). Index and search full-text content locally.

## Features

- **Multi-provider search** - arXiv, OpenAlex, Scopus, Semantic Scholar, CrossRef (parallel queries)
- **Scopus-style query syntax** - `TITLE(transformers) AND AUTHOR(Vaswani)`
- **Programmatic query API** - Compose queries with Python operators (`&`, `|`, `~`)
- **Export formats** - BibTeX, RIS, CSV, JSON, Vault
- **PDF download** - Open Access via Unpaywall (Sci-Hub opt-in) with local caching
- **Fetch specific papers** - Get paper metadata by DOI with `scimesh get`
- **Citation graph** - Get papers citing or cited by a paper with `scimesh citations`
- **Fulltext search** - Index PDFs locally and search their content with SQLite FTS5
- **Metadata merging** - Combine paper data from multiple sources for richer results
- **Async streaming** - Results arrive as they're found
- **Automatic deduplication** - By DOI or title+year across providers

## Installation

Run directly without installing:

```bash
uvx scimesh search "TITLE(transformer)"
```

Install as a CLI tool (recommended):

```bash
uv tool install scimesh
```

Add to a project:

```bash
uv add scimesh
```

With pip:

```bash
pip install scimesh
```

## Quick Start

### CLI

```bash
# Search arXiv and OpenAlex (default providers)
scimesh search "TITLE(transformer) AND AUTHOR(Vaswani)"

# Search multiple providers (comma-separated)
scimesh search "TITLE(BERT)" -p arxiv,openalex,crossref

# Export to BibTeX
scimesh search "TITLE(BERT)" -f bibtex -o papers.bib

# Download PDFs from search results
scimesh search "TITLE(attention)" -f json | scimesh download -o ./pdfs

# Get a specific paper by DOI
scimesh get "10.1038/nature14539"

# Get papers citing a specific paper
scimesh citations "10.1038/nature14539" --direction in

# Index PDFs for fulltext search
scimesh index ./papers/

# Full text search (uses native API for arXiv/Scopus, local index for others)
scimesh search "ALL(attention mechanism)"
```

### Python API

```python
import asyncio
from scimesh import search, title, author, year, citations
from scimesh.providers import Arxiv, OpenAlex

async def main():
    query = title("transformer") & author("Vaswani") & year(2017, 2023) & citations(50)

    result = await search(
        query,
        providers=[Arxiv(), OpenAlex()],
        max_results=100,
    )

    for paper in result.papers:
        print(f"{paper.title} ({paper.year}) - {paper.citations_count} citations")

asyncio.run(main())
```

---

## Query Syntax

### Scopus-Style Strings

The library parses Scopus-compatible query strings automatically.

**Plain Text Search:**

You can search without field specifiers - plain text searches in both title and abstract:

```bash
scimesh search "transformers"                    # Same as TITLE-ABS(transformers)
scimesh search "attention mechanism"             # Searches title OR abstract
scimesh search "deep learning AND PUBYEAR > 2020"  # Can combine with operators
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
| `ALL(...)` | Full text search | `ALL(protein folding)` |

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

> **Note**: OpenAlex supports native citation filtering. Semantic Scholar supports native min filter only. Other providers filter client-side (slower for large result sets).

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

# Filter by citation count (highly cited papers)
scimesh search "TITLE(BERT) AND CITEDBY >= 100"

# Citation range
scimesh search "TITLE(transformer) AND CITATIONS >= 50 AND CITATIONS <= 500"

# Full text search
scimesh search "ALL(CRISPR gene editing)"
```

### Programmatic Query API

Build queries with Python operators for type safety and composability.

**Field Builders:**

```python
from scimesh import title, abstract, author, keyword, doi, fulltext, year, citations

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

**Citation Filters:**

```python
from scimesh import citations

q = citations(100)            # Min 100 citations (same as citations(min=100))
q = citations(min=50)         # At least 50 citations
q = citations(max=500)        # At most 500 citations
q = citations(100, 1000)      # Between 100 and 1000 citations
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

# With citation filter
q = title("BERT") & year(2019, 2024) & citations(100)
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
| `-p, --provider` | Providers (comma-separated or repeated): arxiv, openalex, scopus, semantic_scholar, crossref | openalex |
| `-n, --max` | Max total results | 100 |
| `-f, --format` | Output: tree, csv, json, bibtex, ris, vault | tree |
| `-o, --output` | Output file path | stdout |
| `--on-error` | Error handling: fail, warn, ignore | warn |
| `--no-dedupe` | Disable deduplication | false |
| `--local-fulltext-indexing` | Auto-download and index PDFs for fulltext (S2/CrossRef) | false |
| `--scihub` | Enable Sci-Hub fallback for `--local-fulltext-indexing` downloads | false |
| `--host-concurrency` | Concurrency limit: `3` (all hosts) or `arxiv.org=2,unpaywall.org=3` (per-host) | 5 |
| `--log-level` | Log level: debug, info, warning, error | - |

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

### `scimesh get`

Fetch metadata for a specific paper by DOI.

```bash
scimesh get <paper_id> [OPTIONS]
```

| Flag | Description | Default |
|------|-------------|---------|
| `-p, --provider` | Providers (comma-separated): openalex, semantic_scholar, crossref, arxiv, scopus | openalex, semantic_scholar |
| `-f, --format` | Output: tree, json, bibtex, ris | tree |
| `-o, --output` | Output file path | stdout |
| `--merge` | Merge results from multiple providers | true |

**Examples:**

```bash
# Get paper by DOI (merges data from multiple providers)
scimesh get "10.1038/nature14539"

# Get from specific providers
scimesh get "10.1038/nature14539" -p openalex,crossref

# Export to BibTeX
scimesh get "10.1038/nature14539" -f bibtex -o paper.bib

# Get arXiv paper by ID
scimesh get "1706.03762" --provider arxiv
```

### `scimesh citations`

Get papers citing or cited by a specific paper.

```bash
scimesh citations <paper_id> [OPTIONS]
```

| Flag | Description | Default |
|------|-------------|---------|
| `-p, --provider` | Providers (comma-separated): openalex, semantic_scholar, scopus | openalex |
| `-d, --direction` | Citation direction: in, out, both | both |
| `-n, --max` | Max results | 100 |
| `-f, --format` | Output: tree, csv, json, bibtex, ris | tree |
| `-o, --output` | Output file path | stdout |

**Directions:**
- `in` - Papers that cite this paper (incoming citations)
- `out` - Papers that this paper cites (references)
- `both` - Both directions

**Examples:**

```bash
# Get papers citing a DOI
scimesh citations "10.1038/nature14539" --direction in

# Get references (papers cited by this paper)
scimesh citations "10.1038/nature14539" --direction out

# From Semantic Scholar with limit
scimesh citations "10.1038/nature14539" -p semantic_scholar -n 50

# Export to JSON
scimesh citations "10.1038/nature14539" -f json -o citations.json
```

### `scimesh index`

Index PDFs for fulltext search.

```bash
scimesh index <directory> [OPTIONS]
```

| Flag | Description | Default |
|------|-------------|---------|
| `--clear` | Clear existing index before indexing | false |

**Examples:**

```bash
# Index all PDFs in a directory
scimesh index ./papers/

# Clear and re-index
scimesh index ./papers/ --clear

# Then search indexed content with ALL()
scimesh search "ALL(attention mechanism)"
```

The index is stored at `~/.scimesh/fulltext.db` using SQLite FTS5.

---

## Providers

| Provider | API Key | Notes |
|----------|---------|-------|
| arXiv | No | Preprints |
| OpenAlex | No | 61M+ papers, largest open database |
| Scopus | `SCOPUS_API_KEY` | Requires institutional access |
| Semantic Scholar | `SEMANTIC_SCHOLAR_API_KEY` (optional) | 200M+ papers, citation graph |
| CrossRef | `CROSSREF_API_KEY` (optional) | DOI metadata, references |

```python
from scimesh.providers import Arxiv, OpenAlex, Scopus, SemanticScholar, CrossRef

providers = [
    Arxiv(),
    OpenAlex(mailto="you@example.com"),  # Optional, for polite pool
    Scopus(),  # Uses SCOPUS_API_KEY env var
    SemanticScholar(),  # Optional API key for higher rate limits
    CrossRef(mailto="you@example.com"),  # Optional, for polite pool
]
```

### Provider Capabilities

| Provider | search | get | citations | citation filter |
|----------|--------|-----|-----------|-----------------|
| arXiv | Yes | Yes | No | Client-side* |
| OpenAlex | Yes | Yes | Yes (in/out) | Native |
| Scopus | Yes | Yes | Yes (in only) | Client-side |
| Semantic Scholar | Yes | Yes | Yes (in/out) | Native (min) / Client-side (max) |
| CrossRef | Yes | Yes | No | Client-side |

*arXiv does not provide citation counts, so citation filters return no results.

---

## Vault Export

The `vault` format exports papers to a folder structure where each paper gets its own directory containing an `index.yaml` with metadata and an optional `fulltext.pdf`. A root `index.yaml` tracks the full corpus with query, providers, statistics, and paper list.

This structure is designed to be **LLM-friendly**: agents can read the YAML metadata, process PDFs, and extend the schema with custom fields for screening, annotations, or workflow tracking. The format supports incremental updates—run searches multiple times and new papers are added while existing ones are preserved.

### Usage

```bash
# Export search results to vault
scimesh search "TITLE(transformer)" -f vault -o ./papers-vault

# With PDF downloads (Open Access)
scimesh search "TITLE(attention)" -f vault -o ./review-vault

# With Sci-Hub fallback for paywalled papers
scimesh search "TITLE(BERT)" -f vault -o ./review-vault --scihub

# Run again to add more papers (incremental)
scimesh search "TITLE(GPT)" -f vault -o ./review-vault
```

### Structure

```
papers-vault/
├── index.yaml                          # Root index with query, stats, paper list
├── 2017-vaswani-attention-is-all-you/
│   ├── index.yaml                      # Paper metadata
│   └── fulltext.pdf                    # PDF (if downloaded)
├── 2018-devlin-bert-pre-training-of/
│   ├── index.yaml
│   └── fulltext.pdf
└── 2020-brown-language-models-are/
    ├── index.yaml
    └── fulltext.pdf
```

### Root index.yaml

```yaml
query: "TITLE(transformer) AND PUBYEAR > 2016"
providers:
  - openalex
  - arxiv
searched_at: "2024-01-15T10:30:00Z"
updated_at: "2024-01-16T14:00:00Z"  # Present after incremental updates
stats:
  total: 150
  by_provider:
    openalex: 100
    arxiv: 50
  with_pdf: 120
  deduplicated: 5
  skipped: 10
papers:
  - path: 2017-vaswani-attention-is-all-you
    doi: "10.48550/arXiv.1706.03762"
    title: "Attention Is All You Need"
  - path: 2018-devlin-bert-pre-training-of
    doi: "10.18653/v1/N19-1423"
    title: "BERT: Pre-training of Deep Bidirectional Transformers"
  # ...
```

### Paper index.yaml

```yaml
title: "Attention Is All You Need"
authors:
  - Ashish Vaswani
  - Noam Shazeer
  - Niki Parmar
year: 2017
doi: "10.48550/arXiv.1706.03762"
sources:
  - arxiv
  - openalex
urls:
  arxiv: "https://arxiv.org/abs/1706.03762"
  openalex: "https://openalex.org/W2963403868"
tags:
  - machine-learning
  - attention-mechanism
citations: 95000
journal: "Advances in Neural Information Processing Systems"
open_access: true
pdf: fulltext.pdf
abstract: "The dominant sequence transduction models are based on complex recurrent..."
```

### Designed for LLM Agents

The vault format enables LLM agents to perform systematic literature reviews autonomously. An agent can:

1. **Build the corpus** - Run `scimesh search` to populate the vault with papers and PDFs
2. **Understand the scope** - Read `index.yaml` to see all papers, stats, and the original query
3. **Screen papers** - Read each paper's metadata and abstract, then add `screening_status: included/excluded` and `exclusion_reason` fields
4. **Extract data** - Read PDFs, extract relevant findings, and store them in custom fields like `extracted_findings` or `methods_summary`
5. **Track progress** - Add workflow fields like `review_stage`, `last_reviewed`, or `assigned_to`
6. **Generate synthesis** - Aggregate structured data across papers to produce summaries, identify themes, or flag contradictions

The folder-per-paper structure means agents can also create additional files: `notes.md` for detailed annotations, `figures/` for extracted images, or `quotes.yaml` for key passages. The vault grows organically with the review process.

### Extensibility

The format is intentionally minimal. Agents can add any fields they need:

| Use Case | Custom Fields |
|----------|---------------|
| Screening | `screening_status`, `exclusion_reason`, `screener_notes` |
| Quality assessment | `quality_score`, `bias_risk`, `evidence_level` |
| Data extraction | `extracted_data`, `findings`, `methods_summary` |
| Synthesis | `themes`, `contradictions`, `synthesis_notes` |
| Workflow | `assigned_to`, `review_stage`, `last_reviewed` |

The vault grows with your workflow. Start with metadata, add structure as needed.

---

## PDF Caching

Downloaded PDFs are automatically cached at `~/.scimesh/cache/pdfs/`. This avoids re-downloading the same papers.

```python
from scimesh.download import download_papers, PaperCache

# Cache is enabled by default
async for result in download_papers(papers, output_dir):
    print(f"{result.doi}: {result.source}")  # source="cache" if cached

# Disable cache if needed
async for result in download_papers(papers, output_dir, use_cache=False):
    ...

# Access cache directly
cache = PaperCache()
if cache.has_pdf("10.1038/nature14539"):
    path = cache.get_pdf_path("10.1038/nature14539")
```

---

## Fulltext Search

Index PDFs locally and search their content using SQLite FTS5. The `ALL(...)` operator works transparently across all providers:

- **arXiv, Scopus, OpenAlex**: Use native fulltext search APIs
- **Semantic Scholar, CrossRef**: Search API with local FTS5 filter

**Important**: For providers without native fulltext support (Semantic Scholar, CrossRef), you must provide additional filters (title, author, etc.) along with `ALL()`. The search uses API results filtered by your local index.

```bash
# Index PDFs first (needed for S2/CrossRef fulltext)
scimesh index ./papers/

# arXiv/Scopus/OpenAlex: native fulltext (no additional filters needed)
scimesh search "ALL(attention mechanism)" -p arxiv
scimesh search "ALL(attention mechanism)" -p openalex

# Semantic Scholar/CrossRef: requires additional filter + local index
scimesh search "ALL(CRISPR) AND AUTHOR(Doudna)" -p crossref
scimesh search "ALL(transformer) AND TITLE(bert)" -p semantic_scholar
```

**Auto-download with `--local-fulltext-indexing`:**

For Semantic Scholar and CrossRef, you can enable automatic PDF download during fulltext searches. Papers not in the local index will be downloaded (via Open Access), text extracted, and indexed on-the-fly:

```bash
# Downloads and indexes PDFs automatically (slower, but works without pre-indexing)
scimesh search "ALL(CRISPR) AND TITLE(gene)" -p crossref --local-fulltext-indexing
```

This is useful when you don't have papers pre-indexed locally. Requires `UNPAYWALL_EMAIL` env var.

**Python API:**

```python
from scimesh.fulltext import FulltextIndex, extract_text_from_pdf
from pathlib import Path

# Create or open index
index = FulltextIndex()  # Default: ~/.scimesh/fulltext.db

# Index a PDF
text = extract_text_from_pdf(Path("paper.pdf"))
if text:
    index.add("10.1234/paper", text)

# Search
results = index.search("transformer architecture")  # Returns list of paper IDs

# FTS5 syntax supported
results = index.search('"attention mechanism"')  # Phrase search
results = index.search("deep OR statistical")     # OR search

# Check if indexed
if index.has("10.1234/paper"):
    print("Paper is indexed")

# List all indexed papers
papers = index.list_papers()
```

**Auto-download (Python API):**

```python
from scimesh.providers import CrossRef, SemanticScholar
from scimesh.query import fulltext, title

# Enable auto_download for automatic PDF download and indexing
async with CrossRef(auto_download=True) as provider:
    query = fulltext("CRISPR") & title("gene editing")
    async for paper in provider.search(query):
        print(paper.title)
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
