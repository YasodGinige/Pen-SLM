#!/usr/bin/env python3
"""
Generate complete CSV rows for Soulmate machine
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dataset_generator_helper import create_csv_row, append_rows_to_csv

def generate_soulmate_rows():
    """Generate all CSV rows for Soulmate machine"""
    rows = []
    machine = "Soulmate"

    # Row 1: Initial reconnaissance
    ptt_1 = """1. Network Reconnaissance [to-do]
1.1. Perform initial port scan [to-do]
1.2. Identify running services [to-do]
2. Service Enumeration [to-do]"""

    row_1 = create_csv_row(
        machine=machine,
        ptt=ptt_1,
        previous_strategy="",
        previous_step="",
        previous_step_result="",
        new_strategy="Perform initial reconnaissance to identify open ports and running services",
        strategy_explanation="Beginning penetration test with standard network reconnaissance. Need to discover what services are exposed on the target system to identify potential attack vectors.",
        new_step="Enumerate further on the X service to find software versions, hidden directories and file",
        step_explanation="Execute comprehensive nmap scan to identify all open ports, running services, and version information. This establishes the initial attack surface.",
        mcp_tasks="Nmap: Full TCP port scan with service version detection (-sV -sC -p- -A)"
    )
    rows.append(row_1)

    # Row 2: Port scan results
    ptt_2 = """1. Network Reconnaissance [completed]
1.1. Perform initial port scan [completed]: {Findings: TCP port 22 (SSH) - OpenSSH 8.9p1 Ubuntu, TCP port 80 (HTTP) - nginx 1.18.0 with redirect to soulmate.htb. TTL of 63 indicates Linux one hop away.}
1.2. Identify running services [completed]: {Findings: SSH and HTTP services identified}
2. Service Enumeration [to-do]
2.1. Enumerate HTTP service [to-do]
2.2. Perform subdomain enumeration [to-do]"""

    row_2 = create_csv_row(
        machine=machine,
        ptt=ptt_2,
        previous_strategy="Perform initial reconnaissance to identify open ports and running services",
        previous_step="Enumerate further on the X service to find software versions, hidden directories and file",
        previous_step_result="TCP port 22 (SSH) - OpenSSH 8.9p1 Ubuntu, TCP port 80 (HTTP) - nginx 1.18.0 with redirect to soulmate.htb. TTL of 63 indicates Linux one hop away.",
        new_strategy="Enumerate the web application and discover subdomains",
        strategy_explanation="HTTP service redirects to soulmate.htb hostname, suggesting virtual host routing. Need to enumerate the main website and discover any additional subdomains that may expose different services or attack vectors.",
        new_step="Further Enumerate the website - hidden directories, links and software",
        step_explanation="Enumerate the soulmate.htb website to identify web application technologies, hidden directories, and perform subdomain fuzzing to discover additional virtual hosts.",
        mcp_tasks="Dirbuster: Directory and file enumeration on soulmate.htb; Interactive CLI: Subdomain fuzzing with ffuf/gobuster; Web page interaction: Manual inspection of website functionality"
    )
    rows.append(row_2)

    # Row 3: Web enumeration results
    ptt_3 = """1. Network Reconnaissance [completed]
