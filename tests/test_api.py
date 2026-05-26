import pytest


def get_results(response):
    return response.get_json()['results']


class TestValidation:
    def test_missing_word(self, client):
        r = client.get('/synonyms?tier=all')
        assert r.status_code == 400
        assert 'word' in r.get_json()['error']

    def test_empty_word(self, client):
        r = client.get('/synonyms?word=&tier=all')
        assert r.status_code == 400

    def test_three_word_phrase(self, client):
        r = client.get('/synonyms?word=one+two+three&tier=all')
        assert r.status_code == 400
        assert '2 words' in r.get_json()['error']

    def test_missing_tier_and_minmax(self, client):
        r = client.get('/synonyms?word=happy')
        assert r.status_code == 400
        assert 'tier' in r.get_json()['error']

    def test_unknown_tier(self, client):
        r = client.get('/synonyms?word=happy&tier=bogus')
        assert r.status_code == 400
        data = r.get_json()
        assert 'unknown tier' in data['error']
        assert 'available_tiers' in data

    def test_unknown_corpus(self, client):
        r = client.get('/synonyms?word=happy&tier=all&corpus=bogus')
        assert r.status_code == 400
        data = r.get_json()
        assert 'unknown corpus' in data['error']
        assert 'available_corpora' in data

    def test_unknown_rank(self, client):
        r = client.get('/synonyms?word=happy&tier=all&rank=bogus')
        assert r.status_code == 400
        data = r.get_json()
        assert 'unknown rank' in data['error']
        assert 'available_ranks' in data

    def test_unknown_pos(self, client):
        r = client.get('/synonyms?word=happy&tier=all&pos=bogus')
        assert r.status_code == 400
        data = r.get_json()
        assert 'unknown pos' in data['error']
        assert 'available_pos' in data

    def test_min_without_max(self, client):
        r = client.get('/synonyms?word=happy&min=2.0')
        assert r.status_code == 400
        assert 'both' in r.get_json()['error']

    def test_max_without_min(self, client):
        r = client.get('/synonyms?word=happy&max=5.0')
        assert r.status_code == 400

    def test_non_numeric_minmax(self, client):
        r = client.get('/synonyms?word=happy&min=abc&max=def')
        assert r.status_code == 400
        assert 'numeric' in r.get_json()['error']


class TestResults:
    def test_response_shape(self, client):
        r = client.get('/synonyms?word=happy&tier=all')
        assert r.status_code == 200
        data = r.get_json()
        assert 'results' in data
        assert 'senses' in data
        assert isinstance(data['results'], list)
        assert isinstance(data['senses'], list)

    def test_result_entry_shape(self, client):
        r = client.get('/synonyms?word=happy&tier=all')
        results = get_results(r)
        if results:
            entry = results[0]
            assert 'word' in entry
            assert 'zipf' in entry
            assert 'definition' in entry
            assert 'band' in entry

    def test_returned_words_are_unique(self, client):
        r = client.get('/synonyms?word=run&tier=all')
        results = get_results(r)
        words = [e['word'].lower() for e in results]
        assert len(words) == len(set(words))

    def test_zipf_within_tier_bounds(self, client):
        r = client.get('/synonyms?word=happy&tier=uncommon')
        for entry in get_results(r):
            assert 3.0 <= entry['zipf'] < 4.0, f"{entry['word']} zipf={entry['zipf']} outside uncommon range"

    def test_zipf_within_minmax_bounds(self, client):
        r = client.get('/synonyms?word=run&tier=all&min=2.0&max=4.0')
        for entry in get_results(r):
            assert 2.0 <= entry['zipf'] < 4.0, f"{entry['word']} zipf={entry['zipf']} outside 2.0-4.0"

    def test_band_label_matches_zipf(self, client):
        r = client.get('/synonyms?word=run&tier=all')
        for entry in get_results(r):
            z = entry['zipf']
            expected = (
                'common' if z >= 4.0
                else 'uncommon' if z >= 3.0
                else 'rare' if z >= 2.0
                else 'exotic' if z >= 1.0
                else 'absurd'
            )
            assert entry['band'] == expected, f"{entry['word']} zipf={z} band={entry['band']} expected={expected}"

    def test_query_word_excluded_from_results(self, client):
        r = client.get('/synonyms?word=happy&tier=all')
        words = [e['word'].lower() for e in get_results(r)]
        assert 'happy' not in words

    def test_two_word_phrase(self, client):
        r = client.get('/synonyms?word=hard+work&tier=all')
        assert r.status_code == 200

    def test_comma_separated_tiers(self, client):
        r = client.get('/synonyms?word=run&tier=uncommon,rare')
        assert r.status_code == 200
        for entry in get_results(r):
            assert 2.0 <= entry['zipf'] < 4.0

    def test_definition_truncation(self, client):
        r = client.get('/synonyms?word=run&tier=all')
        for entry in get_results(r):
            assert len(entry['definition']) <= 201


