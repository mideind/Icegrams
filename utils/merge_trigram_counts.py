#!/usr/bin/env python
"""

Icegrams: A trigrams library for Icelandic

utils/merge_trigram_counts.py

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


Merges the per-shard partial trigram counts written by
utils/extract_trigrams.py into one (t1, t2, t3, frequency) .tsv file,
summing counts for trigrams that appear in more than one shard.

This uses the external `sort` command (merge sort with spill-to-disk),
not an in-memory hash map, so it scales to however many distinct
trigrams the full corpus produces without needing a database -- unlike
2019's PostgreSQL upsert table, this never needs more memory than
`sort`'s buffer size regardless of corpus size. The output is already
in the exact 4-column format src/icegrams/ngrams.py's read_tsv expects.

"""

import argparse
import glob
import os
import subprocess


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_glob", help="Glob of *.trigrams.tsv partial count files")
    parser.add_argument("-o", "--output", default="trigrams_final.tsv")
    parser.add_argument(
        "--sort-buffer",
        default="4G",
        help="Memory budget passed to `sort -S` before it spills to disk",
    )
    parser.add_argument("--tmp-dir", default=None, help="Directory for sort's temp files")
    args = parser.parse_args()

    input_files = sorted(glob.glob(args.input_glob))
    if not input_files:
        raise SystemExit(f"No files matched {args.input_glob!r}")
    print(f"Merging {len(input_files)} partial count file(s)...")

    # sort -k1,3 groups identical (t1, t2, t3) keys together without
    # loading everything into memory; a single pass then sums the
    # 4th (count) column across consecutive identical-key lines.
    sort_cmd = ["sort", "-t", "\t", "-k1,1", "-k2,2", "-k3,3", "-S", args.sort_buffer]
    if args.tmp_dir:
        sort_cmd += ["-T", args.tmp_dir]
    sort_cmd += input_files

    with open(args.output, "w", encoding="utf-8") as out:
        # LC_ALL=C makes sort compare raw bytes: under a UTF-8 locale,
        # distinct keys can collate as equal and interleave, splitting one
        # trigram's count across non-adjacent rows (which the single
        # summing pass below would then emit as separate entries).
        sort_env = {**os.environ, "LC_ALL": "C"}
        proc = subprocess.Popen(
            sort_cmd, stdout=subprocess.PIPE, text=True, encoding="utf-8", env=sort_env
        )
        prev_key = None
        prev_count = 0
        n_lines = 0
        n_unique = 0
        for line in proc.stdout:
            n_lines += 1
            t1, t2, t3, count_str = line.rstrip("\n").split("\t")
            key = (t1, t2, t3)
            count = int(count_str)
            if key == prev_key:
                prev_count += count
            else:
                if prev_key is not None:
                    out.write(f"{prev_key[0]}\t{prev_key[1]}\t{prev_key[2]}\t{prev_count}\n")
                    n_unique += 1
                prev_key = key
                prev_count = count
        if prev_key is not None:
            out.write(f"{prev_key[0]}\t{prev_key[1]}\t{prev_key[2]}\t{prev_count}\n")
            n_unique += 1
        ret = proc.wait()
        if ret != 0:
            raise SystemExit(f"sort exited with status {ret}")

    print(f"Read {n_lines:,} partial-count rows, wrote {n_unique:,} unique trigrams to {args.output}")


if __name__ == "__main__":
    main()