1.1. Perform initial port scan [completed]: {Findings: TCP port 22 (SSH) - OpenSSH 8.9p1 Ubuntu, TCP port 80 (HTTP) - nginx 1.18.0 with redirect to soulmate.htb. TTL of 63 indicates Linux one hop away.}
1.2. Identify running services [completed]: {Findings: SSH and HTTP services identified}
2. Service Enumeration [completed]
2.1. Enumerate HTTP service [completed]: {Findings: PHP-based dating website at soulmate.htb with registration/login functionality. SQLite database (soulmate.db) discovered containing bcrypt-hashed admin credentials. File upload functionality exists but has restrictions.}
2.2. Perform subdomain enumeration [completed]: {Findings: Subdomain ftp.soulmate.htb discovered, responds with 302 redirect}
3. Vulnerability Analysis [to-do]
3.1. Analyze ftp subdomain [to-do]"""

    row_3 = create_csv_row(
        machine=machine,
        ptt=ptt_3,
        previous_strategy="Enumerate the web application and discover subdomains",
        previous_step="Further Enumerate the website - hidden directories, links and software",
        previous_step_result="PHP-based dating website at soulmate.htb with registration/login functionality. SQLite database (soulmate.db) discovered containing bcrypt-hashed admin credentials. File upload functionality exists but has restrictions. Subdomain ftp.soulmate.htb discovered, responds with 302 redirect.",
        new_strategy="Investigate the ftp.soulmate.htb subdomain for additional services",
        strategy_explanation="Discovered additional subdomain ftp.soulmate.htb which may expose FTP or related file transfer services. This could provide alternative attack vectors beyond the main dating website.",
        new_step="Enumerate further on the X service to find software versions, hidden directories and file",
        step_explanation="Enumerate the ftp.soulmate.htb subdomain to identify what application is running, its version, and potential vulnerabilities.",
        mcp_tasks="Web page interaction: Access ftp.soulmate.htb and identify the application; Interactive CLI: Use curl to examine HTTP headers and responses; Dirbuster: Directory enumeration on ftp subdomain"
    )
    rows.append(row_3)

    # Row 4: FTP subdomain analysis
    ptt_4 = """1. Network Reconnaissance [completed]
1.1. Perform initial port scan [completed]: {Findings: TCP port 22 (SSH) - OpenSSH 8.9p1 Ubuntu, TCP port 80 (HTTP) - nginx 1.18.0 with redirect to soulmate.htb. TTL of 63 indicates Linux one hop away.}
1.2. Identify running services [completed]: {Findings: SSH and HTTP services identified}
2. Service Enumeration [completed]
2.1. Enumerate HTTP service [completed]: {Findings: PHP-based dating website at soulmate.htb with registration/login functionality. SQLite database (soulmate.db) discovered containing bcrypt-hashed admin credentials. File upload functionality exists but has restrictions.}
2.2. Perform subdomain enumeration [completed]: {Findings: Subdomain ftp.soulmate.htb discovered, responds with 302 redirect}
3. Vulnerability Analysis [in-progress]
3.1. Analyze ftp subdomain [completed]: {Findings: CrushFTP instance running behind nginx reverse proxy. Java-based FTP server requiring authentication. CrushFTP version 10/11 detected.}
3.2. Research CrushFTP vulnerabilities [to-do]"""

    row_4 = create_csv_row(
        machine=machine,
        ptt=ptt_4,
        previous_strategy="Investigate the ftp.soulmate.htb subdomain for additional services",
        previous_step="Enumerate further on the X service to find software versions, hidden directories and file",
        previous_step_result="CrushFTP instance running behind nginx reverse proxy. Java-based FTP server requiring authentication. CrushFTP version 10/11 detected.",
        new_strategy="Research CrushFTP vulnerabilities for potential exploitation",
        strategy_explanation="Identified CrushFTP version 10/11, which is a commercial FTP server. Need to research known vulnerabilities, particularly recent CVEs that may allow authentication bypass or remote code execution.",
        new_step="Do a google search for more information",
        step_explanation="Search for CrushFTP version 10/11 vulnerabilities, specifically CVE-2025-31161 and CVE-2025-54309 which affect this version and enable authentication bypass.",
        mcp_tasks="Google search: Search for CrushFTP CVE-2025-31161 CVE-2025-54309 vulnerabilities and exploitation techniques"
    )
    rows.append(row_4)

    # Row 5: Vulnerability research results
    ptt_5 = """1. Network Reconnaissance [completed]
