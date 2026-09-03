Icegrams 2026 update
=====================

Icegrams gives you frequency counts for single words, word pairs, and word triples (trigrams) in Icelandic, plus the ability to ask "what word tends to follow these two words?". It's built by counting how often word sequences occur across a large corpus of Icelandic text, then compressing those counts into a small binary file that ships with the library.

Vocabulary changes over time as new words enter the language and others fall out of use. We've updated Icegrams with text through July 2026 so it better reflects modern Icelandic.

This document describes how the 2026 Icegrams model was built, how it differs from the 2019 model, and how to reproduce the pipeline.


Contents
--------

1. [Summary of changes](#summary-of-changes)
2. [Source text](#source-text)
3. [Step 1: Corpus selection](#step-1-corpus-selection)
4. [Step 2: Converting the raw files](#step-2-converting-the-raw-files)
5. [Step 3: Correcting spelling and grammar](#step-3-correcting-spelling-and-grammar)
6. [Step 4: Counting trigrams](#step-4-counting-trigrams)
7. [Step 5: Choosing a frequency cutoff and building the model file](#step-5-choosing-a-frequency-cutoff-and-building-the-model-file)
8. [2026 model statistics](#2026-model-statistics)
9. [Reproducing this pipeline](#reproducing-this-pipeline)
10. [Licensing and open-source notes](#licensing-and-open-source-notes)

Summary of changes
------------------------

| | 2019 model | 2026 model |
|---|---|---|
| Amount of text | ~100 million words | ~1 billion words |
| How recent | Text up to ~2017 | Text up to July 2026 |
| Text selection | A few IGC news sources excluded, Morgunblaðið/mbl.is deduplicated for years where both are present | Same IGC sources excluded, as well as the entire IGC-Social. Deduplication of some news media for years where both printed and online versions are present. Each subcorpus can be at most 10% of the total selection. |
| Recency bias | No, but texts before 1980 are excluded | Yes. Texts before 1980 excluded, and gentle recency bias was added to the remaining IGC corpus. |
| Spelling/grammar fixing | A fixed list of ~2,850 known misspellings, applied by hand-run SQL | Miðeind's neural corrector, Málfríður, applied to every sentence |
| Trigram counting | A PostgreSQL database, updated one occurrence at a time | Plain in-memory counting per chunk of text, merged together afterwards -- no database |


Source text
-----------

The 2026 model is built from the following sources:

- **The Icelandic Gigaword Corpus (IGC)**, a large, ongoing collection of Icelandic text maintained by the Árni Magnússon Institute, covering news, books, laws, parliamentary speeches, Wikipedia, journals, and social media. We use the [2022 edition](https://repository.clarin.is/repository/xmlui/handle/20.500.12537/253) plus the [2024 update](https://repository.clarin.is/repository/xmlui/handle/20.500.12537/359) that covers texts from 2022-2023.
- **A separate corpus of recent news**: news articles from 2024 through 2026, collected and parsed by Miðeind (not published).

Combined, the full pool of text available to select from is about 1.9 billion words.
We sample a subset from that pool (~1 billion words for this model), as described next.

Step 1: Corpus selection
------------------------------------

Script: `pipeline/select_pilot_corpus.py` (for IGC) and
`pipeline/select_recent_news_slice.py` (for recent news).

The selection criteria are implemented in code so they can be re-run, adjusted, and audited:

**1. Exclude unwanted subcorpora**
- Nothing older than 1980.
- A fixed list of news sites known to be lower-quality (same as 2019).
- Social media text (IGC-Social) is left out entirely.
- Where the same content might exist twice, i.e. a newspaper's website and its print edition, we keep only one (the larger one) to avoid double-counting the same sentences. These sources are: Morgunblaðið, Stundin, Bændablaðið, Fréttatíminn and Kjarninn.

**2. Gently prefer more recent text.** Text is sampled with a weight that decays the older it is, halving every 8 years. So an article from 8 years ago is about half as likely to be picked as one from this year, one from 16 years ago about a quarter as likely, and so on. Older text is still included, just somewhat less densely than newer text. The sampling method used is [Efraimidis-Spirakis weighted random sampling without replacement (WRS)](https://www.sciencedirect.com/science/article/pii/S002001900500298X). (Wikipedia articles are undated and get a flat medium weight instead, since there's no year to compare.)

**3. Cap how much any single subcorpus can contribute.** Without this limit, a handful of very large news sites would dominate the sample. We cap any single source at 10% of the total word budget. (Testing this on a smaller sample confirmed the effect is real: without the cap, 3 sites made up 64% of the sample; with it, the same 3 sites dropped to 21%, and the number of distinct sites represented rose noticeably.)

**Recent news is handled differently.** The recent news texts (from 2024-2026) are sampled uniformly at random, with no recency weighting at all. At this model's scale, essentially the entire recent-news pool (~100 million of the ~100 million words available) ends up included.

**Final split for the 2026 model:**

| Source | Words used |
|---|---|
| News (web) | ~349M |
| News (other/print) | ~269M |
| Parliamentary speeches | ~90M |
| Administrative/official documents | ~80M |
| Laws | ~60M |
| Journals | ~21M |
| Wikipedia | ~8.5M |
| Books | ~13M |
| Recent news (2024-2026) | ~100M |
| **Total** | **~990M** |

Step 2: Converting the raw files
-----------------------------------

Scripts: `pipeline/convert_selected_igc.py`, `pipeline/convert_recent_news.py`, using `pipeline/igc_converter_scripts/` (see [Licensing](#licensing-and-open-source-notes) for where this converter comes from).

The IGC's raw files are in a structured XML format (TEI-XML), one file per document, with sentence and paragraph boundaries marked as positions within the document's text. This step converts each document into a simpler format: one JSON object per document, with the full text plus the list of sentences already split out. Recent-news articles go through a similar but separate conversion.

Step 3: Correcting spelling and grammar
-------------------------------------------

Script: `pipeline/malfridur_api_correct.py`.

The 2019 model corrected a fixed list of about 2,850 known misspellings and 369 "amalgam" errors (two words wrongly joined or split), applied by hand-written SQL.

The 2026 pipeline instead runs every sentence through Málfríður, Miðeind's own neural spelling and grammar correction model, which can catch a wider range of errors -- typos, missing accents, wrong word forms, and more.

A few practical points about how this step works:
- Very short sentences (3 words or fewer) are corrected together with a neighboring sentence for context, since a model like this performs worse on short, standalone text with nothing to disambiguate it against.
- For the shipped model, the corrections were run in batch on separate infrastructure (with the short-sentence pairing applied at export time) and fed back into the shared correction cache. `malfridur_api_correct.py` reproduces this via the API, sentence by sentence, but does not itself pair short sentences with a neighbor.

Step 4: Counting trigrams
-----------------------------

Scripts: `pipeline/extract_trigrams.py`, `pipeline/merge_trigram_counts.py`.

Once the text is corrected, it's tokenized (numbers, dates, URLs, and similar are replaced with placeholder tokens, same as 2019) and split into overlapping windows of three consecutive words (trigrams), which are counted.

2019 counted trigrams using a database (PostgreSQL). The 2026 pipeline instead counts each chunk of text in memory, writes out partial counts, and merges all the partial counts together afterwards using an external sort/merge.

Step 5: Choosing a frequency cutoff and building the model file
---------------------------------------------------------------------

Script: `pipeline/bucket_view.py`, then `icegrams.ngrams.NgramStorage.compress()`
(the existing, unchanged compressor from the original Icegrams library).

Not every trigram that was ever counted is worth keeping &mdash; many of the lowest-frequency ones are typos, one-off phrases, or noise, and including them all would make the model file much larger for very little benefit.
2019 decided on a minimum-frequency cutoff of 3 (a trigram had to occur at least 3 times to be kept). The 2026 pipeline reimplements that same kind of analysis in code, so the tradeoff between file size and coverage can be inspected and re-decided any time, for any corpus. Running it on the 2026 corpus (~1 billion words, Málfríður-corrected) gives this bucket view of trigram frequencies:

```
 lowbound |      cnt      |  perc |   cum_cnt   | cum_perc | cum_occ_perc
----------+---------------+-------+-------------+----------+--------------
     5000 |        10,873 |  0.00 |      10,873 |     0.00 |        20.60
     2000 |        22,082 |  0.01 |      32,955 |     0.01 |        26.11
     1000 |        40,565 |  0.02 |      73,520 |     0.03 |        30.71
      500 |        87,171 |  0.03 |     160,691 |     0.06 |        35.65
      200 |       276,761 |  0.10 |     437,452 |     0.16 |        42.57
      100 |       473,277 |  0.18 |     910,729 |     0.34 |        47.95
       50 |       959,011 |  0.36 |   1,869,740 |     0.69 |        53.37
       20 |     2,958,831 |  1.10 |   4,828,571 |     1.79 |        60.66
       10 |     5,245,988 |  1.94 |  10,074,559 |     3.73 |        66.40
        5 |    12,012,662 |  4.45 |  22,087,221 |     8.18 |        72.71
        4 |     7,070,624 |  2.62 |  29,157,845 |    10.79 |        75.04
        3 |    13,101,717 |  4.85 |  42,259,562 |    15.64 |        78.27
        2 |    36,261,415 | 13.42 |  78,520,977 |    29.07 |        84.24
        1 |   191,621,090 | 70.93 | 270,142,067 |   100.00 |       100.00
```

Each row's `cnt` is the number of distinct trigrams occurring exactly `lowbound` times (or, for the top three rows, at least that many); `perc` is that count as a share of all 270,142,067 distinct trigrams; `cum_cnt`/`cum_perc` accumulate from the bottom up; and `cum_occ_perc` is the share of all 1,215,650,187 total trigram *occurrences* (not distinct trigrams) covered once you keep everything down to that row. The gap between `perc` and `cum_occ_perc` at the bottom two rows tells the story: trigrams occurring exactly once are 70.93% of all distinct trigrams but only contribute the remaining 15.76% of occurrences left uncovered by row 2 (100% &minus; 84.24%); trigrams occurring exactly twice add another 13.42% of distinct trigrams for only 5.97% more occurrence coverage (84.24% &minus; 78.27%). Keeping this in mind, and following 2019's same reasoning, we settled on a cutoff of freq&gt;=2 for the 2026 model &mdash; this keeps 78,520,977 distinct trigrams (29.07% of the original 270,142,067) while still covering 84.24% of all trigram occurrences. We also tested a stricter freq&gt;=3 cutoff at this corpus size, but it produced a smaller vocabulary than freq&gt;=2 does even at half the corpus size (500 million words), for no real gain in file size &mdash; freq&gt;=2 is the better tradeoff here.

2026 model statistics
-------------------------

The shipped 2026 model is the ~1-billion-word corpus, Málfríður-corrected, at a freq>=2 cutoff (213 MB). The table below shows the other combinations tested along the way, for comparison:

| | 500M, static correction | 500M, Málfríður correction | 1B, static correction | 1B, Málfríður correction (shipped) |
|---|---|---|---|---|
| Distinct trigrams kept (freq >= 2) | 43,118,222 | 43,213,092 | 77,197,255 | 78,520,977 |
| Vocabulary | 1,104,976 | 1,134,837 | 1,679,342 | 1,721,560 |
| Compressed file size | 119.7 MB | 121.3 MB | 213.4 MB | 213.2 MB |

At both corpus sizes, Málfríður correction keeps slightly more distinct trigrams and vocabulary than the static word-list correction, at essentially the same file size. The two methods otherwise produce very similar models &mdash; the corrections affect rarer words, which doesn't show up clearly in the reported numbers.

We also tested a stricter freq>=3 cutoff on the 1B, Málfríður-corrected corpus (119 MB, 42,259,562 trigrams, 1,020,243 vocabulary) &mdash; a smaller vocabulary than even the 500M/freq>=2 model, for no meaningful file-size saving.

Reproducing this pipeline
-----------------------------

All scripts live under `pipeline/` in this repository. A full run looks like:

```
# 1. Choose which text to include
python3 pipeline/select_pilot_corpus.py --target-words 900_000_000
python3 pipeline/select_recent_news_slice.py <recent-news-glob> --target-words 100_000_000

# 2. Convert raw files to a common per-sentence format
python3 pipeline/convert_selected_igc.py ...
python3 pipeline/convert_recent_news.py ...

# 3. Correct spelling and grammar (resumable, cached)
python3 pipeline/malfridur_api_correct.py ...

# 4. Count trigrams and merge partial counts
python3 pipeline/extract_trigrams.py ...
python3 pipeline/merge_trigram_counts.py ...

# 5. Inspect frequency buckets and export the cutoff>=2 model
python3 pipeline/bucket_view.py ...
```

Each script accepts `--help` for its full list of options (word budgets, recency half-life, per-site cap, cutoff values, and so on). Every stage that processes many files writes a marker file per completed piece of work, so an interrupted run can simply be started again rather than restarted from scratch.

Licensing and open-source notes
------------------------------------

- `pipeline/igc_converter_scripts/` and the subcorpus categorization file used for processing the IGC corpus are a published resource available from CLARIN ("Icelandic Gigaword Corpus JSONL Converter", https://repository.clarin.is/repository/xmlui/handle/20.500.12537/336), funded under Iceland's "Language Technology for Icelandic 2019-2023" government initiative.
- `malfridur_api_correct.py` calls Miðeind's Málfríður API, which requires an API key. Users without one can substitute 2019's static word-list correction instead, via `extract_trigrams.py --static-word-correction`.
