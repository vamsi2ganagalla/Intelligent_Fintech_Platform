# Day 7 — Vault + RS256 Asymmetric JWT: Decisions & Outcomes

## Security Story

### Problem with Day 6 (HS256)
- auth-service, user-service, and transaction-service all shared `JWT_SECRET`
- One compromised pod = attacker can forge tokens as any user
- Secret lived in K8s ConfigMap / env vars — visible to anyone with `kubectl describe`

### Solution (RS256 + Vault)
- auth-service holds RSA **private key** (signs tokens) — fetched from Vault at boot
- user-service + transaction-service hold RSA **public key** only (verify tokens)
- Compromising a verifier service yields **zero forgery capability**
- Secret never in git, never in ConfigMap, never on disk

---

## Phase Outcomes

| Phase | What | Outcome |
|-------|------|---------|
| 7.1 | Vault 1.21.4 dev mode on minikube | Running, UI at :30200 |
| 7.2 | RSA-2048 keypair → Vault KV v2 | `secret/fintech/jwt`, kid=fintech-rs256-2026-05-15 |
| 7.3 | AppRole auth, scoped policies, K8s Secrets | Both roles login OK, read JWT secret |
| 7.4 | Spring Cloud BOM 2025.0.0 + vault-config dep | All 3 poms + YAMLs patched, mvnw compile EXIT:0 |
| 7.5 | JwtUtil RS256 rewrite | auth signs RSAPrivateKey, user/txn verify RSAPublicKey only |
| 7.6 | K8s manifests: Vault env vars mounted | VAULT_ROLE_ID/SECRET_ID from K8s Secrets |
| 7.7 | End-to-end verification | JWT header alg:RS256 kid confirmed, user-service 200, txn 200, tampered→401 |
| 7.8 | Vault re-seed Job (python:3.11-slim) | Self-healing across minikube restarts |

---

## Key Decisions

### Vault dev mode (Path A)
Chose dev mode over file-storage backend. Rationale: security architecture
point (RS256 + AppRole separation) is identical either way. Dev mode is
faster and less fragile for demo. Phase 7.8 init-Job compensates for
state loss on restart. Production would use Raft storage + auto-unseal
(deferred tech debt).

### Vault image: 1.21.4 not 2.0.0
Vault 2.0 released April 2026 but only 3 weeks old at time of implementation.
1.21.4 has more Spring Cloud Vault integration examples and lower risk of
breaking changes. Docker Hub tags ≠ GitHub release tags — 1.20.7 listed
in changelog but absent from Docker Hub (Mistake #16 logged).

### Spring Cloud 2025.0.0 (Northfields)
Matches Spring Boot 3.5.x. Uses `spring.config.import: vault://` (modern
Config Data API). Legacy bootstrap.yml approach avoided.

### jjwt 0.11.5 — no upgrade
RS256 is fully supported in 0.11.5 via `SignatureAlgorithm.RS256`.
Upgrading to 0.12.x would require API changes across all three services
for no benefit. Stayed on 0.11.5.

### kid in JWT header
`kid: fintech-rs256-2026-05-15` embedded in every token header now.
Future key rotation = upload new key with new kid. No code change needed.
Schema-as-contract for Day 8+.

### Vault init Job: python:3.11-slim not hashicorp/vault
hashicorp/vault:1.21.4 is a minimal image with no Python runtime.
Job runs as independent pod (not inside Vault pod) so VAULT_ADDR must
use cluster DNS: `http://vault.vault.svc.cluster.local:8200`, not
`127.0.0.1:8200`.

---

## Deferred Tech Debt

- **Vault Transit engine**: verifier services should call `vault transit verify`
  rather than holding public key material. Physical key separation.
- **AppRole response-wrapping**: secret_id should be one-shot, delivered via
  Vault Agent Injector. Current setup uses unlimited-use secret_id (dev shortcut).
- **Raft storage + auto-unseal**: production Vault persistence.
- **Key rotation automation**: kid-based rotation is architected; automation
  is Day 8+.

---

## Verification Evidence
JWT header decoded:
{
"kid": "fintech-rs256-2026-05-15",
"alg": "RS256"
}
user-service /api/v1/users/profile → HTTP 200
transaction-service /api/v1/transactions → HTTP 200 (id:2, status:COMPLETED)
tampered token → HTTP 401
