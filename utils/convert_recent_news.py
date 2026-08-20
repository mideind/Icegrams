#!/usr/bin/env python
"""

Icegrams: A trigrams library for Icelandic

utils/convert_recent_news.py

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


Adapts the 2023-2026 "recent news" supplementary corpus (a flat JSONL
of scraped articles, one per line, e.g.:

  {"id": ..., "url": ..., "source_domain": ..., "source_name": ...,
   "title": ..., "byline": ..., "published_at": ..., "authority": ...,
   "num_sentences": ..., "text": "sentence\\nsentence\\n\\nsentence\\n..."}

) into the same shape the IGC-converter produces (a "document" string
plus metadata.sentences offsets), so it can be fed into
utils/malfridur_api_correct.py unchanged, without going through the
TEI-XML conversion step at all -- this source is neither RMH nor
IGC, so utils/select_pilot_corpus.py doesn't apply to it either.

The "text" field is already pre-segmented: one sentence per line,
paragraphs separated by a blank line. That means Tokenizer's
split_into_sentences (used by the IGC-converter for TEI-XML) isn't
needed here -- sentence boundaries can be read directly off the
existing line structure.

"""

from typing import Any, Dict, List, Tuple

import argparse
import glob
import json
import os


def sentence_spans(text: str) -> List[Dict[str, int]]:
    """Return {"offset", "length"} for each non-blank line in text.
    Blank lines are paragraph separators (from "\\n\\n" in the source)
    and are skipped, but still counted for offset bookkeeping so
    positions stay correct."""
    spans = []
    pos = 0
    for line in text.split("\n"):
        if line.strip():
            spans.append({"offset": pos, "length": len(line)})
        pos += len(line) + 1  # +1 for the newline consumed by split()
    return spans


SOFT_HYPHEN = "­"


def convert_article(article: Dict[str, Any]) -> Dict[str, Any]:
    # Soft hyphens (line-wrap hints from the source CMS, mostly visir.is
    # and vb.is headlines) survive verbatim in the scrape and would
    # otherwise split words like "fjöl­skyldu" into spurious tokens.
    title = (article.get("title") or "").strip().replace(SOFT_HYPHEN, "")
    text = (article.get("text") or "").replace(SOFT_HYPHEN, "")
    if title:
        document = title + "\n\n" + text
    else:
        document = text

    return {
        "document": document,
        "uuid": article.get("id"),
        "metadata": {
            "xml_id": article.get("id"),
            "publish_timestamp": article.get("published_at"),
            "source": article.get("url"),
            "source_corpus": "RecentNews",
            "source_domain": article.get("source_domain"),
            "source_name": article.get("source_name"),
            "authority": article.get("authority"),
            "sentences": sentence_spans(document),
        },
    }


def convert_file(input_path: str, output_path: str) -> Tuple[int, int]:
    n_articles = 0
    n_sentences = 0
    tmp_output = output_path + ".tmp"
    with open(input_path, "r", encoding="utf-8") as fin, open(
        tmp_output, "w", encoding="utf-8"
    ) as fout:
        for line in fin:
            line = line.strip()
            if not line:
                continue
            article = json.loads(line)
            doc = convert_article(article)
            n_articles += 1
            n_sentences += len(doc["metadata"]["sentences"])
            fout.write(json.dumps(doc, ensure_ascii=False) + "\n")
    os.replace(tmp_output, output_path)
    return n_articles, n_sentences


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_glob", help="Glob of recent-news JSONL shard files")
    parser.add_argument("--output-dir", default="./converted_recent_news")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    input_files = sorted(glob.glob(args.input_glob))
    print(f"Converting {len(input_files)} shard(s)")

    total_articles = 0
    total_sentences = 0
    for input_path in input_files:
        output_path = os.path.join(
            args.output_dir, os.path.basename(input_path) + ".converted.jsonl"
        )
        n_articles, n_sentences = convert_file(input_path, output_path)
        total_articles += n_articles
        total_sentences += n_sentences
        print(f"{input_path}: {n_articles:,} articles, {n_sentences:,} sentences")

    print(f"\nTotal: {total_articles:,} articles, {total_sentences:,} sentences")


if __name__ == "__main__":
    main()
