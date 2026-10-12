"""GRAPHITE-PROGRESS-01: the progress ledger's extraction, aggregation, idempotent append, refusals and chart.

Fixtures only: no host file, no run, no spend. A sealed source is refused; an unsourced number is UNMEASURED.
"""

from __future__ import annotations

import json
from decimal import Decimal

import pytest

from scripts.dev.graphite_progress import __main__ as cli
from scripts.dev.graphite_progress import chart, extract, improvement, ledger
from scripts.dev.graphite_progress.model import (
    LINE_SCHEMA,
    UNMEASURED,
    USD_BASIS,
    ProgressError,
)

CH = "battery-fastcharge-ageing-development-v1"


def constructor_doc(
    *,
    bundled=True,
    committed="3.00",
    statuses=(("p-a", "SCORED", "IMPROVEMENT"),),
    state="succeeded",
):
    proposals = [
        {"proposal_id": pid, "kind": "proposal", "status": status, "outcome": outcome}
        for pid, status, outcome in statuses
    ]
    proposals.append(
        {
            "proposal_id": "a-x-00",
            "kind": "ablation",
            "status": "SCORED",
            "outcome": None,
        }
    )
    return {
        "run_id": "graphite-r1",
        "provider_state": state,
        "controller_phase": "completed",
        "budget": {
            "campaigns": {
                "graphite-phase3": {"ceiling": "89.46", "committed": committed}
            }
        },
        "summary": {"proposals": proposals},
        "delivery": {"status": "BUNDLED"} if bundled else None,
        "pod_charges": {"booked_usd": "2.00"},
    }


def attacker_doc(
    *, findings=("f1",), listed=("fa", "fb", "fc"), not_run=("fb", "fc"), usd="0.30"
):
    rows = {name: {} for name in (*listed, "UNASSIGNED")}
    return {
        "coverage": {
            "attempts": 12,
            "families": {"families": rows, "not_run": list(not_run)},
            "findings": list(findings),
            "findings_by_source": {"attacker": [], "copy_probe": list(findings)},
        },
        "session": {
            "run_id": "att-1",
            "provider_state": "succeeded",
            "settled_usd": usd,
        },
    }


def crun(**kw):
    wall = kw.pop("wall", 3600)
    scores = kw.pop("practice_scores", None)
    public = kw.pop("public_improvement", None)
    return extract.constructor_run(
        constructor_doc(**kw),
        level=2,
        source="x.out",
        batch="b1",
        wall=wall,
        practice_scores=scores,
        public_improvement=public,
    )


def arun(**kw):
    return extract.attacker_run(
        attacker_doc(**kw), level=2, source="y.out", batch="b1", wall=1800
    )


def line(runs, **kw):
    base = {
        "batch_id": "b1",
        "level": 2,
        "challenge": CH,
        "date": "2026-10-12",
        "runs": runs,
        "classes": {},
        "triage": {},
        "fixes": None,
        "history": [],
    }
    base.update(kw)
    return ledger.build_line(**base)


# -- extraction ------------------------------------------------------------------------------------
def test_a_constructor_run_is_summarised_from_its_result_document():
    run = crun(
        statuses=(
            ("p-a", "SCORED", "IMPROVEMENT"),
            ("p-b", "REFUSED_UNREBUILDABLE", None),
        )
    )
    assert (
        run["bundled"]
        and run["proposals"] == 2
        and run["outcomes"] == {"IMPROVEMENT": 1}
    )
    assert run["refused"] == {"REFUSED_UNREBUILDABLE": ["p-b"]}
    assert run["booked_usd"] == "3.00" and not run["stalled"]
    assert crun(state="failed")["stalled"] is True


def test_the_wall_clock_comes_from_the_chain_log_or_is_absent():
    log = (
        "2026-10-11T03:01:11Z L2 lane E start ref abc grant X\n"
        "2026-10-11T03:21:11Z L2 lane E exit 0\n"
    )
    assert extract.wall_seconds(log, "L2") == 1200
    assert extract.wall_seconds(log, "L9") is None
    assert extract.wall_seconds("garbage", "L2") is None


