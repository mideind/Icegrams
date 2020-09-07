=======================================================
Icegrams: A fast, compact trigram library for Icelandic
=======================================================

.. image:: https://travis-ci.com/mideind/Icegrams.svg?branch=master
    :target: https://travis-ci.com/mideind/Icegrams

********
Overview
********

**Icegrams** is an MIT-licensed Python 3 (>= 3.5) package that encapsulates a
**large trigram library for Icelandic**. (A trigram is a tuple of
three consecutive words or tokens that appear in real-world text.)

14 million unique trigrams and their frequency counts are heavily compressed
using radix tries and `quasi-succinct indexes <https://arxiv.org/abs/1206.4300>`_
employing Elias-Fano encoding. This enables the ~43 megabyte compressed trigram file
to be mapped directly into memory, with no *ex ante* decompression, for fast queries
(typically ~10 microseconds per lookup).

The Icegrams library is implemented in Python and C/C++, glued together via
`CFFI <https://cffi.readthedocs.io/en/latest/>`_.

The trigram storage approach is based on a
`2017 paper by Pibiri and Venturini <http://pages.di.unipi.it/pibiri/papers/SIGIR17.pdf>`_,
also referring to
`Ottaviano and Venturini <http://www.di.unipi.it/~ottavian/files/elias_fano_sigir14.pdf>`_
(2014) regarding partitioned Elias-Fano indexes.

You can use Icegrams to obtain probabilities (relative frequencies) of
over a million different **unigrams** (single words or tokens), or of
**bigrams** (pairs of two words or tokens), or of **trigrams**. You can also
ask it to return the N most likely successors to any unigram or bigram.

Icegrams is useful for instance in spelling correction, predictive typing,
to help disabled people write text faster, and for various text generation,
statistics and modelling tasks.

The Icegrams trigram corpus is built from the 2017 edition of the
Icelandic Gigaword Corpus
(`Risamálheild <https://malheildir.arnastofnun.is/?mode=rmh2017>`_),
which is collected and maintained by *The Árni Magnússon Institute*
*for Icelandic Studies*. A mixed, manually vetted subset consisting of 157
documents from the corpus was used as the source of the token stream,
yielding over 100 million tokens. Trigrams that only occurred
once or twice in the stream were eliminated before creating the
compressed Icegrams database.

*******
Example
*******

>>> from icegrams import Ngrams
>>> ng = Ngrams()
>>> # Obtain the frequency of the unigram 'Ísland'
>>> ng.freq("Ísland")
42018
>>> # Obtain the probability of the unigram 'Ísland', as a fraction
>>> # of the frequency of all unigrams in the database
>>> ng.prob("Ísland")
0.0003979926900206475
>>> # Obtain the log probability (base e) of the unigram 'Ísland'
>>> ng.logprob("Ísland")
-7.8290769196308005
>>> # Obtain the frequency of the bigram 'Katrín Jakobsdóttir'
>>> ng.freq("Katrín", "Jakobsdóttir")
3517
>>> # Obtain the probability of 'Jakobsdóttir' given 'Katrín'
>>> ng.prob("Katrín", "Jakobsdóttir")
0.23298013245033142
>>> # Obtain the probability of 'Júlíusdóttir' given 'Katrín'
>>> ng.prob("Katrín", "Júlíusdóttir")
0.013642384105960274
>>> # Obtain the frequency of 'velta fyrirtækisins er'
>>> ng.freq("velta", "fyrirtækisins", "er")
4
>>> # adj_freq returns adjusted frequencies, i.e incremented by 1
>>> ng.adj_freq("xxx", "yyy", "zzz")
1
>>> # Obtain the N most likely successors of a given unigram or bigram,
>>> # in descending order by log probability of each successor
>>> ng.succ(10, "stjórnarskrá", "lýðveldisins")
[('Íslands', -1.3708244393477589), ('.', -2.2427905461504567),
    (',', -3.313814878299737), ('og', -3.4920631097060557), ('sem', -4.566577846795106),
    ('er', -4.720728526622363), ('að', -4.807739903611993), ('um', -5.0084105990741445),
    ('en', -5.0084105990741445), ('á', -5.25972502735505)]


*********
Reference
*********

Initializing Icegrams
---------------------

After installing the ``icegrams`` package, use the following code to
import it and initialize an instance of the ``Ngrams`` class::

    from icegrams import Ngrams
    ng = Ngrams()

Now you can use the ``ng`` instance to query for unigram, bigram
and trigram frequencies and probabilities.

The Ngrams class
----------------

* ``__init__(self)``

  Initializes the ``Ngrams`` instance.

