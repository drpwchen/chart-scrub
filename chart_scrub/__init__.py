"""chart-scrub — de-identify Traditional Chinese (Taiwan) clinical text locally.

Two layers, usable separately:

* :mod:`chart_scrub.rules` — a regex masking engine, no state, no database.
* :mod:`chart_scrub.pseudonymize` — a pipeline that swaps each patient for a
  stable alias (PT-0001) and keeps the mapping in a local SQLite file. It also
  runs backwards: :func:`~chart_scrub.pseudonymize.rehydrate` turns aliases in
  a reply back into names, so text can go out to a model and come back
  readable.
"""

from .rules import RULES, Rule, deidentify, deidentify_verbose, normalize
from .pseudonymize import (
    RecordResult,
    RehydrateResult,
    detect_identity,
    ingest,
    process_record,
    rehydrate,
    residue_check,
    split_records,
)
from .store import DEFAULT_DB, AliasStore

__version__ = "0.6.0"

__all__ = [
    "__version__",
    "RULES",
    "Rule",
    "deidentify",
    "deidentify_verbose",
    "normalize",
    "AliasStore",
    "DEFAULT_DB",
    "RecordResult",
    "RehydrateResult",
    "detect_identity",
    "split_records",
    "process_record",
    "ingest",
    "residue_check",
    "rehydrate",
]
