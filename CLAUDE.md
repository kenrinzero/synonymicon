# Synonymicon

## What this is
A multi-source synonym discovery tool with frequency-band filtering. The combined WordNet + fastText pipeline returns candidates; the user filters by frequency band. Originally framed as obscurity-only ("excavate rare lexical outliers"); the framing is broadening toward "better thesaurus including obscure stuff" — the architecture has value across the full Zipf range, not only the rare end.

Not a vocabulary learning tool. Not a definitions-first tool — definitions are supporting context for picking the right candidate.

## Stack
- **Python + Flask**, synchronous, single-process
- **No database** — all state computed on the fly, nothing persisted
- **wordfreq** for frequency: `zipf_frequency(word, 'en')` at query time. No precomputed frequency index. Zipf scale: 0 = vanishingly rare, 7 = extremely common
- **NLTK WordNet** — primary synonym source (synset lemmas)
- **fastText** (fasttext-wiki-news-subwords-300 via gensim) — secondary/fallback synonym source. Note: the gensim distribution is KeyedVectors (pretrained vectors only), not the full FastText model — OOV inputs raise KeyError and must be caught. WordNet still covers OOV cases.
- **Definition fallback chain:** Wiktionary API → Webster's 1913 (local JSON at `data/websters1913.json`) → WordNet gloss → `"[undefined]"` (literal string, rendered in italics). Wiktionary REST API requires a descriptive `User-Agent` header per Wikimedia policy — requests without one return 403 or get rate-limited. Use `requests` for fetches and `beautifulsoup4` (`bs4`) for HTML stripping.
- **Corpus frequency tables** — `data/subtlex_us.xlsx` (SUBTLEX-US, Brysbaert & New 2009) and `data/bnc_lemmas.txt` (BNC, Kilgarriff) loaded at startup alongside wordfreq. `get_zipf(word, corpus)` dispatches to the selected source. SUBTLEX-US Zipf values are pre-computed in the spreadsheet; BNC Zipf is computed as `log10(count × 1B / 85_714_226)` from raw lemma counts.
- **Frontend:** single-page HTML/CSS/JS served from `static/`. Three themes cycled via footer button, persisted in localStorage. Right-heavier layout (38/62); integrated search/control surface on the left; single rounded word surface containing column cells on the right.

## Layout
- `app.py` — Flask app, all backend logic
- `data/websters1913.json` — Webster's 1913, loaded at startup
- `data/subtlex_us.xlsx` — SUBTLEX-US frequency table (Brysbaert & New 2009), loaded at startup
- `data/bnc_lemmas.txt` — BNC lemma frequency list (Kilgarriff), downloaded and loaded at startup
- `static/` — frontend files (`index.html`; CSS and JS inline in the same file)
- `.venv/` — Python venv (gitignored)

### Mobile layout (≤768px)
Single breakpoint at `max-width: 768px`:
- `.layout` switches to `grid-template-columns: 1fr; grid-template-rows: auto 1fr; gap: 0`
- `.left-panel` gets `flex-direction: column; min-width: 0`
- Search tray: full-width, `border-radius: 0`, box-shadow removed, `border-bottom: 1px solid var(--border)` only
- Watermark `&` hidden
- `.control-button` uses `flex: 0 0 auto` (auto-width, not fixed 8rem) so three controls fit on narrow viewports
- Nav arrows repositioned inside surface edges; `.nav-arrow.left { left: 0.25rem }`, `.nav-arrow.right { right: 0.25rem }`
- Footer: `position: sticky; bottom: 0; z-index: 20`; about button hidden via `footer .footer-link.about { display: none }`
- `100dvh` used instead of `100vh` on `html, body, .shell` to handle mobile browser chrome
- `overflow: hidden` on `.layout`, `.right-panel`, `.word-surface`, `.columns-grid` to prevent content overflow on small viewports

## Themes
Three themes cycled via a footer button, persisted in localStorage. Cycle order: lumen → penumbra → umbra → lumen.

