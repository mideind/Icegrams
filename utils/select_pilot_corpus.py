#!/usr/bin/env python
"""

Icegrams: A trigrams library for Icelandic

utils/select_pilot_corpus.py

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


This utility selects a pilot sample of source documents from a raw,
unconverted IGC (Icelandic Gigaword Corpus) TEI-XML tree, following
the same general methodology as the 2019 Icegrams trigram model
(see doc/overview.md), adapted for IGC-2022:

  - Documents from before a cutoff year (default 1980) are dropped.
  - Documents from a fixed exclusion list of low-quality sites are
    dropped -- 433.is, fotbolti.net, bleikt.is, eyjan.is, pressan.is.
  - For years where both mbl.is and Morgunblaðið (web and print
    versions of the same newspaper) are present, the mbl.is copy for
    that year is dropped to reduce duplicate-content risk. The same is
    done for Kjarninn, Fréttatíminn, Stundin and Bændablaðið.
  - IGC-Social is excluded by default.
  - The remaining pool is sampled at the (subcorpus, site, year)
    "collection" level -- mirroring the 2019 selection granularity --
    using weighted-without-replacement sampling biased toward more
    recent years, until a target word budget is reached.

This script only reads TEI headers (word count, site, year) to build
a manifest; it does not extract document bodies. A later stage feeds
the selected file list into the IGC-converter and, from there, into
Málfríður correction and trigram extraction.

"""

from typing import Any, Dict, Iterator, List, Optional, Tuple

import argparse
import json
import os
import random
import sys
import xml.etree.ElementTree as ET


XML_NS = "{http://www.tei-c.org/ns/1.0}"

# Directory-nesting type for each subcorpus, taken from
# Þórunn's IGC-converter (convert_IGC.py: `corpus_types`), since the
# manifest walk has to match the same on-disk layout the converter expects.
#   Type 1: <root>/<subcorpus>-<version>.TEI/<site>/<year>/<file>.xml
#   Type 2: <root>/<subcorpus>-<version>.TEI/<year>/<file>.xml   (no site level)
#   Type 3: <root>/<subcorpus>-<version>.TEI/<site>/<year>/<month>/<file>.xml
#   Type 4: <root>/<subcorpus>-<version>.TEI/<type>/<site>/<year>/<file>.xml
CORPUS_DIR_TYPE = {
    "Adjud": 1,
    "Journals": 1,
    "Law": 1,
    "Books": 2,
    "Parla": 2,
    "Wiki": 2,
    "News1": 3,
    "News2": 3,
    "Social": 4,
}
# Wiki has no year level
NO_YEAR_SUBCORPORA = {"Wiki"}

# Manually curated exclusion list, same as 2019 (doc/overview.md)
LEGACY_EXCLUDED_SITES = {
    ("News2", "433"),
    ("News2", "fotbolti"),
    ("News2", "bleikt"),
    ("News2", "eyjan"),
    ("News2", "pressan"),
}

# Same-year duplicate risk: web vs. print edition of the same outlet.
# For years where both sides of a pair are present, "primary" is kept
# and "secondary"'s copy for those years is dropped. Not always print
# vs. web -- "primary" is whichever side is actually the fuller record
# for that outlet (checked against real word/doc counts, 2026-07-31):
DUPLICATE_RISK_PAIRS = [
    {"primary": ("News2", "morgunbladid"), "secondary": ("News2", "mbl")},
    {"primary": ("News2", "kjarninn"), "secondary": ("News2", "kjarninn_blad")},
    {"primary": ("News2", "frettatiminn_bl"), "secondary": ("News2", "frettatiminn")},
    {"primary": ("News2", "stundin"), "secondary": ("News2", "stundin_blad")},
    {"primary": ("News2", "baendabladid"), "secondary": ("News2", "bbl")},
]

