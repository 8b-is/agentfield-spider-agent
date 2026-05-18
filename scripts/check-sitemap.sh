#!/usr/bin/env bash
# Check 4/5: POST /sitemap/parse against a real sitemap.
# Default target is sitemaps.org's own sitemap (small, stable, exists).

source "$(dirname "$0")/_lib.sh"

TARGET="${SMOKE_SITEMAP_URL:-https://www.sitemaps.org/sitemap.xml}"
echo "═══ D. POST ${BASE_URL}/sitemap/parse against ${TARGET} ═══"

RESP=$(hcurl -X POST \
    -H 'Content-Type: application/json' \
    -d "$(jq -nc --arg u "$TARGET" '{url:$u, queue:false, max_urls:50}')" \
    "${BASE_URL}/sitemap/parse" || echo '{"errors":["http-error"]}')

COUNT=$(echo "$RESP" | jq -r '.count // 0' 2>/dev/null || echo 0)
ERRORS=$(echo "$RESP" | jq -r '.errors // [] | length' 2>/dev/null || echo 0)

echo "  urls discovered: $COUNT"
echo "  errors:          $ERRORS"

if [[ "$COUNT" -ge 1 ]]; then
    echo "  sample: $(echo "$RESP" | jq -r '.urls[0]')"
    echo
    ok "sitemap_parse found $COUNT URL(s)"
else
    fail "sitemap_parse returned 0 URLs"
    echo "$RESP" | jq . 2>/dev/null || echo "$RESP"
    exit 2
fi
