---
phase: quick-260702-ulq
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - api/index.py
  - vercel.json          # only touched if Task 4 (fallback) runs
autonomous: true
requirements: [QUICK-SPA-404]
tags: [vercel, fastapi, spa, static-files, deploy]

must_haves:
  truths:
    - "Production https://www.pacer.moorelabs.uk/ returns 200 and serves the built SPA index.html (body contains <div id=\"root\">)"
    - "A nonexistent client-side route (e.g. /some-nonexistent-spa-route-xyz) returns 200 with the same index.html (SPA fallback)"
    - "A hashed asset under /assets/ returns 200"
    - "/api/health still returns 200 (no regression)"
  artifacts:
    - "api/index.py (StaticFiles mount for /assets + SPA catch-all GET route serving real files or index.html)"
    - "vercel.json functions.includeFiles bundling frontend/dist into the Python function (fallback, Task 4 only if needed)"
  key_links:
    - "app.mount('/api', _backend_app) registered BEFORE the catch-all route so /api/* is never shadowed"
    - "frontend/dist present on the Python function filesystem at request time (resolved via robust path lookup; bundled via includeFiles if runtime lookup fails in production)"
---

<objective>
Fix the production SPA 404. Under the Vercel `fastapi` Framework Preset (which must stay — switching it balloons the Python function bundle past the 500MB limit), every non-API request is routed to the Python function at `api/index.py` and vercel.json rewrites are ignored for non-API paths. Since the function already receives all traffic, make FastAPI itself serve the built frontend: mount the hashed asset bundle and add a catch-all route that serves real static files or falls back to `frontend/dist/index.html` for client-side routing — without ever intercepting `/api/*`.

Purpose: restore the live app at https://www.pacer.moorelabs.uk/ so the blocked production E2E test can proceed.
Output: modified `api/index.py` (and, only if the built dir is not present in the function at runtime, `vercel.json` with `functions.includeFiles`); a verified-live production deploy.
</objective>

<context>
@.planning/STATE.md
@.planning/quick/260702-tth-fix-broken-production-vercel-routing-rev/260702-tth-SUMMARY.md
@api/index.py
@vercel.json

# Do NOT modify backend/main.py internal routes — it is mounted as-is at /api.
# Reference only:
@backend/main.py
</context>

<known_facts>
Confirmed during planning (do not re-derive):
- Built output structure (`frontend/dist/`): `index.html` at the dir root; hashed bundles under `assets/` (e.g. `index-<hash>.js`, `index-<hash>.css`, `src-<hash>.js`); plus root-level static files `favicon.svg`, `icons.svg`, `manifest.webmanifest`, `registerSW.js`, `sw.js`, `workbox-<hash>.js`, `pwa-192x192.png`, `pwa-512x512.png`, `apple-touch-icon.png`.
- Built `index.html` markers to assert against: `<!doctype html` and `<div id="root">`; it references assets as `/assets/index-<hash>.js` and `/assets/index-<hash>.css`. Hashes change every build, so production checks MUST extract the live hashed path from the served HTML, never hardcode a hash.
- `frontend/dist` is NOT git-tracked; Vercel builds it fresh via `buildCommand`. A stale local `frontend/dist` exists (dated 25 Jun) and is structurally valid for local verification; optionally rebuild with `cd frontend && npm run build`.
- `StaticFiles` and `FileResponse` ship with the already-installed `fastapi` — no new dependency, no package-legitimacy gate needed.
- Vercel `functions.includeFiles` is a node-glob pattern that bundles matched files into the function bundle for officially supported runtimes (Python qualifies). It coexists with `buildCommand`, `outputDirectory`, and `rewrites`. Vercel's static `outputDirectory` output and the Python function bundle are SEPARATE build outputs — this is the real risk that `frontend/dist` may not be on the function filesystem at runtime, which Task 4 addresses.
- Production canonical host (matches prior verified curls): `https://www.pacer.moorelabs.uk`.
- Direct push to `main` is pre-approved for this fix (consistent with prior quick task 260702-tth). No feature branch.
</known_facts>

