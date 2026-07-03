# Tasks: TFM Production Rollout (tfm-prod-rollout)

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 800-1200 (IaC 3 layers + compose + nginx + cloud-init + runbook) |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | 3 chained PRs: persistent+edge → stack compose+nginx → stack VM+secrets |
| Delivery strategy | ask-on-risk |
| Chain strategy | feature-branch-chain |

Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: feature-branch-chain
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | Persistent layer (IP + volume + private network + DNS) **+ edge VM** (always-on nginx) | PR 1 | The fixed infra: floating IP, encrypted volume, private network, and the nginx edge that holds the IP. Lands the dangerous volume work in isolation. |
| 2 | Stack compose + nginx routing config (edge/backend split, hardening) | PR 2 | The stack the ephemeral VM runs + the edge nginx conf pointing at the stack private IP. Testable locally before any stack VM exists. |
| 3 | Ephemeral stack VM + SOPS secrets + cloud-init + runbook | PR 3 | Wires 1+2: no-public-IP stack VM on the private network, secret decrypt, up/down runbook. |

> Rationale: the persistent+edge fixed infra (PR 1) is the safety-critical, long-lived part —
> land and verify it alone. PR 2 is pure config, testable on a workstation. PR 3 is the
> ephemeral glue that depends on both.

### Chain layout (feature-branch-chain)

A tracker branch (e.g. `feature/tfm-prod-rollout`) accumulates final integration. Only the
tracker merges to `main`, atomically, once all three PRs are approved.

| PR | Branch | Targets | Contents |
|----|--------|---------|----------|
| PR 1 | `tfm-prod/persistent-edge` | tracker branch | Phase 1 (persistent + edge). |
| PR 2 | `tfm-prod/stack-compose` | PR 1 branch | Phase 2 (stack compose + edge nginx conf). |
| PR 3 | `tfm-prod/stack-vm` | PR 2 branch | Phase 3 (stack VM + secrets + cloud-init + runbook). |

Review diffs stay focused (each PR shows only its layer); `main` never sees a half-applied
infra state. Rollback = drop the tracker branch before merge.

## Phase 1: Persistent Layer + Edge VM (PR 1)

### Persistent
- [x] 1.1 `terraform/hetzner/persistent/backend.tf`: separate (local) state; remote-backend migration documented.
- [x] 1.2 `terraform/hetzner/persistent/main.tf`: `hcloud_volume.data`, `hcloud_floating_ip.ftm`, `hcloud_network.ftm` (10.0.0.0/16) + `hcloud_network_subnet` (10.0.1.0/24). DNS record left as a documented manual/separate-provider step (hcloud provider does not manage DNS).
- [x] 1.3 `prevent_destroy = true` **and** `delete_protection = true` on volume, floating IP, network (double protection).
- [ ] 1.4 Decide + implement volume at-rest encryption (LUKS vs. Hetzner platform). **DEFERRED to PR3** — LUKS unlock lives in the stack VM cloud-init (the VM that mounts the volume).
- [x] 1.5 `outputs.tf`: export `volume_id`, `volume_linux_device`, `floating_ip_id`, `floating_ip_address`, `network_id`, `location`, `network_zone`.
- [ ] 1.6 Scheduled volume **snapshot** (cadence + retention). **DEFERRED to PR3** — Hetzner has no native Terraform volume-snapshot schedule; verify API/approach when wiring the stack.
- [x] 1.7 Pin `hetznercloud/hcloud ~> 1.49` in `versions.tf`; `.terraform.lock.hcl` committed.
- [x] 1.7b `.gitignore` added so `*.tfstate` (may contain the hcloud token) is never committed.

### Edge
- [x] 1.8 `terraform/hetzner/edge/remote_state.tf`: read-only `terraform_remote_state` of persistent.
- [x] 1.9 `terraform/hetzner/edge/main.tf`: `hcloud_server.edge` (CX22, public IP), joins private network (10.0.1.10), assigns floating IP via `hcloud_floating_ip_assignment`.
- [x] 1.10 `hcloud_firewall.edge`: inbound 80/443 from `0.0.0.0/0`, 22 from `operator_ssh_cidrs` only.
- [x] 1.11 Edge cloud-init (`cloud-init.yaml.tftpl`): installs nginx + certbot, configures floating IP via netplan, idempotent cert issuance script (run after DNS resolves). Template render verified.
- [ ] 1.12 Apply persistent then edge; confirm floating IP held by edge, DNS resolves, TLS issues. **Requires live Hetzner credentials — operator step, not code.**

## Phase 2: Stack Compose + Edge nginx Config (PR 2)

