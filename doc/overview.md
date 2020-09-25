The Icegrams trigram model
--------------------------

The trigram model was created as follows:

1. A random sample of document collections from the Icelandic Gigaword Corpus was generated,
   where each collection typically consists of a particular year of text from a particular website.
   From this set, texts dating from before 1980 were deleted, as well as texts from smaller websites
   that were deemed likely to have below-average proofreading standards.[^1] Finally, texts from
   identical years of mbl.is and Morgunblaðið (web and print versions of the same newspaper) were
   removed to reduce the risk of including duplicate texts. The remaining source set was sufficient
   for our “round number” target of processing at least 100 million tokens from the corpus.

2. Sentences from the source set were read and tokenized using the LT Programme’s
   [Tokenizer](https://github.com/mideind/Tokenizer).
   Word tokens were filtered to correct 2,853 distinct context-independent
   spelling errors (_aldrey_ -> _aldrei_), and 369 common amalgams were split into component
   words (_hinsvegar_ -> _hins vegar_). The data for this comes from subproject L6. Numbers,
   amounts, dates, percentages, ordinals, telephone numbers, e-mail addresses, URLs, hashtags
   and user handles (`@twittername`) were replaced with placeholder tokens (“`[NUMBER]`”, etc.)
   Quotation marks were regularized.

3. After tokenization and correction, a sliding window was applied to the resulting token
   stream to generate a trigram stream. This stream was fed to a PostgreSQL database, using
   its “UPSERT” feature to insert new unique trigrams or increment the count of previously seen ones.

4. We now had a database of 101,565,539 unique trigrams with their associated frequency counts.
   The total trigram occurrence count is 369,546,064 and the number of tokens processed is just
   above 100 million. The number of distinct tokens in the database is 2,500,603.

5. We then generated and analyzed a “bucket view” of trigram frequencies, shown here in tabular form:

   ```
    --------+----------+----------+-------+-----------+---------
     bucket | lowbound |   cnt    | perc  |  cum_cnt  | cum_perc
    --------+----------+----------+-------+-----------+---------
         14 |     5000 |     2482 |  0.00 |      2482 |     0.00
         13 |     2000 |     5597 |  0.01 |      8079 |     0.01
         12 |     1000 |    10869 |  0.01 |     18948 |     0.02
         11 |      500 |    24262 |  0.02 |     43210 |     0.04
         10 |      200 |    80177 |  0.08 |    123387 |     0.12
          9 |      100 |   143458 |  0.14 |    266845 |     0.26
          8 |       50 |   297058 |  0.29 |    563903 |     0.56
          7 |       20 |   938120 |  0.92 |   1502023 |     1.48
          6 |       10 |  1690756 |  1.66 |   3192779 |     3.14
          5 |        5 |  3965675 |  3.90 |   7158454 |     7.05
          4 |        4 |  2416991 |  2.38 |   9575445 |     9.43
          3 |        3 |  4602389 |  4.53 |  14177834 |    13.96
          2 |        2 | 14462011 | 14.24 |  28639845 |    28.20
          1 |        1 | 72925694 | 71.80 | 101565539 |   100.00
    --------+----------+----------+-------+-----------+---------
   ```

   By way of explanation, each bucket includes the trigrams that have at
   least the frequency shown in `lowbound`, but are not frequent enough
   to make it up to the next higher bucket. The `perc` column shows the
   size of the bucket as a percentage of all unique trigrams. The `cum_cnt` column
   shows a cumulative count, leading to the total number of unique trigrams
   in the database, and the `cum_perc` column shows the ratio of the cumulative
   count to that number.

6. Rare trigrams are more likely than common ones to contain spelling errors,
   and the presence of such errors detracts from the utility of the trigram database.
   Keeping this in mind, and in order to maximize the information content of the
   trigram model relative to its size, we decided to cut away trigrams with
   frequencies 1 or 2. This greatly reduced the size of the trigram database — to
   14,177,834 distinct trigrams, or just under 14% of the original count — while
   only minimally impacting the information content for the purpose of spelling
   correction. The reduced set of distinct trigrams still covers 267,696,348 total
   (non-unique) occurrences out of 369,546,064 for the whole set, or 72% of the occurrences.

7. The final, pared-down trigram set, along with its frequency data, was exported
   from PostgreSQL to a `.tsv` file and compressed using the _Icegrams_ compressor.
   The package’s dedicated n-gram compression algorithm uses Elias-Fano encoding
   with further enhancements as described in papers by Pibiri, Venturini and
   Ottaviano.[^2] The resulting compressed binary trigrams file is 43 megabytes
   in size and can be directly mapped into memory — even on mobile devices — for
   on-the-fly queries without _ex ante_ decompression.

The released _Icegrams_ package includes a Python wrapper (API), with performance-critical
parts written in C++, to query the compressed database easily and quickly (on the
order of ~10 microseconds per lookup).

The 20 most common trigrams in the database are as follows:

```
|----------+----------+--------+-----------|
|    t1    |    t2    |   t3   | frequency |
|----------+----------+--------+-----------|
| .        |          |        |  14905948 |
|          |          | "      |    816392 |
|          |          | Það    |    644929 |
|          |          | Í      |    595123 |
| "        |          |        |    410183 |
|          |          | Hann   |    401857 |
|          |          | Ég     |    401548 |
| .        | "        |        |    363470 |
| [NUMBER] | .        |        |    337176 |
|          |          | Þá     |    336765 |
| til      | þess     | að     |    294664 |
| ,        | "        | segir  |    285973 |
|          |          | Þetta  |    284744 |
| [YEAR]   | .        |        |    269387 |
| [NUMBER] | /        | [YEAR] |    257848 |
|          |          | Við    |    248546 |
|          | Það      | er     |    245194 |
| ?        |          |        |    234076 |
| nr.      | [NUMBER] | /      |    226382 |
|          |          | Á      |    217052 |
|----------+----------+--------+-----------|
```

From the top row, it can be inferred that the data includes 14,905,948
sentences that end with a period, and 644,929 sentences that start
with _Það_. It also encompasses 337,176 sentences that end with a
number preceding a period. The most common proper 3-word trigram
is _til þess að_, with 294,664 occurrences. It is also interesting
to note that 401,857 sentences start with _Hann [He]_, while 168,164
start with _Hún [She]_.

Below are a few examples of how the Python package can be used to query the database:

    ```
    $ python
    >>> # Import and initialize icegrams
    >>> from icegrams import Ngrams
    >>> ng = Ngrams()
    >>> # Obtain the frequency of the unigram 'Ísland'
    >>> ng.freq("Ísland")
    42018
    >>> # Obtain the frequency of the bigram 'Katrín Jakobsdóttir'
    >>> ng.freq("Katrín", "Jakobsdóttir")
    3517
    >>> # Obtain the probability of 'Jakobsdóttir' given 'Katrín'
    >>> ng.prob("Katrín", "Jakobsdóttir")
    0.23298013245033142
    >>> # Obtain the frequency of 'velta fyrirtækisins er'
    >>> ng.freq("velta", "fyrirtækisins", "er")
    4
    >>> # Obtain the N most likely successors of a given unigram or bigram,
    >>> # in descending order by log probability of each successor
    >>> ng.succ(10, "stjórnarskrá", "lýðveldisins")
    [('Íslands', -1.3708244393477589), ('.', -2.2427905461504567),
        (',', -3.313814878299737), ('og', -3.4920631097060557), ('sem', -4.566577846795106),
        ('er', -4.720728526622363), ('að', -4.807739903611993), ('um', -5.0084105990741445),
        ('en', -5.0084105990741445), ('á', -5.25972502735505)]
    ```

## Notes

[^1]:
     Specifically, we removed texts from 433.is, fotbolti.net, bleikt.is, eyjan.is and pressan.is.

[^2]:
     G.E. Pibiri and R. Venturini (2017): _Efficient Data Structures for Massive N-Gram Datasets_,
     Proceedings of the 40th International ACM SIGIR Conference, pp. 615-624;
     [http://pages.di.unipi.it/pibiri/papers/SIGIR17.pdf](http://pages.di.unipi.it/pibiri/papers/SIGIR17.pdf).
     See also an updated (2018) version of the paper at
     [https://arxiv.org/pdf/1806.09447.pdf](https://arxiv.org/pdf/1806.09447.pdf). We additionally
     use partitioned indexes as described in Ottaviano and Venturini (2014):
     _Partitioned Elias-Fano Indexes_, Proceedings of the 37th International ACM SIGIR Conference,
     pp. 273-282; [http://www.di.unipi.it/~ottavian/files/elias_fano_sigir14.pdf](http://www.di.unipi.it/~ottavian/files/elias_fano_sigir14.pdf).
