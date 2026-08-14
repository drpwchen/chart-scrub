"""The alias store: the one file that must never leave the machine.

Everything the pipeline does is reversible only through this SQLite database.
It holds the real name and chart number next to the alias (PT-0001), which is
exactly the mapping the de-identified output no longer contains.

Keep it local. Do not commit it, sync it, or hand it to a language model.
"""

from __future__ import annotations

import datetime
import os
import sqlite3

__all__ = ["AliasStore", "DEFAULT_DB"]

DEFAULT_DB = os.path.join(os.path.expanduser("~"), ".chart-scrub", "aliases.db")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS patients(
    mrn TEXT PRIMARY KEY,
    name TEXT,
    sex TEXT,
    birth TEXT,
    first_seen TEXT,
    last_seen TEXT,
    last_dx TEXT,
    visit_count INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS aliases(
    alias TEXT PRIMARY KEY,
    mrn TEXT UNIQUE,
    created TEXT);
CREATE TABLE IF NOT EXISTS counters(
    prefix TEXT PRIMARY KEY,
    next INTEGER);
"""


class AliasStore:
    """Thin wrapper over the SQLite mapping table."""

    def __init__(self, path: str = DEFAULT_DB, prefix: str = "PT"):
        self.path = path
        self.prefix = prefix
        parent = os.path.dirname(os.path.abspath(path))
        if parent:
            os.makedirs(parent, exist_ok=True)
        self.con = sqlite3.connect(path)
        self.con.executescript(_SCHEMA)

    # -- context manager -------------------------------------------------
    def __enter__(self) -> "AliasStore":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        self.con.close()

    # -- aliases ---------------------------------------------------------
    def _next_number(self) -> int:
        """Take the next alias number from a counter that only ever goes up.

        ``COUNT(*)+1`` breaks in two quiet ways: two processes can read the
        same count and collide, and deleting a row hands its number to the
        next patient — old output files then point their alias at somebody
        else. A counter row never re-issues a number, whatever happens to
        the aliases table. Seeded from the highest existing alias so a
        pre-counter database keeps its sequence.
        """
        row = self.con.execute(
            "SELECT next FROM counters WHERE prefix=?", (self.prefix,)
        ).fetchone()
        if row:
            n = row[0]
        else:
            seed = self.con.execute(
                "SELECT alias FROM aliases WHERE alias LIKE ? ORDER BY LENGTH(alias) DESC, alias DESC LIMIT 1",
                (f"{self.prefix}-%",),
            ).fetchone()
            n = int(seed[0].rsplit("-", 1)[1]) + 1 if seed else 1
        self.con.execute(
            "INSERT INTO counters(prefix, next) VALUES(?,?) "
            "ON CONFLICT(prefix) DO UPDATE SET next=?",
            (self.prefix, n + 1, n + 1),
        )
        return n

    def alias_for(self, mrn: str) -> str:
        """Return the stable alias for a chart number, creating it if new."""
        row = self.con.execute("SELECT alias FROM aliases WHERE mrn=?", (mrn,)).fetchone()
        if row:
            return row[0]
        # BEGIN IMMEDIATE takes the write lock up front, so two processes
        # cannot both read the same counter value before either writes.
        for attempt in range(5):
            try:
                self.con.execute("BEGIN IMMEDIATE")
                row = self.con.execute(
                    "SELECT alias FROM aliases WHERE mrn=?", (mrn,)
                ).fetchone()
                if row:
                    self.con.rollback()
                    return row[0]
                alias = f"{self.prefix}-{self._next_number():04d}"
                self.con.execute(
                    "INSERT INTO aliases(alias, mrn, created) VALUES(?,?,?)",
                    (alias, mrn, datetime.date.today().isoformat()),
                )
                self.con.commit()
                return alias
            except sqlite3.OperationalError:
                self.con.rollback()
                if attempt == 4:
                    raise
        raise AssertionError("unreachable")

    def upsert_patient(self, mrn: str, name: str | None, birth: str | None) -> None:
        """Record what we know, without ever overwriting a known value with None.

        ``first_seen``/``last_seen`` are maintained here; ``visit_count`` and
        ``last_dx`` are reserved columns that nothing populates yet.
        """
        today = datetime.date.today().isoformat()
        self.con.execute(
            """INSERT INTO patients(mrn, name, birth, first_seen, last_seen)
               VALUES(?,?,?,?,?)
               ON CONFLICT(mrn) DO UPDATE SET
                   name = COALESCE(excluded.name, name),
                   birth = COALESCE(excluded.birth, birth),
                   first_seen = COALESCE(first_seen, excluded.first_seen),
                   last_seen = excluded.last_seen""",
            (mrn, name, birth, today, today),
        )
        self.con.commit()

    def lookup(self, mrn: str) -> tuple[str | None, str | None]:
        """Return ``(name, birth)`` for a chart number we have seen before."""
        row = self.con.execute(
            "SELECT name, birth FROM patients WHERE mrn=?", (mrn,)
        ).fetchone()
        return (row[0], row[1]) if row else (None, None)

    def others(self, exclude_mrn: str | None = None) -> list[tuple[str, str | None]]:
        """Every ``(mrn, name)`` pair except the one given."""
        return list(
            self.con.execute(
                "SELECT mrn, name FROM patients WHERE mrn != ?", (exclude_mrn or "",)
            ).fetchall()
        )

    def all_known(self) -> list[tuple[str, str | None]]:
        """Every ``(mrn, name)`` pair on record — the residue check's input."""
        return list(self.con.execute("SELECT mrn, name FROM patients").fetchall())

    def resolve(self, alias: str) -> tuple[str, str | None, str | None, str | None, str | None] | None:
        """Re-identify an alias. Returns ``(alias, mrn, name, birth, last_dx)``."""
        return self.con.execute(
            """SELECT a.alias, p.mrn, p.name, p.birth, p.last_dx
               FROM aliases a LEFT JOIN patients p ON a.mrn = p.mrn
               WHERE a.alias = ?""",
            (alias.upper(),),
        ).fetchone()

    def roster(self) -> list[tuple[str, str | None]]:
        """Every ``(alias, birth)`` — safe to print, holds no identifiers."""
        return list(
            self.con.execute(
                """SELECT a.alias, p.birth FROM aliases a
                   LEFT JOIN patients p ON a.mrn = p.mrn ORDER BY a.alias"""
            ).fetchall()
        )