1.1. Perform initial port scan [completed]: {Findings: TCP port 22 (SSH) - OpenSSH 8.9p1 Ubuntu, TCP port 80 (HTTP) - nginx 1.18.0 with redirect to soulmate.htb. TTL of 63 indicates Linux one hop away.}
1.2. Identify running services [completed]: {Findings: SSH and HTTP services identified}
2. Service Enumeration [completed]
2.1. Enumerate HTTP service [completed]: {Findings: PHP-based dating website at soulmate.htb with registration/login functionality. SQLite database (soulmate.db) discovered containing bcrypt-hashed admin credentials. File upload functionality exists but has restrictions.}
2.2. Perform subdomain enumeration [completed]: {Findings: Subdomain ftp.soulmate.htb discovered, responds with 302 redirect}
3. Vulnerability Analysis [completed]
3.1. Analyze ftp subdomain [completed]: {Findings: CrushFTP instance running behind nginx reverse proxy. Java-based FTP server requiring authentication. CrushFTP version 10/11 detected.}
3.2. Research CrushFTP vulnerabilities [completed]: {Findings: CVE-2025-31161 - Mishandled AWS S3-compatible authentication headers allowing user creation without credential validation. CVE-2025-54309 - Race condition in AS2 validation enabling authentication bypass. Both vulnerabilities allow admin user creation.}
4. Initial Access Exploitation [to-do]
4.1. Exploit CVE-2025-31161 or CVE-2025-54309 [to-do]"""

    row_5 = create_csv_row(
        machine=machine,
        ptt=ptt_5,
        previous_strategy="Research CrushFTP vulnerabilities for potential exploitation",
        previous_step="Do a google search for more information",
        previous_step_result="CVE-2025-31161 - Mishandled AWS S3-compatible authentication headers allowing user creation without credential validation. CVE-2025-54309 - Race condition in AS2 validation enabling authentication bypass. Both vulnerabilities allow admin user creation.",
        new_strategy="Exploit CrushFTP vulnerabilities to create admin user and gain access",
        strategy_explanation="Have identified two exploitable authentication bypass vulnerabilities. Either CVE-2025-31161 (AWS header exploitation) or CVE-2025-54309 (race condition) will allow creating an admin account in CrushFTP, providing authenticated access to the file server.",
        new_step="Exploit the selected exploitations",
        step_explanation="Execute CVE-2025-31161 exploit by crafting Authorization headers with AWS4-HMAC-SHA256 format and POST requests with XML payloads to create new admin user in CrushFTP.",
        mcp_tasks="Interactive CLI: Craft exploit requests with malicious Authorization headers (AWS4-HMAC-SHA256 Credential=crushadmin/); Web page interaction: Send POST requests to /WebInterface/function/ with XML payloads to create admin user"
    )
    rows.append(row_5)

    # Row 6: Exploitation success, enumerate CrushFTP
    ptt_6 = """1. Network Reconnaissance [completed]
1.1. Perform initial port scan [completed]: {Findings: TCP port 22 (SSH) - OpenSSH 8.9p1 Ubuntu, TCP port 80 (HTTP) - nginx 1.18.0 with redirect to soulmate.htb. TTL of 63 indicates Linux one hop away.}
1.2. Identify running services [completed]: {Findings: SSH and HTTP services identified}
2. Service Enumeration [completed]
2.1. Enumerate HTTP service [completed]: {Findings: PHP-based dating website at soulmate.htb with registration/login functionality. SQLite database (soulmate.db) discovered containing bcrypt-hashed admin credentials. File upload functionality exists but has restrictions.}
2.2. Perform subdomain enumeration [completed]: {Findings: Subdomain ftp.soulmate.htb discovered, responds with 302 redirect}
3. Vulnerability Analysis [completed]
3.1. Analyze ftp subdomain [completed]: {Findings: CrushFTP instance running behind nginx reverse proxy. Java-based FTP server requiring authentication. CrushFTP version 10/11 detected.}
3.2. Research CrushFTP vulnerabilities [completed]: {Findings: CVE-2025-31161 - Mishandled AWS S3-compatible authentication headers allowing user creation without credential validation. CVE-2025-54309 - Race condition in AS2 validation enabling authentication bypass. Both vulnerabilities allow admin user creation.}
4. Initial Access Exploitation [completed]
4.1. Exploit CVE-2025-31161 or CVE-2025-54309 [completed]: {Findings: Admin user created successfully in CrushFTP. Authenticated access to CrushFTP web interface achieved.}
5. Post-Exploitation [to-do]
5.1. Enumerate CrushFTP file system access [to-do]"""

    row_6 = create_csv_row(
        machine=machine,
        ptt=ptt_6,
        previous_strategy="Exploit CrushFTP vulnerabilities to create admin user and gain access",
        previous_step="Exploit the selected exploitations",
        previous_step_result="Admin user created successfully in CrushFTP. Authenticated access to CrushFTP web interface achieved.",
        new_strategy="Leverage CrushFTP admin access to gain code execution",
        strategy_explanation="Have admin access to CrushFTP. Need to explore file mounting capabilities to access the dating website source code directory (/app/webProd) and upload PHP webshell for code execution as www-data user.",
        new_step="Explore the suspicious files, commands and create a summary of the findings",
        step_explanation="Use CrushFTP admin interface to explore file mounting options, identify accessible directories, and locate the dating website document root for webshell upload.",
        mcp_tasks="Web page interaction: Navigate CrushFTP admin interface to configure file mounts and identify web directories; Interactive CLI: Prepare PHP webshell payload for upload"
    )
    rows.append(row_6)

    # Row 7: File system access and webshell upload
    ptt_7 = """1. Network Reconnaissance [completed]
