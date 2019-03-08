/*

   Icegrams: A trigrams library for Icelandic

   trie.h - C++ trie lookup module

   Copyright (C) 2019 Miðeind ehf.
   Original author: Vilhjálmur Þorsteinsson

      This program is free software: you can redistribute it and/or modify
      it under the terms of the GNU General Public License as published by
      the Free Software Foundation, either version 3 of the License, or
      (at your option) any later version.
      This program is distributed in the hope that it will be useful,
      but WITHOUT ANY WARRANTY; without even the implied warranty of
      MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
      GNU General Public License for more details.

   You should have received a copy of the GNU General Public License
   along with this program.  If not, see http://www.gnu.org/licenses/.


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

// Look up items in a monotonic list of integers coded with
// partitioned Elias-Fano
extern "C" UINT64 lookupPartition(const BYTE* pb,
   UINT nOuterQuantum, UINT nInnerQuantum, UINT nIndex);

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

