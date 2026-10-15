"""Discriminating completed-menu producer controls; synthetic outcomes only.

Declarative public IDs/contracts are checked without opening a public outcome.
Execution belongs to remote canonical CI, never the OPERATOR host window.
"""

from __future__ import annotations

import ast
import copy
import gzip
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.dev.score_lab import bank, candidates, owner_dev_v1
from scripts.dev.score_lab import completed_menu as c
from scripts.dev.score_lab import completed_menu_replay as producer
from scripts.dev.score_lab.core import LabRefused


def toy():
    protocol = {
        "first_line": "FIXTURE conditional SCORED stratum",
        "questions": [],
        "P": {"support_frozen": ["q1", "q2"]},
        "folds": {"A": ["q1"], "B": ["q2"]},
    }
    action_of, assessed, coverage = {}, {}, {}
    for i, qid in enumerate(("q1", "q2")):
        ids = [f"ev4:D-toy{i}:{a}:0" for a in ("f", "a", "bad")]
        protocol["questions"].append(
            {
                "question_id": qid,
                "native_context_id": f"D-toy{i}",
                "case_ids": ids,
                "fallback_case_id": ids[0],
            }
        )
        for cid, aid, objective in zip(ids, ("f", "a", "bad"), (300.0, 60.0, 30.0)):
            action_of[cid] = aid
            assessed[cid] = {
                "status": "INFEASIBLE" if aid == "bad" else "FEASIBLE",
                "objective": objective,
            }
            coverage[cid] = covered_row(cid)
    return protocol, action_of, assessed, coverage


def covered_row(cid, m20=2.0, m160=2.0):
    verdict = owner_dev_v1.v2_label(m20 / 1000, None if m160 is None else m160 / 1000)
    return {
        "m20_mv": m20,
        "sealed_v2": (
            None
            if verdict is None
            else {
                "source": "ev4",
                "case_id": cid,
                "m20_mv": m20,
                "m160_mv": m160,
                **verdict,
            }
        ),
    }


def questions_and_predictions():
    protocol, actions, assessed, coverage = toy()
    questions, receipt = c.reference_questions(protocol, actions, assessed, coverage)
    pred = {
        q: {
            a: {"feasible": a != "bad", "objective": rows[0]["objective"]}
            for a, rows in question["actions"].items()
        }
        for q, question in questions.items()
    }
    return protocol, questions, pred, receipt


class FixtureInputs:
    def __init__(self, out, *, model=1, truth=2):
        self.identity = {"scope": "FIXTURE"}
        self.out, self.model, self.value = out, model, truth
        self.events = []

    def models(self):
        self.events.append("models")
        return {
            "scope": "FIXTURE",
            "quantities": {"model": self.model},
            "constructed_controls_included": False,
            "references_opened": False,
        }

    def truth(self):
        self.events.append("truth")
        # This is the actual file written by replay, not a caller chronology flag.
        if "models" in self.events:
            assert json.loads((self.out / "prediction-commitment.json").read_bytes())[
                "quantities"
            ] == {"model": self.model}
        return {}, {"value": self.value}

    def analyze(self, questions, receipt):
        self.events.append("analyze")
        return {"scope": "FIXTURE", "truth": receipt}


def test_c01_actual_producer_closes_commit_before_truth_and_write_failure_stops_it(
    tmp_path, monkeypatch
):
    out = tmp_path / "good"
    fixture = FixtureInputs(out)
    original = Path.open
    handles = []

    def track(path, *args, **kwargs):
        stream = original(path, *args, **kwargs)
        if path.name == "prediction-commitment.json" and args and args[0] == "xb":
            handles.append(stream)
        return stream

    monkeypatch.setattr(Path, "open", track)
    truth = fixture.truth

    def closed_truth():
        assert handles and handles[0].closed
        return truth()

    fixture.truth = closed_truth
    producer.replay(fixture, out)
    assert fixture.events == ["models", "truth", "analyze"]
    broken = FixtureInputs(tmp_path / "broken")
    monkeypatch.setattr(
        producer,
        "write_new",
        lambda *args: (_ for _ in ()).throw(OSError("FIXTURE write refused")),
    )
    with pytest.raises(OSError, match="write refused"):
        producer.replay(broken, broken.out)
    assert broken.events == ["models"]


