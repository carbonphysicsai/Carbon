"""f02 burst-thermal decks, VERSION 3.1 (Burst Thermal 3.1): the 3.0 deck (``f02_deck_v3``, imported UNCHANGED) with the 3.1 pins
and the custody-only observations. Physics is exactly 3.0's deck physics; only the signed law and the signed ranges differ.

PINS (fail closed). Every 3.1 deck refuses until each pin below is set by a reviewed change that cites its owner record:
- ``V31_LAW_DECISION`` / ``V31_LAW_SHA256``: the 3.1 leakage law, signed per the owner's BT 3.1 law sheet (ledger N8). The signed
  law FILE (its ``decision`` field = the record id) and its digest land together in one later change; no coefficient is here.
- ``V31_BOX_SHA256``: the public box of the PUBLIC stages (TRAIN, U panel, edge, gate probe).
- ``V31_REGION_SHA256``: the hidden region of the HIDDEN stages (battery). Digest only; the region file stays in custody.
  The region document carries a custody-random hex ``nonce`` (>= 128 bits), so its public digest cannot be brute-forced from
  round bounds. A 3.1 law pin equal to 3.0's signed law (decision or digest) refuses.
A case is written against EXACTLY ONE of the box or the region and must lie inside it. A TEST_ONLY law never writes a 3.1 deck.

CUSTODY-ONLY observations (owner directive via the researcher, 5 Nov 14:19: kept so a later version can grade them WITHOUT a
re-solve): ``observe_v31`` = ``observe_v3`` (the public scalars, unchanged) plus a ``custody`` block: the die-top trace per solver
step, the source (patch-centre) traces per step, and the time to a SECOND threshold (first upward crossing, interpolated, and the
total time above it). The second threshold is a required parameter with no default (its value is the owner's / Validator's pick).
``f02_deck_v3.SCALAR_KEYS`` / ``scalar_outputs`` are untouched, so a TRAIN row can never carry a custody field; ``custody_outputs``
returns only the custody block, labelled CUSTODY_ONLY.
``observe_v31`` refuses a deck record that is not a 3.1 deck (both version marks). A case that STARTS above the second threshold
reports ``ABOVE_AT_START`` (never "NOT_REACHED").
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

try:  # the repo layout (tests) and the flat reference-package layout (solve hosts) both import the 3.0 deck
    from scripts.dev.reference_packages.elmer import f02_deck_v3 as v3
except ModuleNotFoundError as missing:  # pragma: no cover - flat layout only
    if not (missing.name or "").startswith("scripts"):
        raise
    import f02_deck_v3 as v3

DeckRefused = v3.DeckRefused
HUMAN_INPUT = v3.HUMAN_INPUT
DECK_VERSION = "3.1"
CUSTODY_ONLY = "CUSTODY_ONLY"
REGION_SCHEMA = "carbon.f02.v31-region.v1"
ABOVE_AT_START = "ABOVE_AT_START"
#: a region document carries a custody-random hex nonce (>= 128 bits) so its public digest cannot be brute-forced from round bounds
REGION_NONCE_HEX_MIN = 32

#: The 3.1 pins. HUMAN_INPUT until a reviewed change sets each one from its owner record (fail closed).
#: OWNER-BT31-LAW-ANCHOR-SIGNED-01 (ledger N8): the law on the owner sheet BT31_LAW_OWNER_SHEET; the signed file stays in custody
#: staging (reports/BT31_LAW_SIGNED_20261106/leak_bt31_signed.json); only its digest is here, no coefficient.
V31_LAW_DECISION = "OWNER-BT31-LAW-ANCHOR-SIGNED-01"
V31_LAW_SHA256 = "f3eefda98fcadd0a14b3b1b57050a166a96c6a2e4fe66d8df49a037a5a42ae35"
V31_BOX_SHA256 = HUMAN_INPUT
V31_REGION_SHA256 = HUMAN_INPUT


def _is_pin(value):
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(c in "0123456789abcdef" for c in value)
    )


def pins_status():
    """Which 3.1 pins are still HUMAN_INPUT (an empty list = every pin set)."""
    open_pins = []
    if not (
        isinstance(V31_LAW_DECISION, str)
        and V31_LAW_DECISION
        and V31_LAW_DECISION != HUMAN_INPUT
    ):
        open_pins.append("V31_LAW_DECISION")
    for name in ("V31_LAW_SHA256", "V31_BOX_SHA256", "V31_REGION_SHA256"):
        if not _is_pin(globals()[name]):
            open_pins.append(name)
    return open_pins


def load_v31_law(path):
    """The signed 3.1 leakage law, or a refusal (pins unset, digest differs, a TEST_ONLY or another decision's file)."""
    if "V31_LAW_DECISION" in pins_status() or "V31_LAW_SHA256" in pins_status():
        raise DeckRefused("v31_law_pin_is_human_input")
    if (
        V31_LAW_DECISION == v3.SIGNED_LEAKAGE_DECISION
        or V31_LAW_SHA256 == v3.SIGNED_LEAKAGE_SHA256
    ):
        raise DeckRefused("v31_law_pin_is_the_3_0_law")
    leak = v3.load_leakage(path, expect_sha256=V31_LAW_SHA256)
    if leak["label"] != "REGISTERED" or leak["decision"] != V31_LAW_DECISION:
        raise DeckRefused("v31_law_not_the_signed_law")
    return leak


def _load_ranges(path, *, schema, want, pin_name):
    """An owner-signed range document (box or region): schema, status OWNER_SIGNED, its own sha field AND the canonical sha256 of
    the document without that field both equal to the pin, every input a closed finite range.
    """
    if not _is_pin(want):
        raise DeckRefused(f"{pin_name.lower()}_is_human_input")
    doc = json.loads(Path(path).read_bytes())
    if type(doc) is not dict or doc.get("schema") != schema:
        raise DeckRefused(f"{pin_name.lower()}_schema")
    field = "box_sha256" if schema == v3.BOX_SCHEMA else "region_sha256"
    if doc.get("status") != "OWNER_SIGNED" or doc.get(field) != want:
        raise DeckRefused(f"{pin_name.lower()}_not_the_signed_one")
    canonical = hashlib.sha256(
        json.dumps(
            {k: v for k, v in doc.items() if k != field},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    if canonical != want:
        raise DeckRefused(f"{pin_name.lower()}_changed_after_signing")
    if schema == REGION_SCHEMA:
        nonce = doc.get("nonce")
        if (
            type(nonce) is not str
            or len(nonce) < REGION_NONCE_HEX_MIN
            or any(c not in "0123456789abcdef" for c in nonce)
        ):
            raise DeckRefused("v31_region_needs_a_custody_nonce")
    inputs = doc.get("inputs")
    if type(inputs) is not dict or not inputs:
        raise DeckRefused(f"{pin_name.lower()}_inputs")
    ranges = {}
    for name, bounds in inputs.items():
        if (
            type(bounds) is not list
            or len(bounds) != 2
            or not all(v3._finite(b) for b in bounds)
            or not bounds[0] < bounds[1]
        ):
            raise DeckRefused(f"{pin_name.lower()}_range_invalid:{name}")
        ranges[name] = (float(bounds[0]), float(bounds[1]))
    return {"inputs": ranges, "sha256": "sha256:" + want}


def load_v31_box(path):
    return _load_ranges(
        path, schema=v3.BOX_SCHEMA, want=V31_BOX_SHA256, pin_name="V31_BOX"
    )


def load_v31_region(path):
    return _load_ranges(
        path, schema=REGION_SCHEMA, want=V31_REGION_SHA256, pin_name="V31_REGION"
    )


def write_case_v31(
    case, out, *, leakage_path, box_path=None, region_path=None, level=1, dt_scale=1.0
):
    """The SIGNED 3.1 deck: production tables + the signed 3.1 law + EXACTLY ONE of the signed box (public stages) or the signed
    region (hidden stages), the case inside it. Refuses while any needed pin is HUMAN_INPUT. Physics = 3.0's ``write_case``.
    """
    if (box_path is None) == (region_path is None):
        raise DeckRefused("v31_name_exactly_one_of_box_or_region")
    if box_path is not None:
        ranges, kind = load_v31_box(box_path), "box"
    else:
        ranges, kind = load_v31_region(region_path), "region"
    v3.case_in_box(case, ranges)
    leak = load_v31_law(leakage_path)
    signed = {
        "label": v3.SIGNED,
        "version": DECK_VERSION,
        "tables": v3.TABLES_SHA256,
        "leakage": leak["sha256"],
        "box": f"{kind} {ranges['sha256']}",
        "decision": V31_LAW_DECISION,
    }
    meta = v3.write_case(
        case,
        out,
        level=level,
        dt_scale=dt_scale,
        production=True,
        leakage=leak,
        signed=signed,
    )
    meta["deck_version"] = DECK_VERSION
    tmp = Path(out, "deck.json.tmp")
    tmp.write_text(json.dumps(meta, indent=1) + "\n")
    tmp.replace(
        Path(out, "deck.json")
    )  # atomic: never a 3.1-signed record without its version
    return meta


def is_v31_deck(meta):
    """A deck record written by ``write_case_v31`` (both version marks), else False."""
    return (
        meta.get("deck_version") == DECK_VERSION
        and (meta.get("signed") or {}).get("version") == DECK_VERSION
    )


def _first_up_crossing(t, top, threshold_c, start_c):
    if start_c >= threshold_c:
        return ABOVE_AT_START  # not "never hot": the time above still counts every step
    prev_t, prev_v = 0.0, start_c
    for ti, vi in zip(t, top):
        if vi >= threshold_c > prev_v:
            return prev_t + (threshold_c - prev_v) / (vi - prev_v) * (ti - prev_t)
        prev_t, prev_v = ti, vi
    return "NOT_REACHED"


def observe_v31(
    case_dir, *, threshold_c, second_threshold_c, baseline_top_c=None, log_path=None
):
    """``observe_v3`` (public scalars, unchanged) + the CUSTODY-ONLY block. ``second_threshold_c`` is required (no default)."""
    if (
        type(second_threshold_c) not in (int, float)
        or isinstance(second_threshold_c, bool)
        or not math.isfinite(second_threshold_c)
    ):
        raise DeckRefused("second_threshold_required")
    observed = v3.observe_v3(
        case_dir,
        threshold_c=threshold_c,
        baseline_top_c=baseline_top_c,
        log_path=log_path,
    )
    meta = json.loads(Path(case_dir, "deck.json").read_text())
    if not is_v31_deck(meta):
        raise DeckRefused("not_a_v31_deck")
    observed["deck_version"] = DECK_VERSION
    if observed.get("status") != "OK":
        return observed
    cols, rows = v3.read_scalars(case_dir)
    i_top = next(i for i, c in enumerate(cols) if c.startswith("boundary max"))
    i_src = [
        i for i, c in enumerate(cols) if c.startswith("value: temperature at node")
    ]
    t = [r[0] for r in rows]
    top = [r[i_top] - 273.15 for r in rows]
    observed["custody"] = {
        "label": CUSTODY_ONLY,
        "die_top_trace_c": [[ti, vi] for ti, vi in zip(t, top)],
        "source_traces_c": {cols[i]: [r[i] - 273.15 for r in rows] for i in i_src},
        "second_threshold_c": float(second_threshold_c),
        "second_threshold_crossing_s": _first_up_crossing(
            t, top, second_threshold_c, meta["case"]["initial_c"]
        ),
        "time_above_second_threshold_s": v3.time_above_s(t, top, second_threshold_c),
    }
    return observed


def custody_outputs(observed):
    """Only the CUSTODY-ONLY block of a valid ``observe_v31`` result (for the custody store; never a TRAIN row)."""
    if (
        observed.get("status") != "OK"
        or observed.get("custody", {}).get("label") != CUSTODY_ONLY
    ):
        raise DeckRefused("no_custody_block")
    return dict(observed["custody"])


def public_scalars(observed):
    """The publishable scalars: exactly 3.0's ``scalar_outputs`` (custody fields can never pass)."""
    return v3.scalar_outputs(observed)
