"""GRAPHITE-PROGRESS-01: the progress ledger's extraction, aggregation, idempotent append, refusals and chart.

Fixtures only: no host file, no run, no spend. A sealed source is refused; an unsourced number is UNMEASURED.
"""

from __future__ import annotations

import json
from decimal import Decimal

import pytest

from scripts.dev.graphite_progress import __main__ as cli
from scripts.dev.graphite_progress import chart, extract, ledger
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
    return extract.constructor_run(
        constructor_doc(**kw),
        level=2,
        source="x.out",
        batch="b1",
        wall=wall,
        practice_scores=scores,
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
