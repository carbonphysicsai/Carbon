"""BT 3.2 deck skeleton (f02_deck_v32): the 3.1 physics + two-phase boiling on the underside, pinned as the MEASURED CURVE.

Claims:
- every 3.2 pin ships HUMAN_INPUT and every SIGNED write refuses (writing nothing) until set; a CANDIDATE curve never writes a signed
  deck; the probe writer takes a digest-pinned curve and labels every output TEST_ONLY;
- the 3.2 sif is the 3.0 sif with exactly three edits: the underside coefficient becomes a per-case Variable Temperature table, the
  underside gets the mask flag, and the SaveScalars solver gets one masked underside-max operator;
- the per-case table is h_sp below the onset and sqrt(q_sp^2 + q_nb^2)/(T - T_in) from the onset to T_sat + cap, and it depends on
  the case's own h_sp (so one factor table could not serve every case);
- a coolant other than the curve's inlet refuses (O3); the curve file is validated;
- observe_v32 keeps observe_v3's public result, types an UNDERSIDE max above T_sat + cap REFERENCE_INVALID (out_of_curve_range),
  refuses a missing underside column and a non-3.2 deck, adds the CUSTODY_ONLY block; energy_balance refuses.
"""

from __future__ import annotations

import hashlib
import json
import math

import pytest

from scripts.dev.reference_packages.elmer import f02_deck_v3 as v3
from scripts.dev.reference_packages.elmer import f02_deck_v31 as v31
from scripts.dev.reference_packages.elmer import f02_deck_v32 as v32

LEAK_POINTS = [[280.0, 1.0e6], [340.0, 3.0e6], [400.0, 9.0e6]]
# a FIXTURE curve (not the measured one): inlet 30 C = the fixture case's coolant, T_sat 40 C, onset 2 K, cap 16 K
CURVE = {
    "schema": v32.CURVE_SCHEMA,
    "tsat_c": 40.0,
    "inlet_c": 30.0,
    "onb_superheat_k": {"table_start": 2.0},
    "cap": {"superheat_k": 16.0},
    "superheat_k_to_q_nb_w_m2": [[2.0, 20000.0], [8.0, 90000.0], [16.0, 300000.0]],
}
CASE = {
    "peak_w": 80.0,
    "on_time_s": 6.0,
    "ramp_fraction": 0.0,
    "pulses": 1,
    "h_w_m2_k": 3000.0,
    "coolant_c": 30.0,
    "start_offset_c": 10.0,
    "left_source_fraction": 0.7,
    "tim_thickness_mm": 0.12,
}
INPUTS = {
    "coolant_c": [25, 35],
    "gap_s": [5, 15],
    "h_w_m2_k": [2500, 3500],
    "initial_c": [35, 55],
    "left_source_fraction": [0.5, 0.9],
    "on_time_s": [4, 8],
    "peak_w": [70, 90],
    "pulses": [1, 2],
    "ramp_fraction": [0, 1],
    "tim_thickness_mm": [0.1, 0.15],
}
LAW_DECISION, CURVE_DECISION = "FIXTURE-V32-LAW", "FIXTURE-V32-CURVE"
SIF_ADDED = (
    "  Underside Max = Logical True",
    "  Variable 4 = Temperature",
    "  Operator 4 = boundary max",
    "  Mask Name 4 = String Underside Max",
)


def _write(tmp_path, name, doc):
    path = tmp_path / name
    path.write_text(json.dumps(doc, sort_keys=True))
    return path, hashlib.sha256(path.read_bytes()).hexdigest()


def _leak(tmp_path, decision, name="leak.json"):
    return _write(
        tmp_path,
        name,
        {
            "schema": v3.LEAKAGE_SCHEMA,
            "decision": decision,
            "source": "fixture",
            "form": "table",
            "range_k": [280.0, 400.0],
            "points": LEAK_POINTS,
        },
    )


def _curve(tmp_path, name="curve.json", **over):
    return _write(tmp_path, name, {**CURVE, **over})


def _test_leak(tmp_path):
    return v3.load_leakage(
        _leak(tmp_path, v3.LEAKAGE_TEST_ONLY, "t-leak.json")[0], test_mode=True
    )


