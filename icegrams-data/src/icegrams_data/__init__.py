"""

icegrams-data

The trigram model of the icegrams package: trigrams.bin, the compressed
n-gram database that icegrams memory-maps.

Copyright (C) 2026 Miðeind ehf.

This package is licensed under the MIT License; see LICENSE.txt.

This package has no functionality of its own; install icegrams and it
finds the model here. The model is built by the pipeline in the Icegrams
repository, published as the trigrams.bin asset of the GitHub release
named in MODEL_RELEASE_TAG, and staged into this package by
tools/data_package.py.

"""

import os

try:
    from importlib.metadata import version as _version

    __version__ = _version("icegrams-data")
except Exception:  # Not installed, e.g. imported from a source tree
    __version__ = "0.0.0"

# The GitHub release of the model in this package. icegrams uses the
# model only if this tag is the one it was released with.
MODEL_RELEASE_TAG = "model-2026.08"

MODEL_BASENAME = "trigrams.bin"


def model_path() -> str:
    """Return the path of the model file. The file is missing in a
    source checkout (and in an editable install of one) unless
    tools/data_package.py has staged it."""
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), MODEL_BASENAME)


__all__ = ["MODEL_RELEASE_TAG", "MODEL_BASENAME", "model_path", "__version__"]
