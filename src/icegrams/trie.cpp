/*

   Icegrams: A trigrams library for Icelandic

   trie.cpp - C++ trie lookup module

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


   This module implements lookup of words in a trie structure
   within a compressed, memory-mapped byte buffer. It also includes
   a number of utility functions for working with compressed
   Elias-Fano sequences and arrays of bits.

*/

// #define DEBUG

#include <stdio.h>
#include <assert.h>
#include <time.h>

#include "trie.h"


#define TRUE 1
#define FALSE 0

#define NOT_FOUND 0xFFFFFFFF

typedef int INT;
typedef bool BOOL;
typedef uint16_t UINT16;


class Trie {

private:

#pragma pack(push, 1)

   struct Header {
      BYTE abSignature[16];
      UINT32 nTrieOffset;
   };

#pragma pack(pop)

   const BYTE* m_pbMap;
   const Header* m_pHeader;
   UINT m_nTrieRoot;
   UINT m_nTrieRootHeader;
   UINT m_nWordLen;
   const BYTE* m_pbWord;

   const BYTE* ptr(UINT nOffset) const
      { return this->m_pbMap + nOffset; }

   // Return the UINT32 at the given offset, as a native UINT
   UINT uintAt(UINT nOffset) const
      { return (UINT)*(UINT32*)this->ptr(nOffset); }

   // Return the UINT16 at the given offset, as a native UINT
   UINT uint16At(UINT nOffset) const
      { return (UINT)*(UINT16*)this->ptr(nOffset); }

   UINT childSize(UINT nNodeOffset) const;
   INT matches(UINT nNodeOffset, UINT nFragmentIndex) const;
   UINT lookup(UINT nNodeOffset, UINT nHdr, UINT nFragmentIndex) const;

public:

   Trie(const BYTE* pbMap);
   ~Trie();

   // Return the offset of the meanings of the given word within
   // the memory buffer, or 0xFFFFFFFF if not found (note that 0
   // is a valid offset).
   UINT mapping(const BYTE* pbWord);

};


INT Trie::matches(UINT nNodeOffset, UINT nFragmentIndex) const
{
   /* If the lookup fragment word[fragment_index:] matches the node,
      return the number of characters matched. Otherwise,
      return -1 if the node is lexicographically less than the
      lookup fragment, or 0 if the node is greater than the fragment.
      (The lexicographical ordering here is actually a comparison
      between the ordinal numbers of characters within an alphabet.)
   */
   UINT nHdr = this->uintAt(nNodeOffset);
   if (nHdr & 0x80000000) {
      // Single-character fragment
      BYTE ch = ((nHdr >> 23) & 0x7F); // Index of character in alphabet (can't be zero)
      BYTE chWord = this->m_pbWord[nFragmentIndex];
      if (ch == chWord) {
         // Match
         return 1;
      }
      return (ch > chWord) ? 0 : -1;
   }
   UINT nFrag;
   if (nHdr & 0x40000000) {
      // Childless node
      nFrag = nNodeOffset + sizeof(UINT32);
   }
   else {
      nFrag = nNodeOffset + sizeof(UINT32) + sizeof(BYTE) + sizeof(UINT32);
   }
   INT iMatched = 0;
   UINT nWordLen = (UINT)this->m_nWordLen;
   BYTE* pFrag = (BYTE*)(this->m_pbMap + nFrag);
   while (*pFrag && (nFragmentIndex + iMatched < nWordLen) &&
      (*pFrag == this->m_pbWord[nFragmentIndex + iMatched])) {
      pFrag++;
      iMatched++;
   }
   if (!*pFrag) {
      // Matched the entire fragment: success
      return iMatched;
   }
   if (nFragmentIndex + iMatched >= nWordLen) {
      // The node is longer and thus greater than the fragment
      return 0;
   }
   return (*pFrag > this->m_pbWord[nFragmentIndex + iMatched]) ? 0 : -1;
}

UINT Trie::childSize(UINT nNodeOffset) const {
   // Return the size of the node whose offset is nNodeOffset
   const UINT nHdr = this->uintAt(nNodeOffset);
   const UINT nChildrenSize = (nHdr & 0x40000000) ? 0 : sizeof(BYTE) + sizeof(UINT32);
   const UINT nStrLen = (nHdr & 0x80000000) ?
      0 : (UINT)strlen((char*)ptr(nNodeOffset + sizeof(UINT32) + nChildrenSize)) + 1;
   return (UINT)(sizeof(UINT32) + nChildrenSize + nStrLen);
}

