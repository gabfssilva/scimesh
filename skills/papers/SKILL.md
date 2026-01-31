---
name: papers
description: |
  Search scientific papers on arXiv, OpenAlex, Scopus, Semantic Scholar and CrossRef. Use when the user wants to search, explore or save academic papers.

  USE THIS SKILL FOR ALL:
  - Search scientific papers, academic articles, recent research
  - Explore ML, AI, NLP, Computer Vision literature
  - Save papers to Second Brain vault
  - Find paper citations and references
  - Discover new papers on specific topics
  - Search specific paper by DOI

  TRIGGERS: papers, paper, artigo, artigos, pesquisa, literatura, arxiv, openalex, scopus, semantic scholar, crossref, buscar paper, papers sobre, quero ler sobre, o que tem de novo em, salva esse paper, papers recentes, citacoes, quem cita, referencias, search papers, find papers, academic search, literature review, citations, references, save paper, recent papers, what's new in
---

# Papers Search Skill

Search scientific papers using `scimesh` via `uvx` (no global installation required).

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `SCOPUS_API_KEY` | For Scopus | Elsevier API key (+ institutional VPN) |
| `SEMANTIC_SCHOLAR_API_KEY` | Optional | For higher rate limits on Semantic Scholar |
| `UNPAYWALL_EMAIL` | For download | Email for Unpaywall API |

## Available Providers

| Provider | API Key | Notes | search | get | citations |
|----------|---------|-------|--------|-----|-----------|
| arXiv | No | Preprints | Y | Y | N |
| OpenAlex | No | 61M+ papers, largest open DB | Y | Y | Y |
| Scopus | `SCOPUS_API_KEY` | Requires institutional access | Y | Y | Y (in) |
| Semantic Scholar | Optional | 200M+ papers, citation graph | Y | Y | Y |
| CrossRef | No | DOI metadata, references | Y | Y | N |

## Basic Usage

Execute commands directly with `uvx scimesh`:

```bash
# Search with field operators
uvx scimesh search "TITLE(transformer)"

# Plain text also works (searches in title AND abstract)
uvx scimesh search "transformers"
uvx scimesh search "attention mechanism"
```

## Triggers

- "search papers about X"
- "papers about Y"
- "I want to read about Z"
- "recent papers on W"
- "what's new in transformers?"
- "save this paper to vault"

## Search Flow

1. **Understand the intent**: extract topic/query from user message
2. **Refine with questions** (use AskUserQuestion):
   - Year filter? (2024 / 2023-2024 / 2020-2024 / Run search)
   - Specific area? (ML / NLP / CV / Run search)
   - Preferred sources? (All / arXiv / OpenAlex / Run search)
   - **IMPORTANT**: Always include "Run search" as an option so the user can skip refinements
3. **Execute search using Scopus syntax**:
   ```bash
   uvx scimesh search "TITLE(transformer) AND PUBYEAR > 2020" -p arxiv,openalex -n 20
   ```
4. **Present results** in a readable format

## Full Paper Reading Flow

When the user wants to read a complete paper (fullpaper):

### 1. Download the PDF

Use the scimesh `download` command (requires `UNPAYWALL_EMAIL`):

```bash
# Download via DOI (tries Open Access via Unpaywall)
uvx scimesh download "10.1234/example" -o {papers_dir}/

# With Sci-Hub fallback (use at your own risk)
uvx scimesh download "10.1234/example" --scihub -o {papers_dir}/

# Download multiple DOIs from file
uvx scimesh download -f dois.txt -o {papers_dir}/

# Search + Download directly (pipe)
uvx scimesh search "TITLE(paper)" -f json | uvx scimesh download -o {papers_dir}/

# For arXiv papers, use DOI in the format: 10.48550/arXiv.XXXX.XXXXX
```

**PDF Caching**: PDFs are automatically cached in `~/.scimesh/cache/pdfs/` - avoids re-download.

Manual alternatives:
- **arXiv**: `https://arxiv.org/pdf/XXXX.XXXXX`
- **Generic DOI**: Check the `pdf_url` field in search results

### 2. Folder Structure

Ask user where to save papers (if not already configured):

```python
{
    "question": "Where should I save papers?",
    "header": "Papers dir",
    "options": [
        {"label": "Current directory", "description": "./papers/"},
        {"label": "Documents", "description": "~/Documents/papers/"},
        {"label": "Custom path", "description": "You specify"}
    ],
    "multiSelect": False
}
```

