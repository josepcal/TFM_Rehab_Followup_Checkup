# FTM Production Rollout — Operator Runbook

> 🇪🇸 [Versión en español](RUNBOOK_ES.md)

Ephemeral deploy on Hetzner: an always-on **edge** VM (nginx + floating IP) plus an
on-demand **stack** VM (keycloak, postgres×2, minio, bff, worker) with **no public IP**,
joined over a private network. Data lives on a persistent encrypted volume.

**Architecture and layer rationale:** [`../terraform/README_ES.md`](../terraform/README_ES.md)
(español) / [`../terraform/README.md`](../terraform/README.md) (English).
This runbook is the day-to-day operational procedure; read the architecture doc first if
you have not deployed this system before.

Design records: `openspec/tfm-prod-rollout.md` (proposal), `openspec/design/tfm-prod-rollout.md` (design).

---

## Deployment reference values

The commands below use the **live production values**. Substitute your own if deploying a
separate environment.

| Value | Production |
|---|---|
| Domain | `ftm-followup-checkup.duckdns.org` |
| Floating IP (DNS A record target) | `167.233.190.87` |
| Edge private IP | `10.0.1.10` |
| Stack private IP | `10.0.1.20` |

Every layer takes `-var="domain=..."`. Keep it identical across all three — a mismatch
breaks TLS, the Keycloak issuer, and the presigned-URL signatures.

---

## 0. One-time prerequisites

Tooling on the operator machine: `terraform`, `sops`, `age`, `hcloud` CLI, `node` 20+,
`ssh`, `rsync`.

```bash
export TF_VAR_hcloud_token='<hetzner-api-token>'        # never commit
export TF_VAR_age_private_key="$(cat age.key)"          # your age private key
```

- Generate an age keypair: `age-keygen -o age.key` (public key printed as `age1...`).
- Put the public key in `deploy/.sops.yaml` (replace the placeholder).
- Own a domain whose A record you can point at the floating IP (e.g. DuckDNS).

### Encrypt the secrets (once, and on rotation)

```bash
cp deploy/secrets.sops.yaml.example /tmp/secrets.plain.yaml
# edit /tmp/secrets.plain.yaml with real values (incl. LUKS_PASSPHRASE)
sops --encrypt --age age1YOURPUBKEY /tmp/secrets.plain.yaml > deploy/secrets.sops.yaml
shred -u /tmp/secrets.plain.yaml
```

The encrypted file may be committed — SOPS encrypts the values. The **age private key**
never goes in git and never leaves the operator machine.

---

## 1. Persistent layer (apply ONCE, then leave forever)

```bash
terraform -chdir=terraform/hetzner/persistent init
terraform -chdir=terraform/hetzner/persistent apply \
  -var="domain=ftm-followup-checkup.duckdns.org"
```

Creates: floating IP, encrypted-capable data volume, private network, subnet. All
`prevent_destroy` + `delete_protection`.

```bash
terraform -chdir=terraform/hetzner/persistent output floating_ip_address
```

### Point DNS at the floating IP

Set the domain's A record → floating IP. Confirm before continuing — certbot will fail
otherwise:

```bash
dig +short ftm-followup-checkup.duckdns.org    # must print the floating IP
```

---

## 2. Edge layer (apply ONCE, always on)

```bash
terraform -chdir=terraform/hetzner/edge init
terraform -chdir=terraform/hetzner/edge apply \
  -var='operator_ssh_cidrs=["<your-ip>/32"]' \
  -var="ssh_public_key=$(cat ~/.ssh/id_ed25519.pub)" \
  -var="domain=ftm-followup-checkup.duckdns.org" \
  -var="ssl_cert_email=you@example.com"
```

The edge boots with nginx, a placeholder vhost on `:80`, and NAT masquerading so the
stack VM (which has no public IP) can reach the internet for egress.

### 2a. Issue the TLS certificate

Only after DNS resolves to the floating IP:

```bash
EDGE=167.233.190.87
ssh root@$EDGE /usr/local/bin/ftm-issue-cert.sh
```

The script is idempotent — it exits early if a cert already exists.

### 2b. Install the routing vhost

The cloud-init vhost is a placeholder. Replace it with the real one, which proxies `/api`,
`/realms`, and `/ftm-recordings/` to the stack over the private network:

