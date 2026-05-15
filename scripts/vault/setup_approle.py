#!/usr/bin/env python3
"""
Phase 7.3: Configure Vault AppRole auth + policies + K8s Secrets.

Architecture:
    auth-service       -> AppRole 'auth-service-role'  -> Policy 'fintech-auth-policy'
    user-service       -> AppRole 'verifier-role'      -> Policy 'fintech-verifier-policy'
    transaction-service-> AppRole 'verifier-role'      -> Policy 'fintech-verifier-policy'

Both policies currently grant identical `read` on secret/data/fintech/jwt.
Logical separation is enforced at the application code layer (Phase 7.5):
verifier services have no signing code path.

Idempotent: re-running updates policies/roles in place, generates a NEW
secret_id (old secret_ids continue to work until they expire).

Usage:
    python3 scripts/vault/setup_approle.py [--vault-addr URL] [--token TOKEN]
"""

import argparse
import base64
import json
import subprocess
import sys

import requests


DEFAULT_VAULT_ADDR = "http://192.168.49.2:30200"
DEFAULT_TOKEN = "root-token-dev-fintech-2026"
K8S_NAMESPACE = "default"

# Policy HCL definitions — each grants read on the JWT secret path.
POLICIES = {
    "fintech-auth-policy": '''
path "secret/data/fintech/jwt" {
  capabilities = ["read"]
}
'''.strip(),
    "fintech-verifier-policy": '''
path "secret/data/fintech/jwt" {
  capabilities = ["read"]
}
'''.strip(),
}

ROLES = {
    "auth-service-role": {
        "token_policies": "fintech-auth-policy",
        "token_ttl": "1h",
        "token_max_ttl": "4h",
        "secret_id_ttl": "0",        # dev mode: no expiry. Production would set 24h.
        "secret_id_num_uses": "0",   # dev mode: unlimited. Production would set 1 (response-wrapped).
    },
    "verifier-role": {
        "token_policies": "fintech-verifier-policy",
        "token_ttl": "1h",
        "token_max_ttl": "4h",
        "secret_id_ttl": "0",
        "secret_id_num_uses": "0",
    },
}

# Maps each role to the K8s Secret name it gets written to.
ROLE_TO_K8S_SECRET = {
    "auth-service-role": "vault-approle-auth",
    "verifier-role": "vault-approle-verifier",
}


def get_minikube_ip() -> str:
    try:
        out = subprocess.run(["minikube", "ip"], capture_output=True, text=True, check=True, timeout=5)
        return out.stdout.strip()
    except (subprocess.SubprocessError, FileNotFoundError):
        return "192.168.49.2"


def vault_request(method: str, vault_addr: str, token: str, path: str, payload: dict | None = None) -> dict:
    url = f"{vault_addr}/v1/{path}"
    headers = {"X-Vault-Token": token, "Content-Type": "application/json"}
    data = json.dumps(payload) if payload is not None else None
    resp = requests.request(method, url, headers=headers, data=data, timeout=10)

    # 204 = success with no body (common for writes)
    if resp.status_code == 204:
        return {}
    if resp.status_code >= 400:
        print(f"      FAILED {method} {path}: HTTP {resp.status_code}", file=sys.stderr)
        print(f"      Body: {resp.text}", file=sys.stderr)
        sys.exit(1)
    return resp.json()


def ensure_approle_enabled(vault_addr: str, token: str) -> None:
    print("[1/6] Ensuring AppRole auth method is enabled...")
    # Check current auth methods
    methods = vault_request("GET", vault_addr, token, "sys/auth")
    if "approle/" in methods.get("data", methods):  # response format varies
        # The dict directly contains mount names as keys at top level
        keys = methods.get("data", methods)
        if "approle/" in keys:
            print("      AppRole already enabled — skipping.")
            return
    if "approle/" in methods:
        print("      AppRole already enabled — skipping.")
        return

    # Enable it
    payload = {"type": "approle"}
    vault_request("POST", vault_addr, token, "sys/auth/approle", payload)
    print("      Enabled AppRole at auth/approle/")


def write_policies(vault_addr: str, token: str) -> None:
    print("[2/6] Writing policies...")
    for name, hcl in POLICIES.items():
        payload = {"policy": hcl}
        vault_request("PUT", vault_addr, token, f"sys/policies/acl/{name}", payload)
        print(f"      Wrote policy: {name}")


def create_roles(vault_addr: str, token: str) -> None:
    print("[3/6] Creating AppRoles...")
    for role_name, params in ROLES.items():
        vault_request("POST", vault_addr, token, f"auth/approle/role/{role_name}", params)
        print(f"      Created role: {role_name} (policy={params['token_policies']})")