Save in `{papers_dir}/` with the structure:

```
{papers_dir}/
  <year>-<first-author>-<short-title>/
    fullpaper.pdf
    README.md
```

**Note:** `{papers_dir}` is user-defined. Examples: `./papers/`, `~/Documents/papers/`, `~/brain/08-papers/`

Example: `2024-wang-treb/`

### 3. Read the PDF

- Use `Read` tool directly on the `.pdf` file (native Claude Code support)
- **No need** for `pdftotext`, `PyMuPDF`, or other Python libs
- Claude Code extracts text + renders figures page by page

### 4. Systematic Reading Structure

1. **Abstract** - understand the main claim
2. **Figures/Tables** - often tell the story before the text
3. **Methodology** - how they did it
4. **Results** - specific metrics, comparisons with baselines
5. **Limitations** - what the authors admit (or omit)

### 5. Critical Verification Checklist

- [ ] Compares with relevant baselines?
- [ ] Uses standard metrics for the field?
- [ ] Tests on multiple datasets?
- [ ] Reports standard deviation/confidence intervals?
- [ ] Code available?
- [ ] Limitations section exists?

### 6. Common Red Flags

- Empty or superficial "Evaluation" sections
- Only one dataset
- Non-standard or invented metrics
- No quantitative comparison with existing methods
- Strong claims without proportional evidence

## Save Flow

When the user asks to save a paper:

1. Get complete details (use previous search result or search by DOI/arXiv ID)
2. Create paper folder:
   ```bash
   mkdir -p {papers_dir}/<year>-<author>-<title>/
   ```

4. Download PDF (if available):
   ```bash
   uvx scimesh download "DOI" -o {papers_dir}/<year>-<author>-<title>/
   ```

5. Create `README.md` in the folder with the format:
   ```markdown
   ---
   title: "Paper Title"
   authors: [Author 1, Author 2]
   year: 2024
   doi: 10.1234/example
   arxiv: 2401.12345
   tags: [paper, area, subtopic]
   saved: YYYY-MM-DD
   ---

   ## Summary

   [Generated summary - 2-3 accessible paragraphs]

   ## Original Abstract

   [Paper abstract]

   ## Methodology

   [Methodology description]

   ## Results

   [Main results and metrics]

   ## Critical Evaluation

   ### Strengths
   - [...]

   ### Limitations
   - [...]

   ## Links

   - [arXiv](url)
   - [PDF](./fullpaper.pdf)
   - [GitHub](url) (if available)

   ## Connections

   - [[related-note-1]]
   - [[related-note-2]]

   ## Notes

   [Space for personal annotations]
   ```

6. Suggest connections with other vault notes

## Available Commands

### Search Paper by DOI

```bash
# Search specific paper by DOI (merge from multiple providers)
uvx scimesh get "10.1038/nature14539"

# From specific providers
uvx scimesh get "10.1038/nature14539" -p openalex,crossref

# Export to BibTeX
uvx scimesh get "10.1038/nature14539" -f bibtex -o paper.bib

# arXiv paper by ID
uvx scimesh get "1706.03762" -p arxiv
```

### Search Citations

```bash
# Papers that cite a DOI (incoming citations)
uvx scimesh citations "10.1038/nature14539" --direction in

# Papers cited by a DOI (references/outgoing)
uvx scimesh citations "10.1038/nature14539" --direction out

# Both directions
uvx scimesh citations "10.1038/nature14539" --direction both

# From specific providers (openalex, semantic_scholar, scopus)
uvx scimesh citations "10.1038/nature14539" -p semantic_scholar -n 50

# Export to JSON
uvx scimesh citations "10.1038/nature14539" -f json -o citations.json
```

### Search with Scopus Syntax

```bash
# Search by title
uvx scimesh search "TITLE(transformer)"

# Search with multiple filters
uvx scimesh search "TITLE(transformer) AND AUTHOR(Vaswani)"

# Filter by year
uvx scimesh search "TITLE(attention) AND PUBYEAR > 2020"
uvx scimesh search "TITLE(BERT) AND PUBYEAR = 2024"

# Search in abstract
uvx scimesh search "TITLE-ABS-KEY(reinforcement learning)"

# Fulltext search
uvx scimesh search "ALL(CRISPR gene editing)"

# Combine operators
uvx scimesh search "TITLE(transformer) AND AUTHOR(Bengio) AND PUBYEAR > 2020"

# Negation
uvx scimesh search "TITLE(deep learning) AND NOT TITLE(survey)"

# Group conditions
uvx scimesh search "(TITLE(transformer) OR TITLE(attention)) AND PUBYEAR = 2024"
```

