# CLAUDE.md — agentfield-spider-agent

## Mission

Provide web fetch + RSS/Atom feed polling to the agent fleet (via
AgentField `@app.skill()`) and to any rag-stack-compatible HTTP caller
(via aiohttp on :11700). One Python core, two delivery surfaces.

## Role boundary with `camofox-agent`

The swarm has two anti-detect browser agents. They are NOT redundant —
they specialize:

| Use case | Agent | Why |
|---|---|---|
| Bulk crawl (depth-N) | **`spider-agent` (this one)** | Redis-backed queue, dedup, robots.txt + politeness, RSS/Atom feed poller, rag-stack HTTP API compat on :11700 |
| RSS / Atom feed monitoring | **`spider-agent`** | `feed_add` + scheduled poll baked in |
| Interactive multi-step browse | `camofox-agent` | `browse(actions=[...])` with click/type/snapshot ops on one tab |
| Visual debug (Dynamic Island, VNC) | `camofox-agent` | `fetch_page(watch=True)` returns vncUrl |
| OpenClaw plugin integration | `camofox-agent` | `openclaw.plugin.json` autoloads inside nemoclaw sandboxes |
| Anti-fingerprint at Firefox level | `camofox-agent` | Camoufox source-level fingerprint spoofing |
| Anti-fingerprint at Chromium level | **`spider-agent`** | CloakBrowser source-level Chromium stealth |

Default if you're unsure: `spider-agent` for "scrape N pages",
`camofox-agent` for "drive one browser like a human would".

## Architecture at a glance

- **Pattern:** deterministic dispatcher (no `.ai()`), one agent, externally
  callable skills, an aiohttp HTTP server speaking the rag-stack crawler
  API, shared `spider/` module so the two surfaces never drift.
- **Topology:** `main.py` runs the AgentField agent on :8005.
  `spider_server.py` runs the HTTP server on :11700. Two processes, one
  image, separate services in compose. In k3s: two containers in one pod
  (sidecar pattern) so the browser pool stays single-tenant per replica.
- **Browser:** CloakBrowser (replaces Scrapling). Source-level Chromium
  stealth patches; Playwright-compatible. Binary auto-fetched at first
  run (~200 MB), cached on a persistent volume in k3s.
- **Storage:** Redis. `crawler:queue` (LIST), `crawler:seen` (SET),
  `crawler:feeds` (HASH), `crawler:jobs` (ZSET). External in production;
  bundled as a sidecar in `docker-compose.yml` for local dev.

## Primitive selection rules (binding)

- **No `.ai()` calls.** Deterministic only — no LLM in the fetch/extract
  path. (LLM-driven content scoring is a v2 feature, gated separately.)
- **`@app.skill()`, not `@app.reasoner()`.** Both surfaces share the same
  underlying Python; the skill wrapper is the canonical entry point.
- **No `app.harness(...)`.**
- **One browser per replica.** No fan-out / no shared global pool across
  containers; deduping happens via Redis `crawler:seen`.

## Data-flow rules

- `@app.skill('fetch')` returns `{title, text, links?, ms}` — flat dict,
  no nested response object.
- The HTTP `POST /fetch/sync` returns the same shape.
- `POST /fetch` (async) enqueues to `crawler:queue` and returns
  `{queued: true, url}`. The dispatcher worker drains the queue and
  writes outcomes to `crawler:jobs`.
- `MissingDependencyError` for cloakbrowser-import-failed is the explicit
  signal for "CloakBrowser binary not available". Treat as fatal — pod
  should crashloop, not silently return errors.

## Failure semantics

- Network / timeout / page-load error → record job as `"error"` with the
  exception class + message, return 502 (sync) or just record it (async).
- Robots-disallowed → record as `"blocked-by-robots"`, 403 (sync).
- SSRF-gate fail (loopback / private IP / blocklist) → record as
  `"blocked-by-ssrf-gate"`, 400.
- Empty extraction (< 100 chars) → record as `"empty"`, 200 with empty
  body. Caller's choice whether to retry.
