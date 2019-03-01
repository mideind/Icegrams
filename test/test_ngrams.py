
from random import randint
import struct

from icegrams.ngrams import (
    BitArray, PackedList, MonotonicList, select, retrieve
)

def test_select():
    b = struct.pack("<I", int("0011001010001001", 2))
    assert select(b, 0) == 0
    assert select(b, 1) == 0
    assert select(b, 2) == 3
    assert select(b, 3) == 7
    assert select(b, 4) == 9
    assert select(b, 5) == 12
    assert select(b, 6) == 13

    b = struct.pack("<I", int("00110010100010010", 2))
    assert select(b, 0) == 0
    assert select(b, 1) == 1
    assert select(b, 2) == 4
    assert select(b, 3) == 8
    assert select(b, 4) == 10
    assert select(b, 5) == 13
    assert select(b, 6) == 14


def test_retrieve():
    b = struct.pack("<I", int("1001000110010100010010", 2))
    assert retrieve(b, 0, 0) == 0
    assert retrieve(b, 0, 1) == 0
    assert retrieve(b, 0, 2) == 2
    assert retrieve(b, 0, 3) == 2
    assert retrieve(b, 0, 4) == 2
    assert retrieve(b, 0, 5) == 18
    assert retrieve(b, 1, 4) == 9
    assert retrieve(b, 8, 4) == 5
    assert retrieve(b, 6, 4) == 4


def test_compressed_list():
    """ Test the compressed list classes """
    ba = BitArray()
    ba.append(10, 4)
    ba.append(3, 2)
    ba.append(0, 7)
    ba.append(1, 1)
    ba.append(100, 7)
    ba.append(100, 8)
    ba.append(1000, 10)
    ba.append(1000000, 20)
    ba.append(1000000000, 30)
    ba.append(0, 1)
    ba.finish()
    # print("BitArray is {0}".format("".join(hex(b)[2:] for b in ba.b)))
    assert ba.get(0, 4) == 10
    assert ba.get(4, 2) == 3
    assert ba.get(6, 7) == 0
    assert ba.get(13, 1) == 1
    assert ba.get(14, 7) == 100
    assert ba.get(21, 8) == 100
    assert ba.get(29, 10) == 1000
    assert ba.get(39, 20) == 1000000
    assert ba.get(59, 30) == 1000000000
    assert ba.get(89, 1) == 0
    try:
        ba.get(90, 1)
        assert False, "Should have raised IndexError"
    except IndexError:
        pass
    except:
        assert False, "Should have raised IndexError"
    assert len(ba) == (90 + 7) // 8

    for _ in range(100):
        test_list = [randint(0,2000000) for _ in range(randint(1,1000))]

        pl = PackedList()
        pl.compress(test_list)
        for i in range(len(test_list)):
            assert pl[i] == test_list[i]

        test_list.sort()
        ml = MonotonicList()
        ml.compress(test_list)
        for i in range(len(test_list)):
            assert ml[i] == test_list[i]

    # Test single-element list
    ml = MonotonicList()
    ml.compress([17])
    assert ml[0] == 17
