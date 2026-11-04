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
at runtime. The model is normally installed with the icegrams-data
package, a dependency of icegrams, and the download step

    python -m icegrams.download

(see download.py) remains as a fallback, e.g. for installations
of icegrams without its dependencies. Creating an Ngrams instance
never downloads anything; it only looks for a model file, in this
order:

    1. The file named by the ICEGRAMS_MODEL_FILE environment variable,
       if set.
    2. A model built in place in the package's resources directory
       (the output location of the icegrams.ngrams compressor).
    3. The installed icegrams-data package, if it holds the model of
       this release (MODEL_RELEASE_TAG).
    4. The model cache directory, which is where the download step
       puts the file. Its location can be overridden with the
       ICEGRAMS_MODEL_DIR environment variable.

If no model is found, ModelNotFoundError is raised.

"""

from typing import Optional, Tuple

import os
import re
import sys

# The GitHub release that the current model is published under.
# Model releases are tagged independently of code releases. A new model
# is shipped by uploading it to a new model-* release, updating the
# constants below, and releasing a matching icegrams-data (its version
# and MODEL_RELEASE_TAG follow this tag; tools/data_package.py checks
# that they agree) and an icegrams that requires it (pyproject.toml).
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

DATA_PACKAGE = "icegrams-data"


def data_requirement() -> str:
    """The requirement on icegrams-data that matches MODEL_RELEASE_TAG:
    model-2026.08 is in icegrams-data 2026.8.x. pyproject.toml must
    declare exactly this dependency (a test checks it)."""
    m = re.fullmatch(r"model-(\d{4})\.(\d{2})", MODEL_RELEASE_TAG)
    assert m is not None, MODEL_RELEASE_TAG
    return "{0}=={1}.{2}.*".format(DATA_PACKAGE, int(m.group(1)), int(m.group(2)))

_PATH = os.path.dirname(__file__) or "."


class ModelNotFoundError(FileNotFoundError):
    """Raised when the trigram model file is not present on this machine"""

    pass


def _default_cache_dir() -> str:
    """Return the platform's per-user cache directory for icegrams"""
    home = os.path.expanduser("~")
    if not os.path.isabs(home):
        # No HOME (and no passwd entry to fall back on), e.g. a container
        # running as an arbitrary uid: don't quietly use a relative path
        raise RuntimeError(
            "Unable to determine the home directory; set the {0} "
            "environment variable to choose where the Icegrams model "
            "is stored".format(ENV_MODEL_DIR)
        )
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


def _data_package_model() -> Tuple[Optional[str], str]:
    """Return the path of the model in the installed icegrams-data
    package, or None and the reason why it can't be used. A source
    checkout of icegrams-data (the editable install of a development
    environment) holds no model, and a package of another model
    release is ignored."""
    try:
        import icegrams_data  # type: ignore[import-not-found,unused-ignore]
    except ImportError:
        return None, "{0} is not installed".format(DATA_PACKAGE)
    tag = getattr(icegrams_data, "MODEL_RELEASE_TAG", None)
    if tag != MODEL_RELEASE_TAG:
        return None, "the installed {0} {1} holds {2}, not {3}".format(
            DATA_PACKAGE,
            getattr(icegrams_data, "__version__", "?"),
            tag,
            MODEL_RELEASE_TAG,
        )
    path = icegrams_data.model_path()
    if not _is_model_file(path):
        return None, "the installed {0} holds no model file".format(DATA_PACKAGE)
    return path, ""


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
    # 3. The icegrams-data package, the normal case
    packaged, reason = _data_package_model()
    if packaged is not None:
        return packaged
    # 4. The model fetched by the download step
    try:
        cached = _cached_model_path()
    except RuntimeError as e:
        raise ModelNotFoundError(str(e)) from e
    if _is_model_file(cached):
        return cached
    raise ModelNotFoundError(
        "The Icegrams trigram model was not found: {0}, and there is no "
        "downloaded model at {1}.\n"
        "The model comes with the {2} package, a dependency of icegrams; "
        "install it with\n\n    pip install \"{3}\"\n\n"
        "or download the model once by running\n\n    {4}\n\n"
        "or point the {5} environment variable at an existing model "
        "file.".format(
            reason,
            cached,
            DATA_PACKAGE,
            data_requirement(),
            DOWNLOAD_COMMAND,
            ENV_MODEL_FILE,
        )
    )
