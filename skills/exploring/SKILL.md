---
name: exploring
description: |
  Autonomous scientific literature exploration. Given a theme, explores the literature
  using subagents until saturation or paper limit, then generates a rich synthesis report.
triggers:
  - exploring
  - explore literature
  - explorar literatura
  - literature exploration
  - autonomous exploration
---

# Exploring Skill

Autonomous scientific literature exploration. You are the orchestrator.

## Trigger

User says: `exploring: {theme}`

Example: `exploring: multi-agent systems for scientific discovery`

## Your Role

You are a fully autonomous orchestrator. You:
1. Create a workspace
2. Execute search/condense/tag cycles via subagents
3. Generate rich synthesis via writer subagents
4. Deliver final report

**CRITICAL CONSTRAINTS:**
- You are 100% AUTONOMOUS - NEVER ask user for confirmation
- ONLY use `scimesh` CLI commands via Bash
- Use Read to check workspace state (log.yaml, papers.yaml, synthesis/*.md)
- Use Write/Edit ONLY for log.yaml updates
- Delegate paper-level operations (reading PDFs, updating paper index.yaml) to subagents
- NO git operations until explicitly told
- Dispatch subagents for all file operations

## Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| limit | 500 | Maximum papers to collect |
| providers | openalex,semantic_scholar | Search providers |
| saturation_threshold | 3 | Rounds with <5% new papers to stop |

User can override: `exploring: {theme} --limit 100 --providers openalex`

## Execution Flow

### Phase 1: Initialize

```bash
uvx scimesh workspace init {workspace_path} --type exploration --question "{theme}"
```

Use workspace path: `explorations/{slugified-theme}`

### Phase 2: Exploration Loop

```
WHILE total_papers < limit AND saturation_count < saturation_threshold:

    1. READ STATE
       - Read log.yaml for previous queries, subtopics, suggested_queries
       - Read papers.yaml for total count
       - Use Glob to find papers without condensed.md

    2. DECIDE NEXT QUERY
       - If first round: use theme directly
       - Else: pick from suggested_queries or explore new subtopic
       - Avoid repeating similar queries

    3. EXECUTE SEARCH
       ```bash
       uvx scimesh workspace search {path} "{decided_query}" -p {providers} -n 50
       ```
       Then read `{path}/papers.yaml` to identify new papers.

    4. DISPATCH CONDENSE + TAG SUBAGENTS
       For each new paper (no condensed.md file):

         Step A - Condense (parallel across papers):
         Agent(subagent_type="scimesh:paper-briefer", prompt="""
           Extract from: {workspace_path}/{paper_path}/fulltext.pdf
           Write to: {workspace_path}/{paper_path}/condensed.md
         """)

         Step B - Tag (after condenser completes for each paper):
         Agent(subagent_type="scimesh:paper-tagger", prompt="""
           Condensed: {workspace_path}/{paper_path}/condensed.md
           Protocol: {workspace_path}/index.yaml
           Output: {workspace_path}/{paper_path}/condensed.md (prepend frontmatter)
         """)

       Condensers run in parallel. Each tagger waits for its condenser.

    5. UPDATE LOG
       After condense+tag completes, read frontmatter from condensed.md files.
       Update log.yaml entry with:
       - notes: observations from this round
       - subtopics: newly discovered subtopics (from method_category and tags)
       - suggested_queries: promising directions
       - saturation: true if <5% new papers

    6. CHECK STOPPING CRITERIA
       - total_papers >= limit? → EXIT LOOP
       - saturation_count >= 3? → EXIT LOOP
```

### Phase 3: Synthesis

```
1. IDENTIFY SUBTOPICS
   Read condensed.md frontmatter for each paper (method_category, tags, relevance.score)
   Group papers by method_category or dominant tag clusters
   Select top 3-5 groupings by paper count as subtopics

2. DISPATCH SCIENTIFIC WRITERS (3-5 in parallel)

   For each major subtopic:
     Agent(subagent_type="scimesh:scientific-writer", prompt="""
       workspace_path: {path}
       task: Synthesize the subtopic '{subtopic}' with depth and critical analysis
       papers: [{list of paper paths in this subtopic}]
       context:
         theme: {theme}
         all_subtopics: {list}
       output_file: synthesis/{subtopic-slug}.md
     """)

   Cross-analysis:
     Agent(subagent_type="scimesh:scientific-writer", prompt="""
       workspace_path: {path}
       task: Analyze patterns, connections, and contradictions across all subtopics
       papers: [{all papers with relevance.score >= 4}]
       context:
         theme: {theme}
         subtopics: {list}
       output_file: synthesis/cross-analysis.md
     """)

   Gaps analysis:
     Agent(subagent_type="scimesh:scientific-writer", prompt="""
       workspace_path: {path}
       task: Identify research gaps, open questions, and future directions
       papers: [{all papers}]
       context:
         theme: {theme}
         subtopics: {list}
       output_file: synthesis/gaps.md
     """)
```

### Phase 4: Final Report

```
1. FINISH WORKSPACE
   uvx scimesh workspace finish {workspace_path}

2. COMPILE REPORT
   Read all synthesis/*.md files
   Compile into exploration-report.md:
```

**Report structure:**

```markdown
# {Theme}: A Literature Exploration

## Summary

{Write 2-3 paragraphs integrating all synthesis sections.
Provide the "big picture" of where the field stands.}

## {Subtopic 1}

{Content from synthesis/{subtopic-1}.md}

## {Subtopic 2}

{Content from synthesis/{subtopic-2}.md}

...

## Cross-Cutting Analysis

{Content from synthesis/cross-analysis.md}

## Gaps and Opportunities

{Content from synthesis/gaps.md}

## Key Papers

{List papers with relevance.score >= 4, with one-line justification from key_contribution}

---

## Exploration Report

**Theme:** {theme}
**Period:** {started_at} → {finished_at}
**Papers collected:** {total}
**Stop reason:** {saturation reached | limit reached}

### Search Log

| Round | Query | Found | New | Saturation |
|-------|-------|-------|-----|------------|
| 1 | ... | ... | ... | false |
| 2 | ... | ... | ... | false |
...

### Subtopics Discovered

- {subtopic 1} ({n} papers)
- {subtopic 2} ({n} papers)
...

### Statistics

- Total rounds: {n}
- Providers: {list}
- Duplication rate: {%}
- High relevance papers (score >= 4): {n}
```

## Concurrency Strategy

**Avoid race conditions:**
- Search: ONE at a time (sequential)
- Condense: PARALLEL (each paper writes its own condensed.md)
- Tag: SEQUENTIAL per paper (waits for its condenser), but multiple condense→tag chains run in parallel
- Writers: PARALLEL (each writes different file)
- Log updates: Only orchestrator updates log.yaml (after subagents complete)

## Query Strategy

**Round 1:** Use theme directly
**Round 2+:** Choose from:
1. `suggested_queries` from previous rounds
2. Expand discovered subtopics
3. Combine subtopics in new ways
4. Search for specific methods mentioned
5. Explore gaps identified

**Avoid:**
- Repeating exact queries
- Queries too similar to previous
- Overly broad queries (>100 results usually means too broad)

## Example Session

```
User: exploring: quantum machine learning for drug discovery

Orchestrator:
[Creates workspace at explorations/quantum-ml-drug-discovery]

Round 1:
- Query: "quantum machine learning drug discovery"
- Found: 45 papers, 45 new
- Subtopics: variational quantum circuits, molecular simulation, QSPR
- Suggested: "variational quantum eigensolver molecules", "quantum kernel drug"

Round 2:
- Query: "variational quantum eigensolver molecular simulation"
- Found: 38 papers, 31 new
- Subtopics: VQE optimization, noise-resilient circuits
- Saturation: false

Round 3:
- Query: "quantum kernel methods QSPR"
- Found: 29 papers, 22 new
...

[After 8 rounds, saturation detected]

Synthesis:
- Dispatching writer for "variational quantum circuits"
- Dispatching writer for "molecular simulation"
- Dispatching writer for "quantum kernels"
- Dispatching writer for cross-analysis
- Dispatching writer for gaps

[Compiling final report]

COMPLETE:
- Workspace: explorations/quantum-ml-drug-discovery
- Report: explorations/quantum-ml-drug-discovery/exploration-report.md
- Papers: 247
- Subtopics: 5
- Stop reason: saturation reached
```

## Error Handling & Recovery

### Resuming an Interrupted Exploration

If the workspace already exists when triggered:

1. **Read current state**: Check `log.yaml` for last round, `papers.yaml` for total count
2. **Detect uncondensed papers**: Papers without `condensed.md` file need processing
3. **Resume from last round**: Continue the exploration loop from where it stopped
4. **Do NOT re-initialize**: Skip `workspace init` if workspace already has papers

### Subagent Failures

- **Search fails:** Log the error in notes, try a different query formulation next round
- **Condense/tag fails:** Skip paper, log the error in notes, continue with others
- **Writer fails:** Retry once with same prompt. If still fails, write a placeholder noting the missing section
- **All failures logged** in the final exploration-report.md appendix

### Rate Limiting

- If a provider returns 429 (rate limited), wait 30 seconds before retrying
- Alternate between providers across rounds to distribute load
- If all providers are rate-limited, pause for 60 seconds

### Deduplication

Before dispatching condense subagents, verify the paper does NOT already have a `condensed.md` file. Use Glob to check:
```python
Glob(pattern="{workspace_path}/papers/**/condensed.md")
```
Papers found in multiple search rounds should only be condensed once.
