"""The PUBLIC king card: the crowned grade's statistics, rendered from its private grade breakdown (`grade_breakdown`)
under Validator-2's standing ruling (codex-queue/reports/KING_STATS_DISCLOSURE_20261119.md, 19 Nov 2026).

A closed allow-list, like `queue_public`: the card's key set is pinned (`CARD_KEYS` and the nested sets), and anything
the ruling refuses is never read into it. A breakdown that does not satisfy every condition refuses the WHOLE card
(`KingCardRefused`, a closed code), never a partial one. What it shows, and nothing else:

- ``halves``: the A and D halves, rounded as the public total is (`koth_public.shown_total`);
- ``outputs``: per registered public output name and public class, the median and p90 error at 2 significant digits
  (``metric`` names what the record measures); a class not in the caller's public list is left out, never pooled;
- ``speed``: the scored single-design median at 2 significant digits, the public ceiling, the verdict, and the class
  label of the lane it was timed on (from the caller's closed map; a lane the map does not name refuses);
- ``gates``: PASS per registered gate (a crowned grade passed every gate; any FAIL refuses);
- ``provenance``: epoch, public pack id, grade time, code sha and the label: "official exam, epoch E" for a grade that
  kept its file, or "recomputed from the kept grade, self-check matched" for a king graded before it did.

Never shown (the ruling's refused classes): any per-case, per-row, per-set, per-task or menu value or id; max, min or
any tail past p90; any count (``n``, rows, calls); the per-call seconds or the lane's host; stats for an output or class
not in public registration; anything for a grade that is not the crowned one.

WHICH FILE (Lead, 19 Nov 2026): a crown is decided on the crowning grade AND its repeat. The repeat grades under its own
task id (`lean_recipe_retention.repeat_grade`), so it keeps its OWN breakdown file and never touches the crowning
grade's. The card reads exactly one file, the crowning grade's (`<crowned task>.grade-breakdown.json`), refuses a
breakdown whose ``submission_id`` is not the crowned task, and the render receipt (operator-only) names that file and
its sha256: the repeat can neither win nor lose silently.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from decimal import ROUND_HALF_UP, Decimal

from carbon.scoring import grade_breakdown as gb

SCHEMA = "carbon.king-card.v1"
CARD_KEYS = frozenset({"schema", "challenge", "version", "halves", "outputs", "speed", "gates", "provenance"})
HALF_KEYS = frozenset({"A", "D"})
OUTPUT_KEYS = frozenset({"output", "class", "metric", "median", "p90"})
SPEED_KEYS = frozenset({"median_seconds", "ceiling_seconds", "passed", "class"})
PROVENANCE_KEYS = frozenset({"label", "epoch", "pack_id", "graded_at", "code_sha"})
#: What the accuracy record's aggregates measure (`pool_physics_score._ratios`: |error| / U per reserved case).
METRIC = "abs_error_over_u"
OFFICIAL, RECOMPUTED = "official", "recomputed"
SIGNIFICANT = 2
_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:/-]{0,127}")
_EPOCH = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,31}")
_SHA = re.compile(r"[0-9a-f]{7,64}")
_TIME = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
_LABEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9 ._()/-]{0,79}")


class KingCardRefused(ValueError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _require(condition, code):
    if not condition:
        raise KingCardRefused(code)


def significant(value, digits=SIGNIFICANT):
    """``value`` at ``digits`` significant digits, half up (None stays None)."""
    if value is None:
        return None
    _require(type(value) in (int, float) and math.isfinite(value), "king_card_value_invalid")
    if value == 0:
        return 0.0
    exact = Decimal(repr(float(value)))
    exponent = exact.adjusted() - digits + 1
    return float(exact.quantize(Decimal(1).scaleb(exponent), rounding=ROUND_HALF_UP))


def _shown_total(value):
    if value is None:
        return None
    from carbon.challenge_validator import koth_public

    return koth_public.shown_total(value)


def _names(value, code):
    _require(type(value) in (list, tuple, set, frozenset), code)
    names = set(value)
    _require(all(type(n) is str and _NAME.fullmatch(n) for n in names), code)
    return names


def render(
    document,
    *,
    crowned_task,
    source,
    self_check_matched=False,
    epoch,
    pack_id,
    code_sha,
    public_outputs,
    public_classes,
    lane_classes,
    graded_at=None,
):
    """The public card of the crowned grade, or `KingCardRefused`. ``document`` is the crowning grade's checked
    breakdown; ``source`` is `OFFICIAL` (the grade kept it) or `RECOMPUTED` (the receipted recompute tool wrote it, and
    ``self_check_matched`` must be True); ``public_outputs`` / ``public_classes`` are the public registration's names;
    ``lane_classes`` maps a breakdown's speed lane to its public class label. ``graded_at``: the original grade's time,
    required for `RECOMPUTED` (its file was written at the recompute), refused for `OFFICIAL` (the file's own time)."""
    _require(type(document) is dict and set(document) == gb.FIELDS, "king_card_breakdown_invalid")
    try:
        checked = gb.breakdown(
            **{k: document[k] for k in gb.FIELDS - {"schema", "written_at"}},
            clock=gb._parsed_time(document["written_at"]),
        )
    except gb.GradeBreakdownRefused:
        raise KingCardRefused("king_card_breakdown_invalid") from None
    _require(checked == document and document["schema"] == gb.SCHEMA, "king_card_breakdown_invalid")
    _require(type(crowned_task) is str and document["submission_id"] == crowned_task, "king_card_not_the_crowned_grade")
    _require(source in (OFFICIAL, RECOMPUTED), "king_card_source_invalid")
    _require(source == OFFICIAL or self_check_matched is True, "king_card_recompute_not_self_checked")
    if source == OFFICIAL:
        _require(graded_at is None, "king_card_graded_at_invalid")
        graded_at = document["written_at"]
    _require(type(graded_at) is str and _TIME.fullmatch(graded_at), "king_card_graded_at_invalid")
    _require(type(epoch) is str and _EPOCH.fullmatch(epoch), "king_card_epoch_invalid")
    _require(type(pack_id) is str and _NAME.fullmatch(pack_id), "king_card_pack_id_invalid")
    _require(type(code_sha) is str and _SHA.fullmatch(code_sha), "king_card_code_sha_invalid")
    outputs_public = _names(public_outputs, "king_card_public_names_invalid")
    classes_public = _names(public_classes, "king_card_public_names_invalid")
    _require(type(lane_classes) is dict, "king_card_lane_classes_invalid")
    _require(
        all(type(k) is str and type(v) is str and _LABEL.fullmatch(v) for k, v in lane_classes.items()),
        "king_card_lane_classes_invalid",
    )
    # gates: a crowned grade passed every one
    flags = document["rule_flags"]
    _require(flags and all(v is True for v in flags.values()), "king_card_gate_not_passed")
    halves = document["halves"]
    _require(all(halves[k] is not None for k in HALF_KEYS), "king_card_halves_missing")
    # outputs: public output x public class only; median and p90 only
    shown = []
    for row in document["outputs"] or []:
        if row["output"] not in outputs_public or row["class"] not in classes_public:
            continue
        if row["median"] is None or row["p90"] is None:
            continue
        shown.append(
            {
                "output": row["output"],
                "class": row["class"],
                "metric": METRIC,
                "median": significant(row["median"]),
                "p90": significant(row["p90"]),
            }
        )
    shown.sort(key=lambda r: (r["output"], r["class"]))
    speed = document["speed"]
    _require(speed is not None, "king_card_speed_missing")
    _require(speed["lane"] in lane_classes, "king_card_speed_class_unnamed")
    card = {
        "schema": SCHEMA,
        "challenge": document["challenge_id"],
        "version": document["challenge_version"],
        "halves": {k: _shown_total(halves[k]) for k in sorted(HALF_KEYS)},
        "outputs": shown,
        "speed": {
            "median_seconds": significant(speed["median_seconds"]),
            "ceiling_seconds": speed["ceiling_seconds"],
            "passed": speed["passed"],
            "class": lane_classes[speed["lane"]],
        },
        "gates": {name: "PASS" for name in sorted(flags)},
        "provenance": {
            "label": (
                f"official exam, epoch {epoch}"
                if source == OFFICIAL
                else "recomputed from the kept grade, self-check matched"
            ),
            "epoch": epoch,
            "pack_id": pack_id,
            "graded_at": graded_at,
            "code_sha": code_sha,
        },
    }
    return check_card(card)


def check_card(card):
    """``card`` when its key set is exactly the pinned one at every level, else `KingCardRefused` (fail closed)."""
    _require(type(card) is dict and set(card) == CARD_KEYS and card["schema"] == SCHEMA, "king_card_keys")
    _require(type(card["halves"]) is dict and set(card["halves"]) == HALF_KEYS, "king_card_keys")
    _require(type(card["outputs"]) is list, "king_card_keys")
    _require(all(type(r) is dict and set(r) == OUTPUT_KEYS for r in card["outputs"]), "king_card_keys")
    _require(type(card["speed"]) is dict and set(card["speed"]) == SPEED_KEYS, "king_card_keys")
    _require(type(card["gates"]) is dict and set(card["gates"].values()) <= {"PASS"}, "king_card_keys")
    _require(type(card["provenance"]) is dict and set(card["provenance"]) == PROVENANCE_KEYS, "king_card_keys")
    return card


def dumps(card):
    """Canonical public bytes of a checked card."""
    return json.dumps(check_card(card), sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def text(card):
    """The card as plain lines, for the owner's sign-off and posts."""
    card = check_card(card)
    lines = [
        f"King card: {card['challenge']} {card['version']} ({card['provenance']['label']})",
        f"A half {card['halves']['A']}, D half {card['halves']['D']}",
    ]
    for row in card["outputs"]:
        lines.append(
            f"{row['output']} [{row['class']}] error as a multiple of the exam's U:"
            f" median {row['median']:g}, p90 {row['p90']:g}"
        )
    speed = card["speed"]
    lines.append(
        f"Speed: median {speed['median_seconds']:g} s per design on {speed['class']}"
        f" (ceiling {speed['ceiling_seconds']:g} s, {'PASS' if speed['passed'] else 'FAIL'})"
    )
    lines.append("Gates: " + ", ".join(f"{g} PASS" for g in card["gates"]))
    p = card["provenance"]
    lines.append(f"Pack {p['pack_id']}, graded {p['graded_at']}, code {p['code_sha']}")
    return "\n".join(lines) + "\n"


HOST_CLASS_SCHEMA = "carbon.validator.host-class.v2"
#: The closed label of a lane no host-class record was ever measured for (V2, 19 Nov 2026: honest, never a guess); it
#: becomes the record id once the lane's own record is bound.
UNRECORDED_CLASS = "class not recorded"
_HOST_CLASS_ID = re.compile(r"VALIDATOR-HOST-CLASS-[A-Z0-9][A-Z0-9-]{0,58}")


def public_names(constants_bytes, challenge_id, version):
    """``(outputs, classes)`` from the PUBLIC registration (`pool_version.CONSTANTS`, the served pool constants): the
    version's registered scored outputs (its physics gate thresholds' names) and its public coverage class vocabulary.
    Anything missing refuses (never a guessed list)."""
    try:
        entry = json.loads(constants_bytes)["versions"][f"{challenge_id} {version}"]
        outputs = sorted(entry["physics"]["gate_threshold"])
        classes = list(entry["optimizer"]["coverage_class_vocabulary"])
    except (ValueError, KeyError, TypeError):
        raise KingCardRefused("king_card_registration_unreadable") from None
    _names(outputs, "king_card_registration_unreadable")
    _names(classes, "king_card_registration_unreadable")
    _require(bool(outputs) and bool(classes), "king_card_registration_unreadable")
    return outputs, classes


def lane_class(record_bytes):
    """The device class name of one lane from its host-class record (``id``, schema `HOST_CLASS_SCHEMA`); the card
    shows this name, never the lane's docker host."""
    try:
        record = json.loads(record_bytes)
    except ValueError:
        raise KingCardRefused("king_card_lane_class_record_invalid") from None
    _require(
        type(record) is dict
        and record.get("schema") == HOST_CLASS_SCHEMA
        and type(record.get("id")) is str
        and _HOST_CLASS_ID.fullmatch(record["id"]) is not None,
        "king_card_lane_class_record_invalid",
    )
    return record["id"]


def _sha256(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def receipt(
    card,
    breakdown_path,
    breakdown_bytes,
    crowned_task,
    registration=None,
    lanes=None,
):
    """The OPERATOR-ONLY render receipt: which breakdown file the card read (the crowning grade's), the public
    registration and the lane class records the names came from, each with its sha256."""
    return {
        "schema": "carbon.king-card-receipt.v1",
        "crowned_task": crowned_task,
        "breakdown_file": str(breakdown_path),
        "breakdown_sha256": _sha256(breakdown_bytes),
        "registration": registration,
        "lane_class_records": lanes,
        "card_sha256": _sha256(dumps(card)),
    }
