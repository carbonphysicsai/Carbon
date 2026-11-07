"""f02 burst-thermal decks, VERSION 3.2 (Burst Thermal 3.2): the 3.1 physics (the 3.0 deck, imported UNCHANGED) plus two-phase
(boiling) cooling on the underside. Owner (EQ session, ledger N15): "We aren't launching BT until 3.2"; setup O1-O8 (N16).

THE PIN IS THE MEASURED CURVE, NOT A FACTOR (researcher's CURVE_NOTE_FOR_DC, the same mapping the P0 desk check uses). The pinned
``carbon.f02.boiling-curve.v1`` file gives the fluid's saturation temperature ``tsat_c``, the fixed subcooled inlet ``inlet_c``
(O3), the onset superheat ``onb_superheat_k.table_start``, the tested cap ``cap.superheat_k`` (O5: beyond = out of the curve), and
the measured nucleate-boiling flux ``superheat_k_to_q_nb_w_m2`` = [[T_w - T_sat (K), q_nb (W/m2)], ...]. Per case the deck writes the
underside coefficient as a ``Variable Temperature`` table against the inlet (External Temperature = the coolant = the inlet):

    q_sp = h_sp (T_w - T_in)          h_sp = the case's h_w_m2_k (the single-phase coefficient, still the miner input)
    q_nb = curve(T_w - T_sat)         only at or above the onset superheat; 0 below
    h_eff(T_w) = sqrt(q_sp^2 + q_nb^2) / (T_w - T_in)        (BLEND = asymptotic n = 2; the Validator rules the convention)

on a fixed grid from T_in to T_sat + cap (``TABLE_STEP_K``), so the table is deterministic and its digest is recorded per case. h_eff
depends on h_sp, so one factor(T) table could not be right for every case. No curve value is written here.

THE COOLANT. Under O3 the inlet is fixed by the curve: a case whose ``coolant_c`` differs from ``inlet_c`` refuses (the box change is
the owner's / Validator's). OUT OF THE CURVE (O5 c): any underside node above T_sat + cap at any step is REFERENCE_INVALID
("out_of_curve_range"). The deck adds ONE SaveScalars operator, the underside's own maximum (masked to the underside boundary), because
the existing "boundary max" covers every saved boundary (it is the die top in practice).

PINS (fail closed). Every SIGNED 3.2 deck refuses until each pin is set by a reviewed change citing its owner record:
``V32_LAW_DECISION`` / ``V32_LAW_SHA256`` (the leakage law; 3.0's law refuses), ``V32_HT_DECISION`` / ``V32_HT_SHA256`` (the curve),
``V32_BOX_SHA256`` (public stages), ``V32_REGION_SHA256`` (hidden stages; the 3.1 region schema, nonce required). A case is written
against EXACTLY ONE of the box or the region, inside it. The probe writer takes any digest-pinned curve (a CANDIDATE curve only there)
and labels every output TEST_ONLY. Every writer builds into OUT.partial and renames it to OUT only when complete.
``energy_balance`` assumes a constant h and refuses on a 3.2 deck. ``observe_v32`` = ``observe_v3`` (public scalars, unchanged) + the
out-of-curve check + the CUSTODY_ONLY block of 3.1 (plus the underside-max trace).
"""

from __future__ import annotations

import hashlib
import itertools
import json
import math
import shutil
from contextlib import contextmanager
from pathlib import Path

try:  # the repo layout (tests) and the flat reference-package layout (solve hosts)
    from scripts.dev.reference_packages.elmer import f02_deck_v3 as v3
    from scripts.dev.reference_packages.elmer import f02_deck_v31 as v31
except ModuleNotFoundError as missing:  # pragma: no cover - flat layout only
    if not (missing.name or "").startswith("scripts"):
        raise
    import f02_deck_v3 as v3
    import f02_deck_v31 as v31

DeckRefused = v3.DeckRefused
HUMAN_INPUT = v3.HUMAN_INPUT
DECK_VERSION = "3.2"
TEST_ONLY = v3.LEAKAGE_TEST_ONLY
CURVE_SCHEMA = "carbon.f02.boiling-curve.v1"
CURVE_SCHEMA_CANDIDATE = "carbon.f02.boiling-curve.v1-candidate"
#: candidate forms the probe writer accepts (the researcher's r2 adds the onset ramp inside onb_superheat_k)
CURVE_SCHEMAS_CANDIDATE = (
    CURVE_SCHEMA_CANDIDATE,
    "carbon.f02.boiling-curve.v1-candidate-r2",
)
BLEND = "asymptotic_n2"
TABLE_STEP_K = 0.5
ONSET_EDGE_K = 1e-3  # the table holds h_sp up to just below the onset, then the boiling value: a sharp, deterministic onset
UNDERSIDE_MASK = "Underside Max"
UNDERSIDE_COLUMN = "boundary max: temperature over bc underside max"

