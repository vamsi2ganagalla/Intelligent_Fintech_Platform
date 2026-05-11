# Decisions Log (Working Notes)

Running log of decisions as they're made. Polish into ADR format on Day 10.

## Day 2

- **Logical DBs in shared Postgres** (not 3 containers): saves 16GB laptop RAM
- **JWT HS256 shared secret** (not RS256): simpler now, migrate to Vault PKI on Day 7
- **Lazy profile creation in user-service**: avoids sync coupling auth→user
- **JWT sub = email** (not UUID): simpler, but breaks on email change
- **ddl-auto: update** (not Flyway): rapid iteration; Flyway is Tier 2
- **Jackson fail-on-unknown-properties: true**: defense-in-depth, security improvement on Day 2
- **Postgres 5432 exposed to host**: dev convenience; remove for non-dev

## Day 3

- **Minikube over k3s/kind**: leveraged existing familiarity over theoretical optimality; reduced concurrent unknowns
- **Postgres as StatefulSet** (not Deployment): stable identity + persistent volume claim template; correct for stateful workloads
- **Single Postgres replica with PVC**: dev simplicity; HA replication is Tier 2
- **ConfigMap + Secret split** (not single mixed Secret): non-secret values benefit from `kubectl describe` visibility; secrets isolated for future RBAC scoping
- **DB_USERNAME in ConfigMap, DB_PASSWORD in Secret**: rotating password shouldn't require touching username
- **`stringData` over `data` for Secret**: human-authored, K8s auto-encodes; not encryption (Vault on Day 7)
- **`imagePullPolicy: Never`** with locally-built images: no registry needed for local dev; fails loudly if image missing
- **`eval $(minikube docker-env)` build pattern**: build directly into minikube's daemon; avoids `minikube image load` step but is shell-session-scoped (documented gotcha)
- **NodePort 30081/30082/30083** mirroring service ports: memorability over convention
- **Postgres NOT exposed via NodePort**: defense in depth — DB unreachable from outside cluster
- **`pg_isready -U fintech_user -d postgres`** (fully explicit): defaults fail in containers (OS user = root, db = matching username)
- **Liveness `initialDelaySeconds: 60`**: budget for image pull + JVM warmup + first DB connection on cold start
- **`maxUnavailable: 0`** in rolling updates: zero-downtime deploys when scaled beyond 1 replica (Day 8)

## Day 4 — CVE Remediation

When Trivy stage in build #3 found 3 CRITICAL CVEs in Spring Boot transitive
dependencies, we did NOT suppress with `.trivyignore`. Instead:

1. **Upgraded Spring Boot 3.3.5 → 3.5.9** (3.3.x reached EOL June 2025;
   staying on EOL framework = not getting security patches anymore).
   Resolved CVE-2025-24813 (Tomcat partial PUT RCE) automatically.

2. **Pinned newer transitive versions** via documented override properties:
   - `<tomcat.version>10.1.53</tomcat.version>` fixes CVE-2026-29145
   - `<spring-security.version>6.5.9</spring-security.version>` fixes CVE-2026-22732

3. **Verified post-fix**: Trivy rescan reports 0 CRITICAL across both OS and JAR layers.

No suppressions used. Real fix. This is the canonical DevSecOps remediation
flow: find -> triage -> upgrade -> verify -> document.
