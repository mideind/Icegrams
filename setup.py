#!/usr/bin/env python3

import platform
from glob import glob
from os.path import basename, splitext

from setuptools import find_packages, setup

# Use the stable ABI (abi3) for CPython to create portable wheels that work
# across Python versions (3.9+). PyPy doesn't support the stable ABI, so we
# create version-specific wheels for it. This must match the py_limited_api
# setting in src/icegrams/trie_build.py.
options: dict[str, str] = {}
if platform.python_implementation() == "CPython":
    options["py_limited_api"] = "cp39"

setup(
    packages=find_packages("src"),
    package_dir={"": "src"},
    py_modules=[splitext(basename(path))[0] for path in glob("src/*.py")],
    package_data={"icegrams": ["py.typed"]},
    include_package_data=True,
    zip_safe=False,
    setup_requires=["cffi>=1.15.1", "setuptools"],
    install_requires=["cffi>=1.15.1"],
    cffi_modules=["src/icegrams/trie_build.py:ffibuilder"],
    options={"bdist_wheel": options},
)
