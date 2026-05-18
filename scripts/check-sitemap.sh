#!/usr/bin/env bash
# Check 4/5: POST /sitemap/parse against real sitemaps.
#
# Default target list covers documentation sites + product pages of
# tools we actually use in the swarm. Operators can:
#   - override the whole list with SMOKE_SITEMAP_URLS (comma-separated)
#   - or override just one with SMOKE_SITEMAP_URL (legacy, single)
#   - or skip the multi-target loop entirely with SKIP_MULTI=1
#
# Edit the DEFAULT_TARGETS list below as the fleet's "regularly crawled"
# set evolves — these are the canonical seeds for our docs-RAG +
# feed-poll pipeline.

source "$(dirname "$0")/_lib.sh"

# Canonical sitemap set — domains we use mostly. Re-validate
# regularly; sitemap formats / locations occasionally change.
DEFAULT_TARGETS=(
    # Self / agentfield ecosystem
    "https://agentfield.ai/sitemap.xml"
    # Anthropic + Claude (we call Anthropic's API; docs change frequently)
    "https://docs.anthropic.com/sitemap.xml"
    # OpenRouter (we use it for cheap-tier model rotation)
    "https://openrouter.ai/sitemap.xml"
    # Cloudflare (Tunnel + Workers + AI dashboards)
    "https://developers.cloudflare.com/sitemap.xml"
    # Tailscale (our tailnet substrate)
    "https://tailscale.com/sitemap.xml"
    # Hermes-Agent (the runtime we wrap)
    "https://hermes-agent.nousresearch.com/sitemap.xml"
    # OpenClaw (NemoClaw sandbox guest)
    "https://docs.openclaw.ai/sitemap.xml"
    # Reference small-stable target — confirms the parser itself works
    "https://www.sitemaps.org/sitemap.xml"
)

# Selection logic
if [[ -n "${SMOKE_SITEMAP_URLS:-}" ]]; then
    IFS=',' read -ra TARGETS <<< "$SMOKE_SITEMAP_URLS"
elif [[ -n "${SMOKE_SITEMAP_URL:-}" ]]; then
    TARGETS=("$SMOKE_SITEMAP_URL")
elif [[ "${SKIP_MULTI:-0}" == "1" ]]; then
    TARGETS=("https://www.sitemaps.org/sitemap.xml")
else
    TARGETS=("${DEFAULT_TARGETS[@]}")
fi

echo "═══ D. POST ${BASE_URL}/sitemap/parse — ${#TARGETS[@]} target(s) ═══"

TOTAL_FOUND=0
TOTAL_FAILED=0
SUMMARY_LINES=()

for target in "${TARGETS[@]}"; do
    RESP=$(hcurl -X POST \
        -H 'Content-Type: application/json' \
        -d "$(jq -nc --arg u "$target" '{url:$u, queue:false, max_urls:50}')" \
        "${BASE_URL}/sitemap/parse" 2>/dev/null || echo '{"errors":["http-error"]}')

    COUNT=$(echo "$RESP" | jq -r '.count // 0' 2>/dev/null || echo 0)
    ERR_LIST=$(echo "$RESP" | jq -r '.errors // [] | join(", ")' 2>/dev/null || echo "")

    if [[ "$COUNT" -ge 1 ]]; then
        SAMPLE=$(echo "$RESP" | jq -r '.urls[0]' 2>/dev/null || echo "?")
        printf "  \033[32m✓\033[0m %-60s %3d URLs   first: %s\n" "$target" "$COUNT" "$SAMPLE"
        TOTAL_FOUND=$((TOTAL_FOUND + COUNT))
    else
        printf "  \033[31m✗\033[0m %-60s %3d URLs   err: %s\n" "$target" "$COUNT" "${ERR_LIST:-no urls returned}"
        TOTAL_FAILED=$((TOTAL_FAILED + 1))
    fi
done

echo
echo "  totals: $TOTAL_FOUND URLs across $((${#TARGETS[@]} - TOTAL_FAILED))/${#TARGETS[@]} sitemaps"

# Pass condition: at least ONE target succeeded (some sitemaps may legitimately 404
# if upstream removed/relocated their sitemap.xml — not our bug).
if [[ "$TOTAL_FAILED" == "${#TARGETS[@]}" ]]; then
    fail "ALL ${#TARGETS[@]} sitemap targets failed — parser is likely broken"
    exit 2
elif [[ "$TOTAL_FAILED" -gt 0 ]]; then
    warn "$TOTAL_FAILED/${#TARGETS[@]} sitemaps unreachable or empty — check upstream changes"
    exit 0
else
    ok "all ${#TARGETS[@]} sitemap targets succeeded"
fi