def test_c02_truth_cannot_change_prediction_commitment_but_model_does(tmp_path):
    commits = []
    for n, model, truth in ((1, 10, 1), (2, 10, 99), (3, 11, 1)):
        out = tmp_path / str(n)
        producer.replay(FixtureInputs(out, model=model, truth=truth), out)
        commits.append((out / "prediction-commitment.json").read_bytes())
    assert commits[0] == commits[1] != commits[2]
    assert json.loads(commits[0])["constructed_controls_included"] is False


def registered_grammar():
    protocol = json.loads((producer.REGISTRATION / producer.PROTOCOL).read_bytes())
    contract = json.loads(
        (
            producer.ROOT / protocol["binding_closure"]["native_contract"]["path"]
        ).read_bytes()
    )
    return protocol, contract


def test_c03_exact_registered_33_native_join_and_identity_perturbations():
    protocol, contract = registered_grammar()
    _, action_of, menus = producer.native_menus(protocol, contract)
    assert len(action_of) == 33 and len(menus) == 8
    for mutation in ("missing", "duplicate", "alias", "wrong_context", "foreign"):
        bad = copy.deepcopy(protocol)
        if mutation == "missing":
            bad_actions = dict(action_of)
            bad_actions.pop(next(iter(bad_actions)))
            with pytest.raises(LabRefused):
                c.manifest(bad, bad_actions)
            continue
        if mutation == "duplicate":
            bad["questions"][0]["case_ids"].append(bad["questions"][0]["case_ids"][0])
        elif mutation == "alias":
            bad["questions"][1]["native_context_id"] = bad["questions"][0][
                "native_context_id"
            ]
        elif mutation == "wrong_context":
            bad["questions"][0]["case_ids"][1] = bad["questions"][1]["case_ids"][1]
        else:
            bad["questions"][0]["case_ids"][1] = "ev4:D-T14-S0.12:c1=999,c2=999:0"
        with pytest.raises(LabRefused):
            producer.native_menus(bad, contract)


def test_c04_actual_frozen_lexical_reader_skips_unselected_poison_and_pins_first(
    tmp_path, monkeypatch
):
    readers = producer.frozen_readers()
    assert not hasattr(readers, "main")
    text = '{"member":"fixture","predictions":{"V-secret":{"poison":UNDECODABLE},"D-toy":{"x":7}}}'
    source = tmp_path / "toy.json.gz"
    source.write_bytes(gzip.compress(text.encode()))
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    original_decoder = json.JSONDecoder

    class Decoder(original_decoder):
        def raw_decode(self, text, idx=0):
            assert not text[idx:].startswith('{"poison"')
            return super().raw_decode(text, idx)

    monkeypatch.setattr(json, "JSONDecoder", Decoder)
    assert readers.predictions(source, digest, {"D-toy"}, "fixture") == {
        "D-toy": {"x": 7}
    }
    monkeypatch.setattr(
        gzip, "open", lambda *a, **k: pytest.fail("decoded before hash check")
    )
    with pytest.raises(ValueError, match="INPUT_CHANGED"):
        readers.predictions(source, "0" * 64, {"D-toy"}, "fixture")


def test_c04_original_reference_reader_skips_unselected_v_record_before_decode(
    tmp_path, monkeypatch
):
    reader = producer.frozen_readers().reference_rows
    raw = b'{"poison":UNDECODABLE,"case_id":"V-secret"}\n{"case_id":"D-toy","status":"OK","outputs":{}}\n'
    path = tmp_path / "refs.jsonl"
    path.write_bytes(raw)
    monkeypatch.setitem(
        reader.__globals__, "OLD_REF_SHA", hashlib.sha256(raw).hexdigest()
    )
    assert reader(path, {"D-toy"}) == {
        "D-toy": {"case_id": "D-toy", "status": "OK", "outputs": {}}
    }
    path.write_bytes(raw + b" ")
    with pytest.raises(ValueError, match="INPUT_CHANGED"):
        reader(path, {"D-toy"})


