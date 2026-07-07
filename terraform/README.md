# Deploying FTM on Hetzner

> 🇪🇸 [Versión en español](README_ES.md)

Ephemeral, cost-conscious production deploy of the FTM rehab follow-up system on
Hetzner Cloud. Three Terraform layers you apply in order; the **stack** (the app +
biometric data) has **no public IP** and is reachable only through an always-on
**edge** VM. Voice recordings are GDPR special-category data — the architecture keeps
them off the public internet by construction.

> This README covers the Terraform layers and the manual post-apply steps.
> For the day-to-day up/down demo workflow and secret encryption, see
> [`../deploy/RUNBOOK.md`](../deploy/RUNBOOK.md).

## Architecture at a glance

```
Internet ──HTTPS──> edge VM (public IP, nginx+TLS)  ──private net──> stack VM (NO public IP)
                    167.233.190.87  10.0.1.10                        10.0.1.20
                    · serves frontend                                · keycloak, postgres×2,
                    · proxies /api, /realms, /ftm-recordings         ·   minio, bff, worker
                    · NAT gateway for the stack's egress             · LUKS-encrypted volume
```

| Layer | Lifetime | Holds | Destroyable? |
|-------|----------|-------|--------------|
| `persistent` | forever | floating IP, data volume, private network, NAT route | **No** (`prevent_destroy`) |
| `edge` | always-on | nginx VM (cpx22), TLS cert, NAT gateway | Yes, but rarely |
| `stack` | ephemeral | app containers (cpx32), no public IP | Yes — this is the "up/down" layer |

## Prerequisites

- A Hetzner Cloud project + API token (read/write).
- `terraform >= 1.5`, `hcloud` CLI, `sops` + `age` installed locally.
- An SSH keypair (`ssh-keygen -t ed25519`).
- A domain pointing at the floating IP (DuckDNS works; see step 4).
- Encrypted secrets: `deploy/secrets.sops.yaml` (see [`../deploy/RUNBOOK.md`](../deploy/RUNBOOK.md)).

```bash
export TF_VAR_hcloud_token='<your-hetzner-token>'
```

## Quick path

Apply the layers **in order**. Each depends on the previous via read-only remote state.

```bash
DOMAIN=ftm-followup-checkup.duckdns.org
SSH_PUB="$(cat ~/.ssh/id_ed25519.pub)"

# 1. persistent — floating IP, volume, network, NAT route (apply ONCE)
terraform -chdir=hetzner/persistent init
terraform -chdir=hetzner/persistent apply -var="domain=$DOMAIN"

# 2. Point DNS at the floating IP (see output floating_ip_address), then:

# 3. edge — always-on nginx VM + NAT gateway
terraform -chdir=hetzner/edge init
terraform -chdir=hetzner/edge apply \
  -var="domain=$DOMAIN" \
  -var="ssh_public_key=$SSH_PUB" \
  -var='operator_ssh_cidrs=["<your-ip>/32"]' \
  -var="ssl_cert_email=you@example.com"

# 4. stack — the ephemeral app (repeat this destroy/apply per demo)
terraform -chdir=hetzner/stack init
terraform -chdir=hetzner/stack apply \
  -var="domain=$DOMAIN" \
  -var="ssh_public_key=$SSH_PUB" \
  -var="age_private_key=$(cat ~/path/to/age.key)" \
  -var="repo_url=https://github.com/josepcal/TFM_Rehab_Followup_Checkup.git"
```

## Required variables per layer

Everything else has a sensible default (server types, IPs, location `nbg1`).

| Layer | Required `-var` |
|-------|-----------------|
| `persistent` | `hcloud_token`*, `domain` |
| `edge` | `hcloud_token`*, `domain`, `ssh_public_key`, `operator_ssh_cidrs`, `ssl_cert_email` |
| `stack` | `hcloud_token`*, `domain`, `ssh_public_key`, `age_private_key`, `repo_url` |