def test_run_output_may_open_with_progress_text(tmp_path):
    path = tmp_path / "run.out"
    path.write_text('Research epoch 1: turn 1\n{"run_id": "r", "summary": {}}\n')
    assert extract.read_document(path)["run_id"] == "r"
    (tmp_path / "none.out").write_text("no json here")
    with pytest.raises(ProgressError, match="source_has_no_document"):
        extract.read_document(tmp_path / "none.out")


def test_an_attacker_run_reports_families_findings_and_cost():
    run = arun()
    assert run["families_listed"] == 3 and run["families_attempted"] == 1
    assert run["findings"] == ["f1"] and run["findings_by_source"] == {
        "attacker": 0,
        "copy_probe": 1,
    }
    assert run["booked_usd"] == "0.30"


# -- aggregation -------------------------------------------------------------------------------------
def test_cost_per_bundled_run_states_its_basis_and_sample_size():
    runs = [crun(committed="3.00"), crun(committed="5.00", bundled=False)]
    block = line(runs)["constructor"]
    assert block["bundled_share"]["value"] == 0.5 and block["bundled_share"]["n"] == 2
    cost = block["usd_per_bundled"]
    assert cost["value"] == "8.00" and cost["n"] == 1 and cost["source"] == USD_BASIS
    assert block["booked_usd"] == "8.00"


def test_no_bundled_run_means_the_cost_per_bundled_is_unmeasured_not_zero():
    block = line([crun(bundled=False)])["constructor"]
    assert block["usd_per_bundled"]["value"] == UNMEASURED
    assert block["wall_hours_per_bundled"]["value"] == UNMEASURED


def test_improvement_is_unmeasured_without_a_public_score_and_measured_with_one():
    block = line([crun()])["constructor"]["improvement"]
    assert (
        block["best"]["value"] == UNMEASURED and block["median"]["value"] == UNMEASURED
    )
    assert block["proposals_with_outcome_IMPROVEMENT"]["value"] == 1
    with_scores = line([crun(practice_scores=[0.02, 0.05, 0.03])])["constructor"][
        "improvement"
    ]
    assert (
        with_scores["best"]["value"] == 0.05 and with_scores["median"]["value"] == 0.03
    )
    assert with_scores["best"]["n"] == 3


def test_refusals_are_classed_and_the_unclassified_stay_visible():
    run = crun(
        statuses=(
            ("p-1", "REFUSED_UNREBUILDABLE", None),
            ("p-2", "REFUSED_UNREBUILDABLE", None),
            ("p-3", "FAILED_INFRA", None),
            ("p-4", "SCORED", "IMPROVEMENT"),
        )
    )
    block = line(
        [run], classes={"L2:p-1": "envelope_too_tight", "L0:p-2": "brief_gap"}
    )["constructor"]
    assert block["refusals"]["by_class"] == {
        "brief_gap": 0,
        "envelope_too_tight": 1,
        "correct_block": 0,
        "infra": 1,
        "UNCLASSIFIED": 1,
    }
    assert block["refusals"]["rate"]["value"] == 0.75
    assert block["waste"]["failed_infra"] == 1 and block["waste"]["refused"] == 3


def test_real_findings_need_triage_and_are_otherwise_unmeasured():
    runs = [arun(findings=("f1",))]
    assert line(runs)["attacker"]["real_findings_per_run"]["value"] == UNMEASURED
    triaged = line(runs, triage={"f1": "ORACLE_GAP"})["attacker"]
    assert triaged["real_findings_per_run"]["value"] == 0.0
    assert triaged["triage"] == {"REAL_ESCAPE": 0, "ORACLE_GAP": 1, "FALSE_POSITIVE": 0}
    real = line(runs, triage={"f1": "REAL_ESCAPE"})["attacker"]
    assert real["real_findings_per_run"]["value"] == 1.0
    assert real["usd_per_real_finding"]["value"] == "0.30"