UINT Trie::lookup(UINT nNodeOffset, UINT nHdr, UINT nFragmentIndex) const
{
   while (TRUE) {
      if (nFragmentIndex >= this->m_nWordLen) {
         // We've arrived at our destination:
         // return the associated value (unless this is an interim node)
         UINT nValue = nHdr & 0x007FFFFF;
         return (nValue == 0x007FFFFF) ? NOT_FOUND : nValue;
      }
      if (nHdr & 0x40000000) {
         // Childless node: nowhere to go
         return NOT_FOUND;
      }
      const UINT nNumChildren = (UINT)*this->ptr(nNodeOffset + sizeof(UINT32));
      const UINT nChildOffset = nNodeOffset + sizeof(UINT32) + sizeof(BYTE);
      // Binary search for a matching child node
      UINT nLo = 0;
      UINT nHi = nNumChildren;
      // Prepare a local array of child offsets, based on the
      // offset of the 0th child and adding the sizes of the
      // other children, since they are consecutive in the file.
      // Note that we cannot have more than 127 children of a single node.
      UINT nOffsets[127];
      nOffsets[0] = this->uintAt(nChildOffset);
      for (UINT i = 1; i < nNumChildren; i++)
         nOffsets[i] = nOffsets[i-1] + this->childSize(nOffsets[i-1]);
      BOOL fContinue = TRUE;
      do {
         if (nLo >= nHi) {
            // No child route matches
            return NOT_FOUND;
         }
         const UINT nMid = (nLo + nHi) / 2;
         const UINT nMidOffset = nOffsets[nMid];
         const INT iMatchLen = this->matches(nMidOffset, nFragmentIndex);
         if (iMatchLen > 0) {
             // Set a new starting point and restart from the top
             nNodeOffset = nMidOffset;
             nHdr = this->uintAt(nNodeOffset);
             nFragmentIndex += iMatchLen;
             fContinue = FALSE;
         }
         else
         if (iMatchLen < 0) {
            nLo = nMid + 1;
         }
         else {
            nHi = nMid;
         }
      } while (fContinue);
   }
   // Should never get here
   assert(FALSE);
}

Trie::Trie(const BYTE* pbMap)
   : m_pbMap(pbMap), m_pHeader((const Header*)pbMap),
      m_nTrieRoot(m_pHeader->nTrieOffset),
      m_nTrieRootHeader(this->uintAt(m_nTrieRoot)),
      m_nWordLen(0),
      m_pbWord(NULL)
{
}

Trie::~Trie()
{
}

UINT Trie::mapping(const BYTE* pbWord)
{
   // Note that calls to mapping() on the same Trie instance
   // are not re-entrant. Trie is designed to be instantiated
   // on the stack, per-thread, for each sequence of mapping calls.
   if (!pbWord) {
      return NOT_FOUND;
   }
   this->m_pbWord = pbWord;
   this->m_nWordLen = (UINT)strlen((const char*)pbWord);
   return this->lookup(this->m_nTrieRoot, this->m_nTrieRootHeader, 0);
}

UINT mapping(const BYTE* pbMap, const BYTE* pbWord)
{
   Trie trie(pbMap);
   return trie.mapping(pbWord);
}

UINT bitselect(const BYTE* pb, UINT n)
{
   /* Return the bit index of the n-th set bit in the byte array b */
   UINT nIx = 0;
   BYTE bMask = 0x01;
   while (n) {
      // Search for the next set bit
      while (!(*pb & bMask)) {
         // Skipping a 0 bit
         nIx++;
         bMask <<= 1;
         if (!bMask) {
            pb++;
            bMask = 0x01;
         }
      }
      n--;
      if (n) {
         // Skipping a 1 bit
         nIx++;
         bMask <<= 1;
         if (!bMask) {
            pb++;
            bMask = 0x01;
         }
      }
   }
   return nIx;
}

UINT retrieve(const BYTE* pb, UINT nStart, UINT n)
{
   /* Retrieve the contents of the bits starting
      at bit index start from the beginning of byte array b
      (where the least significant bit has index 0)
      and spanning the given number of bits */
   if (!n)
      return 0;
   pb += nStart >> 3;
   UINT nBuf = ((UINT)*pb) >> (nStart & 0x07);
   UINT nBits = 8 - (nStart & 0x07);
   while (nBits < n) {
      nBuf |= *++pb << nBits;
      nBits += 8;
   }
   return nBuf & ((1 << n) - 1);
}

