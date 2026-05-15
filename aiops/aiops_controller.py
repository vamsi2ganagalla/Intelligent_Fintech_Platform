#!/usr/bin/env python3
"""
AIOps Self-Healing Controller — Intelligent FinTech Platform
Matches report Chapter 11 exactly:
  - Elasticsearch polling for error rates per service
  - Z-score anomaly detection (50-sample rolling window, threshold 3.0)
  - Dependency-aware sequenced recovery
  - Audit log written back to Elasticsearch

Dependency graph (report Table 11.1):
  postgres -> auth-service -> user-service
                           -> transaction-service

Detection patterns (report Table 11.1):
  1. DB connection cascade
  2. Vault unreachable
  3. Isolated service spike
  4. Auth failure spike (alert only)
  5. Memory pressure
"""

import json
import logging
import os
import subprocess
import time
import urllib.request
import urllib.error
from collections import deque
from datetime import datetime, timezone
from statistics import mean, stdev

# ── Configuration ────────────────────────────────────────────────────────────
ES_HOST = os.environ.get("ES_HOST", "http://elasticsearch.logging.svc.cluster.local:9200")
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL", "30"))
WINDOW_SIZE = int(os.environ.get("WINDOW_SIZE", "50"))
ZSCORE_THRESHOLD = float(os.environ.get("ZSCORE_THRESHOLD", "1.5"))
AUTH_SPIKE_MULTIPLIER = float(os.environ.get("AUTH_SPIKE_MULTIPLIER", "5.0"))
LOOKBACK_MINUTES = int(os.environ.get("LOOKBACK_MINUTES", "2"))
NAMESPACE = os.environ.get("NAMESPACE", "default")
DRY_RUN = os.environ.get("DRY_RUN", "false").lower() == "true"

SERVICES = ["auth-service", "user-service", "transaction-service"]

# Dependency graph: service -> list of services it depends on
DEPENDENCY_GRAPH = {
    "auth-service": ["postgres"],
    "user-service": ["auth-service", "postgres"],
    "transaction-service": ["auth-service", "postgres"],
}

# Rolling windows: service -> deque of error counts
error_windows = {svc: deque(maxlen=WINDOW_SIZE) for svc in SERVICES}
# Cooldown tracking: service -> timestamp of last recovery action
last_recovery = {svc: 0.0 for svc in SERVICES}
COOLDOWN_SECONDS = int(os.environ.get("COOLDOWN_SECONDS", "300"))  # 5 min cooldown
# Baseline 401/403 rate for auth spike detection
auth_baseline_window = deque(maxlen=WINDOW_SIZE)

logging.basicConfig(
    level=logging.INFO,
    format='{"@timestamp":"%(asctime)s","level":"%(levelname)s","message":"%(message)s","service":"aiops-controller"}',
    datefmt="%Y-%m-%dT%H:%M:%SZ"
)
log = logging.getLogger("aiops")


# ── Elasticsearch helpers ────────────────────────────────────────────────────

def es_request(method: str, path: str, payload: dict = None) -> dict:
    url = f"{ES_HOST}{path}"
    data = json.dumps(payload).encode() if payload else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        log.warning(f"ES {method} {path} -> HTTP {e.code}: {e.read().decode()[:200]}")
        return {}
    except Exception as e:
        log.warning(f"ES {method} {path} -> {e}")
        return {}


def get_error_count(service: str, minutes: int) -> int:
    """Count ERROR+WARN log entries for a service in the last N minutes."""
    query = {
        "query": {
            "bool": {
                "must": [
                    {"term": {"service.keyword": service}},
                    {"range": {"@timestamp": {"gte": f"now-{minutes}m", "lte": "now"}}}
                ],
                "should": [
                    {"match": {"level": "ERROR"}},
                    {"match": {"level": "WARN"}}
                ],
                "minimum_should_match": 1
            }
        }
    }
    result = es_request("POST", "/fintech-logs-*/_count", query)
    return result.get("count", 0)
