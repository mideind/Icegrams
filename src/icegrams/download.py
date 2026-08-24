"""

Icegrams: A trigrams library for Icelandic

download.py

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


This module locates the compressed trigram model file (trigrams.bin).
The model is too large to bundle inside the Python package, so it is
downloaded from a GitHub release of the Icegrams repository on first
use and cached locally. The lookup order is:

    1. The file named by the ICEGRAMS_MODEL_FILE environment variable,
       if set.
    2. A model built in place in the package's resources directory
       (the output location of the icegrams.ngrams compressor).
    3. The local cache directory, downloading the model into it first
       if it isn't already there.

The cache location can be overridden with the ICEGRAMS_MODEL_DIR
environment variable, and the download source with ICEGRAMS_MODEL_URL.

"""

import hashlib
import os
import ssl
import sys
import tempfile
import urllib.error
import urllib.request

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

ENV_MODEL_FILE = "ICEGRAMS_MODEL_FILE"
ENV_MODEL_DIR = "ICEGRAMS_MODEL_DIR"
ENV_MODEL_URL = "ICEGRAMS_MODEL_URL"

_CHUNK_SIZE = 1024 * 1024
_PROGRESS_STEP = 20 * _CHUNK_SIZE

_PATH = os.path.dirname(__file__) or "."


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
    """Return the directory where the downloaded model is cached"""
    env_dir = os.environ.get(ENV_MODEL_DIR)
    if env_dir:
        return env_dir
    # Keyed by release tag, so bumping MODEL_RELEASE_TAG causes a fresh
    # download instead of reusing a stale cached model
    return os.path.join(_default_cache_dir(), MODEL_RELEASE_TAG)


def _ssl_context() -> ssl.SSLContext:
    """A TLS context that uses certifi's CA bundle when available.
    Some Python installations (notably the python.org installers on
    macOS) ship without CA certificates wired up, making every stdlib
    HTTPS request fail with CERTIFICATE_VERIFY_FAILED."""
    ctx = ssl.create_default_context()
    try:
        import certifi

        ctx.load_verify_locations(certifi.where())
    except ImportError:
        pass
    return ctx


def _download(url: str, dest: str, verify_checksum: bool) -> None:
    """Download the model file from url to dest, atomically"""
    dest_dir = os.path.dirname(dest)
    os.makedirs(dest_dir, exist_ok=True)
    print(
        "Downloading the Icegrams model ({0:.0f} MB) from\n{1}\nto {2}".format(
            MODEL_SIZE / 1e6, url, dest
        ),
        file=sys.stderr,
    )
    h = hashlib.sha256()
    received = 0
    next_report = _PROGRESS_STEP
    # Download into a temporary file in the destination directory and
    # move it into place once complete and verified, so a concurrent or
    # interrupted download can never leave a partial file at dest
    tmp_fd, tmp_path = tempfile.mkstemp(dir=dest_dir, suffix=".tmp")
    try:
        with os.fdopen(tmp_fd, "wb") as tmp:
            try:
                with urllib.request.urlopen(url, context=_ssl_context()) as response:
                    total = int(response.headers.get("Content-Length") or 0)
                    while True:
                        chunk = response.read(_CHUNK_SIZE)
                        if not chunk:
                            break
                        tmp.write(chunk)
                        h.update(chunk)
                        received += len(chunk)
                        if received >= next_report:
                            next_report += _PROGRESS_STEP
                            if total:
                                print(
                                    "...{0:.0f}%".format(100.0 * received / total),
                                    file=sys.stderr,
                                )
            except urllib.error.URLError as e:
                raise RuntimeError(
                    "Unable to download the Icegrams model from {0}: {1}\n"
                    "If you have a copy of the model file, point the "
                    "{2} environment variable at it, or set {3} to an "
                    "alternative download location.".format(
                        url, e, ENV_MODEL_FILE, ENV_MODEL_URL
                    )
                ) from e
        if received == 0:
            raise RuntimeError(
                "Downloaded an empty Icegrams model file from {0}".format(url)
            )
        if verify_checksum:
            if received != MODEL_SIZE or h.hexdigest() != MODEL_SHA256:
                raise RuntimeError(
                    "The downloaded Icegrams model file from {0} is corrupt "
                    "(size {1}, expected {2}); please retry".format(
                        url, received, MODEL_SIZE
                    )
                )
        os.replace(tmp_path, dest)
    except BaseException:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        raise
    print("Download complete", file=sys.stderr)


def model_filename() -> str:
    """Return the path of the trigrams.bin model file,
    downloading it first if necessary"""
    # 1. Explicit override
    env_file = os.environ.get(ENV_MODEL_FILE)
    if env_file:
        if not os.path.isfile(env_file):
            raise FileNotFoundError(
                "{0} points to {1}, which does not exist".format(
                    ENV_MODEL_FILE, env_file
                )
            )
        return env_file
    # 2. A model built in place by the compressor (development setups).
    # The size check skips placeholder files such as git-lfs pointers.
    local = os.path.join(_PATH, "resources", MODEL_BASENAME)
    if os.path.isfile(local) and os.path.getsize(local) > 1024 * 1024:
        return local
    # 3. The cached download, fetched on first use
    dest = os.path.join(model_dir(), MODEL_BASENAME)
    if not os.path.isfile(dest):
        env_url = os.environ.get(ENV_MODEL_URL)
        # The pinned checksum only applies to the default URL
        _download(env_url or MODEL_URL, dest, verify_checksum=not env_url)
    return dest
