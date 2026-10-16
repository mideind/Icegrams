#!/usr/bin/env python3
"""
This file is retained for CFFI compilation.
All package metadata is defined in pyproject.toml.
"""

import platform
import sysconfig

from setuptools import setup

# The cffi_modules and zip_safe settings are not yet supported in pyproject.toml
# and must be defined here.

# Use the stable ABI (abi3) for CPython to create portable wheels that work
# across Python versions (3.10+). PyPy and free-threaded CPython don't support
# the stable ABI, so we create version-specific wheels for them. This must
# match the py_limited_api setting in src/icegrams/trie_build.py.
options: dict[str, str] = {}
if platform.python_implementation() == "CPython" and not sysconfig.get_config_var("Py_GIL_DISABLED"):
    options["py_limited_api"] = "cp310"

setup(
    zip_safe=False,
    cffi_modules=["src/icegrams/trie_build.py:ffibuilder"],
    options={"bdist_wheel": options},
)
