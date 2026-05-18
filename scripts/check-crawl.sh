#!/usr/bin/env bash
# Check 5/5: POST /crawl + GET /crawl/{id} lifecycle against a stable site.
# Conservative defaults — max_depth=1, max_pages=3 — to finish quickly.

source "$(dirname "$0")/_lib.sh"

TARGET="${SMOKE_CRAWL_URL:-https://example.com}"
MAX_PAGES="${SMOKE_CRAWL_MAX_PAGES:-3}"
TIMEOUT="${SMOKE_CRAWL_TIMEOUT_S:-60}"

echo "═══ E. POST ${BASE_URL}/crawl (seed=${TARGET}, max_pages=${MAX_PAGES}) ═══"

START_RESP=$(hcurl -X POST \
    -H 'Content-Type: application/json' \
    -d "$(jq -nc --arg u "$TARGET" --arg n "$MAX_PAGES" \
        '{url:$u, max_depth:1, max_pages:($n|tonumber), same_domain_only:true}')" \
    "${BASE_URL}/crawl" || echo '{}')

JOB_ID=$(echo "$START_RESP" | jq -r '.job_id // empty')
if [[ -z "$JOB_ID" ]]; then
    fail "no job_id in /crawl response"
    echo "$START_RESP" | jq . 2>/dev/null || echo "$START_RESP"
    exit 2
fi
echo "  job_id: $JOB_ID"

# Poll until terminal or timeout.
DEADLINE=$(( $(date +%s) + TIMEOUT ))
LAST_STATE=""
while :; do
    if [[ $(date +%s) -gt $DEADLINE ]]; then
        fail "timeout after ${TIMEOUT}s. Last state: $LAST_STATE"
        hcurl "${BASE_URL}/crawl/${JOB_ID}" | jq . >&2
        exit 2
    fi
    SNAP=$(hcurl "${BASE_URL}/crawl/${JOB_ID}")
    STATE=$(echo "$SNAP" | jq -r '.status // "?"')
    LAST_STATE="$STATE"
    case "$STATE" in
        completed)
            PAGES=$(echo "$SNAP" | jq -r '.pages_fetched // 0')
            ERRORS=$(echo "$SNAP" | jq -r '.error_count // 0')
            echo "  pages_fetched: $PAGES"
            echo "  errors:        $ERRORS"
            echo
            if [[ "$PAGES" -ge 1 ]]; then
                ok "crawl completed; fetched $PAGES page(s)"
            else
                warn "crawl completed but no pages fetched. Possible robots/SSRF block."
                echo "$SNAP" | jq .
            fi
            exit 0
            ;;
        failed|cancelled)
            fail "crawl terminal: $STATE"
            echo "$SNAP" | jq .
            exit 2
            ;;
        queued|running)
            printf "  %s " "$STATE"
            sleep 3
            ;;
        *)
            fail "unexpected status '$STATE'"
            echo "$SNAP" | jq .
            exit 2
            ;;
    esac
done
