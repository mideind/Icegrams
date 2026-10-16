import math
import platform
from random import randint

import pytest

from icegrams import Ngrams, ModelNotFoundError, BACKOFF_FACTOR
from icegrams.model import model_filename
from icegrams.ngrams import BitArray, MonotonicList, PartitionedMonotonicList


def test_compressed_list():
    """Test the compressed list classes"""
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
    except Exception:
        assert False, "Should have raised IndexError"
    assert len(ba) == (90 + 7) // 8

    for _ in range(100):
        test_list = [randint(0, 2000000) for _ in range(randint(1, 1000))]

        test_list.sort()
        ml = MonotonicList()
        ml.compress(test_list)
        for i in range(len(test_list)):
            assert ml[i] == test_list[i]

    # Test single-element list
    ml = MonotonicList()
    ml.compress([17])
    assert ml[0] == 17


def test_partitioned_list():
    pl = PartitionedMonotonicList()
    pl.compress([i for i in range(18000)])
    assert pl[177] == 177
    assert pl[2177] == 2177
    assert pl[4177] == 4177
    assert pl[7177] == 7177
    assert pl[12177] == 12177
    assert pl[14177] == 14177
    assert pl[16177] == 16177
    pl.compress([i * 17 for i in range(1380000)])
    assert pl[199] == 199 * 17
    assert pl[2199] == 2199 * 17
    assert pl[4199] == 4199 * 17
    assert pl[7199] == 7199 * 17
    assert pl[12177] == 12177 * 17
    assert pl[14177] == 14177 * 17
    assert pl[16177] == 16177 * 17
    assert pl[120177] == 120177 * 17
    assert pl[140177] == 140177 * 17
    assert pl[160177] == 160177 * 17
    assert pl[343085] == 343085 * 17
    assert pl[1343085] == 1343085 * 17
    b = pl.to_bytes()
    pl = PartitionedMonotonicList(b)
    assert pl[199] == 199 * 17
    assert pl[2199] == 2199 * 17
    assert pl[4199] == 4199 * 17
    assert pl[7199] == 7199 * 17
    assert pl[12177] == 12177 * 17
    assert pl[14177] == 14177 * 17
    assert pl[16177] == 16177 * 17
    assert pl[120177] == 120177 * 17
    assert pl[140177] == 140177 * 17
    assert pl[160177] == 160177 * 17
    assert pl[343085] == 343085 * 17
    assert pl[1343085] == 1343085 * 17


def test_model_lookup(monkeypatch, tmp_path):
    # Creating an Ngrams instance must never download anything: with no
    # model present, it fails fast with ModelNotFoundError. Point every
    # lookup location at an empty directory to simulate a fresh install.
    monkeypatch.delenv("ICEGRAMS_MODEL_FILE", raising=False)
    monkeypatch.setenv("ICEGRAMS_MODEL_DIR", str(tmp_path))
    monkeypatch.setattr("icegrams.model._PATH", str(tmp_path))
    with pytest.raises(ModelNotFoundError) as excinfo:
        Ngrams()
    assert "python -m icegrams.download" in str(excinfo.value)
    # A truncated or placeholder file is not accepted as a model
    bogus = tmp_path / "trigrams.bin"
    bogus.write_bytes(b"version https://git-lfs.github.com/spec/v1\n")
    monkeypatch.setenv("ICEGRAMS_MODEL_FILE", str(bogus))
    assert model_filename() == str(bogus)  # explicit override is trusted
    monkeypatch.delenv("ICEGRAMS_MODEL_FILE")
    with pytest.raises(ModelNotFoundError):
        model_filename()
    monkeypatch.setenv("ICEGRAMS_MODEL_FILE", str(tmp_path / "missing.bin"))
    with pytest.raises(ModelNotFoundError):
        model_filename()


