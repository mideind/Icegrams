#!/usr/bin/env python
"""

Icegrams: A trigrams library for Icelandic

utils/malfridur_api_correct.py

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


Runs Málfríður grammar correction over the sentences of an IGC-converter
JSONL corpus (see utils/select_pilot_corpus.py and the IGC-converter
under utils/igc_converter_scripts/), at the throughput needed to process
hundreds of millions of sentences. Requires a Málfríður API key. Without
one, the rest of the pipeline can still be run via --skip-correction here,
or extract_trigrams.py --static-word-correction as a fallback.

Design, in three layers:

  1. correction_cache.CorrectionCache: a SQLite-backed original-sentence
     -> corrected-sentence store, grown by every run so no sentence is
     ever sent to the API twice across the whole project. A flat text
     file would force a full linear rescan per lookup; SQLite gives
     O(log n) lookups and lets multiple shard workers share one cache
     file safely (WAL mode).

  2. BatchCorrector: an async client that batches many sentences per
     HTTP call to the Málfríður staging endpoint, runs many calls
     concurrently (bounded by a semaphore), retries transient failures
     with backoff, and validates each result (see correction_cache.py)
     before accepting it -- falling back to the original sentence
     otherwise. Sentences are grouped into batches by byte length before
     sending, since the underlying model pads every item in a batch to
     the longest member (server.py: padding="longest"): mixing very
     short and very long sentences in one batch wastes GPU time on
     padding, so batches are filled from within narrow length bands.

  3. process_shard(): drives one shard (one IGC-converter JSONL file) of
     documents through cache lookup -> batch correction -> validation,
     and writes ONE OUTPUT LINE PER SENTENCE (not a reconstructed
     document) with full provenance. A small per-shard state file makes
     reruns resumable: a shard already marked done is skipped outright.

Byte-length limit: the Málfríður model is byte-level (ByT5-style) with
max_length=512 (model_servers/malfridur/server.py); anything longer is
silently truncated by the tokenizer. Sentences over MAX_SENTENCE_BYTES
are therefore never sent to the API -- they pass through uncorrected,
flagged as "too_long" in the output, so the omission is visible rather
than silently baked into a truncated correction.

"""

from typing import Dict, Iterator, List, Optional, Sequence, Tuple

import argparse
import asyncio
import glob
import json
import os
import time

import httpx

from correction_cache import CorrectionCache, extract_sentences, validate_correction


PRODUCTION_API_URL = "https://api.mideind.is/grammar_nn/"
STAGING_API_URL = "https://staging.api.mideind.is/grammar_nn/"
# The API key has been seen under several names in this codebase's history
# (text_processor.py uses MALSTADUR_STAGING_KEY; the icegrams/.env file
# has both MALSTADUR_API_KEY for production and MALSTADUR_STAGING_API_KEY
# for staging) -- accept any of them, staging key checked first since
# staging is the intended target for bulk correction.
API_KEY_ENVS = ("MALSTADUR_STAGING_API_KEY", "MALSTADUR_STAGING_KEY", "MALSTADUR_API_KEY")

# Safety margin under the model's 512-byte max_length (byte-level tokenizer)
MAX_SENTENCE_BYTES = 480


def length_bucketed_batches(
    sentences: Sequence[str], batch_size: int
) -> Iterator[List[int]]:
    """Yield index batches, ordered by sentence byte length, so that each
    HTTP request pads to a length close to its own members rather than to
    whatever the longest sentence anywhere in the shard happens to be."""
    order = sorted(range(len(sentences)), key=lambda i: len(sentences[i]))
    for i in range(0, len(order), batch_size):
        yield order[i : i + batch_size]


