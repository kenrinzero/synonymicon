import json
import math
import openpyxl
import re
import urllib.request
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
from flask import Flask, request, jsonify
from gensim.downloader import load as fasttext_load
from nltk.corpus import wordnet
from nltk.stem import WordNetLemmatizer
from wordfreq import zipf_frequency as wordfreq_zipf

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

FASTTEXT_MODEL = fasttext_load('fasttext-wiki-news-subwords-300')

with open('data/websters1913.json') as f:
    WEBSTERS = {k.lower(): v for k, v in json.load(f).items()}

# ── Corpus loaders ───────────────────────────────────────────────────────────

SUBTLEX_ZIPF = {}  # {word_lower: zipf}
GOOGLE_ZIPF = {}  # {word_lower: zipf}
KAGGLE_ZIPF = {}  # {word_lower: zipf}
OPENSUBS_ZIPF = {}  # {word_lower: zipf}
GUTEN_ZIPF = {}  # {word_lower: zipf}
GUTEN_ZIPF = {}  # {word_lower: zipf}
WIKIPEDIA_ZIPF = {}  # {word_lower: zipf}
LEIPZIG_NEWS_ZIPF = {}  # {word_lower: zipf}
LEIPZIG_WEB_COM_ZIPF = {}  # {word_lower: zipf}
BNC_ZIPF = {}       # {word_lower: zipf}
BNC_TOTAL = 85714226  # total tokens in BNC

def _load_leipzig_news():
    with open('data/leipzig_news_2025.txt') as f:
        for line in f:
            parts = line.split('\t')
            if len(parts) != 4:
                continue
            try:
                word = parts[2]
                count = int(parts[1])
                zipf_val = math.log10(count) + 1.74
                LEIPZIG_NEWS_ZIPF[word.lower()] = zipf_val
            except ValueError:
                continue

def _load_leipzig_web_com():
    with open('data/leipzig_web_com_2018.txt') as f:
        for line in f:
            parts = line.split('\t')
            if len(parts) != 4:
                continue
            try:
                word = parts[2]
                count = int(parts[1])
                zipf_val = math.log10(count) + 1.83
                LEIPZIG_WEB_COM_ZIPF[word.lower()] = zipf_val
            except ValueError:
                continue

def _load_wikipedia():
    with open('data/wikipedia_freq.txt') as f:
        for line in f:
            parts = line.split()
            if len(parts) != 2:
                continue
            word, count_str = parts[0], parts[1]
            try:
                count = int(count_str)
                zipf_val = math.log10(count) - 0.5
                WIKIPEDIA_ZIPF[word.lower()] = zipf_val
            except ValueError:
                continue

def _load_kaggle():
    with open('data/kaggle_freq.csv') as f:
        next(f)  # skip header: word,count
        for line in f:
            parts = line.strip().split(',')
            if len(parts) != 2:
                continue
            word, count_str = parts[0], parts[1]
            try:
                count = int(count_str)
                zipf_val = math.log10(count) + 3.0
                KAGGLE_ZIPF[word.lower()] = zipf_val
            except ValueError:
                continue

def _load_opensubtitles():
    with open('data/hermitdave_freq.txt') as f:
        for line in f:
            parts = line.split()
            if len(parts) != 2:
                continue
            word, count_str = parts[0], parts[1]
            try:
                count = int(count_str)
                zipf_val = math.log10(count) + 0.37
                OPENSUBS_ZIPF[word.lower()] = zipf_val
            except ValueError:
                continue

def _load_gutenberg():
    with open('data/scriptsmith_freq.txt') as f:
        for line in f:
            parts = line.split()
            if len(parts) != 2:
                continue
            count_str, word = parts[0], parts[1]
            try:
                count = int(count_str)
                zipf_val = math.log10(count) + 0.37
                GUTEN_ZIPF[word.lower()] = zipf_val
            except ValueError:
                continue

def _load_google():
    with open('data/google_1grams.txt') as f:
        for line in f:
            parts = line.split('\t')
            if len(parts) != 2:
                continue
            word, count_str = parts[0], parts[1]
            try:
                count = int(count_str)
                zipf_val = math.log10(count) + 3.0
                GOOGLE_ZIPF[word.lower()] = zipf_val
            except ValueError:
                continue

