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


This module implements the fallback setup step that downloads the
compressed trigram model file (trigrams.bin). Since icegrams 2.2.0
the model is installed with the icegrams-data package, a dependency
of icegrams, and this step is not needed. It remains for installations
without that package (e.g. pip install --no-deps, or machines that
cannot reach PyPI) and for icegrams 2.0 and 2.1. The model is also
published as a GitHub release asset, and this step fetches it from
there into a per-user cache:

    python -m icegrams.download

or icegrams.download.download_model() from Python. If the installed
icegrams-data package already holds the model, both say so and
download nothing (unless a directory, a URL or --force is given).

This is deliberately separate from runtime: creating an Ngrams
instance never touches the network, it only looks for the model file
(see model.py) and raises ModelNotFoundError if it isn't present.

The download destination can be overridden with the ICEGRAMS_MODEL_DIR
environment variable (or --dir), and the download source with
ICEGRAMS_MODEL_URL (or --url).

"""

from typing import Optional

import argparse
import os
import sys

from .model import (
    MODEL_RELEASE_TAG,
    MODEL_BASENAME,
    MODEL_URL,
    MODEL_SIZE,
    MODEL_SHA256,
    ENV_MODEL_FILE,
    ENV_MODEL_DIR,
    ENV_MODEL_URL,
    DOWNLOAD_COMMAND,
    _cached_model_path,
    _data_package_model,
    _is_model_file,
)

_CHUNK_SIZE = 1024 * 1024
_PROGRESS_STEP = 20 * _CHUNK_SIZE
_TIMEOUT_SECONDS = 60.0


def _ssl_context():  # type: ignore[no-untyped-def]
    """A TLS context that uses certifi's CA bundle when available.
    Some Python installations (notably the python.org installers on
    macOS) ship without CA certificates wired up, making every stdlib
    HTTPS request fail with CERTIFICATE_VERIFY_FAILED. certifi is a
    declared dependency, but fall back to the system store if it is
    missing (e.g. an install with --no-deps) rather than refusing."""
    import ssl

    ctx = ssl.create_default_context()
    try:
        import certifi
    except ImportError:
        print(
            "Warning: certifi is not installed; using the system CA store",
            file=sys.stderr,
        )
    else:
        ctx.load_verify_locations(certifi.where())
    return ctx


def _fetch(url: str, dest: str, verify_checksum: bool) -> None:
    """Download the model file from url to dest, atomically"""
    # Network imports are deferred so that importing icegrams
    # doesn't require the ssl module at all
    import hashlib
    import http.client
    import tempfile
    import urllib.request

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
    total = 0
    next_report = _PROGRESS_STEP
    # Download into a temporary file in the destination directory and
    # move it into place once complete and verified, so an interrupted
    # download can never leave a partial file at dest
    tmp_fd, tmp_path = tempfile.mkstemp(dir=dest_dir, suffix=".tmp")
    try:
        try:
            with os.fdopen(tmp_fd, "wb") as tmp:
                with urllib.request.urlopen(
                    url, timeout=_TIMEOUT_SECONDS, context=_ssl_context()
                ) as response:
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
        except (OSError, http.client.HTTPException) as e:
            # OSError covers urllib.error.URLError, socket timeouts,
            # connection resets and local filesystem errors
            raise RuntimeError(
                "Unable to download the Icegrams model from {0}: {1}\n"
                "If you have a copy of the model file, point the "
                "{2} environment variable at it, or set {3} to an "
                "alternative download location.".format(
                    url, e, ENV_MODEL_FILE, ENV_MODEL_URL
                )
            ) from e
        if total and received != total:
            raise RuntimeError(
                "The download of the Icegrams model from {0} was cut short "
                "({1} of {2} bytes received); please retry".format(
                    url, received, total
                )
            )
        if verify_checksum:
            if received != MODEL_SIZE or h.hexdigest() != MODEL_SHA256:
                raise RuntimeError(
                    "The downloaded Icegrams model file from {0} is corrupt "
                    "(size {1}, expected {2}); please retry".format(
                        url, received, MODEL_SIZE
                    )
                )
        elif not _is_model_file(tmp_path):
            raise RuntimeError(
                "The file downloaded from {0} is not an Icegrams model "
                "file".format(url)
            )
        # mkstemp() creates the file readable by the owner only; make
        # the model readable by everyone so that a cache populated by
        # one user (e.g. during a container build) is usable by others
        os.chmod(tmp_path, 0o644)
        os.replace(tmp_path, dest)
    except BaseException:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        raise
    print("Download complete", file=sys.stderr)


def download_model(
    url: Optional[str] = None, dest_dir: Optional[str] = None, force: bool = False
) -> str:
    """Download the trigram model, if it isn't already present, and
    return its path. This is a one-time setup step, needed only if the
    icegrams-data package is not installed: if it is, and none of url,
    dest_dir and force is given, its model's path is returned instead.

    url: where to fetch the model from; defaults to the ICEGRAMS_MODEL_URL
        environment variable, or else the official GitHub release.
        The pinned checksum is only verified for the official URL.
    dest_dir: base directory for the model; defaults to ICEGRAMS_MODEL_DIR
        or the platform's per-user cache directory. The model is stored
        in a subdirectory named after the model release tag.
    force: re-download even if a model is already present.
    """
    if not (url or dest_dir or force):
        packaged, _ = _data_package_model()
        if packaged is not None:
            print(
                "The Icegrams model is provided by the installed icegrams-data "
                "package at " + packaged + "; nothing to download",
                file=sys.stderr,
            )
            return packaged
    if dest_dir:
        dest = os.path.join(dest_dir, MODEL_RELEASE_TAG, MODEL_BASENAME)
    else:
        dest = _cached_model_path()
    env_url = os.environ.get(ENV_MODEL_URL)
    url = url or env_url or MODEL_URL
    official = url == MODEL_URL
    if not force and _is_model_file(dest):
        if not official or os.path.getsize(dest) == MODEL_SIZE:
            print("The Icegrams model is already present at " + dest, file=sys.stderr)
            return dest
        print("Replacing incomplete model file at " + dest, file=sys.stderr)
    _fetch(url, dest, verify_checksum=official)
    return dest


def main() -> int:
    parser = argparse.ArgumentParser(
        prog=DOWNLOAD_COMMAND,
        description="Download the Icegrams trigram model ({0}, {1:.0f} MB). "
        "Not needed if the icegrams-data package, a dependency of icegrams, "
        "is installed: it holds the model.".format(
            MODEL_RELEASE_TAG, MODEL_SIZE / 1e6
        ),
    )
    parser.add_argument(
        "--dir",
        metavar="DIR",
        help="base directory to store the model in "
        "(default: ${0} or the per-user cache directory)".format(ENV_MODEL_DIR),
    )
    parser.add_argument(
        "--url",
        metavar="URL",
        help="alternative URL to download the model from "
        "(default: ${0} or the official GitHub release)".format(ENV_MODEL_URL),
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="re-download even if the model is already present",
    )
    args = parser.parse_args()
    try:
        path = download_model(url=args.url, dest_dir=args.dir, force=args.force)
    except RuntimeError as e:
        print("Error: {0}".format(e), file=sys.stderr)
        return 1
    print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
