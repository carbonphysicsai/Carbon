"""Per-king model card for the Motor exam: public and aggregate values only (DEVELOPMENT, never qualification).

The card is built from two inputs and nothing else:

- the **signed public launch board** (`carbon.validator.launch-board.v6`), verified against a key the operator pins
  out of band (`launch_board.verify`). The king's identity, shown total, margin, bar and crown time come only from
  it, so the card can never show a finer total than the board does;
- an operator-written **facts** file (`FACTS_SCHEMA`): the king's task id, UID, model class and size, build and judge
  images, public gate values, reference cross-checks and, optionally, accuracy AGGREGATES that carry a Validator
  receipt id. Its shape is closed at every level: an unknown key, a non-finite number, an aggregate over fewer than
  `MIN_AGGREGATE_N` cases or a unit outside `ACCURACY_UNITS` refuses the whole card.

There is no path for a per-case value, a hidden input, a seed, a draw id or an uncertainty (U) value. A section the
facts leave out renders `NOT YET MEASURED`; nothing is guessed. The input envelope is read from the public domain
code (`carbon.motor.domain.INPUT_BOUNDS`).

The card is labelled DEVELOPMENT and NOT_QUALIFIED. It is an exam result restated for a reader, not a client
delivery, not a qualification receipt and not a rights grant (owner decision Q5a is open). It is unsigned; its
sha256 is written beside it (signing is a later step).

    python -m scripts.dev.customer_deliverable.king_card --board board.json --pinned-key HEX \
        --facts facts.json --out-dir OUT
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from pathlib import Path

from carbon.challenge_validator import launch_board as lb
from carbon.motor import domain

CARD_SCHEMA = "carbon.motor.king-card.v1"
FACTS_SCHEMA = "carbon.motor.king-card.facts.v1"
LABELS = ("DEVELOPMENT", "NOT_QUALIFIED")
NOT_MEASURED = "NOT YET MEASURED"
#: Disclosure floor, not a science value: an aggregate over fewer cases than this could restate single hidden cases,
#: so the card refuses it. Raising it is always safe; lowering it needs the Validator's receipt.
MIN_AGGREGATE_N = 10
#: Accuracy units a public card may carry. "U" (the exam's uncertainty unit) is deliberately absent.
ACCURACY_UNITS = ("relative", "N.m", "ratio_vs_classical")
ACCURACY_OUTPUTS = (
    "mean_torque",
    "torque_pkpk",
    "torque_waveform_shape",
    "ke_ll_loaded_shape",
    "open_circuit_emf_shape",
)
ACCURACY_SECTIONS = ("in_envelope", "beyond_envelope", "vs_classical")
GATE_UNITS = ("s/design", "s")
#: The public gates a card may name (Motor 1.8 kit): the speed gate, the graded inference wall and the
#: invalid-output check. A number on a gate always carries a unit, so a unitless score cannot ride on one.
GATE_NAMES = ("speed", "graded_wall", "finite_outputs")
#: Every number a card shows from the facts is rounded to this many significant digits: enough for a reader,
#: too coarse to carry an exact total or an unrounded hidden value.
SIGNIFICANT = 4
LIMITS = (
    "2-D periodic cross-section only: no end effects, no thermal model, no demagnetisation check.",
    "Fixed frame: 8 poles, 24 slots, single-layer winding (GRUCAD benchmark dimensions).",
    "Envelope = the public TRAIN box below; behaviour outside it is reported separately, never implied.",
    "Not qualified for any client use; an exam result only.",
    "Rights: no licence for client use is recorded for this submission (owner decision Q5a open).",
)
FACTS_FIELDS = frozenset(
    {
        "schema",
        "task_id",
        "uid",
        "hotkey",
        "model",
        "build",
        "judge",
        "gates",
        "accuracy",
        "reference",
    }
)
REQUIRED_FACTS = frozenset({"schema", "task_id", "uid", "hotkey"})
MODEL_FIELDS = frozenset({"class", "parameter_count", "state_digest", "recipe_hash"})
BUILD_FIELDS = frozenset({"image", "gpu_class", "build_seconds", "cpu_fallback"})
JUDGE_FIELDS = frozenset({"image", "receiver_commit"})
GATE_FIELDS = frozenset({"name", "result", "limit", "measured", "unit"})
ACCURACY_BLOCK_FIELDS = frozenset({"receipt", "outputs"})
OUTPUT_FIELDS = frozenset({"output", "n", "median", "p90", "ci95", "unit"})
REFERENCE_FIELDS = frozenset({"solver", "cross_checks"})
CROSS_CHECK_FIELDS = frozenset({"solver", "public_designs", "report"})
MAX_GATES = 16
MAX_CROSS_CHECKS = 8

_TASK = re.compile(r"rtsk_[0-9a-f]{8,64}")
_LABEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9 ._:/+()-]{0,95}")
_SHA256 = re.compile(r"sha256:[0-9a-f]{64}")
_HEX = re.compile(r"[0-9a-f]{8,128}")
_COMMIT = re.compile(r"[0-9a-f]{7,40}")
_REPORT = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,199}")
#: A free-text label never carries a long hex run (a seed, draw id or key looks like one); digests have own fields.
_HEX_RUN = re.compile(r"[0-9a-fA-F]{16,}")
_SS58 = re.compile(r"[1-9A-HJ-NP-Za-km-z]{47,48}")


class CardRefused(ValueError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False, ensure_ascii=True
    )


def _closed(raw, fields, code, *, required=None):
    needed = fields if required is None else required
    if type(raw) is not dict or not set(raw) <= fields or not needed <= set(raw):
        raise CardRefused(code)
    return raw


def _label(value, code, *, pattern=_LABEL, optional=False):
    if value is None and optional:
        return None
    if type(value) is not str or not pattern.fullmatch(value):
        raise CardRefused(code)
    if pattern in (_LABEL, _REPORT) and _HEX_RUN.search(value):
        raise CardRefused(code)
    return value


def _sig(value):
    """``value`` rounded to `SIGNIFICANT` significant digits (None stays None)."""
    if value is None or value == 0:
        return value
    return float(f"{value:.{SIGNIFICANT}g}")


def _number(value, code, *, optional=False, minimum=0.0):
    if value is None and optional:
        return None
    if (
        type(value) not in (int, float)
        or isinstance(value, bool)
        or not math.isfinite(value)
        or value < minimum
    ):
        raise CardRefused(code)
    return value


def _count(value, code, *, minimum=0):
    if type(value) is not int or value < minimum:
        raise CardRefused(code)
    return value


def _model(raw):
    if raw is None:
        return None
    raw = _closed(raw, MODEL_FIELDS, "card_model")
    return {
        "class": _label(raw["class"], "card_model"),
        "parameter_count": _count(raw["parameter_count"], "card_model", minimum=1),
        "state_digest": _label(
            raw["state_digest"], "card_model", pattern=_SHA256, optional=True
        ),
        "recipe_hash": _label(
            raw["recipe_hash"], "card_model", pattern=_HEX, optional=True
        ),
    }


def _build(raw):
    if raw is None:
        return None
    raw = _closed(raw, BUILD_FIELDS, "card_build")
    if type(raw["cpu_fallback"]) is not bool:
        raise CardRefused("card_build")
    return {
        "image": _label(raw["image"], "card_build"),
        "gpu_class": _label(raw["gpu_class"], "card_build", optional=True),
        "build_seconds": _sig(
            _number(raw["build_seconds"], "card_build", optional=True)
        ),
        "cpu_fallback": raw["cpu_fallback"],
    }


def _judge(raw):
    if raw is None:
        return None
    raw = _closed(raw, JUDGE_FIELDS, "card_judge")
    return {
        "image": _label(raw["image"], "card_judge"),
        "receiver_commit": _label(
            raw["receiver_commit"], "card_judge", pattern=_COMMIT
        ),
    }


def _gates(raw):
    if raw is None:
        return None
    if type(raw) is not list or len(raw) > MAX_GATES:
        raise CardRefused("card_gates")
    gates, seen = [], set()
    for gate in raw:
        gate = _closed(gate, GATE_FIELDS, "card_gates")
        name = gate["name"]
        if (
            name not in GATE_NAMES
            or name in seen
            or gate["result"] not in ("PASS", "FAIL")
        ):
            raise CardRefused("card_gates")
        limit = _number(gate["limit"], "card_gates", optional=True)
        measured = _number(gate["measured"], "card_gates", optional=True)
        if gate["unit"] is not None and gate["unit"] not in GATE_UNITS:
            raise CardRefused("card_gates")
        if (limit is not None or measured is not None) and gate["unit"] is None:
            raise CardRefused("card_gates")
        seen.add(name)
        gates.append(
            {
                "name": name,
                "result": gate["result"],
                "limit": _sig(limit),
                "measured": _sig(measured),
                "unit": gate["unit"],
            }
        )
    return gates


def _accuracy_block(raw, code):
    if raw is None:
        return None
    raw = _closed(raw, ACCURACY_BLOCK_FIELDS, code)
    outputs = raw["outputs"]
    if type(outputs) is not list or not outputs or len(outputs) > len(ACCURACY_OUTPUTS):
        raise CardRefused(code)
    rows, seen = [], set()
    for row in outputs:
        row = _closed(row, OUTPUT_FIELDS, code)
        if (
            row["output"] not in ACCURACY_OUTPUTS
            or row["output"] in seen
            or row["unit"] not in ACCURACY_UNITS
        ):
            raise CardRefused(code)
        seen.add(row["output"])
        n = _count(row["n"], code, minimum=MIN_AGGREGATE_N)
        median = _number(row["median"], code)
        p90 = _number(row["p90"], code)
        ci = row["ci95"]
        if type(ci) is not list or len(ci) != 2:
            raise CardRefused(code)
        low, high = (_number(value, code) for value in ci)
        if not median <= p90 or not low <= median <= high:
            raise CardRefused(code)
        rows.append(
            {
                "output": row["output"],
                "n": n,
                "median": _sig(median),
                "p90": _sig(p90),
                "ci95": [_sig(low), _sig(high)],
                "unit": row["unit"],
            }
        )
    return {"receipt": _label(raw["receipt"], code), "outputs": rows}


def _accuracy(raw):
    if raw is None:
        return dict.fromkeys(ACCURACY_SECTIONS)
    raw = _closed(
        raw, frozenset(ACCURACY_SECTIONS), "card_accuracy", required=frozenset()
    )
    return {
        name: _accuracy_block(raw.get(name), "card_accuracy")
        for name in ACCURACY_SECTIONS
    }


def _reference(raw):
    if raw is None:
        return None
    raw = _closed(raw, REFERENCE_FIELDS, "card_reference")
    checks = raw["cross_checks"]
    if type(checks) is not list or len(checks) > MAX_CROSS_CHECKS:
        raise CardRefused("card_reference")
    out = []
    for check in checks:
        check = _closed(check, CROSS_CHECK_FIELDS, "card_reference")
        out.append(
            {
                "solver": _label(check["solver"], "card_reference"),
                "public_designs": _count(
                    check["public_designs"], "card_reference", minimum=1
                ),
                "report": _label(check["report"], "card_reference", pattern=_REPORT),
            }
        )
    return {"solver": _label(raw["solver"], "card_reference"), "cross_checks": out}


def facts_checked(raw):
    """The closed facts document, or a `CardRefused`."""
    raw = _closed(raw, FACTS_FIELDS, "card_facts", required=REQUIRED_FACTS)
    if raw["schema"] != FACTS_SCHEMA:
        raise CardRefused("card_facts_schema")
    return {
        "task_id": _label(raw["task_id"], "card_task", pattern=_TASK),
        "uid": _count(raw["uid"], "card_uid"),
        "hotkey": _label(raw["hotkey"], "card_hotkey", pattern=_SS58),
        "model": _model(raw.get("model")),
        "build": _build(raw.get("build")),
        "judge": _judge(raw.get("judge")),
        "gates": _gates(raw.get("gates")),
        "accuracy": _accuracy(raw.get("accuracy")),
        "reference": _reference(raw.get("reference")),
    }


def build_card(board, pinned_key, facts):
    """The card for the king of ``board`` (verified against ``pinned_key``), or a `CardRefused`."""
    try:
        board = lb.verify(board, pinned_key)
    except lb.BoardRefused as refused:
        raise CardRefused(refused.code) from None
    if board["schema"] != lb.SCHEMA_V6:
        raise CardRefused("card_board_version")
    king_section = board["king"]
    king = king_section["king"]
    if king is None:
        raise CardRefused("card_no_king")
    checked = facts_checked(facts)
    if checked["hotkey"] != king["hotkey"]:
        raise CardRefused("card_hotkey_mismatch")
    challenge = board["challenge"]
    card = {
        "schema": CARD_SCHEMA,
        "labels": list(LABELS),
        "source": {
            "board_schema": board["schema"],
            "board_version": board["version"],
            "board_generated_at": board["generated_at"],
            "board_sha256": hashlib.sha256(canonical(board).encode()).hexdigest(),
            "facts_sha256": hashlib.sha256(canonical(facts).encode()).hexdigest(),
        },
        "identity": {
            "challenge_id": challenge["id"],
            "challenge_version": challenge["version"],
            "exam_version_label": challenge["exam_version_label"],
            "network": board["network"],
            "task_id": checked["task_id"],
            "uid": checked["uid"],
            "hotkey": king["hotkey"],
            "since_epoch": king["since_epoch"],
            "crowned_utc": king_section["crowned_utc"],
        },
        "score": {
            "total_shown": king["total"],
            "margin": king_section["margin"],
            "to_beat": king_section["to_beat"],
            "to_beat_rule": king_section["to_beat_rule"],
        },
        "gates": checked["gates"],
        "model": checked["model"],
        "build": checked["build"],
        "judge": checked["judge"],
        "accuracy": checked["accuracy"],
        "reference": checked["reference"],
        "envelope": {
            name: list(bounds) for name, bounds in domain.INPUT_BOUNDS.items()
        },
        "limits": list(LIMITS),
        "status": {
            "client_use": "NOT_QUALIFIED",
            "basis": "EXAM_RESULT_ONLY",
            "rights": "UNDECIDED",
        },
    }
    return card


def _cell(value):
    if value is None:
        return NOT_MEASURED
    if type(value) is bool:
        return "yes" if value else "no"
    return str(value)


def render_markdown(card, digest):
    ident, score = card["identity"], card["score"]
    lines = [
        f"# King model card: {ident['challenge_id']} {ident['challenge_version']}, UID {ident['uid']}",
        "",
        f"**{' / '.join(card['labels'])}.** An exam result restated for a reader. Not a client delivery, not a",
        "qualification and not a rights grant. Public and aggregate values only.",
        "",
        "## Identity and score (from the signed public board)",
        "",
        "| Field | Value |",
        "|---|---|",
    ]
    rows = [
        (
            "Exam",
            f"{ident['challenge_id']} {ident['challenge_version']} ({ident['exam_version_label']})",
        ),
        ("Network", ident["network"]),
        ("Task", ident["task_id"]),
        ("UID / hotkey", f"{ident['uid']} / {ident['hotkey']}"),
        ("Crowned (UTC)", ident["crowned_utc"]),
        ("Total (as shown on the board)", score["total_shown"]),
        (
            "Margin / score to beat",
            f"{_cell(score['margin'])} / {_cell(score['to_beat'])} ({score['to_beat_rule']})",
        ),
    ]
    lines += [f"| {name} | {_cell(value)} |" for name, value in rows]
    lines += ["", "## Gates", ""]
    if card["gates"] is None:
        lines.append(NOT_MEASURED)
    else:
        lines += [
            "| Gate | Result | Limit | Measured | Unit |",
            "|---|---|---|---|---|",
        ]
        lines += [
            f"| {g['name']} | {g['result']} | {_cell(g['limit'])} | {_cell(g['measured'])} | {_cell(g['unit'])} |"
            for g in card["gates"]
        ]
    for title, key, fields in (
        ("Model", "model", ("class", "parameter_count", "state_digest", "recipe_hash")),
        ("Build", "build", ("image", "gpu_class", "build_seconds", "cpu_fallback")),
        ("Judge", "judge", ("image", "receiver_commit")),
    ):
        lines += ["", f"## {title}", ""]
        section = card[key]
        if section is None:
            lines.append(NOT_MEASURED)
        else:
            lines += ["| Field | Value |", "|---|---|"]
            lines += [f"| {name} | {_cell(section[name])} |" for name in fields]
    lines += ["", "## Accuracy against the reference (aggregates only)", ""]
    for name in ACCURACY_SECTIONS:
        block = card["accuracy"][name]
        lines.append(
            f"**{name.replace('_', ' ')}:** "
            + (NOT_MEASURED if block is None else f"receipt {block['receipt']}")
        )
        if block is not None:
            lines += [
                "",
                "| Output | n | Median | p90 | 95% CI | Unit |",
                "|---|---|---|---|---|---|",
            ]
            lines += [
                f"| {r['output']} | {r['n']} | {r['median']} | {r['p90']} | {r['ci95'][0]} to {r['ci95'][1]} | {r['unit']} |"
                for r in block["outputs"]
            ]
        lines.append("")
    lines += ["## Reference solver and independent cross-checks", ""]
    ref = card["reference"]
    if ref is None:
        lines.append(NOT_MEASURED)
    else:
        lines += [f"Reference: {ref['solver']}", ""]
        if ref["cross_checks"]:
            lines += [
                "| Cross-check solver | Public designs | Report |",
                "|---|---|---|",
            ]
            lines += [
                f"| {c['solver']} | {c['public_designs']} | {c['report']} |"
                for c in ref["cross_checks"]
            ]
        else:
            lines.append("Cross-checks: " + NOT_MEASURED)
    lines += [
        "",
        "## Input envelope (public TRAIN box)",
        "",
        "| Input | Low | High |",
        "|---|---|---|",
    ]
    lines += [
        f"| {name} | {low} | {high} |" for name, (low, high) in card["envelope"].items()
    ]
    lines += ["", "## Limits", ""] + [f"- {text}" for text in card["limits"]]
    status = card["status"]
    lines += [
        "",
        "## Status",
        "",
        f"Client use: {status['client_use']}. Basis: {status['basis']}. Rights: {status['rights']}.",
        "",
        f"Card sha256: `{digest}` (of card.json). Board sha256: `{card['source']['board_sha256']}`.",
        "",
    ]
    return "\n".join(lines)


def write_card(card, out_dir):
    out = Path(out_dir)
    paths = [out / "card.json", out / "card.md", out / "card.json.sha256"]
    if any(path.exists() or path.is_symlink() for path in paths):
        raise CardRefused("card_output_exists")
    body = canonical(card)
    digest = hashlib.sha256(body.encode()).hexdigest()
    contents = (
        body.encode() + b"\n",
        render_markdown(card, digest).encode("utf-8"),
        f"{digest}  card.json\n".encode(),
    )
    out.mkdir(parents=True, exist_ok=True)
    for path, data in zip(paths, contents, strict=True):
        try:
            with path.open("xb") as handle:
                handle.write(data)
        except FileExistsError:
            raise CardRefused("card_output_exists") from None
    return digest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--board", required=True)
    parser.add_argument("--pinned-key", required=True)
    parser.add_argument("--facts", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args(argv)
    try:
        board = json.loads(Path(args.board).read_text(encoding="utf-8"))
        facts = json.loads(Path(args.facts).read_text(encoding="utf-8"))
        digest = write_card(build_card(board, args.pinned_key, facts), args.out_dir)
    except CardRefused as refused:
        print(f"REFUSED {refused.code}", file=sys.stderr)
        return 2
    except (OSError, ValueError, RecursionError) as error:
        print(f"REFUSED card_input ({type(error).__name__})", file=sys.stderr)
        return 2
    print(digest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
