import json
import threading
import requests
from bs4 import BeautifulSoup
from nltk.corpus import wordnet

with open('data/websters1913.json') as f:
    WEBSTERS = {k.lower(): v for k, v in json.load(f).items()}

WIKTIONARY_CACHE = {}
WIKTIONARY_HEADERS = {'User-Agent': 'Synonymicon/1.0 (https://synonymicon.xyz)'}
DEFINITION_CACHE = {}

# Sentinel distinguishing a transient Wiktionary network failure from a genuine
# "no entry" (None). Transient failures must not be cached, so the word is
# retried instead of being permanently saddled with a degraded fallback.
NETWORK_ERROR = object()


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
    except requests.RequestException:
        return NETWORK_ERROR  # transient — do not cache, allow a later retry
    except (ValueError, KeyError):
        WIKTIONARY_CACHE[key] = None
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
    if key in DEFINITION_CACHE:
        return DEFINITION_CACHE[key]

    wik = get_wiktionary_definition(word)
    wiktionary_errored = wik is NETWORK_ERROR
    if wik and not wiktionary_errored:
        DEFINITION_CACHE[key] = wik
        return wik

    result = get_websters_definition(word) or get_wordnet_gloss(word) or "[undefined]"
    # Only cache when Wiktionary gave a definitive answer. On a transient network
    # error, return the fallback for this request but leave the cache untouched so
    # the next lookup re-attempts Wiktionary.
    if not wiktionary_errored:
        DEFINITION_CACHE[key] = result
    return result