@pytest.mark.parametrize(
    "fault", ["outside", "missing", "pending", "nonfinite", "dominated_unresolved"]
)
def test_c06_unselected_dominated_defect_excludes_whole_question(fault):
    protocol, actions, assessed, coverage = toy()
    cid = protocol["questions"][0]["case_ids"][-1]
    if fault == "outside":
        coverage[cid] = covered_row(cid, 15)
    elif fault == "missing":
        coverage.pop(cid)
    elif fault == "pending":
        coverage[cid] = covered_row(cid, 2, None)
    elif fault == "nonfinite":
        coverage[cid]["m20_mv"] = float("nan")
    else:
        assessed[cid] = {"status": "UNRESOLVED", "objective": 99999.0}
    questions, receipt = c.reference_questions(protocol, actions, assessed, coverage)
    assert questions["q1"]["class"] == "INCOMPLETE"
    assert receipt["scored_questions"] == ["q2"] and receipt["pruned_actions"] == 0
    assert len(questions["q1"]["actions"]) == 3
    assert receipt["class_P_mass"]["INCOMPLETE"] == 0.5


@pytest.mark.parametrize(
    "kind,expected",
    [("unknown", "INCOMPLETE"), ("unsafe", "RESCUE"), ("all_unsafe", "NONE")],
)
def test_c07_anchor_not_replaced_and_unscored_strata_retained(kind, expected):
    protocol, actions, assessed, coverage = toy()
    for cid in protocol["questions"][0]["case_ids"]:
        if cid == protocol["questions"][0]["fallback_case_id"] or kind == "all_unsafe":
            assessed[cid]["status"] = (
                "UNRESOLVED" if kind == "unknown" else "INFEASIBLE"
            )
    questions, receipt = c.reference_questions(protocol, actions, assessed, coverage)
    assert questions["q1"]["class"] == expected
    assert questions["q1"]["fallback_action"] == "f"
    assert receipt["class_counts"][expected] == 1 and receipt["offered_P_mass"] == 1


@pytest.mark.parametrize(
    "key,bad", [("source", "pdd"), ("rule", "draft"), ("m20_mv", 2000)]
)
def test_c08_wrong_source_rule_or_margin_join_refuses(key, bad):
    protocol, actions, assessed, coverage = toy()
    cid = next(iter(actions))
    coverage[cid]["sealed_v2"][key] = bad
    with pytest.raises(LabRefused, match="source_rule_or_join"):
        c.reference_questions(protocol, actions, assessed, coverage)


def test_c08_changed_registered_source_refuses_before_json_or_import(
    tmp_path, monkeypatch
):
    path = tmp_path / "untrusted"
    path.write_bytes(b"not even JSON or Python")
    with pytest.raises(LabRefused, match="input_digest"):
        producer.pinned(path, "0" * 64)
    monkeypatch.setattr(producer, "REGISTRATION", tmp_path)
    (tmp_path / "frozen-public-readers.py.txt").write_text(
        "raise AssertionError('imported')", encoding="utf-8"
    )
    with pytest.raises(LabRefused, match="input_digest"):
        producer.frozen_readers()


def test_c08_new_library_requires_completed_provenance_not_other_allowed_v2_rule():
    row = covered_row("toy", 2, 2)["sealed_v2"]
    producer.completed_library_labels({"toy": row}, {"toy"})
    producer.completed_library_labels(
        {}, {"toy"}
    )  # Missing truth is handled by common mask.
    row["rule"] = "m20-above-window-r1"
    with pytest.raises(LabRefused, match="completed_library_source_rule"):
        producer.completed_library_labels({"toy": row}, {"toy"})


def test_c08_loaded_helper_from_foreign_checkout_refused_with_intact_source_pins(
    tmp_path,
):
    selected = json.loads((producer.REGISTRATION / producer.BINDINGS).read_bytes())[
        "selected_source_files_sha256"
    ]
    origins = producer.bound_module_origins(producer.ROOT, selected)
    assert origins["carbon.battery.exam"] == str(Path(producer.exam.__file__).resolve())
    modules = dict(producer.sys.modules)
    modules["carbon.battery.exam"] = SimpleNamespace(__file__=str(tmp_path / "exam.py"))
    with pytest.raises(LabRefused, match="loaded_module_origin"):
        producer.bound_module_origins(producer.ROOT, selected, modules)


