#!/usr/bin/env python
"""

Icegrams: A trigrams library for Icelandic

pipeline/extract_trigrams.py

Copyright (C) 2019-2026 Miðeind ehf

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


This utility replaces the tokenize-and-count stage of 2019's rmh.py
(see git history) for the new pipeline.
Two things changed from 2019:

  1. Spelling/amalgam correction now happens upstream, sentence by
     sentence, via Málfríður (pipeline/malfridur_api_correct.py).

  2. Trigram counting no longer goes through PostgreSQL upserts, which
     do not scale to this corpus size (one round trip per trigram
     occurrence). Instead each shard is counted independently in memory
     with collections.Counter and flushed to a partial (t1, t2, t3,
     count) TSV file. pipeline/merge_trigram_counts.py then merges the
     partials into one (t1, t2, t3, total_count) TSV.

Input: the sentence-level JSONL shards written by malfridur_api_correct.py
(one line per sentence: doc_uuid, xml_id, sent_idx, corrected, status).
Each sentence is tokenized independently -- this matches 2019's
behaviour, since Tokenizer.tokenize() already treats each sentence as
its own bounded unit (wrapped in blank strings at S_BEGIN/S_END), so a
trigram window never needs to see more than one sentence at a time.

"""

from typing import Any, Callable, Dict, Iterator, List, Set, Tuple

import argparse
import collections
import glob
import json
import os
from itertools import islice, tee

from tokenizer import tokenize, Tok, TOK


# 2019's static word-list correction (correct.txt/delete.txt/split.txt),
# loaded from static_corrections/ next to this script.
# Off by default (correction now normally happens upstream via Málfríður,
# or not at all in --skip-correction test runs) -- enable with
# --static-word-correction for a quick, local, no-API correction.
STATIC_CORRECTION_RESOURCES = os.path.join(
    os.path.dirname(os.path.realpath(__file__)), "static_corrections"
)
STATIC_CORRECTION_ENABLED = False
CHANGING: Set[str] = set()
REPLACING: Dict[str, str] = {}
DELETING: Set[str] = set()
DOUBLING: Dict[str, List[str]] = {}


def load_static_corrections(resources_dir: str = STATIC_CORRECTION_RESOURCES) -> None:
    with open(os.path.join(resources_dir, "correct.txt"), "r", encoding="utf-8") as f:
        for line in f:
            key, val = line.strip().split("\t")
            REPLACING[key] = val
            CHANGING.add(key)
    with open(os.path.join(resources_dir, "delete.txt"), "r", encoding="utf-8") as f:
        for line in f:
            key = line.strip()
            DELETING.add(key)
            CHANGING.add(key)
    with open(os.path.join(resources_dir, "split.txt"), "r", encoding="utf-8") as f:
        for line in f:
            key, val = line.strip().split("\t")
            val = val.strip()
            DOUBLING[key] = val.split()
            CHANGING.add(key)
            if key.islower() and val.islower():
                key_cap, val_cap = key.capitalize(), val.capitalize()
                DOUBLING[key_cap] = val_cap.split()
                CHANGING.add(key_cap)


def handle_word(token: Tok) -> Iterator[str]:
    """Return the text of a word token, after 2019's static word-list
    correction if --static-word-correction is enabled; otherwise a plain
    passthrough (correction happens upstream via Málfríður instead, or
    not at all in a --skip-correction test run)."""
    t = token.txt
    if STATIC_CORRECTION_ENABLED and t in CHANGING:
        if t in REPLACING:
            yield REPLACING[t]
        elif t in DELETING:
            pass
        elif t in DOUBLING:
            yield from DOUBLING[t]
        else:
            assert False
    elif " " in t:
        yield from t.split()
    else:
        yield t


def handle_punctuation(token: Tok) -> Iterator[str]:
    yield token.val[1]


def handle_passthrough(token: Tok) -> Iterator[str]:
    yield token.txt


def handle_split(token: Tok) -> Iterator[str]:
    yield from token.txt.split()


def handle_measurement(token: Tok) -> Iterator[str]:
    yield from ("[NUMBER]", token.val[0])


def handle_none(token: Tok) -> Iterator[str]:
    yield from ()


def handle_other(token: Tok) -> Iterator[str]:
    yield "[" + TOK.descr[token.kind] + "]"


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