def fetch_credentials(vault_addr: str, token: str) -> dict[str, dict]:
    print("[4/6] Fetching role_id + generating secret_id for each role...")
    creds = {}
    for role_name in ROLES.keys():
        # role_id (idempotent — same value across calls)
        role_id_resp = vault_request("GET", vault_addr, token, f"auth/approle/role/{role_name}/role-id")
        role_id = role_id_resp["data"]["role_id"]

        # secret_id (new value each call — old ones still valid until TTL)
        secret_id_resp = vault_request("POST", vault_addr, token, f"auth/approle/role/{role_name}/secret-id", {})
        secret_id = secret_id_resp["data"]["secret_id"]

        creds[role_name] = {"role_id": role_id, "secret_id": secret_id}
        print(f"      {role_name}: role_id={role_id[:8]}... secret_id={secret_id[:8]}...")
    return creds


def write_k8s_secrets(creds: dict[str, dict]) -> None:
    print("[5/6] Writing K8s Secrets to namespace 'default'...")
    for role_name, cred in creds.items():
        secret_name = ROLE_TO_K8S_SECRET[role_name]
        manifest = {
            "apiVersion": "v1",
            "kind": "Secret",
            "metadata": {
                "name": secret_name,
                "namespace": K8S_NAMESPACE,
                "labels": {"managed-by": "phase-7.3", "vault-role": role_name},
            },
            "type": "Opaque",
            "data": {
                "role-id": base64.b64encode(cred["role_id"].encode()).decode(),
                "secret-id": base64.b64encode(cred["secret_id"].encode()).decode(),
            },
        }
        yaml_str = json.dumps(manifest)  # kubectl accepts JSON
        proc = subprocess.run(
            ["kubectl", "apply", "-f", "-"],
            input=yaml_str, capture_output=True, text=True, timeout=10,
        )
        if proc.returncode != 0:
            print(f"      FAILED kubectl apply for {secret_name}:", file=sys.stderr)
            print(proc.stderr, file=sys.stderr)
            sys.exit(1)
        print(f"      {proc.stdout.strip()}")


def verify_login(vault_addr: str, creds: dict[str, dict]) -> None:
    print("[6/6] Verifying each AppRole can log in...")
    for role_name, cred in creds.items():
        url = f"{vault_addr}/v1/auth/approle/login"
        payload = {"role_id": cred["role_id"], "secret_id": cred["secret_id"]}
        resp = requests.post(url, data=json.dumps(payload), timeout=10)
        if resp.status_code != 200:
            print(f"      FAILED login for {role_name}: HTTP {resp.status_code}", file=sys.stderr)
            print(f"      Body: {resp.text}", file=sys.stderr)
            sys.exit(1)
        body = resp.json()
        client_token = body["auth"]["client_token"]
        policies = body["auth"]["token_policies"]
        ttl = body["auth"]["lease_duration"]
        print(f"      {role_name}: logged in OK")
        print(f"        token: {client_token[:12]}... policies={policies} ttl={ttl}s")

        # Also verify the token can actually READ the JWT secret
        read_url = f"{vault_addr}/v1/secret/data/fintech/jwt"
        read_resp = requests.get(read_url, headers={"X-Vault-Token": client_token}, timeout=10)
        if read_resp.status_code != 200:
            print(f"        WARN: token cannot read JWT secret: HTTP {read_resp.status_code}", file=sys.stderr)
            sys.exit(1)
        kid = read_resp.json()["data"]["data"]["kid"]
        print(f"        successfully read secret/fintech/jwt (kid={kid})")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--vault-addr", default=None)
    parser.add_argument("--token", default=DEFAULT_TOKEN)
    args = parser.parse_args()

    vault_addr = args.vault_addr or f"http://{get_minikube_ip()}:30200"
    print(f"Vault address: {vault_addr}")
    print(f"K8s namespace: {K8S_NAMESPACE}")
    print()

    ensure_approle_enabled(vault_addr, args.token)
    write_policies(vault_addr, args.token)
    create_roles(vault_addr, args.token)
    creds = fetch_credentials(vault_addr, args.token)
    write_k8s_secrets(creds)
    verify_login(vault_addr, creds)

    print()
    print("=" * 60)
    print("Phase 7.3 complete.")
    print(f"  AppRoles created: {', '.join(ROLES.keys())}")
    print(f"  Policies created: {', '.join(POLICIES.keys())}")
    print(f"  K8s Secrets in '{K8S_NAMESPACE}': {', '.join(ROLE_TO_K8S_SECRET.values())}")
    print()
    print("Next: Phase 7.4 — Spring Cloud Vault integration")
    print("=" * 60)


if __name__ == "__main__":
    main()
