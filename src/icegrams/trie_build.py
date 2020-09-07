"""

    Icegrams: A trigrams library for Icelandic

    CFFI builder for _trie module

    Copyright (C) 2020 Miðeind ehf.
    Original author: Vilhjálmur Þorsteinsson

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


    This module only runs at setup/installation time. It is invoked
    from setup.py as requested by the cffi_modules=[] parameter of the
    setup() function. It causes the _trie.*.so CFFI wrapper library
    to be built from its source in trie.cpp.

"""

import os
import platform
import cffi

# Don't change the name of this variable unless you
# change it in setup.py as well
ffibuilder = cffi.FFI()

_PATH = os.path.dirname(__file__) or "."
WINDOWS = platform.system() == "Windows"

# What follows is the actual Python-wrapped C interface to trie.*.so
# It must be kept in sync with trie.h

declarations = """

    typedef unsigned int UINT;
    typedef uint8_t BYTE;
    typedef uint32_t UINT32;
    typedef uint64_t UINT64;
    typedef void VOID;

    UINT mapping(const BYTE* pbMap, const BYTE* pbWord);
    UINT bitselect(const BYTE* pb, UINT n);
    UINT retrieve(const BYTE* pb, UINT nStart, UINT n);

    UINT lookupFrequency(const BYTE* pb,
        UINT nQuantumSize, UINT nIndex);

    UINT64 lookupMonotonic(const BYTE* pb,
        UINT nQuantumSize, UINT nIndex);
    VOID lookupPairMonotonic(const BYTE* pb,
        UINT nQuantumSize, UINT nIndex,
        UINT64* pn1, UINT64* pn2);

    UINT64 lookupPartition(const BYTE* pb,
        UINT nOuterQuantum, UINT nInnerQuantum, UINT nIndex);
    VOID lookupPairPartition(const BYTE* pb,
        UINT nQuantumSize, UINT nInnerQuantum, UINT nIndex,
        UINT64* pn1, UINT64* pn2);

    UINT searchMonotonic(const BYTE* pb,
        UINT nQuantumSize, UINT nP1, UINT nP2, UINT64 n);
    UINT searchMonotonicPrefix(const BYTE* pb,
        UINT nQuantumSize, UINT nP1, UINT nP2, UINT64 n);

    UINT searchPartition(const BYTE* pb,
        UINT nOuterQuantum, UINT nInnerQuantum,
        UINT nP1, UINT nP2, UINT64 n);
    UINT searchPartitionPrefix(const BYTE* pb,
        UINT nOuterQuantum, UINT nInnerQuantum,
        UINT nP1, UINT nP2, UINT64 n);

"""

# Do the magic CFFI incantations necessary to get CFFI and setuptools
# to compile trie.cpp at setup time, generate a .so library and
# wrap it so that it is callable from Python and PyPy as _trie

if WINDOWS:
    extra_compile_args = ["/Zc:offsetof-"]
else:
    # Adding -O3 to the compiler arguments doesn't seem to make
    # any discernible difference in lookup speed
    extra_compile_args = ["-std=c++11"]

ffibuilder.set_source(
    "icegrams._trie",
    # trie.cpp is written in C++ but must export a pure C interface.
    # This is the reason for the "extern 'C' { ... }" wrapper.
    'extern "C" {\n' + declarations + "\n}\n",
    source_extension=".cpp",
    sources=["src/icegrams/trie.cpp"],
    extra_compile_args=extra_compile_args,
)

ffibuilder.cdef(declarations)

if __name__ == "__main__":
    ffibuilder.compile(verbose=False)