<tasks>

<task type="auto">
  <name>Task 1: Serve built SPA from FastAPI in api/index.py (StaticFiles + catch-all fallback)</name>
  <files>api/index.py</files>
  <action>
Modify `api/index.py` so the existing `app` serves the built frontend in addition to the `/api` mount. Keep the existing lines exactly: the `sys.path.insert(...)`, `from backend.main import app as _backend_app`, `app = FastAPI()`, and `app.mount("/api", _backend_app)` must remain and stay registered BEFORE anything added below (FastAPI/Starlette match routes in registration order, so the `/api` mount must come first or the catch-all could shadow it).

Add these imports: `from fastapi.staticfiles import StaticFiles` and `from fastapi.responses import FileResponse` (and `import logging` for a startup diagnostic).

Resolve the built directory robustly, because the runtime cwd/layout under Vercel is uncertain. Compute a `REPO_ROOT` as `os.path.dirname(os.path.dirname(os.path.abspath(__file__)))` (this is the same base the existing sys.path insert uses). Build an ordered list of candidate dist paths: `os.path.join(REPO_ROOT, "frontend", "dist")` first, then `os.path.join(os.getcwd(), "frontend", "dist")`. Pick the first candidate for which `os.path.isdir` is true; store it as `DIST`. Log the resolved DIST (or, if none resolved, log the full candidate list that was searched) at import time via `logging` so the Vercel function logs reveal the runtime layout if this fails in production.

If `DIST` resolved and `os.path.isdir(os.path.join(DIST, "assets"))`: mount the hashed bundle with `app.mount("/assets", StaticFiles(directory=os.path.join(DIST, "assets")), name="assets")`. Register this mount AFTER the `/api` mount.

Register a catch-all GET route LAST, as the final route on `app`, using a path parameter (signature `async def spa(full_path: str)` on `@app.get("/{full_path:path}")`). Behavior:
  1. If `DIST` did not resolve, return a JSONResponse with status 503 and a body naming the searched candidate paths (so a production failure is legible, not a silent 404). Do not raise.
  2. Safe-join the request path to DIST: `candidate = os.path.normpath(os.path.join(DIST, full_path))`. Reject path traversal by requiring `os.path.commonpath([DIST, candidate]) == DIST`; on rejection, fall through to serving index.html (do not 500).
  3. If `full_path` is non-empty and `os.path.isfile(candidate)`, return `FileResponse(candidate)` (serves favicon.svg, manifest.webmanifest, registerSW.js, sw.js, workbox-*.js, icons, pwa/apple-touch icons, etc.).
  4. Otherwise return `FileResponse(os.path.join(DIST, "index.html"))` — the SPA client-side-routing fallback.

Do NOT touch `backend/main.py`. Do NOT remove or edit the `/api` mount. Do NOT add a route or mount that matches the `/api` prefix. Keep the module import-safe (no network/DB calls at import; only filesystem checks and logging).
  </action>
  <verify>
    <automated>python -c "import ast,sys; ast.parse(open('api/index.py').read()); src=open('api/index.py').read(); assert 'app.mount(\"/api\"' in src, 'api mount removed'; assert 'StaticFiles' in src and '/{full_path:path}' in src, 'spa serving missing'; assert src.index('app.mount(\"/api\"') < src.index('/{full_path:path}'), 'catch-all registered before /api mount'; print('OK')"</automated>
  </verify>
  <done>api/index.py parses; retains the `/api` mount registered before a new catch-all GET route; mounts `/assets` via StaticFiles; catch-all serves real files under a path-traversal-guarded DIST or falls back to index.html; logs the resolved (or searched) dist path; no changes to backend/main.py.</done>
</task>