def analysis_inputs():
    protocol, questions, prediction, _ = questions_and_predictions()
    ids = ["a", "b", "c", "d"]
    predictions = {m: copy.deepcopy(prediction) for m in ids + ["control"]}
    errors = {m: {"q1": i, "q2": i} for i, m in enumerate(ids + ["control"])}
    groups = {m: "recipe-" + m for m in ids}
    return protocol, questions, predictions, errors, groups, ids


def fixed_rule(predictions, references, metadata):
    # A deterministic toy rule; native rules are exercised in C13/C17 below.
    return {
        "score": sum(
            p["objective"] for ps in predictions.values() for p in ps.values()
        ),
        "detail": {"questions": len(metadata["questions"])},
    }


def test_c05_leg_firewall_and_fixed_selection_under_value_only_changes(monkeypatch):
    protocol, questions, preds, errors, groups, ids = analysis_inputs()
    calls = []

    def spy(p, r, md):
        calls.append((set(p), set(r), set(md["questions"])))
        return fixed_rule(p, r, md)

    monkeypatch.setattr(c.score_proof, "bootstrap", lambda *a, **k: None)
    for side, leg, value in (("A", "q1", "q2"), ("B", "q2", "q1")):
        first = c.orientation(
            protocol,
            questions,
            preds,
            errors,
            groups,
            ids,
            ["control"],
            {"toy": spy},
            leg_fold=side,
        )
        changed = copy.deepcopy(preds)
        changed["a"][value]["a"]["objective"] = 999.0
        second = c.orientation(
            protocol,
            questions,
            changed,
            errors,
            groups,
            ids,
            ["control"],
            {"toy": spy},
            leg_fold=side,
        )
        assert (
            first["rules"]["toy"]["fixed_LEG_selection"]
            == second["rules"]["toy"]["fixed_LEG_selection"]
        )
        assert all(row == ({leg}, {leg}, {leg}) for row in calls)
        calls.clear()
    aliased = copy.deepcopy(protocol)
    aliased["questions"][1]["case_ids"][0] = aliased["questions"][0]["case_ids"][0]
    with pytest.raises(LabRefused):
        c.manifest(
            aliased, {cid: cid for q in aliased["questions"] for cid in q["case_ids"]}
        )


def test_c09_empty_mask_and_undefined_tau_are_null_not_zero():
    protocol, questions, preds, errors, groups, ids = analysis_inputs()
    questions["q1"]["class"] = "INCOMPLETE"
    empty = c.orientation(
        protocol,
        questions,
        preds,
        errors,
        groups,
        ids,
        [],
        {"toy": fixed_rule},
        leg_fold="A",
    )
    assert empty["status"] == "INSUFFICIENT_EVIDENCE" and empty["LEG_questions"] == []
    assert (
        empty["VALUE_questions"] == ["q2"]
        and empty["original_folds"] == protocol["folds"]
    )
    questions["q1"]["class"] = "SCORED"
    tied = c.orientation(
        protocol,
        questions,
        preds,
        errors,
        groups,
        ids,
        [],
        {"toy": fixed_rule},
        leg_fold="A",
    )
    assert tied["rules"]["toy"]["tau"] is None
    assert tied["rules"]["toy"]["bootstrap"]["undefined_fraction"] == 1