```bash
DOMAIN=ftm-followup-checkup.duckdns.org
STACK_IP=10.0.1.20
EDGE=167.233.190.87

sed -e "s|__DOMAIN__|$DOMAIN|g" \
    -e "s|__STACK_PRIVATE_IP__|$STACK_IP|g" \
    deploy/nginx/ftm.conf > /tmp/ftm.conf

scp /tmp/ftm.conf root@$EDGE:/etc/nginx/sites-available/ftm
ssh root@$EDGE 'nginx -t && systemctl reload nginx'
```

`nginx -t` must pass before the reload. If it fails, the old vhost stays active —
fix the config and retry rather than forcing a restart.

### 2c. Build and deploy the frontend

The edge serves the Vite `dist/` as static files from `/var/www/ftm`. Build with the
**production** Keycloak settings — the SPA talks to Keycloak through the edge, on the same
origin, so the URL is the public domain, not the stack's private IP:

```bash
cd web
npm ci
VITE_FTM_AUTH_MODE=pkce \
VITE_FTM_KEYCLOAK_URL=https://ftm-followup-checkup.duckdns.org \
VITE_FTM_KEYCLOAK_REALM=ftm \
VITE_FTM_KEYCLOAK_CLIENT_ID=ftm-web \
npm run build

rsync -av --delete dist/ root@167.233.190.87:/var/www/ftm/
cd ..
```

`--delete` matters: stale hashed assets from a previous build otherwise pile up in
`/var/www/ftm`.

> Rebuild and re-rsync whenever the frontend changes. The edge is always on, so this step
> is independent of the stack's up/down cycle.

