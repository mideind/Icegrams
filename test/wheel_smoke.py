"""

wheel_smoke.py

Smoke test of an installed icegrams wheel, run by cibuildwheel for every
wheel before it is published (CIBW_TEST_COMMAND in wheels.yml), with the
icegrams-data wheel of the same run installed. Not a pytest module.

Copyright (C) 2026 Miðeind ehf.

This software is licensed under the MIT License (see LICENSE.txt).

"""

import sys
import sysconfig

import icegrams_data

from icegrams import Ngrams
from icegrams.model import model_filename

# A wheel holds no model of its own: it comes from icegrams-data
assert model_filename() == icegrams_data.model_path(), model_filename()
n = Ngrams()
assert n.freq("hundurinn", "át", "heimaverkefnið") == 2
assert n.adj_freq("xxx", "yyy", "zzz") == 1
assert 0.0 < n.prob("Ísland") < 1.0
assert len(n.succ(2, "að")) == 2
# On free-threaded Python the extension must not turn the GIL back on
if sysconfig.get_config_var("Py_GIL_DISABLED"):
    assert not sys._is_gil_enabled()  # type: ignore[attr-defined]
print("icegrams wheel smoke test passed")
