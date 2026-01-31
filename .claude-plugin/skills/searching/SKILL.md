---
name: searching
description: |
  Use when building search queries for systematic literature review using scimesh.

  TRIGGERS: slr search, build query, calibrate, search papers, executar busca, construir query, calibrar busca
---

# Searching

Interactive query construction and search execution for systematic literature review.

## Overview

Build search queries **collaboratively with the user**. Never search before showing the query. Always use vault search.

**Core principle:** Query construction is COLLABORATIVE. You build the query WITH the user, not FOR them.

**Prerequisite:** Protocol must be defined first (scimesh:protocoling).

## Iron Rules

1. **NO autonomous query building** - Query construction is INTERACTIVE; user approves each component
2. **Use vault search** - Always use `scimesh vault search` for SLR
3. **ALWAYS show query in Scala code block** - User must see the FULL query before any search

## Query Visibility

**Problem:** Bash tool output truncates long queries.

**Solution:**
1. NEVER search before showing the query to user
2. Generate 3-4 query VARIATIONS first, then ask user to choose
3. Always display final query in a **Scala code block**:

```scala
TITLE-ABS("imputation" AND "tabular")
  AND TITLE-ABS("deep learning" OR "neural network" OR "autoencoder")
  AND PUBYEAR > 2020
  AND CITEDBY >= 10
```

## Scopus-style Syntax (used by scimesh)

| Field | Syntax | Example |
|-------|--------|---------|
| Title | `TITLE(x)` | `TITLE(transformer)` |
| Abstract | `ABS(x)` | `ABS("machine learning")` |
| Title+Abstract | `TITLE-ABS(x)` | `TITLE-ABS(RLHF)` |
| Title+Abstract+Keywords | `TITLE-ABS-KEY(x)` | `TITLE-ABS-KEY(deep learning)` |
| Author | `AUTHOR(x)` | `AUTHOR(Vaswani)` |
| Year | `PUBYEAR > 2020` | `PUBYEAR > 2020 AND PUBYEAR < 2025` |
| Citations | `CITEDBY >= 100` | `CITEDBY >= 50` |

**Operators:** `AND`, `OR`, `AND NOT`, `()`

## Step 1: Identify Key Concepts

Ask user to identify main concepts:

```python
{
    "question": "What are the MAIN concepts in your research question? (select all)",
    "header": "Concepts",
    "options": [
        {"label": "Suggest concept 1", "description": "Based on research question"},
        {"label": "Suggest concept 2", "description": "Based on research question"},
        {"label": "Suggest concept 3", "description": "Based on research question"}
    ],
    "multiSelect": True
}
```

## Step 2: Expand Synonyms

For EACH concept, ask about synonyms:

```python
{
    "question": f"For concept '{concept}', which synonyms should we include?",
    "header": "Synonyms",
    "options": [
        {"label": f"'{synonym1}' (Recommended)", "description": "Common alternative"},
        {"label": f"'{synonym2}'", "description": "Related term"},
        {"label": f"'{synonym3}'", "description": "Technical variant"}
    ],
    "multiSelect": True
}
```

## Step 3: Generate Query Variations

Present 3-4 query strategies:

```python
{
    "question": "Choose query strategy:",
    "header": "Query",
    "options": [
        {"label": "Focused (Rec)", "description": "TITLE-ABS(X AND Y) - both terms required"},
        {"label": "Broad", "description": "TITLE-ABS(X) AND TITLE-ABS(Y) - separate clauses"},
        {"label": "Title-only", "description": "TITLE(X AND Y) - highest precision"}
    ],
    "multiSelect": False
}
```

Then show the FULL query for chosen strategy in Scala block.

## Step 4: Calibrate

**Only after user approves the query**, run scimesh to count results:

```bash
uvx scimesh search "QUERY" -p openalex -n 10 -f json | jq '.papers | length'
```

Then ask:

```python
{
    "question": f"Query returns ~{count} papers. Proceed or adjust?",
    "header": "Calibrate",
    "options": [
        {"label": "Good, proceed", "description": f"{count} is within target"},
        {"label": "Too many, add filters", "description": "Increase citations or narrow terms"},
        {"label": "Too few, broaden", "description": "Remove constraints or add synonyms"}
    ],
    "multiSelect": False
}
```

## Step 5: Execute Search

After final confirmation, use the vault search command:

```bash
uvx scimesh vault search {review_path}/ "FINAL QUERY" \
    -p arxiv,openalex,semantic_scholar \
    -n 200
```

**Note:** `{review_path}` is the vault directory created by `vault init` (e.g., `./reviews/my-review/`)

Vault search:
- Requires existing vault with protocol (run `vault init` first)
- Uses protocol databases by default if `-p` not specified
- Deduplicates against existing papers in `papers.yaml`
- Records search in `searches.yaml` (query, providers, results count)
- Papers track which searches found them via `search_ids`
- Downloads PDFs when available (Open Access)
- Auto-updates vault stats

## Incremental Search

Add more papers to existing vault with additional queries:

```bash
uvx scimesh vault search {review_path}/ "NEW QUERY" \
    -p crossref \
    -n 50
```

## Providers Reference

| Provider | Strengths |
|----------|-----------|
| arxiv | Preprints, CS/Physics/Math, free full-text |
| openalex | 200M+ works, open metadata, citations |
| semantic_scholar | AI/ML focus, citation graph, abstracts |
| crossref | DOI metadata, broad coverage |
| scopus | Comprehensive but requires API key |

## Next Step

After search is complete, use **scimesh:screening** to start the assisted screening loop.