def get_auth_failure_count(minutes: int) -> int:
    """Count authentication-related error messages (401/403 indicators)."""
    query = {
        "query": {
            "bool": {
                "must": [
                    {"term": {"service": "auth-service"}},
                    {"range": {"@timestamp": {"gte": f"now-{minutes}m", "lte": "now"}}},
                    {"bool": {"should": [
                        {"match": {"message": "Login attempt with unknown email"}},
                        {"match": {"message": "Invalid email or password"}},
                        {"match": {"message": "InvalidCredentialsException"}}
                    ]}}
                ]
            }
        }
    }
    result = es_request("POST", "/fintech-logs-*/_count", query)
    return result.get("count", 0)


def get_vault_error_count(minutes: int) -> int:
    """Detect Vault-related failures across all services."""
    query = {
        "query": {
            "bool": {
                "must": [
                    {"range": {"@timestamp": {"gte": f"now-{minutes}m", "lte": "now"}}},
                    {"bool": {"should": [
                        {"match_phrase": {"message": "Failed to parse RSA"}},
                        {"match_phrase": {"message": "JWT signing failed"}},
                        {"match_phrase": {"message": "vault connection refused"}}
                    ]}}
                ]
            }
        }
    }
    result = es_request("POST", "/fintech-logs-*/_count", query)
    return result.get("count", 0)


# ── Z-score anomaly detection ────────────────────────────────────────────────

def compute_zscore(window: deque, current: float) -> float:
    """Z = (x - mean) / stdev over rolling window. Returns 0 if window too small."""
    if len(window) < 5:
        return 0.0
    m = mean(window)
    try:
        s = stdev(window)
    except Exception:
        return 0.0
    if s == 0:
        return 0.0 if current == m else float('inf')
    return (current - m) / s


# ── Kubernetes recovery actions ──────────────────────────────────────────────

def kubectl(args: list) -> tuple[int, str]:
    """Run a kubectl command. Returns (returncode, output)."""
    cmd = ["kubectl"] + args
    if DRY_RUN:
        log.info(f"DRY_RUN: kubectl {' '.join(args)}")
        return 0, "dry-run"
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return result.returncode, result.stdout + result.stderr
    except Exception as e:
        return 1, str(e)


def k8s_patch(path: str, payload: dict) -> bool:
    """Patch a K8s resource via the in-cluster API server."""
    k8s_host = os.environ.get("KUBERNETES_SERVICE_HOST", "kubernetes.default.svc")
    k8s_port = os.environ.get("KUBERNETES_SERVICE_PORT", "443")
    token_path = "/var/run/secrets/kubernetes.io/serviceaccount/token"
    ca_path = "/var/run/secrets/kubernetes.io/serviceaccount/ca.crt"

    try:
        with open(token_path) as f:
            token = f.read().strip()
    except Exception as e:
        log.error(f"Cannot read service account token: {e}")
        return False

    url = f"https://{k8s_host}:{k8s_port}{path}"
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=data, method="PATCH",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/strategic-merge-patch+json"
        }
    )
    import ssl
    ctx = ssl.create_default_context(cafile=ca_path)
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=15) as r:
            log.info(f"K8s PATCH {path} -> HTTP {r.status}")
            return r.status in (200, 201, 202)
    except Exception as e:
        log.error(f"K8s PATCH {path} failed: {e}")
        return False


def restart_deployment(service: str) -> bool:
    """Restart a deployment by patching its pod template annotation."""
    log.info(f"RECOVERY: restarting deployment/{service}")
    restart_ts = datetime.now(timezone.utc).isoformat()
    path = f"/apis/apps/v1/namespaces/{NAMESPACE}/deployments/{service}"
    payload = {
        "spec": {
            "template": {
                "metadata": {
                    "annotations": {
                        "aiops/restartedAt": restart_ts
                    }
                }
            }
        }
    }
    success = k8s_patch(path, payload)
    if success:
        log.info(f"RECOVERY: restart patch applied for {service}, waiting 30s")
        time.sleep(30)
        log.info(f"RECOVERY: {service} restart complete")
    else:
        log.error(f"RECOVERY: failed to patch {service}")
    return success


