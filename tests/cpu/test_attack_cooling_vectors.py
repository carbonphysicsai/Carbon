"""Cooling's Level 0 attack vectors as a public, pure API for the Carbon
Validator's gate-audit harness (VALIDATOR-09), and the byte pin that keeps the
adapter's own output unchanged by it (GRAPHITE-ATTACKER-COOLING-API-01).

The claims tested:
- the pin: every prediction family's attacks, its oracle evidence and specimen
  digests, both control splits and each selective-fault selection on the
  scaffold are byte-identical to `cooling-l0.v2` as merged before the API
  (recorded before the transforms were refactored);
- `VECTOR_NAMES` holds the six vectors, each its family's attack example: on
  the adapter's own references `apply_vector` returns exactly that attack;
- on a synthetic reference set each vector changes its predictions in its own
  direction (optimism lowers the hot group's rise by 20%, the tilt keeps each
  profile's mean, the pressure drop is halved, one hot face is set to the
  inlet), the hot group defaults to the frozen rule's own definition and a
  caller's group is honoured;
- `faulted_cases` selects as the `selective_fault` family does;
- purity: no file is opened and no network or process call is made (an audit
  hook), and the references are never changed;
- an unknown name, `selective_fault` as a transform and malformed input are
  typed refusals;
- mutations: a transform turned the wrong way, or `apply_vector` opening a
  file, turns its guard red.
"""

from __future__ import annotations

import copy
import math
import sys

import pytest

from carbon.agent_campaign.attack.adapters import cooling as c

A = c.ADAPTER

# -- the byte pin: the adapter's output at cooling-l0.v2 --------------------------------------------
#: The families whose attacks or controls are built from the PRACTICE
#: references by the transforms the vector API shares.
PREDICTION_FAMILIES = (
    "cooling_optimism",
    "flow_imbalance_masking",
    "pressure_underprediction",
    "group_sacrifice",
    "mandatory_failure",
    "practice_disclosure",
    "resource_accounting",
)
#: Recorded at origin/main b327ac12d (`cooling-l0.v2`) before the refactor.
PINNED_VERSION = "carbon.attack.adapter.cooling-l0.v2"
PINNED = {
    "attacks": {
        "cooling_optimism": "sha256:ea1b5804650b121bbd698bae7f121fb886588f13888a9484259dc6e77f7a3691",
        "flow_imbalance_masking": "sha256:dcf797c9ccba52bae9af0b91f7abf2cd94d68fb59f6fcc2f079c4deee9331718",
        "group_sacrifice": "sha256:18296414ccd60ecad586bb99df2c19e68da64485ca732b090a20f308895ad2a6",
        "mandatory_failure": "sha256:510b8dbe1e8c4a93abc6c1e346828e4c25ed53b8ac1cc1e9b3f477e2bb49aa86",
        "practice_disclosure": "sha256:82984b9504113be1ca448208cd3bc03d6e81ed9c21953809b97f7a05cd85a65b",
        "pressure_underprediction": "sha256:1722291598ce6896a70cc912303bf7d40ef735dae2df952b6d2f840f591be8ec",
        "resource_accounting": "sha256:6ad0e897af132346384fcab95eee83546ed9ef65f0f0cb42eb384742845c8f5e",
        "selective_fault": "sha256:40b8766a8ab26cf5f99a8b2bc656ac1eba598ad52e768fe8a661778b3a576e4d",
    },
    "controls": {
        "held_out": "sha256:807184c3c0ac21acf54df105cc438c11e410821191358fe9b67c5f77f99eca08",
        "trained": "sha256:c174e79172e5f0598f59e0cc7194b76be0d50d5923aa8d4f0d1cc5d5097d3d4c",
    },
    "evidence": {
        "cooling_optimism": "sha256:e3f70850ec95dfbd31bd4dd8a961b3e928db5e0db87e97cb62fb5ff100be3c6f",
        "flow_imbalance_masking": "sha256:55bff355fe7f29b02129f9a0e6c9aace327469aae5e4c81758629c9231f7f60e",
        "group_sacrifice": "sha256:862440b4f8e6dcb671c2e15f8121e4434c81c1fd74cf8a7839eea6b24c4e45b0",
        "mandatory_failure": "sha256:4c6f41339e248984176e9f6dbe25c08aef66d7953b685569326c3dd9feafa508",
        "practice_disclosure": "sha256:7316a0f2fccdebe26559818663ddf8c1befa8ea170fcd2550d7a2c224f6807e6",
        "pressure_underprediction": "sha256:0f577a288461d90da061fff8a1bbc3a28467855f92b5b9658a40cac93e378b15",
        "resource_accounting": "sha256:43a5d79e47e881e855b3c45152b13a90359a4ba5db85f3236869710e68550bfb",
    },
    "faulted": {
        "above_own_mean": "sha256:1f6656623106e7fefe62012c6d22c1b00437b5a78436c4673e39334694c3c30e",
        "all": "sha256:bacd726eb924b8cdb80aa681e4fe28af5c694bb162f35e7df62e4ae74cf9903a",
        "hot_group": "sha256:e2354991414b429ae14c527582283729ac98b71c40405dc9e3a2c0da088f63a5",
        "none": "sha256:4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
        "worse_half": "sha256:4dddb6b28fcff369bf4b5ec0043b99d7f1dc86e29ae7238a70c24b3ed124c767",
        "worst_k": "sha256:8d59e55e3ca620eaaf35e055103225ecf760d918fd718f7ef890f480be478046",
    },
}