- `lumen` — light, warm-paper background. Default on first load.
- `penumbra` — dark, `#1a1a1e` background.
- `umbra` — OLED black, true `#000` background.

All color properties use CSS variables overridden by `body[data-theme="..."]`. Hardcoded rgba values in page dots, entry headwords, and footer links were replaced with variables in Session 7b — keep this discipline; new color uses must go through variables, not raw rgba.

## Frequency tiers
```python
TIERS = {
    'all':      (float('-inf'), float('inf')),  # default; everything
    'common':   (4.0, float('inf')),
    'uncommon': (3.0, 4.0),
    'rare':     (2.0, 3.0),
    'exotic':   (1.0, 2.0),
    'absurd':   (float('-inf'), 1.0),
}
COMMON_FLOOR = 4.0  # band-label threshold; no longer used for filtering
```
Tier filtering: `zmin <= z < zmax`. Advanced mode accepts raw Zipf min/max instead (backend-supported, UI-deferred).

## Candidate filtering
Results from both WordNet and fastText pass through these filters before frequency matching:
- **Query exclusion:** case-insensitive match against the input word
- **Morphological variants:** query word + common inflections (-s, -ed, -ing, -er, -es, double-consonant variants)
- **Repeated characters:** any character repeating 3+ times (`re.search(r'(.)\1{2,}', key)`)
- **Non-letter start:** result must begin with `[a-z]`
- **Double hyphen:** `--` in key
- **Short words:** fewer than 3 characters
- **Trailing punctuation cleanup:** artifacts like "walk-" or "walk." stripped and re-checked against morph set

## Definition truncation
Definitions over 200 characters are truncated at the last word boundary with "…" appended. The full definition is cached in `DEFINITION_CACHE`; truncation happens at API response time only.

## Band labels
The API includes a `band` field on each result. Band labels match `TIERS` keys exactly. This was off-by-one before Session 7b's fix; `get_band_label(zipf)` in `app.py` is the single source of truth, and any change to `TIERS` boundaries must update `get_band_label` in lockstep.

| Zipf range | `band` value |
|---|---|
| Zipf ≥ 4.0 | `common` |
| 3.0 ≤ Zipf < 4.0 | `uncommon` |
| 2.0 ≤ Zipf < 3.0 | `rare` |
| 1.0 ≤ Zipf < 2.0 | `exotic` |
| Zipf < 1.0 | `absurd` |

## Synonym scoring
Blended single list, no source labels exposed in UI:
- WordNet candidates: flat score = 1.5
- fastText candidates: score = cosine similarity
- Overlap: WordNet wins (true synonym trumps embedding neighbor)
- Normalize for comparison/lookup on lowercase; WordNet lemma underscores become spaces
- Multiword candidates are allowed for MVP
- fastText cosine cutoff: `FASTTEXT_COSINE_CUTOFF = 0.65` 
- **Sort: Zipf descending, score descending as tiebreaker.** 

## API
`GET /synonyms?word=<x>&tier=<t>&pos=<p>&corpus=<c>` — returns JSON list of `{word, zipf, definition, band}`.
Optional: `min` and `max` (Zipf floats) for advanced mode.

Valid `tier` values: `all` (default), `common`, `uncommon`, `rare`, `exotic`, `absurd`. Comma-separated lists accepted (`tier=uncommon,rare`).

Valid `pos` values: `all` (default), `noun`, `verb`, `adj`, `adv`. Multi-select: `noun,verb`. When `pos` is specified, WordNet candidates are filtered to matching POS synsets; fastText standalone candidates are excluded (fastText has no POS metadata). Unknown `pos` values return 400 with `available_pos` list.

Valid `corpus` values: `wordfreq` (default), `subtlex` (SUBTLEX-US film subtitles), `bnc` (British National Corpus, lemmatized). Controls which frequency table is used for Zipf filtering. Unknown values return 400 with `available_corpora` list.

