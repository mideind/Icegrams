#!/usr/bin/env python
"""

Icegrams: A trigrams library for Icelandic

pipeline/correction_cache.py

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

Building blocks for the Málfríður correction step: a SQLite cache of
original -> corrected sentences, validation of corrections, and sentence
extraction from converted JSONL documents. Used by
malfridur_api_correct.py.

"""

from typing import Any, Dict, Iterable, List, Sequence, Tuple

import json
import sqlite3
import unicodedata


class CorrectionCache:
    """SQLite-backed original -> corrected sentence cache, shared across
    every correction run past and future."""

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, timeout=60.0)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        # Unconditional: gating this on the db file's prior existence
        # breaks on an empty pre-created file and races when several
        # shard workers start against a fresh path at once.
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS cache "
            "(original TEXT PRIMARY KEY, corrected TEXT NOT NULL)"
        )
        self.conn.commit()

    def bootstrap_from_legacy(self, jsonl_path: str, batch_size: int = 50_000) -> int:
        """One-time import of a pre-existing {"original", "corrected"} cache JSONL file."""
        n = 0
        rows: List[Tuple[str, str]] = []
        with open(jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                original = obj.get("original")
                corrected = obj.get("corrected")
                if original is None or corrected is None:
                    continue
                rows.append((original, corrected))
                if len(rows) >= batch_size:
                    self.conn.executemany(
                        "INSERT OR IGNORE INTO cache (original, corrected) VALUES (?, ?)",
                        rows,
                    )
                    self.conn.commit()
                    n += len(rows)
                    rows.clear()
        if rows:
            self.conn.executemany(
                "INSERT OR IGNORE INTO cache (original, corrected) VALUES (?, ?)", rows
            )
            self.conn.commit()
            n += len(rows)
        return n

    def lookup_many(self, sentences: Sequence[str]) -> Dict[str, str]:
        """Return {original: corrected} for every sentence already cached."""
        found: Dict[str, str] = {}
        # Chunk the IN clause to stay well under SQLite's variable limit
        CHUNK = 500
        cur = self.conn.cursor()
        for i in range(0, len(sentences), CHUNK):
            chunk = sentences[i : i + CHUNK]
            placeholders = ",".join("?" * len(chunk))
            cur.execute(
                f"SELECT original, corrected FROM cache WHERE original IN ({placeholders})",
                chunk,
            )
            for original, corrected in cur.fetchall():
                found[original] = corrected
        return found

    def store_many(self, pairs: Iterable[Tuple[str, str]]) -> None:
        self.conn.executemany(
            "INSERT OR IGNORE INTO cache (original, corrected) VALUES (?, ?)", pairs
        )
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()


# Punctuation/digits Málfríður might introduce as part of a
# legitimate correction (quote-style normalization, dash/ellipsis
# normalization, etc.) -- excluded from the script check below so
# these don't get misread as "a new writing system appeared".
_COMMON_PUNCTUATION = set(" \t\n,.;:!?()[]{}\"'`-–—/\\%°*&@#+=<>_|~²³´µ„“”‘’…")


def _char_script(ch: str) -> str:
    """Rough script classification via the first word of the Unicode
    character name (e.g. "LATIN", "CYRILLIC", "ARMENIAN", "HEBREW") --
    good enough to catch a correction introducing an entirely different
    writing system, without a separate dependency for real script data."""
    if ch in _COMMON_PUNCTUATION or ch.isdigit():
        return "COMMON"
    name = unicodedata.name(ch, "")
    return name.split(" ")[0] if name else "UNKNOWN"


def introduces_new_script(original: str, corrected: str) -> bool:
    """True if `corrected` contains characters from a script that
    wasn't present anywhere in `original` -- verified against a real
    failure when Málfríður mangled an Armenian-script name fragment
    into nonsense Hebrew-range characters. Just a sanity check that
    may catch a few other cases of garbled text."""
    orig_scripts = {_char_script(c) for c in original} - {"COMMON"}
    corr_scripts = {_char_script(c) for c in corrected} - {"COMMON"}
    return bool(corr_scripts - orig_scripts)


def validate_correction(original: str, corrected: str) -> bool:
    if not corrected:
        return False
    if introduces_new_script(original, corrected):
        return False
    lo, hi = 0.5, 1.8
    ratio = len(corrected) / max(1, len(original))
    if ratio < lo or ratio > hi:
        return False
    return True


def extract_sentences(doc: Dict[str, Any]) -> List[str]:
    text = doc["document"]
    spans = doc.get("metadata", {}).get("sentences") or []
    out = []
    for span in spans:
        offset, length = span["offset"], span["length"]
        out.append(text[offset : offset + length])
    return out
