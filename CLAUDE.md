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
- **Frontend:** single-page HTML/CSS/JS served from `static/`. Modern Light theme only. Right-heavier layout (38/62); integrated search/control surface on the left; single rounded word surface containing column cells on the right.

## Layout
- `app.py` — Flask app, all backend logic
- `data/websters1913.json` — Webster's 1913, loaded at startup
- `static/` — frontend files (`index.html`; CSS and JS inline in the same file)
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

## Band labels
The API includes a `band` field on each result. Band labels match `TIERS` keys exactly:

| Zipf range | `band` value |
|---|---|
| Zipf ≥ 4.0 | `common` (filtered out by `COMMON_FLOOR`; never returned) |
| 3.0 ≤ Zipf < 4.0 | `uncommon` |
| 2.0 ≤ Zipf < 3.0 | `rare` |
| 1.0 ≤ Zipf < 2.0 | `exotic` |
| Zipf < 1.0 | `absurd` |

`get_band_label(zipf)` in `app.py` is the single source of truth. Any change to `TIERS` boundaries must update `get_band_label` in lockstep.

## Synonym scoring
Blended single list, no source labels exposed in UI:
- WordNet candidates: flat score = 1.5
- fastText candidates: score = cosine similarity
- Overlap: WordNet wins (true synonym trumps embedding neighbor)
- Normalize for comparison/lookup on lowercase; WordNet lemma underscores become spaces
- Multiword candidates are allowed for MVP
- fastText cosine cutoff: `FASTTEXT_COSINE_CUTOFF = 0.65` (candidates below this are dropped; tuned in Session 5)
- **Sort: Zipf descending (rarer first), score descending as tiebreaker.** This ordering makes results contiguous by frequency band, which is required for inline band separators in the frontend to render correctly.

## API
`GET /synonyms?word=<x>&tier=<t>` — returns JSON list of `{word, zipf, definition, band}`.
Optional: `min` and `max` (Zipf floats) for advanced mode.

Valid `tier` values: `all` (default), `uncommon`, `rare`, `exotic`, `absurd`.

Parameter precedence:
- Both `min` and `max` → advanced mode; `tier` ignored if present
- Exactly one of `min`/`max` → 400
- Neither → use `tier`; missing `tier` → 400
- Unknown `tier` value → 400 with available tier names
- Missing `word` → 400

## Frontend control surface (left panel)
The left panel contains, top to bottom:

1. **Serif "Synonymicon" wordmark** in the top-left corner — just the word in a serif face. No logo glyph, no ornament.
2. **Integrated search/control surface**, anchored at the upper-third (margin-top ~18vh), structured as a single rounded "tray" containing:
   - Inner search card (input field with magnifying-glass icon and submit-arrow button)
   - Two flat dropdowns sitting on the tray below the search card: `corpus: wordfreq` and `frequency: <current>`
   - The tray, search card, and dropdowns form three layered visual surfaces — outer tray (`--surface`), inner search card (`--column`), and the bare dropdowns on the tray.
3. **Watermark `&` glyph** in the bottom-left, ~18rem, ~7% opacity, fills the otherwise-empty lower portion of the panel.

Frequency dropdown options map to backend tiers:

| UI label | `tier` param |
|---|---|
| `all` (default) | `all` |
| `10k-30k` | `uncommon` |
| `30k-80k` | `rare` |
| `80k-150k` | `exotic` |
| `150k+` | `absurd` |

Display labels (`10k-30k`, etc.) are display-only; backend filters on Zipf.

## Frontend results surface (right panel)
The right panel holds one rounded "word surface" containing up to three column cells per page. Pagination is page-based, not continuous-scroll.

- **Three-column page model.** Each visible page is up to 3 column cells. Empty trailing slots collapse rather than rendering as ghost rectangles.
- **Continuous-flow chunking.** Results fill column 1 to capacity, overflow to column 2, then column 3, then page 2's column 1, etc. The fill logic is continuous; only the visible window is paginated.
- **Peek column.** When more pages exist, ~36px of the next page's first column bleeds past the surface's right edge as an affordance signaling "more results continue." On the last page, the columns sit flush with no peek.
- **Page indicator.** Bar-style active dot (wider, darker) with thin dots for inactive pages, centered below the columns. Clickable.
- **Edge arrows.** Left and right circular arrow buttons positioned outside the surface edges. Disabled (faded) when at the bounds.
- **Page transition.** 220ms fade + slight horizontal slide on page change. The columns container has its `key`-equivalent state cycled to retrigger the animation.

### Within columns
- **Entry layout:** serif headword (~2rem, slight letterspacing), small superscript Zipf badge, italic serif definition (~1rem, muted color, ~1.35 line-height).
- **Hover state:** color deepens on both headword and definition. No movement, no scale, no shadow change.
- **`[undefined]` rendering:** italic, lighter muted color than regular definitions.
- **Band separators (planned for 7b):** when results span multiple bands and the current page contains a band transition, a small-caps muted header with hairline divider above appears inline at the position of the transition. Cross-column tracking ensures a continuing band does not get a redundant header at the top of a new column. A new band starting at the top of a column does get a header.

### Surface layering
- **Outer word surface:** `--surface` background, large radius (`--radius-outer`, 2rem), soft shadow.
- **Inner column cells:** `--column` background, smaller radius (`--radius-inner`, 1.5rem), subtle shadow, hairline border. Use `background-clip: padding-box` to avoid corner-leak rendering artifacts.
- The two-level layering (outer surface + inner cells) is intentional and earns its complexity by making the column boundaries legible without dividers.

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
- Frontend is desktop-first and right-heavier (38/62). Left side fixed for the integrated search/control surface; right side for the word surface only. No top bar; no controls on the right side.
- Results render inside the single word surface with band separators flowing inline through the columns. Do not fix one band per column. Do not mirror or duplicate results across containers. No recursive or looped result repetition.
- Frontend is plain inline HTML/CSS/JS. No build tools, no bundler, no framework. Tailwind, React, etc. are out of scope — translation from any external mockup must produce vanilla output.
- Do not do client-side sorting, scoring, definition lookup, or ranking — the backend returns results in final order; render as-is.
- The current visual treatment intentionally includes: soft shadows on surfaces, a watermark `&` glyph in the lower-left of the search panel, a 220ms page-transition animation, and serif typography (Cormorant Garamond). These are part of the agreed visual model — do not remove them as "decorative excess." Do not, however, add further ornament: no additional decorative glyphs, no additional animations beyond page transition and color-state hover, no additional taglines or branding marks beyond the wordmark and watermark already present.

## Coding rules
- Backend changes are tiny: one-line sort changes, one-function band-label adjustments, etc. Do not refactor `app.py` for "cleanliness" without a reason.
- Frontend is single-file. Inline CSS in `<style>`, inline JS in `<script>`. Do not split into separate files unless there's a load-time reason.
- The fixed-height heuristic for items-per-column (`ITEM_HEIGHT_PX = 130`) is acknowledged-imperfect; do not "fix" it without replacing it with proper dynamic measurement (and only do that as a deliberate session task, not a side effect of other work).
