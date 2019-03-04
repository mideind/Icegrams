
import sys
import time
from random import randrange
import icegrams

n = icegrams.Ngrams()

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
    fq = n.freq('', 'Heildstæðar', 'lausnir') # Should have fq=3
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
        if fq != cnt + 1:
            print("{0}: fq is {1} but should be {2}".format(tg, fq, cnt+1))
        # assert fq == cnt + 1
    t1 = time.time()
    print(
        "{2} lookups in {0:.2f} seconds, {1:.1f} microseconds per lookup"
        .format(t1 - t0, 1e6 * (t1 - t0) / LOOKUPS, LOOKUPS)
    )

n.close()
