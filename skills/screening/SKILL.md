---
name: screening
description: |
  Use when screening papers in a systematic literature review with interactive confirmation.

  TRIGGERS: slr screen, screen papers, triagem, include/exclude, triar papers, continuar screening
---

# Screening

Interactive paper screening with LLM-assisted recommendations and user confirmation.

## Overview

Guide users through **assisted screening** of papers. This is an **interactive skill** - NEVER screen papers autonomously.

**Core principle:** Suggest decisions, always confirm with user.

**Prerequisite:** Search must be executed first (scimesh:searching).

## Iron Rules

1. **NO autonomous screening** - Every paper decision requires AskUserQuestion confirmation (except auto-exclude cases)
2. **NO memory-only state** - All decisions written to paper's index.yaml immediately
3. **NO ignoring user override** - If user disagrees with suggestion, their decision wins
4. **ALWAYS use Tasks for tracking** - Create a Task for EACH paper using TaskCreate. This is NOT optional.
5. **MAXIMIZE parallelism** - Read papers + send multiple AskUserQuestion in parallel

## Step 1: Create Tasks for ALL Papers

**BEFORE screening ANY paper, create a Task for EVERY paper in the vault.**

```python
for paper in all_papers:
    TaskCreate(
        subject=f"Screen: {paper_title[:50]}...",
        description=f"Paper: {title}\nAuthors: {authors}\nYear: {year}\nDOI: {doi}",
        activeForm=f"Screening {paper_title[:30]}..."
    )
```

User sees real-time progress:
```
Task 1: [completed] Screen: "Diffusion models for tabular..."
Task 2: [completed] Screen: "ReMasker: Imputing Tabular..."
Task 3: [in_progress] Screen: "EGG-GAE: scalable GNN..."
Task 4: [pending] Screen: "TabCSDI: Conditional Score..."
```

## Step 2: Screen with Aggressive Parallelism

**Maximize throughput:**

1. **Read papers in parallel** - While AskUserQuestion is pending, READ next batch
2. **Multiple AskUserQuestion calls** - Send 5 AskUserQuestion tool calls in SAME message (20 papers per batch)
3. **Update tasks immediately** - Use `TaskUpdate(taskId, status="completed")` as soon as user responds

## Auto-Exclusion Criteria

**Auto-exclude WITHOUT asking** (just run screen command and mark task completed):

| Condition | Action |
|-----------|--------|
| Topic mentioned only in preprocessing | Auto-exclude: "Topic only in preprocessing" |
| Focus clearly on different task | Auto-exclude: "Focus is on X, not target topic" |
| Corrigendum / Erratum | Auto-exclude: "Corrigendum of existing paper" |
| Clear duplicate (same title+authors) | Auto-exclude: "Duplicate of paper X" |
| Wrong data type | Auto-exclude: "Wrong data modality" |

**Still ASK user for:**
- Papers where topic is secondary but substantial
- Reviews (user may want to include)
- Borderline relevance cases

## Batch Screening

**Send MULTIPLE AskUserQuestion tool calls in ONE message (4 questions x 5 calls = 20 papers per batch):**

```python
# First AskUserQuestion (papers 1-4)
{
    "questions": [
        {"question": "Diffusion + tabular - 2022", "header": "TabCSDI", "options": [...]},
        {"question": "Masked AE for imputation - 2023", "header": "ReMasker", "options": [...]},
        {"question": "GNN scalable imputation - 2022", "header": "EGG-GAE", "options": [...]},
        {"question": "Review DL vs traditional - 2023", "header": "Sun2023", "options": [...]}
    ]
}
# Second, Third, Fourth, Fifth AskUserQuestion - IN THE SAME MESSAGE
```

**Key rules:**
- ONE paper per question
- **header = paper name/acronym** (max 12 chars)
- question = your analysis + year
- Recommendation as first option with "(Rec)"
- Send 5 AskUserQuestion calls in parallel (20 papers per batch)

## Recording Decisions

After user decides, **immediately** run the screen command:

```bash
# Include papers
uvx scimesh vault screen {review_path}/ \
  --include paper-slug:"Proposes novel diffusion-based imputation method"

# Exclude papers
uvx scimesh vault screen {review_path}/ \
  --exclude paper-slug:"Focus is on image data, not tabular"

# Mark as maybe (needs full-text review)
uvx scimesh vault screen {review_path}/ \
  --maybe paper-slug:"Unclear methodology, need to read full paper"

# Batch screening (multiple papers at once)
uvx scimesh vault screen {review_path}/ \
  --include paper1:"reason1" paper2:"reason2" \
  --exclude paper3:"reason3" \
  --maybe paper4:"reason4"
```

Then update Task:
```python
TaskUpdate(taskId="X", status="completed")
```

The screen command automatically updates vault stats.

## Resuming a Session

If user has existing review:

```bash
# List unscreened papers
uvx scimesh vault list {review_path}/ --status unscreened

# Show screening stats
uvx scimesh vault stats {review_path}/
```

```python
{
    "question": "Found existing review with 45/120 papers screened. What do you want to do?",
    "header": "Resume?",
    "options": [
        {"label": "Continue screening (Rec)", "description": "Resume from paper 46"},
        {"label": "Start fresh", "description": "Delete and begin new review"},
        {"label": "Export current results", "description": "Generate PRISMA with partial data"}
    ],
    "multiSelect": False
}
```

## Red Flags - STOP

| Thinking this... | Do this instead |
|------------------|-----------------|
| "Obviously relevant, I'll include it" | Still ask user. Apply criteria explicitly. |
| "User said screen all, I'll batch decide" | Each paper needs confirmation |
| "Clearly off-topic" | State which criterion fails, then ask |
| "I'll create tasks as I go" | NO. Create ALL tasks FIRST |
| "Tasks are optional" | NO. Tasks are MANDATORY |

## Next Step

After screening is complete, use **scimesh:extracting** to extract evidence from included papers.