1.1. Perform initial port scan [completed]: {Findings: TCP port 22 (SSH) - OpenSSH 8.9p1 Ubuntu, TCP port 80 (HTTP) - nginx 1.18.0 with redirect to soulmate.htb. TTL of 63 indicates Linux one hop away.}
1.2. Identify running services [completed]: {Findings: SSH and HTTP services identified}
2. Service Enumeration [completed]
2.1. Enumerate HTTP service [completed]: {Findings: PHP-based dating website at soulmate.htb with registration/login functionality. SQLite database (soulmate.db) discovered containing bcrypt-hashed admin credentials. File upload functionality exists but has restrictions.}
2.2. Perform subdomain enumeration [completed]: {Findings: Subdomain ftp.soulmate.htb discovered, responds with 302 redirect}
3. Vulnerability Analysis [completed]
3.1. Analyze ftp subdomain [completed]: {Findings: CrushFTP instance running behind nginx reverse proxy. Java-based FTP server requiring authentication. CrushFTP version 10/11 detected.}
3.2. Research CrushFTP vulnerabilities [completed]: {Findings: CVE-2025-31161 - Mishandled AWS S3-compatible authentication headers allowing user creation without credential validation. CVE-2025-54309 - Race condition in AS2 validation enabling authentication bypass. Both vulnerabilities allow admin user creation.}
4. Initial Access Exploitation [completed]
4.1. Exploit CVE-2025-31161 or CVE-2025-54309 [completed]: {Findings: Admin user created successfully in CrushFTP. Authenticated access to CrushFTP web interface achieved.}
5. Post-Exploitation [completed]
5.1. Enumerate CrushFTP file system access [completed]: {Findings: File mounting to /app/webProd (dating website source) configured. PHP webshell uploaded as cmd.php to web root.}
5.2. Establish reverse shell [to-do]"""

    row_7 = create_csv_row(
        machine=machine,
        ptt=ptt_7,
        previous_strategy="Leverage CrushFTP admin access to gain code execution",
        previous_step="Explore the suspicious files, commands and create a summary of the findings",
        previous_step_result="File mounting to /app/webProd (dating website source) configured. PHP webshell uploaded as cmd.php to web root.",
        new_strategy="Execute webshell to establish reverse shell as www-data",
        strategy_explanation="Successfully uploaded PHP webshell (cmd.php) to the dating website document root. Now need to access the webshell through the web browser and execute reverse shell command to gain interactive shell access.",
        new_step="Exploit the selected exploitations",
        step_explanation="Access the uploaded cmd.php webshell via soulmate.htb and execute bash reverse shell command to establish connection as www-data user.",
        mcp_tasks="Web page interaction: Access http://soulmate.htb/cmd.php and execute reverse shell command; Netcat: Set up listener to receive reverse shell connection from www-data user"
    )
    rows.append(row_7)

    # Row 8: Shell established, enumerate system
    ptt_8 = """1. Network Reconnaissance [completed]
