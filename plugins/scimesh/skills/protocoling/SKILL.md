---
name: protocoling
description: |
  Use when starting a systematic literature review to define the research protocol.

  TRIGGERS: slr init, protocol, PICO, define criteria, start review, iniciar revisao, definir protocolo, criterios de inclusao, criterios de exclusao
---

# Protocoling

Define research protocol for systematic literature review using PICO framework.

## Overview

Guide users through defining a **complete SLR protocol** before any search. This is an **interactive skill** - use AskUserQuestion to gather all protocol information.

**Core principle:** No search without protocol. Use `scimesh vault init` to create the vault with protocol.

## Iron Rules

1. **NO search without protocol** - Protocol MUST exist BEFORE any search
2. **NO autonomous query building** - Query construction is INTERACTIVE; user approves each component
3. **Use vault commands** - Always use `scimesh vault` commands for SLR

## Workflow

Use AskUserQuestion to gather protocol info. **All questions need 2-4 options.**

**Question 1: Year range**
```python
{
    "question": "What year range should papers be from?",
    "header": "Years",
    "options": [
        {"label": "Last 5 years (Recommended)", "description": "2021-2026"},
        {"label": "Last 10 years", "description": "2016-2026"},
        {"label": "Last 3 years", "description": "2023-2026"},
        {"label": "Custom range", "description": "You specify"}
    ],
    "multiSelect": False
}
```

**Question 2: Languages**
```python
{
    "question": "What languages are acceptable?",
    "header": "Languages",
    "options": [
        {"label": "English only (Recommended)", "description": "Most common in academia"},
        {"label": "English + Portuguese", "description": "Include PT papers"},
        {"label": "Any language", "description": "No language filter"}
    ],
    "multiSelect": False
}
```

**Question 3: Paper types to exclude**
```python
{
    "question": "What types of papers to EXCLUDE?",
    "header": "Exclusions",
    "options": [
        {"label": "Reviews + abstracts (Recommended)", "description": "Only primary research"},
        {"label": "Only conference abstracts", "description": "Allow reviews"},
        {"label": "No exclusions", "description": "Include all types"}
    ],
    "multiSelect": False
}
```

**Question 4: Target pool size**
```python
{
    "question": "How many papers do you want to screen?",
    "header": "Pool size",
    "options": [
        {"label": "30-100 (Recommended)", "description": "Focused review"},
        {"label": "100-200", "description": "Comprehensive review"},
        {"label": "200-500", "description": "Exhaustive review"}
    ],
    "multiSelect": False
}
```

**Question 5: Research question (free text)**
```python
{
    "question": "Describe your research question:",
    "header": "Research Q",
    "options": [
        {"label": "Example: How does X affect Y?", "description": "Cause-effect question"},
        {"label": "Example: What methods exist for X?", "description": "Survey question"}
    ],
    "multiSelect": False
}
# User will select "Other" and type their actual question
```

## Create Vault with Protocol

After gathering all information via AskUserQuestion, create the vault:

```bash
uvx scimesh vault init {review_path}/ \
  --question "Research question here" \
  --population "Population" \
  --intervention "Intervention" \
  --comparison "Comparison" \
  --outcome "Outcome" \
  --inclusion "First inclusion criterion" \
  --inclusion "Second inclusion criterion" \
  --exclusion "First exclusion criterion" \
  --exclusion "Second exclusion criterion" \
  --databases "arxiv,openalex,semantic_scholar" \
  --year-range "2020-2024"
```

**Note:** Use `--inclusion` and `--exclusion` multiple times for multiple criteria.

## Directory Structure

The vault creates this structure:

```
{review_path}/
├── index.yaml       # Protocol + stats
├── searches.yaml    # Search history (queries, results)
├── papers.yaml      # Paper list with search_ids
├── synthesis.md     # Final PRISMA + synthesis (generated later)
└── papers/
    └── {year}/              # Organized by publication year
        └── {paper-slug}/
            ├── index.yaml   # Paper metadata + screening status
            └── fulltext.pdf # PDF (if downloaded)
```

**Note:** `{review_path}` is user-defined. Examples: `./reviews/my-slr/`, `~/Documents/reviews/transformers-2024/`

## Vault File Structure

**index.yaml** - Protocol and stats:
```yaml
protocol:
  question: "Research question here"
  population: ""      # P - Population/Problem
  intervention: ""    # I - Intervention/Exposure
  comparison: ""      # C - Comparison
  outcome: ""         # O - Outcome
  inclusion:
    - "criterion 1"
  exclusion:
    - "criterion 1"
  databases:
    - arxiv
    - openalex
    - semantic_scholar
  year_range: "2021-2026"

stats:
  total: 0
  included: 0
  excluded: 0
  maybe: 0
  unscreened: 0
  with_pdf: 0
```

**searches.yaml** - Search history:
```yaml
- id: b135ec76a5e4
  query: "TITLE(attention) AND PUBYEAR > 2022"
  providers: [arxiv, openalex]
  executed_at: "2026-01-30T10:00:00Z"
  results:
    total: 50
    unique: 45
```

**papers.yaml** - Paper list with traceability:
```yaml
- path: 2024-yang-simulating-hard-attention
  doi: "10.1234/example"
  title: "Simulating Hard Attention..."
  status: unscreened
  search_ids: [b135ec76a5e4]
```

## Modifying Protocol

After init, use these commands to modify:

```bash
# Modify protocol fields
uvx scimesh vault set {review_path}/ --question "New RQ" --year-range "2020-2024"

# Add inclusion criteria
uvx scimesh vault add-inclusion {review_path}/ "Must use deep learning"

# Add exclusion criteria
uvx scimesh vault add-exclusion {review_path}/ "Survey papers"
```

## Validation

Before proceeding to search (scimesh:searching), verify:
- [ ] Vault exists with index.yaml
- [ ] At least 1 inclusion criterion defined
- [ ] At least 1 exclusion criterion defined
- [ ] Research question is filled

**If validation fails:** Run `vault init` or use `vault set`/`add-*` to complete protocol.

## Next Step

After protocol is complete, use **scimesh:searching** to build and execute the query.
