# icegrams-data

The trigram model of the [icegrams](https://pypi.org/project/icegrams/)
package ([Icegrams](https://github.com/mideind/Icegrams)): `trigrams.bin`,
a compressed database of unigram, bigram and trigram frequencies in
Icelandic text.

This package has no functionality of its own. It is a dependency of
`icegrams`, which finds the model here:

```python
>>> from icegrams import Ngrams
>>> Ngrams().freq("hundurinn", "át", "heimaverkefnið")
```

The model is kept in a package of its own because it changes far less often
than the code: a release of icegrams then ships small wheels for each
platform and Python implementation, and the 192 MB model is downloaded once
per environment and cached by pip and uv.

## The model

The model was built from a weighted sample of about 1 billion tokens of the
Icelandic Gigaword Corpus
([Risamálheild](https://repository.clarin.is/repository/xmlui/handle/20.500.12537/253),
collected and maintained by *The Árni Magnússon Institute for Icelandic
Studies*) and of recent news collected by Miðeind, from 1980 through July
2026. Every sentence was corrected with Málfríður, Miðeind's neural spelling
and grammar correction model, and trigrams that occurred only once were
dropped. The process is described in
[doc/2026-update.md](https://github.com/mideind/Icegrams/blob/master/doc/2026-update.md).

## Versions

The version follows the model: `2026.8.x` holds the model of the GitHub
release `model-2026.08`, which is also available as a direct download
(`python -m icegrams.download`). The patch number is for re-releases of the
same model. Each icegrams release requires the model it was tested with
(e.g. `icegrams-data == 2026.8.*`), because a new model changes the results
of queries.

## Copyright and licensing

Copyright © 2026 [Miðeind ehf.](https://mideind.is). This package is
licensed under the MIT License; see `LICENSE.txt`.