1.1. Perform initial port scan [completed]: {Findings: TCP port 22 (SSH) - OpenSSH 8.9p1 Ubuntu, TCP port 80 (HTTP) - nginx 1.18.0 with redirect to soulmate.htb. TTL of 63 indicates Linux one hop away.}
1.2. Identify running services [completed]: {Findings: SSH and HTTP services identified}
2. Service Enumeration [completed]
2.1. Enumerate HTTP service [completed]: {Findings: PHP-based dating website at soulmate.htb with registration/login functionality. SQLite database (soulmate.db) discovered containing bcrypt-hashed admin credentials. File upload functionality exists but has restrictions.}
2.2. Perform subdomain enumeration [completed]: {Findings: Subdomain ftp.soulmate.htb discovered, responds with 302 redirect}
3. Vulnerability Analysis [completed]
3.1. Analyze ftp subdomain [completed]: {Findings: CrushFTP instance running behind nginx reverse proxy. Java-based FTP server requiring authentication. CrushFTP version 10/11 detected.}
3.2. Research CrushFTP vulnerabilities [completed]: {Findings: CVE-2025-31161 - Mishandled AWS S3-compatible authentication headers allowing user creation without credential validation. CVE-2025-54309 - Race condition in AS2 validation enabling authentication bypass. Both vulnerabilities allow admin user creation.}
4. Initial Access Exploitation [completed]
4.1. Exploit CVE-2025-31161 or CVE-2025-54309 [completed]: {Findings: Admin user created successfully in CrushFTP. Authenticated access to CrushFTP web interface achieved.}
5. Post-Exploitation [completed]
5.1. Enumerate CrushFTP file system access [completed]: {Findings: File mounting to /app/webProd (dating website source) configured. PHP webshell uploaded as cmd.php to web root.}
5.2. Establish reverse shell [completed]: {Findings: Reverse shell established as www-data user.}
6. Privilege Escalation Enumeration [to-do]
6.1. Search for credentials and sensitive files [to-do]"""

    row_8 = create_csv_row(
        machine=machine,
        ptt=ptt_8,
        previous_strategy="Execute webshell to establish reverse shell as www-data",
        previous_step="Exploit the selected exploitations",
        previous_step_result="Reverse shell established as www-data user.",
        new_strategy="Enumerate system for privilege escalation vectors",
        strategy_explanation="Have www-data shell access. Need to enumerate the system for credentials, SSH keys, SUID binaries, running services, and configuration files that may enable lateral movement to another user or privilege escalation to root.",
        new_step="Explore the suspicious files, commands and create a summary of the findings",
        step_explanation="Search common locations for credentials, examine running processes, check for SUID binaries, enumerate user home directories, and look for interesting configuration files or scripts.",
        mcp_tasks="Interactive CLI: Search /home/, /opt/, /usr/local/ for credentials and scripts; enumerate running processes; check sudo permissions; find SUID binaries"
    )
    rows.append(row_8)

    # Row 9: Credential discovery
    ptt_9 = """1. Network Reconnaissance [completed]
1.1. Perform initial port scan [completed]: {Findings: TCP port 22 (SSH) - OpenSSH 8.9p1 Ubuntu, TCP port 80 (HTTP) - nginx 1.18.0 with redirect to soulmate.htb. TTL of 63 indicates Linux one hop away.}
1.2. Identify running services [completed]: {Findings: SSH and HTTP services identified}
2. Service Enumeration [completed]
2.1. Enumerate HTTP service [completed]: {Findings: PHP-based dating website at soulmate.htb with registration/login functionality. SQLite database (soulmate.db) discovered containing bcrypt-hashed admin credentials. File upload functionality exists but has restrictions.}
2.2. Perform subdomain enumeration [completed]: {Findings: Subdomain ftp.soulmate.htb discovered, responds with 302 redirect}
3. Vulnerability Analysis [completed]
3.1. Analyze ftp subdomain [completed]: {Findings: CrushFTP instance running behind nginx reverse proxy. Java-based FTP server requiring authentication. CrushFTP version 10/11 detected.}
3.2. Research CrushFTP vulnerabilities [completed]: {Findings: CVE-2025-31161 - Mishandled AWS S3-compatible authentication headers allowing user creation without credential validation. CVE-2025-54309 - Race condition in AS2 validation enabling authentication bypass. Both vulnerabilities allow admin user creation.}
4. Initial Access Exploitation [completed]
4.1. Exploit CVE-2025-31161 or CVE-2025-54309 [completed]: {Findings: Admin user created successfully in CrushFTP. Authenticated access to CrushFTP web interface achieved.}
5. Post-Exploitation [completed]
5.1. Enumerate CrushFTP file system access [completed]: {Findings: File mounting to /app/webProd (dating website source) configured. PHP webshell uploaded as cmd.php to web root.}
5.2. Establish reverse shell [completed]: {Findings: Reverse shell established as www-data user.}
6. Privilege Escalation Enumeration [completed]
6.1. Search for credentials and sensitive files [completed]: {Findings: Erlang SSH script at /usr/local/lib/erlang_login/start.escript contains hard-coded password for user ben: HouseH0ldings998}
7. Lateral Movement [to-do]
7.1. Access ben user account [to-do]"""

    row_9 = create_csv_row(
        machine=machine,
        ptt=ptt_9,
        previous_strategy="Enumerate system for privilege escalation vectors",
        previous_step="Explore the suspicious files, commands and create a summary of the findings",
        previous_step_result="Erlang SSH script at /usr/local/lib/erlang_login/start.escript contains hard-coded password for user ben: HouseH0ldings998",
        new_strategy="Pivot to ben user account using discovered credentials",
        strategy_explanation="Discovered hard-coded password for user ben in Erlang SSH script. This credential should allow switching to ben user via su command or SSH, providing access to a privileged user account.",
        new_step="Exploit the selected exploitations",
        step_explanation="Use the discovered password (HouseH0ldings998) to switch to user ben via su command or establish SSH connection as ben.",
        mcp_tasks="Interactive CLI: Execute 'su - ben' with password HouseH0ldings998; SSH: Alternatively connect via SSH as ben@soulmate.htb with discovered password"
    )
    rows.append(row_9)

    # Row 10: Ben user access, enumerate for root
    ptt_10 = """1. Network Reconnaissance [completed]