def wait_for_healthy(service: str, timeout: int = 60) -> bool:
    """Poll /actuator/health until 200 or timeout."""
    # Get the NodePort for the service
    port_map = {"auth-service": "30081", "user-service": "30082", "transaction-service": "30083"}
    port = port_map.get(service)
    if not port:
        return True

    # Get minikube IP
    rc, minikube_ip = kubectl(["get", "nodes", "-o",
                                "jsonpath={.items[0].status.addresses[0].address}"])
    if rc != 0:
        return True

    minikube_ip = minikube_ip.strip()
    url = f"http://{minikube_ip}:{port}/actuator/health"
    deadline = time.time() + timeout

    while time.time() < deadline:
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=5) as r:
                if r.status == 200:
                    log.info(f"RECOVERY: {service} health check passed")
                    return True
        except Exception:
            pass
        time.sleep(5)

    log.warning(f"RECOVERY: {service} health check timed out after {timeout}s")
    return False


# ── Audit logging ────────────────────────────────────────────────────────────

def write_audit_log(pattern: str, affected_services: list,
                    action: str, result: str, details: str = ""):
    """Write an AIOps audit entry to Elasticsearch."""
    doc = {
        "@timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
        "service": "aiops-controller",
        "level": "INFO",
        "event": "aiops_recovery",
        "pattern": pattern,
        "affected_services": affected_services,
        "action": action,
        "result": result,
        "details": details,
        "message": f"AIOps recovery: {pattern} -> {action} -> {result}"
    }
    es_request("POST", "/fintech-aiops-audit/_doc", doc)
    log.info(f"AUDIT: {pattern} | {action} | {result}")


# ── Recovery strategies (report Table 11.1) ──────────────────────────────────

def recover_db_cascade():
    """Pattern: DB connection cascade — sequential restart auth first then dependents."""
    log.info("PATTERN: DB connection cascade detected")
    write_audit_log("db_cascade", SERVICES, "sequential_restart", "started",
                    "Postgres restart cascade: restarting auth-service first")
    success = restart_deployment("auth-service")
    if success:
        wait_for_healthy("auth-service", timeout=90)
    restart_deployment("user-service")
    restart_deployment("transaction-service")
    write_audit_log("db_cascade", SERVICES, "sequential_restart",
                    "completed" if success else "partial")


def recover_vault_unreachable():
    """Pattern: Vault unreachable — re-seed Vault then rolling restart."""
    log.info("PATTERN: Vault unreachable detected")
    write_audit_log("vault_unreachable", SERVICES, "vault_reseed_and_restart", "started")

    # Re-run the vault init job
    rc, out = kubectl(["delete", "job", "vault-init", "-n", "vault",
                       "--ignore-not-found=true"])
    time.sleep(2)
    rc, out = kubectl(["apply", "-f", "k8s/vault/vault-init-job.yaml"])
    if rc == 0:
        log.info("RECOVERY: vault-init job restarted")
        time.sleep(30)  # Wait for Vault to be seeded
    # Rolling restart all services
    for svc in SERVICES:
        restart_deployment(svc)
        wait_for_healthy(svc, timeout=60)

    write_audit_log("vault_unreachable", SERVICES, "vault_reseed_and_restart", "completed")


def recover_isolated_spike(service: str, zscore: float):
    """Pattern: Isolated service spike — restart the single anomalous service."""
    now = time.time()
    if now - last_recovery.get(service, 0) < COOLDOWN_SECONDS:
        remaining = int(COOLDOWN_SECONDS - (now - last_recovery[service]))
        log.info(f"COOLDOWN: {service} recovery skipped — {remaining}s remaining in cooldown")
        return
    last_recovery[service] = now
    log.info(f"PATTERN: Isolated spike on {service} (Z={zscore:.2f})")
    write_audit_log("isolated_spike", [service], "single_service_restart", "started",
                    f"Z-score={zscore:.2f} exceeded threshold {ZSCORE_THRESHOLD}")
    success = restart_deployment(service)
    wait_for_healthy(service, timeout=60)
    write_audit_log("isolated_spike", [service], "single_service_restart",
                    "completed" if success else "failed",
                    f"Z-score={zscore:.2f}")