def test_trigrams():
    try:
        n = Ngrams()
    except ModelNotFoundError as e:
        pytest.skip("Trigram model not downloaded: {0}".format(e))
    assert n.prob("", "", "Í") < 1.0
    assert n.freq("hundurinn", "át", "heimaverkefnið") == 2
    assert n.adj_freq("xxx", "yyy", "zzz") == 1
    assert n.adj_freq("Hann", "var", "zzz") == 1

    assert n.freq("") > 90000000
    assert n.freq("", "Hér") > 50000
    assert n.freq("Ísland") > 150000
    assert n.prob("Ísland") > 0.00019
    assert n.logprob("Ísland") > -8.530
    assert n.freq("Katrín", "Jakobsdóttir") > 6000
    assert n.adj_freq("velta", "fyrirtækisins", "er") >= 5

    assert "Jakobsdóttir" in set(u for u, _ in n.succ(10, "Katrín"))
    assert "Gunnarsdóttir" in set(u for u, _ in n.succ(10, "Þorgerður", "Katrín"))
    assert "Þorsteinsson" in set(u for u, _ in n.succ(20, "Vilhjálmur"))
    assert "atkvæði" in set(u for u, _ in n.succ(20, "greiddi", "því"))
    assert "heimaverkefnið" in set(u for u, _ in n.succ(20, "hundurinn", "át"))


def test_succ():
    try:
        n = Ngrams()
    except ModelNotFoundError as e:
        pytest.skip("Trigram model not downloaded: {0}".format(e))
    for ctx in [("Ísland",), ("Katrín",), ("hundurinn", "át"), ("Katrín", "Jakobsdóttir")]:
        every = n.succ(10**7, *ctx)
        assert every and all(a[1] >= b[1] for a, b in zip(every, every[1:]))
        # The n best are the first n of the full list, also among equal
        # frequencies, which are common towards the end of it
        for k in (1, 5, 50, max(1, len(every) - 1)):
            assert n.succ(k, *ctx) == every[:k]
        for w, lp in every[:20]:
            assert lp == pytest.approx(n.logprob(*ctx, w))
    s = n.ngrams
    p1, p2 = s._unigram_ptrs_ml.lookup_pair(s.word_to_id("Ísland"))
    assert len(n.succ(10**7, "Ísland")) == p2 - p1
    # Contexts with hundreds of thousands of successors
    assert len(n.succ(10, "")) == len(n.succ(10, "og")) == 10
    assert n.succ(3, "xyzqw") == n.succ(3, "Ísland", "xyzqw") == []
    n.close()


@pytest.mark.skipif(
    platform.python_implementation() != "CPython",
    reason="PyPy unmaps the memory map at close() even while it is in use",
)
def test_close_while_in_use():
    # A query in another thread holds views of the memory map while it runs:
    # close() must still succeed, and the views stay readable until released
    try:
        n = Ngrams()
    except ModelNotFoundError as e:
        pytest.skip("Trigram model not downloaded: {0}".format(e))
    in_use = n.ngrams._unigram_ptrs_ml
    expected = in_use.lookup_pair(0)
    n.close()
    assert in_use.lookup_pair(0) == expected


def backed_off(n, lower_logprob, *context):
    """Expected log probability of an unseen n-gram: the lower-order
    log probability plus log(BACKOFF_FACTOR), capped at the add-one
    estimate of a single unseen continuation of the context"""
    if context == ("",):
        ctx_count = n.ngrams.number_of_sentences()
    else:
        ctx_count = n.freq(*context)
    return min(math.log(BACKOFF_FACTOR) + lower_logprob, -math.log(ctx_count + 1))


