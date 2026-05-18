#!/usr/bin/env bash
# Check 2/5: HTTP /health returns + redis is reachable from spider-http.

source "$(dirname "$0")/_lib.sh"

echo "═══ B. GET ${BASE_URL}/health ═══"
CODE=$(hcurl -o /tmp/spider_health.json -w "%{http_code}" "${BASE_URL}/health" || echo "000")
echo "  HTTP $CODE"

case "$CODE" in
    200)
        cat /tmp/spider_health.json | jq . 2>/dev/null || cat /tmp/spider_health.json
        echo
        ok "spider-http is serving"
        ;;
    000|502|503|504)
        fail "spider-http unreachable at ${BASE_URL}. Check: docker compose logs spider-http"
        exit 2
        ;;
    *)
        fail "unexpected HTTP $CODE — see /tmp/spider_health.json"
        exit 2
        ;;
esac
