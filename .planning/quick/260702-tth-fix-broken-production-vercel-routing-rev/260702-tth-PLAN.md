---
phase: quick-260702-tth
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - vercel.json
autonomous: true
requirements: [QUICK-VERCEL-ROUTING]

must_haves:
  truths:
    - "https://www.pacer.moorelabs.uk/ returns HTTP 200 and serves the SPA index.html"
    - "https://www.pacer.moorelabs.uk/api/health returns HTTP 200 from the Python function"
  artifacts:
    - "vercel.json using rewrites (not routes) with explicit /api/:path* rewrite plus SPA fallback"
  key_links:
    - "vercel.json rewrites -> api/index.py FastAPI mount at /api"
    - "vercel.json SPA fallback -> frontend/dist/index.html"
---

<objective>
Fix broken production routing at https://www.pacer.moorelabs.uk. Commit c44ad33 swapped vercel.json from a working `rewrites` config to a legacy `routes` array, which returns 404 (x-vercel-error: NOT_FOUND at the edge) on both `/` and `/api/health`. Revert to `rewrites` with an explicit `/api/:path*` rewrite to the Python function plus the SPA fallback, then push to main to auto-deploy and verify production is live.

Purpose: Restore production availability. The deployment is READY with zero build/runtime errors; this is a pure routing-config regression.
Output: Corrected vercel.json committed and pushed to main; production verified returning 200 on both `/` and `/api/health`.
</objective>

<execution_context>
@$HOME/.claude/gsd-core/workflows/execute-plan.md
@$HOME/.claude/gsd-core/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@vercel.json
@api/index.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Revert vercel.json to rewrites config with explicit API rewrite</name>
  <files>vercel.json</files>
  <action>
Replace the entire contents of vercel.json with the known-good rewrites config, adding an explicit API rewrite so routing to the Python function does not rely on implicit catch-all behavior. The file must contain exactly:

- buildCommand: "cd frontend && npm install && npm run build"
- outputDirectory: "frontend/dist"
- rewrites array with two entries, in this order:
  1. source "/api/:path*" -> destination "/api/index.py"
  2. source "/((?!api/).*)" -> destination "/index.html"

Remove the legacy `routes` array entirely (the `filesystem` handle and the two `src`/`dest` entries). Do NOT add any other keys. The negative-lookahead source `/((?!api/).*)` ensures every non-API path falls back to the SPA index.html while `/api/*` reaches the FastAPI mount in api/index.py.
  </action>
  <verify>
    <automated>node -e "const c=require('./vercel.json'); if(c.routes) throw new Error('routes still present'); const r=c.rewrites||[]; if(!r.some(x=>x.source==='/api/:path*'&&x.destination==='/api/index.py')) throw new Error('missing api rewrite'); if(!r.some(x=>x.source==='/((?!api/).*)'&&x.destination==='/index.html')) throw new Error('missing spa fallback'); console.log('vercel.json OK')"</automated>
  </verify>
  <done>vercel.json parses as valid JSON, has no `routes` key, and contains both the `/api/:path*` -> `/api/index.py` rewrite and the `/((?!api/).*)` -> `/index.html` SPA fallback in order.</done>
</task>

<task type="auto">
  <name>Task 2: Commit only vercel.json and push to main to trigger auto-deploy</name>
  <files>vercel.json</files>
  <action>
Stage ONLY vercel.json — nothing else. The working tree has pre-existing unrelated changes (.gitignore, .planning/PROJECT.md, .planning/STATE.md, node_modules/, test-ride.fit, docs/, .planning/ui-reviews/) that are OUT OF SCOPE and must NOT be staged or committed.

Run: `git add vercel.json` then `git commit -m "fix(routing): revert vercel.json to rewrites with explicit /api rewrite"` (append the GSD Co-Authored-By trailer). Confirm the commit contains exactly one file via `git show --stat HEAD` before pushing.

