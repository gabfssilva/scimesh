---
name: synthesizing
description: |
  Use when generating PRISMA flowcharts and synthesis for systematic literature review.

  TRIGGERS: slr export, synthesize, PRISMA, generate report, synthesis, generate report, export review
---

# Synthesizing

Generate PRISMA flowcharts and synthesis reports for systematic literature review.

## Overview

Generate final synthesis including PRISMA flowchart, included/excluded paper tables, and export options.

**Prerequisite:** Screening must be complete (scimesh:screening). Optionally, extraction too (scimesh:extracting).

## Generate Stats from Vault

```bash
# Screening statistics
uvx scimesh vault stats {review_path}/
```

Output:
```
Total papers: 120

  included:    31 (25.8%)
  excluded:    85 (70.8%)
  maybe:        4 (3.3%)
  unscreened:   0 (0.0%)

Progress: 100%
```

## Generate PRISMA Flowchart

```bash
# Generate PRISMA synthesis with mermaid flowchart and tables
uvx scimesh vault prisma {review_path}/ -o {review_path}/synthesis.md
```

This generates a complete synthesis document with:
- Mermaid PRISMA flowchart
- Summary statistics
- Included papers table
- Excluded papers table with reasons
- Protocol summary

## Export Options

```bash
# Export included papers to BibTeX
uvx scimesh vault export {review_path}/ --status included -f bibtex -o included.bib

# Export to RIS
uvx scimesh vault export {review_path}/ --status included -f ris -o included.ris

# Export to CSV (spreadsheet-friendly)
uvx scimesh vault export {review_path}/ -f csv -o all_papers.csv

# Export to JSON
uvx scimesh vault export {review_path}/ --status included -f json -o included.json

# Export to YAML
uvx scimesh vault export {review_path}/ -f yaml -o papers.yaml
```

## Vault CLI Reference

```bash
# Screening statistics
uvx scimesh vault stats {review_path}/

# List papers (table format)
uvx scimesh vault list {review_path}/

# List unscreened papers
uvx scimesh vault list {review_path}/ --status unscreened

# List included papers as paths
uvx scimesh vault list {review_path}/ --status included --format paths

# List papers as JSON
uvx scimesh vault list {review_path}/ --format json

# Generate PRISMA synthesis
uvx scimesh vault prisma {review_path}/ -o synthesis.md
```

## Final Output Structure

```
{review_path}/
├── index.yaml          # Protocol + stats
├── searches.yaml       # Search history
├── papers.yaml         # Paper list with search_ids
├── synthesis.md        # PRISMA + synthesis (generated)
├── included.bib        # BibTeX of included papers
└── papers/
    └── {year}/             # Organized by publication year
        └── {paper-slug}/
            ├── index.yaml
            ├── fulltext.pdf
            ├── problem.md
            ├── method.md
            ├── result.md
            └── condensed.md
```

## Ask Before Export Format

```python
{
    "question": "How do you want to export the review?",
    "header": "Export",
    "options": [
        {"label": "Full synthesis (Rec)", "description": "PRISMA + tables + narrative"},
        {"label": "BibTeX only", "description": "Export citations for reference manager"},
        {"label": "CSV summary", "description": "Spreadsheet-friendly format"}
    ],
    "multiSelect": True
}
```
