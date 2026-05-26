import json
import requests
from bs4 import BeautifulSoup
from nltk.corpus import wordnet

with open('data/websters1913.json') as f:
    WEBSTERS = {k.lower(): v for k, v in json.load(f).items()}

WIKTIONARY_CACHE = {}
WIKTIONARY_HEADERS = {'User-Agent': 'Synonymicon/1.0 (https://synonymicon.xyz)'}
DEFINITION_CACHE = {}


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
        return None
    except (ValueError, KeyError):
        return None


def get_websters_definition(word):
    return WEBSTERS.get(word.lower())


def get_wordnet_gloss(word):
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
    d = get_wiktionary_definition(word)
    if d:
        DEFINITION_CACHE[key] = d
        return d
    d = get_websters_definition(word)
    if d:
        DEFINITION_CACHE[key] = d
        return d
    d = get_wordnet_gloss(word)
    if d:
        DEFINITION_CACHE[key] = d
        return d
    DEFINITION_CACHE[key] = "[undefined]"
    return "[undefined]"