def _load_subtlex():
    wb = openpyxl.load_workbook('data/subtlex_us.xlsx', read_only=True, data_only=True)
    ws = wb.active
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i == 0:
            continue  # skip header
        word = row[0]
        if not word or not isinstance(word, str):
            continue
        zipf_val = row[14]  # Zipf-value column (index 14)
        if zipf_val is not None:
            SUBTLEX_ZIPF[word.lower()] = float(zipf_val)
    wb.close()

def _load_bnc():
    with open('data/bnc_all.al') as f:
        for line in f:
            parts = line.split()
            if len(parts) < 4:
                continue
            try:
                freq = int(parts[0])
                word = parts[1]
                # BNC is lemmatized — word is the lemma, use directly
                zipf_val = math.log10(freq * (1_000_000_000 / BNC_TOTAL))
                BNC_ZIPF[word.lower()] = zipf_val
            except ValueError:
                # Skip header lines (e.g. "100106029 !!WHOLE_CORPUS !!ANY 4124")
                continue

_LEMMATIZER = WordNetLemmatizer()

def get_zipf(word, corpus='wordfreq'):
    """Return Zipf frequency for a word from the selected corpus.

    Args:
        word: the word to look up.
        corpus: 'wordfreq' (default), 'subtlex', or 'bnc'.
    """
    wl = word.lower()
    if corpus == 'subtlex':
        return SUBTLEX_ZIPF.get(wl)
    if corpus == 'bnc':
        # BNC is lemmatized — try noun lemma first, then verb lemma as fallback
        lemma = _LEMMATIZER.lemmatize(wl)
        z = BNC_ZIPF.get(lemma)
        if z is None:
            lemma = _LEMMATIZER.lemmatize(wl, 'v')
            z = BNC_ZIPF.get(lemma)
        return z
    if corpus == 'google_1grams':
        return GOOGLE_ZIPF.get(wl)
    if corpus == 'wikipedia':
        return WIKIPEDIA_ZIPF.get(wl)
    if corpus == 'kaggle':
        return KAGGLE_ZIPF.get(wl)
    if corpus == 'opensubtitles':
        return OPENSUBS_ZIPF.get(wl)
    if corpus == 'gutenberg':
        return GUTEN_ZIPF.get(wl)
    if corpus == 'leipzig_news':
        return LEIPZIG_NEWS_ZIPF.get(wl)
    if corpus == 'leipzig_web_com':
        return LEIPZIG_WEB_COM_ZIPF.get(wl)
    return wordfreq_zipf(wl, 'en')

# Load corpora at startup
_load_leipzig_news()
_load_leipzig_web_com()
_load_opensubtitles()
_load_gutenberg()
_load_kaggle()
_load_wikipedia()
_load_google()
_load_subtlex()
_load_bnc()

WIKTIONARY_CACHE = {}
WIKTIONARY_HEADERS = {'User-Agent': 'Synonymicon/0.1 (dev; contact: local)'}
DEFINITION_CACHE = {}


POS_MAP = {'noun': 'n', 'verb': 'v', 'adj': 'a', 'adv': 'r'}


def get_wordnet_candidates(words, pos_filter=None):
    """Collect lemmas from WordNet synsets for one or more words.

    Args:
        words: a single word string OR a list of up to 2 words (for phrases).
               Examples: "run" or ["be", "given"]
        pos_filter: optional set of POS tags to restrict synsets.
    """
    if isinstance(words, str):
        words = [words]

    # Collect synset lemmas per word
    word_synsets = {}
    for w in words:
        synsets = list(wordnet.synsets(w))
        word_synsets[w] = synsets

    candidates = set()

    for w in words:
        for synset in word_synsets[w]:
            if pos_filter and synset.pos() not in pos_filter:
                continue
            for lemma in synset.lemmas():
                name = lemma.name().replace('_', ' ')
                # Exclude the exact phrase match itself
                if name.lower() != ' '.join(words).lower():
                    candidates.add(name)

    # For 2-word phrases, filter candidates to those that contain at least
    # one of the phrase words (and are not just random multi-word results)
    if len(words) == 2:
        w1, w2 = words[0].lower(), words[1].lower()
        filtered = set()
        for c in candidates:
            cl = c.lower()
            # Keep candidates that contain either phrase word as a token,
            # or are exactly the two words in either order
            if w1 in cl.split() or w2 in cl.split() or cl == f"{w1} {w2}" or cl == f"{w2} {w1}":
                filtered.add(c)
        candidates = filtered

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