- [x] 2.1 `deploy/docker-compose.stack.yaml`: keycloak, postgres-keycloak, postgres-app, minio, bff, worker. **No nginx** (runs on edge). **No `ui`** — Vite `dist/` served statically by the edge (design updated).
- [x] 2.2 **Two networks** (not one): `internal_net` (`internal: true`: pg-kc, pg-app, minio, keycloak — no egress) + `egress_net` (bff, worker — need the external LLM). Resolves the worker→LLM egress conflict that a single `internal: true` net would have broken.
- [x] 2.3 Keycloak `start --optimized --import-realm` with `KC_HOSTNAME=${DOMAIN}`, `KC_PROXY_HEADERS=xforwarded`, `KC_HEALTH_ENABLED`; admin creds from env.
- [x] 2.4 All services use env-supplied credentials (no hardcoded `keycloakpass` / `minioadmin`). `deploy/.env.example` documents all keys.
- [x] 2.5 MinIO console (:9001) **unpublished**; only `internal_net`.
- [x] 2.6 `deploy/nginx/ftm.conf` (edge VM): TLS, HSTS/CSP/X-Frame-Options/nosniff, `/` → static dist, `/api` → `__STACK_PRIVATE_IP__:8000`, `/realms|/resources|/admin|/js` → `__STACK_PRIVATE_IP__:8080`.
- [x] 2.7 Images from GHCR via `${API_IMAGE}` for bff+worker (same image, worker runs `python -m app.worker`). ui built separately, copied to edge.
- [x] 2.8 realm-export promoted to prod: `sslRequired` `none`→`external`; redirect URIs / web origins / rootUrl / baseUrl `localhost:5173`→`https://__DOMAIN__` (placeholder substituted by stack cloud-init `sed` at boot); 5 demo users kept but `temporary: false`→`true` (forces password change on first login). PKCE S256 already present on `ftm-web`; `ftm-api` is bearer-only (no client secret needed — validates JWKS). JSON validated.
- [x] 2.9 Cold validation: `docker compose config` valid; verified ports bind to `host_ip: ${STACK_PRIVATE_IP}` (NOT 0.0.0.0 — caught a short-form parsing bug, fixed with long-form ports) and `internal_net` is `internal: true`.

**Security finding (2.9):** short-form `"${IP}:host:container"` port syntax silently dropped `host_ip`, which would have exposed Keycloak/bff on 0.0.0.0. Fixed by using long-form `ports:` with explicit `host_ip`. Verified in resolved config.

## Phase 3: Ephemeral Stack VM + Secrets + Runbook (PR 3)

- [x] 3.1 `deploy/.sops.yaml` (age recipient placeholder) + `deploy/secrets.sops.yaml.example` (plaintext template: LUKS passphrase, pg-app, pg-kc, kc admin, minio root + service user, LLM key). Real `secrets.sops.yaml` is operator-encrypted (sops/age not installed here). `.gitignore` blocks filled plaintext + age keys.
- [x] 3.2 `terraform/hetzner/stack/backend.tf` (separate local state) + `remote_state.tf` reading persistent outputs (volume_id, linux_device, network_id, location) **read-only**.
- [x] 3.3 `terraform/hetzner/stack/main.tf`: `hcloud_server.stack` (CX32) in the volume's location; **public IPv4/IPv6 disabled** (`public_net { ipv4_enabled=false, ipv6_enabled=false }`); joins private network at 10.0.1.20; `hcloud_volume_attachment`.
- [x] 3.4 `hcloud_firewall.stack`: inbound 8000/8080 only from `${edge_private_ip}/32`; nothing from the internet.
- [x] 3.5 `cloud-init.yaml.tftpl`: mounts LUKS-encrypted volume (task 1.4 done here), clones repo, `sops -d` secrets → `.env` on **tmpfs** (`/run/ftm-secrets`), `docker compose up`, then shreds the age key. Render verified via `terraform console`.
- [x] 3.6 No secret passed as a plain TF variable that persists usefully in state — `hcloud_token`, `age_private_key` marked `sensitive`; secrets flow through SOPS, not TF vars. (Note: `sensitive` vars still appear in state; see security note below.)
- [ ] 3.7 `deploy/RUNBOOK.md`: one-time persistent+edge apply; up = stack apply; down = stack destroy. **PENDING.**
- [ ] 3.8 Apply stack; confirm no public IP, served through edge over TLS. **Operator step — needs live Hetzner creds.**
- [x] 3.9 Task 1.4 (LUKS) implemented in stack cloud-init. Task 1.6 (snapshots) still pending — belongs in RUNBOOK/persistent.

**Security note (3.6):** the `age_private_key` is passed via server `user_data`/metadata and thus lands in the stack layer's Terraform state (even as `sensitive`). This is the documented residual from design (age key visible to anyone with Hetzner project access / TF state access) — acceptable for a single operator, but the state file must be protected (see persistent/backend.tf remote-backend note). Rotation = re-encrypt SOPS + recreate stack VM.

## Phase 4: Security Verification

- [ ] 4.1 From outside, `nmap` the **floating IP (edge)** → only 443 (80→redirect) open.
- [ ] 4.2 Confirm the **stack VM has no public IP** (nothing external to scan).
- [ ] 4.3 Confirm edge↔stack traffic travels only on the private network interface.
- [ ] 4.4 `terraform -chdir=terraform/hetzner/stack destroy`; assert volume + floating IP + DNS + **edge VM** still present.
- [ ] 4.5 Re-apply stack; assert volume re-attaches, data intact, DNS + edge unchanged.
- [ ] 4.6 Grep the running image and `terraform show` for plaintext secrets; confirm `.env` only on tmpfs.
- [ ] 4.7 Manual e2e: SPA login via PKCE S256 behind the real domain against the prod realm.
- [ ] 4.8 Trace `ai` module DB access; confirm only pseudonymized `metrics`, no `clinical` join.
- [ ] 4.9 Take and restore a volume snapshot; confirm the backup path works.
- [ ] 4.10 Smoke the full flow: diagnose → assign → record → metrics → report.

## Rollback

- [ ] R.1 GCP Terraform left untouched and deployable; document the fallback in RUNBOOK.
- [ ] R.2 Hetzner layers are additive directories; removing them leaves app + dev env unaffected.