#: The 3.2 pins. HUMAN_INPUT until a reviewed change sets each one from its owner record (fail closed).
V32_LAW_DECISION = HUMAN_INPUT
V32_LAW_SHA256 = HUMAN_INPUT
V32_HT_DECISION = HUMAN_INPUT
V32_HT_SHA256 = HUMAN_INPUT
V32_BOX_SHA256 = HUMAN_INPUT
V32_REGION_SHA256 = HUMAN_INPUT


def pins_status():
    """Which 3.2 pins are still HUMAN_INPUT (an empty list = every pin set)."""
    open_pins = []
    for name in ("V32_LAW_DECISION", "V32_HT_DECISION"):
        value = globals()[name]
        if not (isinstance(value, str) and value and value != HUMAN_INPUT):
            open_pins.append(name)
    for name in (
        "V32_LAW_SHA256",
        "V32_HT_SHA256",
        "V32_BOX_SHA256",
        "V32_REGION_SHA256",
    ):
        if not v31._is_pin(globals()[name]):
            open_pins.append(name)
    return open_pins


def _finite(x):
    return v3._finite(x)


def load_curve(path, *, expect_sha256, test_mode=False):
    """The boiling curve of a digest-pinned file, or a refusal. A CANDIDATE curve is accepted only by the probe writer."""
    if not v31._is_pin(expect_sha256):
        raise DeckRefused("curve_needs_a_pinned_digest")
    raw = Path(path).read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != expect_sha256:
        raise DeckRefused("curve_file_digest_differs")
    try:
        doc = json.loads(raw)
    except ValueError:
        raise DeckRefused("curve_file_not_json") from None
    if (
        type(doc) is not dict
        or doc.get("schema") not in (CURVE_SCHEMA,) + CURVE_SCHEMAS_CANDIDATE
    ):
        raise DeckRefused("curve_schema")
    candidate = doc["schema"] in CURVE_SCHEMAS_CANDIDATE
    if candidate and not test_mode:
        raise DeckRefused("curve_candidate_refuses_production")
    try:
        tsat, tin = doc["tsat_c"], doc["inlet_c"]
        onb, cap = doc["onb_superheat_k"]["table_start"], doc["cap"]["superheat_k"]
        points = doc["superheat_k_to_q_nb_w_m2"]
        ramp, ramp_start = _onset_ramp(doc)
    except (KeyError, TypeError, AttributeError):
        raise DeckRefused("curve_fields") from None
    if not all(_finite(x) for x in (tsat, tin, onb, cap)) or not (
        tin < tsat and 0 <= onb < cap
    ):
        raise DeckRefused("curve_values_invalid")
    if ramp_start is not None and not (
        _finite(ramp_start) and abs((onb - ramp) - ramp_start) <= 1e-9
    ):
        raise DeckRefused(
            "curve_onset_ramp_inconsistent"
        )  # ramp_start_k must equal table_start - onset_ramp_k
    if not (_finite(ramp) and 0 <= ramp and onb - ramp > tin - tsat):
        raise DeckRefused(
            "curve_onset_ramp_invalid"
        )  # finite, >= 0, and the ramp starts above the inlet
    if (
        type(points) is not list
        or len(points) < 2
        or any(
            type(p) is not list or len(p) != 2 or not all(_finite(x) for x in p)
            for p in points
        )
        or any(b[0] <= a[0] for a, b in itertools.pairwise(points))
        or any(p[1] < 0 for p in points)
        or points[0][0] > onb
        or points[-1][0] < cap
    ):
        raise DeckRefused(
            "curve_points_invalid"
        )  # ascending superheat, q >= 0, spanning [onset, cap]
    return {
        "schema": doc["schema"],
        "tsat_c": float(tsat),
        "inlet_c": float(tin),
        "onb_k": float(onb),
        "cap_k": float(cap),
        "ramp_k": float(ramp),
        "points": [(float(a), float(b)) for a, b in points],
        "label": TEST_ONLY if (candidate or test_mode) else "REGISTERED",
        "sha256": "sha256:" + digest,
    }


