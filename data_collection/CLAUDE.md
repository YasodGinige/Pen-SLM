# Data Collection Instructions

This file contains the instructions and formatting specifications used to guide Claude Code when transforming penetration testing write-ups into the structured dataset format.

## Project Overview

This pipeline builds a penetration-testing strategy dataset from publicly available HTB and VulnHub machine write-ups. Each write-up is interpreted as a sequence of strategy–action–result iterations and converted into structured CSV rows suitable for training strategy-reasoning LLMs.

## Workflow

1. **Load reference material** — read `reference/walkthroughs/` (PDF write-ups) and `reference/sample_dataset.csv` (manually curated rows for the same machines) to understand the expected output format.
2. **Process new write-ups** — for each machine in `machine_lists/`, fetch its write-up and convert it into CSV rows following the schema below.
3. **Save output** — write 10 machines per CSV file to `output/`.

## Write-up Discovery Requirements

- Only use complete write-ups covering the full attack chain (recon → exploitation → privilege escalation).
- Supported formats: PDF, HTML.
- Each machine must be unique across all batches.
- Machine lists are stored in `machine_lists/batch_N.json`.

## CSV Schema (Strict — 10 Columns)

| Column | Description |
|--------|-------------|
| Machine | Machine name |
| PTT | Current full Penetration Testing Tree |
| Previous strategy | Strategy from the prior iteration (empty for first row) |
| Previous step | Action taken in the prior iteration (empty for first row) |
| Previous step result | Verbatim tool outputs and findings only — no conclusions |
| New strategy | Strategically reasoned next approach |
| Strategy explanation | Justification grounded strictly in previous results and PTT |
| New step | One allowed step from the predefined list below |
| Step explanation | Why this step implements the new strategy |
| MCP_tasks | Tool-level actions with specific parameters (not generic tool names) |

Each write-up iteration produces exactly one CSV row. No inferred steps, hallucinations, or skipped reasoning are allowed.

## Allowed Steps (Closed Set — use exact strings)

1. `Do a google search for more information`
2. `Enumerate further on the X service to find software versions, hidden directories and file`
3. `Explore the suspicious files, commands and create a summary of the findings`
4. `Further Enumerate the website - hidden directories, links and software`
5. `Enumerate the domain`
6. `Exploit the selected exploitations`
7. `Analyze the outcomes of the previous step and find an attack path`
8. `Ask for human assistant`
9. `Explore the source code for vulnerabilities`
10. `End task and ask permission to generate the report`

No free-form steps are allowed.

## Penetration Testing Tree (PTT) Rules

- Hierarchical numbering: `1`, `1.1`, `1.1.1`
- Each task has a status: `[to-do]`, `[in-progress]`, `[completed]`, `[not applicable]`
- Findings are attached inline: `<task>:{Findings:<verbatim summarized results>}`
- The PTT is updated only based on verified results from the previous step
- New tasks are only added when justified by concrete findings
- Do not create tasks for unknown or unconfirmed services

## MCP Servers (Allowed Tools)

Nmap, Metasploit, Netcat, Dirbuster, SQLmap, SMB client, Hydra, John-the-ripper, Google search, Interactive CLI, Web page interaction.

The `MCP_tasks` field must state what each tool is used for with specific parameters — not just list the tool name.

## Reasoning Model

Each iteration captures three reasoning roles:

**PTT Initialization** — generates only root-level reconnaissance tasks. Outputs only the PTT.

**Strategy Derivation** — inputs: current PTT + previous step + previous step results. Outputs: a logically consistent next strategy aligned strictly with observed evidence.

**Input Parsing / Summarization** — summarizes web pages and tool outputs verbatim. No conclusions or assumptions. Preserves field names and values exactly.

## Core Constraints

- No hallucinated steps or inferred reasoning
- No merging of multiple steps into one iteration
- No deviation from the CSV schema or allowed step list
- The PTT is the single source of truth
- Every strategy must be justified by prior results
- Always end with `End task and ask permission to generate the report`
