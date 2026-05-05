# Leipzig Corpora Analysis

Three corpora from the Leipzig Corpora Collection, all in the same file format.

## Source
- **7: News 2025** — `eng_news_2025_1M-words.txt`, 634,553 entries (579,559 unique words after dedup), 22.2M tokens, 1M sentences
- **8: Web-Public COM 2018** — `eng-com_web-public_2018_1M-words.txt`, 480,158 entries
- **9: Web-Public UK 2018** — `eng-uk_web-public_2018_1M-words.txt`, 444,718 entries

Source: https://wortschatz.uni-leipzig.de/en/download

## Format

**File:** `{prefix}-words.txt`
**Separator:** `\t` (tab)
**Columns:** `rank\tword\tcount` (3 columns)

| col | name | example |
|-----|------|---------|
| 0 | rank | `101` |
| 1 | word | `the` |
| 2 | count | `976578` |

The fourth column (zipf) in the original file uses source-internal normalization and is NOT used — Zipf is computed from `count`.

**Duplicate words:** Files contain multiple entries for the same word in different cases (e.g., "the", "THe", "THE"). Use `setdefault` to keep the first (highest-count) occurrence per normalized word.

## Zipf Normalization

Per-corpus formula derived by calibrating "the" to wordfreq's ~7.73:

| corpus | "the" count | formula | "the" zipf |
|--------|-------------|---------|-----------|
| News 2025 | 976,578 | `log10(count) + 1.74` | 7.73 |
| Web COM 2018 | 795,170 | `log10(count) + 1.83` | 7.73 |
| Web UK 2018 | 936,516 | `log10(count) + 1.76` | 7.73 |

Offsets derived from: `offset = 7.73 - log10(count)`

## Loader Notes

- Parse: `parts = line.split('\t')`, require exactly 3 parts
- Word at `parts[1]`, count at `parts[2].strip()`
- Normalize word to lowercase
- Use `setdefault` to handle duplicate word entries (keep first occurrence)
- No lemmatization needed

## API value naming

- `leipzig_news`
- `leipzig_web_com`
- `leipzig_web_uk`