\* `hcloud_token` is read from `TF_VAR_hcloud_token` — never pass it on the command line.

## Manual steps after the first stack apply

The stack cloud-init installs and boots everything, but **three things are one-time
manual steps** on a *fresh* volume (they persist across later stack destroy/apply):

1. **Issue the TLS cert** on the edge (once DNS resolves to the floating IP):
   ```bash
   ssh root@<floating-ip> /usr/local/bin/ftm-issue-cert.sh
   ```
   Then scp `deploy/nginx/ftm.conf` (with `__DOMAIN__`/`__STACK_PRIVATE_IP__`
   substituted) to `/etc/nginx/sites-available/ftm` and `systemctl reload nginx`.
   Copy the built `web/dist/*` to `/var/www/ftm`.

2. **Run DB migrations** as the DB *owner* (not the bff's runtime role), reading
   credentials from the rendered `.env` on the stack VM:
   ```bash
   ssh -J root@<floating-ip> root@10.0.1.20 'docker exec \
     -e DATABASE_URL=postgresql://$ADMIN_U:$ADMIN_P@postgres-app:5432/$DB \
     -e FTM_APP_DB_PASSWORD=$APP_P \
     deploy-bff-1 sh -c "cd /app/db-migrations && alembic upgrade head"'
   ```
   The `minio-init` container creates the bucket + scoped user automatically.

3. **Verify** end-to-end (see checklist below).

> These run manually today. Wiring them idempotently into the stack cloud-init is
> the documented next step toward a fully hands-off `terraform apply`.

## Gotchas (learned the hard way)

| Symptom | Cause | Fix (already in the code) |
|---------|-------|---------------------------|
| Stack can't `apt install` / `git clone` | No-public-IP VM has no internet | NAT: `persistent` network route → edge; edge masquerades egress |
| `Network is unreachable` from stack | Hetzner DHCP gives no default route | cloud-init `bootcmd`: `ip route ... via 10.0.0.1 onlink` (gateway is the **network** first host, `10.0.0.1`, not the subnet's) |
| `Could not resolve host` | systemd-resolved has no uplink | drop-in sets Hetzner DNS `185.12.64.1` |
| docker-compose vars all blank | `sops -d` emitted YAML | decrypt with `--output-type dotenv` |
| Keycloak/MinIO port not published | container only on `internal:true` net | also attach `egress_net`; bind to `${STACK_PRIVATE_IP}` |
| Presigned upload 403/502 | MinIO signs with internal host / bucket+user missing | `S3_PUBLIC_ENDPOINT_URL` via edge proxy; `minio-init` creates bucket+user |
| Patients see others' data risk | bff connected as the table **owner** (bypasses RLS) | owner = `ADMIN_DB_USER`; bff connects as non-owner `ftm_app` |
| `server type cx22 not found` | Hetzner retired `cx*` | use `cpx22`/`cpx32` |

## Post-deploy verification checklist

- [ ] `terraform -chdir=hetzner/persistent apply` shows the volume with
      `delete_protection = true` (protects biometric data).
- [ ] `ssh -J root@<fip> root@10.0.1.20 'ping -c2 1.1.1.1'` succeeds (NAT works).
- [ ] `docker compose ... ps` shows 6 containers up; postgres×2 + minio healthy.
- [ ] Browser: login (Keycloak) → patient sees only own data (RLS).
- [ ] Browser: record → upload (200) → analyze → metrics appear.
- [ ] `nmap <floating-ip>` shows only 80/443; the stack VM has no public IP to scan.
- [ ] Edge SSH firewall restricted from `0.0.0.0/0` to the operator IP.

## Tearing down a demo

```bash
terraform -chdir=hetzner/stack destroy -var="domain=$DOMAIN" -var=...   # same vars as apply
```

Only the stack VM is destroyed. The volume, floating IP, DNS, network and edge
survive. Bringing it back up = re-run the stack apply; data persists on the volume.
