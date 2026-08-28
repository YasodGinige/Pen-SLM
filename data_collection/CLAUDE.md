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

## CSV Schema (Strict — 11 Columns)

| Column | Description |
|--------|-------------|
| Machine | Machine name |
| PTT | Current full Penetration Testing Tree |
| Previous strategy | Strategy from the prior iteration (empty for first row) |
| Previous step | Free-form narrative describing the step taken in the prior iteration and why (empty for first row) — there is no fixed list of steps to choose from |
| Previous step result | Verbatim tool outputs and findings only — no conclusions |
| New strategy | Strategically reasoned next approach |
| Strategy explanation | Justification grounded strictly in previous results and PTT |
| Action | Concrete, numbered operational plan (typically 4-6 steps) for carrying out the new strategy |
| MCP servers | JSON array of the MCP server(s) used to execute the action — must only use names from the approved list below |
| MCP server usage | One block per server in MCP servers: what it's used for, specific parameters/commands, and expected results |
| Results | Short (2-4 sentence) natural-language summary of the outcome of executing the action |

Each write-up iteration produces exactly one CSV row. No inferred steps, hallucinations, or skipped reasoning are allowed.

`Previous step` and `Action` are free-form prose/plans — they are **not** picked from a predefined list of allowed steps. The only closed-set restriction in this dataset is the approved MCP server list below.

## Penetration Testing Tree (PTT) Rules

- Hierarchical numbering: `1`, `1.1`, `1.1.1`
- Each task has a status: `[to-do]`, `[in-progress]`, `[completed]`, `[not applicable]`
- Findings are attached inline: `<task>:{Findings:<verbatim summarized results>}`
- The PTT is updated only based on verified results from the previous step
- New tasks are only added when justified by concrete findings
- Do not create tasks for unknown or unconfirmed services

## MCP Servers (Approved List — Closed Set of 14)

Nmap, Metasploit, Netcat, Dirbuster, SQLmap, SMB Client, Hydra, Burp Suite, Hashcat, Google Search, File System Analysis, ExploitDB, Interactive CLI, Web Page Analysis.

`MCP servers` must only contain names from this exact list (case-sensitive). `MCP server usage` must state what each selected tool is used for with specific parameters — not just list the tool name — with one section per server, in the same order as `MCP servers`.

## Reasoning Model

Each iteration captures three reasoning roles:

**PTT Initialization** — generates only root-level reconnaissance tasks. Outputs only the PTT.

**Strategy Derivation** — inputs: current PTT + previous step + previous step results. Outputs: a logically consistent next strategy aligned strictly with observed evidence.

**Input Parsing / Summarization** — summarizes web pages and tool outputs verbatim. No conclusions or assumptions. Preserves field names and values exactly.

## Core Constraints

- No hallucinated steps or inferred reasoning
- No merging of multiple steps into one iteration
- No deviation from the CSV schema
- `MCP servers` must only use names from the approved list of 14 — no other tool names, invented or otherwise
- The PTT is the single source of truth
- Every strategy must be justified by prior results
