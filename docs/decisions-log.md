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

## Day 4 — Complete (Jenkins CI/CD Pipeline)

End-to-end automated pipeline from git push to verified K8s deployment.
All 8 stages run on `jenkins` user, native (not containerized).

**Pipeline architecture** (Jenkinsfile at repo root):
1. Checkout & Inspect — git info, workspace listing
2. Secrets Scan (Gitleaks) — fails on any committed secret
3. Build & Unit Test — parallel mvnw clean package for all 3 services, JUnit publish
4. Build Docker Images — parallel, double-tag :BUILD_NUMBER + :latest
5. Image Vulnerability Scan (Trivy) — HIGH reported, CRITICAL blocks
6. Push to Docker Hub — vamsi124/fintech-*-service:N + :latest
7. Deploy to K8s — kubectl rollout restart + status with 180s timeout
8. Smoke Test — settling delay + retry health checks + 4 functional contract tests

**4-build maturity arc:**
- Build #3: caught 3 CRITICAL CVEs in Spring Boot 3.3.5 transitive deps
- Build #4: caught race between K8s rollout-status (returns at readinessProbe pass)
  and Spring Boot 3.5.9 fully serving traffic. Added 20s settling delay + per-port retry.
- Build #5: caught bash-specific ${VAR:start:length} substring failing in Jenkins
  /bin/sh (dash). Replaced with POSIX $(echo "$VAR" | cut -c1-30).
- Build #6: All 8 stages green. End-to-end success.

**Jenkins ↔ K8s wiring:**
- /etc/sudoers.d/jenkins-k8s allows jenkins user to invoke kubectl/minikube/docker
  as the development user vamsi-ganagalla with NOPASSWD (mode 0440)