> ⚠️ **This step needs SSH access to the edge.** Port 22 is restricted to the operator's
> IP; if yours has changed, `rsync` will hang or time out. See
> [Annex A — Operator SSH access](#annex-a--operator-ssh-access).

---

## 3. Bring a demo UP (stack layer)

```bash
terraform -chdir=terraform/hetzner/stack init
terraform -chdir=terraform/hetzner/stack apply \
  -var="ssh_public_key=$(cat ~/.ssh/id_ed25519.pub)" \
  -var="repo_url=<git-url>" \
  -var="repo_ref=<branch-or-tag>" \
  -var="domain=ftm-followup-checkup.duckdns.org" \
  -var="api_image=ghcr.io/josepcal/tfm_rehab_followup_checkup/api:v1.0.2"
```

`api_image` pins the API image (the worker runs the same one). **Optional** — omit it and
the compose falls back to `:latest`. See
[Annex B — Pinning the API image](#annex-b--pinning-the-api-image) for why that fallback is
a problem and how to produce a version tag.

The stack VM boots with **no public IP**, mounts the LUKS-encrypted volume at
`/mnt/ftm-data`, decrypts `secrets.sops.yaml` to tmpfs, renders `.env`, and starts the
compose. It is reachable only from the edge, over the private network.

Cloud-init takes a few minutes (image pulls, Keycloak realm import, MinIO bucket
provisioning). Proceed to verification rather than assuming it is up.

### 3a. Apply pending migrations

> ⚠️ **This step needs SSH access to the edge** (it reaches the stack through it). Port 22
> is restricted to the operator's IP. See
> [Annex A — Operator SSH access](#annex-a--operator-ssh-access).

**Cloud-init does NOT run migrations.** It only clones the repo, decrypts secrets and
brings up the compose. Because the data volume is persistent and survives every
destroy/apply cycle, its schema drifts behind the deployed code. This step is manual and
must be done **whenever the deploy includes a new migration**.

Snapshot the volume first (§6) — real patient data lives there:

```bash
hcloud volume create-snapshot ftm-prod-data --description "pre-migration $(date +%F)"
```

The `bff` container connects as `ftm_app`, which **cannot even read** `alembic_version`.
Override `DATABASE_URL` with the admin role (credentials are in `/run/ftm-secrets/.env` on
the stack VM):

```bash
export ADMIN_DB_USER=<admin-user>
export PASSWORD=<admin-password>
export APP_DB_NAME=<db-name>

# Check the current revision
ssh -J root@167.233.190.87 root@10.0.1.20 \
  "docker exec -w /app/db-migrations \
     -e DATABASE_URL='postgresql://$ADMIN_DB_USER:$PASSWORD@postgres-app:5432/$APP_DB_NAME' \
     deploy-bff-1 alembic current"

# Apply what is pending
ssh -J root@167.233.190.87 root@10.0.1.20 \
  "docker exec -w /app/db-migrations \
     -e DATABASE_URL='postgresql://$ADMIN_DB_USER:$PASSWORD@postgres-app:5432/$APP_DB_NAME' \
     deploy-bff-1 alembic upgrade head"
```

Use **double quotes on the outside** (so the local shell expands the variables) and single
quotes inside. With single quotes outside, the variables are not expanded and the URL
arrives without credentials.

> Symptom of skipping this step: 500s with `invalid input value for enum ...`, or missing
> columns. It is not a code bug — it is a stale schema.

---

## 4. Verify the deploy

### 4a. From the operator machine (public surface)

```bash
DOMAIN=ftm-followup-checkup.duckdns.org

# API health through the edge
curl -fsS https://$DOMAIN/api/health          # -> {"status":"ok"}

# Keycloak realm through the edge
curl -fsS https://$DOMAIN/realms/ftm | head -c 200

# Frontend
curl -fsS -o /dev/null -w '%{http_code}\n' https://$DOMAIN/    # -> 200
```

### 4b. Network isolation (the GDPR-relevant check)

```bash
nmap 167.233.190.87        # expect only 80 (redirect) and 443 — nothing else
```

The stack VM has no public IP, so there is no address to scan. Confirm Terraform agrees:

```bash
terraform -chdir=terraform/hetzner/stack output has_public_ip   # must be false
```

Postgres (5432), MinIO's S3 API (9000), the MinIO console (9001), Keycloak (8080) and the
BFF (8000) must **never** be reachable from the internet. The compose publishes them to
the stack's private IP only.

### 4c. On the stack VM (via the edge as jump host)

The stack has no public IP, so SSH through the edge:

```bash
ssh -J root@167.233.190.87 root@10.0.1.20

# then, on the stack:
cd /opt/ftm/deploy
docker compose -f docker-compose.stack.yaml ps        # all services Up / healthy
docker compose -f docker-compose.stack.yaml logs -f worker
docker compose -f docker-compose.stack.yaml logs keycloak | tail -50
```

`minio-init` is a one-shot job — `Exited (0)` is the correct state for it, not a failure.

### 4d. Functional smoke test (in the browser)

Log in at `https://ftm-followup-checkup.duckdns.org` as `paciente1` / `paciente1` and walk
the full path: **login (PKCE S256) → accept consent → record → upload → metrics → report**.
This is the only check that exercises the presigned-URL round trip through the edge, which
is the most fragile part of the topology.

---

## 5. Tear a demo DOWN (data + IP + DNS + edge survive)

```bash
terraform -chdir=terraform/hetzner/stack destroy
```

Only the stack VM is destroyed. Volume, floating IP, DNS, private network and the edge VM
remain (`prevent_destroy` guards + separate state). Idle billing: volume + floating IP +
edge VM (~€5–7/mo).

Bringing it back up is step 3 again — the data volume is re-attached and re-mounted, so
patients, recordings and metrics survive the cycle.

---

## 6. Backups

Hetzner has no native Terraform volume-snapshot schedule. Take a manual snapshot
before/after significant demos:

```bash
hcloud volume create-snapshot ftm-prod-data --description "pre-demo $(date +%F)"
hcloud image list --type snapshot            # review
```

This is the real safeguard against accidental data loss — NOT multi-AZ. Keep a small
retention (e.g. last 3) and prune older ones.

---

## 7. Troubleshooting

### Certbot fails: "unauthorized" or "DNS problem"

The domain does not resolve to the floating IP yet. `dig +short <domain>` must return the
floating IP. DuckDNS propagation can lag a few minutes. Re-run
`/usr/local/bin/ftm-issue-cert.sh` — it is idempotent.

### Login redirects, then fails / "Invalid parameter: redirect_uri"

The Keycloak realm's `frontendUrl` and the `ftm-web` client's redirect URIs still point at
the old domain. `KC_HOSTNAME` comes from `${DOMAIN}` in the compose, so the *server* knows
the domain — but the **realm-export.json** carries the client config, and it is imported
only on first boot into an empty database.

Fix it with `kcadm.sh`, or correct `deploy/keycloak/realm-export.json` and re-import into a
fresh volume. Changing the domain therefore always means: update the `domain` var in all
three layers → re-issue the cert → update the realm. To patch the client in place, open an
authenticated `kcadm` shell first (§8), then:

```bash
$KC update clients/<CLIENT_ID> -r ftm \
  -s 'redirectUris=["https://<new-domain>/*"]' \
  -s 'webOrigins=["https://<new-domain>"]' \
  -s 'rootUrl=https://<new-domain>' -s 'baseUrl=https://<new-domain>'
```

### 502 Bad Gateway on `/api` or `/realms`

The edge cannot reach the stack over the private network. In order:

```bash
ssh root@167.233.190.87
curl -fsS http://10.0.1.20:8000/health          # BFF reachable from the edge?
curl -fsS http://10.0.1.20:8080/realms/ftm      # Keycloak reachable?
```

If these fail, the stack is still booting (cloud-init/image pulls), or a service is
crash-looping. Check `docker compose ps` on the stack (§4c). If nginx is proxying to the
wrong address, confirm `__STACK_PRIVATE_IP__` was actually substituted:
`ssh root@$EDGE 'grep proxy_pass /etc/nginx/sites-available/ftm'`.

### Stack VM boots but the volume is not mounted

The LUKS passphrase in `secrets.sops.yaml` does not match the one the volume was
encrypted with, or SOPS decryption failed (wrong/missing `TF_VAR_age_private_key`).
Check cloud-init on the stack:

```bash
ssh -J root@167.233.190.87 root@10.0.1.20 'cloud-init status --long; journalctl -u cloud-final --no-pager | tail -40'
```

Never reformat the volume to "fix" this — that destroys the patient data.

### Recording upload returns 403 from `/ftm-recordings/`

Presigned S3v4 signatures are computed over the exact public host and path
(`S3_PUBLIC_ENDPOINT_URL = https://<domain>`). The nginx `location /ftm-recordings/` block
must forward **without rewriting the path** — any rewrite invalidates the signature. If
the bucket or scoped user is missing instead, re-run the one-shot init:
`docker compose -f docker-compose.stack.yaml up minio-init`.

---

## 8. Keycloak administration — use `kcadm.sh`, not the web console

Keycloak is administered with the official CLI (`kcadm.sh`) from inside the container,
**not** the web admin console. This is a deliberate architectural choice for this deploy:

- The admin console (`/admin`) is **not** proxied by the public edge — it is attack
  surface and its inline bootstrap scripts are blocked by the edge's strict CSP
  (`default-src 'self'`), which shows as a permanent "Loading the Administration Console".
- Even over an SSH tunnel the console does not work: `keycloak.js` loads a hidden OIDC
  *login-status-iframe* that frames the public frontend, which the edge blocks with
  `frame-ancestors 'none'` (correct anti-clickjacking for the clinical SPA). That
  iframe is a client-side `keycloak.js` init option baked into the console bundle — not
  a server or realm setting — so it cannot be toggled off from config.

`kcadm.sh` sidesteps all of it: it talks to Keycloak over localhost inside the
container, so no edge, no CSP, no iframe, no browser tunnel.

**Open a shell in the container and authenticate once per session:**

```bash
# On the stack VM
cd /opt/ftm/deploy
docker compose --env-file /run/ftm-secrets/.env -f docker-compose.stack.yaml exec keycloak bash

# Inside the container — define the shorthand used by every command in this section
KC=/opt/keycloak/bin/kcadm.sh

# Authenticate — use the KC_ADMIN_USER / KC_ADMIN_PASSWORD from secrets.sops.yaml
$KC config credentials \
  --server http://localhost:8080 --realm master \
  --user <KC_ADMIN_USER> --password '<KC_ADMIN_PASSWORD>'
```

The `$KC` shorthand and the authenticated session last for that container shell only —
re-run both if you exit and come back. All commands below target the **`ftm`** realm
(`-r ftm`).

**Users — create, delete, list:**

```bash
# List users (id + username + email)
$KC get users -r ftm --fields id,username,email

# Create a user (enabled, with email)
$KC create users -r ftm \
  -s username=nuevo.medico -s email=nuevo.medico@ftm.local \
  -s enabled=true -s emailVerified=true

# Delete a user (needs the id from the list above)
$KC delete users/<USER_ID> -r ftm
```

**Reset a password:**

```bash
# Temporary=false → the user is NOT forced to change it at next login
$KC set-password -r ftm --username medico1 --new-password 'NewStrongPass123' --temporary=false
```

**Roles — assign / remove realm roles:**

```bash
# List available realm roles
$KC get-roles -r ftm --available --uusername medico1

# Assign a realm role (e.g. medical)
$KC add-roles -r ftm --uusername medico1 --rolename medical

# Remove a realm role
$KC remove-roles -r ftm --uusername medico1 --rolename medical

# Show a user's effective realm roles
$KC get-roles -r ftm --uusername medico1 --effective
```

**Clients — review:**

```bash
# List clients (id + clientId)
$KC get clients -r ftm --fields id,clientId

# Inspect one client (e.g. ftm-web) — redirect URIs, mappers, flags
$KC get clients -r ftm -q clientId=ftm-web
```

> To reset the **master admin** password itself (the account above), use
> `$KC set-password -r master --username <KC_ADMIN_USER> --new-password '...' --temporary=false`.

**Gotcha — the bootstrap admin only applies to an empty DB.** `KC_BOOTSTRAP_ADMIN_*`
are honoured only the first time Keycloak starts against an empty `pg-keycloak` volume.
On a persistent volume, changing the password in SOPS does **not** update the existing
admin. To reset it (destroys only the Keycloak DB — app data and MinIO are on separate
volumes, and the `ftm` realm is re-imported from `realm-export.json` on next boot):

```bash
# On the stack VM, in /opt/ftm/deploy. The .env lives on tmpfs — pass it explicitly.
docker compose --env-file /run/ftm-secrets/.env -f docker-compose.stack.yaml stop keycloak postgres-keycloak
docker compose --env-file /run/ftm-secrets/.env -f docker-compose.stack.yaml rm -f keycloak postgres-keycloak
rm -rf /mnt/ftm-data/pg-keycloak/*
docker compose --env-file /run/ftm-secrets/.env -f docker-compose.stack.yaml up -d keycloak
```

> Any manual `docker compose` on the stack VM **must** pass
> `--env-file /run/ftm-secrets/.env`. The decrypted secrets live on tmpfs (RAM), not in
> the compose directory; without the flag every variable resolves to an empty string and
> the command fails with `invalid ip address:` on the MinIO port binding.

---

## Security notes

- **tfstate is sensitive.** The stack layer's state contains the age key (passed via
  metadata). It is gitignored; for real operation migrate to an encrypted remote backend
  (see `terraform/hetzner/persistent/backend.tf`). Do not share the state file.
- **Rotate secrets** by re-encrypting `secrets.sops.yaml` and recreating the stack VM.
  Rotate after the project is handed in, since the encrypted file lives in the repo history.
- **Never publish stack services to `0.0.0.0`.** The compose binds them to
  `${STACK_PRIVATE_IP}`; the MinIO console (`:9001`) is never published at all.
- **The Keycloak admin console is not public.** The edge proxies only `/realms`,
  `/resources` and `/js`; administer with `kcadm.sh` inside the container (§8). Do not add
  `/admin` back to the nginx regex, and do not add
  `'unsafe-inline'` or relax `frame-ancestors` in the CSP to make the console load — that
  weakens XSS / clickjacking protection for the whole clinical SPA.
- **Voice recordings are GDPR special-category data.** Two distinct controls, against two
  distinct threats: the no-public-IP stack and private-network-only access keep them **out of
  reach from the internet**; the LUKS-encrypted volume protects them **at rest**, against
  physical disk access or the provider reassigning the volume. Hetzner does not hold the LUKS
  key. Do not weaken either one for convenience.

---

## Annex A — Operator SSH access

Port 22 on the edge is **not open to the internet**. The Hetzner firewall only accepts SSH
from the operator's IP, set through `operator_ssh_cidrs`. Ports 80 and 443 stay open — the
application is public; only the management path is restricted.

**Why it is closed.** With `0.0.0.0/0` the edge logged **152,017 failed SSH attempts in 5
days** (~30k/day of sustained brute force). No compromise — `sshd` only accepts public-key
auth — but it is needless attack surface. See
[`doc/audit/audit_infra_20260719/AUDIT_REPORT.md`](../doc/audit/audit_infra_20260719/AUDIT_REPORT.md).

### Which steps require it

| Step | Why |
|---|---|
| [§2c Build and deploy the frontend](#2c-build-and-deploy-the-frontend) | `rsync` writes `dist/` to `/var/www/ftm` on the edge |
| [§2b Install the routing vhost](#2b-install-the-routing-vhost) | `scp` of the nginx config |
| [§3a Apply pending migrations](#3a-apply-pending-migrations) | `docker exec` on the stack, reached through the edge |
| [§4c Checks on the stack VM](#4c-on-the-stack-vm-via-the-edge-as-jump-host) | The stack has no public IP |
| `deploy/ftm-status.sh` | Reads all three layers through the edge |

### Symptom of a stale CIDR

The operator IP is usually **dynamic (DHCP)**, so it changes. When it does, every command
above hangs and then times out:

```
ssh: connect to host 167.233.190.87 port 22: Connection timed out
```

Public endpoints (`/api/health`, the frontend) keep working — the application is unaffected.
Only management access is lost.

### Reopening it

**No risk of locking yourself out permanently.** The firewall is managed through the Hetzner
**API**, not over SSH, so Terraform can always reach it. The management plane and the access
plane are independent — a direct benefit of keeping the firewall in IaC.

```bash
curl -s ifconfig.me          # your current public IP

terraform -chdir=terraform/hetzner/edge apply \
  -var='operator_ssh_cidrs=["<new-ip>/32"]' \
  -var="ssh_public_key=$(cat ~/.ssh/id_ed25519.pub)" \
  -var="domain=ftm-followup-checkup.duckdns.org" \
  -var="ssl_cert_email=<your-email>"
```

Takes about 5 seconds and does not restart the VM — it only rewrites the firewall rule.
`TF_VAR_hcloud_token` must be exported (§0).

> On an unstable connection, a `/24` (`188.26.193.0/24`) survives IP changes within the same
> ISP range and still blocks essentially all scanning. A `/32` is stricter and preferable
> whenever the IP is stable.

### Convenience: SSH agent and jump host

Every command above authenticates twice (edge + stack). Load the key once per session:

```bash
eval "$(ssh-agent -s)" && ssh-add ~/.ssh/id_ed25519
```

Optional — `~/.ssh/config` so `ssh ftm-stack` works without the explicit jump. The stack's
host key changes on every demo cycle, hence `StrictHostKeyChecking no` **for the stack
only**; never for the edge, which is the internet-facing machine:

```
Host ftm-edge
    HostName 167.233.190.87
    User root

Host ftm-stack
    HostName 10.0.1.20
    User root
    ProxyJump ftm-edge
    UserKnownHostsFile /dev/null
    StrictHostKeyChecking no
```

---

## Annex B — Pinning the API image

`postgres`, `keycloak` and `minio` are pinned by digest in `docker-compose.stack.yaml`, so
their versions are fixed. The API is not: it resolves through
`${API_IMAGE:-...api:latest}`.

**Why `:latest` is a problem here.** The stack VM is destroyed and recreated on every demo
cycle, and each boot pulls the image afresh. If `main` was pushed in between, the same
`terraform apply` silently brings up different code. Nothing in the deploy records what
actually ran.

### Producing a version tag

CI publishes `api:<sha>` on every push to `main`, and `api:vX.Y.Z` when a version tag is
pushed. **The tag trigger must already be on `main`** — GitHub reads the workflow from the
commit the tag points at, so tagging a commit older than the trigger does nothing.

```bash
git checkout main && git pull
git tag v1.0.2
git push origin v1.0.2

gh run list --workflow=deploy.yml --limit 3    # a run whose BRANCH is v1.0.2
```

A version tag publishes `api:vX.Y.Z` and deliberately does **not** move `latest`, so
re-tagging an older release cannot overwrite what `main` points at.

### Deploying a pinned image

```bash
terraform -chdir=terraform/hetzner/stack apply \
  -var="api_image=ghcr.io/josepcal/tfm_rehab_followup_checkup/api:v1.0.2" \
  ... rest of the vars
```

Cloud-init writes `API_IMAGE` into the stack `.env` **only when the variable is non-empty**;
left empty, the compose default applies and behaviour is unchanged.

### Verifying what is actually running

```bash
./deploy/ftm-status.sh      # see the "image versions" block
```

It prints the tag and the resolved digest per container. The tag says what was requested;
the digest says what is running. For a pinned deploy, `deploy-bff-1` and `deploy-worker-1`
must show `api:vX.Y.Z` rather than `:latest`.

> A digest (`...api@sha256:...`) works in `api_image` too and is stricter still — it cannot
> be re-pointed at all. A version tag is preferred for a release because it is readable and
> matches the tag in the repository.
