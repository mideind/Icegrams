#!/usr/bin/env python3

import re
import io
from glob import glob
from os.path import basename, splitext, dirname, join

from setuptools import find_packages, setup  # type: ignore


def read(*names, **kwargs):
    try:
        return io.open(
            join(dirname(__file__), *names), encoding=kwargs.get("encoding", "utf8")
        ).read()
    except (IOError, OSError):
        return ""


setup(
    name="icegrams",
    version="1.1.3",
    license="MIT",
    description="Trigram statistics for Icelandic",
    long_description="{0}\n{1}".format(
        re.compile("^.. start-badges.*^.. end-badges", re.M | re.S).sub(
            "", read("README.rst")
        ),
        re.sub(":[a-z]+:`~?(.*?)`", r"``\1``", read("CHANGELOG.rst")),
    ),
    author="Miðeind ehf",
    author_email="mideind@mideind.is",
    url="https://github.com/mideind/Icegrams",
    packages=find_packages("src"),
    package_dir={"": "src"},
    py_modules=[splitext(basename(path))[0] for path in glob("src/*.py")],
    package_data={"icegrams": ["py.typed"]},
    include_package_data=True,
    zip_safe=False,
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Operating System :: POSIX",
        "Operating System :: Unix",
        "Operating System :: MacOS",
        "Operating System :: Microsoft :: Windows",
        "Natural Language :: Icelandic",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Programming Language :: Python :: Implementation :: CPython",
        "Programming Language :: Python :: Implementation :: PyPy",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Utilities",
        "Topic :: Text Processing :: Linguistic",
    ],
    keywords=["nlp", "trigram", "ngram", "trigrams", "ngrams", "icelandic"],
    setup_requires=["cffi>=1.15.1"],
    install_requires=["cffi>=1.15.1"],
    cffi_modules=["src/icegrams/trie_build.py:ffibuilder"],
)
