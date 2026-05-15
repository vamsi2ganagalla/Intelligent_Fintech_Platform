#!/usr/bin/env python3
"""
Phase 7.4: Patch all 3 services for Spring Cloud Vault + RS256 JWT config.

Changes per service:
  pom.xml:
    - Add <dependencyManagement> with Spring Cloud BOM 2025.0.0
    - Add spring-cloud-starter-vault-config dependency
  application.yaml:
    - Remove jwt.secret: ${JWT_SECRET}
    - Add spring.cloud.vault AppRole config
    - Add spring.config.import: vault://secret/fintech/jwt
    - Add jwt.public-key placeholder (populated by Vault import)
    - auth-service only: add jwt.private-key placeholder

  Does NOT touch JwtUtil.java — that is Phase 7.5.

Idempotent: checks for markers before inserting to avoid double-patching.
"""

import re
import sys
from pathlib import Path

SERVICES_DIR = Path(__file__).parent.parent.parent / "services"

# Verify we can find the services
for svc in ["auth-service", "user-service", "transaction-service"]:
    assert (SERVICES_DIR / svc / "pom.xml").exists(), f"Cannot find {svc}/pom.xml — run from repo root or adjust SERVICES_DIR"

print(f"Services dir: {SERVICES_DIR}")
print()

# ─────────────────────────────────────────────────────────────
# POM PATCHING
# ─────────────────────────────────────────────────────────────

SPRING_CLOUD_BOM_BLOCK = """
\t<dependencyManagement>
\t\t<dependencies>
\t\t\t<dependency>
\t\t\t\t<groupId>org.springframework.cloud</groupId>
\t\t\t\t<artifactId>spring-cloud-dependencies</artifactId>
\t\t\t\t<version>2025.0.0</version>
\t\t\t\t<type>pom</type>
\t\t\t\t<scope>import</scope>
\t\t\t</dependency>
\t\t</dependencies>
\t</dependencyManagement>"""

SPRING_CLOUD_BOM_BLOCK_SPACES = """
    <dependencyManagement>
        <dependencies>
            <dependency>
                <groupId>org.springframework.cloud</groupId>
                <artifactId>spring-cloud-dependencies</artifactId>
                <version>2025.0.0</version>
                <type>pom</type>
                <scope>import</scope>
            </dependency>
        </dependencies>
    </dependencyManagement>"""

VAULT_DEP_TABS = """\t\t<dependency>
\t\t\t<groupId>org.springframework.cloud</groupId>
\t\t\t<artifactId>spring-cloud-starter-vault-config</artifactId>
\t\t</dependency>"""

VAULT_DEP_SPACES = """        <dependency>
            <groupId>org.springframework.cloud</groupId>
            <artifactId>spring-cloud-starter-vault-config</artifactId>
        </dependency>"""


def detect_indent(content: str) -> str:
    """Detect whether pom uses tabs or spaces by checking the <dependencies> block."""
    for line in content.splitlines():
        if "<dependency>" in line:
            return "tabs" if line.startswith("\t") else "spaces"
    return "spaces"


def patch_pom(service_name: str) -> None:
    pom_path = SERVICES_DIR / service_name / "pom.xml"
    content = pom_path.read_text()

    indent_style = detect_indent(content)
    bom_block = SPRING_CLOUD_BOM_BLOCK if indent_style == "tabs" else SPRING_CLOUD_BOM_BLOCK_SPACES
    vault_dep = VAULT_DEP_TABS if indent_style == "tabs" else VAULT_DEP_SPACES

    print(f"  [{service_name}] indent={indent_style}")

    # Guard: skip if already patched
    if "spring-cloud-dependencies" in content:
        print(f"  [{service_name}] pom already has Spring Cloud BOM — skipping BOM insert")
    else:
        # Insert <dependencyManagement> just before <dependencies>
        # Regex: find first <dependencies> tag (not inside a comment)
        content = re.sub(
            r'(\n\s*<dependencies>)',
            bom_block + r'\1',
            content,
            count=1
        )
        print(f"  [{service_name}] Inserted Spring Cloud BOM <dependencyManagement>")

    if "spring-cloud-starter-vault-config" in content:
        print(f"  [{service_name}] pom already has vault-config dep — skipping dep insert")
    else:
        # Insert vault dep as the LAST item before </dependencies>
        content = re.sub(
            r'(\s*</dependencies>)',
            "\n" + vault_dep + r'\1',
            content,
            count=1
        )
        print(f"  [{service_name}] Inserted spring-cloud-starter-vault-config dependency")

    pom_path.write_text(content)
    print(f"  [{service_name}] pom.xml written OK")


# ─────────────────────────────────────────────────────────────
# YAML PATCHING — full rewrite approach
# ─────────────────────────────────────────────────────────────

# Vault URI uses internal K8s DNS: vault service in vault namespace
VAULT_URI = "http://vault.vault.svc.cluster.local:8200"