def _onset_ramp(doc):
    """(ramp, ramp_start or None): ONE source, never a silent default when a ramp is written somewhere. The researcher's r2 form
    keeps it in onb_superheat_k (onset_ramp_k [+ ramp_start_k]); a top-level onset_ramp_k is accepted only when the nested one is
    absent, and both present must agree. No ramp anywhere = 0 (sharp)."""
    onb_block = doc["onb_superheat_k"]
    nested = onb_block.get("onset_ramp_k") if isinstance(onb_block, dict) else None
    top = doc.get("onset_ramp_k")
    if nested is not None and top is not None and nested != top:
        raise DeckRefused("curve_onset_ramp_ambiguous")
    ramp = nested if nested is not None else (top if top is not None else 0.0)
    return ramp, onb_block.get("ramp_start_k") if isinstance(onb_block, dict) else None


def _interp(points, x):
    for (x0, y0), (x1, y1) in itertools.pairwise(points):
        if x0 <= x <= x1:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    raise DeckRefused("curve_interpolation_out_of_span")


def h_eff_table(case, curve):
    """[(T_K, h_eff)] for this case: h_sp up to just below the onset, the asymptotic blend from the onset to T_sat + cap."""
    # Every point is placed and classified in SUPERHEAT space (s = T - T_sat) with the curve's own exact onset and cap values,
    # so float rounding of T_sat + onset / T_sat + cap can neither push the top point off the curve nor un-boil the onset point.
    h_sp, tin, tsat = float(case["h_w_m2_k"]), curve["inlet_c"], curve["tsat_c"]
    onb, cap, ramp = curve["onb_k"], curve["cap_k"], curve.get("ramp_k", 0.0)
    s_in = tin - tsat  # < 0 (the inlet is subcooled)
    # sharp onset (ramp 0): h_sp up to ONSET_EDGE_K below the onset; a ramp: q_nb rises linearly from 0 at (onset - ramp) to the
    # curve's onset value at the onset (the curve file chooses the ramp: a modelling convention, not a value set here)
    start = onb - (ramp if ramp > 0 else ONSET_EDGE_K)
    points = {
        round(s_in, 9): s_in,
        round(start, 9): start,
        round(onb, 9): onb,
        round(cap, 9): cap,
    }
    k = 1
    while s_in + k * TABLE_STEP_K < cap - 1e-9:
        s = s_in + k * TABLE_STEP_K
        points.setdefault(
            round(s, 9), s
        )  # an exact onset / cap key wins over a grid point at the same place
        k += 1
    table = []
    for key in sorted(points):
        s = points[key]
        if s < s_in or s > cap:
            continue
        if s <= start or (ramp == 0 and s < onb):
            h = h_sp
        elif s < onb:
            q_nb = _interp(curve["points"], onb) * (s - start) / ramp
            q_sp = h_sp * (s - s_in)
            h = math.sqrt(q_sp**2 + q_nb**2) / (s - s_in)
        else:
            q_nb = _interp(curve["points"], min(s, cap))
            q_sp = h_sp * (s - s_in)
            h = math.sqrt(q_sp**2 + q_nb**2) / (s - s_in)
        table.append((round(tsat + s + 273.15, 9), h))
    return table


def _table_digest(table):
    return (
        "sha256:"
        + hashlib.sha256(json.dumps([[t, h] for t, h in table]).encode()).hexdigest()
    )


def _patch(out, case, table):
    """The underside's constant coefficient -> the h_eff(T) table; + the underside-max SaveScalars operator. Each edit must apply
    exactly once (else refuse)."""
    sif_path = Path(out, "case.sif")
    text = sif_path.read_text()
    block = (
        "Boundary Condition 1\n"
        "  Target Boundaries(1) = 1\n"
        '  Name = "underside"\n'
        f"  Heat Transfer Coefficient = {case['h_w_m2_k']!r}\n"
    )
    saver = "  Variable 3 = Temperature\n  Operator 3 = boundary int\n"
    if text.count(block) != 1 or text.count(saver) != 1 or "Variable 4 =" in text:
        raise DeckRefused("sif_edit_points_not_found_exactly_once")
    rows = "\n".join(f"      {t!r} {h!r}" for t, h in table)
    patched = (
        "Boundary Condition 1\n"
        "  Target Boundaries(1) = 1\n"
        '  Name = "underside"\n'
        f"  {UNDERSIDE_MASK} = Logical True\n"
        f"  Heat Transfer Coefficient = Variable Temperature\n    Real\n{rows}\n    End\n"
    )
    text = text.replace(block, patched).replace(
        saver,
        saver
        + f"  Variable 4 = Temperature\n  Operator 4 = boundary max\n  Mask Name 4 = String {UNDERSIDE_MASK}\n",
    )
    tmp = sif_path.with_name("case.sif.tmp")
    tmp.write_text(text)
    tmp.replace(sif_path)


