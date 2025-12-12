#!/usr/bin/env python
# type: ignore
"""

Icegrams: A trigrams library for Icelandic

utils/rmh.py

Copyright (C) 2019-2025 Miðeind ehf

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


This utility program reads text files from the Icelandic Gigaword Corpus
(Risamálheild, RMH), tokenizes them, cuts them into trigrams and
writes them to a PostgreSQL database table. The PostgreSQL database
is assumed to have the name 'rmh', and to be accessible from the PostgreSQL
user/role 'rmh' with password 'rmh'.

"""

from typing import (
    Iterator,
    Iterable,
    Optional,
    Tuple,
    List,
    Dict,
    Set,
    Callable,
    Type,
    Any,
)

import os
import sys
from itertools import islice, tee
import argparse
import glob
import random
from datetime import datetime

from sqlalchemy.ext.declarative import declarative_base  # type: ignore
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    PrimaryKeyConstraint,
)  # type: ignore
from sqlalchemy.orm import sessionmaker, Session  # type: ignore
from sqlalchemy.exc import SQLAlchemyError as DatabaseError  # type: ignore
from sqlalchemy.schema import Table  # type: ignore

from tokenizer import tokenize, Tok, TOK


# Obtain our path
basepath, _ = os.path.split(os.path.realpath(__file__))

# Create the SQLAlchemy ORM Base class
Base: Type[Table] = declarative_base()


# A set of all words we need to change
CHANGING: Set[str] = set()
# fACE_SK.txt
REPLACING: Dict[str, str] = dict()
# d.txt
DELETING: Set[str] = set()
# fMW.txt
DOUBLING: Dict[str, List[str]] = dict()


# Define the command line arguments

parser = argparse.ArgumentParser(
    description=(
        "This program collects trigrams from the Icelandic Gigaword Corpus (RMH)"
    )
)

parser.add_argument(
    "path",
    nargs="?",
    type=str,
    help="glob path of the RMH files to process",
)

parser.add_argument(
    "-n",
    "--number",
    type=int,
    default=0,
    help="number of files to process (default=all)",
)

parser.add_argument(
    "-l",
    "--listfiles",
    default=False,
    action="store_true",
    help="list a random sample of RMH file paths",
)


class Trigram_DB:
    """Wrapper around the SQLAlchemy connection, engine and session"""

    def __init__(self) -> None:
        """Initialize the SQLAlchemy connection to the trigram database"""

        # Assemble the connection string, using psycopg2cffi which
        # supports both PyPy and CPython
        conn_str = "postgresql+{0}://{1}:{2}@{3}:{4}/rmh".format(
            "psycopg2cffi",
            "rmh",  # Settings.DB_USERNAME,
            "rmh",  # Settings.DB_PASSWORD,
            "localhost",  # Settings.DB_HOSTNAME,
            "5432",  # Settings.DB_PORT,
        )

        # Create engine and bind session
        self._engine = create_engine(conn_str)
        self._Session = sessionmaker(bind=self._engine)

    def create_tables(self) -> None:
        """Create all missing tables in the database"""
        Base.metadata.create_all(self._engine)

    def execute(self, sql: str, **kwargs) -> Any:
        """Execute raw SQL directly on the engine"""
        return self._engine.execute(sql, **kwargs)

    @property
    def session(self) -> Session:
        """Returns a freshly created Session instance from the sessionmaker"""
        return self._Session()


class classproperty:
    def __init__(self, f):
        self.f = f

    def __get__(self, obj, owner):
        return self.f(owner)


class SessionContext:
    """Context manager for database sessions"""

    # Singleton instance of Trigram_DB
    _db: Optional[Trigram_DB] = None

    # pylint: disable=no-self-argument
    @classproperty
    def db(cls) -> Trigram_DB:
        if cls._db is None:
            cls._db = Trigram_DB()
        return cls._db

    @classmethod
    def cleanup(cls) -> None:
        """Clean up the reference to the singleton Trigram_DB instance"""
        cls._db = None

    def __init__(self, session=None, commit=False, read_only=False) -> None:
        if session is None:
            # Create a new session that will be automatically committed
            # (if commit == True) and closed upon exit from the context
            # pylint: disable=no-member
            # Creates a new Trigram_DB instance if needed
            self._session = self.db.session
            self._new_session = True
            if read_only:
                # Set the transaction as read only, which can save resources
                self._session.execute("SET TRANSACTION READ ONLY")
                self._commit = True
            else:
                self._commit = commit
        else:
            self._new_session = False
            self._session = session
            self._commit = False

    def __enter__(self):
        """Python context manager protocol"""
        # Return the wrapped database session
        return self._session

    # noinspection PyUnusedLocal
    def __exit__(self, exc_type, exc_value, traceback):
        """Python context manager protocol"""
        if self._new_session:
            if self._commit:
                if exc_type is None:
                    # No exception: commit if requested
                    self._session.commit()
                else:
                    self._session.rollback()
            self._session.close()
        # Return False to re-throw exception from the context, if any
        return False


