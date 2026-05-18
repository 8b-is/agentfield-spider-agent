#!/usr/bin/env bash
# Run all 5 spider-agent live smoke checks in sequence.
# Each prints PASS / WARN / FAIL; first FAIL exits non-zero.
#
# Override targets:
#   SMOKE_FETCH_URL=...      (default: https://example.com)
#   SMOKE_SITEMAP_URL=...    (default: https://www.sitemaps.org/sitemap.xml)
#   SMOKE_CRAWL_URL=...      (default: https://example.com)
#   SMOKE_CRAWL_MAX_PAGES=N  (default: 3)
#   SMOKE_CRAWL_TIMEOUT_S=N  (default: 60)
#
# Skip individual checks:
#   SKIP_CRAWL=1 ./check-all.sh         # skip the longest one
#   SKIP_SITEMAP=1 ./check-all.sh

set -euo pipefail

SCRIPT_DIR="$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

echo
"$SCRIPT_DIR/check-services.sh"
echo
"$SCRIPT_DIR/check-health.sh"
echo
"$SCRIPT_DIR/check-fetch.sh"
echo

if [[ "${SKIP_SITEMAP:-0}" == "1" ]]; then
    echo "═══ D. sitemap ═══"
    echo "SKIP: SKIP_SITEMAP=1"
else
    "$SCRIPT_DIR/check-sitemap.sh"
fi
echo

if [[ "${SKIP_CRAWL:-0}" == "1" ]]; then
    echo "═══ E. crawl ═══"
    echo "SKIP: SKIP_CRAWL=1"
else
    "$SCRIPT_DIR/check-crawl.sh"
fi

echo
echo "═════════════════════════════════"
echo "All spider-agent smoke checks completed."
