# CLAUDE.md

Guidance for Claude Code in this repository. `README.md` documents the API,
`doc/overview.md` the design and `doc/2026-update.md` the 2026 model rebuild.

## Status (2026-11-04): 2.1.0 released, 2.2.0 in a PR

**icegrams 2.1.0 was released on 2026-10-16** (tag `2.1.0` on `a233b53`,
GitHub release 2.1.0, 30 wheels plus the sdist on PyPI). It contains:

- #10, free-threaded CPython: `cp314t` and `cp315t` wheels, cffi >= 2.0,
  Python >= 3.10.
- #12, a faster `succ()`: `heapq.nlargest` keeps only the n best successors.
- #11, capped stupid backoff for unseen bigrams and trigrams
  (`Ngrams(backoff=False)` gives the old behaviour).

The model is unchanged since 2.0.0: `model-2026.08`.

**Next: 2.2.0, the `icegrams-data` package.** PyPI set its file limit to
250 MiB on 2026-11-04
([pypi/support#12724](https://github.com/pypi/support/issues/12724), closed).
The implementation is on branch `icegrams-data` (see "2.2.0" under the
Roadmap for what it does and what is left before the release).

## Key commands

Dependencies are declared in `pyproject.toml` and pinned in `uv.lock`
(committed; installers of the package ignore it). Run `uv lock` after
changing dependencies.

```bash
uv sync --extra dev                  # dev environment (pytest, ruff)
uv run python -m icegrams.download   # fetch the model once (~213 MB)
uv run python -m pytest              # test suite; needs the model
ruff check src/icegrams              # lint, as CI does (3.10 job only)

# The icegrams-data wheel (192 MB), from the cached download if present
python3 tools/data_package.py && uv build --wheel icegrams-data -o dist-data
python3 tools/data_package.py --clean
```

The dev environment installs the `icegrams-data/` subproject editable
(`[tool.uv.sources]`). It holds no model, so lookups fall through to the
download cache. Installing a built data wheel over it
(`uv pip install dist-data/*.whl`) replaces it, as the tests workflow does.

## Where the model lives

The model is `trigrams.bin`, 213,218,123 bytes. It is an asset of the
GitHub release `model-2026.08`; model releases are tagged separately from
code releases. `src/icegrams/model.py` records the tag, URL, size and
SHA-256. From 2.2.0 it is also the package `icegrams-data` 2026.8.0 (one
`py3-none-any` wheel, 191,765,471 bytes, no sdist), a hard dependency of
`icegrams` pinned as `icegrams-data == 2026.8.*` (`model.data_requirement()`
derives that string from the tag, and `test_data_requirement` checks it
against the installed metadata). At runtime `model_filename()` looks, in
this order, at:

1. `ICEGRAMS_MODEL_FILE`;
2. `src/icegrams/resources/trigrams.bin` (a model built in place);
3. the installed `icegrams_data` package, if its `MODEL_RELEASE_TAG` is
   the one in `model.py` and it holds the file;
4. the download cache (`~/.cache/icegrams/<tag>/`, or `ICEGRAMS_MODEL_DIR`).

`Ngrams()` never downloads anything; `ModelNotFoundError` says why the
data package was not used. `python -m icegrams.download` remains as a
fallback, and is a no-op when the data package holds the model.

CI builds the data wheel once per model (`.github/actions/icegrams-data`:
`tools/data_package.py` downloads the release asset and checks its size and
SHA-256, then `uv build`) and caches it under a key made of the SHA-256 and
a hash of `icegrams-data/**` and the script. All three workflows use it;
`wheels.yml` passes it to the other OSes as an artifact, because caches
are per OS.

## Releasing

`wheels.yml` runs on every tag except `model-*` and `data-*`. It builds 30
wheels:

- `cp310-abi3`, `cp314t` and `cp315t`;
- PyPy `pp311` (pp73 and pp80) and `pp312` (pp80);
- on Linux x86_64 and aarch64, macOS x86_64 and arm64, and Windows AMD64.

A check step fails the run if any of the expected wheels is missing, or if
a wheel or the sdist contains a `.bin` file. Every wheel is smoke-tested
by cibuildwheel with the run's own data wheel installed
(`test/wheel_smoke.py`: real queries, plus the GIL check). A tag
containing `test` (e.g. `2.2.0-test1`) is a dry run: everything is built
and nothing is published. Delete the test tags afterwards. Other tags
publish to PyPI through the `pypi` environment, whose only deployment rule
is the tag pattern `*.*.*` (it matches `data-2026.8.0` too). The changelog
is in `README.md`, and the version is in `pyproject.toml`.

### Releasing icegrams-data

`data-release.yml` runs on `data-*` tags and by hand (Actions > Run
workflow). The tag must be `data-` plus the version in
`icegrams-data/pyproject.toml`, e.g. `data-2026.8.0`; a tag containing
`test` (`data-2026.8.0-test1`) or a manual run only builds and tests. It
restores (or builds) the data wheel, tests it with an icegrams wheel built
from the same commit, and publishes the wheel alone through the `pypi`
environment. The PyPI Trusted Publisher of `icegrams-data` must name
`data-release.yml` and `pypi`.

Version scheme: `model-YYYY.MM` is `icegrams-data` `YYYY.M.N` (no leading
zero; N for re-releases of the same model). `tools/data_package.py` fails
if the version, `icegrams_data.MODEL_RELEASE_TAG` and `model.py` disagree.
A new model therefore means: upload it to a new `model-*` GitHub release;
update `model.py` (tag, size, SHA-256), `icegrams_data.MODEL_RELEASE_TAG`,
the icegrams-data version and the pin in `pyproject.toml`; release
`icegrams-data` first, then `icegrams`.

## Roadmap

### 2.2.0: the model as a PyPI package, `icegrams-data`

Decided by villi on 2026-10-16, modelled on BinPackage's `islenska-data`
(`~/github/BinPackage/CLAUDE.md`, `RELEASING.md`). Why:

- `pip install icegrams` then just works, with no second step to forget.
- Lock files, wheelhouses and container layers capture the model, with its
  hash.
- No per-user cache is needed.
- The wheel smoke test can do real lookups.
- PyPI storage: the `icegrams` project uses ~7.0 GB of its 10 GB quota,
  because every wheel up to 1.1.7 bundled the old 38 MB model.
  `icegrams-data` gets its own 10 GB.

The cost: each new environment downloads 192 MB from PyPI, which pip and uv
then cache.

**PyPI:** villi uploaded an empty `icegrams-data` 0.0.0 placeholder on
2026-10-16 (PyPI raises limits only for existing projects), and PyPI set
the project's file limit to 250 MiB on 2026-11-04 (pypi/support#12724).
The wheel is 182.9 MiB.

**Done on branch `icegrams-data` (2026-11-04):** the subproject
`icegrams-data/` (import package `icegrams_data`: `MODEL_RELEASE_TAG`,
`model_path()`), `tools/data_package.py`, the lookup order and error
message in `model.py`, the `download.py` no-op, the pin and
`[tool.uv.sources]` in `pyproject.toml`, version 2.2.0, the composite action
and the three workflows (described above), `test/wheel_smoke.py`, tests of
the lookup order and the pin, README and changelog. Tag scheme: `data-*`,
as in BinPackage (a `model-*` tag would collide with the GitHub release
tags of the model files).

**Left before the release:**

1. On PyPI (villi): add a Trusted Publisher for `icegrams-data`: repository
   `mideind/Icegrams`, workflow `data-release.yml`, environment `pypi`.
   Consider moving the project into the Miðeind organization, as was done
   with `islenska-data`, and yanking the 0.0.0 placeholder after 2026.8.0
   is out.
2. Dry runs: done 2026-11-04. `data-2026.8.0-test1` and `2.2.0-test1`
   passed (30 wheels, each smoke-tested with the data wheel; both publish
   jobs skipped), and the tags were deleted. Repeat them if the workflows
   change before the release.
3. Merge, then tag `data-2026.8.0` and, once it is on PyPI, `2.2.0` (add
   the date to the changelog first). Check a fresh `pip install icegrams`
   on a GIL CPython and on PyPy.

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
