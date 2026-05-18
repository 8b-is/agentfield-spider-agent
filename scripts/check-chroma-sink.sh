#!/usr/bin/env bash
# Check 6/6: chromadb sink — fetch a page, verify it lands in chromadb.
#
# Requires SPIDER_SINK_ENABLED=true + SPIDER_SINK_CHROMA_URL + SPIDER_SINK_COLLECTION
# in the spider-http container's environment. If sink env isn't set,
# script SKIPs cleanly.
#
# Pre-flight env vars (script reads them from the host shell OR from the
# compose container's env via `docker compose exec`):
#   SPIDER_SINK_CHROMA_URL    (e.g. http://chromadb:8000)
#   SPIDER_SINK_COLLECTION    (e.g. spider-fetched)
#   SMOKE_SINK_URL            target page to fetch (default https://example.com)
#
# Verification: after the fetch returns ok, this script queries
#   GET {SPIDER_SINK_CHROMA_URL}/api/v1/collections/{SPIDER_SINK_COLLECTION}/get
# with the document id (sha256 of the URL) and asserts the doc landed.

source "$(dirname "$0")/_lib.sh"

# Read sink env from inside the spider-http container if available
get_env() {
    local var="$1"
    if docker compose ps --services 2>/dev/null | grep -qx spider-http; then
        docker compose exec -T spider-http sh -c "echo \${$var:-}" 2>/dev/null | tr -d '\r' || echo ""
    else
        eval "echo \${$var:-}"
    fi
}

SINK_ENABLED="$(get_env SPIDER_SINK_ENABLED)"
SINK_URL="$(get_env SPIDER_SINK_CHROMA_URL)"
SINK_COLL="$(get_env SPIDER_SINK_COLLECTION)"
TARGET="${SMOKE_SINK_URL:-https://example.com}"

echo "═══ F. chromadb sink smoke ═══"
echo "  enabled:    $SINK_ENABLED"
echo "  chroma_url: ${SINK_URL:-<unset>}"
echo "  collection: ${SINK_COLL:-<unset>}"

if [[ "$SINK_ENABLED" != "true" && "$SINK_ENABLED" != "1" ]]; then
    echo "  SKIP: SPIDER_SINK_ENABLED is not true (current: '$SINK_ENABLED')."
    echo "  Set the SPIDER_SINK_* env vars on spider-http to test this surface."
    exit 0
fi
if [[ -z "$SINK_URL" || -z "$SINK_COLL" ]]; then
    fail "SPIDER_SINK_ENABLED is true but URL/COLLECTION env is missing."
    exit 2
fi

# Step 1: fetch a page via spider — this triggers the sink in run_and_record()
echo
echo "  1) POST /fetch/sync ${TARGET}"
FETCH_RESP=$(hcurl -X POST \
    -H 'Content-Type: application/json' \
    -d "$(jq -nc --arg u "$TARGET" '{url:$u}')" \
    "${BASE_URL}/fetch/sync")
FSTATUS=$(echo "$FETCH_RESP" | jq -r '.status // "?"')
FID=$(echo "$FETCH_RESP" | jq -r '.id // empty')

if [[ "$FSTATUS" != "ok" ]]; then
    fail "fetch failed (status=$FSTATUS) — sink can't run without an ok fetch"
    echo "$FETCH_RESP" | jq .
    exit 2
fi
echo "     ✓ fetch ok (id=$FID, $(echo "$FETCH_RESP" | jq -r '.text | length') chars)"

# Step 2: give the sink ~1s to write asynchronously (it's fire-and-forget per CLAUDE.md)
sleep 1

# Step 3: query chromadb for the document id
# Document id pattern (from spider/sinks/chroma.py): sha256(url)[:16] or similar.
# To avoid mirroring the hash logic here, query by `where: {url: TARGET}` metadata filter.
echo
echo "  2) query chromadb for doc with metadata.url=${TARGET}"

QUERY=$(jq -nc --arg u "$TARGET" '{where: {url: $u}, limit: 1, include: ["documents","metadatas"]}')
QUERY_RESP=$(curl -sS -X POST \
    -H 'Content-Type: application/json' \
    -d "$QUERY" \
    "${SINK_URL%/}/api/v1/collections/${SINK_COLL}/get" 2>/dev/null || echo '{"error":"http"}')

# chromadb returns {ids, documents, metadatas, ...} on success
HIT_COUNT=$(echo "$QUERY_RESP" | jq -r '.ids | length' 2>/dev/null || echo 0)

if [[ "$HIT_COUNT" -ge 1 ]]; then
    DOC_PREVIEW=$(echo "$QUERY_RESP" | jq -r '.documents[0] | .[0:120]' 2>/dev/null)
    METADATA=$(echo "$QUERY_RESP" | jq -c '.metadatas[0]' 2>/dev/null)
    echo "     ✓ doc found in chromadb"
    echo "     metadata: $METADATA"
    echo "     preview:  $DOC_PREVIEW..."
    echo
    ok "chromadb sink working end-to-end (fetch → chromadb)"
else
    fail "no doc with metadata.url=${TARGET} found in collection '${SINK_COLL}'"
    echo "  Possible causes:"
    echo "    1. sink failed silently (check spider-http logs for 'sink.exception')"
    echo "    2. collection name mismatch between spider and chromadb"
    echo "    3. sink embedding step errored (OpenRouter rate-limit / sentence-transformers OOM)"
    echo "    4. chromadb API shape differs (where-filter may need {\"\$eq\": ...} wrapper)"
    echo
    echo "  chromadb response:"
    echo "$QUERY_RESP" | jq . 2>/dev/null || echo "$QUERY_RESP"
    exit 2
fi