class BatchCorrector:
    def __init__(
        self,
        api_key: str,
        api_url: str = STAGING_API_URL,
        concurrency: int = 8,
        batch_size: int = 16,
        timeout: float = 50.0,
        max_retries: int = 4,
    ) -> None:
        self.api_key = api_key
        self.api_url = api_url
        self.batch_size = batch_size
        self.max_retries = max_retries
        self.semaphore = asyncio.Semaphore(concurrency)
        self.client = httpx.AsyncClient(timeout=timeout)
        self.calls = 0
        self.sentences_sent = 0
        self.bytes_sent = 0

    async def close(self) -> None:
        await self.client.aclose()

    async def _post_batch(self, batch: List[str]) -> Optional[List[str]]:
        """Returns the corrected batch, or None if the batch could not
        be corrected (exhausted retries or a non-retryable error). None
        rather than the originals: a failure must stay distinguishable
        from "the API said no change", or it would end up cached as a
        permanent identity correction."""
        headers = {
            "X-API-Key": self.api_key,
            "accept": "application/json",
            "Content-Type": "application/json",
        }
        payload = {"text": batch, "diff_entity": "none"}
        delay = 1.0
        for attempt in range(self.max_retries):
            try:
                async with self.semaphore:
                    resp = await self.client.post(self.api_url, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                results = data.get("results") or []
                out = []
                for i, original in enumerate(batch):
                    if i < len(results) and results[i].get("changed_text"):
                        out.append(results[i]["changed_text"])
                    else:
                        out.append(original)
                self.calls += 1
                self.sentences_sent += len(batch)
                self.bytes_sent += sum(len(s.encode("utf-8")) for s in batch)
                return out
            except httpx.HTTPStatusError as ex:
                status = ex.response.status_code
                if status != 429 and status < 500:
                    # Non-retryable client error (bad/expired key, bad request, etc.)
                    print(f"Malfridur batch failed (HTTP {status}, not retrying): {ex}")
                    return None
                if attempt == self.max_retries - 1:
                    print(f"Malfridur batch failed after retries: {ex}")
                    return None
                await asyncio.sleep(delay)
                delay *= 2
            except (httpx.HTTPError, ValueError) as ex:
                if attempt == self.max_retries - 1:
                    print(f"Malfridur batch failed after retries: {ex}")
                    return None
                await asyncio.sleep(delay)
                delay *= 2
        return None

    async def correct(self, sentences: Sequence[str]) -> List[Optional[str]]:
        """Correct a list of sentences, internally length-bucketed and
        batched, with many batches in flight at once. Positions whose
        batch failed are None -- the caller must treat those as
        uncorrected and must not cache them."""
        if not sentences:
            return []
        results: List[Optional[str]] = [None] * len(sentences)
        tasks = []
        for idx_batch in length_bucketed_batches(sentences, self.batch_size):
            batch_text = [sentences[i] for i in idx_batch]
            tasks.append((idx_batch, asyncio.create_task(self._post_batch(batch_text))))
        for idx_batch, task in tasks:
            corrected_batch = await task
            if corrected_batch is None:
                continue
            for i, corrected in zip(idx_batch, corrected_batch):
                results[i] = corrected
        return results


def shard_state_path(output_path: str) -> str:
    return output_path + ".done"


async def process_shard(
    input_path: str,
    output_path: str,
    cache: CorrectionCache,
    corrector: Optional[BatchCorrector],
    cache_only: bool = False,
) -> Tuple[int, int]:
    """corrector=None, cache_only=False runs in skip-correction mode:
    every sentence passes through unchanged (status "skipped"), no
    cache lookups and no API calls at all. This is for end-to-end
    pipeline tests (corpus selection -> conversion -> trigram
    extraction -> compression) that don't want to wait on or consume
    Malfridur capacity.

    cache_only=True looks sentences up in the cache (e.g. one already
    populated from a colleague's externally-run corrections) but never
    calls the API for a miss -- those pass through unchanged with
    status "not_cached", rather than requiring an API key that this
    mode has no use for.

    Returns (unique_sentences, cache_hits) for this shard, both 0 in
    skip-correction mode."""
    if os.path.exists(shard_state_path(output_path)):
        print(f"Skipping {input_path} (already done)")
        return 0, 0

    docs = []
    with open(input_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                docs.append(json.loads(line))

    all_sentences: List[str] = []
    doc_sentence_ranges: List[Tuple[int, int]] = []
    for doc in docs:
        sents = extract_sentences(doc)
        start = len(all_sentences)
        all_sentences.extend(sents)
        doc_sentence_ranges.append((start, len(all_sentences)))

    n_unique = 0
    n_cache_hits = 0
    not_cached: set = set()
    api_failed: set = set()
    if corrector is None and not cache_only:
        corrected_map: Dict[str, str] = {}
        too_long: set = set()
    elif cache_only:
        unique_sentences = list(dict.fromkeys(all_sentences))
        corrected_map = cache.lookup_many(unique_sentences)
        n_unique = len(unique_sentences)
        n_cache_hits = len(corrected_map)
        not_cached = set(unique_sentences) - set(corrected_map)
        too_long = set()
        print(
            f"{input_path}: {n_cache_hits:,}/{n_unique:,} unique sentences "
            f"served from cache ({100 * n_cache_hits / max(n_unique, 1):.1f}%)"
        )
    else:
        unique_sentences = list(dict.fromkeys(all_sentences))
        cached = cache.lookup_many(unique_sentences)
        n_unique = len(unique_sentences)
        n_cache_hits = len(cached)
        print(
            f"{input_path}: {n_cache_hits:,}/{n_unique:,} unique sentences "
            f"served from cache ({100 * n_cache_hits / max(n_unique, 1):.1f}%)"
        )

        to_correct = []
        too_long = set()
        for s in unique_sentences:
            if s in cached:
                continue
            if len(s.encode("utf-8")) > MAX_SENTENCE_BYTES:
                too_long.add(s)
                continue
            to_correct.append(s)

        t0 = time.time()
        corrected_list = await corrector.correct(to_correct)
        elapsed = time.time() - t0
        if to_correct:
            rate = sum(len(s) for s in to_correct) / max(elapsed, 1e-6)
            print(
                f"{input_path}: corrected {len(to_correct):,} new sentences "
                f"in {elapsed:.1f}s ({rate:,.0f} chars/s)"
            )

        corrected_map = dict(cached)
        new_cache_entries = []
        for original, corrected in zip(to_correct, corrected_list):
            if corrected is None:
                # Batch failed at the API: pass the sentence through
                # unchanged but never cache it, so a later run retries it
                api_failed.add(original)
                corrected_map[original] = original
            elif validate_correction(original, corrected):
                corrected_map[original] = corrected
                new_cache_entries.append((original, corrected))
            else:
                corrected_map[original] = original
        cache.store_many(new_cache_entries)
        if api_failed:
            print(
                f"{input_path}: {len(api_failed):,} sentence(s) failed at the "
                "API and were not cached -- rerun this shard to retry them"
            )

    tmp_output = output_path + ".tmp"
    with open(tmp_output, "w", encoding="utf-8") as out:
        for doc, (start, end) in zip(docs, doc_sentence_ranges):
            meta = doc.get("metadata", {})
            for sent_idx, original in enumerate(all_sentences[start:end]):
                if corrector is None and not cache_only:
                    corrected = original
                    status = "skipped"
                elif original in too_long:
                    corrected = original
                    status = "too_long"
                elif original in not_cached:
                    corrected = original
                    status = "not_cached"
                elif original in api_failed:
                    corrected = original
                    status = "api_failed"
                else:
                    corrected = corrected_map.get(original, original)
                    status = "corrected" if corrected != original else "unchanged"
                out.write(
                    json.dumps(
                        {
                            "doc_uuid": doc.get("uuid"),
                            "xml_id": meta.get("xml_id"),
                            "sent_idx": sent_idx,
                            "original": original,
                            "corrected": corrected,
                            "status": status,
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
    os.replace(tmp_output, output_path)
    if api_failed:
        # No .done marker: the shard's output is kept, but the next run
        # redoes it (cheaply, via the cache) instead of permanently
        # baking the failures in as if they had been corrected.
        print(
            f"{input_path}: no .done marker written ({len(api_failed):,} "
            "API failure(s)) -- shard will be retried on the next run"
        )
    else:
        with open(shard_state_path(output_path), "w") as f:
            f.write("done\n")
    return n_unique, n_cache_hits


async def run(args: argparse.Namespace) -> None:
    cache = CorrectionCache(args.cache_db)
    if args.bootstrap_cache:
        print(f"Bootstrapping cache from {args.bootstrap_cache}...")
        n = cache.bootstrap_from_legacy(args.bootstrap_cache)
        print(f"Imported {n:,} legacy cache entries")

    corrector: Optional[BatchCorrector] = None
    if not args.skip_correction and not args.cache_only:
        api_key = args.api_key
        if not api_key:
            for env_name in API_KEY_ENVS:
                api_key = os.getenv(env_name)
                if api_key:
                    break
        if not api_key:
            raise SystemExit(f"No API key: set one of {API_KEY_ENVS} or pass --api-key")

        corrector = BatchCorrector(
            api_key=api_key,
            api_url=args.api_url,
            concurrency=args.concurrency,
            batch_size=args.batch_size,
        )

    input_files = sorted(glob.glob(args.input_glob))
    os.makedirs(args.output_dir, exist_ok=True)
    mode = " (cache-only mode)" if args.cache_only else (" (skip-correction mode)" if corrector is None else "")
    print(f"Processing {len(input_files)} shard(s){mode}")

    total_unique = 0
    total_cache_hits = 0
    try:
        for input_path in input_files:
            output_path = os.path.join(
                args.output_dir, os.path.basename(input_path) + ".corrected.jsonl"
            )
            n_unique, n_cache_hits = await process_shard(
                input_path, output_path, cache, corrector, cache_only=args.cache_only
            )
            total_unique += n_unique
            total_cache_hits += n_cache_hits
    finally:
        if corrector is not None:
            await corrector.close()
        cache.close()

    if corrector is not None or args.cache_only:
        print(
            f"Total cache hits: {total_cache_hits:,}/{total_unique:,} unique sentences "
            f"({100 * total_cache_hits / max(total_unique, 1):.1f}%)"
        )
    if corrector is not None:
        print(
            f"Total API calls: {corrector.calls:,}, "
            f"sentences sent: {corrector.sentences_sent:,}, "
            f"bytes sent: {corrector.bytes_sent:,}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_glob", help="Glob of IGC-converter JSONL shard files")
    parser.add_argument("--output-dir", default="./malfridur_output")
    parser.add_argument("--cache-db", default="./malfridur_cache.sqlite3")
    parser.add_argument(
        "--bootstrap-cache",
        default=None,
        help="One-time import from a legacy cache.jsonl ({\"original\": ..., \"corrected\": ...} per line)",
    )
    parser.add_argument("--api-key", default=None)
    parser.add_argument(
        "--api-url",
        default=STAGING_API_URL,
        help=f"default {STAGING_API_URL}; production is {PRODUCTION_API_URL}",
    )
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument(
        "--skip-correction",
        action="store_true",
        help="Pass every sentence through unchanged, no API calls or cache lookups -- for end-to-end pipeline tests",
    )
    parser.add_argument(
        "--cache-only",
        action="store_true",
        help="Use the cache only, never call the API -- a miss passes through unchanged (status not_cached)",
    )
    args = parser.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
