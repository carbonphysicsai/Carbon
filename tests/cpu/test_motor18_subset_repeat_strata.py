"""Motor 1.8's subset-repeat strata (CV-Motor-B, Sun 15 Nov, after the owner's "Yes for 66 per stratum"): every graded
row lands in exactly ONE stratum, from its registered source; a row in two or in none refuses; keyed strata re-run
min(66, n) rows and the gate sets every row; the counts tool prints counts only.

The registered sources are read from the committed registration (pool_constants.json) where the test checks them; the
banks and their pool sources are synthetic (no sealed custody material is in the repository).
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from types import SimpleNamespace

import pytest

from carbon.scoring import pool_physics_score
from carbon.scoring import subset_repeat_evidence as subset

ROOT = Path(__file__).resolve().parents[2]
MOTOR = "electric-motor-magnetics"
GRID, PROBE, POOL = "decision_sealed_grid", "probe_response", "pool_design"
NAMES = [
    "probe_response",
    "H-1",
    "H-3a",
    "H-3b",
    "gate_torque_7d1761c3",
    "gate_oc_697a0d7b",
    "menu_D3",
    "menu_D4",
    "menu_D5",
    "menu_D6",
]
KEY = bytes(range(32))  # synthetic K_speed


def _constants():
    return json.loads(
        (ROOT / "scripts/validator_host_classes/pool_constants.json").read_text(
            encoding="utf-8"
        )
    )["versions"][f"{MOTOR} 1.8"]


# -- the definitions are the registered ones ------------------------------------------------------------------------------


def test_the_strata_are_exactly_the_ruled_names_and_the_values_row_names_them():
    defined = subset.definitions(MOTOR, "1.8")
    assert list(defined) == NAMES
    values = json.loads(
        (ROOT / "scripts/validator_host_classes/subset_repeat.json").read_text(
            encoding="utf-8"
        )
    )["rows"][f"{MOTOR} 1.8"]
    assert values["strata"] == NAMES
    assert subset.registered_promise(MOTOR, "1.8")[2] == NAMES


def test_each_stratum_names_its_registered_source():
    defined = subset.definitions(MOTOR, "1.8")
    constants = _constants()
    classes = [n for n, d in defined.items() if d.source == "coverage_class"]
    # exactly the registered admission vocabulary (X-1), never H-2 / H-3
    assert classes == constants["optimizer"]["coverage_class_vocabulary"]
    assert classes == ["H-1", "H-3a", "H-3b"]
    menus = [d.selector for d in defined.values() if d.source == "menu_task"]
    assert (
        menus == sorted(constants["menu"]["records_sha256"]) == ["D3", "D4", "D5", "D6"]
    )
    torque = defined["gate_torque_7d1761c3"]
    oc = defined["gate_oc_697a0d7b"]
    assert torque.every and oc.every and (torque.n, oc.n) == (23, 24)
    # the gate outputs are the registered gate thresholds' outputs, split torque / open circuit
    assert set(torque.selector) | set(oc.selector) == set(
        constants["physics"]["gate_threshold"]
    )
    record = constants["provisional"]["record"]
    assert (
        "gate set 7d1761c3 (n 23)" in record and "OC gate set 697a0d7b n 24" in record
    )
    assert "in-range-cases.json 8ee64cc0 (47 cases)" in record
    assert constants["physics"]["in_range_cases_sha256"].startswith("8ee64cc0")
    assert defined["probe_response"] == subset.Stratum("cohort", PROBE)
    assert not any(d.every for n, d in defined.items() if not n.startswith("gate_"))


def test_another_version_has_no_strata():
    with pytest.raises(subset.SubsetRepeatRefused) as caught:
        subset.definitions(MOTOR, "1.5")
    assert caught.value.code == "subset_repeat_strata_undefined"


# -- the partition on synthetic banks -------------------------------------------------------------------------------------


def _bank(spec):
    """A synthetic bank from ``[(cohort, label), ...]``: each pool row's input is its own index, its label the pool
    source it is put in (None: no source; a tuple: several)."""
    return {
        "cohorts": [cohort for cohort, _ in spec],
        "inputs": [[float(i)] for i in range(len(spec))],
        "pool": {"input_names": ["x"]},
        "_labels": [label for _, label in spec],
    }


def _sources(defined, bank):
    sources = {
        (d.source, d.selector): set() for d in defined.values() if d.source != "cohort"
    }
    for i, label in enumerate(bank["_labels"]):
        for name in (label,) if type(label) is str else (label or ()):
            d = defined[name]
            sources[(d.source, d.selector)].add((float(i),))
    return sources, lambda row: tuple(float(row[n]) for n in ("x",))


@pytest.fixture
def synthetic(monkeypatch):
    """The real Motor 1.8 definitions over synthetic pool sources (the bank's own labels)."""
    monkeypatch.setattr(
        subset,
        "_pool_sources",
        lambda challenge, version, bank, defined: _sources(defined, bank),
    )


def _spec(*, torque=23, oc=24, extra=()):
    sizes = {
        "H-1": 120,
        "H-3a": 40,
        "H-3b": 7,
        "menu_D3": 70,
        "menu_D4": 66,
        "menu_D5": 3,
        "menu_D6": 80,
    }
    spec = [(GRID, None)] * 30 + [(PROBE, None)] * 76
    for name, n in sizes.items():
        spec += [(POOL, name)] * n
    spec += [(POOL, "gate_torque_7d1761c3")] * torque + [
        (POOL, "gate_oc_697a0d7b")
    ] * oc
    return spec + list(extra)


def test_every_row_lands_in_exactly_one_stratum(synthetic):
    bank = _bank(_spec())
    strata = subset.bank_strata(MOTOR, "1.8", bank)
    assert len(strata.sealed) == 30
    sizes = {name: len(rows) for name, rows in strata.members.items()}
    assert sizes == {
        "probe_response": 76,
        "H-1": 120,
        "H-3a": 40,
        "H-3b": 7,
        "gate_torque_7d1761c3": 23,
        "gate_oc_697a0d7b": 24,
        "menu_D3": 70,
        "menu_D4": 66,
        "menu_D5": 3,
        "menu_D6": 80,
    }
    assert strata.every == {"gate_torque_7d1761c3", "gate_oc_697a0d7b"}
    every = sorted(
        [*strata.sealed, *(p for rows in strata.members.values() for p in rows)]
    )
    assert every == list(range(len(bank["cohorts"])))


def test_min_66_per_keyed_stratum_and_every_gate_row(synthetic):
    strata = subset.bank_strata(MOTOR, "1.8", _bank(_spec()))
    counts = subset.registered_counts(MOTOR, "1.8", strata)
    assert counts == {
        "probe_response": 66,
        "H-1": 66,
        "H-3a": 40,
        "H-3b": 7,
        "gate_torque_7d1761c3": 23,
        "gate_oc_697a0d7b": 24,
        "menu_D3": 66,
        "menu_D4": 66,
        "menu_D5": 3,
        "menu_D6": 66,
    }
    sealed, keyed = subset.plan(
        KEY, "rtsk_a", challenge=MOTOR, version="1.8", strata=strata
    )
    assert sealed == list(strata.sealed)
    for name in strata.every:
        assert keyed[name] == list(strata.members[name])  # every gate row, every grade
    for name, rows in keyed.items():
        assert len(rows) == counts[name] and set(rows) <= set(strata.members[name])


@pytest.mark.parametrize(
    "extra, code",
    [
        ([(POOL, ("H-1", "menu_D3"))], "subset_repeat_row_in_two_strata"),
        ([(POOL, ("gate_oc_697a0d7b", "H-3a"))], "subset_repeat_row_in_two_strata"),
        ([(POOL, None)], "subset_repeat_row_in_no_stratum"),
        ([("practice", None)], "subset_repeat_row_in_no_stratum"),
    ],
)
def test_a_row_in_two_strata_or_in_none_refuses(synthetic, extra, code):
    bank = _bank(_spec(extra=extra))
    with pytest.raises(subset.SubsetRepeatRefused) as caught:
        subset.bank_strata(MOTOR, "1.8", bank)
    assert caught.value.code == code
    counted = subset.census(MOTOR, "1.8", bank)
    if code.endswith("two_strata"):
        assert sum(counted["overlaps"].values()) == 1  # reported, never resolved
    else:
        assert len(counted["none"]) == 1


@pytest.mark.parametrize(
    "spec, code",
    [
        (lambda: _spec(torque=22), "subset_repeat_gate_set_size"),
        (lambda: _spec(oc=25), "subset_repeat_gate_set_size"),
        (lambda: [s for s in _spec() if s[1] != "H-3b"], "subset_repeat_stratum_empty"),
        (lambda: [s for s in _spec() if s[0] != GRID], "subset_repeat_bank_strata"),
    ],
)
def test_a_bank_that_is_not_the_registered_shape_refuses(synthetic, spec, code):
    with pytest.raises(subset.SubsetRepeatRefused) as caught:
        subset.bank_strata(MOTOR, "1.8", _bank(spec()))
    assert caught.value.code == code


@pytest.mark.parametrize(
    "strata, code",
    [
        (None, "subset_repeat_strata_unregistered"),
        ([*NAMES[:-1]], "subset_repeat_strata_unregistered"),
        ([*NAMES, "menu_D7"], "subset_repeat_stratum_unknown"),
        ([*NAMES[:3], "H-2", *NAMES[4:]], "subset_repeat_stratum_unknown"),
    ],
)
def test_null_unknown_or_missing_strata_fail_closed(
    synthetic, tmp_path, monkeypatch, strata, code
):
    path = tmp_path / "subset_repeat.json"
    path.write_text(
        json.dumps(
            {
                "schema": subset.VALUES_SCHEMA,
                "rows": {
                    f"{MOTOR} 1.8": {
                        "repeat_fail_fraction": 0.10,
                        "repeat_detect_prob": 0.999,
                        "strata": strata,
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(subset, "VALUES_PATH", path)
    strata_ = subset.bank_strata(MOTOR, "1.8", _bank(_spec()))
    with pytest.raises(subset.SubsetRepeatRefused) as caught:
        subset.registered_counts(MOTOR, "1.8", strata_)
    assert caught.value.code == code


# -- the registered sources are routed to their strata --------------------------------------------------------------------


def test_pool_sources_route_classes_gate_cases_and_menu_rows(monkeypatch):
    """`_pool_sources` with the registry loaders replaced by synthetic ones: a target's designs go to its plan class, an
    in-range case by its truths' outputs, a menu task's rows to that task; nothing else is read.
    """
    from carbon.scoring import pool_exam, pool_grader, pool_menu, pool_version

    def target(target_id, designs):
        return SimpleNamespace(
            target_id=target_id, conditions={"fixed": {"c": 1.0}}, designs=designs
        )

    plan = SimpleNamespace(
        class_of=lambda target_id: {"T1": "H-1", "T2": "H-3a", "T3": "H-3b"}[target_id]
    )
    cases_doc = {
        "schema": pool_physics_score.IN_RANGE_CASES_SCHEMA,
        "cases": [
            {
                "class": "fixture",
                "inputs": {"c": 1.0, "d": 7.0},
                "truths": {"mean_torque_nm": 1.0, "ripple_pk_pk_nm": 1.0},
                "u": {"mean_torque_nm": 0.1, "ripple_pk_pk_nm": 0.1},
            },
            {
                "class": "fixture",
                "inputs": {"c": 1.0, "d": 8.0},
                "truths": {
                    "back_emf_open_circuit": 1.0
                },  # (a waveform where 1.8 registers one)
                "u": {"back_emf_open_circuit": 0.1},
            },
        ],
    }
    from carbon.scoring import pool_grader as grader

    truth = (
        [math.sin(2 * math.pi * k / 60) for k in range(60)]
        if "back_emf_open_circuit" in grader._WAVEFORMS
        else 1.0
    )
    cases_doc["cases"][1]["truths"]["back_emf_open_circuit"] = truth
    cases = pool_physics_score.in_range_cases(cases_doc)
    material = {
        "input_names": ["c", "d"],
        "design_names": ["d"],
        "input_dtype": "<f8",
        "sets": [["T1"], ["T2", "T3"]],
        pool_version.IN_RANGE_CASES: cases_doc,
    }
    loaded = {
        "T1": target("T1", [(1.0,)]),
        "T2": target("T2", [(2.0,)]),
        "T3": target("T3", [(3.0,)]),
    }
    tasks = [
        SimpleNamespace(
            problem=SimpleNamespace(target_id=f"D{k}"), rows=[{"c": 1.0, "d": 10.0 + k}]
        )
        for k in (3, 4, 5, 6)
    ]
    monkeypatch.setattr(pool_version, "check_material", lambda m: m)
    monkeypatch.setattr(
        pool_version,
        "registered_policies",
        lambda c, v: SimpleNamespace(
            physics=SimpleNamespace(in_range_cases_sha256=cases.sha256)
        ),
    )
    monkeypatch.setattr(pool_grader, "load_pool", lambda name: loaded[name])
    monkeypatch.setattr(
        pool_exam,
        "attach_coverage_plan",
        lambda policies, doc, sums, sets: SimpleNamespace(
            optimizer=SimpleNamespace(coverage_plan=plan)
        ),
    )
    monkeypatch.setattr(pool_version, "registered_menu", lambda c, v: "rule")
    monkeypatch.setattr(pool_version, "menu_tasks", lambda m, rule: tasks)
    monkeypatch.setattr(pool_menu, "task_rows", lambda task, names: (task.rows, None))
    sources, _key = subset._pool_sources(
        MOTOR, "1.8", {"pool": material}, subset.definitions(MOTOR, "1.8")
    )
    assert sources[("coverage_class", "H-1")] == {(1.0, 1.0)}
    assert sources[("coverage_class", "H-3a")] == {(1.0, 2.0)}
    assert sources[("coverage_class", "H-3b")] == {(1.0, 3.0)}
    assert sources[("in_range_outputs", ("mean_torque_nm", "ripple_pk_pk_nm"))] == {
        (1.0, 7.0)
    }
    assert sources[("in_range_outputs", ("back_emf_open_circuit",))] == {(1.0, 8.0)}
    for k in (3, 4, 5, 6):
        assert sources[("menu_task", f"D{k}")] == {(1.0, 10.0 + k)}
    # an in-range case set that is not the registered one refuses (Carbon's material)
    monkeypatch.setattr(
        pool_version,
        "registered_policies",
        lambda c, v: SimpleNamespace(
            physics=SimpleNamespace(in_range_cases_sha256="0" * 64)
        ),
    )
    with pytest.raises(subset.SubsetRepeatRefused) as caught:
        subset._pool_sources(
            MOTOR, "1.8", {"pool": material}, subset.definitions(MOTOR, "1.8")
        )
    assert caught.value.code == "subset_repeat_in_range_cases_unregistered"


def test_a_bank_without_pool_material_refuses():
    with pytest.raises(subset.SubsetRepeatRefused) as caught:
        subset.bank_strata(MOTOR, "1.8", {"cohorts": [GRID], "inputs": [[0.0]]})
    assert caught.value.code == "subset_repeat_strata_material"


# -- the counts tool ------------------------------------------------------------------------------------------------------


def _tool():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "subset_repeat_counts", ROOT / "scripts/dev/sealed_exam/subset_repeat_counts.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _numbers_and_names_only(value):
    if type(value) is dict:
        return all(
            type(k) is str and _numbers_and_names_only(v) for k, v in value.items()
        )
    return type(value) in (int, str)


def test_the_counts_tool_prints_counts_only(synthetic):
    document = _tool().counts(_bank(_spec()), MOTOR, "1.8")
    assert _numbers_and_names_only(document)
    assert (
        document["sealed"] == 30
        and document["none"] == 0
        and document["overlaps"] == {}
    )
    assert document["strata"]["H-3a"] == {"n": 40, "mode": "keyed", "per_grade": 40}
    assert document["strata"]["gate_oc_697a0d7b"] == {
        "n": 24,
        "mode": "all",
        "per_grade": 24,
        "registered_n": 24,
    }
    assert (
        document["per_grade_total"]
        == 30 + 66 + 66 + 40 + 7 + 23 + 24 + 66 + 66 + 3 + 66
    )
    assert document["rows"] == len(_spec())
    # an overlap is counted, not resolved and not refused
    overlapping = _tool().counts(
        _bank(_spec(extra=[(POOL, ("H-1", "menu_D3"))])), MOTOR, "1.8"
    )
    assert overlapping["overlaps"] == {"H-1+menu_D3": 1}


def test_only_door_and_grade_modules_import_the_subset_repeat_evidence():
    """V2B: the strata (and the in-range case set they read) live inside the grade; nothing that builds TRAIN, a kit, a
    view, the board or a miner report imports them."""
    import ast

    importers = set()
    for root in ("carbon", "scripts"):
        for path in (ROOT / root).rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
            for node in ast.walk(tree):
                names = []
                if isinstance(node, ast.ImportFrom) and node.module:
                    names = [node.module] + [
                        f"{node.module}.{alias.name}" for alias in node.names
                    ]
                elif isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                if "carbon.scoring.subset_repeat_evidence" in names:
                    importers.add(path.relative_to(ROOT).as_posix())
    assert importers == {
        # the door: the draw, the side file, the serve check; and the receiver's start-up check
        "carbon/challenge_validator/lean_recipe_retention.py",
        "carbon/challenge_validator/direct_receiver.py",
        # the grade: the evaluation key, the calibration tool's exact rule, the producer and its successor row
        "carbon/challenge_validator/bank_promotion.py",
        "carbon/challenge_validator/calibration_grade.py",
        "carbon/scoring/producer_successor.py",
        "carbon/scoring/subset_repeat_produce.py",
        # operator tools run in custody (counts only; the grader's own re-measure)
        "scripts/dev/design_value_parts.py",
        "scripts/dev/sealed_exam/subset_repeat_counts.py",
    }