<task type="auto">
  <name>Task 2: Local verification with uvicorn (proves FastAPI logic + mount ordering)</name>
  <files>api/index.py</files>
  <action>
Verify the SPA-serving logic and mount ordering locally before pushing. This proves the FastAPI code is correct; it does NOT prove Vercel's runtime filesystem availability (that is confirmed only in production, Task 3). Ensure a `frontend/dist` exists locally (the stale 25 Jun build is fine; optionally `cd frontend && npm run build` for fresh hashes).

Boot the app from the repo root: `python -m uvicorn api.index:app --port 8000` (background it, give it a couple seconds). Then curl the four local checks (see verify). Extract the real hashed asset path from the served `/` HTML rather than hardcoding a hash.

Graceful degradation: `backend.main` calls `load_dotenv()` and imports routers that may require local env/secrets. If the full app fails to boot locally due to missing env (not due to your code), record that and rely on Task 3 (production) as the authoritative verification per the task constraints — but still confirm `api/index.py` imports/parses cleanly. Stop the uvicorn process when done.
  </action>
  <verify>
    <automated>set -e; ( python -m uvicorn api.index:app --port 8000 & echo $! > /tmp/uvpid ); sleep 3; B=http://127.0.0.1:8000; H=$(curl -s -o /dev/null -w '%{http_code}' "$B/api/health" || echo 000); R=$(curl -s "$B/" || echo ''); RC=$(curl -s -o /dev/null -w '%{http_code}' "$B/" || echo 000); SC=$(curl -s -o /dev/null -w '%{http_code}' "$B/some-nonexistent-spa-route-xyz" || echo 000); AP=$(printf '%s' "$R" | grep -oE '/assets/[A-Za-z0-9_.-]+\.js' | head -1); AC=$(curl -s -o /dev/null -w '%{http_code}' "$B$AP" || echo 000); kill "$(cat /tmp/uvpid)" 2>/dev/null || true; echo "health=$H root=$RC spa=$SC asset=$AC ($AP)"; printf '%s' "$R" | grep -q 'id="root"' && [ "$H" = 200 ] && [ "$RC" = 200 ] && [ "$SC" = 200 ] && [ "$AC" = 200 ] && echo LOCAL_PASS || echo "LOCAL_INCONCLUSIVE (if boot failed on env, proceed to Task 3 — production is authoritative)"</automated>
  </verify>
  <done>Locally: `/api/health` → 200, `/` → 200 with `id="root"` in body, a `/assets/<hash>.js` → 200, and a nonexistent route → 200 (SPA fallback), confirming the `/api` mount is not shadowed. If local boot is blocked by missing env, `api/index.py` at least imports cleanly and verification defers to Task 3.</done>
</task>

<task type="auto">
  <name>Task 3: Commit api/index.py, push to main, verify LIVE production</name>
  <files>api/index.py</files>
  <action>
Stage ONLY `api/index.py` (do not touch the pre-existing unrelated uncommitted/untracked changes: `.gitignore`, `.planning/PROJECT.md`, `node_modules/`, `test-ride.fit`, `docs/Pace Wireframes (standalone).html`, `.planning/ui-reviews/`). Commit with a message like `fix(deploy): serve built SPA from FastAPI catch-all in api/index.py`. Push to `main` (pre-approved direct push).

Then poll production until Vercel finishes the deploy (~30-90s) with a bounded retry loop (do not loop indefinitely). Run the four authoritative checks against `https://www.pacer.moorelabs.uk`:
  1. `/` → 200 and body contains `<div id="root">` (built SPA served).
  2. `/some-nonexistent-spa-route-xyz` → 200 with the same index.html marker (SPA fallback).
  3. a real hashed asset — extract the live path by grepping the `/` HTML for `/assets/...js`, then curl it → 200.
  4. `/api/health` → 200 (no regression).