1.1. Perform initial port scan [completed]: {Findings: TCP port 22 (SSH) - OpenSSH 8.9p1 Ubuntu, TCP port 80 (HTTP) - nginx 1.18.0 with redirect to soulmate.htb. TTL of 63 indicates Linux one hop away.}
1.2. Identify running services [completed]: {Findings: SSH and HTTP services identified}
2. Service Enumeration [completed]
2.1. Enumerate HTTP service [completed]: {Findings: PHP-based dating website at soulmate.htb with registration/login functionality. SQLite database (soulmate.db) discovered containing bcrypt-hashed admin credentials. File upload functionality exists but has restrictions.}
2.2. Perform subdomain enumeration [completed]: {Findings: Subdomain ftp.soulmate.htb discovered, responds with 302 redirect}
3. Vulnerability Analysis [completed]
3.1. Analyze ftp subdomain [completed]: {Findings: CrushFTP instance running behind nginx reverse proxy. Java-based FTP server requiring authentication. CrushFTP version 10/11 detected.}
3.2. Research CrushFTP vulnerabilities [completed]: {Findings: CVE-2025-31161 - Mishandled AWS S3-compatible authentication headers allowing user creation without credential validation. CVE-2025-54309 - Race condition in AS2 validation enabling authentication bypass. Both vulnerabilities allow admin user creation.}
4. Initial Access Exploitation [completed]
4.1. Exploit CVE-2025-31161 or CVE-2025-54309 [completed]: {Findings: Admin user created successfully in CrushFTP. Authenticated access to CrushFTP web interface achieved.}
5. Post-Exploitation [completed]
5.1. Enumerate CrushFTP file system access [completed]: {Findings: File mounting to /app/webProd (dating website source) configured. PHP webshell uploaded as cmd.php to web root.}
5.2. Establish reverse shell [completed]: {Findings: Reverse shell established as www-data user.}
6. Privilege Escalation Enumeration [completed]
6.1. Search for credentials and sensitive files [completed]: {Findings: Erlang SSH script at /usr/local/lib/erlang_login/start.escript contains hard-coded password for user ben: HouseH0ldings998}
7. Lateral Movement [completed]
7.1. Access ben user account [completed]: {Findings: Successfully switched to user ben. User flag captured.}
8. Root Privilege Escalation [to-do]
8.1. Enumerate ben user privileges [to-do]"""

    row_10 = create_csv_row(
        machine=machine,
        ptt=ptt_10,
        previous_strategy="Pivot to ben user account using discovered credentials",
        previous_step="Exploit the selected exploitations",
        previous_step_result="Successfully switched to user ben. User flag captured.",
        new_strategy="Enumerate ben user environment for root privilege escalation",
        strategy_explanation="Have ben user access. The Erlang SSH script that contained ben's password suggests Erlang is involved in system authentication. Need to investigate the Erlang SSH daemon and its privileges.",
        new_step="Explore the suspicious files, commands and create a summary of the findings",
        step_explanation="Investigate the Erlang SSH daemon configuration, check what user it runs as, and determine if it provides any privilege escalation opportunities through Erlang REPL access.",
        mcp_tasks="Interactive CLI: Examine Erlang SSH daemon process, check running processes for Erlang, investigate /usr/local/lib/erlang_login/ directory for additional scripts and configuration"
    )
    rows.append(row_10)

    # Row 11: Erlang discovery and exploitation
    ptt_11 = """1. Network Reconnaissance [completed]
