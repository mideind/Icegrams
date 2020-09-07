"""

    Icegrams: A trigrams library for Icelandic

    trie.py

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


    This module encapsulated the unigram trie logic used
    by ngrams.py to compress the unigram set and map
    unigrams to integer ids.

    Trie lookup is implemented in trie.cpp.

"""

from typing import Optional, IO, List
from collections import deque
from heapq import heappush, heappop, heapify
import struct


UINT32 = struct.Struct("<I")
UINT16 = struct.Struct("<H")
UINT8 = struct.Struct("<B")


class _Node:

    """ A Node within a Trie """

    __slots__ = ("fragment", "value", "children")

    def __init__(self, fragment: bytes, value: Optional[int]) -> None:
        # The key fragment that leads into this node (and value)
        self.fragment = fragment
        self.value = value
        # List of outgoing nodes
        self.children = None  # type: Optional[List[_Node]]

    def add(self, fragment: bytes, value: int) -> Optional[int]:
        """ Add the given remaining key fragment to this node """
        if len(fragment) == 0:
            if self.value is not None:
                # This key already exists: return its value
                return self.value
            # This was previously an internal node without value;
            # turn it into a proper value node
            self.value = value
            return None

        if self.children is None:
            # Trivial case: add an only child
            self.children = [_Node(fragment, value)]
            return None

        # Check whether we need to take existing child nodes into account
        lo = 0
        hi = len(self.children)
        ch = fragment[0]
        while hi > lo:
            mid = (lo + hi) // 2
            mid_ch = self.children[mid].fragment[0]
            if mid_ch < ch:
                lo = mid + 1
            elif mid_ch > ch:
                hi = mid
            else:
                break

        if hi == lo:
            # No common prefix with any child:
            # simply insert a new child into the sorted list
            # if lo > 0:
            #     assert self._children[lo - 1]._fragment[0] < fragment[0]
            # if lo < len(self._children):
            #     assert self._children[lo]._fragment[0] > fragment[0]
            self.children.insert(lo, _Node(fragment, value))
            return None

        assert hi > lo
        # Found a child with at least one common prefix character
        # noinspection PyUnboundLocalVariable
        child = self.children[mid]
        child_fragment = child.fragment
        # assert child_fragment[0] == ch
        # Count the number of common prefix characters
        common = 1
        len_fragment = len(fragment)
        len_child_fragment = len(child_fragment)
        while (
            common < len_fragment
            and common < len_child_fragment
            and fragment[common] == child_fragment[common]
        ):
            common += 1
        if common == len_child_fragment:
            # We have 'abcd' but the child is 'ab':
            # Recursively add the remaining 'cd' fragment to the child
            return child.add(fragment[common:], value)
        # Here we can have two cases:
        # either the fragment is a proper prefix of the child,
        # or the two diverge after #common characters
        # assert common < len_child_fragment
        # assert common <= len_fragment
        # We have 'ab' but the child is 'abcd',
        # or we have 'abd' but the child is 'acd'
        child.fragment = child_fragment[common:]  # 'cd'
        if common == len_fragment:
            # The fragment is a proper prefix of the child,
            # i.e. it is 'ab' while the child is 'abcd':
            # Break the child up into two nodes, 'ab' and 'cd'
            node = _Node(fragment, value)  # New parent 'ab'
            node.children = [child]  # Make 'cd' a child of 'ab'
        else:
            # The fragment and the child diverge,
            # i.e. we have 'abd' but the child is 'acd'
            new_fragment = fragment[common:]  # 'bd'
            # Make an internal node without a value
            node = _Node(fragment[0:common], None)  # 'a'
            # assert new_fragment[0] != child._fragment[0]
            if new_fragment[0] < child.fragment[0]:
                # Children: 'bd', 'cd'
                node.children = [_Node(new_fragment, value), child]
            else:
                node.children = [child, _Node(new_fragment, value)]
        # Replace 'abcd' in the original children list
        self.children[mid] = node
        return None

    def lookup(self, fragment: bytes) -> Optional[int]:
        """ Lookup the given key fragment in this node and its children
            as necessary """
        if not fragment:
            # We've arrived at our destination: return the value
            return self.value
        if self.children is None:
            # Nowhere to go: the key was not found
            return None
        # Note: The following could be a faster binary search,
        # but this lookup is not used in time critical code,
        # so the optimization is probably not worth it.
        for child in self.children:
            if fragment.startswith(child.fragment):
                # This is a continuation route: take it
                return child.lookup(fragment[len(child.fragment):])
        # No route matches: the key was not found
        return None

    def __str__(self) -> str:
        s = "Fragment: '{0!r}', value '{1}'\n".format(self.fragment, self.value)
        c = ["   {0}".format(child) for child in self.children] if self.children else []
        return s + "\n".join(c)