// Look-up table of counts of 1-bits per byte value
static const BYTE _BIT_COUNT[256] = {
    0x00, 0x01, 0x01, 0x02, 0x01, 0x02, 0x02, 0x03,
    0x01, 0x02, 0x02, 0x03, 0x02, 0x03, 0x03, 0x04,
    0x01, 0x02, 0x02, 0x03, 0x02, 0x03, 0x03, 0x04,
    0x02, 0x03, 0x03, 0x04, 0x03, 0x04, 0x04, 0x05,
    0x01, 0x02, 0x02, 0x03, 0x02, 0x03, 0x03, 0x04,
    0x02, 0x03, 0x03, 0x04, 0x03, 0x04, 0x04, 0x05,
    0x02, 0x03, 0x03, 0x04, 0x03, 0x04, 0x04, 0x05,
    0x03, 0x04, 0x04, 0x05, 0x04, 0x05, 0x05, 0x06,
    0x01, 0x02, 0x02, 0x03, 0x02, 0x03, 0x03, 0x04,
    0x02, 0x03, 0x03, 0x04, 0x03, 0x04, 0x04, 0x05,
    0x02, 0x03, 0x03, 0x04, 0x03, 0x04, 0x04, 0x05,
    0x03, 0x04, 0x04, 0x05, 0x04, 0x05, 0x05, 0x06,
    0x02, 0x03, 0x03, 0x04, 0x03, 0x04, 0x04, 0x05,
    0x03, 0x04, 0x04, 0x05, 0x04, 0x05, 0x05, 0x06,
    0x03, 0x04, 0x04, 0x05, 0x04, 0x05, 0x05, 0x06,
    0x04, 0x05, 0x05, 0x06, 0x05, 0x06, 0x06, 0x07,
    0x01, 0x02, 0x02, 0x03, 0x02, 0x03, 0x03, 0x04,
    0x02, 0x03, 0x03, 0x04, 0x03, 0x04, 0x04, 0x05,
    0x02, 0x03, 0x03, 0x04, 0x03, 0x04, 0x04, 0x05,
    0x03, 0x04, 0x04, 0x05, 0x04, 0x05, 0x05, 0x06,
    0x02, 0x03, 0x03, 0x04, 0x03, 0x04, 0x04, 0x05,
    0x03, 0x04, 0x04, 0x05, 0x04, 0x05, 0x05, 0x06,
    0x03, 0x04, 0x04, 0x05, 0x04, 0x05, 0x05, 0x06,
    0x04, 0x05, 0x05, 0x06, 0x05, 0x06, 0x06, 0x07,
    0x02, 0x03, 0x03, 0x04, 0x03, 0x04, 0x04, 0x05,
    0x03, 0x04, 0x04, 0x05, 0x04, 0x05, 0x05, 0x06,
    0x03, 0x04, 0x04, 0x05, 0x04, 0x05, 0x05, 0x06,
    0x04, 0x05, 0x05, 0x06, 0x05, 0x06, 0x06, 0x07,
    0x03, 0x04, 0x04, 0x05, 0x04, 0x05, 0x05, 0x06,
    0x04, 0x05, 0x05, 0x06, 0x05, 0x06, 0x06, 0x07,
    0x04, 0x05, 0x05, 0x06, 0x05, 0x06, 0x06, 0x07,
    0x05, 0x06, 0x06, 0x07, 0x06, 0x07, 0x07, 0x08,
};

static inline UINT bitcount32(UINT32 v)
{
   /* Return the number of 1-bits in a 32-bit unsigned integer
      See: http://graphics.stanford.edu/~seander/bithacks.html */
   v = v - ((v >> 1) & 0x55555555);
   v = (v & 0x33333333) + ((v >> 2) & 0x33333333);
   v = (v + (v >> 4)) & 0x0F0F0F0F;
   // The following is equivalent to v % 255
   return (v * 0x01010101) >> 24;
}

