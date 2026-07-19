#!/usr/bin/env bash
# FTM deployment status probe.
#
# Reads the health of all three layers (persistent volume, edge, stack) from the
# operator machine. Everything is collected THROUGH the edge over SSH: the stack VM
# has no public IP and the data volume is LUKS-encrypted, so none of this is visible
# from the Hetzner console by design.
#
# Usage:  ./deploy/ftm-status.sh [domain] [edge-ip] [stack-private-ip]

set -uo pipefail

DOMAIN="${1:-ftm-followup-checkup.duckdns.org}"
EDGE="${2:-167.233.190.87}"
STACK="${3:-10.0.1.20}"

SSH_OPTS=(-o ConnectTimeout=10 -o BatchMode=yes)
# The stack VM is recreated on every demo cycle, so its host key changes. Skip
# known_hosts for it rather than training the operator to ignore key warnings.
# LogLevel=ERROR suppresses the "Permanently added ... to the list of known hosts"
# notice that /dev/null would otherwise emit on every single call.
STACK_SSH_OPTS=("${SSH_OPTS[@]}" -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no -o LogLevel=ERROR)

GREEN=$'\033[0;32m'; RED=$'\033[0;31m'; YELLOW=$'\033[0;33m'; BOLD=$'\033[1m'; OFF=$'\033[0m'

section() { printf '\n%s=== %s ===%s\n' "$BOLD" "$1" "$OFF"; }
ok()      { printf '  %s✓%s %s\n' "$GREEN" "$OFF" "$1"; }
bad()     { printf '  %s✗%s %s\n' "$RED" "$OFF" "$1"; }
warn()    { printf '  %s!%s %s\n' "$YELLOW" "$OFF" "$1"; }
info()    { printf '    %s\n' "$1"; }

edge_ssh()  { ssh "${SSH_OPTS[@]}" "root@$EDGE" "$@"; }
stack_ssh() { ssh "${SSH_OPTS[@]}" -J "root@$EDGE" "${STACK_SSH_OPTS[@]}" "root@$STACK" "$@"; }

# HTTP timing through the public domain. Reports time-to-first-byte, which is where
# latency actually shows up — the payloads here are tiny.
probe_http() {
    local label="$1" url="$2" out code ttfb
    out=$(curl -o /dev/null -s -m 15 -w '%{http_code} %{time_starttransfer}' "$url" 2>/dev/null)
    code="${out%% *}"; ttfb="${out##* }"
    if [ "$code" = "200" ]; then
        ok "$label — HTTP $code in ${ttfb}s"
    elif [ "$code" = "000" ]; then
        bad "$label — no response (timeout or DNS failure)"
    else
        warn "$label — HTTP $code in ${ttfb}s"
    fi
}

printf '%sFTM deployment status%s  —  %s\n' "$BOLD" "$OFF" "$(date '+%Y-%m-%d %H:%M:%S %Z')"
printf 'domain=%s  edge=%s  stack=%s\n' "$DOMAIN" "$EDGE" "$STACK"

# ---------------------------------------------------------------- public surface
section "PUBLIC SURFACE (through DNS + edge)"
probe_http "API health      " "https://$DOMAIN/api/health"
probe_http "Keycloak realm  " "https://$DOMAIN/realms/ftm"
probe_http "Frontend        " "https://$DOMAIN/"

resolved=$(getent hosts "$DOMAIN" 2>/dev/null | awk '{print $1; exit}')
if [ -n "$resolved" ]; then
    [ "$resolved" = "$EDGE" ] \
        && ok "DNS A record    — $DOMAIN -> $resolved" \
        || bad "DNS A record    — $DOMAIN -> $resolved (expected $EDGE)"
else
    bad "DNS A record    — $DOMAIN does not resolve"
fi

# ------------------------------------------------------------------------- edge
section "EDGE ($EDGE)"
if ! edge_ssh true 2>/dev/null; then
    bad "unreachable over SSH — everything below is unavailable"
else
    ok "SSH reachable"
    edge_ssh 'uptime | sed "s/^/    /"'
    info "$(edge_ssh "free -h | awk 'NR==2{print \"memory: \" \$3 \" used / \" \$2 \" total, \" \$7 \" available\"}'")"
    info "$(edge_ssh "df -h / | awk 'NR==2{print \"disk:   \" \$3 \" used / \" \$2 \" total (\" \$5 \" full)\"}'")"

    printf '\n  nginx:\n'
    if edge_ssh 'systemctl is-active --quiet nginx' 2>/dev/null; then
        ok "service active"
    else
        bad "service NOT active"
    fi
    info "TLS cert expiry: $(edge_ssh "openssl x509 -enddate -noout -in /etc/letsencrypt/live/$DOMAIN/fullchain.pem 2>/dev/null | cut -d= -f2" || echo 'not found')"
    printf '  recent nginx errors (last 5):\n'
    edge_ssh 'tail -n 5 /var/log/nginx/error.log 2>/dev/null | sed "s/^/    /"' || info "(none)"

    # SSH key logins do not land in wtmp (which `last` reads) — only TTY/console
    # sessions and reboots do. Accepted public-key auth is logged by sshd to the
    # journal, so read it there. Failed attempts are the intrusion signal worth
    # surfacing next to the successful ones.
    printf '\n  last SSH logins (accepted):\n'
    edge_ssh 'journalctl -u ssh -u sshd --no-pager -n 400 2>/dev/null | grep "Accepted" | tail -3 | sed "s/^/    /"' \
        || info "(none recorded)"
    failed=$(edge_ssh 'journalctl -u ssh -u sshd --since "5 days ago" --no-pager 2>/dev/null | grep -c "Failed password\|Invalid user"' 2>/dev/null)
    [ -n "${failed:-}" ] && [ "${failed:-0}" -gt 0 ] \
        && warn "$failed failed/invalid SSH attempts in the last 5 days" \
        || ok "no failed SSH attempts in the last 5 days"
    printf '  most recent failed attempts:\n'
    edge_ssh 'journalctl -u ssh -u sshd --no-pager 2>/dev/null | grep "Failed password\|Invalid user" | tail -3 | sed "s/^/    /"' \
        || info "(none recorded)"
