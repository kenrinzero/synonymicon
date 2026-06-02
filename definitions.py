import json
import threading
import requests
from collections import OrderedDict
from bs4 import BeautifulSoup
from nltk.corpus import wordnet

with open('data/websters1913.json') as f:
    WEBSTERS = {k.lower(): v for k, v in json.load(f).items()}

WIKTIONARY_HEADERS = {'User-Agent': 'Synonymicon/1.0 (https://synonymicon.xyz)'}

_CACHE_MAX = 50000

# Sentinel distinguishing a transient Wiktionary network failure from a genuine
# "no entry" (None). Transient failures must not be cached, so the word is
# retried instead of being permanently saddled with a degraded fallback.
NETWORK_ERROR = object()


class _LRUDict:
    """A simple LRU dict backed by OrderedDict with a max size."""

    _MISS = object()

    def __init__(self, maxsize):
        self._maxsize = maxsize
        self._data = OrderedDict()

    def get(self, key, default=None):
        if key in self._data:
            self._data.move_to_end(key)
            val = self._data[key]
            return default if val is self._MISS else val
        return default

    def contains(self, key):
        return key in self._data

    def set(self, key, value):
        if key in self._data:
            self._data.move_to_end(key)
            self._data[key] = value
        else:
            if len(self._data) >= self._maxsize:
                self._data.popitem(last=False)
            self._data[key] = value

    def clear(self):
        self._data.clear()

    def __contains__(self, key):
        return key in self._data

    def cache_info(self):
        return f'currsize={len(self._data)}, maxsize={self._maxsize}'


WIKTIONARY_CACHE = _LRUDict(_CACHE_MAX)
DEFINITION_CACHE = _LRUDict(_CACHE_MAX)


def get_wiktionary_definition(word):
    key = word.lower()
    if WIKTIONARY_CACHE.contains(key):
        return WIKTIONARY_CACHE.get(key)
    try:
        url = f'https://en.wiktionary.org/api/rest_v1/page/definition/{key}'
        r = requests.get(url, headers=WIKTIONARY_HEADERS, timeout=2.0)
        if r.status_code != 200:
            WIKTIONARY_CACHE.set(key, None)
            return None
        data = r.json()
        en_entries = data.get('en')
        if not en_entries:
            WIKTIONARY_CACHE.set(key, None)
            return None
        definitions = en_entries[0].get('definitions', [])
        if not definitions:
            WIKTIONARY_CACHE.set(key, None)
            return None
        html = definitions[0].get('definition', '')
        text = BeautifulSoup(html, 'html.parser').get_text().strip()
        result = text if text else None
        WIKTIONARY_CACHE.set(key, result)
        return result
    except requests.RequestException:
        return NETWORK_ERROR  # transient — do not cache, allow a later retry
    except (ValueError, KeyError):
        WIKTIONARY_CACHE.set(key, None)
        return None


def get_websters_definition(word):
    return WEBSTERS.get(word.lower())


# NLTK's WordNet reader seeks a shared file handle, so concurrent .synsets()/
# .definition() calls (get_definition runs under a ThreadPoolExecutor) interleave
# seeks and read garbage, raising WordNetError. Serialize gloss access.
_WORDNET_LOCK = threading.Lock()


def get_wordnet_gloss(word):
    with _WORDNET_LOCK:
        synsets = wordnet.synsets(word)
        if synsets:
            defn = synsets[0].definition()
            if defn:
                return defn
    return None


def get_definition(word):
    key = word.lower()
    if DEFINITION_CACHE.contains(key):
        return DEFINITION_CACHE.get(key)

    wik = get_wiktionary_definition(word)
    wiktionary_errored = wik is NETWORK_ERROR
    if wik and not wiktionary_errored:
        DEFINITION_CACHE.set(key, wik)
        return wik

    result = get_websters_definition(word) or get_wordnet_gloss(word) or "[undefined]"
    if not wiktionary_errored:
        DEFINITION_CACHE.set(key, result)
    return result
