---
name: protocoling
description: |
  Use when starting a systematic literature review to define the research protocol.

  TRIGGERS: slr init, protocol, PICO, SPIDER, define criteria, start review, iniciar revisao, definir protocolo, criterios de inclusao, criterios de exclusao
---

# Protocoling

Define research protocol for systematic literature review using PICO, SPIDER, or Custom framework.

## Overview

Guide users through defining a **complete SLR protocol** before any search. This is an **interactive skill** - use AskUserQuestion to gather all protocol information.

**Core principle:** No search without protocol. Use `scimesh vault init` to create the vault with protocol.

## Iron Rules

1. **NO search without protocol** - Protocol MUST exist BEFORE any search
2. **NO autonomous query building** - Query construction is INTERACTIVE; user approves each component
3. **Use vault commands** - Always use `scimesh vault` commands for SLR

## Workflow

Use AskUserQuestion to gather protocol info. **All questions need 2-4 options.**

### Step 1: Framework Selection (FIRST QUESTION)

**Question 1: Framework**
```python
{
    "question": "Which framework do you want to use for your research question?",
    "header": "Framework",
    "options": [
        {"label": "PICO", "description": "Population, Intervention, Comparison, Outcome - quantitative/clinical research"},
        {"label": "SPIDER", "description": "Sample, Phenomenon, Design, Evaluation, Research type - qualitative research"},
        {"label": "Custom", "description": "Build your own from building blocks - flexible for any domain"}
    ],
    "multiSelect": False
}
```

### Step 2: Framework-Specific Questions

#### If PICO Selected

Ask for PICO components:
- **Population**: Who or what is being studied?
- **Intervention**: What treatment, method, or exposure?
- **Comparison**: What is the alternative (if any)?
- **Outcome**: What effects or results are measured?

#### If SPIDER Selected

Ask for SPIDER components:
- **Sample**: Who are the participants?
- **Phenomenon of Interest**: What experience or behavior?
- **Design**: What research design (interviews, focus groups, etc.)?
- **Evaluation**: What outcomes or findings?
- **Research type**: What type (qualitative, mixed-methods)?

#### If Custom Selected

Ask the following building block questions:

**Question 2a: Context fields**
```python
{
    "question": "Which CONTEXT fields do you need? (what/who is being studied)",
    "header": "Context",
    "options": [
        {"label": "Population", "description": "Group or entities being studied"},
        {"label": "Sample", "description": "Specific subset or participants"},
        {"label": "Setting", "description": "Environment or location"},
        {"label": "Domain", "description": "Field or application area"}
    ],
    "multiSelect": True
}
```

**Question 2b: Action fields**
```python
{
    "question": "Which ACTION fields do you need? (what is being done/studied)",
    "header": "Action",
    "options": [
        {"label": "Intervention", "description": "Treatment or method applied"},
        {"label": "Method", "description": "Technique or algorithm"},
        {"label": "Phenomenon", "description": "Experience or behavior of interest"},
        {"label": "Mechanism", "description": "How something works"}
    ],
    "multiSelect": True
}
```

**Question 2c: Result fields**
```python
{
    "question": "Which RESULT fields do you need? (what is measured/evaluated)",
    "header": "Result",
    "options": [
        {"label": "Outcome", "description": "Effects or results measured"},
        {"label": "Metrics", "description": "Specific measures used"},
        {"label": "Evaluation", "description": "Assessment criteria"}
    ],
    "multiSelect": True
}
```

### Step 3: Framework-Independent Questions

These questions apply to ALL frameworks:

**Question 3: Year range**
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

**Question 4: Languages**
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

**Question 5-7: Study types (3 questions, same header)**
```python
{
    "questions": [
        {
            "question": "Which study types to include?",
            "header": "Study types",
            "options": [
                {"label": "Primary research", "description": "Original experiments, empirical studies"},
                {"label": "Systematic reviews", "description": "Systematic reviews, meta-analyses"},
                {"label": "Scoping reviews", "description": "Scoping or mapping reviews"},
                {"label": "Narrative reviews", "description": "Literature reviews, overviews"}
            ],
            "multiSelect": True
        },
        {
            "question": "Which study types to include?",
            "header": "Study types",
            "options": [
                {"label": "Conference papers", "description": "Full papers from conferences"},
                {"label": "Preprints", "description": "arXiv, bioRxiv, medRxiv, SSRN"},
                {"label": "Theses/dissertations", "description": "PhD, Master's theses"},
                {"label": "Book chapters", "description": "Chapters from edited volumes"}
            ],
            "multiSelect": True
        },
        {
            "question": "Which study types to EXCLUDE?",
            "header": "Study types",
            "options": [
                {"label": "Conference abstracts", "description": "Abstracts without full text"},
                {"label": "Editorials/letters", "description": "Opinion pieces, letters to editor"},
                {"label": "Commentaries", "description": "Short commentaries on other papers"},
                {"label": "Protocols", "description": "Study protocols without results"}
            ],
            "multiSelect": True
        }
    ]
}
```