fi

# ------------------------------------------------------------------------ stack
section "STACK ($STACK, via edge)"
if ! stack_ssh true 2>/dev/null; then
    bad "unreachable over SSH — stack is down or still provisioning"
    info "if you just ran terraform apply, cloud-init needs a few minutes"
else
    ok "SSH reachable"
    stack_ssh 'uptime | sed "s/^/    /"'
    info "$(stack_ssh "free -h | awk 'NR==2{print \"memory: \" \$3 \" used / \" \$2 \" total, \" \$7 \" available\"}'")"
    info "$(stack_ssh "df -h / | awk 'NR==2{print \"root:   \" \$3 \" used / \" \$2 \" total (\" \$5 \" full)\"}'")"

    # ------------------------------------------------- persistent encrypted volume
    printf '\n  persistent volume (/mnt/ftm-data):\n'
    if stack_ssh 'mountpoint -q /mnt/ftm-data' 2>/dev/null; then
        ok "mounted and unlocked"
        # MinIO stores the voice recordings here, so this is the volume that actually
        # grows over time. Warn before it becomes a problem rather than reporting a
        # number nobody reads.
        vol_pct=$(stack_ssh "df --output=pcent /mnt/ftm-data | tail -1 | tr -dc '0-9'" 2>/dev/null)
        vol_txt=$(stack_ssh "df -h /mnt/ftm-data | awk 'NR==2{print \$3 \" used / \" \$2 \" total\"}'" 2>/dev/null)
        if [ -n "${vol_pct:-}" ] && [ "${vol_pct:-0}" -ge 80 ] 2>/dev/null; then
            warn "usage:  $vol_txt (${vol_pct}% full — consider resizing the volume)"
        else
            info "usage:  $vol_txt (${vol_pct:-?}% full)"
        fi
        printf '    per-service footprint:\n'
        stack_ssh 'du -sh /mnt/ftm-data/* 2>/dev/null | sed "s/^/      /"'
    else
        bad "NOT mounted — LUKS unlock or cloud-init failed, data is unavailable"
    fi

    # ------------------------------------------------------------------ containers
    printf '\n  containers:\n'
    stack_ssh 'docker ps --format "    {{.Names}}\t{{.Status}}"' 2>/dev/null \
        | sed 's/\t/  —  /' || bad "docker not responding"

    # Only postgres-app, postgres-keycloak and minio declare a healthcheck in the
    # compose file. keycloak, bff and worker do not, so probe their endpoints from
    # inside the stack instead of trusting docker's status column.
    printf '\n  service probes (from inside the stack):\n'
    for probe in \
        "bff       |http://$STACK:8000/health" \
        "keycloak  |http://$STACK:8080/realms/ftm" \
        "minio     |http://$STACK:9000/minio/health/live"
    do
        name="${probe%%|*}"; url="${probe##*|}"
        code=$(stack_ssh "curl -o /dev/null -s -m 10 -w '%{http_code}' '$url'" 2>/dev/null)
        [ "$code" = "200" ] && ok "$name reachable (HTTP $code)" || bad "$name unreachable (HTTP ${code:-000})"
    done

    # ------------------------------------------------------- postgres connections
    # Two constraints shape the quoting here:
    #  - $POSTGRES_USER must expand INSIDE the container (it only exists there), so
    #    the psql invocation travels wrapped in `sh -c '...'` with the $ escaped.
    #  - The SQL must contain no single quote, or it would close that wrapper in
    #    transit. Hence `SHOW max_connections` rather than current_setting('...').
    printf '\n  postgres connections:\n'
    pg_query() {
        stack_ssh "docker exec $1 sh -c 'psql -U \"\$POSTGRES_USER\" -d \"\$POSTGRES_DB\" -tAc \"$2\"'" 2>/dev/null | tr -d ' \r'
    }
    for db in "app|deploy-postgres-app-1" "keycloak|deploy-postgres-keycloak-1"; do
        label="${db%%|*}"; cname="${db##*|}"
        used=$(pg_query "$cname" "SELECT count(*) FROM pg_stat_activity")
        max=$(pg_query "$cname" "SHOW max_connections")
        if [ -n "$used" ] && [ -n "$max" ]; then
            if [ "$used" -gt $(( max * 80 / 100 )) ] 2>/dev/null; then
                warn "$label — $used / $max connections (over 80%)"
            else
                ok "$label — $used / $max connections"
            fi
        else
            warn "$label — could not read connection stats"
        fi
    done

    printf '\n  recent bff errors (last 5):\n'
    stack_ssh 'docker logs --tail 200 deploy-bff-1 2>&1 | grep -iE "error|exception|traceback" | tail -5 | sed "s/^/    /"' \
        || info "(none)"
fi

printf '\n'