def test_the_share_of_findings_that_led_to_a_fix_needs_a_record():
    runs = [arun(findings=("f1",))]
    assert (
        line(runs, triage={"f1": "ORACLE_GAP"})["attacker"]["findings_led_to_fix"][
            "value"
        ]
        == UNMEASURED
    )
    fixed = line(runs, triage={"f1": "ORACLE_GAP"}, fixes={"f1": "PR 1184"})["attacker"]
    assert (
        fixed["findings_led_to_fix"]["value"] == 1.0
        and fixed["findings_led_to_fix"]["n"] == 1
    )


def test_family_coverage_is_listed_against_attempted():
    block = line([arun()])["attacker"]["families"]
    assert block["listed"] == 3 and block["attempted"] == 1
    assert block["share_attempted"]["value"] == round(1 / 3, 4)


def test_the_gate_burn_down_comes_from_the_readiness_history():
    history = [
        {
            "challenge": CH,
            "level": 2,
            "utc": "2026-10-09T10:00:00Z",
            "counts": {"NOT_BUILT": 22, "FAIL": 3},
        },
        {
            "challenge": CH,
            "level": 2,
            "utc": "2026-10-12T10:00:00Z",
            "counts": {"NOT_BUILT": 18, "FAIL": 4},
            "launch_ready": False,
        },
        {
            "challenge": CH,
            "level": 2,
            "utc": "2026-10-12T11:00:00Z",
            "counts": {"NOT_BUILT": 0},
            "partial": True,
        },
        {
            "challenge": CH,
            "level": 1,
            "utc": "2026-10-12T10:00:00Z",
            "counts": {"NOT_BUILT": 0},
        },
    ]
    gate = line([crun()], history=history)["gate"]
    assert (
        gate["runs"] == 2
        and gate["first"]["NOT_BUILT"] == 22
        and gate["last"]["NOT_BUILT"] == 18
    )
    assert line([crun()])["gate"]["value"] == UNMEASURED


# -- the ledger ----------------------------------------------------------------------------------------
def test_append_is_idempotent_per_batch_and_level_and_refuses_a_changed_line(tmp_path):
    path = tmp_path / "progress.jsonl"
    first = line([crun()])
    assert ledger.append_line(path, first) == "appended"
    assert ledger.append_line(path, first) == "unchanged"
    assert len(path.read_text().splitlines()) == 1
    with pytest.raises(ProgressError, match="batch_exists_with_different_content"):
        ledger.append_line(path, line([crun(committed="9.00")]))
    other_level = line([crun()], level=3)
    assert ledger.append_line(path, other_level) == "appended"
    assert [l["schema"] for l in ledger.read_ledger(path)] == [LINE_SCHEMA, LINE_SCHEMA]


def test_a_corrupt_ledger_is_refused(tmp_path):
    path = tmp_path / "progress.jsonl"
    path.write_text("not json\n")
    with pytest.raises(ProgressError, match="ledger_corrupt"):
        ledger.read_ledger(path)
    path.write_text(json.dumps({"schema": "other"}) + "\n")
    with pytest.raises(ProgressError, match="another schema"):
        ledger.read_ledger(path)


@pytest.mark.parametrize(
    "name", ["sealed-batch.out", "hidden.json", "private/run.out", "answer-key.json"]
)
def test_a_sealed_or_private_source_is_refused(tmp_path, name):
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{"a": 1}')
    with pytest.raises(ProgressError, match="sealed_source_refused"):
        extract.read_document(path)
    with pytest.raises(ProgressError, match="sealed_source_refused"):
        ledger.append_line(path, line([crun()]))


# -- the chart and the trend ---------------------------------------------------------------------------
def test_the_chart_is_deterministic_shows_n_and_leaves_unmeasured_as_a_gap(tmp_path):
    path = tmp_path / "progress.jsonl"
    ledger.append_line(
        path, line([crun(), crun(bundled=False)], batch_id="b1", date="2026-10-11")
    )
    ledger.append_line(path, line([crun()], batch_id="b2", date="2026-10-12"))
    lines = ledger.read_ledger(path)
    svg = chart.render_svg(lines)
    assert svg == chart.render_svg(lines)
    assert "n=2" in svg and "n=1" in svg and "UNMEASURED" in svg
    assert svg.startswith("<svg") and svg.rstrip().endswith("</svg>")