def test_backoff():
    try:
        n = Ngrams()
    except ModelNotFoundError as e:
        pytest.skip("Trigram model not downloaded: {0}".format(e))
    legacy = Ngrams(backoff=False)

    # Unseen n-grams whose context is also unseen must not get probability 1
    assert n.prob("xxxq", "yyyq", "zzzq") < 1e-6
    assert n.prob("xxxq", "yyyq") < 1e-6
    assert n.prob("Ísland", "xxxq", "yyyq") < 1e-6
    assert n.prob("xxxq", "yyyq", "Ísland") < n.prob("Ísland")

    # Unseen trigram backs off to the bigram, unseen bigram to the unigram
    assert n.freq("hundurinn", "át", "Ísland") == 0
    assert n.freq("át", "Ísland") == 0
    assert n.logprob("hundurinn", "át", "Ísland") == pytest.approx(
        backed_off(n, n.logprob("át", "Ísland"), "hundurinn", "át")
    )
    assert n.logprob("át", "Ísland") == pytest.approx(
        backed_off(n, n.logprob("Ísland"), "át")
    )
    # With an unseen context the cap is 1.0 and does not apply
    assert n.freq("xxxq", "yyyq") == 0
    assert n.logprob("xxxq", "yyyq", "Ísland") == pytest.approx(
        math.log(BACKOFF_FACTOR) + n.logprob("yyyq", "Ísland")
    )
    assert n.logprob("yyyq", "Ísland") == pytest.approx(
        math.log(BACKOFF_FACTOR) + n.logprob("Ísland")
    )

    # Seen n-grams are unaffected by backoff
    for args in [
        ("Ísland",),
        ("Katrín", "Jakobsdóttir"),
        ("stjórnarskrá", "lýðveldisins", "Íslands"),
        ("", "", "Í"),
    ]:
        assert n.freq(*args) > 0
        assert n.logprob(*args) == legacy.logprob(*args)

    # Legacy behavior is retained when requested
    assert legacy.prob("xxxq", "yyyq", "zzzq") == 1.0
    assert legacy.prob("xxxq", "yyyq") == 1.0
    assert legacy.logprob("hundurinn", "át", "Ísland") == pytest.approx(
        -math.log(n.freq("hundurinn", "át") + 1)
    )
    legacy.close()
    n.close()


def test_backoff_ranking():
    """An unseen n-gram never outscores a seen n-gram in the same context,
    while unseen continuations are still ranked by lower-order evidence"""
    try:
        n = Ngrams()
    except ModelNotFoundError as e:
        pytest.skip("Trigram model not downloaded: {0}".format(e))

    # "Ísland" and "Ég" are both very common but
    # never occur together; that absence must not be outweighed by the
    # unigram frequency of "Ég"
    assert n.freq("Ísland", "okkar") > 0
    assert n.freq("Ísland", "Ég") == 0
    assert n.prob("Ísland", "okkar") > n.prob("Ísland", "Ég")
    # ...but among unseen continuations, the common word ranks above the rare one
    assert n.prob("Ísland", "Ég") > n.prob("Ísland", "xxxq")

    # Systematically: for a range of contexts, the rarest seen successor
    # beats every unseen successor, even very common words
    common = ["Ég", "og", "að", "er", "hann", "ekki", "sem"]
    checked = 0
    for context in [
        ("Ísland",),
        ("hundurinn",),
        ("Katrín",),
        ("Reykjavík",),
        ("sagði",),
        ("hundurinn", "át"),
        ("stjórnarskrá", "lýðveldisins"),
        ("Katrín", "Jakobsdóttir"),
    ]:
        successors = n.succ(100000, *context)
        assert successors
        rarest_logprob = successors[-1][1]
        for w in common:
            if n.freq(*context, w) == 0:
                assert n.logprob(*context, w) < rarest_logprob, (context, w)
                checked += 1
    assert checked >= 10

    # The cap equals the add-one estimate of one unseen continuation
    assert n.prob("hundurinn", "át", "og") <= 1.0 / (n.freq("hundurinn", "át") + 1)
    n.close()


