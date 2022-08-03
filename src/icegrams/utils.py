"""

    Icegrams: A trigrams library for Icelandic

    utils.py

    Copyright (C) 2020 Miðeind ehf.

    This software is licensed under the MIT License:

        Permission is hereby granted, free of charge, to any person
        obtaining a copy of this software and associated documentation
        files (the "Software"), to deal in the Software without restriction,
        including without limitation the rights to use, copy, modify, merge,
        publish, distribute, sublicense, and/or sell copies of the Software,
        and to permit persons to whom the Software is furnished to do so,
        subject to the following conditions:

        The above copyright notice and this permission notice shall be
        included in all copies or substantial portions of the Software.

        THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
        EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
        MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
        IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
        CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
        TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
        SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.


    This module contains helper functions for turning text into a token stream
    or trigram stream that is normalized according to the same normalization
    rules as were used to create the trigram database.

"""

from typing import (
    Iterator, Iterable, Tuple, List, Optional, Dict, Set, Callable, Type, Any
)
import os
from itertools import islice, tee
from tokenizer import tokenize, correct_spaces, Tok, TOK


# Obtain our path
basepath, _ = os.path.split(os.path.realpath(__file__))


# A set of all words we need to change
CHANGING: Set[str] = set()
# fACE_SK.txt
REPLACING: Dict[str, str] = dict()
# d.txt
DELETING: Set[str] = set()
# fMW.txt
DOUBLING: Dict[str, List[str]] = dict()


def load_corrections() -> None:
    """ Fills global data structures for correcting tokens """
    with open(os.path.join(basepath, "resources", "correct.txt"), "r", encoding="utf-8") as myfile:
        for line in myfile:
            key, val = line.strip().split("\t")
            REPLACING[key] = val
            CHANGING.add(key)
    with open(os.path.join(basepath, "resources", "delete.txt"), "r", encoding="utf-8") as myfile:
        for line in myfile:
            key = line.strip()
            DELETING.add(key)
            CHANGING.add(key)
    with open(os.path.join(basepath, "resources", "split.txt"), "r", encoding="utf-8") as myfile:
        for line in myfile:
            key, val = line.strip().split("\t")
            val = val.strip()
            DOUBLING[key] = val.split()
            CHANGING.add(key)
            if key.islower() and val.islower():
                # Also add uppercase version
                key = key.capitalize()
                val = val.capitalize()
                DOUBLING[key] = val.split()
                CHANGING.add(key)


load_corrections()


def handle_word(token: Tok) -> Iterator[str]:
    """ Return the text of a word token, after potential editing """
    t = token.txt
    if t in CHANGING:
        # We take a closer look
        if t in REPLACING:
            # Words we simply need to replace
            yield REPLACING[t]
        elif t in DELETING:
            # Words that don't belong in trigrams
            pass
        elif t in DOUBLING:
            # Words incorrectly in one token
            for part in DOUBLING[t]:
                yield part
        else:
            # Should not happen
            assert False
    elif " " in t:
        yield from t.split()
    else:
        yield t


def handle_punctuation(token: Tok) -> Iterator[str]:
    """ Return the normalized version of punctuation """
    yield token.val[1]


def handle_passthrough(token: Tok) -> Iterator[str]:
    """ Return the token text unchanged """
    yield token.txt


def handle_split(token: Tok) -> Iterator[str]:
    """ Split the token text by spaces and return the components """
    yield from token.txt.split()


def handle_measurement(token: Tok) -> Iterator[str]:
    """ Return a [NUMBER] token followed by a SI unit """
    yield from ("[NUMBER]", token.val[0])


def handle_none(token: Tok) -> Iterator[str]:
    """ Empty generator """
    yield from ()


def handle_other(token: Tok) -> Iterator[str]:
    """ Return a standard placeholder for the token kind """
    yield "[" + TOK.descr[token.kind] + "]"


# Dispatch the various token types to the appropriate generators,
# defaulting to handle_others
token_dispatch: Dict[int, Callable[[Tok], Iterator[str]]] = {
    TOK.WORD: handle_word,
    TOK.PUNCTUATION: handle_punctuation,
    TOK.MEASUREMENT: handle_measurement,
    TOK.MOLECULE: handle_passthrough,
    TOK.PERSON: handle_split,
    TOK.ENTITY: handle_split,
    TOK.COMPANY: handle_split,
    TOK.S_BEGIN: handle_none,
    TOK.S_END: handle_none,
    TOK.P_BEGIN: handle_none,
    TOK.P_END: handle_none,
    TOK.S_SPLIT: handle_none,
}


def tokens(text: str, pad: bool = True) -> Iterator[str]:
    """ Generate normalized tokens that are suitable for use with Icegrams.
        Optionally pad the token stream at the beginning and end with empty
        strings to make trigram generation more convenient. """
    toklist = list(tokenize(text, convert_measurements=True, replace_html_escapes=True))
    if len(toklist) > 1 and all(t.kind != TOK.UNKNOWN for t in toklist):
        if pad:
            yield ""
            yield ""
        for t in toklist:
            yield from token_dispatch.get(t.kind, handle_other)(t)
        if pad:
            yield ""
            yield ""


def trigrams_from_tokens(iterable: Iterable[str]) -> Iterator[Tuple[Any, ...]]:
    """ Generate trigrams (tuples of three strings) from the given iterable """
    return zip(
        *((islice(seq, i, None) for i, seq in enumerate(tee(iterable, 3))))
    )


def trigrams(text: str) -> Iterator[Tuple[Any, ...]]:
    """ Generate normalized trigrams that are suitable for use with Icegrams. """
    return trigrams_from_tokens(tokens(text, pad=True))


