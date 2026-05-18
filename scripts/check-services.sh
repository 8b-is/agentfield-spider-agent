#!/usr/bin/env bash
# Check 1/5: are all expected compose services Up?

source "$(dirname "$0")/_lib.sh"

echo "═══ A. compose ps ═══"
docker compose ps

# Hard requirement: at minimum spider-http + redis must be running.
# spider-agent (the AF skill surface) is optional for the HTTP smoke
# tests below but counts toward the full swarm wiring.
for s in spider-http redis; do
    state=$(docker compose ps --format json "$s" 2>/dev/null | head -1 | jq -r '.State' 2>/dev/null || echo "")
    if [[ "$state" != "running" ]]; then
        fail "$s is not running (State='$state')"
        echo "      Try: docker compose up -d $s && docker compose logs -f $s" >&2
        exit 2
    fi
done
echo
ok "spider-http + redis are up"