def test_backoff_edge_cases():
    try:
        n = Ngrams()
    except ModelNotFoundError as e:
        pytest.skip("Trigram model not downloaded: {0}".format(e))
    legacy = Ngrams(backoff=False)

    assert 0.0 < BACKOFF_FACTOR < 1.0

    # prob() and logprob() agree, with and without backoff
    for args in [("xxxq", "yyyq", "zzzq"), ("hundurinn", "át", "Ísland"), ("Ísland",)]:
        assert n.prob(*args) == pytest.approx(math.exp(n.logprob(*args)))
        assert legacy.prob(*args) == pytest.approx(math.exp(legacy.logprob(*args)))

    # Every probability stays in (0, 1]
    for args in [
        ("xxxq", "yyyq", "zzzq"),
        ("xxxq", "yyyq"),
        ("", "xxxq"),
        ("xxxq", ""),
        ("", "", "xxxq"),
        ("Ísland", "xxxq", "yyyq"),
    ]:
        assert 0.0 < n.prob(*args) <= 1.0

    # Sentence-boundary contexts ("" is the sentence delimiter)
    assert n.freq("", "xxxq") == 0
    assert n.logprob("", "xxxq") == pytest.approx(backed_off(n, n.logprob("xxxq"), ""))
    assert n.freq("", "", "xxxq") == 0
    assert n.logprob("", "", "xxxq") == pytest.approx(
        backed_off(n, n.logprob("", "xxxq"), "", "")
    )
    assert n.freq("xxxq", "") == 0
    assert n.logprob("xxxq", "") == pytest.approx(backed_off(n, n.logprob(""), "xxxq"))
    # Seen sentence-boundary n-grams are unchanged
    assert n.freq("Ísland", "", "") > 0
    assert n.logprob("Ísland", "", "") == legacy.logprob("Ísland", "", "")

    # Words with characters outside the model alphabet are not in the
    # vocabulary and are treated as unseen
    assert n.ngrams.word_to_id("東京") is None
    assert n.prob("東京") < 1e-6
    assert n.logprob("Ísland", "東京") == pytest.approx(
        backed_off(n, n.logprob("東京"), "Ísland")
    )
    assert n.logprob("Ísland", "xxxq", "東京") == pytest.approx(
        backed_off(n, n.logprob("xxxq", "東京"), "Ísland", "xxxq")
    )
    assert legacy.prob("Ísland", "xxxq", "東京") == 1.0

    # More than 3 arguments: only the last 3 are significant, also with backoff
    assert n.logprob("a", "b", "c", "xxxq", "yyyq", "Ísland") == n.logprob(
        "xxxq", "yyyq", "Ísland"
    )

    # Unseen trigram whose bigram (u2, u3) is seen: one level of backoff
    assert n.freq("hundurinn", "át", "mikið") == 0
    assert n.freq("át", "mikið") > 0
    assert n.logprob("hundurinn", "át", "mikið") == pytest.approx(
        backed_off(n, n.logprob("át", "mikið"), "hundurinn", "át")
    )
    # A seen trigram scores higher than an unseen one in the same context
    assert n.freq("hundurinn", "át", "heimaverkefnið") > 0
    assert n.logprob("hundurinn", "át", "heimaverkefnið") > n.logprob(
        "hundurinn", "át", "mikið"
    )
    # Backing off once from a seen bigram scores higher than backing off
    # twice to the unigram of the same word
    assert n.logprob("hundurinn", "át", "mikið") > n.logprob("xxxq", "yyyq", "mikið")

    # The backoff setting is per instance; the two instances do not interfere
    assert n.ngrams.backoff is True
    assert legacy.ngrams.backoff is False
    assert n.prob("xxxq", "yyyq", "zzzq") < 1.0 == legacy.prob("xxxq", "yyyq", "zzzq")

    # The setting is fixed when the instance is created, since threads
    # may share it
    with pytest.raises(AttributeError):
        n.ngrams.backoff = False  # type: ignore[misc]
    assert n.logprob("xxxq", "yyyq", "zzzq") == pytest.approx(
        2 * math.log(BACKOFF_FACTOR) + n.logprob("zzzq")
    )

    legacy.close()
    n.close()


def test_word_ids():
    n = Ngrams().ngrams
    assert n
    for i in range(0, 2048):
        assert n.word_to_id(n.id_to_word(i)) == i
