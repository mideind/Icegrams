"""Queries from many threads at once on one Ngrams must give the same results as from one.

On free-threaded Python (3.14t) the threads really run in parallel.
"""

import random
import sys
import sysconfig
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

import pytest

from icegrams import ModelNotFoundError, Ngrams

FREE_THREADED = not getattr(sys, "_is_gil_enabled", lambda: True)()
# With the GIL the threads take turns, and cffi releases the GIL around every C
# call, so more threads only add hand-offs (8 threads take 25 times as long as
# one for the same queries): use two threads with half of the queries each
THREADS = 8 if FREE_THREADED else 2
SHARE = 1 if FREE_THREADED else THREADS

# Common and rare words, sentence boundaries (""), an unknown word and one
# with a character outside the alphabet
WORDS = [
    "",
    "það",
    "er",
    "gott",
    "að",
    "vera",
    "Ísland",
    "Katrín",
    "Jakobsdóttir",
    "hundurinn",
    "át",
    "xyzqw",
    "ŵ",
]

OPS: list[tuple[str, Callable[[Ngrams, tuple[str, ...]], Any]]] = [
    ("freq", lambda ng, w: ng.freq(*w)),
    ("adj_freq", lambda ng, w: ng.adj_freq(*w)),
    ("logprob", lambda ng, w: ng.logprob(*w)),
    ("prob", lambda ng, w: ng.prob(*w)),
    # Successors of one word can be most of the vocabulary: only two-word contexts
    ("succ", lambda ng, w: ng.succ(5, *w[-2:]) if len(w) == 3 else None),
    ("contains", lambda ng, w: w[-1] in ng),
]

NGRAMS = (
    [(c,) for c in WORDS]
    + [(b, c) for b in WORDS for c in WORDS]
    + [("", b, c) for b in WORDS for c in WORDS]
)


def _ngrams() -> Ngrams:
    try:
        return Ngrams()
    except ModelNotFoundError as e:
        pytest.skip(f"Trigram model not downloaded: {e}")


@pytest.mark.thread_unsafe
def test_parallel_queries_match_serial() -> None:
    serial = _ngrams()
    expected = {(name, w): op(serial, w) for name, op in OPS for w in NGRAMS}
    serial.close()

    # A fresh instance, so that the threads also race to compute its lazily cached values
    shared = _ngrams()
    barrier = threading.Barrier(THREADS)
    ops = dict(OPS)

    def work(seed: int) -> list[tuple[str, tuple[str, ...]]]:
        keys = list(expected)
        random.Random(seed).shuffle(keys)
        keys = keys[: len(keys) // SHARE]
        barrier.wait()
        return [
            (name, w) for name, w in keys if ops[name](shared, w) != expected[(name, w)]
        ]

    with ThreadPoolExecutor(THREADS) as pool:
        mismatches = [m for ms in pool.map(work, range(THREADS)) for m in ms]
    shared.close()
    assert mismatches == []


@pytest.mark.skipif(
    not sysconfig.get_config_var("Py_GIL_DISABLED"), reason="needs free-threaded Python"
)
def test_gil_stays_disabled() -> None:
    # An extension that does not declare free-threading support turns the GIL back on at import
    import icegrams._trie  # noqa: F401  # type: ignore

    assert not sys._is_gil_enabled()  # type: ignore[attr-defined]
