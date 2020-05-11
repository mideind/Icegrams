"""

    Icegrams: A trigrams library for Icelandic

    __init__.py

    Copyright (C) 2020 Miðeind ehf.
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
    along with this program.  If not, see <https://www.gnu.org/licenses/>.

    This module exposes the icegrams API, i.e. the identifiers that are
    directly accessible via the icegrams module object after importing it.

"""

# Expose the icegrams API

from .ngrams import Ngrams, MAX_ORDER

__author__ = "Miðeind ehf."
__copyright__ = "(C) 2020 Miðeind ehf."
__version__ = "0.6.0"
