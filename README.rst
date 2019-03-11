=======================================================
Icegrams: A fast, compact trigram library for Icelandic
=======================================================

.. image:: https://travis-ci.com/vthorsteinsson/Icegrams.svg?branch=master
    :target: https://travis-ci.com/vthorsteinsson/Icegrams

********
Overview
********

**Icegrams** is a Python 3.x package that encapsulates a
**large trigram library for Icelandic**. (A trigram is a tuple of
three consecutive words or tokens that appear in real-world text.)

The almost 34 million trigrams are heavily compressed using radix tries and
`quasi-succinct indexes <https://arxiv.org/abs/1206.4300>`_ employing
Elias-Fano encoding. This enables the compressed trigram file to be mapped
directly into memory, with no *ex ante* decompression, for fast queries
(typically ~40 microseconds per lookup).

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

Icegrams is built on the database of `Greynir.is <https://greynir.is>`_,
comprising over 6 million sentences parsed from Icelandic news articles.

*******
Example
*******

>>> from icegrams import Ngrams
>>> ng = Ngrams()
>>> # Obtain the frequency of the unigram 'Ísland'
>>> ng.freq("Ísland")
42019
>>> # Obtain the probability of the unigram 'Ísland', as a fraction
>>> # of the frequency of all unigrams in the database
>>> ng.prob("Ísland")
0.0003979926900206475
>>> # Obtain the log probability (base e) of the unigram 'Ísland'
>>> ng.logprob("Ísland")
-7.8290769196308005
>>> # Obtain the frequency of the bigram 'Katrín Jakobsdóttir'
>>> ng.freq("Katrín", "Jakobsdóttir")
3518
>>> # Obtain the probability of 'Jakobsdóttir' given 'Katrín'
>>> ng.prob("Katrín", "Jakobsdóttir")
0.23298013245033142
>>> # Obtain the probability of 'Júlíusdóttir' given 'Katrín'
>>> ng.prob("Katrín", "Júlíusdóttir")
0.013642384105960274
>>> # Obtain the frequency of 'velta fyrirtækisins er'
>>> ng.freq("velta", "fyrirtækisins", "er")
5
>>> # All frequencies are adjusted, i.e incremented by 1
>>> ng.freq("xxx", "yyy", "zzz")
1

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
  * **returns** An integer with the adjusted frequency of the unigram,
    bigram or trigram. The adjusted frequency is the actual
    frequency plus 1. The method thus never returns 0.

  To query for the frequency of a unigram in the text, call
  ``ng.freq("unigram1")``. This returns the number of times that
  the unigram appears in the database, plus 1. The unigram is
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
    2974
    >>>> ng.freq("stjórnarskrá", "lýðveldisins")
    40
    >>>> ng.freq("stjórnarskrá", "lýðveldisins", "Íslands")
    13

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
  the frequency of the unigram divided by the sum of the
  frequencies of all unigrams in the database.

  The probability of a *bigram* ``(u1, u2)`` is the frequency
  of the bigram divided by the frequency of the unigram ``u1``,
  i.e. how likely ``u2`` is to succeed ``u1``.

  The probability of a trigram ``(u1, u2, u3)`` is the frequency
  of the trigram divided by the frequency of the bigram ``(u1, u2)``,
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
uses the rules documented there.

*************
Prerequisites
*************

This package runs on CPython 3.4 or newer, and on PyPy 3.5 or newer. It
has been tested on Linux (gcc on x86-64 and ARMhf), MacOS (clang) and
Windows (MSVC).

If a binary wheel package isn't available on `PyPI <https://pypi.org>`_
for your system, you may need to have the ``python3-dev`` and/or potentially
``python3.6-dev`` packages (or their Windows equivalents) installed on your
system to set up Icegrams successfully. This is because a source distribution
install requires a C++ compiler and linker::

    # Debian or Ubuntu:
    sudo apt-get install python3-dev
    sudo apt-get install python3.6-dev

************
Installation
************

To install this package::

    $ pip install icegrams

If you want to be able to edit the source, do like so (assuming you have **git** installed)::

    $ git clone https://github.com/vthorsteinsson/Icegrams
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