class Doc:
    __slots__ = ("corpus", "site", "year", "words", "path")

    def __init__(self, corpus: str, site: str, year: Optional[int], words: int, path: str) -> None:
        self.corpus = corpus
        self.site = site
        self.year = year
        self.words = words
        self.path = path


def word_count_and_year(xml_path: str) -> Tuple[Optional[int], Optional[int]]:
    """Read only the TEI header of a document to get its word count
    and publication year, without parsing the (possibly large) body.
    Returns (word_count, year) where either may be None if not found.
    """
    words: Optional[int] = None
    source_date: Optional[str] = None
    fallback_date: Optional[str] = None
    stack: List[str] = []
    for event, elem in ET.iterparse(xml_path, events=("start", "end")):
        tag = elem.tag
        if event == "start":
            stack.append(tag)
            continue
        stack.pop()
        if tag == f"{XML_NS}measure" and elem.get("unit") == "words":
            try:
                words = int(elem.get("quantity", ""))
            except ValueError:
                pass
        elif tag == f"{XML_NS}date":
            when = elem.get("when")
            if when:
                if f"{XML_NS}sourceDesc" in stack:
                    if source_date is None:
                        source_date = when
                elif fallback_date is None:
                    fallback_date = when
        elif tag == f"{XML_NS}teiHeader":
            break
    date_str = source_date or fallback_date
    year: Optional[int] = None
    if date_str:
        try:
            year = int(date_str[:4])
        except ValueError:
            year = None
    return words, year


def iter_docs(root: str, version: str, corpus: str) -> Iterator[Doc]:
    """Yield Doc entries for one subcorpus, walking its known directory
    layout (see CORPUS_DIR_TYPE).
    """
    dtype = CORPUS_DIR_TYPE[corpus]
    base = os.path.join(root, f"IGC-{corpus}-{version}.TEI")
    if not os.path.isdir(base):
        # Legitimate for releases that ship only some subcorpora (e.g.
        # IGC-2024ext has no Books/Journals/Wiki), but must be visible:
        # a silently skipped directory would drop a whole subcorpus from
        # the manifest, and the manifest cache would then preserve the
        # omission across every future run.
        print(
            f"Warning: {base} does not exist -- {corpus} contributes "
            "no documents from this source",
            file=sys.stderr,
        )
        return

    def files_under(path: str) -> Iterator[str]:
        for name in sorted(os.listdir(path)):
            full = os.path.join(path, name)
            if os.path.isfile(full) and name.endswith(".xml"):
                yield full

    if dtype == 1:
        for site in sorted(os.listdir(base)):
            site_dir = os.path.join(base, site)
            if not os.path.isdir(site_dir):
                continue
            for year_name in sorted(os.listdir(site_dir)):
                year_dir = os.path.join(site_dir, year_name)
                if not os.path.isdir(year_dir):
                    continue
                for fpath in files_under(year_dir):
                    words, year = word_count_and_year(fpath)
                    if year is None:
                        try:
                            year = int(year_name)
                        except ValueError:
                            year = None
                    yield Doc(corpus, site, year, words or 0, fpath)

    elif dtype == 2:
        has_year = corpus not in NO_YEAR_SUBCORPORA
        for year_name in sorted(os.listdir(base)):
            year_dir = os.path.join(base, year_name)
            if not os.path.isdir(year_dir):
                continue
            for fpath in files_under(year_dir):
                words, year = word_count_and_year(fpath)
                if has_year and year is None:
                    try:
                        year = int(year_name)
                    except ValueError:
                        year = None
                elif not has_year:
                    year = None
                yield Doc(corpus, corpus, year, words or 0, fpath)

    elif dtype == 3:
        for site in sorted(os.listdir(base)):
            site_dir = os.path.join(base, site)
            if not os.path.isdir(site_dir):
                continue
            for year_name in sorted(os.listdir(site_dir)):
                year_dir = os.path.join(site_dir, year_name)
                if not os.path.isdir(year_dir):
                    continue
                for month_name in sorted(os.listdir(year_dir)):
                    month_dir = os.path.join(year_dir, month_name)
                    if not os.path.isdir(month_dir):
                        continue
                    for fpath in files_under(month_dir):
                        words, year = word_count_and_year(fpath)
                        if year is None:
                            try:
                                year = int(year_name)
                            except ValueError:
                                year = None
                        yield Doc(corpus, site, year, words or 0, fpath)

    elif dtype == 4:
        for social_type in sorted(os.listdir(base)):
            type_dir = os.path.join(base, social_type)
            if not os.path.isdir(type_dir) or social_type == "Twitter":
                continue
            for site in sorted(os.listdir(type_dir)):
                site_dir = os.path.join(type_dir, site)
                if not os.path.isdir(site_dir):
                    continue
                full_site = f"{social_type}-{site}"
                for year_name in sorted(os.listdir(site_dir)):
                    year_dir = os.path.join(site_dir, year_name)
                    if not os.path.isdir(year_dir):
                        continue
                    for fpath in files_under(year_dir):
                        words, year = word_count_and_year(fpath)
                        if year is None:
                            try:
                                year = int(year_name)
                            except ValueError:
                                year = None
                        yield Doc(corpus, full_site, year, words or 0, fpath)


