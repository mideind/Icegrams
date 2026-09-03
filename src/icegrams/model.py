"""

Icegrams: A trigrams library for Icelandic

model.py

Copyright (C) 2026 Miðeind ehf.

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


This module locates the compressed trigram model file (trigrams.bin)
at runtime. It never downloads anything: the model is fetched once,
after installing the package, by the separate setup step

    python -m icegrams.download

(see download.py). Creating an Ngrams instance only looks for a model
file, in this order:

    1. The file named by the ICEGRAMS_MODEL_FILE environment variable,
       if set.
    2. A model built in place in the package's resources directory
       (the output location of the icegrams.ngrams compressor).
    3. The model cache directory, which is where the download step
       puts the file. Its location can be overridden with the
       ICEGRAMS_MODEL_DIR environment variable.

If no model is found, ModelNotFoundError is raised.

"""

import os
import sys

# The GitHub release that the current model is published under.
# Model releases are tagged independently of code releases, so a new
# model can be shipped by uploading it to a new model-* release and
# updating the constants below.
MODEL_RELEASE_TAG = "model-2026.08"
MODEL_BASENAME = "trigrams.bin"
MODEL_URL = (
    "https://github.com/mideind/Icegrams/releases/download/"
    + MODEL_RELEASE_TAG
    + "/"
    + MODEL_BASENAME
)
MODEL_SIZE = 213218123
MODEL_SHA256 = "273db68d82cf842ddbc67ee11f9093e1204cc8a4692081f1d21601aea928d92d"

# The 16-byte header that every trigrams.bin file starts with
# (must match NgramStorage.VERSION in ngrams.py)
MODEL_HEADER = b"Reynir 001.00.00"

ENV_MODEL_FILE = "ICEGRAMS_MODEL_FILE"
ENV_MODEL_DIR = "ICEGRAMS_MODEL_DIR"
ENV_MODEL_URL = "ICEGRAMS_MODEL_URL"

DOWNLOAD_COMMAND = "python -m icegrams.download"

_PATH = os.path.dirname(__file__) or "."


class ModelNotFoundError(FileNotFoundError):
    """Raised when the trigram model file is not present on this machine"""

    pass


def _default_cache_dir() -> str:
    """Return the platform's per-user cache directory for icegrams"""
    home = os.path.expanduser("~")
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.path.join(
            home, "AppData", "Local"
        )
    elif sys.platform == "darwin":
        base = os.path.join(home, "Library", "Caches")
    else:
        base = os.environ.get("XDG_CACHE_HOME") or os.path.join(home, ".cache")
    return os.path.join(base, "icegrams")


def model_dir() -> str:
    """Return the directory where the downloaded model is stored.
    The directory is keyed by the model release tag, so that bumping
    MODEL_RELEASE_TAG never silently reuses a stale model: the new
    model must be downloaded explicitly before it can be used."""
    base = os.environ.get(ENV_MODEL_DIR) or _default_cache_dir()
    return os.path.join(base, MODEL_RELEASE_TAG)


def _cached_model_path() -> str:
    return os.path.join(model_dir(), MODEL_BASENAME)


def _is_model_file(path: str) -> bool:
    """Return True if path is an existing file that starts with the
    trigrams.bin header. This rejects placeholder files and files that
    were truncated before the header was written."""
    try:
        with open(path, "rb") as f:
            return f.read(len(MODEL_HEADER)) == MODEL_HEADER
    except OSError:
        return False


def model_filename() -> str:
    """Return the path of the trigrams.bin model file. This function
    never downloads anything; it raises ModelNotFoundError if the
    model is not present."""
    # 1. Explicit override
    env_file = os.environ.get(ENV_MODEL_FILE)
    if env_file:
        if not os.path.isfile(env_file):
            raise ModelNotFoundError(
                "{0} points to {1}, which does not exist".format(
                    ENV_MODEL_FILE, env_file
                )
            )
        return env_file
    # 2. A model built in place by the compressor (development setups)
    local = os.path.join(_PATH, "resources", MODEL_BASENAME)
    if _is_model_file(local):
        return local
    # 3. The model fetched by the download step
    cached = _cached_model_path()
    if _is_model_file(cached):
        return cached
    raise ModelNotFoundError(
        "The Icegrams trigram model was not found at {0}.\n"
        "The model is not bundled with the package; download it once "
        "by running\n\n    {1}\n\n"
        "or point the {2} environment variable at an existing model "
        "file.".format(cached, DOWNLOAD_COMMAND, ENV_MODEL_FILE)
    )
