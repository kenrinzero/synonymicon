import math

from corpora import get_zipf
from candidates import get_morphological_variants


class TestCorpusAggregation:
    def test_bnc_aggregates_pos_tagged_rows(self):
        # 'run' has 8 POS-tagged rows in bnc_all.al summing to 22125 occurrences.
        # The stored Zipf must reflect the aggregate, not whichever row is last
        # in the file (the pre-fix bug kept only the final row, 6327).
        z = get_zipf('run', 'bnc')
        expected = math.log10(22125 * 1e9 / 85714226)
        assert z is not None
        assert abs(z - expected) < 0.02, f"bnc 'run' zipf={z}, expected aggregate {expected}"

    def test_leipzig_aggregates_case_variants(self):
        # 'we' appears as we/We/WE in leipzig_news; counts sum to 59789. The
        # pre-fix loader kept only the first (39384) via setdefault.
        z = get_zipf('we', 'leipzig_news')
        offset = 7.73 - math.log10(1131737)  # offset preserves aggregated 'the' = 7.73
        expected = math.log10(59789) + offset
        assert abs(z - expected) < 0.02, f"leipzig_news 'we' zipf={z}, expected aggregate {expected}"

    def test_leipzig_the_anchor_calibrated(self):
        # The cross-corpus calibration anchor ('the' ~= 7.73) must hold after
        # aggregation — i.e. the offsets were recalibrated against the aggregate.
        for corpus in ('leipzig_news', 'leipzig_web_com', 'leipzig_web_uk'):
            z = get_zipf('the', corpus)
            assert abs(z - 7.73) < 0.02, f"{corpus} 'the' zipf={z} drifted from 7.73 anchor"

    def test_the_anchor_holds_across_count_corpora(self):
        # Every corpus we compute the Zipf for ourselves should put 'the' near the
        # wordfreq anchor (~7.73). google_1grams/kaggle (offset +3.0) and gutenberg
        # (offset +0.37 copied from opensubtitles) previously put 'the' at
        # 13.4/13.4/8.6, which shoved nearly every word into the 'common' band.
        for corpus in ('google_1grams', 'kaggle', 'gutenberg', 'wikipedia',
                       'opensubtitles', 'leipzig_news', 'leipzig_web_com', 'leipzig_web_uk'):
            z = get_zipf('the', corpus)
            assert abs(z - 7.73) < 0.2, f"{corpus} 'the' zipf={z} far from the 7.73 anchor"


class TestWordfreqOOV:
    def test_unknown_word_returns_none(self):
        # wordfreq returns 0.0 for unknown words; get_zipf must surface that as
        # None so OOV candidates are dropped uniformly (like the dict-backed
        # corpora) instead of polluting the 'absurd' band under the default corpus.
        assert get_zipf('xyzzyqqpllx', 'wordfreq') is None

    def test_known_word_has_positive_zipf(self):
        assert get_zipf('happy', 'wordfreq') > 0


class TestMorphologicalVariants:
    def test_e_ending_word_includes_plural_and_agent_forms(self):
        # Pre-fix, e-ending words got only the e-drop forms, so 'makes'/'maker'
        # slipped through as undeduplicated inflections of the query 'make'.
        v = get_morphological_variants('make')
        assert 'makes' in v
        assert 'maker' in v