def build_manifest(
    sources: List[Tuple[str, str]], corpora: List[str], manifest_path: str
) -> List[Doc]:
    """Scan one or more (root, version) IGC releases -- e.g. the
    IGC-2022 release and the IGC-2024ext extension -- into a single
    combined manifest, so recency-weighted sampling considers documents
    from every release together.
    """
    # The .done marker records what the manifest was built from, so a
    # cached manifest is only reused for the same sources and corpora --
    # otherwise e.g. adding the IGC-2024ext extension as a second
    # --source would silently keep sampling from the old scan.
    scan_config = {
        "sources": [[root, version] for root, version in sources],
        "corpora": corpora,
    }
    done_marker = manifest_path + ".done"
    if os.path.isfile(manifest_path) and os.path.isfile(done_marker):
        try:
            with open(done_marker, "r", encoding="utf-8") as f:
                cached_config = json.load(f)
        except (json.JSONDecodeError, UnicodeDecodeError):
            cached_config = None
        if cached_config == scan_config:
            print(f"Loading cached manifest from {manifest_path}")
            docs: List[Doc] = []
            with open(manifest_path, "r", encoding="utf-8") as f:
                for line in f:
                    row = json.loads(line)
                    docs.append(
                        Doc(row["corpus"], row["site"], row["year"], row["words"], row["path"])
                    )
            return docs
        print(
            f"{manifest_path} was built from different sources/corpora "
            "(or a pre-config .done marker) -- rescanning"
        )
    elif os.path.isfile(manifest_path):
        print(f"{manifest_path} exists but has no .done marker -- treating as incomplete, rescanning")

    docs = []
    with open(manifest_path, "w", encoding="utf-8") as out:
        for root, version in sources:
            for corpus in corpora:
                print(f"Scanning {corpus} ({root}, version {version})...", flush=True)
                n = 0
                for doc in iter_docs(root, version, corpus):
                    docs.append(doc)
                    out.write(
                        json.dumps(
                            {
                                "corpus": doc.corpus,
                                "site": doc.site,
                                "year": doc.year,
                                "words": doc.words,
                                "path": doc.path,
                            },
                            ensure_ascii=False,
                        )
                        + "\n"
                    )
                    n += 1
                print(f"  {n:,} documents")
    with open(done_marker, "w", encoding="utf-8") as f:
        json.dump(scan_config, f, ensure_ascii=False)
        f.write("\n")
    return docs


