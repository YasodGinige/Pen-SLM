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

client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

ALLOWED_STEPS = [
    "Do a google search for more information",
    "Enumerate further on the X service to find software versions, hidden directories and file",
    "Explore the suspicious files, commands and create a summary of the findings",
    "Further Enumerate the website - hidden directories, links and software",
    "Enumerate the domain",
    "Exploit the selected exploitations",
    "Analyze the outcomes of the previous step and find an attack path",
    "Ask for human assistant",
    "Explore the source code for vulnerabilities",
    "End task and ask permission to generate the report"
]

CSV_HEADERS = [
    "Machine",
    "PTT",
    "Previous strategy",
    "Previous step",
    "Previous step result",
    "New strategy",
    "Strategy explanation",
    "New step",
    "Step explanation",
    "MCP_tasks"
]


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

    prompt = f"""You are parsing a complete penetration testing writeup for machine: {machine_name}

Your task: Extract EVERY sequential iteration of the penetration test as separate steps.

CURRENT PTT:
{current_ptt}

WRITEUP CONTENT:
{writeup_content}

{reference_block}For EACH iteration, extract:
1. What action was taken (map to one of the allowed steps below)
2. What results were obtained (tool outputs, findings - verbatim)
3. What strategy/reasoning led to this action
4. What MCP tools were used

ALLOWED STEPS (you MUST use these exact strings):
{chr(10).join(f'- "{step}"' for step in ALLOWED_STEPS)}

OUTPUT FORMAT (JSON array):
[
  {{
    "previous_strategy": "",
    "previous_step": "",
    "previous_step_result": "",
    "new_strategy": "Perform initial reconnaissance to identify open ports and services",
    "strategy_explanation": "Starting with network reconnaissance as per standard penetration testing methodology",
    "new_step": "Enumerate further on the X service to find software versions, hidden directories and file",
    "step_explanation": "Using nmap to scan all ports and identify running services",
    "mcp_tasks": "Nmap: Full port scan with service detection (-sV -sC -p-)"
  }},
  ...
]

CRITICAL:
- Extract ALL steps from the writeup sequentially
- Use exact strings from ALLOWED STEPS
- Preserve verbatim tool outputs in previous_step_result
- End with "End task and ask permission to generate the report"
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

        row = {
            "Machine": machine_name,
            "PTT": current_ptt,
            "Previous strategy": step.get('previous_strategy', ''),
            "Previous step": step.get('previous_step', ''),
            "Previous step result": step.get('previous_step_result', ''),
            "New strategy": step.get('new_strategy', ''),
            "Strategy explanation": step.get('strategy_explanation', ''),
            "New step": step.get('new_step', ''),
            "Step explanation": step.get('step_explanation', ''),
            "MCP_tasks": step.get('mcp_tasks', '')
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
