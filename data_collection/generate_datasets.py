#!/usr/bin/env python3
"""
Dataset Generation Script for Penetration Testing Writeups
Processes HTB/VulnHub writeups into structured CSV datasets following PTT model.

Usage:
    python generate_datasets.py [--batch-file machine_lists/batch_1.json] [--batch-num 1]

Requires ANTHROPIC_API_KEY environment variable.
"""

import json
import csv
import re
import sys
import argparse
import requests
import pdfplumber
import pandas as pd
from bs4 import BeautifulSoup
from typing import List, Dict, Any
import time
from anthropic import Anthropic
import os

from dataset_generator_helper import CSV_HEADERS, APPROVED_SERVERS

client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))


def load_paired_reference_examples(n_machines: int = 2) -> str:
    """
    For each reference machine, pair its walkthrough PDF with the manually curated
    dataset rows, producing a (writeup -> correct rows) few-shot example block.
    Shows Claude exactly what format and depth is expected for new machines.
    """
    ref_csv = "reference/sample_dataset.csv"
    walkthroughs_dir = "reference/walkthroughs"

    if not os.path.exists(ref_csv):
        return ""

    df = pd.read_csv(ref_csv)
    if list(df.columns) != CSV_HEADERS:
        print(
            f"Warning: {ref_csv} columns {list(df.columns)} don't match the current "
            f"schema {CSV_HEADERS} -- skipping stale few-shot reference examples "
            "(regenerate reference/sample_dataset.csv against the current schema)."
        )
        return ""

    machines = df["Machine"].unique()[:n_machines]
    blocks = []

    for machine in machines:
        # Match PDF file case-insensitively
        pdf_path = None
        for fname in os.listdir(walkthroughs_dir):
            if fname.lower().rstrip(".pdf") == machine.lower():
                pdf_path = os.path.join(walkthroughs_dir, fname)
                break

        if pdf_path is None or not os.path.exists(pdf_path):
            continue

        # Extract PDF text (first ~4000 chars covers recon + initial exploitation)
        try:
            with pdfplumber.open(pdf_path) as pdf:
                text = "\n".join(p.extract_text() or "" for p in pdf.pages)[:4000]
        except Exception as e:
            print(f"Warning: could not read PDF for {machine}: {e}")
            continue

        # Get the first 3 dataset rows for this machine
        rows = df[df["Machine"] == machine].head(3).to_dict(orient="records")
        rows_json = json.dumps(rows, indent=2)

        blocks.append(
            f"=== REFERENCE EXAMPLE: {machine} ===\n"
            f"WALKTHROUGH (excerpt):\n{text}\n\n"
            f"CORRECT DATASET ROWS (first 3 of the sequence):\n{rows_json}"
        )

    return "\n\n".join(blocks)


def fetch_writeup(url: str) -> str:
    """Fetch writeup content from URL"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return ""


def parse_writeup_with_claude(html_content: str, machine_name: str) -> str:
    """Parse writeup HTML and extract main text content"""
    soup = BeautifulSoup(html_content, 'html.parser')
    for tag in soup(['script', 'style', 'nav', 'header', 'footer']):
        tag.decompose()
    main_content = soup.get_text(separator='\n', strip=True)
    if len(main_content) > 100000:
        main_content = main_content[:100000]
    return main_content


def initialize_ptt_with_claude(machine_name: str, writeup_content: str) -> str:
    """Initialize PTT using Claude based on initial reconnaissance"""

    prompt = f"""You are analyzing a penetration testing writeup for the machine: {machine_name}

Based on the following writeup content, generate ONLY the initial root-level Penetration Testing Tree (PTT).

RULES:
1. Create only root reconnaissance tasks (numbered 1, 1.1, 1.2, etc.)
2. Each task has status: to-do, completed, or not applicable
3. Do NOT add findings yet - this is initialization only
4. Use hierarchical numbering
5. Common root tasks include:
   - Network reconnaissance
   - Port scanning
   - Service enumeration
   - Web enumeration (if applicable)
   - Domain enumeration (if applicable)

OUTPUT FORMAT (example):
1. Network Reconnaissance [to-do]
1.1. Perform initial port scan [to-do]
1.2. Identify running services [to-do]
2. Service Enumeration [to-do]
2.1. Enumerate HTTP/HTTPS services [to-do]
2.2. Enumerate SMB services [to-do]

Now generate the initial PTT for {machine_name}.

Writeup content (first portion):
{writeup_content[:3000]}
"""

    try:
        message = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}]
        )
        return message.content[0].text.strip()
    except Exception as e:
        print(f"Error initializing PTT: {e}")
        return """1. Network Reconnaissance [to-do]