**Question 8: Minimum citations**
```python
{
    "question": "Set a minimum citation threshold?",
    "header": "Citations",
    "options": [
        {"label": "No minimum (Recommended)", "description": "Include all papers regardless of citations"},
        {"label": "At least 5 citations", "description": "Filter out very low-impact papers"},
        {"label": "At least 10 citations", "description": "Moderate impact threshold"},
        {"label": "At least 50 citations", "description": "High impact only"}
    ],
    "multiSelect": False
}
```

**Question 9: Data/Code availability**
```python
{
    "question": "Require open data or code?",
    "header": "Open science",
    "options": [
        {"label": "No requirement (Recommended)", "description": "Include all papers"},
        {"label": "Prefer open data/code", "description": "Prioritize but don't exclude"},
        {"label": "Must have open data", "description": "Exclude papers without available data"},
        {"label": "Must have open code", "description": "Exclude papers without available code"}
    ],
    "multiSelect": False
}
```

**Question 10-11: Search providers (2 questions, same header)**
```python
{
    "questions": [
        {
            "question": "Which providers to search?",
            "header": "Providers",
            "options": [
                {"label": "arXiv", "description": "Preprints in CS, Physics, Math. Free full-text PDFs."},
                {"label": "OpenAlex", "description": "200M+ works, open metadata, citation counts."},
                {"label": "Semantic Scholar", "description": "AI/ML focus, citation graph, abstracts."}
            ],
            "multiSelect": True
        },
        {
            "question": "Which providers to search?",
            "header": "Providers",
            "options": [
                {"label": "arXiv", "description": "Preprints, especially for CS/ML/Physics."},
                {"label": "Scopus", "description": "Requires SCOPUS_API_KEY environment variable."}
            ],
            "multiSelect": True
        }
    ]
}
```

**Question 12: Target pool size**
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

**Question 13: Research question (free text)**
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

After gathering all information via AskUserQuestion, create the vault based on the selected framework:

### For PICO Framework

```bash
uvx scimesh vault init {review_path}/ \
  --question "Research question here" \
  --framework pico \
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

### For SPIDER Framework

```bash
uvx scimesh vault init {review_path}/ \
  --question "Research question here" \
  --framework spider \
  --sample "Sample description" \
  --phenomenon "Phenomenon of interest" \
  --design "Research design" \
  --evaluation "Evaluation criteria" \
  --research-type "qualitative" \
  --inclusion "First inclusion criterion" \
  --exclusion "First exclusion criterion" \
  --databases "arxiv,openalex,semantic_scholar" \
  --year-range "2020-2024"
```

### For Custom Framework

```bash
uvx scimesh vault init {review_path}/ \
  --question "Research question here" \
  --framework custom \
  --field "population:Description of population" \
  --field "method:Description of method" \
  --field "outcome:Description of outcome" \
  --inclusion "First inclusion criterion" \
  --exclusion "First exclusion criterion" \
  --databases "arxiv,openalex,semantic_scholar" \
  --year-range "2020-2024"
```

**Note:** Use `--inclusion` and `--exclusion` multiple times for multiple criteria. For Custom framework, use `--field` multiple times with the format `fieldname:description`.

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

**index.yaml** - Protocol and stats (structure varies by framework):

### PICO Framework
```yaml
protocol:
  framework: pico
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

### SPIDER Framework
```yaml
protocol:
  framework: spider
  question: "Research question here"
  sample: ""          # S - Sample
  phenomenon: ""      # PI - Phenomenon of Interest
  design: ""          # D - Design
  evaluation: ""      # E - Evaluation
  research_type: ""   # R - Research type
  inclusion:
    - "criterion 1"
  exclusion:
    - "criterion 1"
  databases:
    - arxiv
    - openalex
  year_range: "2021-2026"

stats:
  total: 0
  included: 0
  excluded: 0
  maybe: 0
  unscreened: 0
  with_pdf: 0
```

### Custom Framework
```yaml
protocol:
  framework: custom
  question: "Research question here"
  fields:
    population: "Description"
    method: "Description"
    outcome: "Description"
  inclusion:
    - "criterion 1"
  exclusion:
    - "criterion 1"
  databases:
    - arxiv
    - openalex
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

# Add custom fields (for custom framework)
uvx scimesh vault set {review_path}/ --field "newfield:Description"
```

## Validation

Before proceeding to search (scimesh:searching), verify:
- [ ] Vault exists with index.yaml
- [ ] Framework is specified (pico, spider, or custom)
- [ ] At least 1 inclusion criterion defined
- [ ] At least 1 exclusion criterion defined
- [ ] Research question is filled

**If validation fails:** Run `vault init` or use `vault set`/`add-*` to complete protocol.

## Next Step

After protocol is complete, use **scimesh:searching** to build and execute the query.
