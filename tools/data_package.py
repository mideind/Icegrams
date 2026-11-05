#!/usr/bin/env python3
"""

Icegrams: A trigrams library for Icelandic

tools/data_package.py

Copyright (C) 2026 Miðeind ehf.

This software is licensed under the MIT License (see LICENSE.txt).


Stages the trigram model into the icegrams-data subproject, so that

    uv build --wheel icegrams-data -o dist-data

builds the icegrams-data wheel. Run it from the repository root:

    python tools/data_package.py [--model PATH]
    python tools/data_package.py --clean

The model is the one that src/icegrams/model.py names (MODEL_RELEASE_TAG,
MODEL_SIZE, MODEL_SHA256). It is taken from --model, else from the
download cache of `python -m icegrams.download`, else downloaded from
MODEL_URL, and its size and SHA-256 are checked in every case. Before
staging, the script checks that model.py, icegrams_data.MODEL_RELEASE_TAG
and the icegrams-data version agree (model-2026.11 is version 2026.11.x).

It needs only the standard library: icegrams need not be installed.
--clean removes the staged model again.

"""

from typing import Any, Dict, Optional

import argparse
import hashlib
import os
import re
import runpy
import shutil
import sys
import tempfile
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_PY = os.path.join(ROOT, "src", "icegrams", "model.py")
DATA_PROJECT = os.path.join(ROOT, "icegrams-data")
DATA_INIT = os.path.join(DATA_PROJECT, "src", "icegrams_data", "__init__.py")
DATA_PYPROJECT = os.path.join(DATA_PROJECT, "pyproject.toml")

_CHUNK_SIZE = 1024 * 1024


def fail(msg: str) -> None:
    print("Error: " + msg, file=sys.stderr)
    sys.exit(1)


def data_version() -> str:
    """The version in icegrams-data/pyproject.toml (no tomllib on 3.10)"""
    with open(DATA_PYPROJECT, encoding="utf-8") as f:
        m = re.search(r'^version\s*=\s*"([^"]+)"', f.read(), re.MULTILINE)
    if m is None:
        fail("No version in " + DATA_PYPROJECT)
        raise AssertionError  # unreachable; for type checkers
    return m.group(1)


def check_versions(model: Dict[str, Any], data: Dict[str, Any]) -> None:
    tag = model["MODEL_RELEASE_TAG"]
    if data["MODEL_RELEASE_TAG"] != tag:
        fail(
            "icegrams_data.MODEL_RELEASE_TAG is {0}, but model.py has {1}".format(
                data["MODEL_RELEASE_TAG"], tag
            )
        )
    m = re.fullmatch(r"model-(\d{4})\.(\d{2})", tag)
    if m is None:
        fail("Unexpected model release tag " + tag)
        raise AssertionError
    expected = "{0}.{1}.".format(int(m.group(1)), int(m.group(2)))
    version = data_version()
    if not version.startswith(expected) or not version[len(expected):].isdigit():
        fail(
            "The icegrams-data version {0} does not belong to {1} "
            "(expected {2}N)".format(version, tag, expected)
        )


def verify(path: str, model: Dict[str, Any]) -> bool:
    """True if the file at path is the model that model.py names"""
    if os.path.getsize(path) != model["MODEL_SIZE"]:
        return False
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(_CHUNK_SIZE), b""):
            h.update(chunk)
    return h.hexdigest() == model["MODEL_SHA256"]


def download(url: str, dest_dir: str) -> str:
    print("Downloading " + url, file=sys.stderr)
    fd, tmp = tempfile.mkstemp(dir=dest_dir, suffix=".tmp")
    with os.fdopen(fd, "wb") as out, urllib.request.urlopen(url, timeout=60) as r:
        shutil.copyfileobj(r, out, _CHUNK_SIZE)
    return tmp


def stage(model: Dict[str, Any], source: Optional[str], dest: str) -> None:
    if os.path.isfile(dest) and verify(dest, model):
        print("The model is already staged at " + dest, file=sys.stderr)
        return
    tmp: Optional[str] = None
    if source is None:
        try:
            cached = model["_cached_model_path"]()
        except RuntimeError:
            cached = None
        if cached and os.path.isfile(cached) and verify(cached, model):
            source = cached
        else:
            source = tmp = download(model["MODEL_URL"], os.path.dirname(dest))
    try:
        if not verify(source, model):
            fail(
                "{0} is not the model of {1} (size {2}, SHA-256 {3})".format(
                    source,
                    model["MODEL_RELEASE_TAG"],
                    model["MODEL_SIZE"],
                    model["MODEL_SHA256"],
                )
            )
        if tmp is not None:
            os.chmod(tmp, 0o644)
            os.replace(tmp, dest)
            tmp = None
        else:
            print("Copying " + source, file=sys.stderr)
            shutil.copyfile(source, dest)
    finally:
        if tmp is not None:
            os.remove(tmp)
    print("Staged the model at " + dest, file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Stage the trigram model into the icegrams-data subproject"
    )
    parser.add_argument("--model", metavar="PATH", help="the trigrams.bin to stage")
    parser.add_argument("--clean", action="store_true", help="remove the staged model")
    args = parser.parse_args()

    model = runpy.run_path(MODEL_PY)
    data = runpy.run_path(DATA_INIT)
    dest = os.path.join(os.path.dirname(DATA_INIT), data["MODEL_BASENAME"])
    if args.clean:
        if os.path.exists(dest):
            os.remove(dest)
            print("Removed " + dest, file=sys.stderr)
        return
    check_versions(model, data)
    stage(model, args.model, dest)


if __name__ == "__main__":
    main()
