#!/usr/bin/env python3
"""
Phase 7.2: Generate RSA-2048 keypair and load into Vault KV v2.

Steps:
  1. Generate RSA-2048 keypair in-memory
  2. Serialize to PEM (PKCS#8 private, X.509 SPKI public)
  3. Write to Vault at secret/fintech/jwt with kid + both PEMs
  4. Read back to verify
  5. Shred any temp files (defensive; we keep keys in memory)

Idempotent: re-running overwrites the secret (KV v2 creates a new version).

Usage:
    python3 scripts/vault/load_jwt_keys.py [--vault-addr URL] [--token TOKEN]

Defaults assume Vault dev mode running at http://<minikube-ip>:30200
with root token 'root-token-dev-fintech-2026'.
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone

import requests
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


# ---------- Defaults ----------
DEFAULT_VAULT_ADDR = "http://192.168.49.2:30200"
DEFAULT_TOKEN = "root-token-dev-fintech-2026"
KV_PATH = "secret/data/fintech/jwt"        # KV v2 API path (note the /data/)
KV_READ_PATH = "secret/data/fintech/jwt"   # same for read
KID = f"fintech-rs256-{datetime.now(timezone.utc).strftime('%Y-%m-%d')}"


def get_minikube_ip() -> str:
    """Try to detect minikube IP; fall back to hardcoded default."""
    try:
        out = subprocess.run(
            ["minikube", "ip"], capture_output=True, text=True, check=True, timeout=5
        )
        return out.stdout.strip()
    except (subprocess.SubprocessError, FileNotFoundError):
        return "192.168.49.2"


def generate_rsa_keypair() -> tuple[str, str]:
    """Generate 2048-bit RSA keypair. Returns (private_pem, public_pem) as strings."""
    print("[1/5] Generating RSA-2048 keypair...")
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")

    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")

    # Sanity-check the PEM headers
    assert private_pem.startswith("-----BEGIN PRIVATE KEY-----"), "Bad private PEM header"
    assert public_pem.startswith("-----BEGIN PUBLIC KEY-----"), "Bad public PEM header"
    print(f"      Private key: {len(private_pem)} chars (PKCS#8 PEM)")
    print(f"      Public key:  {len(public_pem)} chars (X.509 SPKI PEM)")
    return private_pem, public_pem


def vault_write(vault_addr: str, token: str, private_pem: str, public_pem: str) -> None:
    """Write keypair to Vault KV v2 at secret/fintech/jwt."""
    url = f"{vault_addr}/v1/{KV_PATH}"
    payload = {
        "data": {
            "private_key": private_pem,
            "public_key": public_pem,
            "kid": KID,
            "algorithm": "RS256",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    }
    headers = {"X-Vault-Token": token, "Content-Type": "application/json"}

    print(f"[2/5] Writing to Vault at {url}...")
    resp = requests.post(url, headers=headers, data=json.dumps(payload), timeout=10)
    if resp.status_code not in (200, 204):
        print(f"      FAILED: HTTP {resp.status_code}\n      Body: {resp.text}", file=sys.stderr)
        sys.exit(1)

    body = resp.json()
    version = body.get("data", {}).get("version", "?")
    print(f"      OK — version {version} stored")


def vault_read_verify(vault_addr: str, token: str, expected_kid: str) -> dict:
    """Read back the secret and verify it matches what we wrote."""
    url = f"{vault_addr}/v1/{KV_READ_PATH}"
    headers = {"X-Vault-Token": token}

    print(f"[3/5] Reading back from Vault to verify...")
    resp = requests.get(url, headers=headers, timeout=10)
    if resp.status_code != 200:
        print(f"      FAILED: HTTP {resp.status_code}\n      Body: {resp.text}", file=sys.stderr)
        sys.exit(1)

    data = resp.json()["data"]["data"]   # KV v2 nests: outer "data" = metadata wrapper, inner "data" = our fields
    assert data["kid"] == expected_kid, f"kid mismatch: {data['kid']} != {expected_kid}"
    assert data["algorithm"] == "RS256"
    assert data["private_key"].startswith("-----BEGIN PRIVATE KEY-----")
    assert data["public_key"].startswith("-----BEGIN PUBLIC KEY-----")
    print(f"      OK — kid={data['kid']}, algorithm={data['algorithm']}")
    print(f"      private_key: {len(data['private_key'])} chars")
    print(f"      public_key:  {len(data['public_key'])} chars")
    return data


def print_public_key_for_inspection(public_pem: str) -> None:
    """Display the public key — safe to log, useful for verification."""
    print(f"[4/5] Public key (safe to share, log, commit):")
    for line in public_pem.strip().split("\n"):
        print(f"      {line}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--vault-addr", default=None, help="Vault address (default: auto-detect minikube IP:30200)")
    parser.add_argument("--token", default=DEFAULT_TOKEN, help="Vault token")
    args = parser.parse_args()

    vault_addr = args.vault_addr or f"http://{get_minikube_ip()}:30200"
    print(f"Vault address: {vault_addr}")
    print(f"Key ID (kid):  {KID}")
    print()

    # Pre-flight: verify Vault is reachable + unsealed
    try:
        health = requests.get(f"{vault_addr}/v1/sys/health", timeout=5).json()
        if health.get("sealed"):
            print("ERROR: Vault is sealed. Cannot write secrets.", file=sys.stderr)
            sys.exit(1)
        print(f"Vault health: initialized={health.get('initialized')}, sealed={health.get('sealed')}, version={health.get('version')}")
        print()
    except Exception as e:
        print(f"ERROR: Cannot reach Vault at {vault_addr}: {e}", file=sys.stderr)
        sys.exit(1)

    private_pem, public_pem = generate_rsa_keypair()
    vault_write(vault_addr, args.token, private_pem, public_pem)
    vault_read_verify(vault_addr, args.token, KID)
    print_public_key_for_inspection(public_pem)

    # Phase 7.2.5: defensive cleanup. We never wrote keys to disk, but explicitly note that.
    print(f"[5/5] No PEM files written to disk — keys exist only in Vault now.")
    print()
    print("=" * 60)
    print("Phase 7.2 complete.")
    print(f"  Vault path: secret/fintech/jwt")
    print(f"  kid:        {KID}")
    print(f"  algorithm:  RS256")
    print("=" * 60)


if __name__ == "__main__":
    main()
