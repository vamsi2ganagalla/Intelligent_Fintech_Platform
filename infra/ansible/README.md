# Ansible — Intelligent FinTech Platform

Infrastructure as Code (IaC) for the Intelligent FinTech Microservices Platform.
Provisions a complete development environment (Docker, Kubernetes, Jenkins,
security scanners) and deploys the application stack to local minikube.

## Disaster recovery goal

If the development laptop dies, this playbook rebuilds the entire local
development environment on a fresh Ubuntu 24.04 host:

```bash
git clone https://github.com/vamsi2ganagalla/Intelligent_Fintech_Platform.git
cd Intelligent_Fintech_Platform/infra/ansible
cp .vault-password.example .vault-password
# Edit .vault-password and put the project vault password in it
chmod 0600 .vault-password
ansible-playbook playbooks/setup.yml --ask-become-pass
```

Target runtime: ~20 minutes on a fresh machine, ~3 minutes on a warm one.

## Directory structure
infra/ansible/
├── ansible.cfg               Project-local config
├── inventory/hosts.yml       Target machines (localhost + commented Vagrant)
├── group_vars/all/
│   ├── main.yml              Shared variables (versions, sizing, mappings)
│   └── vault.yml             ansible-vault encrypted secrets
├── playbooks/
│   ├── group_vars            Symlink to ../group_vars (Ansible discovery quirk)
│   └── setup.yml             Master orchestration playbook
├── roles/
│   ├── common/               OS verification, base packages, timezone
│   ├── docker/               Docker CE + daemon.json with log rotation
│   ├── kubernetes/           kubectl (apt) + minikube (binary)
│   ├── java_maven/           OpenJDK 17 + Maven (system)
│   ├── jenkins/              Jenkins LTS + sudoers wiring
│   ├── devsecops_tools/      Gitleaks 8.21.2 + Trivy 0.70.0 (version-pinned)
│   └── app_deploy/           Templated K8s manifests + cluster apply
├── .vault-password           Master decryption key (gitignored, 0600)
├── .vault-password.example   Template for cloners
└── README.md                 This file

## Usage

### Full setup (everything from scratch)

```bash
ansible-playbook playbooks/setup.yml --ask-become-pass
```

### Run a specific role

```bash
# Just docker
ansible-playbook playbooks/setup.yml --ask-become-pass --tags docker

# Just deploy the app
ansible-playbook playbooks/setup.yml --ask-become-pass --tags deploy
```

Available tags: `common`, `base`, `docker`, `kubernetes`, `k8s`, `java`, `maven`,
`jenkins`, `ci`, `devsecops`, `security`, `deploy`, `app`.

### Dry-run (preview changes without applying)

```bash
ansible-playbook playbooks/setup.yml --check --diff --ask-become-pass
```

Note: Some tasks (particularly app_deploy) skip in check mode because they
need to actually invoke kubectl.

### Editing vault secrets

```bash
ansible-vault edit group_vars/all/vault.yml
```

Opens an editor with decrypted contents. Save+exit re-encrypts automatically.

## Idempotency

All roles are designed to be idempotent. Running the playbook twice in a row
should produce minimal `changed` reports on the second run.

| Role | Idempotent | Notes |
|------|-----------|-------|
| common | Strict (`changed=0`) | |
| docker | Strict (`changed=0`) | |
| kubernetes | Strict (`changed=0`) | |
| java_maven | Strict (`changed=0`) | |
| jenkins | Strict (`changed=0`) | apt repo marked best-effort due to upstream key state |
| devsecops_tools | Strict (`changed=0`) | |
| app_deploy | Loose (`changed=5`) | Template always renders; kubectl apply reports differently. Cluster state IS idempotent. |

## Secrets management

Three secrets live in `group_vars/all/vault.yml` (encrypted, committed):

- `vault_postgres_password` — DB password (mapped to `postgres_password`)
- `vault_db_password` — Application DB password (mapped to `db_password`)
- `vault_jwt_secret` — JWT signing key (mapped to `jwt_secret`)

Day 7 (Vault role) will replace these with dynamic injection from
HashiCorp Vault, including PKI-issued RSA keypairs for asymmetric JWT (RS256).

## Phase status

- [x] Phase 5.1 — Directory + inventory + common role
- [x] Phase 5.2 — docker role
- [x] Phase 5.3 — kubernetes role (kubectl + minikube)
- [x] Phase 5.4 — java_maven role
- [x] Phase 5.5 — jenkins role (with deferred upstream key issue)
- [x] Phase 5.6 — devsecops_tools role (Gitleaks + Trivy)
- [x] Phase 5.7a — ansible-vault secrets setup
- [x] Phase 5.7b — app_deploy role + templated manifests
- [x] Phase 5.8 — orchestration verification + documentation
- [ ] Phase 5.9 — Vagrant VM proof of disaster-recovery (optional)
- [ ] Phase 5.10 — Decisions log + commit + tag day-5-complete

## Known issues / deferred work

1. **Jenkins apt repo (Phase 5.5)** — Upstream Jenkins LTS key state is in transition;
   apt repo addition marked `ignore_errors: true`. Jenkins is already installed on
   Vamsi's dev machine. For fresh VM (Phase 5.9), need vendored key file.

2. **User-service /users/me returns 500** — Cross-service user lookup bug (auth-service
   creates user in fintech_auth DB; user-service queries fintech_users). Existed
   before Phase 5.7b. Deferred to Day 6 (logging) or Day 7 (Vault).

3. **app_deploy idempotency reporting** — Reports `changed` on re-runs even when
   cluster state is unchanged. Functional idempotency holds (no actual changes).
   Improvement: use `kubectl diff` before `apply`.

4. **Maven version mismatch** — System Maven 3.8.7 (Ubuntu apt) vs Wrapper Maven 3.9.14
   (per-project). System Maven is convenience only; actual builds use `./mvnw`.

5. **Timezone choice** — Currently Asia/Kolkata (local dev convenience). Production
   deployments would override via inventory-specific group_vars to UTC.

## References

- Ansible docs: https://docs.ansible.com/ansible/latest/
- ansible-vault guide: https://docs.ansible.com/ansible/latest/cli/ansible-vault.html
- group_vars layout: https://docs.ansible.com/ansible/latest/inventory_guide/intro_inventory.html#organizing-host-and-group-variables
