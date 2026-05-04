import json
import re
import gensim.downloader as api
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
from flask import Flask, request, jsonify
from nltk.corpus import wordnet
from wordfreq import zipf_frequency

app = Flask(__name__)

TIERS = {
    'all':      (float('-inf'), float('inf')),
    'common':   (4.0, float('inf')),
    'uncommon': (3.0, 4.0),
    'rare':     (2.0, 3.0),
    'exotic':   (1.0, 2.0),
    'absurd':   (float('-inf'), 1.0),
}
COMMON_FLOOR = 4.0
WORDNET_SCORE = 1.5
FASTTEXT_COSINE_CUTOFF = 0.65
MAX_DEFINITION_LENGTH = 200

FASTTEXT_MODEL = api.load('fasttext-wiki-news-subwords-300')

with open('data/websters1913.json') as f:
    WEBSTERS = {k.lower(): v for k, v in json.load(f).items()}

WIKTIONARY_CACHE = {}
WIKTIONARY_HEADERS = {'User-Agent': 'Synonymicon/0.1 (dev; contact: local)'}
DEFINITION_CACHE = {}


POS_MAP = {'noun': 'n', 'verb': 'v', 'adj': 'a', 'adv': 'r'}

def get_wordnet_candidates(word, pos_filter=None):
    """Union of lemmas across all synsets for the input word, excluding the input itself.

    Args:
        word: the input word
        pos_filter: optional set of POS tags (e.g., {'n', 'v'}) to restrict synsets.
                   If None, all POS tags are included.
    """
    candidates = set()
    for synset in wordnet.synsets(word):
        if pos_filter and synset.pos() not in pos_filter:
            continue
        for lemma in synset.lemmas():
            name = lemma.name().replace('_', ' ')
            if name.lower() != word.lower():
                candidates.add(name)
    return candidates


def get_fasttext_candidates(word, n=100):
    wl = word.lower()
    try:
        return [(w, score) for w, score in FASTTEXT_MODEL.most_similar(word, topn=n) if w.lower() != wl]
    except KeyError:
        return []


def get_morphological_variants(word):
    """Generate common morphological variants of a word for filtering."""
    w = word.lower()
    variants = {w}
    if w.endswith('e'):
        variants.add(w[:-1] + 'ing')
        variants.add(w[:-1] + 'ed')
    else:
        variants.add(w + 's')
        variants.add(w + 'ed')
        variants.add(w + 'ing')
        variants.add(w + 'er')
        variants.add(w + 'es')
    # Double consonant: stop -> stopped, stopping
    if len(w) >= 3 and w[-1] not in 'aeiou' and w[-2] in 'aeiou' and w[-3] not in 'aeiou':
        variants.add(w + w[-1] + 'ed')
        variants.add(w + w[-1] + 'ing')
        variants.add(w + w[-1] + 'er')
    return variants


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
    key = word.lower()
    if key in DEFINITION_CACHE:
        return DEFINITION_CACHE[key]
    d = get_wiktionary_definition(word)
    if d:
        DEFINITION_CACHE[key] = d
        return d
    d = get_websters_definition(word)
    if d:
        DEFINITION_CACHE[key] = d
        return d
    d = get_wordnet_gloss(word)
    if d:
        DEFINITION_CACHE[key] = d
        return d
    DEFINITION_CACHE[key] = "[undefined]"
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


def get_blended_results(word, tier=None, zmin=None, zmax=None, pos_filter=None):
    """Merge WordNet + fastText candidates with blended scoring.

    Args:
        pos_filter: optional set of POS tags to restrict WordNet candidates.
                   fastText candidates are included only if they also appear
                   in the WordNet results with a matching POS.
    """
    wn_candidates = get_wordnet_candidates(word, pos_filter)
    ft_candidates = get_fasttext_candidates(word)

    # Build scored dict: {lowercase_word: (display_word, score)}
    scored = {}
    for c in wn_candidates:
        key = c.lower()
        scored[key] = (c, WORDNET_SCORE)
    for w, cosine in ft_candidates:
        key = w.lower()
        # When POS filter is active, only include fastText candidates that
        # also appeared in WordNet (already in scored); skip standalone fastText matches.
        if key not in scored and cosine >= FASTTEXT_COSINE_CUTOFF and not pos_filter:
            scored[key] = (w.replace('_', ' '), cosine)

    # Frequency filter
    if zmin is not None and zmax is not None:
        lo, hi = zmin, zmax
    elif tier is not None:
        lo, hi = TIERS[tier]
    else:
        raise ValueError("Either tier or both zmin/zmax must be provided")

    morph = get_morphological_variants(word)
    results = []
    for key, (display, score) in scored.items():
        if key in morph or len(key) < 3 or '--' in key or re.search(r'(.)\1{2,}', key) or not key[0].isalpha():
            continue
        cleaned = key.rstrip('-.')
        if cleaned in morph:
            continue
        z = zipf_frequency(key, 'en')
        if lo <= z < hi:
            results.append((display, z, score))

    # Sort: Zipf descending (rarer first), score descending as tiebreaker
    results.sort(key=lambda x: (-x[1], -x[2]))
    return [(w, z) for w, z, _ in results]