1.1. Perform initial port scan [completed]: {Findings: Three open ports discovered on target 10.129.242.171: Port 22 (SSH) - OpenSSH 8.9p1 Ubuntu, TCP port 80 (HTTP) - nginx 1.18.0 with redirect to soulmate.htb. TTL of 63 indicates Linux one hop away.}
1.2. Identify running services [completed]: {Findings: SSH and HTTP services identified}
2. Service Enumeration [completed]
2.1. Enumerate HTTP service [completed]: {Findings: PHP-based dating website at soulmate.htb with registration/login functionality. SQLite database (soulmate.db) discovered containing bcrypt-hashed admin credentials. File upload functionality exists but has restrictions.}
2.2. Perform subdomain enumeration [completed]: {Findings: Subdomain ftp.soulmate.htb discovered, responds with 302 redirect}
3. Vulnerability Analysis [completed]
3.1. Analyze ftp subdomain [completed]: {Findings: CrushFTP instance running behind nginx reverse proxy. Java-based FTP server requiring authentication. CrushFTP version 10/11 detected.}
3.2. Research CrushFTP vulnerabilities [completed]: {Findings: CVE-2025-31161 - Mishandled AWS S3-compatible authentication headers allowing user creation without credential validation. CVE-2025-54309 - Race condition in AS2 validation enabling authentication bypass. Both vulnerabilities allow admin user creation.}
4. Initial Access Exploitation [completed]
4.1. Exploit CVE-2025-31161 or CVE-2025-54309 [completed]: {Findings: Admin user created successfully in CrushFTP. Authenticated access to CrushFTP web interface achieved.}
5. Post-Exploitation [completed]
5.1. Enumerate CrushFTP file system access [completed]: {Findings: File mounting to /app/webProd (dating website source) configured. PHP webshell uploaded as cmd.php to web root.}
5.2. Establish reverse shell [completed]: {Findings: Reverse shell established as www-data user.}
6. Privilege Escalation Enumeration [completed]
6.1. Search for credentials and sensitive files [completed]: {Findings: Erlang SSH script at /usr/local/lib/erlang_login/start.escript contains hard-coded password for user ben: HouseH0ldings998}
7. Lateral Movement [completed]
7.1. Access ben user account [completed]: {Findings: Successfully switched to user ben. User flag captured.}
8. Root Privilege Escalation [completed]
8.1. Enumerate ben user privileges [completed]: {Findings: Erlang SSH daemon runs as root. Provides full Erlang REPL with root-level code execution. Erlang functions file:read_file() and os:cmd() allow reading root files and executing root commands.}
8.2. Exploit Erlang REPL for root access [to-do]"""

    row_11 = create_csv_row(
        machine=machine,
        ptt=ptt_11,
        previous_strategy="Enumerate ben user environment for root privilege escalation",
        previous_step="Explore the suspicious files, commands and create a summary of the findings",
        previous_step_result="Erlang SSH daemon runs as root. Provides full Erlang REPL with root-level code execution. Erlang functions file:read_file() and os:cmd() allow reading root files and executing root commands.",
        new_strategy="Exploit Erlang REPL running as root to achieve full system compromise",
        strategy_explanation="Discovered Erlang SSH daemon running as root with REPL access. Can use Erlang's built-in functions like file:read_file() to read /root/root.txt and os:cmd() to execute arbitrary commands as root. This provides complete system compromise.",
        new_step="Exploit the selected exploitations",
        step_explanation="Connect to Erlang SSH daemon and use Erlang REPL to execute root commands. Can read root flag directly with file:read_file('/root/root.txt') or create SetUID bash for persistent root shell.",
        mcp_tasks="Interactive CLI: Connect to Erlang REPL and execute Erlang commands - file:read_file('/root/root.txt') to read root flag, os:cmd('chmod 6777 /tmp/rootshell; cp /bin/bash /tmp/rootshell') to create SetUID root shell"
    )
    rows.append(row_11)

    # Row 12: Root achieved, end
    ptt_12 = """1. Network Reconnaissance [completed]