def test_c10_pinned_cohort_partition_and_group_spoofs():
    records = [
        {
            "public_member_id": str(i),
            "dependence_group_RESEARCH_V1": "recipe" + str(i // 2),
        }
        for i in range(137)
    ]
    cohorts = {
        "primary_ev4_cpu_100": [str(i) for i in range(100)],
        "other_raw_37": [str(i) for i in range(100, 137)],
    }
    assert len(producer.cohort_partition({"records": records}, cohorts)[0]) == 137
    for kind in ("duplicate", "group", "cohort"):
        bad_r, bad_c = copy.deepcopy(records), copy.deepcopy(cohorts)
        if kind == "duplicate":
            bad_r[-1]["public_member_id"] = "0"
        elif kind == "group":
            bad_r[0]["dependence_group_RESEARCH_V1"] = None
        else:
            bad_c["other_raw_37"][0] = "0"
        with pytest.raises(LabRefused):
            producer.cohort_partition({"records": bad_r}, bad_c)


def test_c10_missing_model_keeps_declared_denominator_and_reference_mask(monkeypatch):
    protocol, questions, preds, errors, groups, ids = analysis_inputs()
    preds.pop("d")
    monkeypatch.setattr(c.score_proof, "bootstrap", lambda *a, **k: None)
    result = c.orientation(
        protocol,
        questions,
        preds,
        errors,
        groups,
        ids,
        ["control"],
        {"toy": fixed_rule},
        leg_fold="A",
    )
    row = result["rules"]["toy"]
    assert row["matched_real_members"] == ["a", "b", "c"]
    assert row["fixed_LEG_selection"]["admitted_count"] == 4
    assert row["fixed_LEG_selection"]["status"] == "INSUFFICIENT_EVIDENCE"
    assert row["unavailable_real_members"] == ["d"]
    assert result["LEG_questions"] == ["q1"] and result["VALUE_questions"] == ["q2"]
    with pytest.raises(LabRefused):
        c.orientation(
            protocol, questions, preds, errors, groups, ids, ["a"], {}, leg_fold="A"
        )


def test_c11_diagnostic_selection_does_not_claim_vacuous_gamer_pass():
    selection = c.diagnostic_selection(
        {"a": 4, "b": 3, "c": 2, "d": 2}, ["a", "b", "c", "d"]
    )
    assert selection["selected"] == ["a", "b", "c"] and selection["cutoff_ties"] == [
        "c",
        "d",
    ]
    assert selection["gamer_screen"].startswith("UNMEASURED")
    assert "no_gamer_in_top_half" not in selection
    assert c.diagnostic_selection({"a": 1}, ["a", "b", "c"])["missing_scores"] == [
        "b",
        "c",
    ]


def test_c12_selected_missing_value_cannot_choose_fourth_member(monkeypatch):
    protocol, questions, preds, errors, groups, ids = analysis_inputs()
    preds["b"]["q2"] = None
    monkeypatch.setattr(c.score_proof, "bootstrap", lambda *a, **k: None)
    result = c.orientation(
        protocol,
        questions,
        preds,
        errors,
        groups,
        ids,
        [],
        {"toy": fixed_rule},
        leg_fold="A",
    )
    row = result["rules"]["toy"]
    assert row["fixed_LEG_selection"]["selected"] == ["a", "b", "c"]
    assert row["selected_gross_regret_minutes"]["status"] == "INSUFFICIENT_EVIDENCE"
    assert row["selected_gross_regret_minutes"]["unresolved_selected_outcomes"] == [
        ["b", "q2"]
    ]
    assert row["matched_real_members"] == ["a", "c", "d"]


def test_c10_actual_model_quantity_path_and_nonfinite_derived_accounting(
    tmp_path, monkeypatch
):
    inputs = object.__new__(producer.PublicInputs)
    _, inputs.contract = registered_grammar()
    inputs.public, inputs.action_of, inputs.identity = (
        tmp_path,
        {"D-toy": "a"},
        {"scope": "FIXTURE"},
    )
    (tmp_path / "data").mkdir()
    (tmp_path / "data/fixture.json.gz").write_bytes(b"fixture")
    inputs.records = {
        "m": {
            "manifest_folder": "data",
            "public_source_file": "old/fixture.json.gz",
            "compressed_sha256": "fixture",
        }
    }
    outputs = {
        k: ([0.0] * shape[0] if shape else 0.0)
        for k, shape in producer.calibration.SHAPES.items()
    }
    outputs["voltage_v"] = [4.0] * 10 + [4.2] * (len(outputs["voltage_v"]) - 10)
    inputs.readers = SimpleNamespace(predictions=lambda *args: {"D-toy": outputs})
    committed = inputs.models()
    assert committed["quantities"]["m"]["D-toy"] == producer.decision.measure(
        inputs.contract, outputs
    )
    assert committed["references_opened"] is False
    monkeypatch.setattr(
        producer.decision, "measure", lambda *args: {"objective": float("nan")}
    )
    rejected = inputs.models()
    assert rejected["quantities"] == {}
    assert rejected["invalid_or_unavailable_members"] == {
        "m": "INVALID_OR_NONFINITE_DERIVED_PREDICTIONS"
    }


def test_c09_control_missing_failed_reference_quantity_is_not_imputed(monkeypatch):
    inputs = object.__new__(producer.PublicInputs)
    inputs.protocol, _, _, _ = toy()
    inputs.contract = {}
    inputs.scenarios = {
        q["native_context_id"]: {"id": q["native_context_id"]}
        for q in inputs.protocol["questions"]
    }
    inputs.question_candidates = {
        q["question_id"]: [] for q in inputs.protocol["questions"]
    }
    inputs.action_of = {
        cid: cid for q in inputs.protocol["questions"] for cid in q["case_ids"]
    }
    quantities = {
        cid: {"marker": "FIXTURE"}
        for cid in inputs.protocol["questions"][0]["case_ids"]
    }
    calls = []

    def assessed(contract, scenario, candidates, quantities):
        calls.append(scenario["id"])
        return {"fixture": True}

    monkeypatch.setattr(producer.decision, "assess_predicted", assessed)
    result = inputs._predictions(quantities)
    assert result == {"q1": {"fixture": True}, "q2": None}
    assert calls == ["D-toy0"]


@pytest.mark.parametrize("mode", ["good", "unsafe", "abstain", "short_menu"])
def test_c13_c14_utility_exact_parity_costs_and_gross_units(mode):
    _, questions, preds, _ = questions_and_predictions()
    q = questions["q1"]
    if mode == "unsafe":
        preds["q1"]["a"]["feasible"] = False
        preds["q1"]["bad"]["feasible"] = True
    elif mode == "abstain":
        preds["q1"] = {a: {"feasible": False, "objective": None} for a in q["actions"]}
    elif mode == "short_menu":
        q["actions"].pop("bad")
        preds["q1"].pop("bad")
    direct = bank._v2_question(q, preds["q1"], cap=3, kappa=0.1, unit=120, detail=True)
    result = c.value_vectors(questions, preds, ["q1"])
    assert {k: result["utilities"]["q1"][k] for k in direct} == direct
    regret = result["regret_seconds"]["q1"]
    assert regret == pytest.approx(300 - 120 * direct["G"] - 60)
    assert regret == (240 if mode in ("unsafe", "abstain") else 0)
    assert direct["n"] == (0 if mode == "abstain" else 1)
    if mode == "unsafe":
        assert direct["U"] == -0.1 and direct["infeasible_attempts"] == 1
    selection = c.diagnostic_selection({"a": 3, "b": 2, "c": 1}, ["a", "b", "c"])
    minutes = owner_dev_v1.selected_regret_minutes(
        selection, {m: {"q1": regret} for m in ("a", "b", "c")}, ["q1"]
    )
    assert minutes["mean_regret_min"] == regret / 60


def test_c12_unresolved_attempt_withholds_entire_value_vector():
    _, questions, preds, _ = questions_and_predictions()
    questions["q2"]["actions"]["a"][0]["status"] = "UNRESOLVED"
    result = c.value_vectors(questions, preds, ["q1", "q2"])
    assert result["status"] == "UNRESOLVED_REFERENCE_VALUE_VECTOR"
    assert "regret_seconds" not in result and "losses" not in result
    assert result["utilities"]["q2"]["unresolved_attempts"] == 1


def test_c15_question_weighting_not_action_count_weighting():
    protocol, _, _, _ = toy()
    protocol["questions"][1]["case_ids"].pop()
    errors = {
        cid: (1 if q["question_id"] == "q1" else 3)
        for q in protocol["questions"]
        for cid in q["case_ids"]
    }
    means = c.question_errors(errors, protocol)
    assert means == {"q1": 1, "q2": 3}
    assert c.accuracy_score(means, ["q1", "q2"]) == pytest.approx(1 / 3)
    assert c.accuracy_score(means, ["q1"]) == 0.5


def test_c16_preflight_never_reads_models_and_existing_outputs_refused(tmp_path):
    fixture = FixtureInputs(tmp_path / "preflight")
    result = producer.preflight(fixture, fixture.out)
    assert (
        fixture.events == ["truth"] and result["prediction_coverage_checked"] is False
    )
    before = (fixture.out / "reference-preflight.json").read_bytes()
    with pytest.raises(FileExistsError):
        producer.replay(fixture, fixture.out)
    assert (fixture.out / "reference-preflight.json").read_bytes() == before
    with pytest.raises(FileExistsError):
        producer.write_new(fixture.out / "reference-preflight.json", {})


def test_c16_consumer_dependency_surface_and_isolation_guard(tmp_path):
    source = Path(producer.__file__).read_text(encoding="utf-8")
    calls = {
        ast.unparse(node.func)
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Call)
    }
    assert not any(
        name in calls
        for name in (
            "subprocess.run",
            "os.system",
            "rebuild",
            "infer",
            "solve",
            "requests.post",
            "readers.main",
        )
    )
    with pytest.raises(LabRefused, match="isolated_no_site_no_bytecode"):
        producer.main(
            [
                "replay",
                "--packet-root",
                str(tmp_path),
                "--public-dir",
                str(tmp_path),
                "--out",
                str(tmp_path / "out"),
            ]
        )