def test_the_trend_lines_state_direction_with_n_and_say_unmeasured(tmp_path):
    path = tmp_path / "progress.jsonl"
    ledger.append_line(
        path, line([crun(), crun(bundled=False)], batch_id="b1", date="2026-10-11")
    )
    ledger.append_line(path, line([crun()], batch_id="b2", date="2026-10-12"))
    text = "\n".join(cli.trend_lines(ledger.read_ledger(path)))
    assert "L2 bundled share: 0.5 (n=2) -> 1.0 (n=1), up, 2 points" in text
    assert "L2 real findings per attacker run: UNMEASURED" in text


def test_a_batch_runs_end_to_end_from_a_manifest(tmp_path, capsys):
    root = tmp_path / "runs"
    root.mkdir()
    (root / "c.out").write_text(json.dumps(constructor_doc()))
    (root / "a.out").write_text(json.dumps(attacker_doc()))
    (root / "chain.log").write_text(
        "2026-10-11T03:00:00Z L2-E start x\n2026-10-11T03:30:00Z L2-E exit 0\n"
    )
    manifest = {
        "batch": "stage-test",
        "challenge": CH,
        "date": "2026-10-12",
        "runs": [
            {
                "file": "c.out",
                "role": "constructor",
                "level": 2,
                "chain_log": "chain.log",
                "chain_label": "L2-E",
            },
            {"file": "a.out", "role": "attacker", "level": 2},
        ],
        "refusal_classes": {},
        "triage": {"f1": "ORACLE_GAP"},
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest))
    out = tmp_path / "ledger" / "progress.jsonl"
    svg = tmp_path / "ledger" / "progress.svg"
    args = [
        "batch",
        "--manifest",
        str(manifest_path),
        "--root",
        str(root),
        "--ledger",
        str(out),
        "--chart",
        str(svg),
    ]
    assert cli.main(args) == 0
    assert json.loads(capsys.readouterr().out)["levels"] == {"L2": "appended"}
    assert cli.main(args) == 0  # idempotent
    assert json.loads(capsys.readouterr().out)["levels"] == {"L2": "unchanged"}
    [written] = ledger.read_ledger(out)
    assert written["constructor"]["agent_hours"]["value"] == 0.5
    assert written["attacker"]["real_findings_per_run"]["value"] == 0.0
    assert svg.read_text().startswith("<svg")
    sealed = tmp_path / "x"
    assert (
        cli.main(
            [
                "batch",
                "--manifest",
                str(manifest_path),
                "--root",
                str(root),
                "--ledger",
                str(sealed / "hidden.jsonl"),
            ]
        )
        == 2
    )


def test_the_usd_basis_is_stated_and_no_account_data_is_in_a_line():
    text = json.dumps(line([crun(), arun()]))
    assert "reservation" in text and "model charge" in text
    for forbidden in ("account", "balance", "api_key", "credential"):
        assert forbidden not in text.lower()
    assert Decimal(line([crun()])["constructor"]["booked_usd"]) == Decimal("3.00")


def test_an_excluded_source_is_named_in_the_line_with_its_reason():
    excluded = [
        {"file": "early.out", "level": None, "reason": "level not recorded"},
        {"file": "other.out", "level": 3, "reason": "not for this level"},
    ]
    shown = line([crun()], excluded=excluded)["excluded_sources"]
    assert [e["file"] for e in shown] == ["early.out"]
    assert line([crun()])["excluded_sources"] == []


def test_a_partial_session_duration_says_how_many_runs_have_one():
    runs = [crun(wall=3600), crun(wall=None)]
    block = line(runs)["constructor"]
    assert block["agent_hours"]["value"] == 1.0 and block["agent_hours"]["n"] == 1
    assert "1 of 2 runs" in block["agent_hours"]["source"]


# -- public-development improvement (the executor's records) -----------------------------------------
PUBLIC_SHA = "sha256:" + "ab" * 32


