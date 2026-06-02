import os

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

FASTTEXT_ENABLED = os.environ.get('SYNONYMICON_FASTTEXT', '1') != '0'

POS_MAP = {'noun': 'n', 'verb': 'v', 'adj': 'a', 'adv': 'r'}

VALID_POS = {'all', 'noun', 'verb', 'adj', 'adv'}
VALID_RANKS = {'common', 'rare', 'relevance'}

_ALL_CORPORA = {
    'wordfreq', 'subtlex', 'bnc', 'google_1grams', 'wikipedia',
    'kaggle', 'opensubtitles', 'gutenberg', 'leipzig_news',
    'leipzig_web_com', 'leipzig_web_uk',
}

# Prune to only the corpora that actually loaded at startup.
# corpora.LOADED_CORPORA is populated by _load_all() at import time.
try:
    from corpora import LOADED_CORPORA
    VALID_CORPORA = _ALL_CORPORA & LOADED_CORPORA
except Exception:
    VALID_CORPORA = _ALL_CORPORA