- Crawl timeout exceeded → crawl status becomes `"completed"` when
  `max_pages` is hit or queue is empty.
- Sitemap parse error (non-200 HTTP, invalid XML, etc.) → returned as
  `errors` array in response; does not fail the request.
- Chromadb sink error → silently skipped (never fails primary fetch).
  Logged at `sink.exception` level.

## Runtime contract

- AgentField agent: `python main.py` (port **8005**) or `docker compose up`.
- HTTP server: `python spider_server.py` (port **11700**) or via compose.
- Both surfaces require `REDIS_URL` (default `redis://redis:6379/0` in
  compose).
- k3s: two containers in one pod, see `deploy/k3s/`.

## Known broken tests (TODO before relying on crawl/sitemap in prod)

Five test failures in the May 2026 extension (crawl + sitemap + sink +
new AF skills). Other 86 tests pass. Triage:

| Test | Cause | Fix |
|---|---|---|
| `test_crawl.py::test_crawl_{start,status,status_not_found}` (3 errors) | References a `mock_redis_dict` fixture that doesn't exist in conftest.py. The tests create their own `AsyncMock` internally so the fixture parameter is dead. | Remove the `mock_redis_dict` arg from those 3 test signatures. |
| `test_crawl.py::test_extract_links` | `_extract_links()` in `spider/crawl.py:92` returns a list that doesn't contain the absolute-resolved URL the test expects. Either BeautifulSoup is parsing the malformed test HTML differently than expected, or the urljoin produces an unexpected form. | Run `_extract_links(<test html>, "https://example.com")` interactively; compare to assertion. May need to use `bs4`'s `lxml` parser instead of `html.parser`, or fix the test's HTML to be well-formed. |
| `test_sitemap.py::test_sitemap_parse_basic` | `sitemap_parse()` in `spider/sitemap.py:16` returns 0 URLs from a well-formed sitemap. Likely an XML namespace handling bug in the `findall` path — the namespace map lookup works for root but may fail for nested element querying. | Add a print of `root.tag` and the actual `findall` results to debug. Validate against a real sitemap.xml (e.g. https://www.sitemaps.org/sitemap.xml) before promoting. |

The crawl + sitemap features are wired end-to-end (HTTP routes, AF
skills, Redis state, integration with the existing fetch pipeline)
and were submitted for live operator verification. They are not
production-ready until the above tests pass.

## Hard rejections

- Topic-driven crawling, search-engine fan-out, reranker scoring — those
  live in rag-stack's crawler and are explicitly out of scope. See the
  approved plan.
- pocket / rag-pocket ingestion. The fetch returns text; callers persist
  if they want.
- Reddit-specific stealth (was in the Go spider — `reddit_stealth.go`).
  Out of scope for v1.
- Adding extra browser backends. CloakBrowser is the only backend.
- Bypassing `spider/security.py` for SSRF — all fetches must be gated.

## Delivery contract

Every change must preserve:

- `python -m py_compile main.py spider_server.py reasoners/*.py spider/*.py`
- `pytest -v --tb=short` — all unit tests pass without live network /
  browser. Browser-dependent paths use the mock pool in `tests/conftest.py`.
- `docker compose config > /dev/null` (compose syntax).
- The smoke ladder in `README.md`.

## Port assignment

| Port | Surface | Process |
|---|---|---|
| 8005 | AgentField skill | `main.py` |
| 11700 | HTTP API (rag-stack-compatible) | `spider_server.py` |

8005 chosen to avoid collision with: 8001 (my-agent), 8003 (pr-enricher),
8004 (web-search-agent), 8006 (data-engineer-agent).

## Security

- All outbound URLs pass through `spider/security.py`
  (`is_safe_external_url_with_dns` + `follow_safe_redirects`).
- Loopback, link-local, RFC1918 ranges, and a hostname blocklist are
  rejected pre-fetch.
- Redis: bind only via the in-cluster Service (k3s) or the compose
  network (local). No public exposure.
- No credentials are required for v1 — the browser fetches public pages.
  If we add authenticated scraping in v2, secrets go in a k8s Secret.