@pytest.fixture(autouse=True)
def contract(tmp_path, monkeypatch):
    """A stand-in for the committed contract's literal digest (the contract is #1188's file)."""
    path = tmp_path / "contract.json"
    path.write_text(json.dumps({"public_reference_sha256": PUBLIC_SHA}))
    monkeypatch.setattr(improvement, "CONTRACT", path)
    return path


def pub(baseline_dec, model_dec, baseline_acc=0.10, model_acc=0.08):
    return {
        "schema": improvement.IMPROVEMENT_SCHEMA,
        "public_only": True,
        "panel": {
            "scoring_set": {
                "function": improvement.PUBLIC_EV4_FUNCTION,
                "sha256": PUBLIC_SHA,
                "cases": 12,
            }
        },
        "baseline": {"accuracy_error": baseline_acc, "decision_loss": baseline_dec},
        "model": {"accuracy_error": model_acc, "decision_loss": model_dec},
    }


def test_the_relative_improvement_is_positive_when_the_model_is_better():
    assert improvement.relative(10.0, 8.0) == pytest.approx(0.2)
    assert improvement.relative(10.0, 12.0) == pytest.approx(-0.2)
    assert (
        improvement.relative(0, 1.0) is None and improvement.relative(None, 1.0) is None
    )


def test_the_bootstrap_is_deterministic_and_brackets_the_median():
    values = [0.02, 0.05, 0.03, 0.08, 0.01, 0.04]
    first = improvement.bootstrap_interval(values)
    assert first == improvement.bootstrap_interval(values)
    assert first[0] <= 0.035 <= first[1]
    assert improvement.bootstrap_interval([0.1]) is None


def test_public_dev_improvement_is_median_best_interval_and_n_with_a_small_n_flag():
    records = [pub(10.0, 9.0), pub(10.0, 8.0), pub(10.0, 7.0)]
    block = line([crun(public_improvement=r) for r in records])["constructor"][
        "improvement"
    ]["public_dev"]
    decision = block["decision_loss"]
    assert decision["value"] == pytest.approx(0.2) and decision[
        "best"
    ] == pytest.approx(0.3)
    assert (
        decision["n"] == 3
        and decision["small_n"] is True
        and len(decision["ci95"]) == 2
    )
    assert (
        "PUBLIC-DEV-MEASURED" in decision["source"]
        and "not a qualification" in decision["source"]
    )
    assert block["accuracy_error"]["value"] == pytest.approx(0.2)


def test_without_an_executor_record_the_public_improvement_is_unmeasured():
    assert (
        line([crun()])["constructor"]["improvement"]["public_dev"]["value"]
        == UNMEASURED
    )


@pytest.mark.parametrize(
    "damage",
    [
        {"schema": "other"},
        {"public_only": False},
        {"baseline": None},
        {"model": {"decision_loss": -1}},
    ],
)
def test_a_record_that_is_not_public_only_or_is_malformed_is_refused(damage):
    with pytest.raises(ProgressError):
        improvement.validate({**pub(10.0, 9.0), **damage})


def test_a_record_file_with_a_sealed_name_is_refused(tmp_path):
    path = tmp_path / "sealed-improvement.json"
    path.write_text(json.dumps(pub(10.0, 9.0)))
    with pytest.raises(ProgressError, match="sealed_source_refused"):
        extract.read_document(path)


@pytest.mark.parametrize(
    "panel",
    [
        None,
        {},
        {
            "scoring_set": {
                "function": "scoring_set",
                "sha256": PUBLIC_SHA,
            }
        },
        {
            "scoring_set": {
                "function": improvement.PUBLIC_EV4_FUNCTION,
                "sha256": "sha256:" + "0" * 64,
            }
        },
        {"scoring_set": {"function": improvement.PUBLIC_EV4_FUNCTION}},
    ],
)
def test_a_record_not_on_the_public_ev4_scoring_set_digest_is_refused(panel):
    record = pub(10.0, 9.0)
    if panel is None:
        del record["panel"]
    else:
        record["panel"] = panel
    with pytest.raises(ProgressError, match="scoring_set_not_public_ev4"):
        improvement.validate(record)


