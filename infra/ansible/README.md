# Ansible — Intelligent FinTech Platform

Infrastructure as Code (IaC) for the project. Replaces manual install steps with
a single command:

```bash
cd infra/ansible
ansible-playbook -i inventory/hosts.yml playbooks/setup.yml --ask-become-pass
```

## Goal

If the host laptop dies, this Ansible playbook rebuilds the entire local
development environment on a fresh Ubuntu 24.04 host in ~20 minutes.

## Structure
infra/ansible/
├── ansible.cfg              Project-local config (overrides /etc/ansible)
├── inventory/hosts.yml      Defines target hosts (localhost + vagrant)
├── group_vars/all.yml       Shared variables across all hosts
├── playbooks/setup.yml      Top-level orchestration playbook
└── roles/                   Modular roles (one per concern)
└── common/              Base system: apt update, base packages, timezone

## Phase status

- [x] Phase 5.1 — Directory + inventory + common role
- [ ] Phase 5.2 — docker role
- [ ] Phase 5.3 — kubernetes role (kubectl + minikube)
- [ ] Phase 5.4 — java_maven role
- [ ] Phase 5.5 — jenkins role
- [ ] Phase 5.6 — devsecops_tools role
- [ ] Phase 5.7 — app_deploy role + ansible-vault secrets
- [ ] Phase 5.8 — full setup.yml orchestration
- [ ] Phase 5.9 — Vagrant VM test
- [ ] Phase 5.10 — Decisions log + commit + tag

## Idempotency

All roles MUST be idempotent. Running the playbook twice in a row should result
in zero "changed" tasks on the second run.

## Secrets

K8s secrets (POSTGRES_PASSWORD, DB_PASSWORD, JWT_SECRET) are stored encrypted in
`group_vars/vault.yml` via `ansible-vault`. See Phase 5.7 for details.
