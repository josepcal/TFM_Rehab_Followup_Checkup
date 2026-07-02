# Proposal: TFM Production Rollout (tfm-prod-rollout)

**Change Name**: `tfm-prod-rollout`  
**Status**: Proposed

## Intent

Deploy the FTM Rehab Follow-up MVP to a reachable environment for TFM defense/demos,
optimized for the **real operating model**: single user, non-continuous load, compute
powered down between demos, keeping only **data volume + DNS + floating IP** alive when
idle. The deployment must preserve the **GDPR biometric anonymization/isolation boundary**
(voice = special-category data) while being near-zero cost at rest and quick to bring up
on demand.

## Decision

Adopt **Option 4 (fixed/variable split on Hetzner)** with an **edge/stack VM split** over a
**Hetzner private network**, as analyzed in
[explore/tfm-prod-rollout.md](explore/tfm-prod-rollout.md). nginx is separated out of the
stack onto its own always-on edge VM (user requirement), recovering VM/hypervisor + network
separation between the public edge and the biometric zone.

- **Edge VM (fixed, always-on, CX22 2vCPU/4GB, ~€4/mo):** nginx (TLS termination, security
  headers, routing) + certbot. Holds the floating IPv4. Permanent public front; survives all
  stack power-downs. **Only host with a public IP.**
- **Stack VM (ephemeral, created/destroyed per demo, CX32 2vCPU/8GB):** keycloak,
  postgres-keycloak, postgres-app, bff, worker, ui-build, minio. **No public IP.** Runs the
  docker-compose stack; keeps a `backend` docker network `internal: true` as an added layer.
- **Persistent layer (`prevent_destroy`):** floating IPv4, DNS record (→ edge floating IP),
  encrypted data volume (Postgres data + MinIO objects/WAVs; data only — no cert, no secrets),
  private network. (TLS cert lives on the edge VM; secrets live SOPS-encrypted in the repo.)
- **Private network (Hetzner, 10.x):** edge ↔ stack traffic (`/api`, `/realms`) travels only
  over the private network by private IP. Biometric traffic never touches the internet.

Rejected alternatives (kept documented in explore): Option 1 GCP 4-VMs = correct for real
multi-patient production but over-built and cost/idle-mismatched here; Option 2 flat
all-in-one = cheapest but discards network segmentation; Option 3 alone = good running
posture but does not model the ephemeral teardown the workload requires. Flat single-VM
all-in-one was superseded by this edge/stack split to keep nginx off the biometric VM.

## Scope

### In Scope

- New Hetzner Terraform IaC split into **three layers**: persistent (floating IP + DNS +
  encrypted volume + private network), edge (always-on nginx VM), and ephemeral stack VM.
  Lifecycle: `prevent_destroy` on volume, floating IP, DNS and private network; the stack
  layer destroyable without touching persistent or edge.
- **Hetzner private network** joining edge and stack VMs; stack VM has no public IP.
- Production docker-compose derived from `bbdd_dev_setup/` for the **stack VM** (keycloak,
  postgres-keycloak, postgres-app, bff, worker, ui-build, minio) with a `backend` network
  `internal: true` and **no published host ports** (edge reaches services over the private
  network).
- nginx prod config on the **edge VM**: TLS termination (Let's Encrypt, cert persisted on the
  always-on edge VM for reuse), HSTS/CSP/X-Frame-Options/nosniff, routing `/` → ui, `/api` →
  bff (stack private IP), `/realms|/resources|/admin|/js` → keycloak (stack private IP).
- Cloud-init/bootstrap for the ephemeral stack VM: join private network, mount volume,
  decrypt secrets, pull images, bring up compose.
- Production Keycloak realm promoted from `bbdd_dev_setup/keycloak/realm-export.json`
  (redirect URIs behind the real domain, PKCE S256, bearer-only api client).
- Host firewall: only 80/443 inbound from internet; SSH restricted to operator source.
- Up/down operator runbook (bring stack up for a demo, tear the variable layer down after).
- Image delivery path (registry pull on boot) wired to the CI/CD outline in plan §9.

### Out of Scope

- **Deep secret-handling implementation** — the *approach* is chosen (SOPS + age, encrypted
  in repo, decrypted to tmpfs on the stack VM; see design). Key custody/rotation procedures
  and CI integration are elaborated in design/tasks, not here. Hetzner has no managed Secret
  Manager, so secrets are handled explicitly via SOPS.
- HA, autoscaling, multi-AZ, load balancing (not required for single-user workload).
- Keeping the existing GCP Terraform running; it is retained only as the documented
  "productionization path" for a future real multi-patient service.
- Application code changes (UC features) — this change is deployment topology only.
- RGPD data lifecycle/retention/export-erase on object storage (deferred, per UC-05).
- Observability/alerting stack beyond basic container logs.

## Capabilities

### New Capabilities

- `prod-persistent-infra`: floating IP + DNS + encrypted data volume + private network that
  survive stack teardown, so DNS stays valid and data persists across demos.
- `prod-edge-vm`: always-on nginx VM holding the floating IP; single public entry, TLS
  termination + security headers; survives stack power-downs.
