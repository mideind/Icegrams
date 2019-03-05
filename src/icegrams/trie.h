/*

   Reynir: Natural language processing for Icelandic

   C++ trie lookup module

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
   trie structure.

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
extern "C" UINT lookupFrequency(const BYTE* pb, UINT nQuantumSize, UINT nIndex);
extern "C" UINT64 lookupMonotonic(const BYTE* pb, UINT nQuantumSize, UINT nIndex);
extern "C" UINT64 lookupPartition(const BYTE* pb, UINT nOuterQuantum, UINT nInnerQuantum, UINT nIndex);

