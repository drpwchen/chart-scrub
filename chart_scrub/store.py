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
    def alias_for(self, mrn: str) -> str:
        """Return the stable alias for a chart number, creating it if new."""
        row = self.con.execute("SELECT alias FROM aliases WHERE mrn=?", (mrn,)).fetchone()
        if row:
            return row[0]
        n = self.con.execute("SELECT COUNT(*) FROM aliases").fetchone()[0] + 1
        alias = f"{self.prefix}-{n:04d}"
        self.con.execute(
            "INSERT INTO aliases(alias, mrn, created) VALUES(?,?,?)",
            (alias, mrn, datetime.date.today().isoformat()),
        )
        self.con.commit()
        return alias

    def upsert_patient(self, mrn: str, name: str | None, birth: str | None) -> None:
        """Record what we know, without ever overwriting a known value with None."""
        self.con.execute(
            """INSERT INTO patients(mrn, name, birth) VALUES(?,?,?)
               ON CONFLICT(mrn) DO UPDATE SET
                   name = COALESCE(excluded.name, name),
                   birth = COALESCE(excluded.birth, birth)""",
            (mrn, name, birth),
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
