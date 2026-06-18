from concurrent.futures import ThreadPoolExecutor
import json
import logging
import sys
import time
from flask import Flask, request, jsonify
from config import TIERS, POS_MAP, MAX_DEFINITION_LENGTH, VALID_POS, VALID_RANKS, VALID_CORPORA
from candidates import get_blended_results, get_blended_results_multi, get_band_label, get_senses
from corpora import get_zipf
from definitions import get_definition

app = Flask(__name__)

# Minimal structured logging: JSON-formatted request/error records to stderr.
_logger = logging.getLogger('synonymicon')
_handler = logging.StreamHandler(sys.stderr)
_handler.setFormatter(logging.Formatter('%(message)s'))
_logger.addHandler(_handler)
_logger.setLevel(logging.INFO)


def _log_json(event, **kwargs):
    payload = {'event': event, 'timestamp': time.time()}
    payload.update(kwargs)
    _logger.info(json.dumps(payload))


@app.after_request
def _after_request(response):
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "font-src https://fonts.gstatic.com; "
        "style-src 'self' https://fonts.googleapis.com 'unsafe-inline'; "
        "script-src 'unsafe-inline'"
    )
    _log_json('request', method=request.method, path=request.path,
              status=response.status_code, remote_addr=request.remote_addr)
    return response

# Simple token-bucket rate limiter: ~60 requests per minute per IP.
# No external dependency; in-memory and process-local.
_RATE_LIMIT = 60  # requests per window
_RATE_WINDOW = 60  # seconds
_buckets: dict[str, tuple[float, int]] = {}

def _rate_limit():
    ip = request.remote_addr or '127.0.0.1'
    now = time.time()
    stale = [k for k, (ws, _) in _buckets.items() if now - ws >= _RATE_WINDOW * 2]
    for k in stale:
        del _buckets[k]
    if ip in _buckets:
        window_start, count = _buckets[ip]
        if now - window_start >= _RATE_WINDOW:
            _buckets[ip] = (now, 1)
            return None
        if count >= _RATE_LIMIT:
            return jsonify({'error': 'rate limit exceeded, try again later'}), 429
        _buckets[ip] = (window_start, count + 1)
    else:
        _buckets[ip] = (now, 1)
    return None


@app.route('/')
def index():
    return app.send_static_file('index.html')


@app.route('/health')
def health():
    status = {'status': 'ok', 'checks': {}}
    try:
        from nltk.corpus import wordnet
        wordnet.synsets('test')
        status['checks']['wordnet'] = 'ok'
    except (ImportError, AttributeError, KeyError) as e:
        status['checks']['wordnet'] = 'fail'
        status['status'] = 'error'
    try:
        from corpora import LOADED_CORPORA
        if LOADED_CORPORA:
            status['checks']['corpora'] = f'{len(LOADED_CORPORA)} loaded'
        else:
            status['checks']['corpora'] = 'none'
            status['status'] = 'error'
    except (ImportError, NameError):
        status['checks']['corpora'] = 'fail'
        status['status'] = 'error'
    code = 200 if status['status'] == 'ok' else 503
    return jsonify(status), code


@app.route('/synonyms')
def synonyms():
    limited = _rate_limit()
    if limited:
        return limited
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

    # Check if the query word exists in the selected corpus's frequency table.
    query_in_corpus = get_zipf(word, corpus_raw) is not None if len(words_in_phrase) == 1 else None

    words = [w for w, z in results]
    with ThreadPoolExecutor(max_workers=10) as pool:
        definitions = list(pool.map(get_definition, words))

    def truncate(d):
        if d == "[undefined]" or len(d) <= MAX_DEFINITION_LENGTH:
            return d
        return d[:MAX_DEFINITION_LENGTH].rsplit(' ', 1)[0] + '…'

    return jsonify({
        'senses': senses,
        'query_in_corpus': query_in_corpus,
        'results': [
            {'word': w, 'zipf': z, 'definition': truncate(d), 'band': get_band_label(z)}
            for (w, z), d in zip(results, definitions)
        ],
    })


if __name__ == '__main__':
    import os
    # Debug (Werkzeug reloader + interactive debugger) is off by default; opt in
    # with FLASK_DEBUG=1 for local use only. Production runs via gunicorn.
    app.run(debug=os.environ.get('FLASK_DEBUG') == '1')
