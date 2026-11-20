"""The one error table (miner-ux item 4): what a miner sees, what it means and what to do, whose side it is, and whether
anything was charged.

The words are NOT written here. The "what it means and what to do" column is `supervisor.NEXT_ACTIONS` (a refusal code) or
`projection.GRADE_STATE_WORDS` (a grade state), word for word, so the page, the Launchpad and docs/MINING.md cannot
disagree. This module adds only the two short columns a miner asked for ("ours or yours?", "was I charged?"), each worded
from what that sentence itself says: a refusal whose words do not say whether anything was charged says "Not stated",
never a guess. `render()` writes the markdown block that docs/MINING.md carries between `START` and `END`; a test fails
when the document and this table differ, so editing a sentence means regenerating the block:

    python -m scripts.dev.miner_launchpad.error_table --write docs/MINING.md

Ordered by what miners actually quote (miner-x, 20 Nov 2026), ours-first within each group. No hidden value, allowance
formula, hardware name or per-output detail appears; the codes are the closed ones a miner already sees.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

START = "<!-- error-table:start (generated: python -m scripts.dev.miner_launchpad.error_table --write docs/MINING.md) -->"
END = "<!-- error-table:end -->"

OURS = "Ours"
YOURS = "Yours"
RULE = "A rule, not a failure"
EITHER = "Either: your connection or the validator"
NOT_STATED = "Not stated"

#: (source, code, whose side, charged?). source "next" = `supervisor.NEXT_ACTIONS`; "grade" = `projection.GRADE_STATE_WORDS`.
ROWS = (
    # --- the validator turned the request away or could not take it: ours ---
    ("next", "TRANSPORT_STALE", OURS, "No: turned away before it was admitted"),
    ("next", "intake_busy", OURS, "No: nothing was sent, charged or graded"),
    ("next", "door_updating", OURS, "No: nothing was charged"),
    ("next", "capacity", OURS, NOT_STATED),
    ("next", "TRANSPORT_CAPACITY", OURS, NOT_STATED),
    ("next", "TRANSPORT_STORE", OURS, NOT_STATED),
    ("next", "allowance_group_unmapped", OURS, "No graded-exam slot was used"),
    ("next", "allowance_group_unresolved", OURS, "No graded-exam slot was used"),
    # --- the validator stopped or closed before it ran your submission: ours ---
    ("next", "direct_task_cancelled", OURS, "No: nothing was graded or charged"),
    ("next", "version_closed", OURS, "No: nothing was charged"),
    ("grade", "FAILED_INFRA", OURS, "No: a counted slot is given back"),
    ("grade", "NOT_GRADED", NOT_STATED, "No: the slot was given back and nothing was charged"),
    # --- a rule of the exam ---
    ("next", "hotkey_submission_waiting", RULE, "No: it used none of your allowance"),
    ("next", "coldkey_submission_waiting", RULE, "No: it used none of your allowance"),
    ("next", "epoch_limit_reached", RULE, "No: it used none of your allowance"),
    ("next", "exam_daily_allowance_reached", RULE, "No: it used none of your allowance"),
    ("next", "same_recipe_already_submitted", RULE, "No: this final exam is still unused"),
    ("grade", "ROUND_LIMIT_REACHED", RULE, "Not graded"),
    ("grade", "SUPERSEDED_BY_OWN_LATER_SUBMIT", YOURS + " (your own later submission)", "Not graded"),
    # --- yours to fix ---
    ("next", "TRANSPORT_RATE", YOURS + " (too many requests at once)", NOT_STATED),
    ("next", "rate", YOURS + " (too many requests)", NOT_STATED),
    ("next", "fitted_info_over_budget", YOURS, "Nothing was graded"),
    ("next", "candidate_build_refused", YOURS, "Nothing was graded"),
    ("grade", "RECONSTRUCTION_FAILED", YOURS, "Nothing was graded"),
    ("grade", "CANDIDATE_FAILED", YOURS, "Yes: counted as your try"),
    # --- could not reach the validator ---
    (
        "next",
        "construction_intake_unavailable",
        EITHER,
        "Not stated; if it got your submission, submitting again returns that result and it is never graded twice",
    ),
    (
        "next",
        "construction_request_deadline",
        EITHER,
        "Not stated; if it got your submission, submitting again returns that result and it is never graded twice",
    ),
)


def _cell(text):
    return re.sub(r"\s+", " ", str(text)).replace("|", "/").strip()


def _words(source, code):
    if source == "next":
        from scripts.dev.miner_launchpad import supervisor

        return supervisor.NEXT_ACTIONS[code]
    from scripts.dev.miner_launchpad import projection

    text = projection.GRADE_STATE_WORDS[code]
    return "Grade state: " + text[:1].upper() + text[1:] + "."


def render():
    """The markdown block (markers included) for docs/MINING.md."""
    lines = [
        START,
        "",
        "| You see | What it means and what to do | Whose side | Charged? |",
        "|---|---|---|---|",
    ]
    for source, code, side, charged in ROWS:
        lines.append(
            f"| `{_cell(code)}` | {_cell(_words(source, code))} | {_cell(side)} | {_cell(charged)} |"
        )
    lines += [
        "",
        "*Not stated* means that code's own words do not say, so this table does not guess. If a message repeats, "
        "send us the UTC time and the last 4 characters of your hotkey.",
        "",
        END,
    ]
    return "\n".join(lines)


def document_block(text):
    """The marked block inside ``text`` (markers included), or None."""
    start = text.find(START)
    end = text.find(END)
    if start < 0 or end < start:
        return None
    return text[start : end + len(END)]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--write", metavar="MINING_MD", help="rewrite the block in this file")
    args = parser.parse_args(argv)
    block = render()
    if not args.write:
        sys.stdout.write(block + "\n")
        return 0
    path = Path(args.write)
    text = path.read_bytes().decode("utf-8")
    old = document_block(text)
    if old is None:
        sys.stderr.write("the markers are not in the file; add them where the table goes\n")
        return 2
    path.write_bytes(text.replace(old, block).encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
