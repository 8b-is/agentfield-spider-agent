# Shared bits for spider-agent smoke scripts. Source-able from anywhere;
# anchors to the compose dir via BASH_SOURCE.

set -euo pipefail

SCRIPT_DIR="$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
COMPOSE_DIR="$( cd -- "$SCRIPT_DIR/.." &> /dev/null && pwd )"
cd "$COMPOSE_DIR"

# Spider's HTTP port (rag-stack-compatible). Override via .env or env.
HTTP_PORT="${SPIDER_HTTP_PORT:-11700}"
HTTP_HOST="${SPIDER_HTTP_HOST:-localhost}"
BASE_URL="http://${HTTP_HOST}:${HTTP_PORT}"

# Helper: curl via the local docker network so we don't need host port-forward
# (the spider-http service runs in the spider-int network). Falls back to
# direct curl if you've already exposed the port.
hcurl() {
    if docker compose ps --status running --services 2>/dev/null | grep -qx spider-http; then
        docker compose exec -T spider-http curl -sS "$@"
    else
        curl -sS "$@"
    fi
}

ok()   { printf "\033[32m✓\033[0m %s\n" "$*"; }
fail() { printf "\033[31m✗\033[0m %s\n" "$*" >&2; }
warn() { printf "\033[33m!\033[0m %s\n" "$*" >&2; }