If all four pass: this task and the fix are complete — SKIP Task 4. If after the retry budget `/` still 404s or errors: STOP here and proceed to Task 4 (the single documented fallback). Capture the exact failure mode now — status codes for each check, the `/` response body, and (if the Vercel CLI is authenticated) the function runtime logs via `vercel logs` for the latest deployment; the api/index.py startup diagnostic will have logged which dist path it searched.
  </action>
  <verify>
    <automated>B=https://www.pacer.moorelabs.uk; T=$(mktemp); PASS=0; for i in $(seq 1 12); do RC=$(curl -s -o "$T" -w '%{http_code}' "$B/"); AP=$(grep -oE '/assets/[A-Za-z0-9_.-]+\.js' "$T" | head -1); AC=000; [ -n "$AP" ] && AC=$(curl -s -o /dev/null -w '%{http_code}' "$B$AP"); SC=$(curl -s -o /dev/null -w '%{http_code}' "$B/some-nonexistent-spa-route-xyz"); HC=$(curl -s -o /dev/null -w '%{http_code}' "$B/api/health"); if [ "$RC" = 200 ] && [ "$AC" = 200 ] && [ "$SC" = 200 ] && [ "$HC" = 200 ] && grep -q 'id="root"' "$T"; then echo "PROD_PASS root=$RC asset=$AC($AP) spa=$SC health=$HC"; PASS=1; break; fi; echo "attempt $i: root=$RC asset=$AC($AP) spa=$SC health=$HC"; sleep 15; done; [ "$PASS" = 1 ] && echo DONE || echo "PROD_FAIL — proceed to Task 4 fallback"</automated>
  </verify>
  <done>Either: all four production checks pass (`/` and a nonexistent route both 200 with `id="root"`; a `/assets/<hash>.js` 200; `/api/health` 200) — fix complete, Task 4 skipped. Or: `/` still fails after the retry budget, with the exact failure mode (status codes + `/` body + function logs if available) captured for Task 4.</done>
</task>

<task type="auto">
  <name>Task 4 (CONDITIONAL fallback — run ONLY if Task 3 production checks failed): bundle frontend/dist into the function via vercel.json includeFiles</name>
  <files>vercel.json</files>
  <action>
SKIP THIS TASK ENTIRELY if Task 3's production checks all passed.

Run only if Task 3 showed `/` still 404s/errors in production, which indicates `frontend/dist` is not present on the Python function's filesystem at runtime (Vercel's static output and the function bundle are separate build outputs). This is the SINGLE documented fallback — do not attempt further speculative fixes beyond it.

Edit `vercel.json` to add a top-level `functions` object bundling the built frontend into the Python function, keeping the existing `buildCommand`, `outputDirectory`, and `rewrites` untouched:
  add `"functions": { "api/index.py": { "includeFiles": "frontend/dist/**" } }`.
This globs all built files under `frontend/dist` into the function bundle. `frontend/dist` is ~1MB, far under the 500MB function limit, so it will not affect the bundle-size constraint that forces the `fastapi` preset. Do NOT add a `framework` field and do NOT change the Framework Preset (must stay `fastapi`).

Because Task 1's DIST resolution already checks `REPO_ROOT/frontend/dist`, the bundled files (which Vercel places relative to the project root inside the function) will be found with no further code change.

Stage ONLY `vercel.json`, commit (e.g. `fix(deploy): bundle frontend/dist into python function via includeFiles`), push to `main`, and re-run the exact production verification from Task 3.