**BNC lemmatization:** BNC is a lemmatized corpus — `walk`, `walks`, `walked`, `walking` all collapse to the lemma `walk`. The query word is lemmatized via NLTK `WordNetLemmatizer` (noun form first, verb form as fallback) before BNC Zipf lookup.

Phrases of up to 2 words supported (e.g., `word=hard+work`). 3+ words return 400.

## Performance
- **Definition cache:** `DEFINITION_CACHE` at module scope caches full `get_definition` results. Repeated lookups across queries are instant.
- **Concurrent fetches:** `/synonyms` uses `ThreadPoolExecutor(max_workers=10)` for parallel definition lookups. Fresh queries ~5-10x faster than sequential; cache-hit queries near-instant.

Parameter precedence:
- Both `min` and `max` → advanced mode; `tier` ignored if present
- Exactly one of `min`/`max` → 400
- Neither → use `tier`; missing `tier` → 400
- Unknown `tier` value → 400 with available tier names
- Missing `word` → 400

## Frontend control surface (left panel)
The left panel contains, top to bottom:

1. **Serif "Synonymicon" wordmark** in the top-left corner — just the word in a serif face, 1.75rem (Session 7b bump). No logo glyph, no ornament.
2. **Integrated search/control surface**, anchored at the upper-third (margin-top ~18vh), structured as a single rounded "tray" containing:
   - Inner search card (input field with magnifying-glass icon and submit-arrow button). Placeholder text: `discover`.
   - Three flat dropdowns sitting on the tray below the search card: `corpus: <current>`, `frequency: <current>`, and `pos: <current>`.
   - The tray, search card, and dropdowns form three layered visual surfaces — outer tray (`--surface`), inner search card (`--column`), and the bare dropdowns on the tray.
3. **Watermark `&` glyph** in the bottom-left, ~18rem, ~7% opacity, fills the otherwise-empty lower portion of the panel.

Frequency dropdown is checkbox-style with multi-select. `all` is mutually exclusive with bands; selecting any band deselects `all`. Empty selection reverts to `all`. Selecting all individual bands collapses to `all`. Trigger label shows `all` when all selected, band name when one selected, `custom` when multiple selected. A divider separates `all` from the band options.

POS dropdown mirrors the frequency pattern: `all` mutually exclusive with individual POSes. Trigger label shows `all` / POS name / `custom`. Selecting all collapses to `all`.

| UI label | `tier` param |
|---|---|
| `all` (default) | `all` |
| `common` | `common` |
| `10k-30k` | `uncommon` |
| `30k-80k` | `rare` |
| `80k-150k` | `exotic` |
| `150k+` | `absurd` |

Display labels (`10k-30k`, etc.) are display-only; backend filters on Zipf.

The corpus dropdown has three options: `wordfreq` (general English internet-derived frequencies, default), `subtlex` (SUBTLEX-US film subtitle frequencies, Brysbaert & New 2009), and `bnc` (British National Corpus, lemmatized, Kilgarriff). Switching corpora re-filters results through the selected frequency table; tier boundaries (Zipf values) remain fixed — only the per-word Zipf value changes. Corpus selection is persisted in URL params (`?corpus=...`) and restored on back/forward navigation and page load.

## Frontend results surface (right panel)
The right panel holds one rounded "word surface" containing column cells per page. Pagination is page-based, not continuous-scroll.

