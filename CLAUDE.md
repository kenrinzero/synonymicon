# Synonymicon — CLAUDE.md

## What this is
A frequency-driven discovery tool for obscure English synonyms. Not a general thesaurus or dictionary. Not a vocabulary learning tool. Common words are inputs, not outputs. The point is to excavate rare lexical outliers at user-controlled levels of obscurity.

## Stack
- **Python + Flask**, synchronous, single-process
- **No database** — all state computed on the fly, nothing persisted
- **wordfreq** for frequency: `zipf_frequency(word, 'en')` at query time. No precomputed frequency index. Zipf scale: 0 = vanishingly rare, 7 = extremely common
- **NLTK WordNet** — primary synonym source (synset lemmas)
- **fastText** (fasttext-wiki-news-subwords-300 via gensim) — secondary/fallback synonym source. Note: the gensim distribution is KeyedVectors (pretrained vectors only), not the full FastText model — OOV inputs raise KeyError and must be caught. WordNet still covers OOV cases.
- **Definition fallback chain:** Wiktionary API → Webster's 1913 (local JSON at `data/websters1913.json`) → WordNet gloss → `"[undefined]"` (literal string, rendered in italics). Wiktionary REST API requires a descriptive `User-Agent` header per Wikimedia policy — requests without one return 403 or get rate-limited. Use `requests` for fetches and `beautifulsoup4` (`bs4`) for HTML stripping.
- Frontend: single-file HTML/CSS/JS served from `static/`. Modern Light theme only for MVP

## Layout
- `app.py` — Flask app, all backend logic
- `data/websters1913.json` — Webster's 1913, loaded at startup
- `static/` — frontend (used from Session 4)
- `.venv/` — Python venv (gitignored)

## Frequency tiers
```python
TIERS = {
    'uncommon': (3.0, 4.0),
    'rare':     (2.0, 3.0),
    'exotic':   (1.0, 2.0),
    'absurd':   (float('-inf'), 1.0),
}
COMMON_FLOOR = 4.0  # Zipf >= 4.0 excluded from all results
```
Tier filtering: `zmin <= z < zmax`. Advanced mode accepts raw Zipf min/max instead.

## Synonym scoring
Blended single list, no source labels exposed in UI:
- WordNet candidates: flat score = 1.5
- fastText candidates: score = cosine similarity
- Overlap: WordNet wins (true synonym trumps embedding neighbor)
- Normalize for comparison/lookup on lowercase; WordNet lemma underscores become spaces
- Multiword candidates are allowed for MVP
- fastText cosine cutoff: `FASTTEXT_COSINE_CUTOFF = 0.6` (candidates below this are dropped)
- Sort: score descending, Zipf ascending as tiebreaker (rarer first within score band)

## API
`GET /synonyms?word=<x>&tier=<t>` — returns JSON list of `{word, zipf, definition}`
Optional: `min` and `max` (Zipf floats) for advanced mode.

Parameter precedence:
- Both `min` and `max` → advanced mode; `tier` ignored if present
- Exactly one of `min`/`max` → 400
- Neither → use `tier`; missing `tier` → 400
- Unknown `tier` value → 400 with available tier names
- Missing `word` → 400

## Run commands
```bash
cd ~/projects/synonymicon
source .venv/bin/activate
flask run --debug
```
Dev server on localhost:5000.

## Non-goals — do not add these
- General synonyms or common words in results
- Dictionary-like features (etymology, pronunciation, usage examples)
- Languages other than English
- Dark, OLED, or Dictionary visual themes (post-MVP)
- Part-of-speech filtering (post-MVP)
- Pivot-on-click (post-MVP)
- Mobile-specific layout 
- Any database, ORM, or persistent storage
- Additional frequency corpora beyond wordfreq (post-MVP)

## Scope rails
- Do not introduce a database
- Ephemeral in-memory caches are fine; do not add persistent storage
- Do not add features outside the MVP scope listed above
- Do not "improve" the minimalist UI with animations, shadows, or unrequested elements
- The recursive scrolling loop (results rendered twice for seamless endless effect) is intentional — do not "fix" it
- Keep the frontend as simple inline HTML/CSS/JS. No build tools, no bundler, no framework
