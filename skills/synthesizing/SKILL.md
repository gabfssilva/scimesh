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

## Generate Stats from Workspace

```bash
# Screening statistics
uvx scimesh workspace stats {review_path}/
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
uvx scimesh workspace prisma {review_path}/ -o {review_path}/synthesis.md
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
uvx scimesh workspace export {review_path}/ --status included -f bibtex -o included.bib

# Export to RIS
uvx scimesh workspace export {review_path}/ --status included -f ris -o included.ris

# Export to CSV (spreadsheet-friendly)
uvx scimesh workspace export {review_path}/ -f csv -o all_papers.csv

# Export to JSON
uvx scimesh workspace export {review_path}/ --status included -f json -o included.json

# Export to YAML
uvx scimesh workspace export {review_path}/ -f yaml -o papers.yaml
```

## Workspace CLI Reference

```bash
# Screening statistics
uvx scimesh workspace stats {review_path}/

# List papers (table format)
uvx scimesh workspace list {review_path}/

# List unscreened papers
uvx scimesh workspace list {review_path}/ --status unscreened

# List included papers
uvx scimesh workspace list {review_path}/ --status included

# Generate PRISMA synthesis
uvx scimesh workspace prisma {review_path}/ -o synthesis.md
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
            └── condensed.md
```

## Pre-Extraction Decision

Before writing a narrative synthesis, check how many included papers have extraction data (condensed.md files). Present this to the user:

```python
{
    "question": "Extraction status: {extracted}/{included} papers have condensed.md. How to proceed?",
    "header": "Synthesis",
    "options": [
        {"label": "Synthesize now (Recommended)", "description": "Use available data (abstracts + any extractions)"},
        {"label": "Extract first", "description": "Run scimesh:extracting before synthesis"},
        {"label": "PRISMA only", "description": "Generate PRISMA flowchart without narrative synthesis"}
    ],
    "multiSelect": False
}
```

To count extraction status, check each included paper directory for a `condensed.md` file:

```bash
# List included papers
uvx scimesh workspace list {review_path}/ --status included
```

Then use Glob to check which of those paper directories contain `condensed.md`:
```python
Glob(pattern="{review_path}/papers/**/condensed.md")
```

## Synthesis Workflow

After PRISMA generation, write a **narrative synthesis** that ties the included papers together. The approach depends on whether extraction was done.

### When extraction WAS done (condensed.md exists)

1. **Read all condensed.md files** from included papers. Each contains structured summaries of the paper's problem, method, results, and limitations.
2. **Identify themes** across papers. Group by:
   - Research question or problem addressed
   - Methodology (e.g., experimental vs. observational, simulation vs. analytical)
   - Domain or application area
   - Chronological development of the field
3. **Write thematic sections** (minimum 3). Each section should:
   - Open with the theme and why it matters
   - Discuss papers that contribute to this theme, citing them by author/year
   - Compare and contrast findings across papers within the theme
   - Note where papers agree, disagree, or leave gaps
4. **Write a cross-cutting discussion** that connects themes and identifies the overall state of knowledge.

### When extraction was NOT done (abstracts only)

1. **Read index.yaml** for each included paper. Use the `title`, `abstract`, `year`, and any screening `notes` fields.
2. **Identify themes** from abstracts alone. Grouping will be coarser:
   - Broad topic or research area
   - Type of contribution (theoretical, empirical, review, tool/framework)
   - Recency (older foundational work vs. recent developments)
3. **Write thematic sections** (minimum 3). Each section should:
   - Summarize what the group of papers addresses based on abstracts
   - Cite papers by author/year
   - Acknowledge that depth is limited without full-text extraction
4. **Flag papers** where the abstract alone is insufficient to place them confidently in a theme.

### Narrative structure template

Use this structure for the narrative synthesis section appended to `synthesis.md`:

```markdown
## Narrative Synthesis

### Overview
Brief paragraph summarizing the scope: how many papers, what time period, what broad questions they address.

### Theme 1: {Descriptive Theme Name}
Discussion of papers in this theme. Every claim cites at least one paper.
Compare and contrast findings. Note agreements and contradictions.

### Theme 2: {Descriptive Theme Name}
...

### Theme 3: {Descriptive Theme Name}
...

### Cross-Cutting Discussion
How do the themes relate? What is the overall trajectory of the field?
Where do findings converge or diverge across themes?

### Gaps and Limitations
What questions remain unanswered? What methodological limitations are common?
What populations, domains, or conditions are underrepresented?
```

Do NOT just list papers sequentially. The synthesis must be organized by themes, not by paper.

## Quality Criteria

The narrative synthesis must meet ALL of the following criteria:

1. **Every claim must cite at least one paper.** Do not make unsupported assertions. Use (Author, Year) format consistently.
2. **Include contradictions and disagreements.** If two papers reach different conclusions, say so explicitly. Do not smooth over conflicts in the literature.
3. **Note limitations of the evidence base.** Are most studies small-scale? Is there geographic or methodological bias? Are there publication bias concerns?
4. **Provide concrete numbers and metrics when available.** Instead of "the method improved performance," write "the method improved accuracy by 12% (Author, 2023)." Pull specific values from condensed.md or abstracts.
5. **Minimum 3 thematic sections.** If the included papers span fewer than 3 clear themes, discuss methodological variation or chronological development as additional dimensions.
6. **No orphan papers.** Every included paper must appear in at least one thematic section. If a paper does not fit any theme, create a "Other Contributions" section rather than omitting it.
7. **Balanced coverage.** Do not devote 80% of the synthesis to one paper. Aim for roughly proportional coverage across the included studies.

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
