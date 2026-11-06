"""BT 3.1 deck skeleton (f02_deck_v31; A3 + A3b).

Claims:
- every 3.1 pin ships as HUMAN_INPUT and every 3.1 write refuses until the pins are set (fail closed);
- with pins set (monkeypatched fixtures, never real values), a 3.1 deck is the 3.0 signed deck's physics, labelled version 3.1,
  written against EXACTLY ONE of the signed box or the signed region, the case inside it;
- a TEST_ONLY law, another decision's law, a changed file, a box or region that is not the signed one, a case outside it refuse;
- the 3.0 deck module is unchanged by 3.1 (its public pins and scalar keys are the same objects);
- observe_v31 keeps observe_v3's public result and adds a CUSTODY_ONLY block (die-top trace, source traces, second threshold with
  no default); public_scalars / v3.scalar_outputs never carry a custody field.
"""

from __future__ import annotations

import hashlib
import json

import pytest

from scripts.dev.reference_packages.elmer import f02_deck_v3 as v3
from scripts.dev.reference_packages.elmer import f02_deck_v31 as v31

POINTS = [[280.0, 1.0e6], [340.0, 3.0e6], [400.0, 9.0e6]]
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
FIXTURE_DECISION = "FIXTURE-V31-LAW-DECISION"


def _leak(tmp_path, decision, name="leak.json", points=POINTS):
    doc = {
        "schema": v3.LEAKAGE_SCHEMA,
        "decision": decision,
        "source": "test fixture",
        "form": "table",
        "range_k": [points[0][0], points[-1][0]],
        "points": points,
    }
    path = tmp_path / name
    path.write_text(json.dumps(doc, sort_keys=True))
    return path


