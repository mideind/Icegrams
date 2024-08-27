
import sys
import time
from random import randrange
import icegrams
import os

n = icegrams.Ngrams()

FILENAME=os.path.join("src", "icegrams", "resources", "trigrams-subset.tsv")

d = []
with open(FILENAME, encoding="utf-8") as f:
    for line in f:
        tg = line.rstrip().split()
        if len(tg) != 4:
            tg = line.rstrip().split("\t")
        if len(tg) == 4:
            cnt = int(tg[3])
            trigram = tuple(tg[0:3])
            d.append((trigram, cnt))
        else:
            print("Something wrong with '{0}'".format(line))
            break
if d:
    LOOKUPS = 10000
    t0 = time.time()
    for i in range(LOOKUPS):
        ix = randrange(len(d))
        trigram, cnt = d[ix]
        if not set("".join(trigram)).issubset(icegrams.ngrams.ALPHABET_SET):
            # print("Skipping {0}".format(tg))
            continue
        fq = n.freq(*trigram)
        # print("Testing {0}, cnt is {1}/{2}".format(tg, cnt + 1, fq), flush=True)
        if fq != cnt + 1:
            print("{0}: fq is {1} but should be {2}".format(trigram, fq, cnt+1))
        # assert fq == cnt + 1
    t1 = time.time()
    print(
        "{2} lookups in {0:.2f} seconds, {1:.1f} microseconds per lookup"
        .format(t1 - t0, 1e6 * (t1 - t0) / LOOKUPS, LOOKUPS)
    )

n.close()