def filter_docs(
    docs: List[Doc],
    min_year: int,
) -> List[Doc]:
    kept = []
    corpora_present = {d.corpus for d in docs}
    # For each pair whose primary side is actually present,
    # collect the years it covers, so the secondary side can be
    # dropped for exactly those years.
    dup_years_by_secondary: List[Tuple[Tuple[str, str], set]] = []
    for pair in DUPLICATE_RISK_PAIRS:
        if pair["primary"][0] not in corpora_present:
            continue
        primary_years = {d.year for d in docs if (d.corpus, d.site) == pair["primary"]}
        if primary_years:
            dup_years_by_secondary.append((pair["secondary"], primary_years))

    for doc in docs:
        if doc.year is not None and doc.year < min_year:
            continue
        if (doc.corpus, doc.site) in LEGACY_EXCLUDED_SITES:
            continue
        if any(
            (doc.corpus, doc.site) == secondary and doc.year in years
            for secondary, years in dup_years_by_secondary
        ):
            continue
        kept.append(doc)
    return kept


def recency_weight(year: Optional[int], current_year: int, half_life: float) -> float:
    if year is None:
        # Undated pools (e.g. Wiki) get a flat, medium weight
        return 0.5
    age = max(0, current_year - year)
    return 0.5 ** (age / half_life)


def sample_to_budget(
    docs: List[Doc],
    target_words: int,
    current_year: int,
    half_life: float,
    uniform: bool = False,
    max_site_share: Optional[float] = None,
    initial_site_words: Optional[Dict[Tuple[str, str], int]] = None,
    cap_total_words: Optional[int] = None,
) -> List[Doc]:
    """Weighted sampling without replacement at the (corpus, site, year)
    collection-unit level, biased toward recent years, using the
    Efraimidis-Spirakis A-ExpJ scheme (draw key = U^(1/weight) per unit,
    take units in descending key order) so that no unit is picked twice
    and higher weight means higher expected priority.

    max_site_share caps how much a single (corpus, site) can contribute
    (e.g. 0.15 = at most 15%). Without this, a handful of giant
    single-site-year units can swallow most of the budget before
    smaller sites ever get a chance. The cap is a share of
    cap_total_words when given, else of target_words: with pinning,
    target_words is only the residual fill budget while site totals are
    seeded at full-selection scale, so the cap must be computed against
    the full selection size.
    """
    units: Dict[Tuple[str, str, Any], List[Doc]] = {}
    for doc in docs:
        key = (doc.corpus, doc.site, doc.year) if doc.year is not None else (doc.corpus, doc.site, doc.path)
        units.setdefault(key, []).append(doc)

    keyed = []
    for unit_key, unit_docs in units.items():
        # The unit key's third element is a path (not a year) for undated
        # docs -- always read the real year off the documents themselves.
        weight = 1.0 if uniform else recency_weight(unit_docs[0].year, current_year, half_life)
        u = random.random()
        priority = u ** (1.0 / weight)
        keyed.append((priority, unit_key, unit_docs))
    keyed.sort(key=lambda t: t[0], reverse=True)

    cap_base = cap_total_words if cap_total_words is not None else target_words
    site_cap = max_site_share * cap_base if max_site_share is not None else None
    site_words: Dict[Tuple[str, str], int] = dict(initial_site_words) if initial_site_words else {}

    selected: List[Doc] = []
    total_words = 0
    for _, unit_key, unit_docs in keyed:
        if total_words >= target_words:
            break
        site_key = (unit_key[0], unit_key[1])
        unit_words = sum(d.words for d in unit_docs)
        if site_cap is not None and site_words.get(site_key, 0) + unit_words > site_cap:
            continue
        selected.extend(unit_docs)
        total_words += unit_words
        site_words[site_key] = site_words.get(site_key, 0) + unit_words
    return selected


