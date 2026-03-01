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

**Core principle:** No search without protocol. Use `uvx scimesh workspace init --type slr` to create the workspace with protocol.

## Iron Rules

1. **NO search without protocol** - Protocol MUST exist BEFORE any search
2. **NO autonomous query building** - Query construction is INTERACTIVE; user approves each component
3. **Use workspace commands** - Always use `uvx scimesh workspace` commands for SLR

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
        {"label": "Last 5 years (Recommended)", "description": "Dynamic: based on current year"},
        {"label": "Last 10 years", "description": "Dynamic: based on current year"},
        {"label": "Last 3 years", "description": "Dynamic: based on current year"},
        {"label": "Custom range", "description": "You specify"}
    ],
    "multiSelect": False
}
```

**Note:** Compute the actual year range dynamically from the current date. For example, if today is 2026, "Last 5 years" means "2021-2026".

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

**Question 5: Study types to include**
```python
{
    "questions": [
        {
            "question": "Which study types to include?",
            "header": "Include",
            "options": [
                {"label": "Primary research", "description": "Original experiments, empirical studies"},
                {"label": "Systematic reviews", "description": "Systematic reviews, meta-analyses"},
                {"label": "Conference papers", "description": "Full papers from conferences"},
                {"label": "Preprints", "description": "arXiv, bioRxiv, medRxiv, SSRN"}
            ],
            "multiSelect": True
        },
        {
            "question": "Which study types to EXCLUDE?",
            "header": "Exclude",
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

**Question 6: Minimum citations**
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

**Question 7: Data/Code availability**
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

**Question 8: Search providers**
```python
{
    "question": "Which providers to search?",
    "header": "Providers",
    "options": [
        {"label": "OpenAlex (Recommended)", "description": "200M+ works, open metadata, citation counts."},
        {"label": "Semantic Scholar", "description": "AI/ML focus, citation graph, abstracts."},
        {"label": "arXiv", "description": "Preprints in CS, Physics, Math. Free full-text PDFs."},
        {"label": "Scopus", "description": "Comprehensive coverage. Requires SCOPUS_API_KEY environment variable."}
    ],
    "multiSelect": True
}
```

**Question 9: Target pool size**
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

**Question 10: Research question (free text)**
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

## Create Workspace with Protocol

After gathering all information via AskUserQuestion, create the workspace in two steps:

### Step 1: Initialize the workspace

```bash
uvx scimesh workspace init {review_path}/ \
  --type slr \
  --question "Research question here" \
  --framework pico \
  --databases "arxiv,openalex,semantic_scholar" \
  --year-range "2021-2026"
```

**Available flags for `workspace init`:**
- `--type`: slr, exploration, collection (required for SLR)
- `--question`: Research question
- `--framework`: pico, spider, custom
- `--databases`: Comma-separated provider list
- `--year-range`: Year range string

### Step 2: Add inclusion and exclusion criteria

```bash
# Add inclusion criteria (one call with all criteria)
uvx scimesh workspace add-inclusion {review_path}/ \
  "First inclusion criterion" \
  "Second inclusion criterion"

# Add exclusion criteria
uvx scimesh workspace add-exclusion {review_path}/ \
  "First exclusion criterion" \
  "Second exclusion criterion"
```

### Step 3: Set framework-specific fields

The `workspace init` creates the workspace with an empty framework. To populate framework fields (PICO, SPIDER, or Custom), **edit the index.yaml directly** using the Edit tool:

#### For PICO Framework

Edit `{review_path}/index.yaml` to set:
```yaml
framework:
  type: pico
  fields:
    population: "Description of population"
    intervention: "Description of intervention"
    comparison: "Description of comparison"
    outcome: "Description of outcome"
```

#### For SPIDER Framework

Edit `{review_path}/index.yaml` to set:
```yaml
framework:
  type: spider
  fields:
    sample: "Description of sample"
    phenomenon: "Description of phenomenon"
    design: "Description of design"
    evaluation: "Description of evaluation"
    research_type: "qualitative"
```

#### For Custom Framework

Edit `{review_path}/index.yaml` to set:
```yaml
framework:
  type: custom
  fields:
    population: "Description"
    method: "Description"
    outcome: "Description"
```

## Directory Structure

The workspace creates this structure:

```
{review_path}/
├── index.yaml       # Workspace config + stats
├── log.yaml         # Search history (queries, results)
├── papers.yaml      # Paper list with search_ids
└── papers/
    └── {year}/              # Organized by publication year
        └── {paper-slug}/
            ├── index.yaml   # Paper metadata + screening status
            └── fulltext.pdf # PDF (if downloaded)
```

**Note:** `{review_path}` is user-defined. Examples: `./reviews/my-slr/`, `~/Documents/reviews/transformers-2024/`

## Workspace File Structure

**index.yaml** - Workspace config and stats:

### SLR Workspace (actual structure)
```yaml
type: slr
question: "Research question here"
framework:
  type: pico
  fields:
    population: ""
    intervention: ""
    comparison: ""
    outcome: ""
constraints:
  databases:
    - arxiv
    - openalex
    - semantic_scholar
  year_range: "2021-2026"
inclusion:
  - "criterion 1"
exclusion:
  - "criterion 1"
stats:
  total: 0
  included: 0
  excluded: 0
  maybe: 0
  unscreened: 0
  with_pdf: 0
```

**log.yaml** - Search history:
```yaml
- id: b135ec76a5e4
  type: search
  query: "TITLE(attention) AND PUBYEAR > 2022"
  providers: [arxiv, openalex]
  executed_at: "2026-01-30T10:00:00Z"
  results:
    total: 50
    unique: 45
```

**papers.yaml** - Paper list with traceability:
```yaml
- path: 2024/yang-simulating-hard-attention
  doi: "10.1234/example"
  title: "Simulating Hard Attention..."
  status: unscreened
  search_ids: [b135ec76a5e4]
```

## Modifying Protocol

After init, use these commands to modify:

```bash
# Modify workspace-level fields
uvx scimesh workspace set {review_path}/ --question "New RQ" --year-range "2020-2024"

# Add inclusion criteria
uvx scimesh workspace add-inclusion {review_path}/ "Must use deep learning"

# Add exclusion criteria
uvx scimesh workspace add-exclusion {review_path}/ "Survey papers"

# For framework-specific fields, edit index.yaml directly with the Edit tool
```

## Validation

Before proceeding to search (scimesh:searching), verify:
- [ ] Workspace exists with index.yaml
- [ ] Framework is specified (pico, spider, or custom) with fields populated
- [ ] At least 1 inclusion criterion defined
- [ ] At least 1 exclusion criterion defined
- [ ] Research question is filled

**If validation fails:** Run `workspace init --type slr` or use `workspace set`/`add-*`/Edit to complete protocol.

## Next Step

After protocol is complete, use **scimesh:searching** to build and execute the query.
