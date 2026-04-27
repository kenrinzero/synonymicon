import json
import gensim.downloader as api
import requests
from bs4 import BeautifulSoup
from flask import Flask, request, jsonify
from nltk.corpus import wordnet
from wordfreq import zipf_frequency

app = Flask(__name__)

TIERS = {
    'all':      (float('-inf'), 4.0),
    'uncommon': (3.0, 4.0),
    'rare':     (2.0, 3.0),
    'exotic':   (1.0, 2.0),
    'absurd':   (float('-inf'), 1.0),
}
COMMON_FLOOR = 4.0
WORDNET_SCORE = 1.5
FASTTEXT_COSINE_CUTOFF = 0.65

FASTTEXT_MODEL = api.load('fasttext-wiki-news-subwords-300')

with open('data/websters1913.json') as f:
    WEBSTERS = {k.lower(): v for k, v in json.load(f).items()}

WIKTIONARY_CACHE = {}
WIKTIONARY_HEADERS = {'User-Agent': 'Synonymicon/0.1 (dev; contact: local)'}


def get_wordnet_candidates(word):
    """Union of lemmas across all synsets for the input word, excluding the input itself."""
    candidates = set()
    for synset in wordnet.synsets(word):
        for lemma in synset.lemmas():
            name = lemma.name().replace('_', ' ')
            if name.lower() != word.lower():
                candidates.add(name)
    return candidates


def get_fasttext_candidates(word, n=100):
    try:
        return [(w, score) for w, score in FASTTEXT_MODEL.most_similar(word, topn=n) if w != word]
    except KeyError:
        return []


def get_wiktionary_definition(word):
    key = word.lower()
    if key in WIKTIONARY_CACHE:
        return WIKTIONARY_CACHE[key]
    try:
        url = f'https://en.wiktionary.org/api/rest_v1/page/definition/{key}'
        r = requests.get(url, headers=WIKTIONARY_HEADERS, timeout=2.0)
        if r.status_code != 200:
            WIKTIONARY_CACHE[key] = None
            return None
        data = r.json()
        en_entries = data.get('en')
        if not en_entries:
            WIKTIONARY_CACHE[key] = None
            return None
        definitions = en_entries[0].get('definitions', [])
        if not definitions:
            WIKTIONARY_CACHE[key] = None
            return None
        html = definitions[0].get('definition', '')
        text = BeautifulSoup(html, 'html.parser').get_text().strip()
        WIKTIONARY_CACHE[key] = text if text else None
        return WIKTIONARY_CACHE[key]
    except Exception:
        WIKTIONARY_CACHE[key] = None
        return None


def get_websters_definition(word):
    return WEBSTERS.get(word.lower())


def get_wordnet_gloss(word):
    synsets = wordnet.synsets(word)
    if synsets:
        defn = synsets[0].definition()
        if defn:
            return defn
    return None


def get_definition(word):
    d = get_wiktionary_definition(word)
    if d:
        return d
    d = get_websters_definition(word)
    if d:
        return d
    d = get_wordnet_gloss(word)
    if d:
        return d
    return "[undefined]"


def get_band_label(zipf):
    """Map a Zipf frequency score to a band label."""
    if zipf >= COMMON_FLOOR:
        return 'common'
    elif zipf >= 3.0:
        return 'uncommon'
    elif zipf >= 2.0:
        return 'rare'
    elif zipf >= 1.0:
        return 'exotic'
    else:
        return 'absurd'


def get_blended_results(word, tier=None, zmin=None, zmax=None):
    """Merge WordNet + fastText candidates with blended scoring."""
    # Gather candidates from both sources
    wn_candidates = get_wordnet_candidates(word)
    ft_candidates = get_fasttext_candidates(word)

    # Build scored dict: {lowercase_word: (display_word, score)}
    scored = {}
    for c in wn_candidates:
        key = c.lower()
        scored[key] = (c, WORDNET_SCORE)
    for w, cosine in ft_candidates:
        key = w.lower()
        if key not in scored and cosine >= FASTTEXT_COSINE_CUTOFF:
            scored[key] = (w.replace('_', ' '), cosine)

    # Frequency filter
    if zmin is not None and zmax is not None:
        lo, hi = zmin, zmax
    elif tier is not None:
        lo, hi = TIERS[tier]
    else:
        raise ValueError("Either tier or both zmin/zmax must be provided")

    results = []
    for key, (display, score) in scored.items():
        z = zipf_frequency(key, 'en')
        if z < COMMON_FLOOR and lo <= z < hi:
            results.append((display, z, score))

    # Sort: Zipf descending (rarer first), score descending as tiebreaker
    results.sort(key=lambda x: (-x[1], -x[2]))
    return [(w, z) for w, z, _ in results]


@app.route('/')
def index():
    return app.send_static_file('index.html')


@app.route('/synonyms')
def synonyms():
    word = request.args.get('word')
    if not word:
        return jsonify({'error': 'missing required parameter: word'}), 400

    tier = request.args.get('tier')
    min_raw = request.args.get('min')
    max_raw = request.args.get('max')

    has_min = min_raw is not None
    has_max = max_raw is not None

    # Parameter precedence for frequency range
    if has_min and has_max:
        # Both supplied → advanced mode; tier ignored
        try:
            zmin = float(min_raw)
            zmax = float(max_raw)
        except ValueError:
            return jsonify({'error': 'min and max must be numeric'}), 400
        results = get_blended_results(word, zmin=zmin, zmax=zmax)
    elif has_min or has_max:
        # Exactly one supplied → 400
        return jsonify({'error': 'both min and max must be provided together'}), 400
    else:
        # Neither min nor max → use tier
        if tier is None:
            return jsonify({'error': 'missing required parameter: tier (or min/max)'}), 400
        if tier not in TIERS:
            return jsonify({
                'error': f'unknown tier: {tier}',
                'available_tiers': list(TIERS.keys()),
            }), 400
        results = get_blended_results(word, tier=tier)

    return jsonify([
        {'word': w, 'zipf': z, 'definition': get_definition(w), 'band': get_band_label(z)}
        for w, z in results
    ])


if __name__ == '__main__':
    app.run(debug=True)