# The spring.cloud.vault block to inject, with placeholders for role vars
VAULT_YAML_BLOCK_AUTH = """\
  cloud:
    vault:
      uri: ${VAULT_URI:http://vault.vault.svc.cluster.local:8200}
      authentication: APPROLE
      app-role:
        role-id: ${VAULT_ROLE_ID}
        secret-id: ${VAULT_SECRET_ID}
        app-auth-path: approle
      kv:
        enabled: true
        backend: secret
        default-context: fintech/jwt
      fail-fast: true
      config:
        lifecycle:
          enabled: true
  config:
    import: "vault://secret/fintech/jwt"
"""

VAULT_YAML_BLOCK_VERIFIER = """\
  cloud:
    vault:
      uri: ${VAULT_URI:http://vault.vault.svc.cluster.local:8200}
      authentication: APPROLE
      app-role:
        role-id: ${VAULT_ROLE_ID}
        secret-id: ${VAULT_SECRET_ID}
        app-auth-path: approle
      kv:
        enabled: true
        backend: secret
        default-context: fintech/jwt
      fail-fast: true
      config:
        lifecycle:
          enabled: true
  config:
    import: "vault://secret/fintech/jwt"
"""

# JWT section replacements
JWT_SECTION_AUTH = """\
jwt:
  private-key: ${private_key}
  public-key: ${public_key}
  kid: ${kid}
  expiration: ${JWT_EXPIRATION:3600000}
  refresh-expiration: ${JWT_REFRESH_EXPIRATION:604800000}
"""

JWT_SECTION_VERIFIER = """\
jwt:
  public-key: ${public_key}
  kid: ${kid}
  expiration: ${JWT_EXPIRATION:3600000}
"""


def patch_yaml(service_name: str, is_auth: bool) -> None:
    yaml_path = SERVICES_DIR / service_name / "src/main/resources/application.yaml"
    content = yaml_path.read_text()

    # Guard: skip if already patched
    if "spring-cloud-starter-vault-config" in content or "vault.vault.svc" in content:
        print(f"  [{service_name}] application.yaml already patched — skipping")
        return

    vault_block = VAULT_YAML_BLOCK_AUTH if is_auth else VAULT_YAML_BLOCK_VERIFIER
    jwt_section = JWT_SECTION_AUTH if is_auth else JWT_SECTION_VERIFIER

    # Step 1: Find the spring: block and inject vault + config.import into it.
    # We insert our vault block just before the closing of the spring: section.
    # Strategy: find "  jpa:" (the next top-level spring child after datasource)
    # and insert the vault block before it. This avoids multiline replacement issues.
    # More robust: find the line "  jpa:" and insert before it.

    lines = content.splitlines(keepends=True)
    new_lines = []
    vault_inserted = False
    jwt_replaced = False

    i = 0
    while i < len(lines):
        line = lines[i]

        # Replace the entire jwt: block (jwt: + everything until next top-level key or EOF)
        if re.match(r'^jwt:', line) and not jwt_replaced:
            # Skip all lines of the old jwt block
            new_lines.append(jwt_section)
            jwt_replaced = True
            i += 1
            # Skip continuation lines of jwt block (indented lines)
            while i < len(lines) and (lines[i].startswith("  ") or lines[i].strip() == ""):
                i += 1
            continue

        # Insert vault block before "  jpa:" inside spring: section
        if re.match(r'^  jpa:', line) and not vault_inserted:
            new_lines.append(vault_block)
            vault_inserted = True

        new_lines.append(line)
        i += 1

    if not vault_inserted:
        print(f"  [{service_name}] WARNING: could not find '  jpa:' anchor — vault block NOT inserted", file=sys.stderr)
        sys.exit(1)
    if not jwt_replaced:
        print(f"  [{service_name}] WARNING: could not find 'jwt:' block — jwt section NOT replaced", file=sys.stderr)
        sys.exit(1)

    new_content = "".join(new_lines)
    yaml_path.write_text(new_content)
    print(f"  [{service_name}] application.yaml written OK (vault_inserted={vault_inserted}, jwt_replaced={jwt_replaced})")


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

def main() -> None:
    services = [
        ("auth-service", True),
        ("user-service", False),
        ("transaction-service", False),
    ]

    print("=== POM PATCHING ===")
    for svc, is_auth in services:
        patch_pom(svc)
        print()

    print("=== YAML PATCHING ===")
    for svc, is_auth in services:
        patch_yaml(svc, is_auth)
        print()

    print("=" * 60)
    print("Phase 7.4 patching complete.")
    print()
    print("NEXT STEPS (manual verification before building):")
    print("  1. git diff services/auth-service/pom.xml")
    print("  2. git diff services/auth-service/src/main/resources/application.yaml")
    print("  3. git diff services/user-service/pom.xml")
    print("  4. Same for transaction-service")
    print()
    print("Then Phase 7.5: rewrite JwtUtil in all 3 services for RS256")
    print("=" * 60)


if __name__ == "__main__":
    main()