1.1. Perform initial port scan [to-do]
1.2. Identify running services [to-do]
2. Service Enumeration [to-do]"""


def extract_steps_with_claude(machine_name: str, writeup_content: str, current_ptt: str) -> List[Dict[str, str]]:
    """Extract sequential penetration testing steps using Claude"""

    reference_examples = load_paired_reference_examples(n_machines=2)
    reference_block = ""
    if reference_examples:
        reference_block = f"""REFERENCE EXAMPLES — each shows a real walkthrough excerpt paired with its correct dataset rows.
Use these to infer the exact format, depth, field content, and PTT style expected:

{reference_examples}

---
"""

    approved_servers_block = "\n".join(f'- "{s}"' for s in APPROVED_SERVERS)

    prompt = f"""You are parsing a complete penetration testing writeup for machine: {machine_name}

Your task: Extract EVERY sequential iteration of the penetration test as separate steps.

CURRENT PTT:
{current_ptt}

WRITEUP CONTENT:
{writeup_content}

{reference_block}For EACH iteration, extract:
1. previous_step: a free-form narrative description of the step taken in the PRIOR iteration and the reasoning behind it (there is no fixed list of steps -- write natural prose, not a canned label)
2. previous_step_result: the results obtained from that step (tool outputs, findings - verbatim where possible)
3. new_strategy / strategy_explanation: the next high-level strategy and reasoning grounded in the PTT and previous_step_result
4. action: a concrete, numbered operational plan (4-6 steps) for carrying out new_strategy
5. mcp_servers: the MCP server(s) used to execute the action
6. mcp_server_usage: for each server in mcp_servers, a short block describing what it's used for, how (specific parameters/commands), and what to expect
7. results: a short (2-4 sentence) natural-language summary of the outcome of executing the action

APPROVED MCP SERVERS -- this is a closed set. mcp_servers must ONLY use these exact names, nothing else:
{approved_servers_block}

OUTPUT FORMAT (JSON array):
[
  {{
    "previous_strategy": "",
    "previous_step": "",
    "previous_step_result": "",
    "new_strategy": "Perform initial reconnaissance to identify open ports and running services",
    "strategy_explanation": "Beginning penetration test with standard network reconnaissance. Need to discover what services are exposed on the target system to identify potential attack vectors.",
    "action": "1. Execute a comprehensive Nmap scan against the target machine to identify all open TCP and UDP ports.\\n2. Perform service version detection and OS fingerprinting on all discovered open ports.\\n3. Run Nmap NSE default scripts against identified services to detect misconfigurations and common vulnerabilities.\\n4. Document the attack surface based on identified services.",
    "mcp_servers": ["Nmap"],
    "mcp_server_usage": "Nmap:\\n* Perform a full TCP SYN scan with service version detection, OS fingerprinting, and default NSE scripts against the target IP.\\n* Use flags: nmap -sS -sV -sC -O -p- -T4 <target_IP>.\\n* Expect: list of open TCP ports, identified service names/versions, OS detection results, and NSE script findings.",
    "results": "A comprehensive Nmap scan with version detection and NSE was run and revealed the open services. Findings inform the next enumeration step."
  }},
  ...
]

CRITICAL:
- Extract ALL steps from the writeup sequentially
- previous_step and action are free-form prose/plans -- do not force them into canned phrases
- mcp_servers must only contain names from the APPROVED MCP SERVERS list above
- mcp_server_usage must have exactly one section per server listed in mcp_servers, using the same server names, in the same order
- Preserve verbatim tool outputs in previous_step_result
- No hallucinations or invented steps

Generate the JSON array now:
"""

    try:
        message = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=16000,
            messages=[{"role": "user", "content": prompt}]
        )

        response_text = message.content[0].text.strip()
        json_match = re.search(r'\[.*\]', response_text, re.DOTALL)
        if json_match:
            steps = json.loads(json_match.group())
            return steps
        else:
            print(f"No JSON found in response for {machine_name}")
            return []

    except Exception as e:
        print(f"Error extracting steps for {machine_name}: {e}")
        return []


def update_ptt_with_claude(current_ptt: str, step_result: str, new_strategy: str) -> str:
    """Update PTT based on previous step results using Claude"""

    prompt = f"""You are maintaining a Penetration Testing Tree (PTT).

CURRENT PTT:
{current_ptt}

PREVIOUS STEP RESULT:
{step_result}

NEW STRATEGY:
{new_strategy}

Your task: Update the PTT based on the previous step result.

RULES:
1. Mark completed tasks as [completed]
2. Add findings inline: <task>:{{Findings:<verbatim results>}}
3. Add new subtasks only if justified by concrete findings
4. Use hierarchical numbering (1, 1.1, 1.1.1, etc.)
5. Do NOT create tasks for unknown services
6. Update task status based on actual results

