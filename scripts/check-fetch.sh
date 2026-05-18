#!/usr/bin/env bash
# Check 3/5: POST /fetch/sync against a real, stable URL.

source "$(dirname "$0")/_lib.sh"

TARGET="${SMOKE_FETCH_URL:-https://example.com}"
echo "═══ C. POST ${BASE_URL}/fetch/sync against ${TARGET} ═══"

RESP=$(hcurl -X POST \
    -H 'Content-Type: application/json' \
    -d "$(jq -nc --arg u "$TARGET" '{url:$u}')" \
    "${BASE_URL}/fetch/sync" || echo '{"status":"http-error"}')

STATUS=$(echo "$RESP" | jq -r '.status // "?"' 2>/dev/null || echo "non-json")
case "$STATUS" in
    ok)
        TITLE=$(echo "$RESP" | jq -r '.title // empty')
        TEXT_LEN=$(echo "$RESP" | jq -r '.text // "" | length')
        MS=$(echo "$RESP" | jq -r '.ms // 0')
        echo "  title:    $TITLE"
        echo "  text len: $TEXT_LEN chars"
        echo "  ms:       $MS"
        echo
        ok "fetch succeeded"
        ;;
    blocked-by-robots|blocked-by-ssrf-gate)
        warn "fetch blocked: $STATUS — try a different SMOKE_FETCH_URL"
        echo "$RESP" | jq .
        exit 2
        ;;
    *)
        fail "fetch failed: status=$STATUS"
        echo "$RESP" | jq . 2>/dev/null || echo "$RESP"
        exit 2
        ;;
esac
