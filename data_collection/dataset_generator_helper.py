#!/usr/bin/env python3
"""
Helper utilities for manual dataset generation.
Provides the shared schema, the approved MCP server list, and CSV append
helpers used by machine-specific generator scripts in examples/.
"""

import csv
import json
from typing import List, Dict, Optional

CSV_HEADERS = [
    "Machine",
    "PTT",
    "Previous strategy",
    "Previous step",
    "Previous step result",
    "New strategy",
    "Strategy explanation",
    "Action",
    "MCP servers",
    "MCP server usage",
    "Results"
]

# The dataset's one real closed-set restriction: "MCP servers" may only name
# tools from this list of 14. ("Previous step" and "Action" are free-form
# narrative/plans -- there is no equivalent closed set of allowed steps.)
APPROVED_SERVERS = [
    "Nmap", "Metasploit", "Netcat", "Dirbuster", "SQLmap", "SMB Client",
    "Hydra", "Burp Suite", "Hashcat", "Google Search", "File System Analysis",
    "ExploitDB", "Interactive CLI", "Web Page Analysis",
]


def create_csv_row(
    machine: str,
    ptt: str,
    previous_strategy: str = "",
    previous_step: str = "",
    previous_step_result: str = "",
    new_strategy: str = "",
    strategy_explanation: str = "",
    action: str = "",
    mcp_servers: Optional[List[str]] = None,
    mcp_server_usage: str = "",
    results: str = ""
) -> Dict[str, str]:
    """Create a properly formatted CSV row.

    `mcp_servers` must only contain names from APPROVED_SERVERS -- that's the
    dataset's one closed-set restriction, so it's validated here.
    """
    mcp_servers = mcp_servers or []
    invalid = [s for s in mcp_servers if s not in APPROVED_SERVERS]
    if invalid:
        print(f"WARNING: {invalid} not in the approved MCP servers!")
        for server in APPROVED_SERVERS:
            print(f"  - {server}")

    return {
        "Machine": machine,
        "PTT": ptt,
        "Previous strategy": previous_strategy,
        "Previous step": previous_step,
        "Previous step result": previous_step_result,
        "New strategy": new_strategy,
        "Strategy explanation": strategy_explanation,
        "Action": action,
        "MCP servers": json.dumps(mcp_servers),
        "MCP server usage": mcp_server_usage,
        "Results": results
    }


def append_rows_to_csv(filename: str, rows: List[Dict[str, str]]):
    """Append rows to existing CSV or create new one"""

    existing_rows = []
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            if reader.fieldnames and reader.fieldnames != CSV_HEADERS:
                raise ValueError(
                    f"{filename} uses a different column schema {reader.fieldnames} than the "
                    f"current schema {CSV_HEADERS}. Move or rename the existing file before "
                    "appending new rows so old- and new-schema rows don't get mixed together."
                )
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


def print_mcp_servers():
    print("\nAPPROVED MCP SERVERS (closed set of 14 -- 'MCP servers' must only use these):")
    print("=" * 60)
    for server in APPROVED_SERVERS:
        print(f"  - {server}")
    print("=" * 60)


if __name__ == "__main__":
    print("Dataset Generator Helper")
    print("=" * 60)
    print_mcp_servers()
    print_ptt_template()
    print("\nTo generate rows for a machine, import create_csv_row and append_rows_to_csv.")
    print("See examples/ for reference machine generators.")
