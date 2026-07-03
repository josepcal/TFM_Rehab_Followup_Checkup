# Explore: TFM Production Rollout (tfm-prod-rollout)

> Analysis authored from a **security & network analyst** perspective. Goal: choose a
> deployment topology for the FTM MVP evaluated across three axes — **security**,
> **economic cost**, and **development effort** — given the *real* workload
> (single user, non-continuous, servers powered down between demos, only
> disk + DNS + floating IP kept alive).

## User Need

Deploy the FTM Rehab Follow-up MVP to a reachable environment for TFM defense/demos.
The system handles **voice recordings = GDPR special-category biometric data**
(art. 9), so the deployment must keep the anonymization boundary intact and isolate
the identified/biometric zone from the public-facing edge. It must be cheap to keep
idle and quick to bring up on demand.

## Current State

- **Existing IaC = Terraform targeting GCP** (`hashicorp/google ~> 5.0`), NOT
  docker-compose. Modules: `network`, `postgresql`, `nginx`, `keycloak`, `app`;
  environments `dev`/`prod` with remote backends.
- GCP topology is **4 separate VMs**: nginx (public subnet 10.0.1.0/24) + keycloak,
  postgresql, app (private subnet 10.0.2.0/24). Cloud NAT for private egress.
- Security posture already implemented in GCP:
  - Least-privilege firewall by network tags — every hop explicit
    (nginx→app:8000, app→pg:5432, app→kc:8080, nginx→kc:8080); nothing else open.
  - Internet → only nginx :80/:443. SSH only via IAP range (35.235.240.0/20).
  - Shielded VMs (secure boot + vTPM + integrity monitoring), `block-project-ssh-keys`.
  - nginx terminates TLS (Let's Encrypt), HSTS + CSP + X-Frame-Options + nosniff.
  - Secret Manager with per-secret IAM (app-db-password, llm-api-key); Artifact Registry.
  - Postgres VM serves two DBs (keycloak + `ftm_app`); app DB runtime role must not bypass RLS.
- **`bbdd_dev_setup/`** already contains a working docker-compose local stack:
  postgres-app, recording-database (MinIO) with bucket policy templates, keycloak with
  `realm-export.json`, alembic migrations. This is the seed for any all-in-one option.
- Prod sizing in tfvars is **over-provisioned** for a single-user MVP
  (postgresql e2-standard-4 = 4vCPU/16GB). Not driven by measured load.

## Constraints

- **GDPR / biometric boundary (hard):** raw audio + patient identity never reach the
  LLM; pseudonym↔patient map lives only in `clinical` schema under RLS; `ai` module reads
  only from `metrics`. Deployment must not weaken this. Data residency = EU.
- **Network isolation (graded):** the biometric DB and identity store (Keycloak) should be
  unreachable from the public edge except through nginx.
- **Idle cost must be near-zero:** only disk (volume), DNS, and a fixed/floating IP persist
  when the stack is down. Compute is created on demand and destroyed after.
- **Single operator, single user, non-continuous load.** No HA, no autoscaling, no
  multi-AZ required. Over-engineering is itself a failure mode here.
- **Reuse existing assets** where cheap: dev compose stack, realm-export.json, alembic,
  MinIO bucket policies.

## Options Considered

### Threat model (shared baseline for scoring)

For a single-user ephemeral TFM demo the realistic threats are, in order:
1. **Misconfiguration exposure** — a DB/Keycloak port accidentally reachable from internet.
2. **Public-edge compromise** — attacker pivots from the internet-facing component toward
   the biometric DB.
3. **Secret leakage** — DB/LLM credentials in repo, image, or world-readable on host.
4. **Data-at-rest exposure** — volume/snapshot readable outside the stack.
DoS, multi-tenant isolation, and insider threat are largely out of scope for this workload.

### Option 1 — Reuse GCP separated VMs (status quo)

Keep the existing Terraform: 4 VMs, public/private subnets, tag-based firewall, Secret
Manager, IAP SSH, Shielded VMs.

- **Security: STRONGEST.** Isolation by *hypervisor + network*. Public-edge compromise does
  not reach Postgres/Keycloak (separate VMs, private subnet, explicit firewall hops).
  Managed secrets with per-secret IAM. Threat #2 strongly mitigated; #1 hard to hit because
  every hop is deny-by-default.
- **Cost: HIGHEST.** ~€185–230/mo running (over-provisioned). Critically, **the "power down
  between demos" pattern fits GCP poorly**: stopped VMs still bill for reserved static IP +
  persistent disks, and tearing down/recreating 4 VMs + NAT + router each time is heavy.
  Idle-but-usable is expensive; full teardown loses the operational simplicity.
- **Effort: LOWEST to keep, MEDIUM to operate.** IaC already written and coherent. But the
  ephemeral up/down workflow is not modeled; NAT + IAP + Secret Manager add moving parts for
  a one-person demo. Sizing should be cut regardless.
- **Verdict:** correct for a real multi-patient production service; **over-built and
  cost-inefficient for the actual TFM workload**, especially the idle-cost requirement.

### Option 2 — All-in-one on Hetzner (single VM, flat)

One Hetzner VM (CX32, 2vCPU/8GB) runs the whole docker-compose: nginx + keycloak +
postgres-keycloak + postgres-app + ui + bff + worker + minio, on a single docker network.

- **Security: WEAKEST of the Hetzner options.** No network segmentation: all containers share
  one bridge and one kernel. If any published-port mistake happens (a `5432:5432` "for
  debugging"), Postgres is exposed to host and possibly internet — threat #1 becomes easy.
  Public-edge compromise (#2) reaches the biometric DB with only container-namespace isolation
  in the way. Still: only nginx *needs* to publish 443, and host firewall can block the rest.
- **Cost: LOWEST.** VM ~€8/mo running (CX32); idle (server destroyed, keep volume + Primary
  IP) ~€2–3/mo. Compute billed by the hour actually powered on. Best fit for idle-cost
  requirement.
- **Effort: LOW.** Reuses the dev compose almost verbatim; one host, one compose, one TLS cert.
  But requires rewriting IaC GCP→Hetzner and replacing Secret Manager/Artifact Registry with
  Hetzner Volumes + GHCR + manual/`.env` secret handling (a security regression on threat #3
  if done carelessly).
- **Verdict:** cheapest and simplest, but throws away the segmentation the system was designed
  around. Acceptable only with compensating controls (host firewall, no stray published ports).

### Option 3 — Hybrid all-in-one with internal docker network

Same single Hetzner VM, but two docker networks: `edge` (only nginx, publishes 443) and
`backend` (`internal: true` — keycloak, both Postgres, bff, worker, minio; **no published
ports**). Only nginx bridges edge↔backend.

- **Security: MEDIUM (best value on the single VM).** Recovers most defense-in-depth:
  `internal: true` removes the external route to the backend network and blocks backend
  egress; a stray `ports:` on a backend service still won't reach internet because the network
  has no gateway. Threat #1 radius shrinks a lot. **Honest limits:** still one shared kernel
  (container-escape via a runc CVE, `privileged`, or a mounted docker socket = full host =
  all networks); `internal: true` is routing topology, not encryption/authn — backend traffic
  is cleartext; a single misassignment of a container to the wrong network collapses it.
  Weaker than VM/hypervisor separation, but a genuine, documentable control — not theater.
- **Cost: LOWEST (= Option 2).** Same VM, same idle profile ~€2–3/mo down.
- **Effort: LOW–MEDIUM.** Marginal over Option 2: split the compose into two networks, ensure
  no backend service publishes host ports, keep nginx as the only bridge. Same GCP→Hetzner
  IaC rewrite and secret-handling work as Option 2.
- **Verdict:** **best security-per-euro for the real workload.** For a single-user ephemeral
  demo of biometric data, `internal: true` + host firewall + no `privileged` + no docker-socket
  mount is a defensible, honestly-documented posture in the TFM.

### Option 4 — Fixed/Variable split (persistent core + ephemeral compute)

Split infrastructure into two Terraform layers on Hetzner:
- **Fixed (never destroyed, `prevent_destroy`):** nginx (or at least its config), **Primary/
  floating IPv4**, **DNS record**, **data volume** (Postgres data, MinIO objects/WAVs).
- **Variable (created/destroyed per demo):** the compute running minio, postgres(-app/-kc),
  keycloak, and app (ui+bff+worker) — as containers on an on-demand server that attaches the
  fixed volume and floating IP on boot.

- **Security: MEDIUM–STRONG, and operationally the safest for *this* pattern.** Same
  single-kernel caveat as Option 3 while running (can be combined with `internal: true`).
  But it **directly models the "keep only disk+DNS+IP" requirement**: the persistent layer has
  no compute attack surface when down (a volume + a reserved IP have essentially no exploitable
  service). Floating IP keeps DNS valid across server recreation — avoids the classic failure of
  losing the IP on teardown and pointing DNS at a stranger's new VM. Data-at-rest (threat #4)
  is the main residual: the volume should be encrypted and snapshots access-controlled.
- **Cost: LOWEST idle, and *clean*.** Down state = volume (~€0.50/10GB) + Primary IP (~€0.60–1)
  = ~€1.5–3/mo, with **zero compute**. Up state = CX32 hours only. Cleaner cost story than
  Option 2/3 because teardown of the variable layer is a first-class operation, not an
  afterthought.
- **Effort: MEDIUM (highest of the Hetzner options).** Two Terraform layers with correct
  lifecycle (`prevent_destroy` on volume/IP/DNS; `-target` or separate state for the variable
  layer), cloud-init to mount the volume + attach floating IP + bring up compose, and a repeatable
  up/down runbook. More upfront design, but it is the pattern the requirement actually describes.
- **Verdict:** **best fit to the stated operating model** (ephemeral compute, persistent
  disk+DNS+IP). Pairs naturally with Option 3's internal network for the running posture. The
  cost is design/runbook effort, not money.

## Comparative Summary

| Option | Security | Cost (run / idle) | Dev effort | Fit to real workload |
|--------|----------|-------------------|------------|----------------------|
| 1. GCP separated VMs | Strongest (hypervisor+net) | ~€185–230/mo / poor idle | Lowest to keep, awkward to operate ephemerally | Over-built; idle-cost mismatch |
| 2. Hetzner all-in-one flat | Weakest | ~€8 / ~€2–3 | Low | Cheap but discards segmentation |
| 3. Hetzner hybrid (internal net) | Medium (best per €) | ~€8 / ~€2–3 | Low–Medium | Strong value; good running posture |
| 4. Fixed/variable split | Medium–Strong (models teardown) | ~€8 running / ~€1.5–3 idle, zero compute | Medium | **Best fit to stated operating model** |

## Decision (proposed, to confirm in propose phase)

Lead with **Option 4 (fixed/variable split on Hetzner) combined with Option 3's internal
docker network** for the running posture:
- Persistent layer: floating IP + DNS + encrypted data volume (+ nginx/TLS config).
- Ephemeral layer: on-demand server running the compose with `edge`/`backend` (`internal:true`)
  networks; only nginx publishes 443.
- This satisfies idle-cost (only disk+DNS+IP persist), keeps a defensible biometric-isolation
  posture, and matches the single-user ephemeral operating model without GCP's cost/operational
  overhead.

Keep Option 1 documented as the "productionization path" if the system ever serves real
multi-patient traffic (segmentation by VM/hypervisor is the right answer there).

> **Update (confirmed in propose):** the running posture evolved from "one VM with
> edge/backend docker networks" to an **edge/stack VM split over a Hetzner private network** —
> nginx moved to its own always-on edge VM, the stack VM has no public IP, and edge↔stack
> traffic stays on the private network. This *strengthens* Option 4: it recovers VM/hypervisor
> separation between the public edge and the biometric zone at ~€5–7/mo idle. See the proposal
> and design for the final topology. Secret handling was resolved as **SOPS + age** (see design).

## Open Questions (for propose / product owner)

- **Secret handling on Hetzner:** `.env` on the encrypted volume vs. a lightweight secret store
  (e.g. SOPS-encrypted files, Hetzner has no managed Secret Manager). Threat #3 depends on this.
- **Image delivery:** GHCR pull on boot vs. baking images into a snapshot. Affects boot time and
  the CI/CD from the plan's §9.
- **Volume & snapshot encryption:** confirm at-rest encryption for the data volume and access
  control on snapshots (threat #4).
- **Keycloak realm for prod:** promote `bbdd_dev_setup/keycloak/realm-export.json` to a prod
  realm (redirect URIs behind the real domain, PKCE S256, bearer-only api client).
- **TLS on ephemeral compute:** Let's Encrypt rate limits vs. reusing a cert stored on the
  persistent volume across server recreations.
- **State backend for two-layer Terraform:** where the variable-layer state lives so teardown is
  clean and does not risk the persistent layer.
- **Data lifecycle/retention & RGPD export/erase** on object storage remain deferred (noted in
  UC-05 explore) but interact with the volume design here.
```
