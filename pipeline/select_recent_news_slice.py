#!/usr/bin/env python
"""

Icegrams: A trigrams library for Icelandic

pipeline/select_recent_news_slice.py

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


Draws a word-budgeted slice from the already-converted recent-news
corpus (pipeline/convert_recent_news.py's output), sampling uniformly at
random across the whole 2024-2026 span.

"""

from typing import List

import argparse
import glob
import json
import random


def load_articles(input_glob: str) -> List[dict]:
    articles = []
    for path in sorted(glob.glob(input_glob)):
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    articles.append(json.loads(line))
    return articles


def sample_to_budget(articles: List[dict], target_words: int) -> List[dict]:
    shuffled = articles[:]
    random.shuffle(shuffled)

    selected = []
    total_words = 0
    for article in shuffled:
        if total_words >= target_words:
            break
        selected.append(article)
        total_words += len(article["document"].split())
    return selected


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_glob", help="Glob of convert_recent_news.py output shards")
    parser.add_argument("--target-words", type=int, default=10_000_000)
    parser.add_argument("--output", default="recent_news_slice.jsonl")
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    articles = load_articles(args.input_glob)
    print(f"Loaded {len(articles):,} articles")

    selected = sample_to_budget(articles, args.target_words)
    total_words = sum(len(a["document"].split()) for a in selected)

    year_counts = {}
    for a in selected:
        ts = a.get("metadata", {}).get("publish_timestamp") or ""
        year = ts[:4] if len(ts) >= 4 else "unknown"
        year_counts[year] = year_counts.get(year, 0) + 1

    with open(args.output, "w", encoding="utf-8") as out:
        for a in selected:
            out.write(json.dumps(a, ensure_ascii=False) + "\n")

    print(f"Selected {len(selected):,} articles, {total_words:,} words -> {args.output}")
    print(f"By year: {dict(sorted(year_counts.items()))}")


if __name__ == "__main__":
    main()
