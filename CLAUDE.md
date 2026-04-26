# Synonymicon

## What this is
A frequency-driven discovery tool for obscure English synonyms. Not a general thesaurus or dictionary. Not a vocabulary learning tool. Common words are inputs, not outputs. The point is to excavate rare lexical outliers at user-controlled levels of obscurity.

## Stack
- **Python + Flask**, synchronous, single-process
- **No database** — all state computed on the fly, nothing persisted
- **wordfreq** for frequency: `zipf_frequency(word, 'en')` at query time. No precomputed frequency index. Zipf scale: 0 = vanishingly rare, 7 = extremely common
- **NLTK WordNet** — primary synonym source (synset lemmas)
- **fastText** (fasttext-wiki-news-subwords-300 via gensim) — secondary/fallback synonym source. Note: the gensim distribution is KeyedVectors (pretrained vectors only), not the full FastText model — OOV inputs raise KeyError and must be caught. WordNet still covers OOV cases.
- **Definition fallback chain:** Wiktionary API → Webster's 1913 (local JSON at `data/websters1913.json`) → WordNet gloss → `"[undefined]"` (literal string, rendered in italics). Wiktionary REST API requires a descriptive `User-Agent` header per Wikimedia policy — requests without one return 403 or get rate-limited. Use `requests` for fetches and `beautifulsoup4` (`bs4`) for HTML stripping.
- **Frontend:** single-page HTML/CSS/JS served from `static/`. Modern Light theme only. Right-heavier layout (~40/60 or 42/58); integrated search/control surface on the left; rounded trays with dynamic frequency bands on the right. Dark, OLED, and Dictionary modes are post-MVP.

## Layout
- `app.py` — Flask app, all backend logic
- `data/websters1913.json` — Webster's 1913, loaded at startup
- `static/` — frontend files (index.html plus optional style.css / app.js)
- `.venv/` — Python venv (gitignored)

## Frequency tiers
```python
TIERS = {
    'all':      (float('-inf'), 4.0),  # default; everything below COMMON_FLOOR
    'uncommon': (3.0, 4.0),
    'rare':     (2.0, 3.0),
    'exotic':   (1.0, 2.0),
    'absurd':   (float('-inf'), 1.0),
}
COMMON_FLOOR = 4.0  # Zipf >= 4.0 excluded from all results
```
Tier filtering: `zmin <= z < zmax`. Advanced mode accepts raw Zipf min/max instead (backend-supported, UI-deferred).

## Synonym scoring
Blended single list, no source labels exposed in UI:
- WordNet candidates: flat score = 1.5
- fastText candidates: score = cosine similarity
- Overlap: WordNet wins (true synonym trumps embedding neighbor)
- Normalize for comparison/lookup on lowercase; WordNet lemma underscores become spaces
- Multiword candidates are allowed for MVP
- fastText cosine cutoff: `FASTTEXT_COSINE_CUTOFF = 0.65` (candidates below this are dropped; tuned in Session 5)
- Sort: score descending, Zipf ascending as tiebreaker (rarer first within score band)

## API
`GET /synonyms?word=<x>&tier=<t>` — returns JSON list of `{word, zipf, definition}`
Optional: `min` and `max` (Zipf floats) for advanced mode.

Valid `tier` values: `all` (default), `uncommon`, `rare`, `exotic`, `absurd`.

Parameter precedence:
- Both `min` and `max` → advanced mode; `tier` ignored if present
- Exactly one of `min`/`max` → 400
- Neither → use `tier`; missing `tier` → 400
- Unknown `tier` value → 400 with available tier names
- Missing `word` → 400

## Frontend control surface
The left panel contains, top to bottom:

1. **Serif "Synonymicon" wordmark** in the top-left corner — just the word in a serif face. No logo glyph, no ornament.
2. **Integrated search/control surface**, positioned higher than vertical center (more empty space below than above; roughly upper-third anchoring), containing:
   - Search input (debounced ~250ms; `AbortController` cancels stale requests)
   - `corpus: wordfreq` selector (one option for now; future-proofing)
   - `frequency: all` selector — five options mapping to backend tiers:

| UI label | `tier` param |
|---|---|
| `all` (default) | `all` |
| `10k-30k` | `uncommon` |
| `30k-80k` | `rare` |
| `80k-150k` | `exotic` |
| `150k+` | `absurd` |

Rank labels (`10k-30k`, etc.) are display-only; backend filters on Zipf. The bottom of the left panel stays empty.

## Frontend results surface
The right panel holds one or more rounded trays containing results.
- Bands flow through trays as soft horizontal section dividers, each rendered only as tall as the words it contains.
- Render only bands with content; empty bands do not appear.
- A band that overflows continues into the next tray without losing identity (its label/divider reappears mid-tray rather than at the top).
- Adaptive tray count: one tray for few results, two for enough, implied third with continuation cue (right-edge `→` and/or pagination dots) for many.
- When `frequency` is set to a single band (not `all`), only that band renders — no internal dividers needed.
- Italic rendering for `[undefined]` definitions (`.result-def .undefined { font-style: italic }`).

## Run commands
```bash
cd ~/projects/synonymicon
source .venv/bin/activate
flask run --no-reload
```
Dev server on localhost:5000. Use `--no-reload` because the fastText model loads at module scope and the reloader would spawn two processes that both load it. Server startup ~2.5–3 minutes due to fastText (~1GB into RAM).

## Non-goals — do not add these
- General synonyms or common words in results
- Dictionary-like features (etymology, pronunciation, usage examples)
- Languages other than English
- Dark, OLED, or Dictionary visual themes until their dedicated sessions
- `simple / advanced` mode toggle in the UI (backend `min`/`max` params remain supported; UI exposure deferred indefinitely)
- Part-of-speech filtering (post-MVP)
- Pivot-on-click (post-MVP)
- Mobile-specific layout
- Any database, ORM, or persistent storage
- Additional frequency corpora beyond wordfreq (post-MVP)

## Scope rails
- Do not introduce a database. Ephemeral in-memory caches are fine; do not add persistent storage.
- Do not add features outside the MVP scope listed above.
- Do not "improve" the minimalist UI with animations, shadows, decorative cards, helper panels, logo glyphs, ornaments, taglines, or unrequested elements. The serif "Synonymicon" wordmark in the top-left is the only branding element.
- Frontend is desktop-first and right-heavier (~40/60 or 42/58). Left side fixed for the integrated search/control surface; right side scrollable for results only. No top bar; no controls on the right side.
- Results render inside rounded trays with dynamic frequency bands flowing through them. Do not fix one band per tray. Do not mirror or duplicate results across containers. No recursive or looped result repetition.
- Frontend is plain inline or lightly split HTML/CSS/JS. No build tools, no bundler, no framework.
- Do not do client-side sorting, scoring, definition lookup, or ranking — the backend returns results in final order; render as-is.