def test_c17_native_n4_skipped_question_count_and_none_objective():
    _, questions, preds, _ = questions_and_predictions()
    rules, _ = candidates.load()
    questions["q1"]["actions"].pop("bad")
    preds["q1"].pop("bad")
    n4 = c.score_side(
        "N4-TOP-REGION-RANKING",
        rules["N4-TOP-REGION-RANKING"]["rule"],
        questions,
        preds,
        ["q1", "q2"],
    )
    assert n4["status"] == "UNMEASURED_INCOMPLETE_LEG_RULE_COVERAGE"
    assert n4["required_questions"] == 2 and n4["native_coverage"]["questions"] == 1
    assert n4["skipped_questions"] == ["q1"]
    for rid in ("N2-VERIFIED-REGRET-ON-PICK", "V2r2@k3,kappa0.1"):
        assert (
            c.score_side(rid, rules[rid]["rule"], questions, preds, ["q1", "q2"])[
                "status"
            ]
            == "MEASURED_DIAGNOSTIC_PROXY"
        )
    preds["q2"]["a"] = {"feasible": False, "objective": None}
    unmeasured = c.score_side(
        "N4-TOP-REGION-RANKING",
        rules["N4-TOP-REGION-RANKING"]["rule"],
        questions,
        preds,
        ["q2"],
    )
    assert unmeasured["status"] == "UNMEASURED_NATIVE_RULE_INPUT"
    assert unmeasured["missing_predicted_objectives"] == [["q2", "a"]]
    assert (
        c.score_side(
            "N2-VERIFIED-REGRET-ON-PICK",
            rules["N2-VERIFIED-REGRET-ON-PICK"]["rule"],
            questions,
            preds,
            ["q2"],
        )["status"]
        == "MEASURED_DIAGNOSTIC_PROXY"
    )