- **Responsive column count.** Column count adapts to window width via `getColumnsPerPage()`: ≥1150px → 3 columns, ≥800px → 2 columns, <800px → 1 column. Grid template columns and width are set inline by JS. Resize handler debounced at 150ms.
- **Continuous-flow chunking.** Results fill column 1 to capacity, overflow to column 2, then column 3, then page 2's column 1, etc. The fill logic is continuous; only the visible window is paginated.
- **Peek column.** When more pages exist and column count > 1, ~36px of the next page's first column bleeds past the surface's right edge as an affordance signaling "more results continue." Disabled at 1-column width. On the last page, the columns sit flush with no peek.
- **Page indicator.** Bar-style active dot (wider, darker) with thin dots for inactive pages, centered below the columns. Clickable.
- **Edge arrows.** Left and right circular arrow buttons positioned outside the surface edges. Disabled (faded) when at the bounds.
- **Page transition.** 220ms fade + slight horizontal slide on page change. The columns container has its `key`-equivalent state cycled to retrigger the animation.

### Within columns
- **Entry layout:** serif headword (~2rem, slight letterspacing), small superscript Zipf badge, italic serif definition (~1rem, muted color, ~1.35 line-height).
- **Pivot-on-click:** clicking a result headword fires a new search for that word. `cursor: pointer` is the only visual affordance — no underlines, no link styling. Page resets to 1 on pivot. Browser history via `history.pushState({word, tiers, pos})`; `popstate` listener restores word + tier + pos on back/forward. On page load, `?word=...&tier=...&pos=...` params are read and auto-searched (bookmarkable queries).

**Brand wordmark reset.** The "Synonymicon" wordmark is clickable and resets to the empty state. Enter key with an empty search field also triggers the reset. `history.replaceState` clears the URL so refreshing on the empty state stays there.
- **Hover state:** color deepens on both headword and definition. No movement, no scale, no shadow change.
- **`[undefined]` rendering:** italic, lighter muted color than regular definitions.
- **Band separators (Session 7b):** when results span multiple bands and the current page contains a band transition, a small-caps muted header with hairline divider above appears inline at the position of the transition. Cross-column tracking via `prevBand` state through the render loop ensures a continuing band does not get a redundant header at the top of a new column. A new band starting at the top of a column does get a header.

### Surface layering
- **Outer word surface:** `--surface` background, large radius (`--radius-outer`, 2rem), soft shadow.
- **Inner column cells:** `--column` background, smaller radius (`--radius-inner`, 1.5rem), subtle shadow, hairline border. Use `background-clip: padding-box` to avoid corner-leak rendering artifacts. Scrollable vertically (`overflow-y: auto`) so long band sections don't clip.
- The two-level layering (outer surface + inner cells) is intentional and earns its complexity by making the column boundaries legible without dividers.

## Frontend states
- **Loading:** 6px dot, 1.2s pulse animation, anchored bottom-center of the word surface.
- **Empty:** contextual message — `begin with a word` when no query has been issued, `no synonyms found in this band` when a query returned zero results in the selected tier. Empty state renders directly on the `--surface` tray background without a `.column-cell` wrapper — the message cell uses `grid-column: 1/-1; display: grid; place-items: center`.
- **Error:** muted red message in the word surface area.

## Run commands
```bash
cd ~/projects/synonymicon
source .venv/bin/activate
flask run --no-reload
```
Dev server on localhost:5000. Use `--no-reload` because the fastText model loads at module scope and the reloader would spawn two processes that both load it. Server startup ~2.5–3 minutes due to fastText (~1GB into RAM).

## Non-goals — do not add these
- General synonyms across the full frequency range with no filtering applied (the multi-source pipeline is broad, but the tool always exposes frequency as a control)
- Dictionary-like features beyond definition (etymology, pronunciation, usage examples)
- Languages other than English
- A fourth or fifth ad-hoc theme — three is the committed set; further themes need a deliberate session
- `simple / advanced` mode toggle in the UI (backend `min`/`max` params remain supported; UI exposure deferred indefinitely)
- Any database, ORM, or persistent storage

## Scope rails
- Do not introduce a database. Ephemeral in-memory caches are fine; do not add persistent storage. (The definition cache is in-memory module-scope only.)
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
- When a `Planned for Session 8` item lands, fold it into the relevant spec section in the same change and remove the bullet. The planned-changes section is a staging area, not permanent documentation.