def test_a_record_that_names_a_private_role_source_is_refused():
    record = pub(10.0, 9.0)
    record["note"] = (
        "docs/development/evidence/exam-design-2026-09-24/refs-b/out/battery_refs/records.jsonl"
    )
    with pytest.raises(ProgressError, match="names_a_private_source"):
        improvement.validate(record)


def test_the_digest_is_read_from_the_committed_contract_not_a_constant(contract):
    assert improvement.committed_reference_sha() == PUBLIC_SHA
    contract.write_text(json.dumps({"public_reference_sha256": "sha256:" + "cd" * 32}))
    with pytest.raises(ProgressError, match="scoring_set_not_public_ev4"):
        improvement.validate(pub(10.0, 9.0))  # the record carries the old digest


@pytest.mark.parametrize(
    "content",
    [None, "{not json", "{}", json.dumps({"public_reference_sha256": "abc"})],
)
def test_a_missing_or_digestless_contract_refuses_every_record(contract, content):
    if content is None:
        contract.unlink()
    else:
        contract.write_text(content)
    with pytest.raises(ProgressError, match="contract"):
        improvement.validate(pub(10.0, 9.0))


# -- noisy decision loss ---------------------------------------------------------------------------------
def with_mask(record, mask, run):
    return {**record, "questions": {"common_mask": mask}, "run_id": run}


def test_decision_loss_with_differing_masks_is_measured_but_noisy_and_not_a_claim():
    records = [
        with_mask(pub(10.0, 9.0), 9, "r1"),
        with_mask(pub(10.0, 8.0), 8, "r2"),
        with_mask(pub(10.0, 7.0), 8, "r3"),
    ]
    block = line([crun(public_improvement=r) for r in records])["constructor"][
        "improvement"
    ]["public_dev"]
    decision = block["decision_loss"]
    assert decision["value"] == improvement.NOISY
    assert (
        "masks differ" in decision["reading"]
        and "NOT an improvement claim" in decision["reading"]
    )
    assert [p["common_mask"] for p in decision["per_run"]] == [9, 8, 8]
    assert decision["per_run"][0]["run"] == "r1" and decision[
        "median_if_read"
    ] == pytest.approx(0.2)
    # the accuracy column is unaffected and numeric
    assert block["accuracy_error"]["value"] == pytest.approx(0.2)


def test_runs_that_disagree_in_sign_are_noisy_even_on_one_mask():
    records = [with_mask(pub(10.0, 9.0), 9, "r1"), with_mask(pub(10.0, 12.0), 9, "r2")]
    decision = line([crun(public_improvement=r) for r in records])["constructor"][
        "improvement"
    ]["public_dev"]["decision_loss"]
    assert (
        decision["value"] == improvement.NOISY
        and "disagree in sign" in decision["reading"]
    )


def test_a_consistent_decision_loss_is_a_number():
    records = [with_mask(pub(10.0, 9.0), 9, "r1"), with_mask(pub(10.0, 8.0), 9, "r2")]
    decision = line([crun(public_improvement=r) for r in records])["constructor"][
        "improvement"
    ]["public_dev"]["decision_loss"]
    assert decision["value"] == pytest.approx(0.15) and "reading" not in decision


def test_the_chart_leaves_a_noisy_column_as_a_gap():
    records = [with_mask(pub(10.0, 9.0), 9, "r1"), with_mask(pub(10.0, 8.0), 8, "r2")]
    svg = chart.render_svg([line([crun(public_improvement=r) for r in records])])
    assert "UNMEASURED" in svg  # the decision-loss panel has no plottable point


def test_five_runs_still_carry_the_small_n_flag():
    records = [with_mask(pub(10.0, 9.0 - i / 10), 9, f"r{i}") for i in range(5)]
    block = line([crun(public_improvement=r) for r in records])["constructor"][
        "improvement"
    ]["public_dev"]["accuracy_error"]
    assert block["n"] == 5 and block["small_n"] is True


# -- Level 1 records -----------------------------------------------------------------------------------
def level_record(level=1, **kw):
    record = {**pub(None, None, 0.0997, 0.0722), "level": level, "run_id": "r1"}
    record["questions"] = {
        "decision_loss_null_reason": "bundle is not a registered member of the panel"
    }
    record["model"]["rebuild"] = "rebuilt through level_compile.base_for"
    return {**record, **kw}