- Critical flag: sudo -u vamsi-ganagalla -H kubectl ... (the -H sets HOME, without
  which kubectl couldn't find kubeconfig and defaulted to localhost:8080 = Jenkins UI)

**Docker Hub credentials:**
- Jenkins credential ID: dockerhub-credentials (username vamsi124, token with R+W+D)
- Referenced in Jenkinsfile via withCredentials wrapper around Stage 6


## Day 5 — Complete (Ansible Infrastructure as Code)

End-to-end Ansible automation that provisions a complete dev environment
(Docker, Kubernetes, Jenkins, security scanners) and deploys the FinTech
microservices stack to local minikube. **One command rebuilds the entire
environment in 90 seconds on a warm laptop, ~20 min on a fresh Ubuntu host.**

### Roles built (7 total, all idempotent)

| Role | Responsibility |
|------|---------------|
| common | OS verification, base packages, timezone (Asia/Kolkata for local dev) |
| docker | Docker CE from upstream apt repo + daemon.json log rotation + live-restore |
| kubernetes | kubectl via apt + minikube binary (no cluster start — operational choice) |
| java_maven | OpenJDK 17 headless + Maven (system) |
| jenkins | Jenkins LTS + sudoers wiring for K8s deploy |
| devsecops_tools | Gitleaks 8.21.2 + Trivy 0.70.0 (versions pinned to match Jenkinsfile) |
| app_deploy | Templated K8s manifest deployment with vault-decrypted secrets |

### Architectural decisions

**Decision: Hybrid host strategy (localhost playbook + VM proof path)**
The playbook targets `localhost` via `ansible_connection: local`. Inventory
includes a commented `vagrant` group for future fresh-VM testing (Phase 5.9
deferred). On localhost, most tasks become idempotent no-ops (tools already
installed); on a fresh VM, every task fires for full provisioning.

**Decision: Directory-based group_vars (`group_vars/all/`)**
Ansible's group_vars auto-discovery only loads files matching group names OR
files inside group-named subdirectories. Single-file pattern (`group_vars/all.yml`)
works for plaintext-only setups; the moment vault is added, the directory pattern
(`group_vars/all/main.yml` + `group_vars/all/vault.yml`) is required. Restructured
from single-file to directory in Phase 5.7a after vault discovery failures.

**Decision: ansible-vault for secrets (3 secrets encrypted)**
- vault_postgres_password, vault_db_password, vault_jwt_secret
- Encrypted file (`group_vars/all/vault.yml`) committed to git
- Decryption password in `.vault-password` (mode 0600, gitignored)
- `.vault-password.example` template committed for repo cloners
- Convention-bridge mapping in `main.yml` lets roles reference public names
  (`postgres_password`) without vault awareness

**Decision: Template K8s secrets to /tmp, clean up after apply**
The `app_deploy` role renders the K8s Secret manifest from vault values to
`/tmp/fintech-secret-rendered.yaml`, applies it via kubectl, then deletes the
plaintext file. Trade-off: temporary plaintext on disk for ~5 seconds vs.
leaving it in the repo tree where `git stash` or `git clean` might expose it.

**Decision: jenkins role uses `state: started`, not `restarted`**
Critical safety: never disrupt running Jenkins. Our role manages apt repo,
package install, sudoers, and service-enabled state but explicitly does NOT
touch `/var/lib/jenkins/` (where job configs and build history live).

**Decision: become_user for kubectl invocations**
Ansible's native `become_user` is the proper idiom for running tasks as a
different user. Replaces the `sudo -u vamsi-ganagalla -H kubectl ...` pattern
from Jenkinsfile. Both approaches set HOME correctly so kubectl finds kubeconfig.

### Bug-fix log (lessons from real failures during Day 5)

1. **`stdout_callback = yaml` deprecated** (Phase 5.1) — replaced with
   `stdout_callback = default` + `result_format = yaml`. Newer Ansible
   versions removed the community.general.yaml callback.

2. **Task name templating limitation** (Phase 5.1) — Ansible 2.20+ renders
   task `name:` fields with a narrower variable scope than module args.
   Lesson: keep task names as literal strings, not data-derived.

3. **group_vars location** (Phase 5.1) — when playbook is in a subdirectory,
   Ansible looks for `group_vars/` next to the playbook, NOT next to the
   inventory. Solved via symlink `playbooks/group_vars -> ../group_vars`.

4. **Apt signed-by requires binary keyring** (Phase 5.2, 5.3, 5.5) — Docker,
   Kubernetes, and Jenkins all serve their GPG keys in ASCII-armored format
   from upstream. The modern `signed-by=` apt directive requires binary
   (dearmored) keyrings. Two-step pattern: download armored → gpg --dearmor
   to target path with `creates:` for idempotency.

5. **Jenkins upstream key state** (Phase 5.5) — the current Jenkins LTS
   signing key (`63667E...`) expired 2026-03-26, with a newer key
   (`7198F4B714ABFC68`) referenced in repo metadata but not published at
   the expected URL. Role marks apt repo addition as `ignore_errors: true`;
   on Vamsi's machine Jenkins 2.541.2 was already installed pre-Day-5.
   Deferred: vendored key file in `roles/jenkins/files/jenkins.gpg` for
   fresh VM provisioning (Phase 5.9).

6. **Vault file in subdirectory not auto-discovered** (Phase 5.7a) — see
   directory-based group_vars decision above. Single-file pattern silently
   ignored `vault.yml`. Restructure to `all/` subdir resolved.

7. **Check-mode limitations** (Phase 5.6, 5.7b) — `--check` mode cannot
   actually create state, so chains where one task creates a dir and the
   next task writes into it will fail in check mode. Real runs work.
   Accepted as Ansible limitation; documented in role.

### Idempotency

| Role | Strict (changed=0) | Notes |
|------|-------------------|-------|
| common | ✅ | |
| docker | ✅ | |
| kubernetes | ✅ | |
| java_maven | ✅ | |
| jenkins | ✅ | apt repo best-effort |
| devsecops_tools | ✅ | |
| app_deploy | ⚠️ Loose (changed=5) | Template renders + apply tasks always report changed; cluster state IS idempotent |

### Verification metrics

Full playbook run, end-to-end:
- 94 tasks executed
- 0 failed
- 5 changed (app_deploy template + apply tasks)
- 11 skipped (conditional install tasks where state already correct)
- Runtime: 1m30s on warm laptop

Functional verification: All 3 services healthy at NodePorts after
`ansible-playbook` finishes. Register + login + cross-pod JWT all functional.

### Known issues / deferred work

1. Jenkins apt repo (Phase 5.5) — upstream key in transition, marked best-effort
2. User-service `/users/me` returns 500 — pre-existing cross-service user lookup
   bug (auth-service writes to fintech_auth DB, user-service reads from
   fintech_users). Deferred to Day 6 (events) or Day 7 (Vault).
3. app_deploy idempotency reporting — functionally idempotent, but Ansible
   reports `changed=5` due to always-renders template and apply output parsing.
   Improvement: `kubectl diff` before `apply`.
4. Vagrant VM proof (Phase 5.9) — deferred. Playbook is verified working on
   localhost; fresh-VM test postponed to Day 9 polish if time allows.

### Future work referenced from Day 5

- **Day 6**: ELK + JSON logging will provide the observability needed to debug
  app-level bugs like the /users/me 500 systematically.
- **Day 7**: HashiCorp Vault will replace ansible-vault for runtime secret
  injection, plus add PKI-issued RSA keypairs for RS256 asymmetric JWT.
- **Day 8**: AIOps will detect the pod-restart cascade pattern observed when
  docker daemon restarts (seen in Phases 5.2 and 5.3), and accelerate recovery
  from ~2 min (K8s exponential backoff) to ~20 sec (dependency-aware restart).
