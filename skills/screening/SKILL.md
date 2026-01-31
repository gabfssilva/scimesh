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
| Wrong data type/modality | Auto-exclude: "Wrong data modality" |
| Retracted paper | Auto-exclude: "Paper has been retracted" |
| Editorial / Commentary / Letter to editor | Auto-exclude: "Not primary research" |
| Conference abstract only (no full paper) | Auto-exclude: "Abstract only, insufficient data" |
| Poster / Extended abstract | Auto-exclude: "Poster/extended abstract only" |
| Preprint with published version already included | Auto-exclude: "Preprint superseded by published version" |
| Paper not accessible (paywall, no PDF) | Auto-exclude: "Full text not accessible" |
| Book chapter (unless protocol allows) | Auto-exclude: "Book chapter excluded by protocol" |
| Thesis/Dissertation (unless protocol allows) | Auto-exclude: "Thesis excluded by protocol" |
| Non-peer-reviewed source (blog, white paper) | Auto-exclude: "Non-peer-reviewed source" |

**Still ASK user for:**
- Papers where topic is secondary but substantial
- Reviews / Systematic reviews / Meta-analyses (user may want to include)
- Preprints (if protocol doesn't specify)
- Borderline relevance cases
- Unclear methodology quality

## Batch Screening

**Send MULTIPLE AskUserQuestion tool calls in ONE message (4 questions x 5 calls = 20 papers per batch):**

```python
# First AskUserQuestion (papers 1-4)
{
    "questions": [
        {
            # Example: INCLUDE recommended - Include is FIRST
            "question": "Attention Is All You Need\n\nThe dominant sequence transduction models are based on complex recurrent or convolutional neural networks that include an encoder and a decoder. The best performing models also connect the encoder and decoder through an attention mechanism. We propose a new simple network architecture, the Transformer, based solely on attention mechanisms, dispensing with recurrence and convolutions entirely. Experiments on two machine translation tasks show these models to be superior in quality while being more parallelizable and requiring significantly less time to train. We achieve 28.4 BLEU on the WMT 2014 English-to-German translation task, improving over the existing best results by over 2 BLEU.\n\nTags: transformer, attention-mechanism, sequence-to-sequence, machine-translation, neural-network, encoder-decoder, parallelization, NLP",
            "header": "2017, Vaswani",
            "options": [
                {"label": "Include (Rec)", "description": "The paper meets all inclusion criteria for this systematic review. It presents a relevant contribution to the research question, employs appropriate methodology, and provides empirically validated results. Will be included in the data extraction and synthesis phases."},
                {"label": "Exclude", "description": "The paper does not meet inclusion criteria or violates an exclusion criterion. Possible reasons: scope outside research question, inadequate methodology, lack of empirical validation, duplicate entry, or ineligible publication type."},
                {"label": "Maybe", "description": "Uncertainty about the paper's eligibility for this review. Requires discussion with a second reviewer, full-text reading for final decision, or clarification on specific criteria."}
            ],
            "multiSelect": False
        },
        {
            # Example: EXCLUDE recommended - Exclude is FIRST
            "question": "Deep Residual Learning for Image Recognition\n\nDeeper neural networks are more difficult to train. We present a residual learning framework to ease the training of networks that are substantially deeper than those used previously. We explicitly reformulate the layers as learning residual functions with reference to the layer inputs, instead of learning unreferenced functions. We provide comprehensive empirical evidence showing that these residual networks are easier to optimize, and can gain accuracy from considerably increased depth. On the ImageNet dataset we evaluate residual nets with a depth of up to 152 layers, 8x deeper than VGG nets but still having lower complexity.\n\nTags: ResNet, residual-learning, deep-learning, image-recognition, CNN, skip-connections, ImageNet, computer-vision, batch-normalization",
            "header": "2015, He et al.",
            "options": [
                {"label": "Exclude (Rec)", "description": "The paper does not meet inclusion criteria or violates an exclusion criterion. Possible reasons: scope outside research question, inadequate methodology, lack of empirical validation, duplicate entry, or ineligible publication type."},
                {"label": "Include", "description": "The paper meets all inclusion criteria for this systematic review. It presents a relevant contribution to the research question, employs appropriate methodology, and provides empirically validated results. Will be included in the data extraction and synthesis phases."},
                {"label": "Maybe", "description": "Uncertainty about the paper's eligibility for this review. Requires discussion with a second reviewer, full-text reading for final decision, or clarification on specific criteria."}
            ],
            "multiSelect": False
        },
        # ... more papers
    ]
}
# Second, Third, Fourth, Fifth AskUserQuestion - IN THE SAME MESSAGE
```

**CRITICAL - Question format:**
- **header = "Year, Author"** (e.g., "2017, Vaswani", "2023, Chen et al.")
- **question = FULL Title + COMPLETE Abstract + Tags** (plain text, NO markdown formatting)
- The abstract must be COMPLETE - do NOT truncate or summarize it
- Add paper tags at the end: "Tags: tag1, tag2, tag3"
- Options are ALWAYS: Include, Exclude, Maybe with VERBOSE descriptions explaining each choice

**Key rules:**
- ONE paper per question
- **RECOMMENDED OPTION MUST BE FIRST** - Reorder options so your recommendation is always the first option with "(Rec)" suffix
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
