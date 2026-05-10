# Kubernetes Manifests

Local Kubernetes (minikube) deployment for the Intelligent FinTech Platform.

The `docker-compose.yml` at the project root is the reference for the same workload running outside K8s; this directory contains the K8s translation.

## Prerequisites

| Tool | Tested version | Notes |
|------|----------------|-------|
| minikube | v1.38.1 | k8s 1.35.x bundled |
| kubectl | v1.35+ | Client-only; minikube provides server |
| Docker | 20.10+ | minikube uses `--driver=docker` |
| 4GB free RAM | — | minikube allocation |

```bash
# One-time minikube config (persists across cluster recreates)
minikube config set memory 4096
minikube config set cpus 2
```

## Directory Layout
infra/k8s/
├── 10-config/
│   ├── configmap.yaml          # Non-secret config: DB URLs, JWT exp, usernames
│   ├── secret.yaml             # Sensitive: passwords, JWT signing key (GITIGNORED)
│   └── secret.yaml.example     # Template for the above
├── 20-postgres/
│   ├── init-db-configmap.yaml  # Bootstrap script: creates 3 logical DBs
│   ├── statefulset.yaml        # Postgres StatefulSet + volumeClaimTemplate (2Gi PVC)
│   └── service.yaml            # ClusterIP postgres:5432 (internal only)
└── 30-services/
├── auth-service.yaml       # Deployment + NodePort 30081
├── user-service.yaml       # Deployment + NodePort 30082
└── transaction-service.yaml # Deployment + NodePort 30083

The numeric prefixes preserve apply order when using `kubectl apply -f infra/k8s/ -R`.

## First-Time Setup

```bash
# 1. Start cluster
minikube start

# 2. Confirm namespace context
kubectl config set-context --current --namespace=default

# 3. Create secret.yaml from template (NOT in git)
cp infra/k8s/10-config/secret.yaml.example infra/k8s/10-config/secret.yaml
# Edit secret.yaml — replace CHANGE_ME values with real secrets

# 4. CRITICAL: rewire shell to minikube's docker daemon
eval $(minikube docker-env)

# 5. Build all 3 images INSIDE minikube
cd services/auth-service && docker build -t fintech-auth-service:latest . && cd -
cd services/user-service && docker build -t fintech-user-service:latest . && cd -
cd services/transaction-service && docker build -t fintech-transaction-service:latest . && cd -

# 6. Verify images are visible to minikube
docker images | grep fintech    # should list 3 images, ~323MB each

# 7. Apply manifests in order
kubectl apply -f infra/k8s/10-config/
kubectl apply -f infra/k8s/20-postgres/
# Wait for postgres to be Ready BEFORE applying services (see "Verify Postgres" below)
kubectl apply -f infra/k8s/30-services/

# 8. Confirm all 4 pods Running 1/1
kubectl get pods
```

## Verify Postgres Before Applying Services

```bash
kubectl wait --for=condition=ready pod -l app=postgres --timeout=120s
```

This blocks until `postgres-0` is Ready. Skipping this leads to brittle service startup: pods will start, fail to connect, restart in CrashLoopBackOff for 30-60 seconds before stabilizing.

## Smoke Test

```bash
MINIKUBE_IP=$(minikube ip)

# Health checks (expect all 200)
for port in 30081 30082 30083; do
  echo -n "Port $port: "
  curl -s -o /dev/null -w "%{http_code}\n" http://$MINIKUBE_IP:$port/actuator/health
done

# Register
curl -s -X POST http://$MINIKUBE_IP:30081/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"smoke@test.com","password":"TestPass123!"}'

# Login + capture token
TOKEN=$(curl -s -X POST http://$MINIKUBE_IP:30081/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"smoke@test.com","password":"TestPass123!"}' \
  | grep -oP '"accessToken":"[^"]+"' | cut -d'"' -f4)

# Cross-pod JWT validation
curl -s -o /dev/null -w "user-service: %{http_code}\n" \
  -X GET http://$MINIKUBE_IP:30082/api/v1/users/profile \
  -H "Authorization: Bearer $TOKEN"
curl -s -o /dev/null -w "transaction-service: %{http_code}\n" \
  -X GET http://$MINIKUBE_IP:30083/api/v1/transactions \
  -H "Authorization: Bearer $TOKEN"
```

Expected output: all 200.

## Service-to-Port Map

| Service | NodePort | ClusterIP port | DNS name (in-cluster) |
|---------|----------|----------------|----------------------|
| auth-service | 30081 | 8081 | `auth-service:8081` |
| user-service | 30082 | 8082 | `user-service:8082` |
| transaction-service | 30083 | 8083 | `transaction-service:8083` |
| postgres | (none) | 5432 | `postgres:5432` |

Postgres is intentionally NOT exposed via NodePort — defense in depth. Use `kubectl exec postgres-0 -- psql ...` for direct DB access during debugging.

## Common Operations

```bash
# Tail logs of a service
kubectl logs -f -l app=auth-service --tail=50

# Restart a service (rolls a new pod, old one drains)
kubectl rollout restart deployment auth-service

# Scale a service (also see Day 8 HPA work for automatic scaling)
kubectl scale deployment auth-service --replicas=2

# View all resources tagged as part of this project
kubectl get all -l app.kubernetes.io/part-of=fintech-platform

# Tear down everything except the cluster itself
kubectl delete -f infra/k8s/30-services/
kubectl delete -f infra/k8s/20-postgres/
kubectl delete -f infra/k8s/10-config/
kubectl delete pvc postgres-data-postgres-0   # PVC NOT auto-deleted with StatefulSet

# Nuclear: wipe entire cluster (preserves minikube install)
minikube delete
```

## Known Gotchas

### `eval $(minikube docker-env)` is shell-scoped

The eval rewires `docker` in the current shell only. Closing the terminal reverts. If you build images in a fresh shell without re-running the eval, your changes go to the host docker daemon, not minikube's, and Kubernetes never sees them.

**Diagnostic when this happens:** pod stays in `ContainerCreating` or shows `ErrImageNeverPull`. Run `eval $(minikube docker-env)`, rebuild, `kubectl rollout restart deployment <name>`.

### `imagePullPolicy: Never` on all 3 services

Tells K8s "use only locally-cached images." Required because we don't push to a registry. Side effect: K8s fails fast (rather than retrying pulls forever) if image is missing. This is the right tradeoff for local dev.

### Postgres readiness probe must specify both `-U` and `-d`

`pg_isready` defaults to OS user (root inside container) and a DB matching the username. Both defaults fail in our setup. Probe explicitly uses `pg_isready -U fintech_user -d postgres`.

### PVC survives StatefulSet delete

Deleting the StatefulSet does NOT delete `postgres-data-postgres-0`. This is intentional — protects against accidental data loss. To force fresh init-db.sh execution, manually `kubectl delete pvc postgres-data-postgres-0` AFTER deleting the StatefulSet.

### NodePort range is 30000-32767

K8s reserves this range. Choosing 30081/30082/30083 to mirror service ports for memorability.

## Architecture Decisions for Phase 3

Detailed decision records (database-per-service, JWT secret strategy, image strategy, ConfigMap/Secret split) are tracked in `docs/decisions-log.md` for now and will be polished into the project README at end of Day 10.
