# Design: TFM Production Rollout (tfm-prod-rollout)

> Authored from a **security & network analyst** perspective. Implements the topology
> decided in [../tfm-prod-rollout.md](../tfm-prod-rollout.md): Option 4 (fixed/variable
> split on Hetzner) with an **edge/stack VM split over a Hetzner private network**, plus
> a `backend` docker network `internal: true` inside the stack.

## Technical Approach

Three independently-stated Terraform layers on Hetzner Cloud (EU region), joined by a
Hetzner private network:

- **Persistent layer** — floating IPv4, DNS record, encrypted data volume (data only),
  private network (`hcloud_network`). Never destroyed; `prevent_destroy` on every stateful
  resource. (TLS cert lives on the edge VM, not here; secrets live in the repo, not here.)
- **Edge layer** — always-on nginx VM (CX22). Joins the private network, holds the floating
  IP, terminates TLS, and proxies to the stack VM by its **private IP**. Survives all stack
  power-downs. Only host with a public IP.
- **Stack layer** — on-demand VM (CX32) with **no public IP**. Joins the private network,
  attaches the persistent volume, and boots the production docker-compose stack.

The stack compose is derived from `bbdd_dev_setup/` but re-parented into a single `backend`
docker network (`internal: true`, no published host ports) and **hardened** (dev defaults
removed). nginx is NOT in this compose — it runs on the edge VM and reaches the stack over
the private network. Secrets travel as an age/SOPS-encrypted file **committed to the repo**
(values encrypted); the stack VM pulls it in cloud-init and decrypts it with the age key
passed via metadata. The persistent volume holds only data (Postgres, MinIO objects), never
secrets or the cert.

## Architecture Decisions

