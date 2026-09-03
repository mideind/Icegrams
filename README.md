[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9](https://img.shields.io/badge/python-3.9-blue.svg)](https://www.python.org/downloads/release/python-3817/)
![Release](https://shields.io/github/v/release/mideind/Icegrams?display_name=tag)
![PyPI](https://img.shields.io/pypi/v/icegrams)
[![Python package](https://github.com/mideind/Icegrams/actions/workflows/python-package.yml/badge.svg)](https://github.com/mideind/Icegrams/actions?query=workflow%3A%22Python+package%22)

# Icegrams: A fast, compact trigram library for Icelandic

## Overview

**Icegrams** is an MIT-licensed Python 3 (>=3.9) package that encapsulates a
**large trigram library for Icelandic**. (A trigram is a tuple of
three consecutive words or tokens that appear in real-world text.)

Over 78 million unique trigrams and their frequency counts are heavily compressed
using radix tries and [quasi-succinct indexes](https://arxiv.org/abs/1206.4300)
employing Elias-Fano encoding. This enables the ~213 megabyte compressed trigram file
to be mapped directly into memory, with no *ex ante* decompression, for fast queries
(typically ~10 microseconds per lookup).

The Icegrams library is implemented in Python and C/C++, glued together via
[CFFI](https://cffi.readthedocs.io/en/latest/).

The trigram storage approach is based on a
[2017 paper by Pibiri and Venturini](http://pages.di.unipi.it/pibiri/papers/SIGIR17.pdf),
also referring to
[Ottaviano and Venturini](http://www.di.unipi.it/~ottavian/files/elias_fano_sigir14.pdf)
(2014) regarding partitioned Elias-Fano indexes.

You can use Icegrams to obtain probabilities (relative frequencies) of
over 1.7 million different **unigrams** (single words or tokens), or of
**bigrams** (pairs of two words or tokens), or of **trigrams**. You can also
ask it to return the N most likely successors to any unigram or bigram.

Icegrams is useful for instance in spelling correction, predictive typing,
to help disabled people write text faster, and for various text generation,
statistics and modelling tasks.

The Icegrams trigram corpus is built from the Icelandic Gigaword Corpus
([Risamálheild](https://repository.clarin.is/repository/xmlui/handle/20.500.12537/253)),
which is collected and maintained by *The Árni Magnússon Institute*
*for Icelandic Studies*, supplemented by a corpus of recent news articles
collected by Miðeind. A weighted sample of the corpora, containing about
1 billion tokens of text from 1980 through July 2026, was used as the
source of the token stream. Every sentence was corrected with Málfríður,
Miðeind's neural spelling and grammar correction model. Trigrams that only
occurred once in the stream were eliminated before creating the
compressed Icegrams database. The creation process is further
[described here](https://github.com/mideind/Icegrams/blob/master/doc/2026-update.md);
the previous (2019) model is described
[here](https://github.com/mideind/Icegrams/blob/master/doc/overview.md).
The 2019 model itself also remains available: it is bundled inside
`icegrams` releases up to and including 1.1.6 on
[PyPI](https://pypi.org/project/icegrams/1.1.6/), and can be retrieved
from this repository's git history, where it was tracked via Git LFS as
`src/icegrams/resources/trigrams.bin` until version 2.0.0.

## Example

```python
>>> from icegrams import Ngrams
>>> ng = Ngrams()
>>> # Obtain the frequency of the unigram 'Ísland'
>>> ng.freq("Ísland")
708104
>>> # Obtain the probability of the unigram 'Ísland', as a fraction
>>> # of the frequency of all unigrams in the database
>>> ng.prob("Ísland")
0.00023349672913028182
>>> # Obtain the log probability (base e) of the unigram 'Ísland'
>>> ng.logprob("Ísland")
-8.362342488960794
>>> # Obtain the frequency of the bigram 'Katrín Jakobsdóttir'
>>> ng.freq("Katrín", "Jakobsdóttir")
47918
>>> # Obtain the probability of 'Jakobsdóttir' given 'Katrín'
>>> ng.prob("Katrín", "Jakobsdóttir")
0.1746471994635099
>>> # Obtain the probability of 'Júlíusdóttir' given 'Katrín'
>>> ng.prob("Katrín", "Júlíusdóttir")
0.027305595241566307
>>> # Obtain the frequency of 'velta fyrirtækisins er'
>>> ng.freq("velta", "fyrirtækisins", "er")
15
>>> # adj_freq returns adjusted frequencies, i.e incremented by 1
>>> ng.adj_freq("xxx", "yyy", "zzz")
1
>>> # Obtain the N most likely successors of a given unigram or bigram,
>>> # in descending order by log probability of each successor
>>> ng.succ(10, "stjórnarskrá", "lýðveldisins")
[('Íslands', -1.4328143767547825), ('.', -2.4118815147731096),
    (',', -2.960989325110117), ('og', -3.4164648537929434), ('að', -4.693559922947841),
    ('sem', -4.728651242759112), ('er', -5.016333315210893), ('í', -5.49590639547278),
    ('en', -5.575949103146316), ('?', -5.575949103146316)]
>>> ng.succ(1, "Ég", "hlýði")
[('Víði', -0.9694005571881035)]
```

## Reference

### Initializing Icegrams

After installing the `icegrams` package, use the following code to
import it and initialize an instance of the `Ngrams` class:

```python
from icegrams import Ngrams
ng = Ngrams()
```

Now you can use the `ng` instance to query for unigram, bigram
and trigram frequencies and probabilities.

Note that the trigram model file must be downloaded once before an
`Ngrams` instance can be created, as described in the
[Installation](#installation) section. If the model is not present,
the `Ngrams()` constructor raises `icegrams.ModelNotFoundError`.

### The Ngrams class

* `__init__(self)`

  Initializes the `Ngrams` instance.

* `freq(self, *args) -> int`

  Returns the frequency of a unigram, bigram or trigram.

  * `str[] *args` A parameter sequence of consecutive unigrams
    to query the frequency for.
  * **returns** An integer with the frequency of the unigram,
    bigram or trigram.

  To query for the frequency of a unigram in the text, call
  `ng.freq("unigram1")`. This returns the number of times that
  the unigram appears in the database. The unigram is
  queried as-is, i.e. with no string stripping or lowercasing.

  To query for the frequency of a bigram in the text, call
  `ng.freq("unigram1", "unigram2")`.

  To query for the frequency of a trigram in the text, call
  `ng.freq("unigram1", "unigram2", "unigram3")`.

  If you pass more than 3 arguments to `ng.freq()`, only the
  last 3 are significant, and the query will be treated
  as a trigram query.

  Examples:

  ```python
  >>>> ng.freq("stjórnarskrá")
  107427
  >>>> ng.freq("stjórnarskrá", "lýðveldisins")
  3167
  >>>> ng.freq("stjórnarskrá", "lýðveldisins", "Íslands")
  755
  >>>> ng.freq("xxx", "yyy", "zzz")
  0
  ```

* `adj_freq(self, *args) -> int`

  Returns the adjusted frequency of a unigram, bigram or trigram.

  * `str[] *args` A parameter sequence of consecutive unigrams
    to query the frequency for.
  * **returns** An integer with the adjusted frequency of the unigram,
    bigram or trigram. *The adjusted frequency is the actual*
    *frequency plus 1.* The method thus never returns 0.

  To query for the frequency of a unigram in the text, call
  `ng.adj_freq("unigram1")`. This returns the number of times that
  the unigram appears in the database, plus 1. The unigram is
  queried as-is, i.e. with no string stripping or lowercasing.

  To query for the frequency of a bigram in the text, call
  `ng.adj_freq("unigram1", "unigram2")`.

  To query for the frequency of a trigram in the text, call
  `ng.adj_freq("unigram1", "unigram2", "unigram3")`.

  If you pass more than 3 arguments to `ng.adj_freq()`, only the
  last 3 are significant, and the query will be treated
  as a trigram query.

  Examples:

  ```python
  >>>> ng.adj_freq("stjórnarskrá")
  107428
  >>>> ng.adj_freq("stjórnarskrá", "lýðveldisins")
  3168
  >>>> ng.adj_freq("stjórnarskrá", "lýðveldisins", "Íslands")
  756
  >>>> ng.adj_freq("xxx", "yyy", "zzz")
  1
  ```

* `prob(self, *args) -> float`

  Returns the probability of a unigram, bigram or trigram.

  * `str[] *args` A parameter sequence of consecutive unigrams
    to query the probability for.
  * **returns** A float with the probability of the given unigram,
    bigram or trigram.

  The probability of a *unigram* is
  the frequency of the unigram divided by the sum of the
  frequencies of all unigrams in the database.

  The probability of a *bigram* `(u1, u2)` is the frequency
  of the bigram divided by the frequency of the unigram `u1`,
  i.e. how likely `u2` is to succeed `u1`.

  The probability of a trigram `(u1, u2, u3)` is the frequency
  of the trigram divided by the frequency of the bigram `(u1, u2)`,
  i.e. how likely `u3` is to succeed `u1 u2`.

  If you pass more than 3 arguments to `ng.prob()`, only the
  last 3 are significant, and the query will be treated
  as a trigram probability query.

  Examples:

  ```python
  >>>> ng.prob("stjórnarskrá")
  3.542424727548586e-05
  >>>> ng.prob("stjórnarskrá", "lýðveldisins")
  0.02948951856126892
  >>>> ng.prob("stjórnarskrá", "lýðveldisins", "Íslands")
  0.23863636363636387
  ```

* `logprob(self, *args) -> float`

  Returns the log probability of a unigram, bigram or trigram.

  * `str[] *args` A parameter sequence of consecutive unigrams
    to query the log probability for.
  * **returns** A float with the natural logarithm (base *e*) of the
    probability of the given unigram, bigram or trigram.

  The probability of a *unigram* is
  the adjusted frequency of the unigram divided by the sum of the
  frequencies of all unigrams in the database.

  The probability of a *bigram* `(u1, u2)` is the adjusted frequency
  of the bigram divided by the adjusted frequency of the unigram `u1`,
  i.e. how likely `u2` is to succeed `u1`.

  The probability of a trigram `(u1, u2, u3)` is the adjusted frequency
  of the trigram divided by the adjusted frequency of the bigram `(u1, u2)`,
  i.e. how likely `u3` is to succeed `u1 u2`.

  If you pass more than 3 arguments to `ng.logprob()`, only the
  last 3 are significant, and the query will be treated
  as a trigram probability query.

  Examples:

  ```python
  >>>> ng.logprob("stjórnarskrá")
  -10.248114021011704
  >>>> ng.logprob("stjórnarskrá", "lýðveldisins")
  -3.523720381779265
  >>>> ng.logprob("stjórnarskrá", "lýðveldisins", "Íslands")
  -1.4328143767547825
  ```

* `succ(self, n, *args) -> list[tuple]`

  Returns the *N* most probable successors of a unigram or bigram.

  * `int n` A positive integer specifying how many successors,
    at a maximum, should be returned.
  * `str[] *args` One or two string parameters containing the
    unigram or bigram to query the successors for.
  * **returns** A list of tuples of (successor unigram, log probability),
    in descending order of probability.

  If you pass more than 2 string arguments to `ng.succ()`, only the
  last 2 are significant, and the query will be treated
  as a bigram successor query.

  Examples:

  ```python
  >>>> ng.succ(2, "stjórnarskrá")
  [('.', -1.8955821526777576), ('og', -2.45003747615368)]
  >>>> ng.succ(2, "stjórnarskrá", "lýðveldisins")
  [('Íslands', -1.4328143767547825), ('.', -2.4118815147731096)]
  >>>> # The following is equivalent to ng.succ(2, "lýðveldisins", "Íslands")
  >>>> ng.succ(2, "stjórnarskrá", "lýðveldisins", "Íslands")
  [(',', -1.799606749884445), ('nr.', -1.8759797286690185)]
  ```

## Notes

Icegrams is built with a sliding window over the source text. This means that
a sentence such as `"Maðurinn borðaði ísinn."` results in the following
trigrams being added to the database:

```python
   ("", "", "Maðurinn")
   ("", "Maðurinn", "borðaði")
   ("Maðurinn", "borðaði", "ísinn")
   ("borðaði", "ísinn", ".")
   ("ísinn", ".", "")
   (".", "", "")
```

The same sliding window strategy is applied for bigrams, so the following
bigrams would be recorded for the same sentence:

```python
   ("", "Maðurinn")
   ("Maðurinn", "borðaði")
   ("borðaði", "ísinn")
   ("ísinn", ".")
   (".", "")
```

You can thus obtain the N unigrams that most often start
a sentence by asking for `ng.succ(N, "")`.

And, of course, four unigrams are also added, one for each token in the
sentence.

The tokenization of the source text into unigrams is done with the
[Tokenizer package](https://pypi.org/project/tokenizer) and
uses the rules documented there. Importantly, tokens other than words,
abbreviations, entity names, person names and punctuation are
**replaced by placeholders**. This means that all numbers are represented by the token
`[NUMBER]`, amounts by `[AMOUNT]`, dates by `[DATEABS]` and `[DATEREL]`,
e-mail addresses by `[EMAIL]`, etc. For the complete mapping of token types
to placeholder strings, see the
[documentation for the Tokenizer package](https://github.com/mideind/Tokenizer/blob/master/README.rst).

## Prerequisites

This package runs on CPython 3.9 or newer, and on PyPy 3.9 or newer. It
has been tested on Linux (gcc on x86-64 and ARMhf), macOS (clang) and
Windows (MSVC).

If a binary wheel package isn't available on [PyPI](https://pypi.org)
for your system, you may need to have the `python3-dev` package
(or its Windows equivalent) installed on your system to set up
Icegrams successfully. This is because a source distribution
install requires a C++ compiler and linker:

```bash
# Debian or Ubuntu:
sudo apt-get install python3-dev
```

## Installation

To install this package:

```bash
pip install icegrams
```

The trigram model file (~213 MB) is not included in the package itself.
It is published as an asset of a GitHub release of this repository and
must be downloaded once, after installing the package:

```bash
python -m icegrams.download
```

This stores the model in a per-user cache directory (on Linux typically
`~/.cache/icegrams/`), verifies its checksum, and is a no-op if the
model is already there. The same step is available from Python as
`icegrams.download.download_model()`. Downloading is deliberately a separate
setup step: creating an `Ngrams` instance never accesses the network,
it only checks that the model is present and raises
`icegrams.ModelNotFoundError` if it isn't.

The following environment variables affect where the model is stored
and looked up:

* `ICEGRAMS_MODEL_DIR`: base directory for the model, instead of the
  per-user cache directory. The model is stored in a subdirectory named
  after the model release (e.g. `model-2026.08`), so a package upgrade
  that ships a new model requires running the download step again.
* `ICEGRAMS_MODEL_FILE`: path of an existing model file to use directly,
  skipping the lookup entirely (useful for offline or air-gapped
  environments).
* `ICEGRAMS_MODEL_URL`: alternative URL for the download step to fetch
  the model from. The pinned checksum is only verified for the
  official URL.

Run `python -m icegrams.download --help` for the corresponding
command-line options (`--dir`, `--url` and `--force`).

If you want to be able to edit the source, do like so (assuming you have **git** installed):

```bash
git clone https://github.com/mideind/Icegrams
cd Icegrams
# [ Activate your virtualenv here if you have one ]
python setup.py develop
```

The package source code is now in `./src/icegrams`.

## Tests

To run the built-in tests, install [pytest](https://docs.pytest.org/en/latest/),
`cd` to your `Icegrams` subdirectory (and optionally activate your
virtualenv), then run:

```bash
python -m pytest
```

## Changelog

* Version 2.0.0: New trigram model built from a ~1 billion word corpus
  (IGC-2022 and IGC-2024ext plus recent news through July 2026), corrected
  with Miðeind's Málfríður neural spelling and grammar correction model.
  The model file is no longer bundled in the package; it is fetched from
  a GitHub release in a separate one-time step, `python -m icegrams.download`,
  and `Ngrams()` raises `ModelNotFoundError` if it isn't present. (2026-09-03)
* Version 1.1.7: Published abi3 wheels; fixed C++ linking in source builds. (2026-06-11)
* Version 1.1.6: Added abi3 wheel support for smaller release size. (2025-12-12)
* Version 1.1.5: Fixed PEP 561 compliance (py.typed). Fixed ruff linting in CI. (2025-12-12)
* Version 1.1.4: Added support for Python 3.14 and Windows. Improved CI with PyPI trusted publishing. (2025-12-12)
* Version 1.1.3: Minor tweaks. Support for Python 3.13. Now requires Python 3.9+. (2024-08-27)
* Version 1.1.2: Minor bug fixes. Cross-platform wheels provided. Now requires Python 3.7+. (2022-12-14)
* Version 1.1.0: Python 3.5 support dropped; macOS builds fixed; PyPy wheels
  generated
* Version 1.0.0: New trigram database sourced from the Icelandic Gigaword Corpus
  (Risamálheild) with improved tokenization. Replaced GNU GPLv3 with MIT license.
* Version 0.6.0: Python type annotations added
* Version 0.5.0: Trigrams corpus has been spell-checked

## Copyright and licensing

Icegrams is Copyright © 2020-2026 [Miðeind ehf.](https://mideind.is).
The original author of this software is *Vilhjálmur Þorsteinsson*.

This software is licensed under the **MIT License**:

*Permission is hereby granted, free of charge, to any person*
*obtaining a copy of this software and associated documentation*
*files (the "Software"), to deal in the Software without restriction,*
*including without limitation the rights to use, copy, modify, merge,*
*publish, distribute, sublicense, and/or sell copies of the Software,*
*and to permit persons to whom the Software is furnished to do so,*
*subject to the following conditions:*

**The above copyright notice and this permission notice shall be**
**included in all copies or substantial portions of the Software.**

*THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,*
*EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF*
*MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.*
*IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY*
*CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,*
*TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE*
*SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.*