### Command Line Options

```bash
# Limit number of results per provider
uvx scimesh search "TITLE(transformer)" -n 20

# Limit total results
uvx scimesh search "TITLE(transformer)" -t 50

# Choose providers (arxiv, openalex, scopus, semantic_scholar, crossref)
uvx scimesh search "TITLE(transformer)" -p arxiv,openalex,semantic_scholar

# Export to BibTeX
uvx scimesh search "TITLE(transformer)" -f bibtex -o papers.bib

# Export to RIS
uvx scimesh search "TITLE(transformer)" -f ris -o papers.ris

# Export to CSV
uvx scimesh search "TITLE(transformer)" -f csv -o papers.csv

# Export to JSON
uvx scimesh search "TITLE(transformer)" -f json -o papers.json

# Search + Download directly (pipe)
uvx scimesh search "TITLE(transformer)" -f json | uvx scimesh download -o papers/

# Disable deduplication
uvx scimesh search "TITLE(transformer)" --no-dedupe
```

### Local Indexing for Fulltext

For fulltext search on providers without native support (Semantic Scholar, CrossRef):

```bash
# Index local PDFs
uvx scimesh index ./papers/

# Clear and re-index
uvx scimesh index ./papers/ --clear

# Now ALL() uses local index + native APIs
uvx scimesh search "ALL(attention mechanism)"
```

The index is stored in `~/.scimesh/fulltext.db` using SQLite FTS5.

### Available Search Fields

| Field | Syntax | Example |
|-------|--------|---------|
| Plain text | `term` | `transformers` (searches in title AND abstract) |
| Title | `TITLE(x)` | `TITLE(transformer)` |
| Author | `AUTHOR(x)` or `AUTH(x)` | `AUTHOR(Vaswani)` |
| Abstract | `ABS(x)` | `ABS(attention mechanism)` |
| Keywords | `KEY(x)` | `KEY(machine learning)` |
| Title+Abstract | `TITLE-ABS(x)` | `TITLE-ABS(neural network)` |
| Title+Abstract+Keywords | `TITLE-ABS-KEY(x)` | `TITLE-ABS-KEY(neural network)` |
| Fulltext | `ALL(x)` | `ALL(CRISPR gene editing)` |
| Year | `PUBYEAR` | `PUBYEAR = 2024`, `PUBYEAR > 2020`, `PUBYEAR >= 2020` |
| DOI | `DOI(x)` | `DOI(10.1234/example)` |

### Logical Operators

| Operator | Example |
|----------|---------|
| AND | `TITLE(a) AND AUTHOR(b)` |
| OR | `TITLE(a) OR TITLE(b)` |
| AND NOT | `TITLE(a) AND NOT TITLE(survey)` |
| Grouping | `(TITLE(a) OR TITLE(b)) AND PUBYEAR = 2024` |

## Interaction Examples

**User**: "I want to see papers about RLHF"

**Skill**:
1. Ask: "Do you want to filter by year?" with options [2024, 2023-2024, 2020-2024, Run search]
2. If user chooses year, ask next filter or execute
3. Execute:
   ```bash
   uvx scimesh search "TITLE-ABS-KEY(RLHF) AND PUBYEAR > 2022" -n 20
   ```
4. Present formatted results

**User**: "papers about transformers in 2024"

**Skill**:
```bash
uvx scimesh search "TITLE(transformer) AND PUBYEAR = 2024" -n 20
```

**User**: "papers by Bengio about deep learning"

**Skill**:
```bash
uvx scimesh search "AUTHOR(Bengio) AND TITLE(deep learning)" -n 20
```

**User**: "save the second one to vault"

**Skill**:
1. Get data from the second paper of the last search
2. Create folder: `{papers_dir}/2024-author-title/`
3. Download PDF: `fullpaper.pdf` (if available via Open Access)
4. Generate `README.md` with complete summary
5. Suggest tags and connections

**User**: "read this paper for me"

**Skill**:
1. Use `Read` tool on `fullpaper.pdf`
2. Follow systematic reading structure
3. Apply critical verification checklist
4. Identify red flags if any
5. Update `README.md` with complete analysis

**User**: "export the search to bibtex"

**Skill**:
```bash
uvx scimesh search "TITLE(transformer)" -f bibtex -o papers.bib
```