UINT lookupFrequency(const BYTE* pb,
   UINT nQuantumSize, UINT nIndex) {
   /* Look up the frequency rank at index nIndex from
      the memory area pointed to by pb */

   UINT nNumRanks = (UINT)*(UINT16*)pb;
   const UINT16* pnRanks = (const UINT16*)(pb + sizeof(UINT16));
   // Skip past the ranks
   const BYTE* p = pb + sizeof(UINT16) * (nNumRanks + 1);
   // Skip past the quantized frequency index
   const UINT32* pnIndex = (const UINT32*)p;
   p += (1 + *pnIndex) * sizeof(UINT32);
   // Point to the first index entry
   pnIndex++;
   // Number of codeword bytes
   UINT nCwBytes = (UINT)*(UINT32*)p;
   // Skip past the cwbits size and the cwbits themselves
   // to point at the startbits
   p += sizeof(UINT32) + nCwBytes;
   UINT nSkip = nIndex;
   // First, skip past frequency indices (start bits) by quantum number
   UINT nQ = nIndex / nQuantumSize;
   if (nQ) {
      // Get the number of bits to skip
      UINT nBcnt = pnIndex[nQ - 1];
      // Move past the whole bytes
      p += nBcnt >> 3;
      // Subtract the quanta we're skipping
      BYTE bMask = (1 << (nBcnt & 0x07)) - 1;
      nSkip -= nQ * nQuantumSize - (UINT)_BIT_COUNT[*p & bMask];
   }
   // Then, skip bytes in the start bit sequence while
   // they contain fewer 1-bits than the ones we
   // are trying to skip
   while (1) {
      UINT nBcnt = (UINT)_BIT_COUNT[*p];
      if (nBcnt >= nSkip)
          break;
      p++;
      nSkip -= nBcnt;
   }
   // The byte containing the bit we want is now at *p
   // We add 1 to the bit index (skip) here because
   // the 1-bits are numbered from 1 (index 0 is
   // always the least significant bit)
   UINT nStart = bitselect(p, nSkip + 1);
   UINT nEnd = bitselect(p, nSkip + 2);
   // Find out the number of bits, i.e. the log2 used when packing
   UINT nLog2 = nEnd - nStart;
   // Go back to the cwbits array to retrieve the code word
   UINT nCw = retrieve(p - nCwBytes, nStart, nLog2);
   // Reverse the codeword formula from write_frequencies()
   nIndex = nCw - 2 + (1 << nLog2);
   // Return the frequency rank
   return (UINT)pnRanks[nIndex];
}

#pragma pack(push, 1)

// The header of a packed MonotonicList instance
struct MonoListHeader {
   UINT32 n;               // Number of elements in the list
   UINT16 nLb, nHb;        // The number of low and high bits
   UINT32 anHbufIndex[0];  // Array of indices into the high-bit buffer
};

#pragma pack(pop)