@contextmanager
def _building(out):
    """Write the deck into a sibling OUT.partial and rename it to OUT only when complete: a refusal or a crash leaves no OUT."""
    out = Path(out)
    tmp = out.with_name(out.name + ".partial")
    if out.exists() or tmp.exists():
        raise DeckRefused("v32_out_exists")
    try:
        yield tmp
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    tmp.rename(out)


def _check_coolant(case, curve):
    if abs(case["coolant_c"] - curve["inlet_c"]) > 1e-9:
        raise DeckRefused("coolant_not_the_curve_inlet")


def _finish(out, meta, curve, table, *, test=False):
    meta["deck_version"] = DECK_VERSION
    meta["h_curve"] = {
        "schema": curve["schema"],
        "sha256": curve["sha256"],
        "label": curve["label"],
        "tsat_c": curve["tsat_c"],
        "inlet_c": curve["inlet_c"],
        "onb_k": curve["onb_k"],
        "cap_k": curve["cap_k"],
        "ramp_k": curve["ramp_k"],
        "blend": BLEND,
        "table_sha256": _table_digest(table),
    }
    if test or curve["label"] == TEST_ONLY:
        meta["tables"] = TEST_ONLY
    tmp = Path(out, "deck.json.tmp")
    tmp.write_text(json.dumps(meta, indent=1) + "\n")
    tmp.replace(Path(out, "deck.json"))
    return meta


def write_case_v32_test(
    case, out, *, curve_path, curve_sha256, leakage, tables=None, level=1, dt_scale=1.0
):
    """The TEST-MODE 3.2 deck (probes only): ``v3.write_case(test_mode=True)`` with a leakage law + a digest-pinned curve (a
    CANDIDATE curve is allowed here only); every output is labelled TEST_ONLY. Never exam material.
    """
    if leakage is None:
        raise DeckRefused("v32_needs_the_leakage_law")
    curve = load_curve(curve_path, expect_sha256=curve_sha256, test_mode=True)
    case = v3.resolve_case(case)
    _check_coolant(case, curve)
    table = h_eff_table(case, curve)
    with _building(out) as tmp:
        meta = v3.write_case(
            case,
            tmp,
            level=level,
            dt_scale=dt_scale,
            tables=tables,
            test_mode=True,
            leakage=leakage,
        )
        _patch(tmp, case, table)
        meta = _finish(tmp, meta, curve, table, test=True)
    return meta


def write_case_v32(
    case,
    out,
    *,
    leakage_path,
    curve_path,
    box_path=None,
    region_path=None,
    level=1,
    dt_scale=1.0,
):
    """The SIGNED 3.2 deck: production tables + the signed law + the signed curve + EXACTLY ONE of the signed box or region."""
    if (box_path is None) == (region_path is None):
        raise DeckRefused("v32_name_exactly_one_of_box_or_region")
    if box_path is not None:
        ranges, kind = (
            v31._load_ranges(
                box_path, schema=v3.BOX_SCHEMA, want=V32_BOX_SHA256, pin_name="V32_BOX"
            ),
            "box",
        )
    else:
        ranges, kind = (
            v31._load_ranges(
                region_path,
                schema=v31.REGION_SCHEMA,
                want=V32_REGION_SHA256,
                pin_name="V32_REGION",
            ),
            "region",
        )
    case = v3.case_in_box(case, ranges)
    for name in (
        "V32_LAW_DECISION",
        "V32_LAW_SHA256",
        "V32_HT_DECISION",
        "V32_HT_SHA256",
    ):
        if name in pins_status():
            raise DeckRefused(f"{name.lower()}_is_human_input")
    if (
        V32_LAW_DECISION == v3.SIGNED_LEAKAGE_DECISION
        or V32_LAW_SHA256 == v3.SIGNED_LEAKAGE_SHA256
    ):
        raise DeckRefused("v32_law_pin_is_the_3_0_law")
    leak = v3.load_leakage(leakage_path, expect_sha256=V32_LAW_SHA256)
    if leak["label"] != "REGISTERED" or leak["decision"] != V32_LAW_DECISION:
        raise DeckRefused("v32_law_not_the_signed_law")
    curve = load_curve(curve_path, expect_sha256=V32_HT_SHA256)
    _check_coolant(case, curve)
    table = h_eff_table(case, curve)
    signed = {
        "label": v3.SIGNED,
        "version": DECK_VERSION,
        "tables": v3.TABLES_SHA256,
        "leakage": leak["sha256"],
        "h_curve": curve["sha256"],
        "box": f"{kind} {ranges['sha256']}",
        "decision": V32_LAW_DECISION,  # v3's sif header names this one record id
        "ht_decision": V32_HT_DECISION,
        "table_sha256": _table_digest(table),
    }
    with _building(out) as tmp:
        meta = v3.write_case(
            case,
            tmp,
            level=level,
            dt_scale=dt_scale,
            production=True,
            leakage=leak,
            signed=signed,
        )
        _patch(tmp, case, table)
        meta = _finish(tmp, meta, curve, table)
    return meta