def _adapter_output():
    """The adapter's own output the pin binds, computed fresh."""
    out = {"attacks": {}, "evidence": {}, "controls": {}, "faulted": {}}
    for name in PREDICTION_FAMILIES + ("selective_fault",):
        spec = A.family_spec(name)
        out["attacks"][name] = c._digest([[n, v] for n, v in spec.attacks()])
    for name in PREDICTION_FAMILIES:
        spec = A.family_spec(name)
        readings = (A.assess(spec, item) for item in spec.attacks())
        out["evidence"][name] = c._digest(
            [[r.oracle.evidence_digest, r.oracle.specimen_digest] for r in readings]
        )
    for split in c.SPLITS:
        out["controls"][split] = A.controls_digest(split)
    for select in c.FAULT_SELECTIONS:
        out["faulted"][select] = c._digest(c._faulted_cases(c._scaffold(), select))
    return out


def test_the_adapters_output_is_byte_identical_to_the_pin():
    """The adapter's attacks, oracle evidence, controls and fault selections
    are unchanged; a change here is a change to the emitted output and moves
    `ADAPTER_VERSION`."""
    assert c.ADAPTER_VERSION == PINNED_VERSION
    c.clear_caches()
    assert _adapter_output() == PINNED


# -- the vector API ---------------------------------------------------------------------------------
PREDICTION_VECTORS = (
    "cooling_optimism",
    "flow_imbalance_masking",
    "pressure_underprediction",
    "group_sacrifice",
    "mandatory_failure",
)
HOT_CASES = frozenset(f"case-{i:02d}" for i in range(5, 12))


def _synthetic():
    """Twelve synthetic cases (no cooling data): a 30 C inlet, reference peaks
    from 60 C to 115 C in 5 K steps (85 C exactly among them), a profile of
    six segments rising along the flow and a pressure drop per case."""
    references = {}
    for i in range(12):
        inlet, peak = 30.0, 60.0 + 5.0 * i
        case = f"case-{i:02d}"
        references[case] = {
            "case_id": case,
            "inputs": {"inlet_c": inlet, "flow_lpm_per_kw": 1.0},
            "outputs": {
                "peak_c": peak,
                "profile_c": [
                    inlet + (peak - inlet) * (0.4 + 0.1 * j) for j in range(6)
                ],
                "pressure_drop_pa": 1000.0 + 100.0 * i,
            },
        }
    return references


def _exact(references):
    return {
        case: {k: r["outputs"][k] for k in ("peak_c", "profile_c", "pressure_drop_pa")}
        for case, r in references.items()
    }


def _check_optimism(name, references, hot):
    """The hot group's rise above the inlet 20% low, every other case exact."""
    out = c.apply_vector(name, references)
    exact = _exact(references)
    assert set(out) == set(references)
    for case, r in references.items():
        inlet, want, got = r["inputs"]["inlet_c"], exact[case], out[case]
        assert got["pressure_drop_pa"] == want["pressure_drop_pa"]
        if case not in hot:
            assert got == want, case
            continue
        assert got["peak_c"] - inlet == pytest.approx(
            0.8 * (want["peak_c"] - inlet), rel=1e-12
        )
        assert got["peak_c"] < want["peak_c"], case
        for t, w in zip(got["profile_c"], want["profile_c"], strict=True):
            assert t - inlet == pytest.approx(0.8 * (w - inlet), rel=1e-12)