If it PASSES: fix complete. If it STILL fails after this one fallback: STOP. Do NOT loop or try more speculative fixes. Report the exact observed failure mode — per-check status codes, the `/` response body, and the function runtime logs (which include the api/index.py searched-paths diagnostic) — and leave the decision to a human.
  </action>
  <verify>
    <automated>node -e "const c=require('./vercel.json'); if(!(c.functions&&c.functions['api/index.py']&&c.functions['api/index.py'].includeFiles==='frontend/dist/**')) throw new Error('includeFiles not set'); if(!c.buildCommand||!c.outputDirectory||!c.rewrites) throw new Error('existing keys lost'); if(c.framework) throw new Error('must not set framework preset'); console.log('vercel.json OK')" && B=https://www.pacer.moorelabs.uk; T=$(mktemp); PASS=0; for i in $(seq 1 12); do RC=$(curl -s -o "$T" -w '%{http_code}' "$B/"); AP=$(grep -oE '/assets/[A-Za-z0-9_.-]+\.js' "$T" | head -1); AC=000; [ -n "$AP" ] && AC=$(curl -s -o /dev/null -w '%{http_code}' "$B$AP"); HC=$(curl -s -o /dev/null -w '%{http_code}' "$B/api/health"); if [ "$RC" = 200 ] && [ "$AC" = 200 ] && [ "$HC" = 200 ] && grep -q 'id="root"' "$T"; then echo "PROD_PASS root=$RC asset=$AC health=$HC"; PASS=1; break; fi; echo "attempt $i: root=$RC asset=$AC health=$HC"; sleep 15; done; [ "$PASS" = 1 ] && echo DONE || echo "STILL_FAILING — stop, report failure mode, escalate to human (do not loop)"</automated>
  </verify>
  <done>Only reached if Task 3 failed. `vercel.json` gains `functions."api/index.py".includeFiles: "frontend/dist/**"` with existing keys intact and no `framework` field; after push, production `/` returns 200 with `id="root"`, asset 200, `/api/health` 200. If it still fails, the task stops with a documented failure report for human decision — no further attempts.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| client → catch-all file server | Untrusted request path (`full_path`) is joined to the DIST directory to locate a file |

## STRIDE Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|-----------|----------|-----------|----------|-------------|-----------------|
| T-ulq-01 | Information Disclosure | catch-all `GET /{full_path:path}` file resolution | high | mitigate | Normalize the joined path and require `os.path.commonpath([DIST, candidate]) == DIST`; on any traversal attempt fall through to index.html — never serve files outside DIST (Task 1) |
| T-ulq-02 | Tampering | `/api/*` shadowing by the SPA catch-all | medium | mitigate | Register the `/api` mount before the catch-all and StaticFiles mounts; assert registration order in Task 1 verify and confirm `/api/health` 200 locally (Task 2) and in production (Task 3) |
| T-ulq-03 | Denial of Service | import-time filesystem/logging in api/index.py | low | accept | Only cheap `os.path.isdir` checks and a single log line at import; no network/DB calls; returns a legible 503 (not a crash) if DIST is unresolved |
</threat_model>

<verification>
Phase-level acceptance (authoritative = live production, per task constraints):
- `https://www.pacer.moorelabs.uk/` → 200, body contains `<div id="root">`.
- `https://www.pacer.moorelabs.uk/some-nonexistent-spa-route-xyz` → 200, same index.html (SPA fallback).
- A live-extracted `/assets/<hash>.js` → 200.
- `https://www.pacer.moorelabs.uk/api/health` → 200 (no regression).
- Framework Preset unchanged (`fastapi`); only `api/index.py` (and, if needed, `vercel.json` `functions.includeFiles`) changed; no unrelated files staged.
</verification>

<success_criteria>
Production SPA is live: root and client-side routes serve the built index.html (200), static assets resolve (200), and `/api/health` remains 200 — achieved by FastAPI serving `frontend/dist` under the retained `fastapi` preset, with `includeFiles` applied only if the function could not find the built dir at runtime. If the bounded fallback still fails, the executor stops and reports the exact failure mode for human decision rather than looping.
</success_criteria>

<output>
Create `.planning/quick/260702-ulq-fix-production-spa-404-have-fastapi-serv/260702-ulq-SUMMARY.md` when done. Record: which tasks ran (whether Task 4 fallback was needed), the final production check results, and — if it ultimately failed — the exact observed failure mode and function-log diagnostic for the human decision.
</output>