- `prod-ephemeral-stack`: on-demand stack VM (keycloak/pg/minio/app) with no public IP,
  created for a demo and destroyed after, billed only while powered on.
- `prod-network-isolation`: Hetzner private network between edge and stack + `backend` docker
  network `internal: true` inside the stack; the biometric DB/Keycloak are not externally
  routable and edge↔stack traffic never leaves the private network.
- `prod-tls-edge`: nginx TLS termination with security headers as the single public entry.

### Modified Capabilities

- `keycloak-realm-config`: dev realm export promoted to a production realm bound to the
  real domain behind the edge nginx.

## Approach

Build a fresh `terraform/hetzner/` with **three states/layers** so the stack layer can be
`destroy`ed independently of persistent and edge. The persistent layer provisions a floating
IPv4, a DNS record pointing at it, an encrypted `hcloud_volume`, and a `hcloud_network`
private network; all marked `prevent_destroy`. The edge layer provisions the always-on nginx
VM, joins the private network, and assigns the floating IP. The stack layer provisions the
ephemeral VM (no public IP), joins the private network, attaches the volume, and runs a
cloud-init that starts the compose. The compose reuses the dev services (`bbdd_dev_setup/`)
on a `backend` network `internal: true` with no published ports; nginx on the edge reaches
them over the private network by private IP. The TLS cert is persisted on the always-on edge
VM for reuse across stack recreations. Secrets travel SOPS-encrypted in the repo, decrypted on
the stack VM at boot into tmpfs (see design).

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `terraform/hetzner/persistent/` | New | Floating IP, DNS, encrypted volume, private network; `prevent_destroy`. |
| `terraform/hetzner/edge/` | New | Always-on nginx VM; joins private network; holds floating IP. |
| `terraform/hetzner/stack/` | New | Ephemeral stack VM (no public IP), volume attach, private network, cloud-init. |
| `deploy/docker-compose.stack.yaml` | New | Stack services on `backend` (`internal: true`), no published ports. |
| `deploy/nginx/` | New | Edge nginx conf: TLS, headers, routing to stack private IP. |
| `bbdd_dev_setup/keycloak/realm-export.json` | Dependency | Source for the prod realm. |
| `bbdd_dev_setup/` compose files | Dependency | Source services to unify into the stack compose. |
| `terraform/` (GCP) | Retained | Left in place as documented productionization path. |
| CI/CD (plan §9) | Modified | Build/push images to registry pulled on stack boot. |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Stray published port exposes Postgres/Keycloak | Medium | `backend` `internal: true`; no `ports:` on stack services; stack VM has no public IP; host firewall; review. |
| Stack VM accidentally gets a public IP | Medium | Explicitly disable public IPv4/IPv6 on the stack server resource; verify with external `nmap`. |
| Container escape reaches all networks (shared kernel) | Low | No `privileged`, no docker-socket mount; keep host patched; residual is confined to the stack VM, not the edge. |
| Losing floating IP on teardown breaks DNS | Medium | Floating IP in persistent layer with `prevent_destroy`; assigned to always-on edge VM; DNS points at it. |
| Secret leakage without managed Secret Manager | Medium | Deferred to design; secrets encrypted, never in repo/image/state. |
| Data-at-rest exposure via volume/snapshot | Medium | Encrypt data volume; restrict snapshot access. |
| Stack destroy accidentally hits persistent/edge | Medium | Separate Terraform state per layer; `prevent_destroy` guards; stack reads persistent outputs read-only. |
| Let's Encrypt rate limits | Low | Cert lives on the always-on edge VM; not re-issued on stack recreation. |

## Rollback Plan

The GCP Terraform remains intact and deployable; if the Hetzner rollout is abandoned, revert
to Option 1 with no code loss. The Hetzner layers are additive (new directories); removing
them leaves the application and dev environment unaffected.

## Dependencies

- Hetzner Cloud account/project in EU region, API token for the `hcloud` provider.
- Registered domain with DNS manageable to point at the floating IP.
- `bbdd_dev_setup/` compose services and `realm-export.json` as the stack source.
- Container registry (e.g. GHCR) for api/worker/web images.
- Secret-handling mechanism chosen in the design phase.

## Success Criteria

- [ ] Persistent layer (floating IP + DNS + encrypted volume + private network) applies once
      and survives `destroy` of the stack layer.
- [ ] Edge VM stays up across stack power-downs, holds the floating IP, and serves TLS.
- [ ] Stack layer can be brought up on demand, joins the private network, attaches the volume,
      and is served through the edge nginx over TLS.
- [ ] Stack VM has **no public IP**; from the internet only the edge nginx (443) is reachable;
      Postgres, Keycloak and MinIO are not externally routable (verified with external `nmap`).
- [ ] edge↔stack traffic travels only over the Hetzner private network.
- [ ] Tearing down the stack layer leaves only volume + DNS + floating IP + edge VM billing
      (~€5–7/mo) with zero stack compute.
- [ ] Keycloak prod realm authenticates the SPA via Authorization Code + PKCE S256 behind
      the real domain.
- [ ] Biometric isolation boundary preserved: LLM path reads only pseudonymized metrics.
- [ ] Operator runbook lets a single person bring the stack up and down repeatably.
```
