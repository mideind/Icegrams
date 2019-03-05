=======================================================
Icegrams: A fast, compact trigram library for Icelandic
=======================================================

.. image:: https://travis-ci.org/vthorsteinsson/Icegrams.svg?branch=master
    :target: https://travis-ci.org/vthorsteinsson/Icegrams

********
Overview
********

**Icegrams** is a Python 3.x package that encapsulates a
**large trigram library for Icelandic**. (A trigram is a tuple of
three consecutive words or tokens that appear in real-world text.)

The almost 34 million trigrams are heavily compressed using radix tries and
`quasi-succinct indexes <https://arxiv.org/abs/1206.4300>`_ employing
Elias-Fano encoding. This enables the trigrams to be mapped into memory
for very fast queries (typically ~40 microseconds per lookup). The library
is implemented in Python and C/C++, glued together via
`CFFI <https://cffi.readthedocs.io/en/latest/>`_.

The trigram storage approach is based on a
`2017 paper by Pibiri and Venturini <http://pages.di.unipi.it/pibiri/papers/SIGIR17.pdf>`_.

You can use Icegrams to obtain probabilities (relative frequencies) of
over a million different unigrams (single words or tokens), or of
bigrams (pairs of two words or tokens), or of trigrams. You can also
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
>>> ng.freq("Ísland")
42019
>>>> ng.prob("Ísland")
0.0003979926900206475
>>>> ng.logprob("Ísland")
-7.8290769196308005
>>>>
>>> ng.freq("Katrín", "Jakobsdóttir")
3518
>>>> ng.prob("Katrín", "Jakobsdóttir")
0.23298013245033142
>>>> ng.prob("Katrín", "Júlíusdóttir")
0.013642384105960274
>>> ng.freq("velta", "fyrirtækisins", "er")
5
>>>> ng.prob("velta", "fyrirtækisins", "er")
0.2272727272727272
>>>> ng.prob("velta", "fyrirtækisins", "var")
0.04545454545454544
>>>> ng.freq("xxx", "yyy", "zzz")
1

*************
Prerequisites
*************

This package runs on CPython 3.4 or newer, and on PyPy 3.5 or newer.

If a binary wheel package isn't available on `PyPi <https://pypi.org>`_
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

*********
Reference
*********

TBD

