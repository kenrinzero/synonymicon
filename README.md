# Synonymicon

A multi-source synonym discovery tool with frequency-band filtering. Combines WordNet and fastText to surface candidates across the full Zipf range. Pick a corpus, pick a frequency band, get synonyms.

Live at [synonymicon.xyz](https://synonymicon.xyz).

## Stack

- Python 3.12 + Flask (synchronous, single-process, no database)
- [wordfreq](https://github.com/rspeer/wordfreq) for default frequency
- NLTK WordNet for primary synonyms
- fastText (`fasttext-wiki-news-subwords-300` via gensim) for secondary candidates
- Included frequency corpora: wordfreq, SUBTLEX-US, BNC, Google 1-grams, Wikipedia, Kaggle, OpenSubtitles, Project Gutenberg, Leipzig News 2025, Leipzig Web COM 2018, Leipzig Web UK 2018
- Definition fallback chain: Wiktionary REST API → Webster's 1913 (local) → WordNet gloss → `[undefined]`
- Vanilla single-page frontend (no build step, no framework)

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/setup_nltk.py
```

The fastText model (~1 GB) downloads on first run via gensim and is cached under `~/gensim-data/`.

## Run (development)

```bash
flask run --no-reload
```

Use `--no-reload` because fastText loads at module scope and the reloader would spawn two processes that both load it. Startup takes ~2.5–3 minutes.

Server on `localhost:5000`.

## Run (production)

```bash
gunicorn -w 1 -t 120 -b 127.0.0.1:5000 app:app
```

- `-w 1` (one worker) is intentional; each worker loads ~1.5 GB of model + corpus data.
- `-t 120` keeps gunicorn from killing the worker during the long startup.
- Run behind a reverse proxy (nginx, Caddy) for TLS.

## Memory & startup

- Resident memory: ~1.5–2 GB (fastText ~1 GB, corpora ~200 MB, runtime).
- Cold start: ~2.5–3 minutes.
- Not compatible with serverless or sleep-on-idle hosting.

## API

```
GET /synonyms?word=<x>&tier=<t>&pos=<p>&corpus=<c>
```

Returns JSON: `[{word, zipf, definition, band}, ...]`.

| Param  | Values |
|--------|--------|
| `word` | required; up to 2 words for phrase queries |
| `tier` | `all`, `common`, `uncommon`, `rare`, `exotic`, `absurd` (or comma-separated) |
| `pos`  | `all`, `noun`, `verb`, `adj`, `adv` (or comma-separated) |
| `corpus` | `wordfreq` (default), `subtlex`, `bnc`, `google_1grams`, `wikipedia`, `kaggle`, `opensubtitles`, `gutenberg`, `leipzig_news`, `leipzig_web_com`, `leipzig_web_uk` |
| `min`, `max` | optional Zipf floats (advanced mode; overrides `tier`) |

## Layout

```
app.py                  Flask app (all backend logic)
data/                   Corpus files + Webster's 1913
static/index.html       Single-page frontend (HTML + inline CSS + inline JS)
scripts/setup_nltk.py   One-time NLTK data download
requirements.txt        Pinned dependencies
CLAUDE.md               Architecture and design rationale
```

## License

MIT — see [LICENSE](LICENSE).

## Credits

Frequency corpora are credited in-app under the "corpora" link in the footer.