def _check_tilt(references):
    """Every profile tilted along the flow with its mean kept: the inlet end
    cooler, the outlet end hotter; the peak still bounds the profile."""
    out = c.apply_vector("flow_imbalance_masking", references)
    for case, r in references.items():
        want, got = r["outputs"], out[case]
        assert got["profile_c"] != want["profile_c"], case
        assert math.isclose(
            sum(got["profile_c"]), sum(want["profile_c"]), rel_tol=1e-12
        ), case
        assert got["profile_c"][0] < want["profile_c"][0], case
        assert got["profile_c"][-1] > want["profile_c"][-1], case
        assert got["peak_c"] >= max(got["profile_c"]), case
        assert got["peak_c"] >= want["peak_c"], case
        assert got["pressure_drop_pa"] == want["pressure_drop_pa"], case


def _check_pressure(references):
    """Every pressure drop halved, temperatures exact."""
    out = c.apply_vector("pressure_underprediction", references)
    for case, r in references.items():
        want, got = r["outputs"], out[case]
        assert got["pressure_drop_pa"] == 0.5 * want["pressure_drop_pa"], case
        assert got["peak_c"] == want["peak_c"], case
        assert got["profile_c"] == want["profile_c"], case


def _check_mandatory(references, hot):
    """Exactly one case changed, the first hot case by id: its heated face no
    warmer than its inlet (a gate failure), everything else exact."""
    out = c.apply_vector("mandatory_failure", references)
    exact = _exact(references)
    target = min(hot)
    for case, r in references.items():
        want, got = exact[case], out[case]
        if case != target:
            assert got == want, case
            continue
        inlet = r["inputs"]["inlet_c"]
        assert got["peak_c"] == inlet
        assert got["profile_c"] == [inlet] * len(want["profile_c"])
        assert got["pressure_drop_pa"] == want["pressure_drop_pa"]


def _directions_hold():
    references = _synthetic()
    for name in ("cooling_optimism", "group_sacrifice"):
        _check_optimism(name, references, HOT_CASES)
    _check_tilt(references)
    _check_pressure(references)
    _check_mandatory(references, HOT_CASES)


def test_vector_names_are_the_six_cooling_vectors_under_the_adapter_version():
    assert c.VECTOR_NAMES == (
        "cooling_optimism",
        "flow_imbalance_masking",
        "pressure_underprediction",
        "group_sacrifice",
        "selective_fault",
        "mandatory_failure",
    )
    assert c.ADAPTER_VERSION == PINNED_VERSION
    for name in c.VECTOR_NAMES:
        assert A.family_spec(name).name == name


@pytest.mark.parametrize("name", PREDICTION_VECTORS)
def test_each_vector_is_its_familys_attack_example(name):
    """On the adapter's own public PRACTICE references, `apply_vector` returns
    exactly the prediction set of the family's attack example."""
    spec = A.family_spec(name)
    value = dict(spec.attacks())[spec.attack_example]
    expected = value.get("predictions", value)
    assert c.apply_vector(name, c._references()) == expected


def test_the_hot_group_defaults_to_the_frozen_rules_definition():
    references = _synthetic()
    assert c._hot(references) == HOT_CASES
    # case-05's reference peak is exactly T_IMPORTANT_C: it is in the group.
    assert references["case-05"]["outputs"]["peak_c"] == c.T_IMPORTANT_C
    assert "case-05" in HOT_CASES


def test_each_vector_changes_predictions_in_its_own_direction():
    _directions_hold()


def test_a_callers_important_group_is_honoured():
    references = _synthetic()
    exact = _exact(references)
    chosen = {"case-01", "case-03"}
    for name in ("cooling_optimism", "group_sacrifice"):
        out = c.apply_vector(name, references, important=chosen)
        assert {case for case in out if out[case] != exact[case]} == chosen, name
    out = c.apply_vector("mandatory_failure", references, important=chosen)
    assert {case for case in out if out[case] != exact[case]} == {"case-01"}
    assert out["case-01"]["peak_c"] == references["case-01"]["inputs"]["inlet_c"]
    # The vectors that touch every case read no group.
    for name in ("flow_imbalance_masking", "pressure_underprediction"):
        assert c.apply_vector(name, references, important=chosen) == c.apply_vector(
            name, references
        )