class Trigram(Base):
    """A database table containing trigrams of tokens from a parsed sentence"""

    __tablename__ = "trigrams"

    MAX_WORD_LEN = 64

    # Token 1
    t1 = Column(String(MAX_WORD_LEN), nullable=False)

    # Token 2
    t2 = Column(String(MAX_WORD_LEN), nullable=False)

    # Token 3
    t3 = Column(String(MAX_WORD_LEN), nullable=False)

    # Frequency
    frequency = Column(Integer, default=0, nullable=False)

    # The "upsert" query (see explanation below)
    _Q = """
        insert into trigrams as tg (t1, t2, t3, frequency) values(:t1, :t2, :t3, 1)
            on conflict (t1, t2, t3)
            do update set frequency = tg.frequency + 1;
        """
    # where tg.t1 = :t1 and tg.t2 = :t2 and tg.t3 = :t3;

    __table_args__ = (PrimaryKeyConstraint("t1", "t2", "t3", name="trigrams_pkey"),)

    @staticmethod
    def upsert(session, t1, t2, t3):
        """Insert a trigram, or increment the frequency count if already present"""
        # The following code uses "upsert" functionality (INSERT...ON CONFLICT...DO UPDATE)
        # that was introduced in PostgreSQL 9.5. This means that the upsert runs on the
        # server side and is atomic, either an insert of a new trigram or an update of
        # the frequency count of an existing identical trigram.
        mwl = Trigram.MAX_WORD_LEN
        if len(t1) > mwl:
            t1 = t1[0:mwl]
        if len(t2) > mwl:
            t2 = t2[0:mwl]
        if len(t3) > mwl:
            t3 = t3[0:mwl]
        session.execute(Trigram._Q, dict(t1=t1, t2=t2, t3=t3))

    @staticmethod
    def delete_all(session):
        """Delete all trigrams"""
        session.execute("delete from trigrams;")

    def __repr__(self):
        return "Trigram(t1='{0}', t2='{1}', t3='{2}')".format(self.t1, self.t2, self.t3)


def load_corrections() -> None:
    """Fills global data structures for correcting tokens"""
    with open(os.path.join(basepath, "correct.txt"), "r", encoding="utf-8") as myfile:
        for line in myfile:
            key, val = line.strip().split("\t")
            REPLACING[key] = val
            CHANGING.add(key)
    with open(os.path.join(basepath, "delete.txt"), "r", encoding="utf-8") as myfile:
        for line in myfile:
            key = line.strip()
            DELETING.add(key)
            CHANGING.add(key)
    with open(os.path.join(basepath, "split.txt"), "r", encoding="utf-8") as myfile:
        for line in myfile:
            key, val = line.strip().split("\t")
            val = val.strip()
            DOUBLING[key] = val.split()
            CHANGING.add(key)
            if key.islower() and val.islower():
                # Also add uppercase version
                key = key.capitalize()
                val = val.capitalize()
                DOUBLING[key] = val.split()
                CHANGING.add(key)


def handle_word(token: Tok) -> Iterator[str]:
    """Return the text of a word token, after potential editing"""
    t = token.txt
    if t in CHANGING:
        # We take a closer look
        if t in REPLACING:
            # Words we simply need to replace
            yield REPLACING[t]
        elif t in DELETING:
            # Words that don't belong in trigrams
            pass
        elif t in DOUBLING:
            # Words incorrectly in one token
            for part in DOUBLING[t]:
                yield part
        else:
            # Should not happen
            assert False
    elif " " in t:
        yield from t.split()
    else:
        yield t


def handle_punctuation(token: Tok) -> Iterator[str]:
    """Return the normalized version of punctuation"""
    yield token.val[1]


def handle_passthrough(token: Tok) -> Iterator[str]:
    """Return the token text unchanged"""
    yield token.txt


def handle_split(token: Tok) -> Iterator[str]:
    """Split the token text by spaces and return the components"""
    yield from token.txt.split()


def handle_measurement(token: Tok) -> Iterator[str]:
    """Return a [NUMBER] token followed by a SI unit"""
    yield from ("[NUMBER]", token.val[0])


def handle_none(token: Tok) -> Iterator[str]:
    """Empty generator"""
    yield from ()


