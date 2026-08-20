#!/usr/bin/env python
"""

Icegrams: A trigrams library for Icelandic

utils/convert_selected_igc.py

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


Converts an arbitrary list of selected IGC TEI-XML files -- e.g. the
output of utils/select_pilot_corpus.py -- into sharded JSONL in the
same document/metadata.sentences shape utils/malfridur_api_correct.py
consumes.

This is needed because Þórunn's IGC-converter (convert_IGC.py) only
knows how to convert an entire subcorpus directory at once (it walks
every site/year/file under a subcorpus root itself); it has no notion
of "convert just these N files out of the corpus". The per-file
conversion logic it's built on (XMLToJsonlConverter.convert_to_jsonl)
already takes a single file path, though, so this script reuses that
directly and does the file-list iteration and sharding itself, instead
of duplicating any TEI-parsing logic.

"""

from typing import Dict, List, Optional

import argparse
import hashlib
import json
import os
import re
import sys

# Local copy of Thorunn's scripts/convert_xml.py (see igc_converter_scripts/),
# copied once into this repo rather than importing live from her scratch
# directory on every run.
_UTILS_DIR = os.path.dirname(os.path.realpath(__file__))
if _UTILS_DIR not in sys.path:
    sys.path.insert(0, _UTILS_DIR)

from igc_converter_scripts import XMLToJsonlConverter  # noqa: E402


# Subcorpora XMLToJsonlConverter knows how to parse (see its
# PARAGRAPH_TYPES/TITLE_TYPES dicts) -- used both to validate a corpus
# name and, via the IGC-<name>- pattern, to infer it from a file path.
KNOWN_CORPORA = ["Adjud", "Books", "Journals", "Law", "News1", "News2", "Parla", "Social", "Wiki"]
CORPUS_PATTERN = re.compile(r"IGC-(" + "|".join(KNOWN_CORPORA) + r")-")


def infer_corpus(path: str) -> Optional[str]:
    match = CORPUS_PATTERN.search(path)
    return match.group(1) if match else None


def read_file_list(path: str) -> List[str]:
    with open(path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def shard_state_path(shard_path: str) -> str:
    return shard_path + ".done"


def shard_fingerprint(shard_files: List[str]) -> str:
    """Identity of a shard's actual contents. The .done marker records
    this, so resuming against a regenerated file list (where the same
    shard index now holds different files) reconverts instead of
    wrongly skipping."""
    return hashlib.sha256("\n".join(shard_files).encode("utf-8")).hexdigest()


def convert_files(
    file_list: List[str], output_dir: str, shard_size: int
) -> None:
    os.makedirs(output_dir, exist_ok=True)
    converters: Dict[str, XMLToJsonlConverter] = {}

    n_shards = (len(file_list) + shard_size - 1) // shard_size
    n_converted = 0
    n_failed = 0
    n_unknown_corpus = 0

    for shard_idx in range(n_shards):
        shard_files = file_list[shard_idx * shard_size : (shard_idx + 1) * shard_size]
        shard_path = os.path.join(output_dir, f"shard_{shard_idx:05d}.jsonl")

        fingerprint = shard_fingerprint(shard_files)
        marker_path = shard_state_path(shard_path)
        if os.path.exists(marker_path):
            try:
                with open(marker_path, "r", encoding="utf-8") as f:
                    recorded = json.load(f).get("files_sha256")
            except (json.JSONDecodeError, UnicodeDecodeError):
                recorded = None
            if recorded == fingerprint:
                print(f"Skipping shard {shard_idx} (already done)")
                continue
            print(
                f"Shard {shard_idx}: existing marker does not match the current "
                "file list (regenerated selection, or a pre-fingerprint marker) "
                "-- reconverting"
            )

        shard_failures = 0
        tmp_path = shard_path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as out:
            for path in shard_files:
                corpus = infer_corpus(path)
                if corpus is None:
                    n_unknown_corpus += 1
                    shard_failures += 1
                    print(f"Could not infer corpus for {path}, skipping")
                    continue

                converter = converters.get(corpus)
                if converter is None:
                    converter = XMLToJsonlConverter(corpus, "", "")
                    converters[corpus] = converter

                try:
                    doc = converter.convert_to_jsonl(path)
                except Exception as ex:
                    n_failed += 1
                    shard_failures += 1
                    print(f"Failed to convert {path}: {ex}")
                    continue

                out.write(json.dumps(doc, ensure_ascii=False) + "\n")
                n_converted += 1

        os.replace(tmp_path, shard_path)
        if shard_failures == 0:
            with open(marker_path, "w", encoding="utf-8") as f:
                json.dump(
                    {"files_sha256": fingerprint, "n_files": len(shard_files)},
                    f,
                    ensure_ascii=False,
                )
                f.write("\n")
            print(f"Shard {shard_idx}: wrote {len(shard_files)} candidate documents -> {shard_path}")
        else:
            # No marker: the shard's output is kept, but the next run
            # retries it instead of permanently baking in the failures.
            print(
                f"Shard {shard_idx}: {shard_failures} file(s) failed or were "
                f"skipped -> {shard_path} -- no .done marker written, shard "
                "will be reconverted on the next run"
            )

    print(
        f"\nConverted {n_converted:,} documents, "
        f"{n_failed:,} failed, {n_unknown_corpus:,} had unrecognized corpus"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file_list", help="Text file of TEI-XML paths, one per line")
    parser.add_argument("--output-dir", default="./converted_selected")
    parser.add_argument("--shard-size", type=int, default=5000, help="Documents per output shard")
    args = parser.parse_args()

    file_list = read_file_list(args.file_list)
    print(f"Converting {len(file_list):,} files from {args.file_list}")
    convert_files(file_list, args.output_dir, args.shard_size)


if __name__ == "__main__":
    main()
