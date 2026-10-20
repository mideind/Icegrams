# CLAUDE.md

Guidance for Claude Code in this repository. `README.md` documents the API,
`doc/overview.md` the design and `doc/2026-update.md` the 2026 model rebuild.

## Status (2026-10-20): 2.1.0 released, 2.2.0 waiting on PyPI

**icegrams 2.1.0 was released on 2026-10-16** (tag `2.1.0` on `a233b53`,
GitHub release 2.1.0, 30 wheels plus the sdist on PyPI). It contains:

- #10, free-threaded CPython: `cp314t` and `cp315t` wheels, cffi >= 2.0,
  Python >= 3.10.
- #12, a faster `succ()`: `heapq.nlargest` keeps only the n best successors.
- #11, capped stupid backoff for unseen bigrams and trigrams
  (`Ngrams(backoff=False)` gives the old behaviour).

The model is unchanged since 2.0.0: `model-2026.08`.

**Next: 2.2.0, the `icegrams-data` package** (see the Roadmap below). It is
blocked until PyPI raises the file size limit for `icegrams-data`, which
was requested in [pypi/support#12724](https://github.com/pypi/support/issues/12724).
When that issue gets a reply, start with "When the limit is granted" below.

## Key commands

Dependencies are declared in `pyproject.toml` and pinned in `uv.lock`
(committed; installers of the package ignore it). Run `uv lock` after
changing dependencies.

```bash
uv sync --extra dev                  # dev environment (pytest, ruff)
uv run python -m icegrams.download   # fetch the model once (~213 MB)
uv run python -m pytest              # test suite; needs the model
ruff check src/icegrams              # lint, as CI does (3.10 job only)
```

## Where the model lives today

The model is `trigrams.bin`, 213,218,123 bytes. It is an asset of the
GitHub release `model-2026.08`; model releases are tagged separately from
code releases. `src/icegrams/model.py` records the tag, URL, size and
SHA-256. At runtime `model_filename()` looks, in this order, at:

1. `ICEGRAMS_MODEL_FILE`;
2. `src/icegrams/resources/trigrams.bin` (a model built in place);
3. the download cache (`~/.cache/icegrams/<tag>/`, or `ICEGRAMS_MODEL_DIR`).

`Ngrams()` never downloads anything. The user runs
`python -m icegrams.download` once, and `ModelNotFoundError` is raised if
they haven't. CI (`python-package.yml`) caches `~/.cache/icegrams` keyed by
the tag and then runs the download step.

## Releasing

`wheels.yml` runs on every tag except `model-*`. It builds 30 wheels:

- `cp310-abi3`, `cp314t` and `cp315t`;
- PyPy `pp311` (pp73 and pp80) and `pp312` (pp80);
- on Linux x86_64 and aarch64, macOS x86_64 and arm64, and Windows AMD64.

A check step fails the run if any of the expected wheels is missing. A tag
containing `test` (e.g. `2.2.0-test1`) is a dry run: everything is built
and nothing is published. Delete the test tags afterwards. Other tags
publish to PyPI through the `pypi` environment, whose only deployment rule
is the tag pattern `*.*.*`. The changelog is in `README.md`, and the
version is in `pyproject.toml`.

## Roadmap

### 2.2.0: the model as a PyPI package, `icegrams-data`

Decided by villi on 2026-10-16. It ships as its own PR with its own version
bump, after 2.1.0. `icegrams-data` is a **hard dependency** of `icegrams`,
modelled on BinPackage's `islenska-data`; read
`~/github/BinPackage/CLAUDE.md` and `RELEASING.md` ("Releasing the data
package") first.

Why:

- `pip install icegrams` then just works, with no second step to forget.
- Lock files, wheelhouses and container layers capture the model, with its
  hash.
- No per-user cache is needed.
- The wheel smoke test can do real lookups (see below).
- PyPI storage: the `icegrams` project uses ~7.0 GB of its 10 GB quota,
  because every wheel up to 1.1.7 bundled the old 38 MB model.
  `icegrams-data` gets its own 10 GB.

The cost: each new environment downloads 192 MB from PyPI, which pip and uv
then cache.

**State on PyPI (2026-10-16):**

- villi uploaded an empty `icegrams-data` 0.0.0 placeholder (wheel and
  sdist, ~1.5 KB each), because PyPI raises limits only for existing
  projects. Creating a project needs an account-wide API token; a token
  scoped to `icegrams` cannot create one.
- The model wheel is 192 MB (183 MiB), over PyPI's 100 MiB per-file
  default, so a File Limit Request for 250 MiB was filed:
  [pypi/support#12724](https://github.com/pypi/support/issues/12724),
  template `limit-request-file.yml`.
- On 2026-10-20 the request was untouched, with ~60 limit requests ahead
  of it and none closed since 2026-10-16.

**When the limit is granted:**

1. Check the granted size on the issue and on PyPI (the project's settings
   page).
2. On PyPI (villi): add a Trusted Publisher for `icegrams-data` that names
   the new workflow file and the `pypi` environment. Consider moving the
   project into the Miðeind organization, as was done with `islenska-data`.
3. On GitHub (villi, repo settings): add a tag rule for the new tag pattern
   to the `pypi` environment, next to `*.*.*`, as BinPackage has
   `data-*.*.*`.
4. Do the PR (design below), with a dry run of both workflows. Then release
   `icegrams-data` first and `icegrams` 2.2.0 after it, so that 2.2.0 can
   be installed as soon as it is published.

**Design (sketch, following BinPackage):**

- **Subproject `icegrams-data/`** with its own `pyproject.toml` and README.
  The import package is `icegrams_data`, holding `trigrams.bin` and a few
  lines that return its path. It is released as one pure `py3-none-any`
  wheel, with no sdist (an sdist would just duplicate the model).
- **Versions follow the model**, e.g. `icegrams-data 2026.8.0` for
  `model-2026.08`. `icegrams` pins it exactly (`icegrams-data == 2026.8.*`),
  because a new model changes query results. BinPackage pins only a data
  format; that is the difference.
- **Its own release workflow on `model-*` tags** (`wheels.yml` already
  ignores them). Still open: `model-2026.08` already exists as the tag of
  the GitHub release asset, so decide on the tag scheme for the package
  release, e.g. `model-2026.8.0`. The workflow must check that the tag
  matches the version, as BinPackage's `data-release.yml` does.
- **`model.py` lookup order:** `ICEGRAMS_MODEL_FILE` → `resources/` → the
  installed `icegrams_data` package → the download cache. Keep
  `python -m icegrams.download` as a fallback for 2.0/2.1 setups and for
  machines that cannot reach PyPI.
- **Dev environment:** `[tool.uv.sources]` points at the local subproject
  (editable, normally without the model), as in BinPackage.
- **CI:**
  - Build the data wheel once per model and cache it, like BinPackage's
    composite action `.github/actions/islenska-data`.
  - Run the tests against it instead of the download cache.
  - Assert that no `.bin` file lands in an `icegrams` wheel or the sdist
    (`MANIFEST.in` already prunes `resources/`).
- **Wheel smoke test** (item 3 of the #10 review, deferred by villi "for a
  later further discussion"): today `CIBW_TEST_COMMAND` only imports
  `icegrams._trie` and checks the GIL. With the data wheel it can do real
  queries, as BinPackage's `test/wheel_smoke.py` does.
- **Docs:** update the README's Installation section, `model.py` and
  `download.py` docstrings, and the changelog.

### With the next model rebuild (format change)

Both items below change the `trigrams.bin` format. That means a new
`MODEL_HEADER` (now `Reynir 001.00.00`, matching `NgramStorage.VERSION`), a
model rebuild and a new model release. They can ship together with the
`icegrams-data` switch or later.

- **Store the vocabulary uncompressed** in the file. It is gzip-compressed
  today, so `load()` unpacks it into a 21.7 MB `bytes` object in every
  process; everything else stays in shared, file-backed mmap pages.
- **Kneser-Ney counts**, from the "Future work" note in PR #11. Stupid
  backoff gives well-ordered scores, but they are not normalized
  probabilities. Interpolated Kneser-Ney needs:
  - per-context continuation counts, which can be derived from the trie's
    child ranges;
  - one extra vocabulary-sized array of `N1+(• w)`, written by
    `NgramStorage.compress()`.

  The discount D is about 0.75, or can be estimated from the
  count-of-counts that `bucket_view.py` produces.

### Other loose ends

- Draft PR #3 (2022, peturorri): move the trigram generation code into the
  package.
- Unmerged remote branches that nobody has reviewed against 2.1.0:
  - `abi3-wheels` (2026-06, "Publish abi3 wheels; fix C++ linking in
    source builds");
  - `winfix` (2025-05, Windows-only wheel builds in CI).
- 17 tags `1.1.3-0` … `1.1.3-16`, leftover build attempts from 2024; the
  1.1.3 release itself is on `1.1.3-final`. Asked about deleting them on
  2026-10-16; no answer yet.