def get_blended_results(word, tier=None, zmin=None, zmax=None, pos_filter=None, phrase_words=None, corpus='wordfreq'):
    """Merge WordNet + fastText candidates with blended scoring.

    Args:
        pos_filter: optional set of POS tags to restrict WordNet candidates.
                   fastText candidates are included only if they also appear
                   in the WordNet results with a matching POS.
        phrase_words: optional list of words for multi-word phrase lookups.
                      If None, falls back to [word].
        corpus: 'wordfreq' (default) or 'subtlex'.
    """
    wn_words = phrase_words if phrase_words else [word]
    wn_candidates = get_wordnet_candidates(wn_words, pos_filter)
    ft_candidates = get_fasttext_candidates(word)

    # Build scored dict: {lowercase_word: (display_word, score)}
    scored = {}
    for c in wn_candidates:
        key = c.lower()
        scored[key] = (c, WORDNET_SCORE)
    for w, cosine in ft_candidates:
        key = w.lower()
        if key not in scored and cosine >= FASTTEXT_COSINE_CUTOFF and not pos_filter:
            scored[key] = (w.replace('_', ' '), cosine)

    # Frequency filter
    if zmin is not None and zmax is not None:
        lo, hi = zmin, zmax
    elif tier is not None:
        lo, hi = TIERS[tier]
    else:
        raise ValueError("Either tier or both zmin/zmax must be provided")

    morph = get_morphological_variants(word.lower())
    results = []
    for key, (display, score) in scored.items():
        if key in morph or len(key) < 3 or '--' in key or re.search(r'(.)\1{2,}', key) or not key[0].isalpha():
            continue
        cleaned = key.rstrip('-.')
        if cleaned in morph:
            continue
        z = get_zipf(key, corpus)
        # Skip words absent from the selected corpus
        if z is None:
            continue
        if lo <= z < hi:
            results.append((display, z, score))

    # Sort: Zipf descending (rarer first), score descending as tiebreaker
    results.sort(key=lambda x: (-x[1], -x[2]))
    return [(w, z) for w, z, _ in results]


def get_blended_results_multi(word, ranges, pos_filter=None, phrase_words=None, corpus='wordfreq'):
    """Merge WordNet + fastText candidates with blended scoring, filtering across multiple ranges."""
    wn_words = phrase_words if phrase_words else [word]
    wn_candidates = get_wordnet_candidates(wn_words, pos_filter)
    ft_candidates = get_fasttext_candidates(word)

    scored = {}
    for c in wn_candidates:
        key = c.lower()
        scored[key] = (c, WORDNET_SCORE)
    for w, cosine in ft_candidates:
        key = w.lower()
        if key not in scored and cosine >= FASTTEXT_COSINE_CUTOFF and not pos_filter:
            scored[key] = (w.replace('_', ' '), cosine)

    morph = get_morphological_variants(word.lower())
    results = []
    for key, (display, score) in scored.items():
        if key in morph or len(key) < 3 or '--' in key or re.search(r'(.)\1{2,}', key) or not key[0].isalpha():
            continue
        cleaned = key.rstrip('-.')
        if cleaned in morph:
            continue
        z = get_zipf(key, corpus)
        if z is None:
            continue
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
    words_in_phrase = word.split(' ')
    if len(words_in_phrase) > 2:
        return jsonify({'error': 'phrases of up to 2 words are supported'}), 400

    tier = request.args.get('tier')
    min_raw = request.args.get('min')
    max_raw = request.args.get('max')
    pos_raw = request.args.get('pos')
    corpus_raw = request.args.get('corpus', 'wordfreq')

    VALID_POS = {'all', 'noun', 'verb', 'adj', 'adv'}
    VALID_CORPORA = {'wordfreq', 'subtlex', 'bnc', 'google_1grams', 'wikipedia', 'kaggle', 'opensubtitles', 'gutenberg', 'leipzig_news', 'leipzig_web_com'}
    if corpus_raw not in VALID_CORPORA:
        return jsonify({
            'error': f'unknown corpus: {corpus_raw}',
            'available_corpora': list(VALID_CORPORA),
        }), 400
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
        results = get_blended_results(word, zmin=zmin, zmax=zmax, pos_filter=pos_filter, phrase_words=words_in_phrase, corpus=corpus_raw)
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
            results = get_blended_results(word, tier=tier_list[0], pos_filter=pos_filter, phrase_words=words_in_phrase, corpus=corpus_raw)
        else:
            ranges = [TIERS[t] for t in tier_list]
            results = get_blended_results_multi(word, ranges, pos_filter=pos_filter, phrase_words=words_in_phrase, corpus=corpus_raw)

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
