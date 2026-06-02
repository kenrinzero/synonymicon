import math
import sys
import openpyxl
from nltk.stem import WordNetLemmatizer
from wordfreq import zipf_frequency as wordfreq_zipf

BNC_TOTAL = 85714226
_BNC_OFFSET = math.log10(1e9 / BNC_TOTAL)  # per-billion normalization == log10(count * 1e9 / BNC_TOTAL)

# corpus name -> dict[word, zipf]; populated once at import.
_ZIPF_TABLES = {}

# Set of corpus names that loaded successfully. Exported so the app can
# prune VALID_CORPORA if any corpus failed to load at startup.
# 'wordfreq' is always available (computed at query time via the wordfreq library).
LOADED_CORPORA = {'wordfreq'}

# Count-based corpora. Counts are AGGREGATED (summed) per lowercased word before
# the Zipf is computed, so POS-tagged duplicates (BNC: one row per POS tag) and
# capitalization variants (Leipzig: the/The/THE as separate rows) are combined
# rather than silently dropped. Each offset is calibrated so 'the' ~= 7.73, the
# wordfreq anchor, for cross-corpus tier consistency.
_COUNT_CORPORA = {
    'google_1grams':    dict(path='data/google_1grams.txt',        word_col=0, count_col=1, offset=-2.634,     sep='\t', exact_cols=2),
    'wikipedia':        dict(path='data/wikipedia_freq.txt',       word_col=0, count_col=1, offset=-0.5,                 exact_cols=2),
    'kaggle':           dict(path='data/kaggle_freq.csv',          word_col=0, count_col=1, offset=-2.634,     sep=',',  exact_cols=2, skip_header=True),
    'opensubtitles':    dict(path='data/hermitdave_freq.txt',      word_col=0, count_col=1, offset=0.37,                 exact_cols=2),
    'gutenberg':        dict(path='data/scriptsmith_freq.txt',     word_col=1, count_col=0, offset=-0.5,                 exact_cols=2),
    'leipzig_news':     dict(path='data/leipzig_news_2025.txt',    word_col=1, count_col=2, offset=1.6763,     sep='\t', exact_cols=3),
    'leipzig_web_com':  dict(path='data/leipzig_web_com_2018.txt', word_col=1, count_col=2, offset=1.7779,     sep='\t', exact_cols=3),
    'leipzig_web_uk':   dict(path='data/leipzig_web_uk_2018.txt',  word_col=1, count_col=2, offset=1.6987,     sep='\t', exact_cols=3),
    'bnc':              dict(path='data/bnc_all.al',               word_col=1, count_col=0, offset=_BNC_OFFSET,           min_cols=4),
}


def _load_counts(path, word_col, count_col, sep=None, skip_header=False, exact_cols=None, min_cols=None):
    counts = {}
    with open(path) as f:
        if skip_header:
            next(f, None)
        for line in f:
            parts = line.split(sep) if sep is not None else line.split()
            if exact_cols is not None and len(parts) != exact_cols:
                continue
            if min_cols is not None and len(parts) < min_cols:
                continue
            if len(parts) <= max(word_col, count_col):
                continue
            try:
                count = int(parts[count_col].strip())
            except ValueError:
                continue
            word = parts[word_col].strip().lower()
            if not word:
                continue
            counts[word] = counts.get(word, 0) + count
    return counts


def _zipf_from_counts(counts, offset):
    return {w: math.log10(c) + offset for w, c in counts.items() if c > 0}


def _load_subtlex():
    # SUBTLEX-US ships pre-computed Zipf values (column index 14); no aggregation.
    table = {}
    wb = openpyxl.load_workbook('data/subtlex_us.xlsx', read_only=True, data_only=True)
    ws = wb.active
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i == 0:
            continue  # skip header
        word = row[0]
        if not word or not isinstance(word, str):
            continue
        zipf_val = row[14]
        if zipf_val is not None:
            table[word.lower()] = float(zipf_val)
    wb.close()
    return table


def _load_all():
    for name, spec in _COUNT_CORPORA.items():
        try:
            offset = spec['offset']
            parse_args = {k: v for k, v in spec.items() if k != 'offset'}
            _ZIPF_TABLES[name] = _zipf_from_counts(_load_counts(**parse_args), offset)
            LOADED_CORPORA.add(name)
        except Exception as e:
            print(f'WARNING: corpus "{name}" failed to load ({e}), skipping', file=sys.stderr)
    try:
        _ZIPF_TABLES['subtlex'] = _load_subtlex()
        LOADED_CORPORA.add('subtlex')
    except Exception as e:
        print(f'WARNING: corpus "subtlex" failed to load ({e}), skipping', file=sys.stderr)


_LEMMATIZER = WordNetLemmatizer()


def get_zipf(word, corpus='wordfreq'):
    wl = word.lower()
    if corpus == 'wordfreq':
        z = wordfreq_zipf(wl, 'en')
        # wordfreq returns 0.0 for unknown words; treat that as None so OOV words
        # are dropped uniformly, matching the dict-backed corpora.
        return z if z > 0 else None
    if corpus == 'bnc':
        # BNC surface forms are lemmatized; try noun lemma first, then verb.
        table = _ZIPF_TABLES['bnc']
        z = table.get(_LEMMATIZER.lemmatize(wl))
        if z is None:
            z = table.get(_LEMMATIZER.lemmatize(wl, 'v'))
        return z
    table = _ZIPF_TABLES.get(corpus)
    if table is None:
        return None
    return table.get(wl)


_load_all()
