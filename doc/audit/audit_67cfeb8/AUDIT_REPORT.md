# OWASP Top 10 Security Audit — FTM Rehab Follow-up

**Commit:** `67cfeb8` (`67cfeb81a7b001c00e9048e8f0a57d2e05589dc6`)
**Branch:** `feature/documentation`
**Scope:** web, api, terraform, deploy
**Date:** 2026-07-15

## Executive Summary

The codebase shows a high standard of security hygiene. RS256 is pinned, Postgres
Row-Level Security is enforced, there is a database-level anonymisation boundary,
SOPS-encrypted secrets, restrictive firewalls, and an audit log that records denied
BOLA/BFLA probes. Most of the OWASP Top 10 is well covered. The findings below are
ordered by severity.

**Status:** the single HIGH finding (#1, exposed Keycloak admin console) has been
**resolved** — see its Resolution note. The remaining findings are MEDIUM/LOW and are
documented as known trade-offs or minor hardening opportunities.

---

## Findings

### HIGH

#### 1. Keycloak admin console exposed to the internet — A05 (Security Misconfiguration) — ✅ RESOLVED

**File:** `deploy/nginx/ftm.conf:66`

```nginx
location ~ ^/(realms|resources|admin|js)/ {
    proxy_pass http://__STACK_PRIVATE_IP__:8080;
```

The regex included `admin`, so `https://<domain>/admin/` reached the Keycloak admin
console directly. OIDC login only needs `/realms/`, `/resources/` and `/js/`. The
`/admin/` path should not be public — it is attack surface (admin brute force, admin
console CVEs).

**Recommendation:** Remove `admin` from the public regex, or restrict `/admin/` to the
operator CIDR.

**✅ Resolution:** `admin` was removed from the nginx Keycloak `location` regex — the
edge now proxies only `/realms`, `/resources` and `/js`. The admin console is no longer
reachable from the internet. Administration is performed with `kcadm.sh` inside the
container (localhost, no edge, no CSP), documented in `deploy/RUNBOOK.md` under "Keycloak
administration". Serving the web console through the edge was deliberately rejected: its
inline scripts and OIDC login-status iframe are incompatible with the edge's strict CSP
(`default-src 'self'`, `frame-ancestors 'none'`), and relaxing the CSP to accommodate it
would weaken XSS/clickjacking protection for the whole clinical SPA.

---

### MEDIUM

#### 2. Bootstrap secrets travel via server metadata → land in tfstate — A02 / A05

**Files:** `terraform/hetzner/stack/cloud-init.yaml.tftpl:27-30` (age key),
lines 44-48 (LUKS passphrase derived from the same channel).

The `age_private_key` (which decrypts ALL SOPS secrets) is passed as a Terraform
variable and is serialised in `terraform.tfstate` in cleartext. The tfstate is NOT
committed (verified), but it lives on the local disk unencrypted and the remote
backend must be encrypted. The file's own comment acknowledges this as MVP debt.

**Recommendation:** Acceptable risk for a TFM, but document it explicitly. Longer term,
deliver the age key out-of-band (not through TF vars) and ensure remote state encryption.

#### 3. Default `database_url` ships a hardcoded password — A05 / A07

**File:** `api/app/config.py:12` — `thisIsMyFTMAppDBPassword123`.

It is a dev default and `get_settings()` forces Keycloak in prod, so it is not
exploitable if the deploy is correct — but an embedded credential default is a smell.

**Recommendation:** Make the default empty and fail loudly when unset in prod.

---

### LOW / Observations

#### 4. JWKS has no explicit refresh timeout — A08

**File:** `api/app/auth.py:27-29`. The `@lru_cache` over `_jwks()` is only cleared on an
unknown `kid`. Functionally correct, but rotating compromised IdP keys would propagate
slowly. Minor.

#### 5. LLM error handling / payloads not deeply audited — A10 (SSRF)

`api/app/ai/service.py` was not deeply reviewed. The DB-level boundary
(`ai_session()` → `ftm_ai`) is excellent and limits blast radius, but a dedicated pass
on `llm_api_base` handling would be worthwhile if A10 matters.

---

## What is done well (for the record)

- **A01 (Broken Access Control):** Postgres RLS + `require_role` + audit of denied access. Well above average.
- **A02 (Crypto Failures):** Fernet for PII, LUKS at-rest, SOPS for secrets, TLS 1.2+.
- **A03 (Injection):** All queries parameterised; the only f-string (`SET LOCAL ROLE`) uses a closed dict, not user input. Verified at `api/app/db.py:78`.
- **A05:** OpenAPI/docs disabled in prod, CSP + HSTS + `frame-ancestors 'none'`, restrictive firewalls, no CORS wildcard.
- **A07 (Auth):** RS256 pinned (blocks `alg=none`), issuer + audience validation, dev-mode blocked in prod.

## Verified evidence

- `terraform.tfstate` is git-ignored (not committed) across edge/persistent/stack.
- `deploy/secrets.sops.yaml` is genuinely SOPS-encrypted (`ENC[AES256_GCM,...]`).
- Stack firewall restricts ports 8000/8080/9000 to the edge private IP only.
- Edge firewall: 80/443 public, SSH restricted to `operator_ssh_cidrs`.