SCORES = {
    f"case-{i:02d}": s
    for i, s in enumerate(
        (0.1, 0.9, 0.3, 0.9, 0.45, 0.2, 0.8, 0.05, 0.7, 0.4, 0.6, 0.15)
    )
}


def test_faulted_cases_selects_as_the_selective_fault_family_does():
    every = sorted(SCORES)
    assert c.faulted_cases("none", SCORES) == []
    assert c.faulted_cases("all", SCORES) == every
    # worst_k: a tenth by default (at least one); ties broken by case id.
    assert c.faulted_cases("worst_k", SCORES) == ["case-01"]
    assert c.faulted_cases("worst_k", SCORES, k=2) == ["case-01", "case-03"]
    assert c.faulted_cases("worst_k", SCORES, k=3) == ["case-01", "case-03", "case-06"]
    assert c.faulted_cases("worst_k", SCORES, k=99) == every
    assert c.faulted_cases("worse_half", SCORES) == [
        "case-01",
        "case-03",
        "case-04",
        "case-06",
        "case-08",
        "case-10",
    ]
    assert c.faulted_cases("above_own_mean", SCORES) == [
        "case-01",
        "case-03",
        "case-06",
        "case-08",
        "case-10",
    ]
    assert c.faulted_cases("hot_group", SCORES, important={"case-07", "case-02"}) == [
        "case-02",
        "case-07",
    ]


def test_the_adapter_selects_its_faulted_cases_through_the_public_function():
    """The family's own selection on the scaffold is `faulted_cases` over the
    scaffold's per-case error on the public PRACTICE references."""
    errors = c._honest(c._scaffold())["errors"]
    for select in c.FAULT_SELECTIONS:
        assert c._faulted_cases(c._scaffold(), select) == c.faulted_cases(
            select, errors, important=c._important_ids()
        ), select


#: Audit events that would make the API impure: a file opened, a directory
#: listed, a network or process call.
IMPURE_EVENTS = frozenset(
    {
        "open",
        "os.listdir",
        "os.scandir",
        "socket.connect",
        "socket.getaddrinfo",
        "subprocess.Popen",
        "os.system",
    }
)
_SEEN = []
_WATCHING = []


def _watch(event, args):
    if _WATCHING and event in IMPURE_EVENTS:
        _SEEN.append((event, repr(args)[:200]))


def _impure_events():
    """Every audited event while every vector and every selection runs."""
    if not getattr(sys, "_cooling_vector_audit", False):
        sys.addaudithook(_watch)
        sys._cooling_vector_audit = True
    references = _synthetic()
    _SEEN.clear()
    _WATCHING.append(True)
    try:
        for name in PREDICTION_VECTORS:
            c.apply_vector(name, references)
            c.apply_vector(name, references, important={"case-06"})
        for select in c.FAULT_SELECTIONS:
            c.faulted_cases(select, SCORES, important={"case-06"})
        c.faulted_cases("worst_k", SCORES, k=4)
    finally:
        _WATCHING.clear()
    return list(_SEEN)


def _pure():
    assert _impure_events() == []


def test_the_api_opens_no_file_and_calls_nothing_outside():
    _pure()


def test_the_api_never_changes_the_references_or_shares_their_lists():
    references = _synthetic()
    before = copy.deepcopy(references)
    for name in PREDICTION_VECTORS:
        out = c.apply_vector(name, references)
        for case, prediction in out.items():
            given = references[case]["outputs"]["profile_c"]
            assert prediction["profile_c"] is not given, (name, case)
        out["case-00"]["profile_c"].append(0.0)
    assert references == before
    scores = dict(SCORES)
    c.faulted_cases("above_own_mean", scores)
    assert scores == SCORES


def _refused(call, code, kind=c.VectorError):
    with pytest.raises(kind) as raised:
        call()
    assert isinstance(raised.value, ValueError)
    assert raised.value.code == code, raised.value
    return raised.value