Output the UPDATED PTT:
"""

    try:
        message = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=3000,
            messages=[{"role": "user", "content": prompt}]
        )
        return message.content[0].text.strip()
    except Exception as e:
        print(f"Error updating PTT: {e}")
        return current_ptt


def process_machine(machine_data: Dict[str, Any]) -> List[Dict[str, str]]:
    """Process a single machine writeup and generate CSV rows"""

    machine_name = machine_data['machine_name']
    writeup_url = machine_data['writeup_urls'][0]

    print(f"\nProcessing: {machine_name}")
    print(f"URL: {writeup_url}")

    html_content = fetch_writeup(writeup_url)
    if not html_content:
        print(f"Failed to fetch writeup for {machine_name}")
        return []

    writeup_content = parse_writeup_with_claude(html_content, machine_name)

    print(f"Initializing PTT for {machine_name}...")
    current_ptt = initialize_ptt_with_claude(machine_name, writeup_content)

    print(f"Extracting steps for {machine_name}...")
    time.sleep(2)
    steps = extract_steps_with_claude(machine_name, writeup_content, current_ptt)

    if not steps:
        print(f"No steps extracted for {machine_name}")
        return []

    csv_rows = []

    for i, step in enumerate(steps):
        if i > 0:
            previous_result = steps[i-1].get('previous_step_result', '')
            if previous_result:
                print(f"Updating PTT for step {i+1}...")
                time.sleep(1)
                current_ptt = update_ptt_with_claude(
                    current_ptt,
                    previous_result,
                    step.get('new_strategy', '')
                )

        raw_servers = step.get('mcp_servers', []) or []
        if isinstance(raw_servers, str):
            try:
                raw_servers = json.loads(raw_servers)
            except json.JSONDecodeError:
                raw_servers = [s.strip() for s in raw_servers.split(",") if s.strip()]
        mcp_servers = [s for s in raw_servers if s in APPROVED_SERVERS]
        if len(mcp_servers) != len(raw_servers):
            dropped = [s for s in raw_servers if s not in APPROVED_SERVERS]
            print(f"Warning: dropping non-approved MCP server(s) {dropped} for {machine_name} step {i+1}")

        row = {
            "Machine": machine_name,
            "PTT": current_ptt,
            "Previous strategy": step.get('previous_strategy', ''),
            "Previous step": step.get('previous_step', ''),
            "Previous step result": step.get('previous_step_result', ''),
            "New strategy": step.get('new_strategy', ''),
            "Strategy explanation": step.get('strategy_explanation', ''),
            "Action": step.get('action', ''),
            "MCP servers": json.dumps(mcp_servers),
            "MCP server usage": step.get('mcp_server_usage', ''),
            "Results": step.get('results', '')
        }
        csv_rows.append(row)

    print(f"Generated {len(csv_rows)} rows for {machine_name}")
    return csv_rows


def save_csv_batch(rows: List[Dict[str, str]], batch_num: int, start_idx: int, end_idx: int):
    """Save CSV file for a batch of machines"""
    filename = f"output/pentest_dataset_batch{batch_num}_machines_{start_idx+1}-{end_idx}.csv"
    os.makedirs("output", exist_ok=True)

    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n{'='*60}")
    print(f"Saved: {filename}")
    print(f"Total rows: {len(rows)}")
    print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(description="Generate pentest dataset from writeups")
    parser.add_argument("--batch-file", default="machine_lists/batch_1.json",
                        help="JSON file listing machines to process")
    parser.add_argument("--batch-num", type=int, default=1,
                        help="Batch number used in output filename")
    args = parser.parse_args()

    with open(args.batch_file, 'r') as f:
        machines = json.load(f)

    print(f"Loaded {len(machines)} machines from {args.batch_file}")

    batch_size = 10
    num_batches = (len(machines) + batch_size - 1) // batch_size

    for batch_idx in range(num_batches):
        start_idx = batch_idx * batch_size
        end_idx = min(start_idx + batch_size, len(machines))

        print(f"\n{'='*60}")
        print(f"PROCESSING BATCH {args.batch_num + batch_idx}: Machines {start_idx + 1}-{end_idx}")
        print(f"{'='*60}")

        batch_machines = machines[start_idx:end_idx]
        all_rows = []

        for machine_data in batch_machines:
            try:
                rows = process_machine(machine_data)
                all_rows.extend(rows)
                time.sleep(3)
            except Exception as e:
                print(f"Error processing {machine_data['machine_name']}: {e}")
                continue

        if all_rows:
            save_csv_batch(all_rows, args.batch_num + batch_idx, start_idx, end_idx)
        else:
            print(f"No rows generated for batch {args.batch_num + batch_idx}")

    print("\n" + "="*60)
    print("DATASET GENERATION COMPLETE")
    print("="*60)


if __name__ == "__main__":
    main()