def tokens(text: str) -> Iterator[str]:
    toklist = list(tokenize(text, convert_measurements=True, replace_html_escapes=True))
    if len(toklist) > 1 and all(t.kind != TOK.UNKNOWN for t in toklist):
        yield ""
        yield ""
        for t in toklist:
            yield from token_dispatch.get(t.kind, handle_other)(t)
        yield ""
        yield ""


def trigrams(iterable) -> Iterator[Tuple[Any, ...]]:
    return zip(*((islice(seq, i, None) for i, seq in enumerate(tee(iterable, 3)))))


def count_trigrams(text: str, counter: "collections.Counter[Tuple[str, str, str]]") -> int:
    n = 0
    for tg in trigrams(tokens(text)):
        if any(tg):
            counter[tg] += 1
            n += 1
    return n


def process_shard(input_path: str, output_path: str) -> Tuple[int, int]:
    """Count trigrams for one malfridur_api_correct.py output shard. Returns
    (sentences processed, trigram occurrences counted)."""
    counter: "collections.Counter[Tuple[str, str, str]]" = collections.Counter()
    n_sentences = 0
    n_trigrams = 0
    with open(input_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            text = row.get("corrected") or row.get("original")
            if not text:
                continue
            n_sentences += 1
            n_trigrams += count_trigrams(text, counter)

    tmp_output = output_path + ".tmp"
    with open(tmp_output, "w", encoding="utf-8") as out:
        for (t1, t2, t3), count in counter.items():
            out.write(f"{t1}\t{t2}\t{t3}\t{count}\n")
    os.replace(tmp_output, output_path)
    return n_sentences, n_trigrams


def shard_state_path(output_path: str) -> str:
    return output_path + ".done"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_glob", help="Glob of malfridur_api_correct.py output JSONL shards")
    parser.add_argument("--output-dir", default="./trigram_counts")
    parser.add_argument(
        "--static-word-correction",
        action="store_true",
        help="Apply static correct.txt/delete.txt/split.txt word-list correction "
        "(local, no API) instead of a plain passthrough",
    )
    args = parser.parse_args()

    if args.static_word_correction:
        global STATIC_CORRECTION_ENABLED
        STATIC_CORRECTION_ENABLED = True
        load_static_corrections()
        print(f"Loaded static word corrections: {len(REPLACING)} replace, {len(DELETING)} delete, {len(DOUBLING)} split")

    os.makedirs(args.output_dir, exist_ok=True)
    input_files = sorted(glob.glob(args.input_glob))
    print(f"Processing {len(input_files)} shard(s)")

    total_sentences = 0
    total_trigrams = 0
    for input_path in input_files:
        output_path = os.path.join(args.output_dir, os.path.basename(input_path) + ".trigrams.tsv")
        if os.path.exists(shard_state_path(output_path)):
            print(f"Skipping {input_path} (already done)")
            continue
        n_sentences, n_trigrams = process_shard(input_path, output_path)
        with open(shard_state_path(output_path), "w") as f:
            f.write("done\n")
        total_sentences += n_sentences
        total_trigrams += n_trigrams
        print(f"{input_path}: {n_sentences:,} sentences, {n_trigrams:,} trigram occurrences")

    print(f"\nTotal: {total_sentences:,} sentences, {total_trigrams:,} trigram occurrences")

    # The merge step globs *.trigrams.tsv from the output dir, so partial
    # counts left over from a different run would be silently summed into
    # the final counts -- warn if any such files are present. (Best
    # practice: use a fresh --output-dir per run.)
    expected = {
        os.path.join(args.output_dir, os.path.basename(p) + ".trigrams.tsv")
        for p in input_files
    }
    strays = sorted(
        set(glob.glob(os.path.join(args.output_dir, "*.trigrams.tsv"))) - expected
    )
    if strays:
        print(
            f"\nWARNING: {len(strays)} partial-count file(s) in {args.output_dir} "
            "do not belong to this run's input set and WOULD be included by the "
            "merge glob below -- delete them or use a fresh output dir:"
        )
        for stray in strays[:10]:
            print(f"  {stray}")
        if len(strays) > 10:
            print(f"  ... and {len(strays) - 10} more")

    print(
        "\nNext step -- merge all partial counts into the final "
        "(t1, t2, t3, frequency) .tsv that ngrams.py's compressor expects:\n"
        f"  python3 pipeline/merge_trigram_counts.py '{args.output_dir}/*.trigrams.tsv' "
        "-o trigrams_final.tsv"
    )


if __name__ == "__main__":
    main()
