import requests

import definitions


class TestDefinitionCachePoisoning:
    def test_network_error_is_not_cached(self, monkeypatch):
        definitions.DEFINITION_CACHE.clear()
        definitions.WIKTIONARY_CACHE.clear()

        def boom(*args, **kwargs):
            raise requests.exceptions.ConnectionError("simulated offline")

        monkeypatch.setattr(definitions.requests, 'get', boom)

        # A transient Wiktionary failure must fall back for this request WITHOUT
        # poisoning the cache, so the word is retried once the network recovers.
        word = 'zzz_transient_test_word'
        definitions.get_definition(word)
        assert word not in definitions.DEFINITION_CACHE

        class _Resp:
            status_code = 200

            def json(self):
                return {'en': [{'definitions': [{'definition': '<b>recovered</b> value'}]}]}

        monkeypatch.setattr(definitions.requests, 'get', lambda *a, **k: _Resp())
        assert definitions.get_definition(word) == 'recovered value'
