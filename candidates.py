import re
from gensim.downloader import load as fasttext_load
from nltk.corpus import wordnet
from config import (
    FASTTEXT_ENABLED, WORDNET_SCORE, FASTTEXT_COSINE_CUTOFF,
    TIERS, COMMON_FLOOR,
)
from corpora import get_zipf

if FASTTEXT_ENABLED:
    FASTTEXT_MODEL = fasttext_load('fasttext-wiki-news-subwords-300')
else:
    FASTTEXT_MODEL = None


WN_POS_LABELS = {'n': 'noun', 'v': 'verb', 'a': 'adj', 's': 'adj', 'r': 'adv'}
MAX_SENSES = 8


def get_senses(word, pos_filter=None):
    synsets = wordnet.synsets(word)
    senses = []
    for s in synsets:
        if pos_filter and s.pos() not in pos_filter:
            continue
        senses.append({
            'id': s.name(),
            'gloss': s.definition(),
            'pos': WN_POS_LABELS.get(s.pos(), s.pos()),
        })
        if len(senses) >= MAX_SENSES:
            break
    return senses


def get_wordnet_candidates(words, pos_filter=None):
    if isinstance(words, str):
        words = [words]

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
                if name.lower() != ' '.join(words).lower():
                    candidates.add(name)

    if len(words) == 2:
        w1, w2 = words[0].lower(), words[1].lower()
        filtered = set()
        for c in candidates:
            cl = c.lower()
            if w1 in cl.split() or w2 in cl.split() or cl == f"{w1} {w2}" or cl == f"{w2} {w1}":
                filtered.add(c)
        candidates = filtered

    return candidates


def get_fasttext_candidates(word, n=100):
    if not FASTTEXT_ENABLED:
        return []
    wl = word.lower()
    try:
        return [(w, score) for w, score in FASTTEXT_MODEL.most_similar(word, topn=n) if w.lower() != wl]
    except KeyError:
        return []


def get_morphological_variants(word):
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
    if len(w) >= 3 and w[-1] not in 'aeiou' and w[-2] in 'aeiou' and w[-3] not in 'aeiou':
        variants.add(w + w[-1] + 'ed')
        variants.add(w + w[-1] + 'ing')
        variants.add(w + w[-1] + 'er')
    return variants


def get_band_label(zipf):
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


def _score_and_filter(word, scored, corpus, rank):
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
        results.append((display, z, score))

    if rank == 'relevance':
        results.sort(key=lambda x: (-x[2], -x[1]))
    elif rank == 'rare':
        results.sort(key=lambda x: (x[1], -x[2]))
    else:
        results.sort(key=lambda x: (-x[1], -x[2]))
    return results


def _build_scored(wn_candidates, ft_candidates, pos_filter):
    scored = {}
    for c in wn_candidates:
        key = c.lower()
        scored[key] = (c, WORDNET_SCORE)
    for w, cosine in ft_candidates:
        key = w.lower()
        if key not in scored and cosine >= FASTTEXT_COSINE_CUTOFF and not pos_filter:
            scored[key] = (w.replace('_', ' '), cosine)
    return scored


def get_blended_results(word, tier=None, zmin=None, zmax=None, pos_filter=None, phrase_words=None, corpus='wordfreq', rank='common'):
    wn_words = phrase_words if phrase_words else [word]
    wn_candidates = get_wordnet_candidates(wn_words, pos_filter)
    ft_candidates = get_fasttext_candidates(word)
    scored = _build_scored(wn_candidates, ft_candidates, pos_filter)

    if zmin is not None and zmax is not None:
        lo, hi = zmin, zmax
    elif tier is not None:
        lo, hi = TIERS[tier]
    else:
        raise ValueError("Either tier or both zmin/zmax must be provided")

    all_results = _score_and_filter(word, scored, corpus, rank)
    return [(w, z) for w, z, _ in all_results if lo <= z < hi]


def get_blended_results_multi(word, ranges, pos_filter=None, phrase_words=None, corpus='wordfreq', rank='common'):
    wn_words = phrase_words if phrase_words else [word]
    wn_candidates = get_wordnet_candidates(wn_words, pos_filter)
    ft_candidates = get_fasttext_candidates(word)
    scored = _build_scored(wn_candidates, ft_candidates, pos_filter)

    all_results = _score_and_filter(word, scored, corpus, rank)
    return [(w, z) for w, z, _ in all_results if any(lo <= z < hi for lo, hi in ranges)]