def is_v32_deck(meta):
    return meta.get("deck_version") == DECK_VERSION and isinstance(
        meta.get("h_curve"), dict
    )


def energy_balance(case_dir):
    """3.0's balance assumes a constant underside h: it refuses on a 3.2 deck."""
    if is_v32_deck(json.loads(Path(case_dir, "deck.json").read_text())):
        raise DeckRefused("energy_balance_assumes_constant_h")
    return v3.energy_balance(case_dir)


def observe_v32(
    case_dir, *, threshold_c, second_threshold_c, baseline_top_c=None, log_path=None
):
    """``observe_v3`` (public scalars, unchanged) + the out-of-curve check on the UNDERSIDE max + the CUSTODY_ONLY block."""
    if (
        type(second_threshold_c) not in (int, float)
        or isinstance(second_threshold_c, bool)
        or not math.isfinite(second_threshold_c)
    ):
        raise DeckRefused("second_threshold_required")
    meta = json.loads(Path(case_dir, "deck.json").read_text())
    if not is_v32_deck(meta):
        raise DeckRefused("not_a_v32_deck")
    observed = v3.observe_v3(
        case_dir,
        threshold_c=threshold_c,
        baseline_top_c=baseline_top_c,
        log_path=log_path,
    )
    observed["deck_version"] = DECK_VERSION
    observed["h_curve"] = {
        "label": meta["h_curve"]["label"],
        "sha256": meta["h_curve"]["sha256"],
    }
    if observed.get("status") != "OK":
        return observed
    cols, rows = v3.read_scalars(case_dir)
    if UNDERSIDE_COLUMN not in cols:
        raise DeckRefused(
            "underside_max_column_missing"
        )  # a deck / solver mismatch, never a physics verdict
    i_under = cols.index(UNDERSIDE_COLUMN)
    i_top = next(i for i, c in enumerate(cols) if c.startswith("boundary max"))
    i_src = [
        i for i, c in enumerate(cols) if c.startswith("value: temperature at node")
    ]
    t = [r[0] for r in rows]
    top = [r[i_top] - 273.15 for r in rows]
    under = [r[i_under] - 273.15 for r in rows]
    limit_c = meta["h_curve"]["tsat_c"] + meta["h_curve"]["cap_k"]
    if max(under) > limit_c:
        invalid = {
            "status": "REFERENCE_INVALID",
            "deck_version": DECK_VERSION,
            "tables": observed.get("tables"),
            "h_curve": observed["h_curve"],
            "reference": {
                "status": "REFERENCE_INVALID",
                "reason": "out_of_curve_range",
                "limit_c": limit_c,
                "underside_max_c": max(under),
            },
        }
        if "leakage" in observed:
            invalid["leakage"] = observed["leakage"]
        return invalid
    observed["custody"] = {
        "label": v31.CUSTODY_ONLY,
        "die_top_trace_c": [[ti, vi] for ti, vi in zip(t, top)],
        "underside_max_trace_c": [[ti, vi] for ti, vi in zip(t, under)],
        "source_traces_c": {cols[i]: [r[i] - 273.15 for r in rows] for i in i_src},
        "second_threshold_c": float(second_threshold_c),
        "second_threshold_crossing_s": v31._first_up_crossing(
            t, top, second_threshold_c, meta["case"]["initial_c"]
        ),
        "time_above_second_threshold_s": v3.time_above_s(t, top, second_threshold_c),
    }
    return observed


def custody_outputs(observed):
    return v31.custody_outputs(observed)


def public_scalars(observed):
    return v3.scalar_outputs(observed)