UINT64 lookupMonotonic(const BYTE* pb,
   UINT nQuantumSize, UINT nIndex)
{
   /* Returns the integer at index ix within the sequence */
   // Extract information about the monotonic (Elias-Fano) list
   // from its header
   struct MonoListHeader* ph = (struct MonoListHeader*)pb;
   // Number of items in the list
   UINT n = (UINT)ph->n;
   // Number of low and high bits
   UINT nLb = (UINT)ph->nLb;
   UINT nHb = (UINT)ph->nHb;
   // High-bits buffer indices
   UINT32* pnHbufIndex = &ph->anHbufIndex[0];
   UINT nHbufSize = nHb ? ((n - 1) / nQuantumSize) * sizeof(pnHbufIndex[0]) : 0;
   // Move the byte pointer past the header and the indices
   pb += sizeof(MonoListHeader) + nHbufSize;
   // Low bit mask
   UINT nLowMask = (1 << nLb) - 1;
   // Index of first low bit to read
   UINT nLowBitIndex = nIndex * nLb;
   // Calculate the starting byte index
   UINT nBy = nLowBitIndex >> 3;
   // Calculate the starting bit index within the byte
   // (position 0 is the leftmost/least significant bit)
   nLowBitIndex &= 0x07;
   // If end > 8 we need to fetch more than one byte.
   // This is either because we are using more than 8 lower bits,
   // or because we are starting from a nonzero index within the byte,
   // or both.
   UINT nEnd = nLb + nLowBitIndex;
   UINT64 nBits = 0;
   UINT nBitCount = 0;
   while (1) {
      nBits |= ((UINT64)pb[nBy]) << nBitCount;
      nBitCount += 8;
      if (nBitCount >= nEnd)
         break;
      nBy += 1;
   }
   // Extract the low part from the accumulated bits
   UINT64 nLowPart = (nBits >> nLowBitIndex) & nLowMask;
   if (!nHb)
      // No high bits: we're done
      return nLowPart;
   UINT64 nHighPart = 0;
   // Now for the high part
   // Find out where it starts
   nBy = (n * nLb + 7) >> 3;
   UINT nHpos = nIndex;
   BYTE bMask = 0xFF;
   if (nIndex >= nQuantumSize) {
      // Find out which quantum we're looking for
      UINT nQ = nIndex / nQuantumSize;
      // At the quantum index point, we had written
      // q*QUANTUM_SIZE 1-nBits to the high buffer and
      // had advanced to byte hby, which means that we
      // had written a total of hby * 8 nBits and therefore
      // (hby * 8) - (q * QUANTUM_SIZE) 0-nBits
      UINT nHbit = (UINT)pnHbufIndex[nQ-1];
      nBy += nHbit >> 3;
      bMask = 0xFF ^ ((1 << (nHbit & 0x07)) - 1);
      nHpos -= nQ * nQuantumSize;
      nHighPart = (nHbit & ~0x07) - nQ * nQuantumSize;
   }
   while (1) {
      // How many 1 bits do we have in the current byte
      // of the high part?
      UINT nBcnt = (UINT)_BIT_COUNT[pb[nBy] & bMask];
      if (nHpos < nBcnt)
         // The bit we're looking for is somewhere in this byte
         break;
      bMask = 0xFF;
      // Increment the high part by the number of skipped zeroes
      nHighPart += 8 - nBcnt;
      // Skip this byte
      nHpos -= nBcnt;
      nBy += 1;
   }
   // Now we need to find our 1-bit
   nBy = (UINT)(pb[nBy] & bMask);
   while (1) {
      if (nBy & 1) {
         if (nHpos == 0)
            // Our job is done
            break;
         // We are closer to the target
         nHpos -= 1;
      }
      else
         // Found a zero: increment high part
         nHighPart += 1;
      // Go look at the next bit
      nBy >>= 1;
   }
   return (nHighPart << nLb) | nLowPart;
}