1.1. Perform initial port scan [completed]: {Findings: TCP port 22 (SSH) - OpenSSH 8.9p1 Ubuntu, TCP port 80 (HTTP) - nginx 1.18.0 with redirect to soulmate.htb. TTL of 63 indicates Linux one hop away.}
1.2. Identify running services [completed]: {Findings: SSH and HTTP services identified}
2. Service Enumeration [completed]
2.1. Enumerate HTTP service [completed]: {Findings: PHP-based dating website at soulmate.htb with registration/login functionality. SQLite database (soulmate.db) discovered containing bcrypt-hashed admin credentials. File upload functionality exists but has restrictions.}
2.2. Perform subdomain enumeration [completed]: {Findings: Subdomain ftp.soulmate.htb discovered, responds with 302 redirect}
3. Vulnerability Analysis [completed]
3.1. Analyze ftp subdomain [completed]: {Findings: CrushFTP instance running behind nginx reverse proxy. Java-based FTP server requiring authentication. CrushFTP version 10/11 detected.}
3.2. Research CrushFTP vulnerabilities [completed]: {Findings: CVE-2025-31161 - Mishandled AWS S3-compatible authentication headers allowing user creation without credential validation. CVE-2025-54309 - Race condition in AS2 validation enabling authentication bypass. Both vulnerabilities allow admin user creation.}
4. Initial Access Exploitation [completed]
4.1. Exploit CVE-2025-31161 or CVE-2025-54309 [completed]: {Findings: Admin user created successfully in CrushFTP. Authenticated access to CrushFTP web interface achieved.}
5. Post-Exploitation [completed]
5.1. Enumerate CrushFTP file system access [completed]: {Findings: File mounting to /app/webProd (dating website source) configured. PHP webshell uploaded as cmd.php to web root.}
5.2. Establish reverse shell [completed]: {Findings: Reverse shell established as www-data user.}
6. Privilege Escalation Enumeration [completed]
6.1. Search for credentials and sensitive files [completed]: {Findings: Erlang SSH script at /usr/local/lib/erlang_login/start.escript contains hard-coded password for user ben: HouseH0ldings998}
7. Lateral Movement [completed]
7.1. Access ben user account [completed]: {Findings: Successfully switched to user ben. User flag captured.}
8. Root Privilege Escalation [completed]
8.1. Enumerate ben user privileges [completed]: {Findings: Erlang SSH daemon runs as root. Provides full Erlang REPL with root-level code execution. Erlang functions file:read_file() and os:cmd() allow reading root files and executing root commands.}
8.2. Exploit Erlang REPL for root access [completed]: {Findings: Root flag captured via Erlang file:read_file(). SetUID bash created for persistent root shell. Complete system compromise achieved.}"""

    row_12 = create_csv_row(
        machine=machine,
        ptt=ptt_12,
        previous_strategy="Exploit Erlang REPL running as root to achieve full system compromise",
        previous_step="Exploit the selected exploitations",
        previous_step_result="Root flag captured via Erlang file:read_file(). SetUID bash created for persistent root shell. Complete system compromise achieved.",
        new_strategy="Complete penetration test and prepare final report",
        strategy_explanation="Successfully completed full attack chain: CrushFTP authentication bypass, webshell upload for initial access, hard-coded credential discovery for lateral movement, and Erlang REPL exploitation for root access. All objectives achieved.",
        new_step="End task and ask permission to generate the report",
        step_explanation="Penetration test complete. Documented attack chain from CrushFTP CVE exploitation through root compromise via Erlang REPL. Ready to generate comprehensive report with findings and remediation recommendations.",
        mcp_tasks="Interactive CLI: Collect final evidence and screenshots for report; Document complete attack chain and vulnerabilities discovered"
    )
    rows.append(row_12)

    return rows

if __name__ == "__main__":
    print("Generating Soulmate machine dataset...")
    rows = generate_soulmate_rows()
    filename = os.path.join(os.path.dirname(__file__), "..", "output", "pentest_dataset_batch1_machines_1-10.csv")
    append_rows_to_csv(filename, rows)
    print(f"Generated {len(rows)} rows for Soulmate")