* ``freq(self, *args) -> int``

  Returns the frequency of a unigram, bigram or trigram.

  * ``str[] *args`` A parameter sequence of consecutive unigrams
    to query the frequency for.
  * **returns** An integer with the frequency of the unigram,
    bigram or trigram.

  To query for the frequency of a unigram in the text, call
  ``ng.freq("unigram1")``. This returns the number of times that
  the unigram appears in the database. The unigram is
  queried as-is, i.e. with no string stripping or lowercasing.

  To query for the frequency of a bigram in the text, call
  ``ng.freq("unigram1", "unigram2")``.

  To query for the frequency of a trigram in the text, call
  ``ng.freq("unigram1", "unigram2", "unigram3")``.

  If you pass more than 3 arguments to ``ng.freq()``, only the
  last 3 are significant, and the query will be treated
  as a trigram query.

  Examples::

    >>>> ng.freq("stjórnarskrá")
    2973
    >>>> ng.freq("stjórnarskrá", "lýðveldisins")
    39
    >>>> ng.freq("stjórnarskrá", "lýðveldisins", "Íslands")
    12
    >>>> ng.freq("xxx", "yyy", "zzz")
    0

* ``adj_freq(self, *args) -> int``

  Returns the adjusted frequency of a unigram, bigram or trigram.

  * ``str[] *args`` A parameter sequence of consecutive unigrams
    to query the frequency for.
  * **returns** An integer with the adjusted frequency of the unigram,
    bigram or trigram. The adjusted frequency is the actual
    frequency plus 1. The method thus never returns 0.

  To query for the frequency of a unigram in the text, call
  ``ng.adj_freq("unigram1")``. This returns the number of times that
  the unigram appears in the database, plus 1. The unigram is
  queried as-is, i.e. with no string stripping or lowercasing.

  To query for the frequency of a bigram in the text, call
  ``ng.adj_freq("unigram1", "unigram2")``.

  To query for the frequency of a trigram in the text, call
  ``ng.adj_freq("unigram1", "unigram2", "unigram3")``.

  If you pass more than 3 arguments to ``ng.adj_freq()``, only the
  last 3 are significant, and the query will be treated
  as a trigram query.

  Examples::

    >>>> ng.adj_freq("stjórnarskrá")
    2974
    >>>> ng.adj_freq("stjórnarskrá", "lýðveldisins")
    40
    >>>> ng.adj_freq("stjórnarskrá", "lýðveldisins", "Íslands")
    13
    >>>> ng.adj_freq("xxx", "yyy", "zzz")
    1

* ``prob(self, *args) -> float``

  Returns the probability of a unigram, bigram or trigram.

  * ``str[] *args`` A parameter sequence of consecutive unigrams
    to query the probability for.
  * **returns** A float with the probability of the given unigram,
    bigram or trigram.

  The probability of a *unigram* is
  the frequency of the unigram divided by the sum of the
  frequencies of all unigrams in the database.

  The probability of a *bigram* ``(u1, u2)`` is the frequency
  of the bigram divided by the frequency of the unigram ``u1``,
  i.e. how likely ``u2`` is to succeed ``u1``.

  The probability of a trigram ``(u1, u2, u3)`` is the frequency
  of the trigram divided by the frequency of the bigram ``(u1, u2)``,
  i.e. how likely ``u3`` is to succeed ``u1 u2``.

  If you pass more than 3 arguments to ``ng.prob()``, only the
  last 3 are significant, and the query will be treated
  as a trigram probability query.

  Examples::

    >>>> ng.prob("stjórnarskrá")
    2.8168929772755334e-05
    >>>> ng.prob("stjórnarskrá", "lýðveldisins")
    0.01344989912575655
    >>>> ng.prob("stjórnarskrá", "lýðveldisins", "Íslands")
    0.325

* ``logprob(self, *args) -> float``

  Returns the log probability of a unigram, bigram or trigram.

  * ``str[] *args`` A parameter sequence of consecutive unigrams
    to query the log probability for.
  * **returns** A float with the natural logarithm (base *e*) of the
    probability of the given unigram, bigram or trigram.

  The probability of a *unigram* is
  the adjusted frequency of the unigram divided by the sum of the
  frequencies of all unigrams in the database.

  The probability of a *bigram* ``(u1, u2)`` is the adjusted frequency
  of the bigram divided by the adjusted frequency of the unigram ``u1``,
  i.e. how likely ``u2`` is to succeed ``u1``.

  The probability of a trigram ``(u1, u2, u3)`` is the adjusted frequency
  of the trigram divided by the adjusted frequency of the bigram ``(u1, u2)``,
  i.e. how likely ``u3`` is to succeed ``u1 u2``.

  If you pass more than 3 arguments to ``ng.logprob()``, only the
  last 3 are significant, and the query will be treated
  as a trigram probability query.

  Examples::

    >>>> ng.logprob("stjórnarskrá")
    -10.477290968535172
    >>>> ng.logprob("stjórnarskrá", "lýðveldisins")
    -4.308783672906165
    >>>> ng.logprob("stjórnarskrá", "lýðveldisins", "Íslands")
    -1.1239300966523995

