#!/usr/bin/env python3

from glob import glob
from os.path import basename, splitext

from setuptools import find_packages, setup

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
)
