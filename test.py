
import sys
import time
from random import randrange
import icegrams

n = icegrams.Ngrams()

print("Tuple for 'desired' is {0}".format(n.ngrams.indices("desired")))
print("Tuple for 'function' is {0}".format(n.ngrams.indices("function")))
print("Tuple for 'desired function' is {0}".format(n.ngrams.indices("desired", "function")))
print("Tuple for 'desired instruction' is {0}".format(n.ngrams.indices("desired", "instruction")))
print("Tuple for 'desired branch' is {0}".format(n.ngrams.indices("desired", "branch")))
print("Tuple for 'the arrays are' is {0}".format(n.ngrams.indices("the", "arrays", "are")))
print("Tuple for 'in the code' is {0}".format(n.ngrams.indices("in", "the", "code")))

print("Freq for 'function' is {0}".format(n.freq("function")))
print("Freq for 'desired' is {0}".format(n.freq("desired")))
print("Freq for 'góður' is {0}".format(n.freq("góður")))

print("Freq for 'desired function' is {0}".format(n.freq("desired", "function")))
print("Freq for 'desired instruction' is {0}".format(n.freq("desired", "instruction")))
print("Freq for 'desired branch' is {0}".format(n.freq("desired", "branch")))
print("Freq for 'góður branch' is {0}".format(n.freq("góður", "branch")))
print("Freq for 'desired góður' is {0}".format(n.freq("desired", "góður")))

print("Freq for 'the arrays are' is {0}".format(n.freq("the", "arrays", "are")))
print("Freq for 'in the code' is {0}".format(n.freq("in", "the", "code")))
print("Freq for 'test setup but' is {0}".format(n.freq("test", "setup", "but")))
print("Freq for '78. Assume no' is {0}".format(n.freq('78.', 'Assume', 'no')))

# sys.exit(0)

# FILENAME="3-grams.sorted"
FILENAME="trigrams-subset.tsv"

d = []
with open(FILENAME, encoding="utf-8") as f:
    for line in f:
        tg = line.rstrip().split()
        if len(tg) != 4:
            tg = line.rstrip().split("\t")
        if len(tg) == 4:
            cnt = int(tg[3])
            tg = tuple(tg[0:3])
            d.append((tg, cnt))
        else:
            print("Something wrong with '{0}'".format(line))
            break
if d:
    LOOKUPS = 10000
    t0 = time.time()
    for i in range(LOOKUPS):
        ix = randrange(len(d))
        tg, cnt = d[ix]
        if not set("".join(tg)).issubset(icegrams.ngrams.ALPHABET_SET):
            # print("Skipping {0}".format(tg))
            continue
        fq = n.freq(*tg)
        # print("Testing {0}, cnt is {1}/{2}".format(tg, cnt + 1, fq), flush=True)
        assert fq == cnt + 1
    t1 = time.time()
    print(
        "{2} lookups in {0:.2f} seconds, {1:.1f} microseconds per lookup"
        .format(t1 - t0, 1e6 * (t1 - t0) / LOOKUPS, LOOKUPS)
    )

n.close()
