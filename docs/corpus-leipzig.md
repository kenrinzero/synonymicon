# Leipzig Corpora Analysis

Three corpora from the Leipzig Corpora Collection, all in the same file format.

## Source
- **7: News 2025** — `eng_news_2025_1M-words.txt`, 634,553 word types, 22.2M tokens, 1M sentences
- **8: Web-Public COM 2018** — `eng-com_web-public_2018_1M-words.txt`, 480,158 word types
- **9: Web-Public UK 2018** — `eng-uk_web-public_2018_1M-words.txt`, 444,718 word types

Source: https://wortschatz.uni-leipzig.de/en/download

## Format

**File:** `{prefix}-words.txt`  
**Separator:** `\t` (tab)  
**Columns:** `rank\tcount\tword\tzipf`

| col | name | example |
|-----|------|---------|
| 0 | rank | `101` |
| 1 | count | `976578` |
| 2 | word | `the` |
| 3 | zipf | `21.87` ← pre-computed, not token-normalized, ignore |

The pre-computed Zipf in column 3 uses a source-internal normalization (source-specific, not token-count-normalized like wordfreq). Do not use it — compute Zipf from `count` using the formula below.

## Zipf Normalization

Per-corpus formula derived by calibrating "the" to wordfreq's ~7.73:

| corpus | "the" count | formula | "the" zipf |
|--------|-------------|---------|-----------|
| News 2025 | 976,578 | `log10(count) + 1.74` | 7.73 |
| Web COM 2018 | 795,170 | `log10(count) + 1.83` | 7.73 |
| Web UK 2018 | 936,516 | `log10(count) + 1.76` | 7.73 |

Offsets derived from: `offset = 7.73 - log10(count)`

## Loader Notes

- Parse: `parts = line.split('\t')`, require exactly 4 parts, skip header/metadata lines
- Count at `parts[1]`, word at `parts[2]`
- Word is already lowercase in all three files
- No lemmatization needed
- Per-corpus offset stored in a dict, passed at load time

## File Naming (proposed)

After copying to `data/`:
- `leipzig_news_2025.txt`
- `leipzig_web_com_2018.txt`
- `leipzig_web_uk_2018.txt`

## API value naming (proposed)

- `leipzig_news`
- `leipzig_web_com`
- `leipzig_web_uk`