VOID lookupPairMonotonic(const BYTE* pb,
   UINT nQuantumSize, UINT nIndex,
   UINT64* pn1, UINT64* pn2)
{
   if (!pn1 || !pn2)
      return;
   /* Returns the integer at index ix within the sequence */
   // Extract information about the monotonic (Elias-Fano) list
   // from its header
   struct MonoListHeader* ph = (struct MonoListHeader*)pb;
   // Number of items in the list
   UINT n = (UINT)ph->n;
   // Number of low and high bits
   UINT nLb = (UINT)ph->nLb;
   UINT nHb = (UINT)ph->nHb;
   // High-bits buffer indices
   UINT32* pnHbufIndex = &ph->anHbufIndex[0];
   UINT nHbufSize = nHb ? ((n - 1) / nQuantumSize) * sizeof(pnHbufIndex[0]) : 0;
   // Move the byte pointer past the header and the indices
   pb += sizeof(MonoListHeader) + nHbufSize;
   // Low bit mask
   UINT nLowMask = (1 << nLb) - 1;
   // Index of first low bit to read
   UINT nLowBitIndex = nIndex * nLb;
   // Calculate the starting byte index
   UINT nBy = nLowBitIndex >> 3;
   // Calculate the starting bit index within the byte
   // (position 0 is the leftmost/least significant bit)
   nLowBitIndex &= 0x07;
   // If end > 8 we need to fetch more than one byte.
   // This is either because we are using more than 8 lower bits,
   // or because we are starting from a nonzero index within the byte,
   // or both.
   UINT nEnd = nLb + nLowBitIndex;
   UINT64 nBits = 0;
   UINT nBitCount = 0;
   while (1) {
      nBits |= ((UINT64)pb[nBy]) << nBitCount;
      nBitCount += 8;
      if (nBitCount >= nEnd)
         break;
      nBy += 1;
   }
   // Extract the low part of pn1 from the accumulated bits
   nBits >>= nLowBitIndex;
   UINT64 nLowPart1 = nBits & nLowMask;
   // Continue to pn2
   nBits >>= nLb;
   nBitCount -= nLowBitIndex + nLb;
   while (nBitCount < nLb) {
      // We don't have enough bits for pn2; add them
      nBits |= ((UINT64)pb[++nBy]) << nBitCount;
      nBitCount += 8;
   }
   // Extract the low part of pn2 from the accumulated bits
   UINT64 nLowPart2 = nBits & nLowMask;
   if (!nHb) {
      // No high bits: we're done
      *pn1 = nLowPart1;
      *pn2 = nLowPart2;
      return;
   }
   UINT64 nHighPart1 = 0;
   UINT64 nHighPart2 = 0;
   // Now for the high part
   // Find out where it starts
   nBy = (n * nLb + 7) >> 3;
   UINT nHpos = nIndex;
   BYTE bMask = 0xFF;
   if (nIndex >= nQuantumSize) {
      // Find out which quantum we're looking for
      UINT nQ = nIndex / nQuantumSize;
      // At the quantum index point, we had written
      // q*QUANTUM_SIZE 1-nBits to the high buffer and
      // had advanced to byte hby, which means that we
      // had written a total of hby * 8 nBits and therefore
      // (hby * 8) - (q * QUANTUM_SIZE) 0-nBits
      UINT nHbit = (UINT)pnHbufIndex[nQ-1];
      nBy += nHbit >> 3;
      bMask = 0xFF ^ ((1 << (nHbit & 0x07)) - 1);
      nHpos -= nQ * nQuantumSize;
      nHighPart1 = (nHbit & ~0x07) - nQ * nQuantumSize;
   }
   UINT nBcnt = (UINT)_BIT_COUNT[pb[nBy] & bMask];
   while (1) {
      // How many 1 bits do we have in the current byte
      // of the high part?
      if (nHpos < nBcnt)
         // The bit we're looking for is somewhere in this byte
         break;
      // Increment the high part by the number of skipped zeroes
      nHighPart1 += 8 - nBcnt;
      // Skip this byte
      nHpos -= nBcnt;
      nBy += 1;
      nBcnt = (UINT)_BIT_COUNT[pb[nBy]];
      bMask = 0xFF;
   }
   // Continue from this point to retrieve pn2, from nHpos+1
   nHighPart2 = nHighPart1;
   UINT nBy2 = nBy;
   UINT nHpos2 = nHpos + 1;
   BYTE bMask2 = bMask;
   while (1) {
      // How many 1 bits do we have in the current byte
      // of the high part?
      if (nHpos2 < nBcnt)
         // The bit we're looking for is somewhere in this byte
         break;
      // Increment the high part by the number of skipped zeroes
      nHighPart2 += 8 - nBcnt;
      // Skip this byte
      nHpos2 -= nBcnt;
      nBy2 += 1;
      nBcnt = (UINT)_BIT_COUNT[pb[nBy2]];
      bMask2 = 0xFF;
   }
   // Now we need to find the 1-bit for pn1
   nBy = (UINT)(pb[nBy] & bMask);
   while (1) {
      if (nBy & 1) {
         if (nHpos == 0)
            // Our job is done
            break;
         // We are closer to the target
         nHpos -= 1;
      }
      else
         // Found a zero: increment high part
         nHighPart1 += 1;
      // Go look at the next bit
      nBy >>= 1;
   }
   // Now we need to find the 1-bit for pn2
   nBy = (UINT)(pb[nBy2] & bMask2);
   while (1) {
      if (nBy & 1) {
         if (nHpos2 == 0)
            // Our job is done
            break;
         // We are closer to the target
         nHpos2 -= 1;
      }
      else
         // Found a zero: increment high part
         nHighPart2 += 1;
      // Go look at the next bit
      nBy >>= 1;
   }
   *pn1 = (nHighPart1 << nLb) | nLowPart1;
   *pn2 = (nHighPart2 << nLb) | nLowPart2;
}

UINT searchMonotonic(const BYTE* pb,
   UINT nQuantumSize, UINT nP1, UINT nP2,
   UINT64 n)
{
   // Do a binary search for the value n within the range [nP1, nP2> in the Elias-Fano list
   while (1) {
      if (nP1 >= nP2)
         return (UINT)0xFFFFFFFF;
      UINT nMid = (nP1 + nP2) / 2;
      UINT64 nThis = lookupMonotonic(pb, nQuantumSize, nMid);
      if (nThis == n)
         return nMid;
      if (nThis > n)
         nP2 = nMid;
      else
         nP1 = nMid + 1;
   }
}

