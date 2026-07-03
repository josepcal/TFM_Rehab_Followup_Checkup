# FTM Production Rollout — Operator Runbook

Ephemeral deploy on Hetzner: an always-on **edge** VM (nginx + floating IP) plus an
on-demand **stack** VM (keycloak, postgres×2, minio, bff, worker) with **no public IP**,
joined over a private network. Data lives on a persistent encrypted volume.

Topology and rationale: see `openspec/tfm-prod-rollout.md` (proposal) and
`openspec/design/tfm-prod-rollout.md` (design).

---

## 0. One-time prerequisites

```bash
export TF_VAR_hcloud_token='<hetzner-api-token>'        # never commit
export TF_VAR_age_private_key="$(cat age.key)"          # your age private key
```

- Generate an age keypair: `age-keygen -o age.key` (public key printed as `age1...`).
- Put the public key in `deploy/.sops.yaml` (replace the placeholder).
- Choose a domain (e.g. DuckDNS `ftm-demo.duckdns.org`).

### Encrypt the secrets (once, and on rotation)

```bash
cp deploy/secrets.sops.yaml.example /tmp/secrets.plain.yaml
# edit /tmp/secrets.plain.yaml with real values (incl. LUKS_PASSPHRASE)
sops --encrypt --age age1YOURPUBKEY /tmp/secrets.plain.yaml > deploy/secrets.sops.yaml
shred -u /tmp/secrets.plain.yaml
git add deploy/secrets.sops.yaml   # safe: values are encrypted
```

---

## 1. Persistent layer (apply ONCE, then leave forever)

```bash
terraform -chdir=terraform/hetzner/persistent init
terraform -chdir=terraform/hetzner/persistent apply -var="domain=ftm-demo.duckdns.org"
```

Creates: floating IP, encrypted-capable data volume, private network, subnet. All
`prevent_destroy` + `delete_protection`. **Note the floating IP** from the output.

### Point DNS at the floating IP

Set the domain's A record → floating IP (e.g. update DuckDNS). Wait for it to resolve.

---

## 2. Edge layer (apply ONCE, always on)

```bash
terraform -chdir=terraform/hetzner/edge init
terraform -chdir=terraform/hetzner/edge apply \
  -var='operator_ssh_cidrs=["<your-ip>/32"]' \
  -var="ssh_public_key=$(cat ~/.ssh/id_ed25519.pub)" \
  -var="domain=ftm-demo.duckdns.org" \
  -var="ssl_cert_email=you@example.com"
```

After it boots and DNS resolves, issue the TLS cert (once):

```bash
ssh root@<floating-ip> /usr/local/bin/ftm-issue-cert.sh
```

Then install the real routing vhost (`deploy/nginx/ftm.conf`) on the edge, replacing
`__DOMAIN__` and `__STACK_PRIVATE_IP__` (10.0.1.20), and reload nginx. Copy the built
Vite `dist/` to `/var/www/ftm` on the edge.

---

## 3. Bring a demo UP (stack layer)

```bash
terraform -chdir=terraform/hetzner/stack init
terraform -chdir=terraform/hetzner/stack apply \
  -var="ssh_public_key=$(cat ~/.ssh/id_ed25519.pub)" \
  -var="repo_url=<git-url>" \
  -var="repo_ref=<branch-or-tag>" \
  -var="domain=ftm-demo.duckdns.org"
```

The stack VM boots with **no public IP**, mounts the LUKS-encrypted volume, decrypts
secrets to tmpfs, and starts the compose. Reachable only from the edge over the private
network.

Smoke test (in the browser): login (PKCE S256) → record → metrics → report.

---

## 4. Tear a demo DOWN (data + IP + DNS + edge survive)

```bash
terraform -chdir=terraform/hetzner/stack destroy
```

Only the stack VM is destroyed. Volume, floating IP, DNS, private network and the edge VM
remain (`prevent_destroy` guards + separate state). Idle billing: volume + floating IP +
edge VM (~€5–7/mo).

---

## 5. Backups (task 1.6 — do this manually)

Hetzner has no native Terraform volume-snapshot schedule. Take a manual snapshot before/
after significant demos:

```bash
# via hcloud CLI
hcloud volume create-snapshot ftm-prod-data --description "pre-demo $(date +%F)"
```

This is the real safeguard against accidental data loss — NOT multi-AZ. Keep a small
retention (e.g. last 3) and prune older ones.

---

## Security notes

- **tfstate is sensitive.** The stack layer's state contains the age key (passed via
  metadata). It is gitignored; for real operation migrate to an encrypted remote backend
  (see `terraform/hetzner/persistent/backend.tf`). Do not share the state file.
- **Verify isolation after apply:** from outside, `nmap <floating-ip>` → only 443 (80
  redirect). The stack VM has no public IP to scan.
- **Rotate secrets** by re-encrypting `secrets.sops.yaml` and recreating the stack VM.
- **Domain change** (e.g. DuckDNS → real domain): update `domain` var, re-issue cert,
  and update Keycloak realm `frontendUrl` + `ftm-web` redirect URIs, or login breaks.
