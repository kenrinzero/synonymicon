import math
import openpyxl
from nltk.stem import WordNetLemmatizer
from wordfreq import zipf_frequency as wordfreq_zipf

SUBTLEX_ZIPF = {}
GOOGLE_ZIPF = {}
KAGGLE_ZIPF = {}
OPENSUBS_ZIPF = {}
GUTEN_ZIPF = {}
WIKIPEDIA_ZIPF = {}
LEIPZIG_NEWS_ZIPF = {}
LEIPZIG_WEB_COM_ZIPF = {}
LEIPZIG_WEB_UK_ZIPF = {}
BNC_ZIPF = {}
BNC_TOTAL = 85714226


def _load_leipzig_news():
    with open('data/leipzig_news_2025.txt') as f:
        for line in f:
            parts = line.split('\t')
            if len(parts) != 3:
                continue
            try:
                word = parts[1].lower()
                count = int(parts[2].strip())
                zipf_val = math.log10(count) + 1.74
                LEIPZIG_NEWS_ZIPF.setdefault(word, zipf_val)
            except ValueError:
                continue


def _load_leipzig_web_com():
    with open('data/leipzig_web_com_2018.txt') as f:
        for line in f:
            parts = line.split('\t')
            if len(parts) != 3:
                continue
            try:
                word = parts[1].lower()
                count = int(parts[2].strip())
                zipf_val = math.log10(count) + 1.83
                LEIPZIG_WEB_COM_ZIPF.setdefault(word, zipf_val)
            except ValueError:
                continue


def _load_leipzig_web_uk():
    with open('data/leipzig_web_uk_2018.txt') as f:
        for line in f:
            parts = line.split('\t')
            if len(parts) != 3:
                continue
            try:
                word = parts[1].lower()
                count = int(parts[2].strip())
                zipf_val = math.log10(count) + 1.76
                LEIPZIG_WEB_UK_ZIPF.setdefault(word, zipf_val)
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
                zipf_val = math.log10(freq * (1_000_000_000 / BNC_TOTAL))
                BNC_ZIPF[word.lower()] = zipf_val
            except ValueError:
                continue


_LEMMATIZER = WordNetLemmatizer()


def get_zipf(word, corpus='wordfreq'):
    wl = word.lower()
    if corpus == 'subtlex':
        return SUBTLEX_ZIPF.get(wl)
    if corpus == 'bnc':
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
    if corpus == 'leipzig_web_uk':
        return LEIPZIG_WEB_UK_ZIPF.get(wl)
    return wordfreq_zipf(wl, 'en')


_load_leipzig_news()
_load_leipzig_web_com()
_load_leipzig_web_uk()
_load_opensubtitles()
_load_gutenberg()
_load_kaggle()
_load_wikipedia()
_load_google()
_load_subtlex()
_load_bnc()