UINT searchMonotonicPrefix(const BYTE* pb,
   UINT nQuantumSize, UINT nP1, UINT nP2,
   UINT64 n)
{
   // Add a prefix sum to the value n before searching for it in the Elias-Fano list
   if (nP1 >= nP2)
      return (UINT)0xFFFFFFFF;
   if (nP1)
      n += lookupMonotonic(pb, nQuantumSize, nP1 - 1);
   return searchMonotonic(pb, nQuantumSize, nP1, nP2, n);
}

#pragma pack(push, 1)

// The header of a packed PartitionedMonotonicList instance
struct PartitionListHeader {
   UINT32 nChunks;         // Number of chunks
   UINT32 anChunkIndex[0]; // Array of chunk offsets
};

#pragma pack(pop)

UINT64 lookupPartition(const BYTE* pb,
   UINT nOuterQuantum, UINT nInnerQuantum,
   UINT nIndex)
{
   // Look up a value from a partitioned monotonic (Elias-Fano) list
   UINT nQ = nIndex / nOuterQuantum;
   UINT nR = nIndex % nOuterQuantum;
   const PartitionListHeader* pHeader = (const PartitionListHeader*)pb;
   const BYTE* pbOuter = pb + sizeof(UINT32) * (1 + pHeader->nChunks);
   const BYTE* pbInner = pb + pHeader->anChunkIndex[nQ];
   UINT64 nPrefix = nQ ? lookupMonotonic(pbOuter, nInnerQuantum, nQ - 1) : 0;
   return nPrefix + lookupMonotonic(pbInner, nInnerQuantum, nR);
}

VOID lookupPairPartition(const BYTE* pb,
   UINT nOuterQuantum, UINT nInnerQuantum,
   UINT nIndex, UINT64* pn1, UINT64* pn2)
{
   // Look up a value from a partitioned monotonic (Elias-Fano) list
   UINT nR = nIndex % nOuterQuantum;
   if (nR == nOuterQuantum - 1) {
      // Looking up the last element in a quantum: we need two lookups
      *pn1 = lookupPartition(pb, nOuterQuantum, nInnerQuantum, nIndex);
      *pn2 = lookupPartition(pb, nOuterQuantum, nInnerQuantum, nIndex + 1);
      return;
   }
   UINT nQ = nIndex / nOuterQuantum;
   const PartitionListHeader* pHeader = (const PartitionListHeader*)pb;
   const BYTE* pbOuter = pb + sizeof(UINT32) * (1 + pHeader->nChunks);
   const BYTE* pbInner = pb + pHeader->anChunkIndex[nQ];
   UINT64 nPrefix = nQ ? lookupMonotonic(pbOuter, nInnerQuantum, nQ - 1) : 0;
   lookupPairMonotonic(pbInner, nInnerQuantum, nR, pn1, pn2);
   *pn1 += nPrefix;
   *pn2 += nPrefix;
}

UINT searchPartition(const BYTE* pb,
   UINT nOuterQuantum, UINT nInnerQuantum,
   UINT nP1, UINT nP2, UINT64 n)
{
   // Do a binary search for the value n within the range [nP1, nP2> in the
   // partitioned Elias-Fano list
   while (1) {
      if (nP1 >= nP2)
         return (UINT)0xFFFFFFFF;
      UINT nMid = (nP1 + nP2) / 2;
      UINT64 nThis = lookupPartition(pb, nOuterQuantum, nInnerQuantum, nMid);
      if (nThis == n)
         return nMid;
      if (nThis > n)
         nP2 = nMid;
      else
         nP1 = nMid + 1;
   }
}

UINT searchPartitionPrefix(const BYTE* pb,
   UINT nOuterQuantum, UINT nInnerQuantum,
   UINT nP1, UINT nP2, UINT64 n)
{
   // Add a prefix sum to the value n before searching for it in
   // the partitioned Elias-Fano list
   if (nP1 >= nP2)
      return (UINT)0xFFFFFFFF;
   if (nP1)
      n += lookupPartition(pb, nOuterQuantum, nInnerQuantum, nP1 - 1);
   return searchPartition(pb, nOuterQuantum, nInnerQuantum, nP1, nP2, n);
}
