from concurrent.futures import ThreadPoolExecutor
from flask import Flask, request, jsonify
from config import TIERS, POS_MAP, MAX_DEFINITION_LENGTH, VALID_POS, VALID_RANKS, VALID_CORPORA
from candidates import get_blended_results, get_blended_results_multi, get_band_label, get_senses
from definitions import get_definition

app = Flask(__name__)


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
    rank_raw = request.args.get('rank', 'common')

    if rank_raw not in VALID_RANKS:
        return jsonify({
            'error': f'unknown rank: {rank_raw}',
            'available_ranks': list(VALID_RANKS),
        }), 400
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

    if has_min and has_max:
        try:
            zmin = float(min_raw)
            zmax = float(max_raw)
        except ValueError:
            return jsonify({'error': 'min and max must be numeric'}), 400
        results = get_blended_results(word, zmin=zmin, zmax=zmax, pos_filter=pos_filter, phrase_words=words_in_phrase, corpus=corpus_raw, rank=rank_raw)
    elif has_min or has_max:
        return jsonify({'error': 'both min and max must be provided together'}), 400
    else:
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
            results = get_blended_results(word, tier=tier_list[0], pos_filter=pos_filter, phrase_words=words_in_phrase, corpus=corpus_raw, rank=rank_raw)
        else:
            ranges = [TIERS[t] for t in tier_list]
            results = get_blended_results_multi(word, ranges, pos_filter=pos_filter, phrase_words=words_in_phrase, corpus=corpus_raw, rank=rank_raw)

    senses = get_senses(word, pos_filter) if len(words_in_phrase) == 1 else []

    words = [w for w, z in results]
    with ThreadPoolExecutor(max_workers=10) as pool:
        definitions = list(pool.map(get_definition, words))

    def truncate(d):
        if d == "[undefined]" or len(d) <= MAX_DEFINITION_LENGTH:
            return d
        return d[:MAX_DEFINITION_LENGTH].rsplit(' ', 1)[0] + '…'

    return jsonify({
        'senses': senses,
        'results': [
            {'word': w, 'zipf': z, 'definition': truncate(d), 'band': get_band_label(z)}
            for (w, z), d in zip(results, definitions)
        ],
    })


if __name__ == '__main__':
    app.run(debug=True)