def handle_other(token: Tok) -> Iterator[str]:
    """Return a standard placeholder for the token kind"""
    yield "[" + TOK.descr[token.kind] + "]"


# Dispatch the various token types to the appropriate generators,
# defaulting to handle_others
token_dispatch: Dict[int, Callable[[Tok], Iterator[str]]] = {
    TOK.WORD: handle_word,
    TOK.PUNCTUATION: handle_punctuation,
    TOK.MEASUREMENT: handle_measurement,
    TOK.MOLECULE: handle_passthrough,
    TOK.PERSON: handle_split,
    TOK.ENTITY: handle_split,
    TOK.COMPANY: handle_split,
    TOK.S_BEGIN: handle_none,
    TOK.S_END: handle_none,
    TOK.P_BEGIN: handle_none,
    TOK.P_END: handle_none,
    TOK.S_SPLIT: handle_none,
}


def tokens(text: str) -> Iterator[str]:
    """Generator for token stream"""
    toklist = list(tokenize(text, convert_measurements=True, replace_html_escapes=True))
    if len(toklist) > 1 and all(t.kind != TOK.UNKNOWN for t in toklist):
        # For each sentence, start and end with empty strings
        yield ""
        yield ""
        for t in toklist:
            yield from token_dispatch.get(t.kind, handle_other)(t)
        yield ""
        yield ""


def trigrams(iterable: Iterable[str]) -> Iterator[Tuple[Any, ...]]:
    """Generate trigrams (tuples of three strings) from the given iterable"""
    return zip(*((islice(seq, i, None) for i, seq in enumerate(tee(iterable, 3)))))


def process(session: SessionContext, text: str) -> int:
    """Process a single line of text from an RMH file"""
    upserted = 0
    for tg in trigrams(tokens(text)):
        if any(tg):
            try:
                Trigram.upsert(session, *tg)
                upserted += 1
            except DatabaseError as ex:
                print("*** Exception {0} on trigram {1}, skipped".format(ex, tg))
    return upserted


def path_iterator(path: str, limit: int = 0) -> Iterator[str]:
    """Return an iterator of file paths"""
    path = path.strip()
    if path.startswith("@"):
        # Interpret the path as the path of a file to read paths from
        with open(path[1:], "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    yield line
    if limit <= 0:
        # No limit: Iterate through all files matching the glob pattern
        yield from glob.iglob(path, recursive=True)
    else:
        # Limit: Sample N files from the list of files matching the glob pattern
        yield from random.sample(glob.glob(path, recursive=True), limit)


def make_trigrams(path_iterator: Iterable[str], *, limit: int = 0):
    """Iterate through files according to the given glob path spec,
    extracting trigrams from contained sentences. The trigrams
    are corrected and subsequently 'upserted' into the trigrams
    table of a PostgreSQL database."""

    FLUSH_THRESHOLD = 10000

    load_corrections()

    with SessionContext(commit=False) as session:
        # Delete existing trigrams
        Trigram.delete_all(session)
        session.commit()

        try:
            limited = limit > 0

            file_count = 0

            # Iterate through the selected RMH files
            for fpath in path_iterator:
                file_count += 1
                if limited:
                    report = "({0}/{1}) ".format(file_count, limit)
                else:
                    report = "({0}) ".format(file_count)

                print("Reading {0} {1}".format(fpath, report), end="", flush=True)
                upserted = 0
                cnt = 0

                with open(fpath, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            a = line.split("\t", maxsplit=1)
                            if len(a) == 2:
                                text = a[1]
                                u = process(session, text)
                                upserted += u
                                cnt += u
                        if cnt >= FLUSH_THRESHOLD:
                            session.flush()
                            session.commit()
                            print(".", end="", flush=True)
                            cnt = 0

                print(" upserted {0} trigrams".format(upserted), flush=True)

        finally:
            session.flush()
            session.commit()


def main():
    args = parser.parse_args()
    if not args.path:
        print("Path to RMH files must be specified.")
        sys.exit(1)

    limit = args.number

    if args.listfiles:
        # Output a random sample of RMH file paths
        for fpath in sorted(random.sample(glob.glob(args.path, recursive=True), limit)):
            print(fpath)
        sys.exit(0)

    start = datetime.utcnow()
    print("Processing started at {0}".format(start))
    print(
        "Processing {0} files from path {1}".format(
            limit if limit else "all", args.path
        )
    )
    file_paths = path_iterator(args.path, limit=limit)
    make_trigrams(file_paths, limit=limit)
    finish = datetime.utcnow()
    print("Processing finished at {0}".format(finish))
    duration = finish - start
    print("Duration: {0}".format(duration))


if __name__ == "__main__":
    main()
