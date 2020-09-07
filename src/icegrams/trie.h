/*

   Icegrams: A trigrams library for Icelandic

   trie.h - C++ trie lookup module

   Copyright (C) 2019 Miðeind ehf.
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


   This module implements lookup of words in a compressed, memory-mapped
   trie structure, as well as utility functions for working with
   Elias-Fano compressed lists and bit arrays.

*/

#include <stdlib.h>
#include <string.h>
#include <stdint.h>


// Assert macro
#ifdef DEBUG
   #define ASSERT(x) assert(x)
#else
   #define ASSERT(x)
#endif


typedef unsigned int UINT;
typedef uint8_t BYTE;
typedef uint32_t UINT32;
typedef uint64_t UINT64;
typedef void VOID;

// Map a word to an offset within the memory mapped buffer
extern "C" UINT mapping(const BYTE* pbMap, const BYTE* pbWord);

// Return the index of the n-th 1-bit within the byte buffer pb
extern "C" UINT bitselect(const BYTE* pb, UINT n);
extern "C" UINT retrieve(const BYTE* pb, UINT nStart, UINT n);

// Look up an n-gram frequency from packed list of bucket indices
extern "C" UINT lookupFrequency(const BYTE* pb, UINT nQuantumSize, UINT nIndex);

// Look up items in a monotonic list of integers coded with Elias-Fano
extern "C" UINT64 lookupMonotonic(const BYTE* pb,
   UINT nQuantumSize, UINT nIndex);

extern "C" VOID lookupPairMonotonic(const BYTE* pb,
   UINT nQuantumSize, UINT nIndex,
   UINT64* pn1, UINT64* pn2);

// Look up items in a monotonic list of integers coded with
// partitioned Elias-Fano
extern "C" UINT64 lookupPartition(const BYTE* pb,
   UINT nOuterQuantum, UINT nInnerQuantum, UINT nIndex);

extern "C" VOID lookupPairPartition(const BYTE* pb,
   UINT nQuantumSize, UINT nInnerQuantum, UINT nIndex,
   UINT64* pn1, UINT64* pn2);

// Binary search over a monotonic Elias-Fano list of integers
extern "C" UINT searchMonotonic(const BYTE* pb,
   UINT nQuantumSize, UINT nP1, UINT nP2, UINT64 n);

// Binary search over a monotonic Elias-Fano list of integers
// encoded with a prefix sum in position [nP1-1]
extern "C" UINT searchMonotonicPrefix(const BYTE* pb,
   UINT nQuantumSize, UINT nP1, UINT nP2, UINT64 n);

// Binary search over a partitioned monotonic
// Elias-Fano list of integers
extern "C" UINT searchPartition(const BYTE* pb,
   UINT nOuterQuantum, UINT nInnerQuantum,
   UINT nP1, UINT nP2, UINT64 n);

// Binary search over a partitioned monotonic Elias-Fano
// list of integers encoded with a prefix sum in position [nP1-1]
extern "C" UINT searchPartitionPrefix(const BYTE* pb,
   UINT nOuterQuantum, UINT nInnerQuantum,
   UINT nP1, UINT nP2, UINT64 n);

