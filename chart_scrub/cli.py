"""Command line interface.

    chart-scrub mask   [FILE]        rules only, no database, prints to stdout
    chart-scrub ingest FILE          full pipeline, writes .deid.txt files
    chart-scrub verify FILE...       re-run the residue check on finished files
    chart-scrub who    PT-0001       re-identify — prints a real name, see below
    chart-scrub list                 aliases and ages only, safe to show anyone

``who`` is the only command that prints an identifier. Run it in your own
terminal. Do not run it through an AI assistant, and do not paste its output
anywhere.

Exit codes: 0 success, 2 residue check failed (do not use the output file).
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys

from .pseudonymize import ingest, process_record, residue_check
from .rules import deidentify_verbose
from .store import DEFAULT_DB, AliasStore


def read_text(path: str) -> str:
    """Read a file that may be UTF-8, UTF-16 or Big5 — clinic exports vary.

    UTF-16 is only attempted when the file actually carries a byte order mark.
    Without that guard, Python happily decodes a Big5 file as little-endian
    UTF-16 and returns mojibake: no exception, no warning, and a pipeline that
    reports success while de-identifying nothing, because none of the patterns
    match garbage. A silent pass is the worst possible failure here.
    """
    raw = open(path, "rb").read()
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        try:
            return raw.decode("utf-16")
        except (UnicodeDecodeError, UnicodeError):
            pass
    for enc in ("utf-8-sig", "cp950"):
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, UnicodeError):
            continue
    return raw.decode("utf-8", errors="replace")


def _load_input(path: str | None) -> str:
    if path in (None, "-"):
        return sys.stdin.read()
    return read_text(path)  # type: ignore[arg-type]


# ---------------------------------------------------------------- commands
def cmd_mask(args: argparse.Namespace) -> int:
    text, hits = deidentify_verbose(_load_input(args.file), do_normalize=not args.raw)
    sys.stdout.write(text)
    if args.stats:
        total = sum(hits.values())
        print(f"\n--- {total} masked: " + ", ".join(f"{k}×{v}" for k, v in hits.items()),
              file=sys.stderr)
    return 0


def cmd_ingest(args: argparse.Namespace) -> int:
    text = _load_input(args.file)
    out_dir = args.out or (os.path.dirname(os.path.abspath(args.file)) if args.file else ".")
    os.makedirs(out_dir, exist_ok=True)

    with AliasStore(args.db, prefix=args.prefix) as store:
        if args.mrn or args.name or args.birth:
            # Explicit identity given: treat the input as exactly one record.
            results = [process_record(store, text, args.mrn, args.name, args.birth)]
            results[0].leaks = residue_check(store, results[0].text)
        else:
            results = ingest(store, text)

        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        for r in results:
            base = f"{r.alias or 'UNKNOWN'}_{stamp}"
            path = os.path.join(out_dir, base + ".deid.txt")
            n = 1
            while os.path.exists(path):
                path = os.path.join(out_dir, f"{base}_{n}.deid.txt")
                n += 1
            with open(path, "w", encoding="utf-8") as f:
                f.write(r.text)
            r.path = path

    ok = all(r.ok for r in results)
    if args.json:
        print(json.dumps(
            {"ok": ok, "count": len(results),
             "records": [{"alias": r.alias, "age": r.age, "out": r.path,
                          "stats": r.stats, "identified": r.identified,
                          "leaks": r.leaks} for r in results]},
            ensure_ascii=False))
    else:
        print(f"{len(results)} record(s):")
        for r in results:
            head = f"  {r.alias or '⚠️ unidentified'}"
            if r.age is not None:
                head += f" ({r.age}y)"
            print(head + "  " + ", ".join(f"{k}:{v}" for k, v in r.stats.items()))
            print(f"    -> {os.path.basename(r.path or '')}")
            if r.leaks:
                print(f"    residue check FAILED: {','.join(r.leaks)} — do not use this file")
        print("all records passed the residue check" if ok else "residue check failed")
    return 0 if ok else 2


def cmd_verify(args: argparse.Namespace) -> int:
    ok = True
    with AliasStore(args.db) as store:
        for path in args.files:
            leaks = residue_check(store, read_text(path))
            if leaks:
                ok = False
                print(f"FAIL {path}: {','.join(leaks)}")
            elif not args.quiet:
                print(f"ok   {path}")
    return 0 if ok else 2


def cmd_who(args: argparse.Namespace) -> int:
    with AliasStore(args.db) as store:
        row = store.resolve(args.alias)
    if not row:
        print("no such alias")
        return 1
    alias, mrn, name, birth, last_dx = row
    print(f"{alias} = {name} (chart {mrn}, born {birth}) {last_dx or ''}")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    from .pseudonymize import age_from_birth

    with AliasStore(args.db) as store:
        for alias, birth in store.roster():
            age = age_from_birth(birth)
            print(f"  {alias}  {age if age is not None else '?'}y")
    return 0


# ---------------------------------------------------------------- parser
def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="chart-scrub", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=DEFAULT_DB,
                    help=f"alias database (default: {DEFAULT_DB})")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("mask", help="rules only, no database")
    p.add_argument("file", nargs="?", help="input file, or - for stdin")
    p.add_argument("--raw", action="store_true",
                   help="skip NFKC normalisation (full-width digits may slip through)")
    p.add_argument("--stats", action="store_true", help="print per-rule hit counts to stderr")
    p.set_defaults(fn=cmd_mask)

    p = sub.add_parser("ingest", help="full pseudonymisation pipeline")
    p.add_argument("file", nargs="?", help="input file, or - for stdin")
    p.add_argument("--out", help="output directory (default: next to the input)")
    p.add_argument("--prefix", default="PT", help="alias prefix (default: PT)")
    p.add_argument("--mrn"), p.add_argument("--name"), p.add_argument("--birth")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_ingest)

    p = sub.add_parser("verify", help="re-run the residue check on finished files")
    p.add_argument("files", nargs="+")
    p.add_argument("--quiet", action="store_true", help="only print failures")
    p.set_defaults(fn=cmd_verify)

    p = sub.add_parser("who", help="re-identify an alias (prints a real name)")
    p.add_argument("alias")
    p.set_defaults(fn=cmd_who)

    p = sub.add_parser("list", help="aliases and ages only")
    p.set_defaults(fn=cmd_list)
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