def print_summary(label: str, docs: List[Doc]) -> None:
    total_words = sum(d.words for d in docs)
    by_corpus: Dict[str, int] = {}
    for d in docs:
        by_corpus[d.corpus] = by_corpus.get(d.corpus, 0) + d.words
    print(f"\n{label}: {len(docs):,} documents, {total_words:,} words")
    for corpus, words in sorted(by_corpus.items(), key=lambda kv: -kv[1]):
        print(f"  {corpus:10s} {words:>14,} words")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        dest="sources",
        action="append",
        required=True,
        metavar="ROOT:VERSION",
        help="IGC release to scan, as root:version -- repeatable.",
    )
    parser.add_argument(
        "--corpora",
        default="Adjud,Books,Journals,Law,News1,News2,Parla,Wiki",
        help="Comma-separated subcorpora to consider (Social excluded by default)",
    )
    parser.add_argument("--min-year", type=int, default=1980)
    parser.add_argument("--target-words", type=int, default=200_000_000)
    parser.add_argument("--current-year", type=int, default=2026)
    parser.add_argument("--half-life-years", type=float, default=8.0)
    parser.add_argument(
        "--uniform",
        action="store_true",
        help="Disable recency weighting -- uniform random sampling across units, matching 2019's rmh.py",
    )
    parser.add_argument(
        "--max-site-share",
        type=float,
        default=0.10,
        help="Cap any single (corpus, site) at this fraction of target-words (default 0.10 = 10%%). "
        "Pass 1.0 or higher to disable.",
    )
    parser.add_argument("--manifest", default="pilot_manifest.jsonl")
    parser.add_argument("--output-files", default="pilot_selected_files.txt")
    parser.add_argument(
        "--pin-selected",
        default=None,
        help="A previous run's --output-files list. Every file in it is kept "
        "unconditionally (so Málfríður's sentence cache stays maximally useful "
        "as more source data is added later). The rest of the budget is filled "
        "from the remaining pool.",
    )
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    sources = []
    for s in args.sources:
        root, _, version = s.rpartition(":")
        if not root:
            raise SystemExit(f"--source must be ROOT:VERSION, got {s!r}")
        sources.append((root, version))

    corpora = [c.strip() for c in args.corpora.split(",") if c.strip()]

    docs = build_manifest(sources, corpora, args.manifest)
    print_summary("Full scanned pool", docs)

    filtered = filter_docs(docs, args.min_year)
    print_summary("After grisjun (year/exclusion-list/dedup filters)", filtered)

    max_site_share = args.max_site_share if args.max_site_share < 1.0 else None

    pinned: List[Doc] = []
    remaining = filtered
    if args.pin_selected:
        with open(args.pin_selected, "r", encoding="utf-8") as f:
            pinned_paths = {line.strip() for line in f if line.strip()}
        pinned = [d for d in filtered if d.path in pinned_paths]
        remaining = [d for d in filtered if d.path not in pinned_paths]
        missing = len(pinned_paths) - len(pinned)
        if missing:
            print(
                f"Warning: {missing:,} pinned path(s) from {args.pin_selected} "
                "were not found in the current filtered pool (grisjun rules or "
                "source data may have changed) and will be dropped"
            )
        print_summary("Pinned (carried over unconditionally)", pinned)

    pinned_words = sum(d.words for d in pinned)
    pinned_site_words: Dict[Tuple[str, str], int] = {}
    for d in pinned:
        key = (d.corpus, d.site)
        pinned_site_words[key] = pinned_site_words.get(key, 0) + d.words

    fill_budget = max(0, args.target_words - pinned_words)
    newly_selected = sample_to_budget(
        remaining,
        fill_budget,
        args.current_year,
        args.half_life_years,
        uniform=args.uniform,
        max_site_share=max_site_share,
        initial_site_words=pinned_site_words if pinned else None,
        cap_total_words=args.target_words,
    )
    if pinned:
        print_summary("Newly drawn to fill remaining budget", newly_selected)

    selected = pinned + newly_selected
    print_summary("Pilot selection (pinned + newly drawn)" if pinned else "Pilot selection", selected)

    with open(args.output_files, "w", encoding="utf-8") as f:
        for doc in selected:
            f.write(doc.path + "\n")
    print(f"\nWrote {len(selected):,} file paths to {args.output_files}")


if __name__ == "__main__":
    main()
