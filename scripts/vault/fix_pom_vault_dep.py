#!/usr/bin/env python3
"""
Fix: move spring-cloud-starter-vault-config from <dependencyManagement>
into the main <dependencies> block where it belongs.

The previous patch inserted it as the last item inside <dependencyManagement>
(before the closing </dependencies> of that block). This script:
  1. Removes it from <dependencyManagement>
  2. Inserts it correctly into the main <dependencies> block

Idempotent: checks current state before modifying.
"""

import re
import sys
from pathlib import Path

SERVICES_DIR = Path(__file__).parent.parent.parent / "services"

VAULT_DEP_TABS = """\t\t<dependency>
\t\t\t<groupId>org.springframework.cloud</groupId>
\t\t\t<artifactId>spring-cloud-starter-vault-config</artifactId>
\t\t</dependency>"""

VAULT_DEP_SPACES = """        <dependency>
            <groupId>org.springframework.cloud</groupId>
            <artifactId>spring-cloud-starter-vault-config</artifactId>
        </dependency>"""


def detect_indent(content: str) -> str:
    for line in content.splitlines():
        if "<dependency>" in line:
            return "tabs" if line.startswith("\t") else "spaces"
    return "spaces"


def fix_pom(service_name: str) -> None:
    pom_path = SERVICES_DIR / service_name / "pom.xml"
    content = pom_path.read_text()
    indent = detect_indent(content)
    vault_dep = VAULT_DEP_TABS if indent == "tabs" else VAULT_DEP_SPACES

    print(f"  [{service_name}] indent={indent}")

    # ── Step 1: verify the bug is present ──────────────────────────────────
    # The misplaced dep is inside dependencyManagement — detect this by
    # checking if spring-cloud-starter-vault-config appears before </dependencyManagement>
    dm_block_match = re.search(
        r'<dependencyManagement>.*?</dependencyManagement>',
        content, re.DOTALL
    )
    if not dm_block_match:
        print(f"  [{service_name}] No <dependencyManagement> block found — skipping")
        return

    dm_block = dm_block_match.group(0)
    if "spring-cloud-starter-vault-config" not in dm_block:
        print(f"  [{service_name}] vault-config NOT in dependencyManagement — already fixed or unexpected state")
        # Check it's in main deps
        if "spring-cloud-starter-vault-config" in content:
            print(f"  [{service_name}] vault-config found in main deps — OK")
        return

    # ── Step 2: remove vault-config dep from inside dependencyManagement ───
    # It appears as either tabs or spaces variant just before </dependencies>
    # inside the dependencyManagement block. Remove it precisely.

    # Pattern: optional whitespace + <dependency> block for vault-config + trailing newline
    removal_pattern = re.compile(
        r'\n[ \t]*<dependency>\n[ \t]*<groupId>org\.springframework\.cloud</groupId>\n'
        r'[ \t]*<artifactId>spring-cloud-starter-vault-config</artifactId>\n'
        r'[ \t]*</dependency>',
        re.MULTILINE
    )

    # Only remove the FIRST occurrence (which is inside dependencyManagement)
    # Count occurrences first
    occurrences = len(removal_pattern.findall(content))
    print(f"  [{service_name}] Found {occurrences} occurrence(s) of vault-config dep")

    content_after_removal = removal_pattern.sub("", content, count=1)

    if content_after_removal == content:
        print(f"  [{service_name}] ERROR: removal pattern did not match — manual inspection needed", file=sys.stderr)
        sys.exit(1)

    print(f"  [{service_name}] Removed vault-config from dependencyManagement")

    # ── Step 3: insert vault-config into the MAIN <dependencies> block ─────
    # The main <dependencies> block comes AFTER </dependencyManagement>.
    # Strategy: find </dependencyManagement> then find the NEXT </dependencies>
    # and insert our dep just before it.

    if "spring-cloud-starter-vault-config" in content_after_removal:
        print(f"  [{service_name}] vault-config still present after removal — unexpected, aborting", file=sys.stderr)
        sys.exit(1)

    # Split on </dependencyManagement> to operate only on the portion after it
    parts = content_after_removal.split("</dependencyManagement>", 1)
    if len(parts) != 2:
        print(f"  [{service_name}] Cannot split on </dependencyManagement> — aborting", file=sys.stderr)
        sys.exit(1)

    before_dm_close = parts[0]
    after_dm_close = parts[1]

    # In the after_dm_close portion, insert before the LAST </dependencies>
    # (which is the closing tag of the main <dependencies> block)
    insert_pattern = re.compile(r'(\s*</dependencies>\s*</project>)', re.DOTALL)
    replacement = "\n" + vault_dep + r'\1'
    after_dm_close_patched, n = insert_pattern.subn(replacement, after_dm_close, count=1)

    if n == 0:
        print(f"  [{service_name}] ERROR: could not find main </dependencies> insertion point", file=sys.stderr)
        sys.exit(1)

    final_content = before_dm_close + "</dependencyManagement>" + after_dm_close_patched
    pom_path.write_text(final_content)
    print(f"  [{service_name}] vault-config inserted into main <dependencies> — pom.xml written OK")


def main() -> None:
    for svc in ["auth-service", "user-service", "transaction-service"]:
        fix_pom(svc)
        print()

    print("=" * 60)
    print("Pom fix complete. Verify with:")
    print("  git diff services/auth-service/pom.xml")
    print("  git diff services/user-service/pom.xml")
    print("  git diff services/transaction-service/pom.xml")
    print("=" * 60)


if __name__ == "__main__":
    main()