* ``succ(self, n, *args) -> list[tuple]``

  Returns the *N* most probable successors of a unigram or bigram.

  * ``int n`` A positive integer specifying how many successors,
    at a maximum, should be returned.
  * ``str[] *args`` One or two string parameters containing the
    unigram or bigram to query the successors for.
  * **returns** A list of tuples of (successor unigram, log probability),
    in descending order of probability.

  If you pass more than 2 string arguments to ``ng.succ()``, only the
  last 2 are significant, and the query will be treated
  as a bigram successor query.

  Examples::

    >>>> ng.succ(2, "stjórnarskrá")
    [('.', -1.8259625296091855), ('landsins', -2.223111581475692)]
    >>>> ng.succ(2, "stjórnarskrá", "lýðveldisins")
    [('Íslands', -1.1239300966523995), ('og', -1.3862943611198904)]
    >>>> # The following is equivalent to ng.succ(2, "lýðveldisins", "Íslands")
    >>>> ng.succ(2, "stjórnarskrá", "lýðveldisins", "Íslands")
    [('.', -1.3862943611198908), (',', -1.6545583477145702)]

*****
Notes
*****

Icegrams is built with a sliding window over the source text. This means that
a sentence such as ``"Maðurinn borðaði ísinn."`` results in the following
trigrams being added to the database::

   ("", "", "Maðurinn")
   ("", "Maðurinn", "borðaði")
   ("Maðurinn", "borðaði", "ísinn")
   ("borðaði", "ísinn", ".")
   ("ísinn", ".", "")
   (".", "", "")

The same sliding window strategy is applied for bigrams, so the following
bigrams would be recorded for the same sentence::

   ("", "Maðurinn")
   ("Maðurinn", "borðaði")
   ("borðaði", "ísinn")
   ("ísinn", ".")
   (".", "")

You can thus obtain the N unigrams that most often start
a sentence by asking for ``ng.succ(N, "")``.

And, of course, four unigrams are also added, one for each token in the
sentence.

The tokenization of the source text into unigrams is done with the
`Tokenizer package <https://pypi.org/project/tokenizer>`_ and
uses the rules documented there. Importantly, tokens other than words,
abbreviations, entity names, person names and punctuation are
**replaced by placeholders**. This means that all numbers are represented by the token
``[NUMBER]``, amounts by ``[AMOUNT]``, dates by ``[DATEABS]`` and ``[DATEREL]``,
e-mail addresses by ``[EMAIL]``, etc. For the complete mapping of token types
to placeholder strings, see the
`documentation for the Tokenizer package <https://github.com/mideind/Tokenizer/blob/master/README.rst>`_.

*************
Prerequisites
*************

This package runs on CPython 3.5 or newer, and on PyPy 3.5 or newer. It
has been tested on Linux (gcc on x86-64 and ARMhf), MacOS (clang) and
Windows (MSVC).

If a binary wheel package isn't available on `PyPI <https://pypi.org>`_
for your system, you may need to have the ``python3-dev`` package
(or its Windows equivalent) installed on your system to set up
Icegrams successfully. This is because a source distribution
install requires a C++ compiler and linker::

    # Debian or Ubuntu:
    sudo apt-get install python3-dev

************
Installation
************

To install this package::

    $ pip install icegrams

If you want to be able to edit the source, do like so (assuming you have **git** installed)::

    $ git clone https://github.com/mideind/Icegrams
    $ cd Icegrams
    $ # [ Activate your virtualenv here if you have one ]
    $ python setup.py develop

The package source code is now in ``./src/icegrams``.

*****
Tests
*****

To run the built-in tests, install `pytest <https://docs.pytest.org/en/latest/>`_,
``cd`` to your ``Icegrams`` subdirectory (and optionally activate your
virtualenv), then run::

    $ python -m pytest

*********
Changelog
*********

* Version 1.0.0: New trigram database sourced from the Icelandic Gigaword Corpus
  (Risamálheild) with improved tokenization. Replaced GNU GPLv3 with MIT license.
* Version 0.6.0: Python type annotations added
* Version 0.5.0: Trigrams corpus has been spell-checked