def test_unknown_names_and_malformed_input_are_typed_refusals():
    references = _synthetic()
    for name in ("nope", "out_of_regime_reynolds", None, 3):
        _refused(
            lambda n=name: c.apply_vector(n, references),
            "unknown_vector",
            c.UnknownVector,
        )
        _refused(
            lambda n=name: c.faulted_cases(n, SCORES), "unknown_vector", c.UnknownVector
        )
    refusal = _refused(
        lambda: c.apply_vector("selective_fault", references), "fault_pattern"
    )
    assert not isinstance(refusal, c.UnknownVector)

    def broken(edit):
        bad = _synthetic()
        edit(bad["case-03"])
        return bad

    malformed = (
        {},
        [],
        {3: references["case-00"]},
        broken(lambda r: r["inputs"].pop("inlet_c")),
        broken(lambda r: r["outputs"].update(peak_c=math.nan)),
        broken(lambda r: r["outputs"].update(pressure_drop_pa=True)),
        broken(lambda r: r["outputs"].update(profile_c=[40.0])),
        broken(lambda r: r["outputs"].update(profile_c="40,50")),
        broken(lambda r: r.pop("outputs")),
    )
    for bad in malformed:
        _refused(
            lambda b=bad: c.apply_vector("cooling_optimism", b), "malformed_reference"
        )
    for important in ("case-05", [["case-05"]], {"case-99"}, 5):
        _refused(
            lambda i=important: c.apply_vector(
                "cooling_optimism", references, important=i
            ),
            "malformed_important",
        )
    _refused(
        lambda: c.apply_vector("mandatory_failure", references, important=set()),
        "no_important_case",
    )
    for k in (0, -1, True, 1.5, "2"):
        _refused(lambda k=k: c.faulted_cases("worst_k", SCORES, k=k), "malformed_k")
    _refused(lambda: c.faulted_cases("worse_half", SCORES, k=2), "k_not_applicable")
    _refused(lambda: c.faulted_cases("hot_group", SCORES), "important_required")
    _refused(
        lambda: c.faulted_cases("hot_group", SCORES, important={"case-99"}),
        "malformed_important",
    )
    for scores in ({}, {"case-00": math.inf}, {"case-00": None}, {1: 0.5}):
        _refused(lambda s=scores: c.faulted_cases("worst_k", s), "malformed_case_score")


# -- mutations: each broken property turns its guard red -------------------------------------------
def _scaled_the_other_way(m, name, change):
    original = getattr(c, name)
    m.setattr(c, name, lambda refs, x, *a, **kw: original(refs, change(x), *a, **kw))


def _optimism_turned_conservative(m):
    _scaled_the_other_way(m, "_rise_scaled", lambda f: 1 / f)


def _pressure_raised(m):
    _scaled_the_other_way(m, "_pressure_scaled", lambda f: 1 / f)


def _tilt_reversed(m):
    _scaled_the_other_way(m, "_redistributed", lambda f: -f)


def _hot_face_left_warm(m):
    m.setattr(c, "_face_at_inlet", lambda p, t_in: {**p, "peak_c": t_in})


def _apply_vector_opens_a_file(m):
    original = c._exact

    def reading(references):
        with open(c.__file__, encoding="utf-8") as handle:
            handle.read(1)
        return original(references)

    m.setattr(c, "_exact", reading)


def _faulted_cases_lists_a_directory(m):
    import os

    original = c._checked_cases

    def listing(*args):
        os.listdir(os.path.dirname(c.__file__))
        return original(*args)

    m.setattr(c, "_checked_cases", listing)


MUTATIONS = {
    "optimism_turned_conservative": (_optimism_turned_conservative, _directions_hold),
    "pressure_raised": (_pressure_raised, _directions_hold),
    "tilt_reversed": (_tilt_reversed, _directions_hold),
    "hot_face_left_warm": (_hot_face_left_warm, _directions_hold),
    "apply_vector_opens_a_file": (_apply_vector_opens_a_file, _pure),
    "faulted_cases_lists_a_directory": (_faulted_cases_lists_a_directory, _pure),
}


@pytest.mark.parametrize("name", sorted(MUTATIONS))
def test_each_broken_property_turns_its_guard_red(name, monkeypatch):
    mutate, guard = MUTATIONS[name]
    mutate(monkeypatch)
    with pytest.raises(AssertionError):
        guard()
    monkeypatch.undo()
    guard()