def _ranges(tmp_path, name, schema, field):
    doc = {
        "schema": schema,
        "status": "OWNER_SIGNED",
        "record": "fixture",
        "inputs": INPUTS,
    }
    if schema == v31.REGION_SCHEMA:
        doc["nonce"] = "cd" * 16
    sha = hashlib.sha256(
        json.dumps(doc, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    path = tmp_path / name
    path.write_text(json.dumps({**doc, field: sha}))
    return path, sha


@pytest.fixture
def pinned(tmp_path, monkeypatch):
    leak, leak_sha = _leak(tmp_path, LAW_DECISION)
    curve, curve_sha = _curve(tmp_path)
    box, box_sha = _ranges(tmp_path, "box.json", v3.BOX_SCHEMA, "box_sha256")
    region, region_sha = _ranges(
        tmp_path, "region.json", v31.REGION_SCHEMA, "region_sha256"
    )
    for name, value in (
        ("V32_LAW_DECISION", LAW_DECISION),
        ("V32_LAW_SHA256", leak_sha),
        ("V32_HT_DECISION", CURVE_DECISION),
        ("V32_HT_SHA256", curve_sha),
        ("V32_BOX_SHA256", box_sha),
        ("V32_REGION_SHA256", region_sha),
    ):
        monkeypatch.setattr(v32, name, value)
    return leak, curve, box, region


def _strip_3_2(sif):
    """The sif with the 3.2 edits removed: the underside coefficient (constant or table), the mask flag, the masked operator."""
    out, skip = [], False
    for line in sif.splitlines():
        if line.startswith("  Heat Transfer Coefficient ="):
            skip = line.endswith("Variable Temperature")
            continue
        if skip:
            if line.strip() == "End":
                skip = False
            continue
        if line in SIF_ADDED:
            continue
        out.append(line)
    return out


def _physics(sif):
    return [x for x in sif.splitlines() if not x.startswith("!")]


# --- pins -------------------------------------------------------------------------------------------------------------


def test_every_pin_ships_as_human_input(tmp_path):
    assert v32.DECK_VERSION == "3.2" and v32.BLEND == "asymptotic_n2"
    assert v32.pins_status() == [
        "V32_LAW_DECISION",
        "V32_HT_DECISION",
        "V32_LAW_SHA256",
        "V32_HT_SHA256",
        "V32_BOX_SHA256",
        "V32_REGION_SHA256",
    ]
    leak, _ = _leak(tmp_path, LAW_DECISION)
    curve, _ = _curve(tmp_path)
    box, _ = _ranges(tmp_path, "box.json", v3.BOX_SCHEMA, "box_sha256")
    with pytest.raises(v3.DeckRefused, match="v32_box_is_human_input"):
        v32.write_case_v32(
            CASE, tmp_path / "d", leakage_path=leak, curve_path=curve, box_path=box
        )
    assert not (tmp_path / "d").exists()


def test_signed_write_refuses_while_the_curve_pin_is_open(
    tmp_path, pinned, monkeypatch
):
    leak, curve, box, _region = pinned
    monkeypatch.setattr(v32, "V32_HT_SHA256", v3.HUMAN_INPUT)
    with pytest.raises(v3.DeckRefused, match="v32_ht_sha256_is_human_input"):
        v32.write_case_v32(
            CASE, tmp_path / "d", leakage_path=leak, curve_path=curve, box_path=box
        )
    assert not (tmp_path / "d").exists()


def test_the_3_0_law_cannot_be_the_3_2_pin(tmp_path, pinned, monkeypatch):
    leak, curve, box, _region = pinned
    for name, value in (
        ("V32_LAW_SHA256", v3.SIGNED_LEAKAGE_SHA256),
        ("V32_LAW_DECISION", v3.SIGNED_LEAKAGE_DECISION),
    ):
        monkeypatch.setattr(v32, name, value)
        with pytest.raises(v3.DeckRefused, match="v32_law_pin_is_the_3_0_law"):
            v32.write_case_v32(
                CASE, tmp_path / "d", leakage_path=leak, curve_path=curve, box_path=box
            )


# --- the per-case table ----------------------------------------------------------------------------------------------


def _curve_dict():
    return {
        "tsat_c": 40.0,
        "inlet_c": 30.0,
        "onb_k": 2.0,
        "cap_k": 16.0,
        "points": [tuple(p) for p in CURVE["superheat_k_to_q_nb_w_m2"]],
    }


def test_table_is_h_sp_below_onset_and_the_blend_above():
    curve = _curve_dict()
    table = v32.h_eff_table(CASE, curve)
    ts = [t for t, _ in table]
    assert (
        ts == sorted(set(ts))
        and ts[0] == pytest.approx(30.0 + 273.15)
        and ts[-1] == pytest.approx(56.0 + 273.15)
    )
    for t_k, h in table:
        t_c = t_k - 273.15
        if t_c - 40.0 < 2.0:
            assert h == 3000.0
        else:
            q_nb = v32._interp(curve["points"], t_c - 40.0)
            assert h == pytest.approx(
                math.sqrt((3000.0 * (t_c - 30.0)) ** 2 + q_nb**2) / (t_c - 30.0)
            )
            assert h > 3000.0
    # a sharp onset: h_sp just below, the boiling value at the onset
    by_t = {round(t, 6): h for t, h in table}
    assert (
        by_t[round(42.0 - v32.ONSET_EDGE_K + 273.15, 6)] == 3000.0
        and by_t[round(42.0 + 273.15, 6)] > 3000.0
    )


def test_table_depends_on_the_cases_own_h_sp():
    curve = _curve_dict()
    a = {
        round(t, 6): h for t, h in v32.h_eff_table({**CASE, "h_w_m2_k": 2000.0}, curve)
    }
    b = {
        round(t, 6): h for t, h in v32.h_eff_table({**CASE, "h_w_m2_k": 6000.0}, curve)
    }
    t = round(50.0 + 273.15, 6)
    assert a[t] / 2000.0 != pytest.approx(
        b[t] / 6000.0, rel=1e-3
    )  # not one factor(T) for every case


# --- the deck ---------------------------------------------------------------------------------------------------------


def test_test_mode_deck_is_the_3_0_deck_plus_the_3_2_edits(tmp_path):
    leak = _test_leak(tmp_path)
    curve, curve_sha = _curve(tmp_path)
    meta = v32.write_case_v32_test(
        CASE, tmp_path / "d32", curve_path=curve, curve_sha256=curve_sha, leakage=leak
    )
    v3.write_case(CASE, tmp_path / "d30", test_mode=True, leakage=leak)
    s32 = (tmp_path / "d32" / "case.sif").read_text()
    s30 = (tmp_path / "d30" / "case.sif").read_text()
    assert _strip_3_2(s32) == _strip_3_2(s30)
    assert s32.count("Heat Transfer Coefficient = Variable Temperature") == 1
    for line in SIF_ADDED:
        assert s32.splitlines().count(line) == 1
    for t, h in v32.h_eff_table(
        v3.resolve_case(CASE),
        v32.load_curve(curve, expect_sha256=curve_sha, test_mode=True),
    ):
        assert f"      {t!r} {h!r}" in s32
    assert (
        meta["deck_version"] == "3.2"
        and meta["tables"] == v32.TEST_ONLY
        and meta["nonlinear"] is not None
    )
    assert (
        meta["h_curve"]["label"] == v32.TEST_ONLY
        and meta["h_curve"]["sha256"] == "sha256:" + curve_sha
    )
    assert meta["h_curve"]["blend"] == "asymptotic_n2" and meta["h_curve"][
        "table_sha256"
    ].startswith("sha256:")
    assert (
        json.loads((tmp_path / "d32" / "deck.json").read_text())["deck_version"]
        == "3.2"
    )


def test_a_candidate_curve_writes_probe_decks_only(tmp_path, pinned, monkeypatch):
    leak, _curve_ok, box, _region = pinned
    cand, cand_sha = _curve(tmp_path, "cand.json", schema=v32.CURVE_SCHEMA_CANDIDATE)
    v32.write_case_v32_test(
        CASE,
        tmp_path / "p",
        curve_path=cand,
        curve_sha256=cand_sha,
        leakage=_test_leak(tmp_path),
    )
    monkeypatch.setattr(v32, "V32_HT_SHA256", cand_sha)
    with pytest.raises(v3.DeckRefused, match="curve_candidate_refuses_production"):
        v32.write_case_v32(
            CASE, tmp_path / "d", leakage_path=leak, curve_path=cand, box_path=box
        )
    assert not (tmp_path / "d").exists()


def test_a_coolant_other_than_the_inlet_refuses(tmp_path, pinned):
    leak, curve, box, _region = pinned
    other = {**CASE, "coolant_c": 31.0}
    with pytest.raises(v3.DeckRefused, match="coolant_not_the_curve_inlet"):
        v32.write_case_v32(
            other, tmp_path / "s", leakage_path=leak, curve_path=curve, box_path=box
        )
    tc, tc_sha = _curve(tmp_path, "tc.json")
    with pytest.raises(v3.DeckRefused, match="coolant_not_the_curve_inlet"):
        v32.write_case_v32_test(
            other,
            tmp_path / "t",
            curve_path=tc,
            curve_sha256=tc_sha,
            leakage=_test_leak(tmp_path),
        )
    assert not (tmp_path / "s").exists() and not (tmp_path / "t").exists()


def test_signed_deck_box_and_region(tmp_path, pinned):
    leak, curve, box, region = pinned
    meta = v32.write_case_v32(
        CASE, tmp_path / "b", leakage_path=leak, curve_path=curve, box_path=box
    )
    assert (
        meta["deck_version"] == "3.2"
        and meta["signed"]["version"] == "3.2"
        and meta["tables"] == "PRODUCTION"
    )
    assert (
        meta["signed"]["h_curve"].startswith("sha256:")
        and meta["h_curve"]["label"] == "REGISTERED"
    )
    v32.write_case_v32(
        CASE, tmp_path / "r", leakage_path=leak, curve_path=curve, region_path=region
    )
    assert _physics((tmp_path / "b" / "case.sif").read_text()) == _physics(
        (tmp_path / "r" / "case.sif").read_text()
    )
    for kw in ({}, {"box_path": box, "region_path": region}):
        with pytest.raises(
            v3.DeckRefused, match="v32_name_exactly_one_of_box_or_region"
        ):
            v32.write_case_v32(
                CASE, tmp_path / "x", leakage_path=leak, curve_path=curve, **kw
            )


def test_signed_deck_refuses_another_law(tmp_path, pinned, monkeypatch):
    _leak_ok, curve, box, _region = pinned
    other, other_sha = _leak(tmp_path, "OTHER-LAW", "ol.json")
    monkeypatch.setattr(v32, "V32_LAW_SHA256", other_sha)
    with pytest.raises(v3.DeckRefused, match="v32_law_not_the_signed_law"):
        v32.write_case_v32(
            CASE, tmp_path / "d", leakage_path=other, curve_path=curve, box_path=box
        )
    assert not (tmp_path / "d").exists()


def test_a_patch_refusal_leaves_no_deck(tmp_path, pinned, monkeypatch):
    leak, curve, box, _region = pinned

    def boom(*_a, **_k):
        raise v3.DeckRefused("sif_edit_points_not_found_exactly_once")

    monkeypatch.setattr(v32, "_patch", boom)
    with pytest.raises(v3.DeckRefused, match="sif_edit_points_not_found_exactly_once"):
        v32.write_case_v32(
            CASE, tmp_path / "s", leakage_path=leak, curve_path=curve, box_path=box
        )
    for name in ("s", "s.partial"):
        assert not (tmp_path / name).exists()


def test_an_existing_out_refuses(tmp_path):
    tc, tc_sha = _curve(tmp_path)
    (tmp_path / "d").mkdir()
    with pytest.raises(v3.DeckRefused, match="v32_out_exists"):
        v32.write_case_v32_test(
            CASE,
            tmp_path / "d",
            curve_path=tc,
            curve_sha256=tc_sha,
            leakage=_test_leak(tmp_path),
        )


@pytest.mark.parametrize(
    "over, why",
    [
        ({"schema": "x"}, "curve_schema"),
        ({"tsat_c": 25.0}, "curve_values_invalid"),
        ({"onb_superheat_k": {}}, "curve_fields"),
        ({"cap": {"superheat_k": 1.0}}, "curve_values_invalid"),
        ({"superheat_k_to_q_nb_w_m2": [[2.0, 1.0]]}, "curve_points_invalid"),
        (
            {"superheat_k_to_q_nb_w_m2": [[2.0, 1.0], [1.0, 2.0], [16.0, 3.0]]},
            "curve_points_invalid",
        ),
        (
            {"superheat_k_to_q_nb_w_m2": [[2.0, -1.0], [16.0, 3.0]]},
            "curve_points_invalid",
        ),
        (
            {"superheat_k_to_q_nb_w_m2": [[2.0, 1.0], [10.0, 3.0]]},
            "curve_points_invalid",
        ),  # does not reach the cap
        (
            {"superheat_k_to_q_nb_w_m2": [[3.0, 1.0], [16.0, 3.0]]},
            "curve_points_invalid",
        ),  # starts after the onset
    ],
)
def test_curve_file_validation(tmp_path, over, why):
    path, digest = _curve(tmp_path, **over)
    with pytest.raises(v3.DeckRefused, match=why):
        v32.load_curve(path, expect_sha256=digest, test_mode=True)


def test_the_curve_digest_is_always_pinned(tmp_path):
    path, _digest = _curve(tmp_path)
    for want, why in (
        (None, "curve_needs_a_pinned_digest"),
        ("HUMAN_INPUT", "curve_needs_a_pinned_digest"),
        ("0" * 64, "curve_file_digest_differs"),
    ):
        with pytest.raises(v3.DeckRefused, match=why):
            v32.load_curve(path, expect_sha256=want, test_mode=True)


# --- observation ------------------------------------------------------------------------------------------------------


SERIES = [
    (0.0, 40.0),
    (20.0, 40.0),
    (25.0, 100.0),
    (30.0, 70.0),
    (40.0, 40.0),
    (120.0, 40.0),
]


def _case_dir(
    tmp_path, *, under_peak=50.0, version="3.2", name="case", with_under=True
):
    case = v3.resolve_case(CASE)
    d = tmp_path / name
    d.mkdir()
    cols = ["   1: time", "   2: boundary max: temperature over bc save scalars"]
    if with_under:
        cols.append(f"   3: {v32.UNDERSIDE_COLUMN}")
    cols.append(f"   {len(cols) + 1}: value: temperature at node 1")
    lines = []
    for t, v in SERIES:
        row = [t, v + 273.15]
        if with_under:
            row.append(min(v, under_peak) + 273.15)
        row.append(v - 5.0 + 273.15)
        lines.append(" ".join(repr(x) for x in row))
    (d / "scalars.dat").write_text("\n".join(lines) + "\n")
    (d / "scalars.dat.names").write_text("\n".join(cols) + "\n")
    meta = {
        "case": case,
        "schedule_w": v3.schedule(case),
        "tables": "TEST_ONLY",
        "nonlinear": None,
        "deck_version": version,
        "h_curve": {
            "label": "TEST_ONLY",
            "sha256": "sha256:" + "0" * 64,
            "tsat_c": 40.0,
            "cap_k": 16.0,
        },
    }
    (d / "deck.json").write_text(json.dumps(meta))
    return d


def test_observe_v32_public_result_plus_custody(tmp_path):
    d = _case_dir(tmp_path)
    obs = v32.observe_v32(d, threshold_c=85.0, second_threshold_c=70.0)
    pub = v3.observe_v3(d, threshold_c=85.0)
    assert {k: obs[k] for k in pub} == pub
    assert obs["deck_version"] == "3.2" and obs["custody"]["label"] == v31.CUSTODY_ONLY
    assert [v for _t, v in obs["custody"]["underside_max_trace_c"]] == [
        pytest.approx(min(v, 50.0)) for _t, v in SERIES
    ]
    assert obs["custody"]["second_threshold_crossing_s"] == pytest.approx(22.5)
    assert set(v32.public_scalars(obs)) == set(v3.SCALAR_KEYS)


def test_an_underside_above_the_cap_is_out_of_curve(tmp_path):
    obs = v32.observe_v32(
        _case_dir(tmp_path, under_peak=57.0), threshold_c=85.0, second_threshold_c=70.0
    )
    assert (
        obs["status"] == "REFERENCE_INVALID"
        and obs["reference"]["reason"] == "out_of_curve_range"
    )
    assert (
        obs["reference"]["limit_c"] == 56.0 and obs["h_curve"]["label"] == "TEST_ONLY"
    )
    assert "custody" not in obs and "peak_top_c" not in obs


def test_a_die_top_above_the_cap_alone_is_not_out_of_curve(tmp_path):
    obs = v32.observe_v32(
        _case_dir(tmp_path, under_peak=55.0), threshold_c=85.0, second_threshold_c=70.0
    )
    assert obs["status"] == "OK"  # the die top reaches 100 C; only the underside counts


def test_a_missing_underside_column_refuses(tmp_path):
    with pytest.raises(v3.DeckRefused, match="underside_max_column_missing"):
        v32.observe_v32(
            _case_dir(tmp_path, with_under=False),
            threshold_c=85.0,
            second_threshold_c=70.0,
        )


def test_observe_v32_refuses_other_decks_and_needs_the_second_threshold(tmp_path):
    with pytest.raises(v3.DeckRefused, match="not_a_v32_deck"):
        v32.observe_v32(
            _case_dir(tmp_path, version="3.1", name="v31"),
            threshold_c=85.0,
            second_threshold_c=70.0,
        )
    d = _case_dir(tmp_path, name="ok")
    for bad in (None, True, float("inf")):
        with pytest.raises(v3.DeckRefused, match="second_threshold_required"):
            v32.observe_v32(d, threshold_c=85.0, second_threshold_c=bad)


def test_a_non_ok_reference_passes_through_with_its_labels(tmp_path):
    d = _case_dir(tmp_path, name="bad")
    meta = json.loads((d / "deck.json").read_text())
    meta["property_range_k"] = [290.0, 300.0]
    (d / "deck.json").write_text(json.dumps(meta))
    obs = v32.observe_v32(d, threshold_c=85.0, second_threshold_c=70.0)
    assert (
        obs["status"] == "REFERENCE_INVALID"
        and obs["reference"]["reason"] == "out_of_property_range"
    )
    assert (
        obs["deck_version"] == "3.2"
        and obs["h_curve"]["label"] == "TEST_ONLY"
        and "custody" not in obs
    )


def test_energy_balance_refuses_on_a_3_2_deck(tmp_path):
    with pytest.raises(v3.DeckRefused, match="energy_balance_assumes_constant_h"):
        v32.energy_balance(_case_dir(tmp_path))


# --- review additions -------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "tsat, sub, onb, cap",
    [
        (30.0, 3.0, 2.0, 5.7),
        (59.6, 5.0, 2.0, 16.4),
        (45.3, 7.7, 0.3, 11.1),
        (70.1, 2.2, 3.3, 9.9),
    ],
)
def test_rounding_prone_curves_keep_top_and_boiling_onset(tsat, sub, onb, cap):
    curve = {
        "tsat_c": tsat,
        "inlet_c": tsat - sub,
        "onb_k": onb,
        "cap_k": cap,
        "points": [(onb, 1000.0), (cap, 2.0e5)],
    }
    table = v32.h_eff_table(CASE, curve)
    temps = [t for t, _ in table]
    assert temps == sorted(set(temps))
    assert temps[-1] == pytest.approx(tsat + cap + 273.15) and table[-1][1] > 3000.0
    at_onset = [
        h for t, h in table if t == pytest.approx(tsat + onb + 273.15, abs=1e-9)
    ]
    assert (
        at_onset and at_onset[0] > 3000.0
    )  # the onset point itself boils (P0's rule: superheat >= onset)


def test_signed_block_names_both_records_and_the_table(tmp_path, pinned):
    leak, curve, box, _region = pinned
    meta = v32.write_case_v32(
        CASE, tmp_path / "b", leakage_path=leak, curve_path=curve, box_path=box
    )
    assert (
        meta["signed"]["decision"] == LAW_DECISION
        and meta["signed"]["ht_decision"] == CURVE_DECISION
    )
    assert meta["signed"]["table_sha256"] == meta["h_curve"]["table_sha256"]


def test_patch_refuses_a_sif_whose_edit_points_are_not_unique(tmp_path):
    curve, curve_sha = _curve(tmp_path)
    v32.write_case_v32_test(
        CASE,
        tmp_path / "d",
        curve_path=curve,
        curve_sha256=curve_sha,
        leakage=_test_leak(tmp_path),
    )
    table = v32.h_eff_table(
        v3.resolve_case(CASE),
        v32.load_curve(curve, expect_sha256=curve_sha, test_mode=True),
    )
    v3.write_case(CASE, tmp_path / "e", test_mode=True, leakage=_test_leak(tmp_path))
    sif = tmp_path / "e" / "case.sif"
    base = sif.read_text()
    for broken in (
        base + "\n  Variable 4 = Temperature\n",
        base.replace("  Operator 3 = boundary int\n", "  Operator 3 = boundary max\n"),
    ):
        sif.write_text(broken)
        with pytest.raises(
            v3.DeckRefused, match="sif_edit_points_not_found_exactly_once"
        ):
            v32._patch(tmp_path / "e", v3.resolve_case(CASE), table)


def test_an_onset_ramp_from_the_curve_file_smooths_the_jump():
    curve = {
        **_curve_dict(),
        "ramp_k": 1.0,
    }  # q_nb rises from 0 at superheat 1.0 to the onset value at 2.0
    by_s = {round(t - 273.15 - 40.0, 6): h for t, h in v32.h_eff_table(CASE, curve)}
    assert by_s[1.0] == 3000.0  # the ramp start is still single-phase
    s = 1.5  # half way up the ramp (a grid point: inlet at -10 + k x 0.5)
    q_nb = 20000.0 * 0.5
    assert by_s[s] == pytest.approx(
        math.sqrt((3000.0 * (s + 10.0)) ** 2 + q_nb**2) / (s + 10.0)
    )
    assert 3000.0 < by_s[s] < by_s[2.0]
    assert (
        round(2.0 - v32.ONSET_EDGE_K, 6) not in by_s
    )  # no sharp edge point when a ramp is set


@pytest.mark.parametrize(
    "ramp, why",
    [
        (-0.1, "curve_onset_ramp_invalid"),
        (float("nan"), "curve_onset_ramp_invalid"),
        (12.5, "curve_onset_ramp_invalid"),
    ],
)
def test_an_invalid_onset_ramp_refuses(tmp_path, ramp, why):
    path, digest = _curve(tmp_path, onset_ramp_k=ramp)
    with pytest.raises(v3.DeckRefused, match=why):
        v32.load_curve(path, expect_sha256=digest, test_mode=True)


def test_the_ramp_is_recorded_in_the_deck(tmp_path):
    curve, curve_sha = _curve(tmp_path, onset_ramp_k=0.5)
    meta = v32.write_case_v32_test(
        CASE,
        tmp_path / "d",
        curve_path=curve,
        curve_sha256=curve_sha,
        leakage=_test_leak(tmp_path),
    )
    assert meta["h_curve"]["ramp_k"] == 0.5


# --- the r2 curve form (onset ramp inside onb_superheat_k) ------------------------------------------------------------


def _r2(tmp_path, name="r2.json", **onb):
    block = {"table_start": 2.0, **onb}
    return _curve(
        tmp_path,
        name,
        schema="carbon.f02.boiling-curve.v1-candidate-r2",
        onb_superheat_k=block,
    )


def test_the_r2_nested_ramp_is_read_never_silently_dropped(tmp_path):
    path, digest = _r2(tmp_path, onset_ramp_k=0.4, ramp_start_k=1.6)
    curve = v32.load_curve(path, expect_sha256=digest, test_mode=True)
    assert curve["ramp_k"] == 0.4 and curve["label"] == v32.TEST_ONLY


def test_r2_is_a_candidate_form(tmp_path, pinned, monkeypatch):
    leak, _curve_ok, box, _region = pinned
    path, digest = _r2(tmp_path, onset_ramp_k=0.4)
    monkeypatch.setattr(v32, "V32_HT_SHA256", digest)
    with pytest.raises(v3.DeckRefused, match="curve_candidate_refuses_production"):
        v32.write_case_v32(
            CASE, tmp_path / "d", leakage_path=leak, curve_path=path, box_path=box
        )


@pytest.mark.parametrize(
    "onb, top, why",
    [
        ({"onset_ramp_k": 0.4}, 0.5, "curve_onset_ramp_ambiguous"),
        (
            {"onset_ramp_k": 0.4, "ramp_start_k": 1.5},
            None,
            "curve_onset_ramp_inconsistent",
        ),
    ],
)
def test_ambiguous_or_inconsistent_ramps_refuse(tmp_path, onb, top, why):
    over = {"onset_ramp_k": top} if top is not None else {}
    path, digest = _curve(
        tmp_path,
        "x.json",
        schema="carbon.f02.boiling-curve.v1-candidate-r2",
        onb_superheat_k={"table_start": 2.0, **onb},
        **over,
    )
    with pytest.raises(v3.DeckRefused, match=why):
        v32.load_curve(path, expect_sha256=digest, test_mode=True)


def test_the_researchers_curve_a_loads_with_its_ramp_when_present():
    from pathlib import Path

    real = (
        Path(__file__).resolve().parents[2]
        / "codex-queue"
        / "reports"
        / "BT32_P0_20261106"
        / "curve_A_r134a.json"
    )
    if not real.is_file():
        pytest.skip("the researcher's curve file is not in the repository")
    digest = hashlib.sha256(real.read_bytes()).hexdigest()
    assert v32.load_curve(real, expect_sha256=digest, test_mode=True)["ramp_k"] == 0.4
