"""Every decision or ticket id the repository cites resolves to its record
(PR Head and Validator, 2026-10-21; after OWNER-SOLVER-READINESS-SCIENCE-
DELEGATION-01 was cited for six days with no record behind it).

An id is a derived prefix followed by dash-separated upper-case segments
ending in a number (`OWNER-L4-VALUES-01`, `VALIDATOR-05`). The prefixes are
derived from `.agent/decisions` filenames, never hardcoded, so a new record
family is covered as soon as its first record lands, and a look-alike such as
a GPU model (`A100-SXM4-80`) is not. Its boundaries are whitelists (space,
quotes, brackets, punctuation, `/`), so a prefix never matches inside a
longer id (`GATE-DESIGN-01` in `FEASIBILITY-GATE-DESIGN-01`), a ticket path's
`_slug` or a file label (`R4.L4-G-CONSTRUCTOR-3.json`).

Cited ids are scanned in tracked files under `carbon/`, `scripts/` and
`docs/development/evidence/`. An id resolves when it is
- declared by a `.agent/decisions` record (its content or filename);
- recorded in `.agent/DECISIONS.md`, where historical decisions stay
  (AGENTS.md); or
- a ticket id with a `.agent/tickets` file. A ticket is authoritative for its
  own id; demanding a decision record for a ticket would only manufacture
  records to satisfy this test.

Ids that were already unresolved on 2026-10-21 are listed in `UNRECORDED`.
The Validator triages them. The list only shrinks: a new unresolved id fails,
and a listed id that now resolves or is no longer cited must be removed.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.invariant

ROOT = Path(__file__).resolve().parents[2]
DECISIONS = ROOT / ".agent" / "decisions"
HISTORY = ROOT / ".agent" / "DECISIONS.md"
TICKETS = ROOT / ".agent" / "tickets"
SCANNED = ("carbon", "scripts", "docs/development/evidence")
_DATE = re.compile(r"\A\d{4}-\d{2}-\d{2}-")
#: What may stand next to an id (the text's edge always may): a whitelist,
#: not a blacklist, since `-`, `_` and `.` each once let a non-id through.
_BEFORE = r"\s\"'`(\[{<,;:=/*|>"
_AFTER = r"\s\"'`)\]}>,;:.!?/*|"

#: Cited and unresolved on 2026-10-21 (derived over the base 2a0f504a6, the
#: tree this runs on). Shrink only.
UNRECORDED = frozenset(
    {
        "BATTERY-IMPL-3",
        "BENCHMARK-READINESS-BUILD-01",
        "CHALLENGE-COLD-PLATE-02",
        "CHALLENGE-PHOTONIC-02",
        "CHALLENGE-PROTOCOL-04",
        "CHAMPIONSHIP-03",
        "CHAMPIONSHIP-04",
        "EVIDENCE-ENTRYPOINTS-01",
        "GRAPHITE-GRANT-L4-G-CONSTRUCTOR-2",
        "GRAPHITE-GRANT-L4-G-CONSTRUCTOR-3",
        "GRAPHITE-GRANT-RESEARCH-SCORELAB-1",
        "GRAPHITE-L4-STARTER-01",
        "GRAPHITE-L5-HUNT-01",
        "GRAPHITE-POD-LAUNCH-RETRY-01",
        "GRAPHITE-PROGRESS-01",
        "GRAPHITE-RESEARCH-SCORELAB-01",
        "LAUNCHPAD-BATTERY-L4-ENSEMBLE-01",
        "LAUNCHPAD-SMOKE-PRACTICE-01",
        "LP-02",
        "LP-03",
        "OPT-07",
        "OPT-09",
        "OWNER-BACKBONE-CATALOG-01",
        "OWNER-RUNPOD-SOLVER-READINESS-01",
        "PHYSICS-CALIBRATION-01",
        "PHYSICS-CONSISTENCY-GATES-01",
        "PILOT-RUNNABILITY-TOP2-01",
        "PLT-13",
        "PLT-36",
        "REFERENCE-SOLVERS-HOST-MESH-01",
        "SCORE-CEILING-01",
        "VALIDATOR-33",
    }
)


def _records():
    return sorted(p for p in DECISIONS.iterdir() if p.is_file())


def _stem(path):
    return _DATE.sub("", path.stem)


def _pattern():
    prefixes = {re.split(r"[-_]", _stem(p))[0] for p in _records()} - {""}
    alternation = "|".join(
        re.escape(p) for p in sorted(prefixes, key=len, reverse=True)
    )
    return prefixes, re.compile(
        rf"(?<![^{_BEFORE}])(?:{alternation})(?:-[A-Z0-9_]+)*-\d+(?![^{_AFTER}])"
    )


def _text(path):
    try:
        return path.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def _resolved(pattern):
    declared = set()
    for path in _records():
        declared.add(_stem(path))
        declared.update(pattern.findall(_text(path)))
    if HISTORY.is_file():
        declared.update(pattern.findall(_text(HISTORY)))
    if TICKETS.is_dir():
        declared.update(re.split(r"[_.]", p.name)[0] for p in TICKETS.iterdir())
    return declared


def _cited(pattern):
    # Fail, never skip, when git is missing: the tracked tree is the scope.
    assert shutil.which("git"), "git is required for this invariant"
    tracked = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "-z", "--", *SCANNED],
        capture_output=True,
        check=True,
    ).stdout.split(b"\0")
    cited = {}
    for name in filter(None, tracked):
        relative = name.decode("utf-8")
        for found in set(pattern.findall(_text(ROOT / relative))):
            cited.setdefault(found, []).append(relative)
    return cited


@pytest.fixture(scope="module")
def scan():
    prefixes, pattern = _pattern()
    return {
        "prefixes": prefixes,
        "declared": _resolved(pattern),
        "cited": _cited(pattern),
    }


def test_the_scan_sees_the_record_families_and_their_citations(scan):
    prefixes, declared, cited = scan["prefixes"], scan["declared"], scan["cited"]
    # A broken derivation or an empty checkout would pass vacuously.
    assert {"OWNER", "VALIDATOR", "LAUNCHPAD"} <= prefixes
    assert len(prefixes) >= 100 and len(declared) >= 500 and len(cited) >= 300


def test_every_cited_id_resolves_or_is_listed(scan):
    declared, cited = scan["declared"], scan["cited"]
    unresolved = {i: paths for i, paths in cited.items() if i not in declared}
    new = {
        i: sorted(paths)[:3] for i, paths in unresolved.items() if i not in UNRECORDED
    }
    assert not new, f"cited ids with no decision, history or ticket record: {new}"


def test_the_unrecorded_list_only_shrinks(scan):
    declared, cited = scan["declared"], scan["cited"]
    stale = sorted(i for i in UNRECORDED if i in declared or i not in cited)
    assert (
        not stale
    ), f"now resolved or no longer cited; remove from UNRECORDED: {stale}"


@pytest.mark.parametrize(
    "text, found",
    [
        ("see OWNER-L4-VALUES-01.", ["OWNER-L4-VALUES-01"]),
        ("VALIDATOR-05 and PLT-13", ["VALIDATOR-05", "PLT-13"]),
        ("FEASIBILITY-GATE-DESIGN-01", []),  # GATE only inside a longer id
        (".agent/tickets/CHALLENGE-MOTOR-01_development.md", []),
        ("an A100-SXM4-80 GPU", []),
        ("reviews/R4.L4-G-CONSTRUCTOR-3.json", []),
        ("OWNER-L4-VALUES-01-draft", []),
    ],
)
def test_the_id_boundaries(text, found):
    prefixes, pattern = _pattern()
    if "FEASIBILITY" in prefixes or "A100" in prefixes:
        pytest.fail("a fixture prefix became a record family; update this test")
    assert pattern.findall(text) == found