def test_two_runs_have_no_interval_and_say_so_instead_of_a_fabricated_one():
    records = [level_record(), level_record(run_id="r2")]
    records[1]["model"] = {**records[1]["model"], "accuracy_error": 0.0651}
    block = improvement.public_dev_block(records)["accuracy_error"]
    assert block["n"] == 2 and block["small_n"] is True and block["ci95"] is None
    assert block["ci95_note"] == "interval not meaningful at n=2"
    assert block["best"] > block["value"] > 0.2
    assert improvement.bootstrap_interval([0.1, 0.2]) is None
    assert len(improvement.bootstrap_interval([0.1, 0.2, 0.3])) == 2


def test_a_level_above_zero_record_carries_the_missing_panel_guard_caveat():
    block = improvement.public_dev_block([level_record()])["accuracy_error"]
    assert block["caveats"] == [improvement.LEVEL_REBUILD_CAVEAT]
    assert "WITHOUT its registered-panel guard" in block["caveats"][0]
    level_zero = improvement.public_dev_block([level_record(level=0)])["accuracy_error"]
    assert "caveats" not in level_zero


def test_a_null_decision_loss_keeps_the_executors_reason():
    block = improvement.public_dev_block([level_record()])["decision_loss"]
    assert block["value"] == UNMEASURED
    assert "not a registered member" in block["source"]


def test_levels_two_to_four_say_they_need_the_panel_member_registration():
    for level in (2, 3, 4):
        block = improvement.public_dev_block([], level)
        assert block["value"] == UNMEASURED and "Test Engineer" in block["source"]
    assert "Test Engineer" not in improvement.public_dev_block([], 1)["source"]
    assert "Test Engineer" not in improvement.public_dev_block([])["source"]


def test_a_record_for_a_different_level_than_its_manifest_run_is_refused(tmp_path):
    (tmp_path / "c.out").write_text(json.dumps(constructor_doc()))
    (tmp_path / "rec.json").write_text(json.dumps(level_record(level=1)))
    manifest = {
        "batch": "m",
        "runs": [
            {
                "file": "c.out",
                "role": "constructor",
                "level": 2,
                "public_improvement_file": "rec.json",
            }
        ],
    }
    with pytest.raises(ProgressError, match="public_improvement_level_mismatch"):
        cli.load_runs(manifest, tmp_path)


# -- Levels 2 to 4 -------------------------------------------------------------------------------------
def test_three_runs_get_an_interval_flagged_coarse_and_five_do_not():
    three = [level_record(level=2, run_id=f"r{i}") for i in range(3)]
    for i, record in enumerate(three):
        record["model"] = {**record["model"], "accuracy_error": 0.08 - i / 100}
    block = improvement.public_dev_block(three)["accuracy_error"]
    assert block["n"] == 3 and block["small_n"] is True and len(block["ci95"]) == 2
    assert block["ci95_note"].startswith("coarse at n=3")
    five = [level_record(level=2, run_id=f"r{i}") for i in range(5)]
    for i, record in enumerate(five):
        record["model"] = {**record["model"], "accuracy_error": 0.08 - i / 100}
    assert "ci95_note" not in improvement.public_dev_block(five)["accuracy_error"]


def test_a_level_four_line_is_labelled_base_recipe_only_on_the_line_and_the_column():
    record = level_record(level=4)
    block = improvement.public_dev_block([record])["accuracy_error"]
    assert improvement.L4_BASE_RECIPE_CAVEAT in block["caveats"]
    assert "NOT graph lowering" in improvement.L4_BASE_RECIPE_CAVEAT
    made = line([crun(public_improvement=record)], level=2)
    assert "caveats" in made and improvement.L4_BASE_RECIPE_CAVEAT in made["caveats"]
    lower = line([crun(public_improvement=level_record(level=2))], level=2)
    assert improvement.L4_BASE_RECIPE_CAVEAT not in lower["caveats"]
    assert "caveats" not in line([crun(public_improvement=level_record(level=0))])
