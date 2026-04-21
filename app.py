import gensim.downloader as api
from flask import Flask, request, jsonify
from nltk.corpus import wordnet
from wordfreq import zipf_frequency

app = Flask(__name__)

TIERS = {
    'uncommon': (3.0, 4.0),
    'rare':     (2.0, 3.0),
    'exotic':   (1.0, 2.0),
    'absurd':   (float('-inf'), 1.0),
}
COMMON_FLOOR = 4.0
WORDNET_SCORE = 1.5
FASTTEXT_COSINE_CUTOFF = 0.6

FASTTEXT_MODEL = api.load('fasttext-wiki-news-subwords-300')


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

    # Sort: score descending, Zipf ascending as tiebreaker
    results.sort(key=lambda x: (-x[2], x[1]))
    return [(w, z) for w, z, _ in results]


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
        {'word': w, 'zipf': z, 'definition': None}
        for w, z in results
    ])


if __name__ == '__main__':
    app.run(debug=True)
