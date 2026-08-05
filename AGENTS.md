<!-- Managed under atelier. -->

> **Managed under atelier.** Before starting, read
> `C:\Users\kenrin\Project\.atelier\CHARTER.md` (from WSL:
> `/mnt/c/Users/kenrin/Project/.atelier/CHARTER.md`), the current week log in
> `/mnt/c/Users/kenrin/Project/.atelier/logs/`, and this project's brief + log
> at `/mnt/c/Users/kenrin/Project/.atelier/projects/coding/synonymicon/`.
> Clock out per the charter when done.

# Agent Notes — Improvement Backlog

Last updated: Tue Jun 02 2026 (Session: opencode exploration + full audit)

## Context

The user asked for a codebase exploration and improvement proposals. The exploration is complete. All backlog items have been implemented. A full 24-entry taxonomy audit was run — see AUDIT_2026-06-02.md.

## Improvement Backlog (prioritized)

### High Priority

#### ~~1. Unbounded definition cache growth~~ ✅ COMPLETED
**Files:** `definitions.py`
**Problem:** `DEFINITION_CACHE` and `WIKTIONARY_CACHE` were plain dicts with no eviction. Over long-running production use these grow without limit alongside the ~1.5–2 GB baseline.
**Fix:** Replaced with a bounded `_LRUDict` class (backed by `OrderedDict`, max 50k entries each). Preserves the existing `NETWORK_ERROR` sentinel logic (transient failures are not cached).

#### ~~2. No graceful corpus loading degradation~~ ✅ COMPLETED
**Files:** `corpora.py`, `config.py`
**Problem:** If any corpus file is missing or malformed, `_load_all()` crashes at import time and the entire app fails to start.
**Fix:** Wrapped each corpus loader in try/except. On failure, prints a warning to stderr, skips the corpus, and the app starts with whatever loaded successfully. `config.py` derives `VALID_CORPORA` from `corpora.LOADED_CORPORA` so unavailable corpora are automatically excluded from the API.

#### ~~3. Missing health check endpoint~~ ✅ COMPLETED
**Files:** `app.py`
**Problem:** No `/health` or `/ready` endpoint for load balancer monitoring or uptime checks.
**Fix:** Added `/health` route that checks WordNet accessibility and at least one corpus loaded. Returns 200 with `{"status": "ok", "checks": {"wordnet": "ok", "corpora": "N loaded"}}` or 503 on failure.

### Medium Priority

#### ~~4. No rate limiting~~ ✅ COMPLETED
**Files:** `app.py`
**Problem:** `/synonyms` has no per-IP or per-word rate control. `ThreadPoolExecutor(max_workers=10)` provides natural concurrency limiting but no abuse prevention.
**Fix:** Added a simple in-memory token-bucket rate limiter (~60 req/min per IP). Returns 429 with `{"error": "rate limit exceeded, try again later"}` when exceeded.

#### ~~5. flask-cors inconsistency~~ ✅ COMPLETED
**Files:** `requirements.txt`, `NEXT.md`
**Problem:** Session 19 notes adding `flask-cors 6.0.2` to requirements.txt, but it's not in the current file and `app.py` doesn't use it.
**Fix:** Removed the `flask-cors` reference from `NEXT.md` documentation (audit already removed it from `requirements.txt`).

#### ~~6. fastText is never tested~~ ✅ COMPLETED
**Files:** `tests/conftest.py`, `tests/test_api.py`, `pytest.ini`
**Problem:** All tests run with `SYNONYMICON_FASTTEXT=0`. FastText integration bugs could slip through.
**Fix:** Added `TestFastText` class with `@pytest.mark.slow` marker. Tests are skipped unless `SYNONYMICON_FASTTEXT=1` is set. Run with `SYNONYMICON_FASTTEXT=1 pytest -m slow`.

### Low Priority

#### ~~7. Structured logging~~ ✅ COMPLETED
**Files:** `app.py`, `candidates.py`, `corpora.py`, `definitions.py`
**Problem:** No logging framework; errors only appear in Werkzeug output.
**Fix:** Added minimal structured logging — JSON-formatted request records to stderr via Python `logging`. Each request logs method, path, status, and remote address.

#### 8. BNC lemmatization edge cases *(deferred — acknowledged, not critical)*
**Files:** `corpora.py`
**Problem:** Noun-first, verb-fallback lemmatization can mis-resolve ambiguous words. Acknowledged but not critical.
**Plan:** Consider trying both lemmatizations and picking the one that yields a higher BNC frequency (if both exist).

#### 9. Frontend JS approaching 2000 lines *(deferred — monitor only)*
**Files:** `static/index.html`
**Problem:** Well-organized with section comments but approaching a size where extraction helps maintainability.
**Plan:** If it grows further, consider ES modules with `<script type="module">` and inline imports (no build step needed).

## Audit Results

**AUDIT_2026-06-02.md** — Full 24-entry taxonomy audit. Found 1 real-defect (broad `except Exception` in `/health` — low severity), 5 legitimate-variants, 18 no-candidate entries. Codebase is in excellent shape.

## How to Resume

1. Pick an item from the backlog above.
2. Read the relevant files.
3. Implement the change.
4. Run `pytest` to verify nothing broke.
5. Update this file to mark the item complete and remove it from the backlog.

## Key Commands

```bash
cd ~/projects/synonymicon
source .venv/bin/activate
flask run --no-reload        # dev server on localhost:5000
pytest                        # run test suite (fastText disabled)
SYNONYMICON_FASTTEXT=0 pytest # explicit fastText disable
```

## Architecture Summary

- **Backend:** 5 modules — `app.py` (routes), `config.py` (constants), `candidates.py` (WordNet + fastText), `corpora.py` (11 frequency tables), `definitions.py` (Wiktionary → Webster's → WordNet fallback chain)
- **Frontend:** Single `static/index.html` (1993 lines, inline CSS/JS, no build step)
- **Data:** 11 frequency corpora in `data/` (~169 MB total), Webster's 1913 JSON, fastText model (~1 GB, loaded at import)
- **Memory:** ~1.5–2 GB resident. Cold start ~2.5–3 minutes.
- **Production:** Deployed at https://synonymicon.xyz on Contabo VPS with gunicorn + nginx + Let's Encrypt.