class Trie:

    """ Wrapper class for a radix (compact) trie data structure.
        Each node in the trie contains a prefix string, leading
        to its children. """

    def __init__(
        self, root_fragment: bytes=b"", reserve_zero_for_empty: bool=True
    ) -> None:
        # We reserve the 0 index for the empty string
        self._cnt = 1 if reserve_zero_for_empty else 0
        self._root = _Node(root_fragment, None)

    @property
    def root(self) -> _Node:
        """ Return the root node of the trie """
        return self._root

    def add(self, key: bytes, value: Optional[int]=None) -> int:
        """ Add the given (key, value) pair to the trie.
            Duplicates are not allowed and not added to the trie.
            If the value is None, it is set to the number of entries
            already in the trie, thereby making it function as
            an automatic generator of list indices. """
        if not key:
            return 0
        if value is None:
            value = self._cnt
        prev_value = self._root.add(key, value)
        if prev_value is not None:
            # The key was already found in the trie: return the
            # corresponding value
            return prev_value
        # Not already in the trie: add to the count and return the new value
        self._cnt += 1
        return value

    def get(self, key: bytes, default: Optional[int]=None) -> Optional[int]:
        """ Lookup the given key and return the associated value,
            or the default if the key is not found. """
        if not key:
            return 0
        value = self._root.lookup(key)
        return default if value is None else value

    def __getitem__(self, key: bytes) -> int:
        """ Lookup in square bracket notation """
        if not key:
            return 0
        value = self._root.lookup(key)
        if value is None:
            raise KeyError(key)
        return value

    def __len__(self) -> int:
        """ Return the number of unique keys within the trie,
            including the empty string sentinel that has the value 0 """
        return self._cnt

    def write(self, f: IO, *, verbose: bool=False) -> None:
        """ Write the unigram trie contents to a packed binary stream """
        # We assume that the alphabet can be represented in 7 bits
        todo = deque()  # type: deque
        node_cnt = 0
        single_char_node_count = 0
        multi_char_node_count = 0
        no_child_node_count = 0
        max_distance = 0

        def write_node(node: _Node, parent_loc: int) -> None:
            """ Write a single node to the packed binary stream,
                and fix up the parent's pointer to the location
                of this node """
            loc = f.tell()
            val = 0x007FFFFF if node.value is None else node.value
            assert val < 2**23
            nonlocal node_cnt, single_char_node_count, multi_char_node_count
            nonlocal no_child_node_count
            node_cnt += 1
            childless_bit = 0 if node.children else 0x40000000
            if len(node.fragment) <= 1:
                # Single-character fragment:
                # Pack it into 32 bits, with the high bit
                # being 1, the childless bit following it,
                # the fragment occupying the next 7 bits,
                # and the value occupying the remaining 23 bits
                if len(node.fragment) == 0:
                    chix = 0
                else:
                    chix = node.fragment[0]
                    assert chix != 0
                assert chix < 2**7
                f.write(
                    UINT32.pack(
                        0x80000000
                        | childless_bit
                        | (chix << 23)
                        | (val & 0x007FFFFF)
                    )
                )
                single_char_node_count += 1
                b = None
            else:
                # Multi-character fragment:
                # Store the value first, in 32 bits, and then
                # the fragment bytes with a trailing zero
                f.write(UINT32.pack(childless_bit | (val & 0x007FFFFF)))
                b = node.fragment
                multi_char_node_count += 1
            # Write the child nodes, if any
            if node.children:
                f.write(bytes([len(node.children)]))
                # Write a placeholder for the child pointer
                # - will be overwritten
                pos = f.tell()
                f.write(UINT32.pack(0xFFFFFFFF))
                for child in node.children:
                    todo.append((child, pos))
                    # Since the children are consecutive in the file,
                    # we only write the address of the first child
                    # and calculate the address of the others at run-time
                    pos = 0
            else:
                no_child_node_count += 1
            if b is not None:
                f.write(struct.pack("{0}s".format(len(b) + 1), b))
            if parent_loc > 0:
                # Fix up the parent
                end = f.tell()
                f.seek(parent_loc)
                f.write(UINT32.pack(loc))
                nonlocal max_distance
                if loc - parent_loc > max_distance:
                    max_distance = loc - parent_loc
                f.seek(end)

        write_node(self.root, 0)
        while todo:
            # Using a deque and popleft here causes child nodes
            # to be written consecutively in the output file
            write_node(*todo.popleft())

        if verbose:
            print(
                "Written {0:,} nodes, thereof {1:,} single-char nodes "
                "and {2:,} multi-char."
                .format(node_cnt, single_char_node_count, multi_char_node_count)
            )
            print("Childless nodes are {0:,}.".format(no_child_node_count))
            print("Maximum fixup distance is {0:,} bytes.".format(max_distance))