class TestRanking:
    def test_common_rank_zipf_descending(self, client):
        r = client.get('/synonyms?word=run&tier=all&rank=common')
        results = get_results(r)
        if len(results) >= 2:
            zipfs = [e['zipf'] for e in results]
            assert zipfs == sorted(zipfs, reverse=True)

    def test_rare_rank_zipf_ascending(self, client):
        r = client.get('/synonyms?word=run&tier=all&rank=rare')
        results = get_results(r)
        if len(results) >= 2:
            zipfs = [e['zipf'] for e in results]
            assert zipfs == sorted(zipfs)

    def test_default_rank_is_common(self, client):
        r_default = client.get('/synonyms?word=happy&tier=all')
        r_common = client.get('/synonyms?word=happy&tier=all&rank=common')
        assert r_default.get_json() == r_common.get_json()


class TestSenses:
    def test_polysemous_word_has_senses(self, client):
        r = client.get('/synonyms?word=run&tier=all')
        senses = r.get_json()['senses']
        assert len(senses) >= 2

    def test_sense_shape(self, client):
        r = client.get('/synonyms?word=run&tier=all')
        senses = r.get_json()['senses']
        if senses:
            s = senses[0]
            assert 'id' in s
            assert 'gloss' in s
            assert 'pos' in s

    def test_senses_capped(self, client):
        r = client.get('/synonyms?word=run&tier=all')
        senses = r.get_json()['senses']
        assert len(senses) <= 8

    def test_pos_filter_limits_senses(self, client):
        r_all = client.get('/synonyms?word=run&tier=all')
        r_noun = client.get('/synonyms?word=run&tier=all&pos=noun')
        all_senses = r_all.get_json()['senses']
        noun_senses = r_noun.get_json()['senses']
        assert len(noun_senses) <= len(all_senses)
        for s in noun_senses:
            assert s['pos'] == 'noun'

    def test_phrase_has_no_senses(self, client):
        r = client.get('/synonyms?word=hard+work&tier=all')
        senses = r.get_json()['senses']
        assert senses == []


class TestCorpora:
    def test_all_valid_corpora_accepted(self, client):
        corpora = ['wordfreq', 'subtlex', 'bnc', 'google_1grams', 'wikipedia',
                    'kaggle', 'opensubtitles', 'gutenberg', 'leipzig_news',
                    'leipzig_web_com', 'leipzig_web_uk']
        for c in corpora:
            r = client.get(f'/synonyms?word=happy&tier=all&corpus={c}')
            assert r.status_code == 200, f"corpus={c} returned {r.status_code}"


class TestPOS:
    def test_all_valid_pos_accepted(self, client):
        for pos in ['all', 'noun', 'verb', 'adj', 'adv']:
            r = client.get(f'/synonyms?word=run&tier=all&pos={pos}')
            assert r.status_code == 200, f"pos={pos} returned {r.status_code}"

    def test_comma_separated_pos(self, client):
        r = client.get('/synonyms?word=run&tier=all&pos=noun,verb')
        assert r.status_code == 200

    def test_pos_filter_changes_results(self, client):
        r_noun = client.get('/synonyms?word=run&tier=all&pos=noun')
        r_verb = client.get('/synonyms?word=run&tier=all&pos=verb')
        nouns = {e['word'] for e in get_results(r_noun)}
        verbs = {e['word'] for e in get_results(r_verb)}
        assert nouns != verbs or (len(nouns) == 0 and len(verbs) == 0)