def get_blended_results_multi(word, ranges, pos_filter=None):
    """Merge WordNet + fastText candidates with blended scoring, filtering across multiple ranges."""
    wn_candidates = get_wordnet_candidates(word, pos_filter)
    ft_candidates = get_fasttext_candidates(word)

    scored = {}
    for c in wn_candidates:
        key = c.lower()
        scored[key] = (c, WORDNET_SCORE)
    for w, cosine in ft_candidates:
        key = w.lower()
        if key not in scored and cosine >= FASTTEXT_COSINE_CUTOFF and not pos_filter:
            scored[key] = (w.replace('_', ' '), cosine)

    morph = get_morphological_variants(word)
    results = []
    for key, (display, score) in scored.items():
        if key in morph or len(key) < 3 or '--' in key or re.search(r'(.)\1{2,}', key) or not key[0].isalpha():
            continue
        cleaned = key.rstrip('-.')
        if cleaned in morph:
            continue
        z = zipf_frequency(key, 'en')
        if any(lo <= z < hi for lo, hi in ranges):
            results.append((display, z, score))

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
    if ' ' in word or '_' in word:
        return jsonify({'error': 'single-word searches only; phrases are not yet supported'}), 400

    tier = request.args.get('tier')
    min_raw = request.args.get('min')
    max_raw = request.args.get('max')
    pos_raw = request.args.get('pos')

    VALID_POS = {'all', 'noun', 'verb', 'adj', 'adv'}
    pos_filter = None
    if pos_raw is not None:
        pos_list = [p.strip() for p in pos_raw.split(',')]
        for p in pos_list:
            if p not in VALID_POS:
                return jsonify({
                    'error': f'unknown pos: {p}',
                    'available_pos': list(VALID_POS),
                }), 400
        if 'all' not in pos_list:
            pos_filter = {POS_MAP[p] for p in pos_list}

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
        results = get_blended_results(word, zmin=zmin, zmax=zmax, pos_filter=pos_filter)
    elif has_min or has_max:
        # Exactly one supplied → 400
        return jsonify({'error': 'both min and max must be provided together'}), 400
    else:
        # Neither min nor max → use tier (single or comma-separated)
        if tier is None:
            return jsonify({'error': 'missing required parameter: tier (or min/max)'}), 400
        tier_list = [t.strip() for t in tier.split(',')]
        for t in tier_list:
            if t not in TIERS:
                return jsonify({
                    'error': f'unknown tier: {t}',
                    'available_tiers': list(TIERS.keys()),
                }), 400
        if len(tier_list) == 1:
            results = get_blended_results(word, tier=tier_list[0], pos_filter=pos_filter)
        else:
            ranges = [TIERS[t] for t in tier_list]
            results = get_blended_results_multi(word, ranges, pos_filter=pos_filter)

    words = [w for w, z in results]
    with ThreadPoolExecutor(max_workers=10) as pool:
        definitions = list(pool.map(get_definition, words))

    def truncate(d):
        if d == "[undefined]" or len(d) <= MAX_DEFINITION_LENGTH:
            return d
        return d[:MAX_DEFINITION_LENGTH].rsplit(' ', 1)[0] + '…'

    return jsonify([
        {'word': w, 'zipf': z, 'definition': truncate(d), 'band': get_band_label(z)}
        for (w, z), d in zip(results, definitions)
    ])


if __name__ == '__main__':
    app.run(debug=True)
