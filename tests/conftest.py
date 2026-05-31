import os
os.environ['SYNONYMICON_FASTTEXT'] = '0'

import pytest
from app import app as flask_app
import definitions


class _FakeWiktionaryResponse:
    """A 404 stand-in so get_wiktionary_definition takes its 'no entry' path."""
    status_code = 404

    def json(self):
        return {}


@pytest.fixture(autouse=True)
def offline_wiktionary(monkeypatch):
    """Keep the suite hermetic and deterministic.

    Without this, get_definition makes live HTTP calls to en.wiktionary.org for
    every result word — slow, flaky offline, and impolite to the public API.
    Stubbing requests.get with a 404 forces the offline
    Webster's -> WordNet -> [undefined] fallback chain. Caches are cleared per
    test so cross-test cache state cannot leak.
    """
    definitions.WIKTIONARY_CACHE.clear()
    definitions.DEFINITION_CACHE.clear()
    monkeypatch.setattr(definitions.requests, 'get', lambda *a, **k: _FakeWiktionaryResponse())
    yield


@pytest.fixture
def client():
    flask_app.config['TESTING'] = True
    with flask_app.test_client() as c:
        yield c