def _ranges(tmp_path, name, schema, field, inputs=INPUTS, **over):
    doc = {
        "schema": schema,
        "status": "OWNER_SIGNED",
        "record": "fixture",
        "inputs": inputs,
        **({"nonce": "ab" * 16} if schema == v31.REGION_SCHEMA else {}),
        **over,
    }
    sha = hashlib.sha256(
        json.dumps(doc, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    path = tmp_path / name
    path.write_text(json.dumps({**doc, field: sha}))
    return path, sha


@pytest.fixture
def pinned(tmp_path, monkeypatch):
    leak = _leak(tmp_path, FIXTURE_DECISION)
    box, box_sha = _ranges(tmp_path, "box.json", v3.BOX_SCHEMA, "box_sha256")
    wide = {**INPUTS, "peak_w": [60, 110]}
    region, region_sha = _ranges(
        tmp_path, "region.json", v31.REGION_SCHEMA, "region_sha256", inputs=wide
    )
    monkeypatch.setattr(v31, "V31_LAW_DECISION", FIXTURE_DECISION)
    monkeypatch.setattr(
        v31, "V31_LAW_SHA256", hashlib.sha256(leak.read_bytes()).hexdigest()
    )
    monkeypatch.setattr(v31, "V31_BOX_SHA256", box_sha)
    monkeypatch.setattr(v31, "V31_REGION_SHA256", region_sha)
    return leak, box, region


# --- pins fail closed ------------------------------------------------------------------------------------------------


def test_every_pin_ships_as_human_input():
    assert v31.V31_LAW_DECISION == v3.HUMAN_INPUT
    assert (
        v31.V31_LAW_SHA256
        == v31.V31_BOX_SHA256
        == v31.V31_REGION_SHA256
        == v3.HUMAN_INPUT
    )
    assert v31.pins_status() == [
        "V31_LAW_DECISION",
        "V31_LAW_SHA256",
        "V31_BOX_SHA256",
        "V31_REGION_SHA256",
    ]
    assert v31.DECK_VERSION == "3.1"


def test_unpinned_writes_refuse(tmp_path):
    leak = _leak(tmp_path, FIXTURE_DECISION)
    box, _ = _ranges(tmp_path, "box.json", v3.BOX_SCHEMA, "box_sha256")
    region, _ = _ranges(tmp_path, "region.json", v31.REGION_SCHEMA, "region_sha256")
    with pytest.raises(v3.DeckRefused, match="v31_box_is_human_input"):
        v31.write_case_v31(CASE, tmp_path / "d", leakage_path=leak, box_path=box)
    with pytest.raises(v3.DeckRefused, match="v31_region_is_human_input"):
        v31.write_case_v31(CASE, tmp_path / "d", leakage_path=leak, region_path=region)
    with pytest.raises(v3.DeckRefused, match="v31_law_pin_is_human_input"):
        v31.load_v31_law(leak)
    assert not (tmp_path / "d").exists()


def test_law_pin_alone_still_refuses_writes(tmp_path, monkeypatch):
    leak = _leak(tmp_path, FIXTURE_DECISION)
    box, _ = _ranges(tmp_path, "box.json", v3.BOX_SCHEMA, "box_sha256")
    monkeypatch.setattr(v31, "V31_LAW_DECISION", FIXTURE_DECISION)
    monkeypatch.setattr(
        v31, "V31_LAW_SHA256", hashlib.sha256(leak.read_bytes()).hexdigest()
    )
    assert v31.load_v31_law(leak)["decision"] == FIXTURE_DECISION
    with pytest.raises(v3.DeckRefused, match="v31_box_is_human_input"):
        v31.write_case_v31(CASE, tmp_path / "d", leakage_path=leak, box_path=box)


# --- the pinned path --------------------------------------------------------------------------------------------------


def _physics(directory):
    sif = (directory / "case.sif").read_text()
    return "".join(line + "\n" for line in sif.splitlines() if not line.startswith("!"))


def test_pinned_box_deck_is_3_0_physics_labelled_3_1(tmp_path, pinned, monkeypatch):
    leak, box, _region = pinned
    meta = v31.write_case_v31(CASE, tmp_path / "d31", leakage_path=leak, box_path=box)
    assert meta["deck_version"] == "3.1" and meta["signed"]["version"] == "3.1"
    assert meta["deck_label"] == v3.SIGNED and meta["tables"] == "PRODUCTION"
    assert (
        meta["signed"]["box"].startswith("box sha256:")
        and meta["signed"]["decision"] == FIXTURE_DECISION
    )
    on_disk = json.loads((tmp_path / "d31" / "deck.json").read_text())
    assert on_disk["deck_version"] == "3.1"
    # same physics as the 3.0 signed deck on the same law file (3.0 pins monkeypatched to the fixture)
    monkeypatch.setattr(v3, "SIGNED_LEAKAGE_DECISION", FIXTURE_DECISION)
    monkeypatch.setattr(
        v3, "SIGNED_LEAKAGE_SHA256", hashlib.sha256(leak.read_bytes()).hexdigest()
    )
    monkeypatch.setattr(v3, "SIGNED_BOX_SHA256", v31.V31_BOX_SHA256)
    v3.write_signed_case(CASE, tmp_path / "d30", leakage_path=leak, box_path=box)
    assert _physics(tmp_path / "d31") == _physics(tmp_path / "d30")


def test_region_path_accepts_a_case_outside_the_box_but_inside_the_region(
    tmp_path, pinned
):
    leak, box, region = pinned
    hot = {**CASE, "peak_w": 100.0}
    with pytest.raises(v3.DeckRefused, match="case_outside_the_signed_box:peak_w"):
        v31.write_case_v31(hot, tmp_path / "b", leakage_path=leak, box_path=box)
    meta = v31.write_case_v31(
        hot, tmp_path / "r", leakage_path=leak, region_path=region
    )
    assert meta["signed"]["box"].startswith("region sha256:")
    with pytest.raises(v3.DeckRefused, match="case_outside_the_signed_box:peak_w"):
        v31.write_case_v31(
            {**CASE, "peak_w": 120.0},
            tmp_path / "r2",
            leakage_path=leak,
            region_path=region,
        )


def test_exactly_one_of_box_or_region(tmp_path, pinned):
    leak, box, region = pinned
    for kw in ({}, {"box_path": box, "region_path": region}):
        with pytest.raises(
            v3.DeckRefused, match="v31_name_exactly_one_of_box_or_region"
        ):
            v31.write_case_v31(CASE, tmp_path / "d", leakage_path=leak, **kw)


def test_wrong_law_files_refuse(tmp_path, pinned):
    _leak_ok, box, _region = pinned
    test_only = _leak(tmp_path, v3.LEAKAGE_TEST_ONLY, "test.json")
    other = _leak(tmp_path, "ANOTHER-DECISION", "other.json")
    changed = _leak(
        tmp_path,
        FIXTURE_DECISION,
        "changed.json",
        points=[[280.0, 1.0e6], [400.0, 9.5e6]],
    )
    for path, why in (
        (test_only, "leakage_file_digest_differs"),
        (other, "leakage_file_digest_differs"),
        (changed, "leakage_file_digest_differs"),
    ):
        with pytest.raises(v3.DeckRefused, match=why):
            v31.write_case_v31(CASE, tmp_path / "d", leakage_path=path, box_path=box)


def test_test_only_or_other_decision_refuses_even_at_the_pinned_digest(
    tmp_path, monkeypatch
):
    for decision, why in (
        (v3.LEAKAGE_TEST_ONLY, "leakage_test_coefficients_refuse_production"),
        ("ANOTHER-DECISION", "v31_law_not_the_signed_law"),
    ):
        leak = _leak(tmp_path, decision, f"{decision}.json")
        monkeypatch.setattr(v31, "V31_LAW_DECISION", FIXTURE_DECISION)
        monkeypatch.setattr(
            v31, "V31_LAW_SHA256", hashlib.sha256(leak.read_bytes()).hexdigest()
        )
        with pytest.raises(v3.DeckRefused, match=why):
            v31.load_v31_law(leak)


def test_box_and_region_must_be_the_signed_ones(tmp_path, pinned):
    leak, box, region = pinned
    doc = json.loads(box.read_text())
    bad = tmp_path / "bad-box.json"
    bad.write_text(json.dumps({**doc, "inputs": {**doc["inputs"], "peak_w": [70, 95]}}))
    with pytest.raises(v3.DeckRefused, match="v31_box_changed_after_signing"):
        v31.write_case_v31(CASE, tmp_path / "d", leakage_path=leak, box_path=bad)
    with pytest.raises(
        v3.DeckRefused, match="v31_box_schema"
    ):  # a region offered as the box
        v31.write_case_v31(CASE, tmp_path / "d", leakage_path=leak, box_path=region)
    with pytest.raises(
        v3.DeckRefused, match="v31_region_schema"
    ):  # the box offered as the region
        v31.write_case_v31(CASE, tmp_path / "d", leakage_path=leak, region_path=box)
    unsigned = tmp_path / "unsigned.json"
    unsigned.write_text(
        json.dumps({**json.loads(region.read_text()), "status": "HUMAN_INPUT"})
    )
    with pytest.raises(v3.DeckRefused, match="v31_region_not_the_signed_one"):
        v31.write_case_v31(
            CASE, tmp_path / "d", leakage_path=leak, region_path=unsigned
        )


def test_3_0_deck_is_untouched():
    assert v31.v3 is v3
    assert v3.SCALAR_KEYS == (
        "peak_top_c",
        "first_95c_crossing_s",
        "extra_energy_j",
        "time_above_s",
        "threshold_recovery_s",
        "second_pulse_peak_c",
    )
    assert (
        v3.SIGNED_LEAKAGE_SHA256
        == "f5d6f768d95ed6b7a3a8089a1b98963e555c232a493819fb669d417e96a95112"
    )
    assert (
        v3.SIGNED_BOX_SHA256
        == "d144ae42c22428654a9c61939aa55ae5de5745916cda79a48fea2128349b7227"
    )


# --- A3b: custody-only observations ------------------------------------------------------------------------------------


def _case_dir(tmp_path, series, version="3.1", name="case"):
    case = v3.resolve_case(CASE)
    directory = tmp_path / name
    directory.mkdir()
    (directory / "scalars.dat").write_text(
        "\n".join(f"{t!r} {v + 273.15!r} {v - 5.0 + 273.15!r}" for t, v in series)
        + "\n"
    )
    (directory / "scalars.dat.names").write_text(
        "   1: time\n   2: boundary max: temperature\n   3: value: temperature at node 1\n"
    )
    (directory / "deck.json").write_text(
        json.dumps(
            {
                "case": case,
                "schedule_w": v3.schedule(case),
                "tables": "PRODUCTION",
                "nonlinear": None,
                "deck_version": version,
                "signed": {"version": version},
            }
        )
    )
    return directory


SERIES = [
    (0.0, 40.0),
    (20.0, 40.0),
    (25.0, 100.0),
    (30.0, 70.0),
    (40.0, 40.0),
    (120.0, 40.0),
]


def test_observe_v31_keeps_the_public_result_and_adds_custody(tmp_path):
    d = _case_dir(tmp_path, SERIES)
    pub = v3.observe_v3(d, threshold_c=85.0)
    obs = v31.observe_v31(d, threshold_c=85.0, second_threshold_c=70.0)
    assert {k: obs[k] for k in pub} == pub
    assert obs["deck_version"] == "3.1"
    c = obs["custody"]
    assert c["label"] == v31.CUSTODY_ONLY
    assert c["die_top_trace_c"] == [[t, pytest.approx(v)] for t, v in SERIES]
    assert list(c["source_traces_c"]) == ["value: temperature at node 1"]
    assert c["source_traces_c"]["value: temperature at node 1"] == [
        pytest.approx(v - 5.0) for _t, v in SERIES
    ]
    # 40 -> 100 over 20..25 s crosses 70 C at 22.5 s; above 70 C from 22.5 s to 30 s
    assert c["second_threshold_crossing_s"] == pytest.approx(22.5)
    assert c["time_above_second_threshold_s"] == pytest.approx(
        v3.time_above_s([t for t, _ in SERIES], [v for _, v in SERIES], 70.0)
    )
    assert (
        v31.observe_v31(d, threshold_c=85.0, second_threshold_c=150.0)["custody"][
            "second_threshold_crossing_s"
        ]
        == "NOT_REACHED"
    )


def test_custody_never_reaches_the_public_scalars(tmp_path):
    obs = v31.observe_v31(
        _case_dir(tmp_path, SERIES), threshold_c=85.0, second_threshold_c=70.0
    )
    public = v31.public_scalars(obs)
    assert set(public) == set(v3.SCALAR_KEYS)
    assert (
        "custody" not in public
        and v31.custody_outputs(obs)["label"] == v31.CUSTODY_ONLY
    )


def test_second_threshold_has_no_default(tmp_path):
    d = _case_dir(tmp_path, SERIES)
    for bad in (None, True, float("nan"), "HUMAN_INPUT"):
        with pytest.raises(v3.DeckRefused, match="second_threshold_required"):
            v31.observe_v31(d, threshold_c=85.0, second_threshold_c=bad)
    with pytest.raises(TypeError):
        v31.observe_v31(d, threshold_c=85.0)  # pylint: disable=missing-kwoa


def test_custody_outputs_refuses_without_a_custody_block(tmp_path):
    pub = v3.observe_v3(_case_dir(tmp_path, SERIES), threshold_c=85.0)
    with pytest.raises(v3.DeckRefused, match="no_custody_block"):
        v31.custody_outputs(pub)


# --- review additions -----------------------------------------------------------------------------------------------------


def test_region_needs_a_custody_nonce(tmp_path, monkeypatch):
    leak = _leak(tmp_path, FIXTURE_DECISION)
    for nonce in (None, "short", "ZZ" * 16):
        over = {} if nonce is None else {"nonce": nonce}
        doc = {
            "schema": v31.REGION_SCHEMA,
            "status": "OWNER_SIGNED",
            "record": "fixture",
            "inputs": INPUTS,
            **over,
        }
        sha = hashlib.sha256(
            json.dumps(doc, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        path = tmp_path / f"r-{nonce}.json"
        path.write_text(json.dumps({**doc, "region_sha256": sha}))
        monkeypatch.setattr(v31, "V31_REGION_SHA256", sha)
        with pytest.raises(v3.DeckRefused, match="v31_region_needs_a_custody_nonce"):
            v31.write_case_v31(
                CASE, tmp_path / "d", leakage_path=leak, region_path=path
            )
    assert not (tmp_path / "d").exists()


def test_the_3_0_law_cannot_be_re_pinned_as_3_1(tmp_path, monkeypatch):
    leak = _leak(tmp_path, v3.SIGNED_LEAKAGE_DECISION)
    monkeypatch.setattr(v31, "V31_LAW_DECISION", v3.SIGNED_LEAKAGE_DECISION)
    monkeypatch.setattr(
        v31, "V31_LAW_SHA256", hashlib.sha256(leak.read_bytes()).hexdigest()
    )
    with pytest.raises(v3.DeckRefused, match="v31_law_pin_is_the_3_0_law"):
        v31.load_v31_law(leak)
    monkeypatch.setattr(v31, "V31_LAW_DECISION", FIXTURE_DECISION)
    monkeypatch.setattr(v31, "V31_LAW_SHA256", v3.SIGNED_LEAKAGE_SHA256)
    with pytest.raises(v3.DeckRefused, match="v31_law_pin_is_the_3_0_law"):
        v31.load_v31_law(leak)


def test_partial_pins_refuse_and_write_nothing(tmp_path, monkeypatch):
    leak = _leak(tmp_path, FIXTURE_DECISION)
    box, box_sha = _ranges(tmp_path, "box.json", v3.BOX_SCHEMA, "box_sha256")
    region, region_sha = _ranges(
        tmp_path, "region.json", v31.REGION_SCHEMA, "region_sha256"
    )
    monkeypatch.setattr(v31, "V31_BOX_SHA256", box_sha)
    monkeypatch.setattr(v31, "V31_REGION_SHA256", region_sha)
    # box + region pinned, law unset
    for kw in ({"box_path": box}, {"region_path": region}):
        with pytest.raises(v3.DeckRefused, match="v31_law_pin_is_human_input"):
            v31.write_case_v31(CASE, tmp_path / "d", leakage_path=leak, **kw)
    # law + box pinned, region unset: the region path refuses, the box path writes
    monkeypatch.setattr(v31, "V31_REGION_SHA256", v3.HUMAN_INPUT)
    monkeypatch.setattr(v31, "V31_LAW_DECISION", FIXTURE_DECISION)
    monkeypatch.setattr(
        v31, "V31_LAW_SHA256", hashlib.sha256(leak.read_bytes()).hexdigest()
    )
    with pytest.raises(v3.DeckRefused, match="v31_region_is_human_input"):
        v31.write_case_v31(CASE, tmp_path / "d", leakage_path=leak, region_path=region)
    assert not (tmp_path / "d").exists()
    v31.write_case_v31(CASE, tmp_path / "ok", leakage_path=leak, box_path=box)
    assert v31.is_v31_deck(json.loads((tmp_path / "ok" / "deck.json").read_text()))
    assert not (tmp_path / "ok" / "deck.json.tmp").exists()


def test_refusals_after_the_pin_checks_write_nothing(tmp_path, pinned):
    leak, box, region = pinned
    for kw, case in (
        ({"box_path": box}, {**CASE, "peak_w": 100.0}),
        ({"region_path": region}, {**CASE, "peak_w": 120.0}),
    ):
        with pytest.raises(v3.DeckRefused, match="case_outside_the_signed_box"):
            v31.write_case_v31(case, tmp_path / "d", leakage_path=leak, **kw)
    test_only = _leak(tmp_path, v3.LEAKAGE_TEST_ONLY, "t.json")
    with pytest.raises(v3.DeckRefused):
        v31.write_case_v31(CASE, tmp_path / "d", leakage_path=test_only, box_path=box)
    assert not (tmp_path / "d").exists()


def test_region_deck_physics_is_the_box_decks(tmp_path, pinned):
    leak, box, region = pinned
    v31.write_case_v31(CASE, tmp_path / "b", leakage_path=leak, box_path=box)
    v31.write_case_v31(CASE, tmp_path / "r", leakage_path=leak, region_path=region)
    assert _physics(tmp_path / "b") == _physics(tmp_path / "r")


def test_observe_v31_refuses_a_deck_that_is_not_3_1(tmp_path):
    for version, name in ((None, "none"), ("3.0", "v30")):
        d = _case_dir(tmp_path, SERIES, version=version, name=name)
        with pytest.raises(v3.DeckRefused, match="not_a_v31_deck"):
            v31.observe_v31(d, threshold_c=85.0, second_threshold_c=70.0)


def test_start_above_the_second_threshold_is_labelled(tmp_path):
    obs = v31.observe_v31(
        _case_dir(tmp_path, SERIES), threshold_c=85.0, second_threshold_c=35.0
    )
    c = obs["custody"]
    assert c["second_threshold_crossing_s"] == v31.ABOVE_AT_START
    assert c["time_above_second_threshold_s"] == pytest.approx(120.0)
