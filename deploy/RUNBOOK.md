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

---

## 3. Bring a demo UP (stack layer)

```bash
terraform -chdir=terraform/hetzner/stack init
terraform -chdir=terraform/hetzner/stack apply \
  -var="ssh_public_key=$(cat ~/.ssh/id_ed25519.pub)" \
  -var="repo_url=<git-url>" \
  -var="repo_ref=<branch-or-tag>" \
  -var="domain=ftm-followup-checkup.duckdns.org"
```

The stack VM boots with **no public IP**, mounts the LUKS-encrypted volume at
`/mnt/ftm-data`, decrypts `secrets.sops.yaml` to tmpfs, renders `.env`, and starts the
compose. It is reachable only from the edge, over the private network.

Cloud-init takes a few minutes (image pulls, Keycloak realm import, MinIO bucket
provisioning). Proceed to verification rather than assuming it is up.

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

Fix in the Keycloak admin console (`https://<domain>/admin`, credentials from
`secrets.sops.yaml`), or correct `deploy/keycloak/realm-export.json` and re-import into a
fresh volume. Changing the domain therefore always means: update the `domain` var in all
three layers → re-issue the cert → update the realm.

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

## Security notes

- **tfstate is sensitive.** The stack layer's state contains the age key (passed via
  metadata). It is gitignored; for real operation migrate to an encrypted remote backend
  (see `terraform/hetzner/persistent/backend.tf`). Do not share the state file.
- **Rotate secrets** by re-encrypting `secrets.sops.yaml` and recreating the stack VM.
  Rotate after the project is handed in, since the encrypted file lives in the repo history.
- **Never publish stack services to `0.0.0.0`.** The compose binds them to
  `${STACK_PRIVATE_IP}`; the MinIO console (`:9001`) is never published at all.
- **Voice recordings are GDPR special-category data.** Two distinct controls, against two
  distinct threats: the no-public-IP stack and private-network-only access keep them **out of
  reach from the internet**; the LUKS-encrypted volume protects them **at rest**, against
  physical disk access or the provider reassigning the volume. Hetzner does not hold the LUKS
  key. Do not weaken either one for convenience.
