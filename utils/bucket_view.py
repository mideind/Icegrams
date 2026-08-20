#!/usr/bin/env python
"""

Icegrams: A trigrams library for Icelandic

utils/bucket_view.py

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


This replaces the ad hoc SQL bucket-view analysis from the 2019 model
(doc/overview.md, step 5-6). It reads
the final merged (t1, t2, t3, frequency) .tsv from
utils/merge_trigram_counts.py and does two things in one pass:

  1. Prints a bucket view: for each frequency lower bound, how many
     distinct trigrams fall in that bucket, as a percentage of all
     distinct trigrams, cumulatively -- plus, unlike 2019's table, the
     cumulative share of total trigram OCCURRENCES retained at each
     cutoff (2019 quoted this figure prose-side for their chosen
     cutoff; here it's given for every candidate cutoff so the decision
     is data-driven instead of a one-off calculation).

  2. Given one or more --cutoff values, writes one filtered .tsv per
     cutoff (trigrams with frequency >= cutoff), each already in the
     4-column format src/icegrams/ngrams.py's compressor expects. This
     is how the small/fast and big models are both derived from a
     single corrected-and-counted corpus: same input file, two cutoffs,
     two output .tsv files, no separate pipeline run needed.

"""

from typing import List

import argparse


# Same bucket boundaries as the 2019 model's published bucket view
# (doc/overview.md), so a new run's table is directly comparable.
DEFAULT_BOUNDS = [1, 2, 3, 4, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000]


def bucket_view(input_path: str, bounds: List[int]) -> None:
    bounds = sorted(set(bounds))
    # counts[i] = number of distinct trigrams with bounds[i] <= freq < bounds[i+1]
    bucket_unique = [0] * len(bounds)
    bucket_occurrences = [0] * len(bounds)
    total_unique = 0
    total_occurrences = 0

    with open(input_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line:
                continue
            freq = int(line.rsplit("\t", 1)[1])
            total_unique += 1
            total_occurrences += freq
            # Find the highest bound <= freq (bisect from the top since
            # most trigrams are low-frequency and hit an early bucket)
            for i in range(len(bounds) - 1, -1, -1):
                if freq >= bounds[i]:
                    bucket_unique[i] += 1
                    bucket_occurrences[i] += freq
                    break

    print(f"{'lowbound':>10}{'cnt':>14}{'perc':>8}{'cum_cnt':>14}{'cum_perc':>9}{'cum_occ_perc':>14}")
    cum_cnt = 0
    cum_occ = 0
    # Print from the highest bucket down, matching 2019's table order
    for i in range(len(bounds) - 1, -1, -1):
        cum_cnt += bucket_unique[i]
        cum_occ += bucket_occurrences[i]
        cum_perc = 100 * cum_cnt / total_unique if total_unique else 0.0
        cum_occ_perc = 100 * cum_occ / total_occurrences if total_occurrences else 0.0
        perc = 100 * bucket_unique[i] / total_unique if total_unique else 0.0
        print(
            f"{bounds[i]:>10}{bucket_unique[i]:>14,}{perc:>7.2f}%"
            f"{cum_cnt:>14,}{cum_perc:>8.2f}%{cum_occ_perc:>13.2f}%"
        )

    print(f"\nTotal distinct trigrams: {total_unique:,}")
    print(f"Total trigram occurrences: {total_occurrences:,}")


def export_cutoff(input_path: str, cutoff: int, output_path: str) -> None:
    kept = 0
    total = 0
    kept_occurrences = 0
    total_occurrences = 0
    with open(input_path, "r", encoding="utf-8") as fin, open(
        output_path, "w", encoding="utf-8"
    ) as fout:
        for line in fin:
            stripped = line.rstrip("\n")
            if not stripped:
                continue
            freq = int(stripped.rsplit("\t", 1)[1])
            total += 1
            total_occurrences += freq
            if freq >= cutoff:
                fout.write(line if line.endswith("\n") else line + "\n")
                kept += 1
                kept_occurrences += freq
    pct_unique = 100 * kept / total if total else 0.0
    pct_occ = 100 * kept_occurrences / total_occurrences if total_occurrences else 0.0
    print(
        f"cutoff={cutoff}: kept {kept:,}/{total:,} distinct trigrams ({pct_unique:.2f}%), "
        f"covering {kept_occurrences:,}/{total_occurrences:,} occurrences ({pct_occ:.2f}%) "
        f"-> {output_path}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="Final merged (t1, t2, t3, frequency) .tsv")
    parser.add_argument(
        "--bounds",
        default=",".join(str(b) for b in DEFAULT_BOUNDS),
        help="Comma-separated bucket lower bounds for the bucket view",
    )
    parser.add_argument(
        "--cutoff",
        action="append",
        type=int,
        default=[],
        metavar="FREQ",
        help="Export a filtered .tsv keeping trigrams with frequency >= FREQ (repeatable)",
    )
    parser.add_argument(
        "--output-template",
        default="trigrams_cutoff{cutoff}.tsv",
        help="Output filename template, {cutoff} is replaced with the cutoff value",
    )
    args = parser.parse_args()

    bounds = [int(b) for b in args.bounds.split(",") if b.strip()]
    bucket_view(args.input, bounds)

    for cutoff in args.cutoff:
        output_path = args.output_template.format(cutoff=cutoff)
        print()
        export_cutoff(args.input, cutoff, output_path)


if __name__ == "__main__":
    main()
