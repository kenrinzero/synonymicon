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


def get_wordnet_candidates(word):
    """Union of lemmas across all synsets for the input word, excluding the input itself."""
    candidates = set()
    for synset in wordnet.synsets(word):
        for lemma in synset.lemmas():
            name = lemma.name().replace('_', ' ')
            if name.lower() != word.lower():
                candidates.add(name)
    return candidates


def filter_by_zipf(candidates, tier=None, zmin=None, zmax=None):
    """Look up Zipf for each candidate, filter by range, return sorted list of (word, zipf)."""
    if zmin is not None and zmax is not None:
        lo, hi = zmin, zmax
    elif tier is not None:
        lo, hi = TIERS[tier]
    else:
        raise ValueError("Either tier or both zmin/zmax must be provided")

    results = []
    for word in candidates:
        z = zipf_frequency(word, 'en')
        if z < COMMON_FLOOR and lo <= z < hi:
            results.append((word, z))
    results.sort(key=lambda x: x[0])
    return results


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
        candidates = get_wordnet_candidates(word)
        results = filter_by_zipf(candidates, zmin=zmin, zmax=zmax)
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
        candidates = get_wordnet_candidates(word)
        results = filter_by_zipf(candidates, tier=tier)

    return jsonify([
        {'word': w, 'zipf': z, 'definition': None}
        for w, z in results
    ])


if __name__ == '__main__':
    app.run(debug=True)
