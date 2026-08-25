#!/usr/bin/env python3
"""
Helper utilities for manual dataset generation.
Provides the shared schema, allowed steps, and CSV append helpers
used by machine-specific generator scripts in examples/.
"""

import csv
import json
from typing import List, Dict

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


def create_csv_row(
    machine: str,
    ptt: str,
    previous_strategy: str = "",
    previous_step: str = "",
    previous_step_result: str = "",
    new_strategy: str = "",
    strategy_explanation: str = "",
    new_step: str = "",
    step_explanation: str = "",
    mcp_tasks: str = ""
) -> Dict[str, str]:
    """Create a properly formatted CSV row"""

    if new_step and new_step not in ALLOWED_STEPS:
        print(f"WARNING: '{new_step}' is not in allowed steps!")
        for step in ALLOWED_STEPS:
            print(f"  - {step}")

    return {
        "Machine": machine,
        "PTT": ptt,
        "Previous strategy": previous_strategy,
        "Previous step": previous_step,
        "Previous step result": previous_step_result,
        "New strategy": new_strategy,
        "Strategy explanation": strategy_explanation,
        "New step": new_step,
        "Step explanation": step_explanation,
        "MCP_tasks": mcp_tasks
    }


def append_rows_to_csv(filename: str, rows: List[Dict[str, str]]):
    """Append rows to existing CSV or create new one"""

    existing_rows = []
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            existing_rows = list(reader)
    except FileNotFoundError:
        pass

    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        writer.writeheader()
        writer.writerows(existing_rows + rows)

    print(f"Added {len(rows)} rows to {filename} (total: {len(existing_rows) + len(rows)})")


def print_ptt_template():
    print("""
PTT Template:
-------------
1. Network Reconnaissance [to-do/in-progress/completed/not applicable]
1.1. Perform initial port scan [status]: {Findings: <results>}
1.2. Identify running services [status]
2. Service Enumeration [status]
2.1. Enumerate HTTP/HTTPS services [status]
2.2. Enumerate SMB services [status]
3. Vulnerability Analysis [status]
4. Initial Access Exploitation [status]
5. Post-Exploitation Enumeration [status]
6. Privilege Escalation [status]
7. Report Generation [status]

Notes:
- Hierarchical numbering: 1, 1.1, 1.1.1
- Statuses: to-do, in-progress, completed, not applicable
- Findings inline: {Findings: <verbatim tool output>}
- Only add subtasks justified by findings
""")


def print_allowed_steps():
    print("\nALLOWED STEPS (use exact strings):")
    print("=" * 60)
    for i, step in enumerate(ALLOWED_STEPS, 1):
        print(f"{i}. {step}")
    print("=" * 60)


def print_mcp_servers():
    print("\nMCP SERVERS:")
    print("=" * 60)
    for server in ["Nmap", "Metasploit", "Netcat", "Dirbuster", "SQLmap",
                   "SMB client", "Hydra", "John-the-ripper", "Google search",
                   "Interactive CLI", "Web page interaction"]:
        print(f"  - {server}")
    print("=" * 60)


if __name__ == "__main__":
    print("Dataset Generator Helper")
    print("=" * 60)
    print_allowed_steps()
    print_mcp_servers()
    print_ptt_template()
    print("\nTo generate rows for a machine, import create_csv_row and append_rows_to_csv.")
    print("See examples/ for reference machine generators.")