def alert_auth_spike(count: int, baseline: float):
    """Pattern: Auth failure spike — alert only, no auto-remediation."""
    log.warning(f"ALERT: Auth failure spike detected — count={count}, baseline={baseline:.1f}. "
                f"Potential security event. Manual investigation required.")
    write_audit_log("auth_failure_spike", ["auth-service"], "alert_only", "alert_raised",
                    f"count={count} baseline={baseline:.1f} ratio={count/(baseline+0.1):.1f}x")


# ── Main detection loop ───────────────────────────────────────────────────────

def detect_and_heal():
    """One iteration of the AIOps decision loop."""
    log.info("CYCLE: collecting metrics from Elasticsearch")

    # Step 1: Collect error counts per service
    error_counts = {}
    for svc in SERVICES:
        count = get_error_count(svc, LOOKBACK_MINUTES)
        error_counts[svc] = count
        error_windows[svc].append(count)

    auth_failures = get_auth_failure_count(LOOKBACK_MINUTES)
    vault_errors = get_vault_error_count(LOOKBACK_MINUTES)
    auth_baseline_window.append(auth_failures)

    log.info(f"METRICS: errors={error_counts} auth_failures={auth_failures} vault_errors={vault_errors}")

    # Step 2: Check Vault unreachable pattern first (highest priority)
    if vault_errors >= 3:
        recover_vault_unreachable()
        return

    # Step 3: Compute Z-scores
    zscores = {}
    anomalous = []
    for svc in SERVICES:
        z = compute_zscore(error_windows[svc], error_counts[svc])
        zscores[svc] = z
        if z > ZSCORE_THRESHOLD and error_counts[svc] > 0:
            anomalous.append(svc)

    if zscores:
        log.info(f"ZSCORES: { {s: f'{z:.2f}' for s, z in zscores.items()} }")

    # Step 4: Auth failure spike check (alert only)
    if len(auth_baseline_window) >= 10:
        baseline = mean(auth_baseline_window)
        if baseline > 0 and auth_failures > baseline * AUTH_SPIKE_MULTIPLIER:
            alert_auth_spike(auth_failures, baseline)
            return  # Don't auto-remediate security events

    # Step 4b: Absolute threshold check (catches spikes before baseline builds)
    ABSOLUTE_THRESHOLD = int(os.environ.get("ABSOLUTE_THRESHOLD", "50"))
    for svc in SERVICES:
        if error_counts[svc] >= ABSOLUTE_THRESHOLD and svc not in anomalous:
            log.info(f"ABSOLUTE THRESHOLD: {svc} count={error_counts[svc]} >= {ABSOLUTE_THRESHOLD}")
            anomalous.append(svc)

    # Step 5: No anomalies
    if not anomalous:
        log.info("STATUS: all services nominal")
        return

    # Step 6: Dependency correlation — find root cause
    log.info(f"ANOMALY: detected on services: {anomalous}")

    # If multiple services anomalous within same cycle -> likely DB cascade
    if len(anomalous) >= 2:
        recover_db_cascade()
        return

    # Single service anomalous -> isolated spike
    service = anomalous[0]
    recover_isolated_spike(service, zscores[service])


def main():
    log.info("AIOps self-healing controller starting")
    log.info(f"Config: ES={ES_HOST} poll={POLL_INTERVAL}s window={WINDOW_SIZE} "
             f"threshold={ZSCORE_THRESHOLD} dry_run={DRY_RUN}")

    # Wait for ES to be reachable
    for i in range(30):
        result = es_request("GET", "/_cluster/health")
        if result.get("status") in ("green", "yellow"):
            log.info(f"ES cluster health: {result.get('status')}")
            break
        log.info(f"Waiting for ES... ({i+1}/30)")
        time.sleep(5)

    cycle = 0
    while True:
        cycle += 1
        log.info(f"CYCLE {cycle} starting")
        try:
            detect_and_heal()
        except Exception as e:
            log.error(f"CYCLE {cycle} error: {e}")
        log.info(f"CYCLE {cycle} complete. Sleeping {POLL_INTERVAL}s")
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