def test_registered_accepted_bytes_and_original_owner_history_unchanged():
    assert (
        hashlib.sha256(
            (producer.REGISTRATION / producer.PROTOCOL).read_bytes()
        ).hexdigest()
        == producer.PROTOCOL_SHA
    )
    assert (
        hashlib.sha256(
            (producer.REGISTRATION / producer.BINDINGS).read_bytes()
        ).hexdigest()
        == producer.BINDINGS_SHA
    )
    registration = json.loads(owner_dev_v1.REGISTRATION.read_bytes())
    assert registration["job"]["observer_binding"]["start_soc"] == 0.1
    assert registration["job"]["observer_binding"]["target_soc"] == 0.8
    assert registration["job"]["observer_binding"]["implementation_receipt"] is None
    assert (
        registration["job"]["objective_owner_text_original_record"]
        == "minutes 0->80% SOC, no 30-min cap"
    )
    amendment = registration["prospective_amendments"][-1]
    assert (
        hashlib.sha256((producer.ROOT / amendment["path"]).read_bytes()).hexdigest()
        == amendment["sha256"]
    )
    authority = registration["authority"]
    assert (
        hashlib.sha256((producer.ROOT / authority["path"]).read_bytes()).hexdigest()
        == "1ec37ebd23f3afd5bee4832a58c65c68e3a1ea4714375f554e051814b1dbf6df"
    )