| Decision | Choice | Alternatives | Rationale |
|---|---|---|---|
| Layer isolation | **Three separate Terraform states** (`persistent/`, `edge/`, `stack/`) | Single state with `-target`; workspaces | `-target` is error-prone and Terraform itself warns against it; separate state makes an accidental `destroy` of the stack layer *unable* to reach the volume or the edge. Hard safety boundary. |
| Cross-layer wiring | `edge/` and `stack/` read persistent outputs via `terraform_remote_state` (read-only) | Hardcode IDs; data sources by name | Read-only reference cannot mutate/destroy persistent resources; explicit dependency. |
| Volume/IP protection | `prevent_destroy = true` + `lifecycle.ignore_changes` where apt | Rely on discipline | Belt-and-suspenders: even a `destroy` in the persistent state aborts on protected resources. |
| Secret handling | **SOPS + age**, encrypted file on the persistent volume | Plain `.env` on volume; **Docker secrets + encrypted TF state**; Hetzner has no managed secret store; HashiCorp Vault | SOPS+age keeps secrets encrypted at rest and in git (if committed); single age key held by operator; no server to run. Vault is over-engineered for one operator. Plain `.env` fails threat #3. **Docker secrets + encrypted state rejected — see below.** |
| Secret delivery | cloud-init decrypts SOPS file with age key passed once, renders `.env` on tmpfs | Bake secrets into image; env in Terraform | Keeps plaintext off disk (tmpfs) and out of the image/registry. |
| nginx placement | **Separate always-on edge VM** (CX22), off the stack VM | nginx as a container in the stack compose (flat all-in-one) | Recovers VM/hypervisor separation between public edge and biometric zone; edge survives stack teardown; a stack-container escape cannot reach the public edge. |
| edge↔stack transport | **Hetzner private network**, stack VM has no public IP | Public IP on stack + firewall allowlisting the edge | Biometric traffic never touches the internet; stack is unroutable from outside by construction, not just by firewall rule. |
| Network segmentation | Private network (edge↔stack) + `backend` docker network `internal: true` inside the stack | Flat network + host firewall only | Two independent layers: no public route to the stack VM at all, and no host-published ports inside it. |
| Data-at-rest | Hetzner volume + LUKS or app-level; scheduled volume snapshots | Unencrypted volume | Biometric data (threat #4); snapshots also cover the "accidental delete" gap that multi-AZ does NOT. |
| Keycloak mode | `start` (production) with `KC_HOSTNAME`, `KC_PROXY=edge`, `--optimized` | Keep `start-dev` | `start-dev` disables HTTPS enforcement and caching; unacceptable for an identity store behind a real domain. |
| MinIO exposure | API on `backend` only; **console NOT published** | Publish :9001 console | Console is an admin surface; must never face the internet. bff reaches MinIO over `backend`. |
| TLS lifecycle | Cert lives on the **always-on edge VM** (where nginx runs), not on the volume | Store on volume; re-issue per boot | The volume is mounted by the ephemeral stack VM, but nginx runs on the edge — the cert must be where nginx can read it. Edge is always-on, so the cert survives stack recreations and Let's Encrypt is not re-issued. |
| Image delivery | Pull tagged images from GHCR on boot | Build on server; bake snapshot | Reproducible, fast boot; ties into CI/CD (plan §9). Snapshot baking kept as fallback. |

## Layer Topology

```text
PERSISTENT state (terraform/hetzner/persistent/)
  hcloud_floating_ip.ftm         (prevent_destroy)
  hcloud_volume.data             (prevent_destroy)   # pg-app, pg-kc, minio data ONLY (no secrets, no cert)
  hcloud_network.ftm  (10.0.0.0/16) + subnet         (prevent_destroy)
  hetzner DNS record  -> floating_ip                 (prevent_destroy)
  outputs: floating_ip_id/addr, volume_id, network_id, zone

EDGE state (terraform/hetzner/edge/)  — always on
  data.terraform_remote_state.persistent  (read-only)
  hcloud_server.edge (CX22, public IP)
      - joins network_id (private IP e.g. 10.0.1.10)
      - assigns floating_ip_id
      - certbot + nginx; TLS cert persisted on edge VM
  hcloud_firewall.edge -> inbound 80/443 from 0.0.0.0/0 ; 22 from operator IP only

STACK state (terraform/hetzner/stack/)  — ephemeral
  data.terraform_remote_state.persistent  (read-only)
  hcloud_server.stack (CX32, NO public IPv4/IPv6)
      - joins network_id (private IP e.g. 10.0.1.20)
      - attaches volume_id
      - cloud-init: mount volume, decrypt secrets, docker compose up
  hcloud_firewall.stack -> inbound from private subnet only (edge private IP)
```

## Network Model (running posture)

```text
                        internet
                           │  80/443 only  (edge hcloud_firewall + host firewall)
                     ┌─────▼──────┐
   EDGE VM (CX22)    │   nginx    │  public IP = floating IP ; private IP 10.0.1.10
                     └─────┬──────┘
                           │  Hetzner private network (10.0.0.0/16)
                           │  proxy_pass to 10.0.1.20 : /api → bff, /realms → keycloak
══════════════════════════╪══════════════════  VM boundary (separate kernel/hypervisor)
   STACK VM (CX32)         │  NO public IP ; private IP 10.0.1.20
   backend network         │  internal: true  (no gateway, no published host ports)
     ┌──────────┬──────────┼──────────┬──────────┬─────────┐
     ▼          ▼          ▼          ▼          ▼         ▼
  keycloak  pg-keycloak  pg-app      bff       worker    minio
```

Verification requirements:
- From a host *outside*, `nmap` the **floating IP (edge)** → only 443 (and 80→redirect).
- From a host *outside*, the **stack VM has no public IP** to scan at all.
- edge↔stack traffic observed only on the private network interface.

## Secret Handling (design deliverable, deferred from explore)

Secrets in scope: `pg-app` password, `pg-keycloak` password, Keycloak admin password,
Keycloak `ftm-api` client secret, MinIO root + service-user credentials, LLM API key.

- **At rest / source of truth:** a single `secrets.sops.yaml` encrypted with **age**,
  **committed to the repo** — SOPS encrypts the values, keys stay readable, so it is safe in
  git. This is the single source of truth; the persistent volume does NOT store secrets.
- **Key custody:** the age private key is held by the operator, never in the repo/volume/state.
  Passed to the stack VM cloud-init once via Hetzner's `user_data`/metadata at create time.
- **At boot:** cloud-init on the stack VM fetches `secrets.sops.yaml` (repo checkout), runs
  `sops -d`, writes a rendered `.env` onto a **tmpfs** mount (RAM, never touches disk), and
  `docker compose --env-file` reads it.
- **Never:** plaintext secrets in the image, registry, Terraform state, persistent volume, or
  on any non-tmpfs disk.

Residual: the age key in server metadata is visible to anyone with Hetzner project access →
acceptable for a single operator; documented. Rotation = re-encrypt SOPS file + recreate the
stack VM.

### Rejected alternative: Docker secrets + encrypted Terraform state

Evaluated and rejected. It looks like "two security layers" but covers **less** than SOPS+age
with **more** moving parts, because the two halves solve different problems and neither closes
the at-rest gap on its own.

1. **Compose `secrets:` are not managed/encrypted secrets.** True tmpfs-mounted, orchestrator-
   managed secrets exist only in **Docker Swarm**. In plain `docker compose`, the `secrets:`
   block just **bind-mounts a host file** into the container — no encryption, no management. So
   the source file still lives *somewhere in cleartext*; to protect it at rest you need… a tool
   like SOPS again. Running Swarm solely to get real secrets is over-engineering for a
   single-user all-in-one (swap a key-custody problem for operating an orchestrator).

2. **Encrypted TF state solves a different layer.** State encryption protects
   `terraform.tfstate` at the backend / in client (TF ≥1.7). It says nothing about how secrets
   reach containers at runtime. Worse, it invites the **anti-pattern of putting secrets into
   Terraform**: any secret passed as a TF variable lands in the state in plaintext, so encrypting
   the state is patching a hole you should never have opened. This design’s rule is the opposite —
   *secrets never enter the state* (cloud-init decrypts on the server, not in Terraform).

3. **Coverage comparison.**

   | Property | SOPS + age | Docker secrets + encrypted state |
   |---|---|---|
   | Secrets encrypted at rest (repo + volume) | Yes | **No** — source file cleartext unless separately encrypted |
   | Secrets kept out of TF state | Yes (decrypt on server) | Fragile — easily leak into state |
   | Plaintext only in RAM (tmpfs) | Yes | Only with manual Swarm/tmpfs setup |
   | New pieces to operate | one age key | cleartext file + state-encryption config (covers less) |

**Conclusion:** not a substitute — a downgrade. SOPS+age is the minimal single tool that covers
at-rest + delivery + out-of-state. The only legitimate niche for Docker secrets is **if already
running Swarm**, where Swarm secrets could replace the tmpfs-delivery half of SOPS — but you would
*still* need SOPS-style at-rest encryption and *still* want secrets out of the state. Not either/or.

## Dev → Prod Hardening Checklist

The `bbdd_dev_setup/` stack ships insecure defaults that MUST NOT reach prod:

| Dev default | Prod requirement |
|---|---|
| Keycloak `start-dev`, admin/admin | `start --optimized`, admin from SOPS, `KC_HOSTNAME`, `KC_PROXY=edge` |
| `POSTGRES_PASSWORD: keycloakpass` (hardcoded) | from SOPS-rendered `.env` |
| MinIO `minioadmin/minioadmin123` | root creds from SOPS; service user scoped to bucket (already modeled) |
| MinIO console `:9001` published | not published; `backend` only |
| Postgres `ports: 5432:5432` | no published ports; `backend` only |
| Keycloak `ports: 8085:8080` | no published ports; `backend` only |
| nginx inside the same compose/VM | nginx on the **separate edge VM**; not in the stack compose |
| Stack reachable on public IP | Stack VM has **no public IP**; reachable only via private network from edge |
| No TLS | edge nginx TLS termination + HSTS/CSP/nosniff/X-Frame-Options |

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `terraform/hetzner/persistent/main.tf` | Create | Floating IP, encrypted volume, private network, DNS; all `prevent_destroy`. |
| `terraform/hetzner/persistent/outputs.tf` | Create | Export IDs (floating IP, volume, network, zone). |
| `terraform/hetzner/persistent/backend.tf` | Create | Separate remote state. |
| `terraform/hetzner/edge/main.tf` | Create | Always-on CX22 nginx VM; joins network; holds floating IP; certbot. |
| `terraform/hetzner/edge/remote_state.tf` | Create | Read-only `terraform_remote_state` of persistent. |
| `terraform/hetzner/stack/main.tf` | Create | Ephemeral CX32 VM, NO public IP, volume attach, network join, firewall, cloud-init. |
| `terraform/hetzner/stack/remote_state.tf` | Create | Read-only `terraform_remote_state` of persistent (volume, network, edge private IP). |
| `terraform/hetzner/stack/cloud-init.yaml.tftpl` | Create | Mount volume, SOPS decrypt→tmpfs, compose up. |
| `deploy/docker-compose.stack.yaml` | Create | Stack services on `backend` (`internal: true`), no dev ports, no nginx. |
| `deploy/nginx/ftm.conf` | Create | Edge nginx: TLS, headers, routing to stack private IP `/`,`/api`,`/realms|/resources|/admin|/js`. |
| `deploy/secrets.sops.yaml` | Create | age-encrypted secrets (values encrypted). |
| `deploy/.sops.yaml` | Create | SOPS ruleset (age recipient). |
| `deploy/RUNBOOK.md` | Create | Operator up/down procedure. |
| `bbdd_dev_setup/keycloak/ftm-keycloak/realm-export.json` | Source | Promote to prod realm (domain redirect URIs). |

## Operator Runbook (shape)

```text
# One-time
terraform -chdir=terraform/hetzner/persistent apply     # IP + volume + network + DNS, forever
terraform -chdir=terraform/hetzner/edge apply           # always-on nginx VM, holds floating IP

# Bring a demo up
terraform -chdir=terraform/hetzner/stack apply          # stack VM boots on private net, served via edge TLS

# Tear the demo down (data + IP + DNS + edge survive)
terraform -chdir=terraform/hetzner/stack destroy        # cannot touch persistent or edge state
```

## Testing / Verification Strategy

| Layer | What to verify | Approach |
|-------|----------------|----------|
| Network isolation | Only 443/80 reachable on the edge floating IP | `nmap` the floating IP from outside; expect only 443 (80→redirect). |
| No public stack | Stack VM has no public IP to scan | Confirm stack server has public IPv4/IPv6 disabled; nothing to nmap. |
| Private transport | edge↔stack only over private network | Observe traffic on the private interface; no public egress for stack services. |
| Layer safety | Stack `destroy` cannot delete volume/edge | Run destroy, assert volume + IP + DNS + edge VM still present. |
| Secret hygiene | No plaintext secrets on disk/image/state | Grep image + `terraform show`; confirm `.env` only on tmpfs. |
| Auth | SPA login via PKCE S256 behind real domain | Manual e2e against prod realm. |
| Biometric boundary | LLM path reads only pseudonymized metrics | Trace `ai` module DB access; no `clinical` join. |
| Recreate | Volume re-attaches cleanly on new stack VM | Destroy + apply stack; data intact, DNS + edge unchanged. |
| At-rest | Volume encrypted; snapshot schedule works | Confirm encryption; take/restore a snapshot. |

## Migration / Rollout

Persistent + edge layers applied once. Stack layer is the repeatable up/down unit. GCP
Terraform left intact as rollback/productionization path. First rollout: apply persistent →
point domain DNS at floating IP → apply edge → apply stack → smoke test (login, record,
metrics, report) → snapshot volume.

## Open Questions (carry to tasks)

- Exact Hetzner region/zone for volume+server co-location (volume is zone-bound → single-zone
  by design; confirm the zone once).
- LUKS on the volume vs. relying on Hetzner's platform encryption — decide the at-rest layer.
- GHCR auth on boot (read-only token via SOPS) vs. public images.
- Snapshot cadence + retention for the data volume (the real safeguard against accidental delete).
```
