#!/usr/bin/env python3
"""

Icegrams: A trigrams library for Icelandic

tools/upgrade_model.py

Copyright (C) 2026 Miðeind ehf.

This software is licensed under the MIT License (see LICENSE.txt).


Converts a trigrams.bin model file in format 1 (the format of the
model-2026.08 release and earlier, with a gzip-compressed vocabulary)
to the current format, which stores the vocabulary uncompressed so that
it is memory-mapped along with the rest of the file:

    python tools/upgrade_model.py SRC DEST

SRC defaults to the model that icegrams finds (see model.py). Only the
vocabulary section, the last one in the file, is rewritten. The script
then checks that DEST gives the same word for every unigram id as SRC,
and prints the size and SHA-256 of DEST, for model.py.

It needs an environment with icegrams installed, e.g. the dev
environment (uv run python tools/upgrade_model.py ...).

"""

import argparse
import hashlib
import os
import time

from icegrams.model import model_filename
from icegrams.ngrams import NgramStorage, to_str, upgrade_model_file


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert a format 1 trigrams.bin to the current format"
    )
    parser.add_argument("src", nargs="?", help="the model to convert")
    parser.add_argument("dest", help="the file to write")
    args = parser.parse_args()
    src = args.src or model_filename()

    t0 = time.time()
    upgrade_model_file(src, args.dest)
    print("Wrote {0} in {1:.1f} s".format(args.dest, time.time() - t0))

    old = NgramStorage()
    old.load(src)
    new = NgramStorage()
    new.load(args.dest)
    assert old._compressed_vocab is not None
    words = old._compressed_vocab[:-1].split(b"\x00")
    assert new._vocab_count == len(words), (new._vocab_count, len(words))
    for i, w in enumerate(words):
        if new.id_to_word(i) != to_str(w):
            raise SystemExit("Error: word {0} differs".format(i))
    old.close()
    new.close()
    print("All {0:,} words are the same".format(len(words)))

    print("{0}: {1:,} -> {2:,} bytes".format(
        src, os.path.getsize(src), os.path.getsize(args.dest)))
    print("MODEL_SIZE = {0}".format(os.path.getsize(args.dest)))
    print('MODEL_SHA256 = "{0}"'.format(sha256(args.dest)))


if __name__ == "__main__":
    main()