Then push to main: `git push origin main`. This triggers Vercel's production auto-deploy from the main branch. This is a direct push to main (no feature branch) — the user explicitly approved applying and pushing to production for this fix.
  </action>
  <verify>
    <automated>test "$(git show --stat --name-only --pretty=format: HEAD | grep -v '^$' | tr -d ' ')" = "vercel.json" && git log origin/main -1 --pretty=%H | grep -q "$(git rev-parse HEAD)" && echo "committed and pushed"</automated>
  </verify>
  <done>HEAD commit modifies only vercel.json; the commit is present on origin/main (push succeeded). No unrelated working-tree files were staged.</done>
</task>

<task type="auto">
  <name>Task 3: Poll production until the new deploy is live and both routes return 200</name>
  <files>vercel.json</files>
  <action>
Poll production until the freshly-pushed deployment goes live. Vercel production deploys typically take 30-90 seconds. Use curl with retry/backoff against both endpoints:

- https://www.pacer.moorelabs.uk/api/health (expect HTTP 200 from the Python function)
- https://www.pacer.moorelabs.uk/ (expect HTTP 200 serving the SPA)

Implement a bash loop: up to ~15 attempts with a 10-second sleep between attempts (allows ~2.5 min total, comfortably covering the deploy window). On each attempt, curl `-s -o /dev/null -w "%{http_code}"` for both URLs. Success = BOTH return 200. If after all retries either endpoint is not 200, report the last observed status codes and any `x-vercel-error` response header (curl `-I`) so the failure mode is visible (e.g. still NOT_FOUND vs a new error). Do not mark the task done until both endpoints return 200.

Note: a transient 404 immediately after push is expected while the old deployment is still aliased; keep polling. The `x-vercel-error: NOT_FOUND` header should disappear once the new deploy takes over the alias.
  </action>
  <verify>
    <automated>for i in $(seq 1 15); do a=$(curl -s -o /dev/null -w "%{http_code}" https://www.pacer.moorelabs.uk/api/health); b=$(curl -s -o /dev/null -w "%{http_code}" https://www.pacer.moorelabs.uk/); if [ "$a" = "200" ] && [ "$b" = "200" ]; then echo "LIVE: /api/health=$a /=$b"; exit 0; fi; echo "attempt $i: /api/health=$a /=$b — retrying"; sleep 10; done; echo "FAILED: /api/health=$a /=$b"; curl -sI https://www.pacer.moorelabs.uk/ | grep -i x-vercel-error; exit 1</automated>
  </verify>
  <done>https://www.pacer.moorelabs.uk/api/health returns 200 AND https://www.pacer.moorelabs.uk/ returns 200 from the new deployment.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| public internet -> Vercel edge | Untrusted requests hit the edge router before any function; routing config controls what is reachable |
| Vercel edge -> Python function | /api/* is rewritten to api/index.py (FastAPI mount) |

## STRIDE Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|-----------|----------|-----------|----------|-------------|-----------------|
| T-quick-01 | Denial of Service | vercel.json rewrite regex | low | accept | Negative-lookahead `/((?!api/).*)` is a static, well-formed pattern reverting to a previously-proven-good config; no user input compiles the regex |
| T-quick-02 | Information Disclosure | api/index.py exposure via /api/* | low | accept | No routing change widens API surface; explicit `/api/:path*` rewrite maps to the same FastAPI mount already in production before the regression |
| T-quick-SC | Tampering | npm/pip/cargo installs | n/a | accept | No package installs in this plan; config-only change to vercel.json |
</threat_model>

<verification>
- vercel.json is valid JSON, contains `rewrites` (not `routes`), with the explicit API rewrite and SPA fallback in order (Task 1 automated check).
- Exactly one file (vercel.json) committed and present on origin/main (Task 2 automated check).
- Production returns 200 on both `/api/health` and `/` after the auto-deploy completes (Task 3 poll loop).
- No unrelated working-tree files were staged or committed.
</verification>

<success_criteria>
- https://www.pacer.moorelabs.uk/ returns HTTP 200 (SPA served)
- https://www.pacer.moorelabs.uk/api/health returns HTTP 200 (Python function reachable)
- vercel.json uses rewrites with explicit `/api/:path*` -> `/api/index.py` and `/((?!api/).*)` -> `/index.html`
- Fix commit on origin/main touches only vercel.json
</success_criteria>

<output>
Create `.planning/quick/260702-tth-fix-broken-production-vercel-routing-rev/260702-tth-SUMMARY.md` when done
</output>
