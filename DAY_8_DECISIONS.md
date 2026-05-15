# Day 8 — HPA + AIOps Self-Healing: Decisions & Outcomes

## HPA (Horizontal Pod Autoscaler)

### Setup
- Enabled minikube metrics-server addon
- Deployed autoscaling/v2 HPA for all 3 services
- CPU target: 70%, Memory target: 80%, min 1 / max 5 replicas

### Observed Metrics at Rest
- auth-service:        cpu 3%/70%,  memory 79%/80%
- user-service:        cpu 2%/70%,  memory 76%/80%
- transaction-service: cpu 4%/70%,  memory 75%/80%

Memory sits at 75-79% — close to threshold, realistic for
Spring Boot JVM baseline. CPU headroom is large as expected
at idle. Under transaction load, CPU would trigger scale-out.

---

## AIOps Self-Healing Controller

### Architecture
- Python 3.11 controller running as K8s Deployment in `aiops` namespace
- ServiceAccount with ClusterRole: patch deployments, get/list pods
- Polls Elasticsearch every 30 seconds via cluster-internal DNS
- Writes audit log back to Elasticsearch at fintech-aiops-audit index
- Uses Kubernetes in-cluster API (service account token) for remediation
  — no kubectl binary required

### Detection Logic
Two-layer detection matching report Chapter 11:
1. Z-score (rolling 50-sample window, threshold 1.5)
2. Absolute threshold (count >= 50 per 2-minute window)
   — catches spikes before Z-score baseline builds

### Verified End-to-End (evidence from logs)

Anomaly injection: 100 bad login attempts -> 100 WARN logs in ES

Cycle 3 detection:
  ABSOLUTE THRESHOLD: auth-service count=100 >= 50
  ANOMALY: detected on services: ['auth-service']
  PATTERN: Isolated spike on auth-service

Recovery:
  K8s PATCH /apis/apps/v1/.../deployments/auth-service -> HTTP 200
  RECOVERY: auth-service restart complete
  AUDIT: isolated_spike | single_service_restart | completed

Recovery confirmed:
  Cycle 6: errors={'auth-service': 0} -> STATUS: all services nominal
  auth-service health: {"status":"UP"}

### Detection Patterns Implemented (report Table 11.1)
| Pattern              | Trigger                        | Action                    |
|----------------------|--------------------------------|---------------------------|
| Isolated spike       | count >= 50 OR Z > 1.5         | Restart affected service  |
| DB cascade           | 2+ services anomalous          | Sequential restart        |
| Vault unreachable    | vault_errors >= 3              | Re-seed job + restart all |
| Auth failure spike   | 5x baseline auth failures      | Alert only (no restart)   |

### Key Decisions

**K8s API over kubectl**: python:3.11-slim has no kubectl binary.
Used in-cluster service account token to PATCH deployment template
annotation (aiops/restartedAt) — triggers rolling restart without
kubectl. Cleaner and faster.

**match vs term queries**: Elasticsearch mapped level/service fields
as text type (not keyword). term queries return 0. match queries
work correctly. service.keyword used for exact service name matching.

**Absolute threshold alongside Z-score**: Z-score needs baseline
history to fire. Absolute threshold (>= 50 errors in 2 min) fires
immediately on first spike — useful for demo and for genuine sudden
failures with no prior history.

**Vault error false positive fix**: Original query matched "Vault"
as a substring, catching unrelated messages. Replaced with
match_phrase on specific error strings only.

### Deferred Tech Debt
- Cool-down period: controller currently restarts on every cycle
  where threshold is exceeded. Production needs a 5-minute
  cool-down after recovery to avoid restart loops.
- LSTM anomaly detection: replace Z-score + absolute threshold
  with trained time-series model (Future Enhancements section).
- Alert routing: auth failure spike currently logs only.
  Production would route to PagerDuty/Slack.
