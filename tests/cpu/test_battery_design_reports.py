"""Synthetic producer-format Q3 report tests; no sealed material or solver."""

import json

import pytest

from carbon.battery import quiz_stratum as qs
from carbon.battery.value import decision as bd
from carbon.battery.value import quiz as bq
from carbon.challenge_validator import tuning
from carbon.design_search import battery_q3_v8 as reports
from carbon.design_search import tasks
from carbon.design_search.__main__ import main as cli_main

LAW = "carbon/battery/value/laws/battery-q3-v8.question-law.v1.json"


def _private(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")
    path.chmod(0o600)


def _fixture(tmp_path):
    work = tmp_path / "q3"
    work.mkdir(mode=0o700)
    work.chmod(0o700)
    contract = qs.contract(reports.Path(__file__).resolve().parents[2])
    draws = []
    records = []
    for i in range(12):
        entry = {
            "scenario_id": f"synthetic-q3-{i:02d}",
            "condition": [10.0 + i, 0.10 + 0.01 * i],
            "attempt": i,
        }
        draws.append(entry)
        fastest = bq.q3_candidates()[i % 13]["id"]
        for candidate, job in zip(
            bq.q3_candidates(), bq.q3_grid(contract, qs.scenario(entry))
        ):
            outputs = {
                "voltage_v": [
                    3.9,
                    4.5 if candidate["id"] == fastest else 4.2,
                    4.5,
                    4.5,
                ],
                "temperature_c": [40.0, 40.0, 40.0, 40.0],
                "plating_margin_v": -0.01 if i < 2 else 0.01,
            }
            records.append(
                {
                    "case_id": job["case_id"],
                    "status": "OK",
                    "inputs": {k: job[k] for k in ("c1", "c2", "t_amb_c", "soc0")},
                    "outputs": outputs,
                }
            )
    _private(
        work / "draws.json",
        {
            "schema": tuning.QUIZ_DRAWS_SCHEMA,
            "role": "synthetic-role",
            "round": 1,
            "q2": [],
            "q3": draws,
        },
    )
    with (work / "records.jsonl").open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record) + "\n")
    (work / "records.jsonl").chmod(0o600)
    standard = qs.solved(records)
    points = qs.refine_points(contract, draws, standard)
    assert not qs.refine_jobs(points)
    chosen, redraws = qs.q3_select(contract, draws, standard)
    assert len(chosen) == 8
    document = qs.document(
        "synthetic-role",
        1,
        [],
        qs.with_refine(contract, chosen, points, {}, standard),
        redraws,
    )
    _private(work / "quiz.json", document)
    journal = tmp_path / "journal.jsonl"
    qs.seeds.SeedJournal(journal)._append(qs.public_entry(document))
    return work, journal


def test_battery_v8_reports_are_aggregate_and_conditional(tmp_path):
    work, journal = _fixture(tmp_path)
    bank = reports.load_bank(work, journal, LAW)
    assert len(bank["cases"]) == 12
    assert sum(case["kept"] for case in bank["cases"]) == 8
    assert all(
        case["task"]["identity"]["query_budget"] == 117 for case in bank["cases"]
    )
    diversity = reports.diversity_report(
        bank, seed=11, replicates=40, interval_level=0.9
    )
    assert diversity == reports.diversity_report(
        bank, seed=11, replicates=40, interval_level=0.9
    )
    assert diversity["exact_sealed_batch"]["kept"]["count"] == 8
    assert diversity["observed_draw_pool"]["not_kept"]["count"] == 4
    assert diversity["job_identity"] == "battery-q3-v8"
    assert 0 < diversity["empirical_future_batch"]["completion_rate"] <= 1
    power = reports.power_report(
        bank,
        seed=11,
        replicates=20,
        interval_level=0.9,
        alpha=0.1,
        power_target=0.8,
        severities={"edge": 0.02, "caution": 0.02, "sign": 0.02, "path": 0.02},
    )
    assert power["job_identity"] == "battery-q3-v8"
    assert len(power["exact_sealed_batch"]["kept"]) == 4
    specs = reports._control_set(
        {"edge": 0.02, "caution": 0.02, "sign": 0.02, "path": 0.02}
    )
    native = [reports._run_case(case, specs) for case in bank["cases"] if case["kept"]]
    v8 = bq.q3_measures(
        [row["controls"][0] for row in native], bank["cases"][0]["contract"]
    )
    edge = power["exact_sealed_batch"]["kept"][0]["metrics"]
    assert edge["false_feasible"]["control"] == v8["false_feasible"]
    assert edge["regret"]["control"] == pytest.approx(v8["regret"])
    assert edge["abstention"]["control"] == v8["over_caution"]
    # An exhaustive optimizer queries the entire registered lattice. A
    # path-aware control is therefore indistinguishable on this path.
    assert (
        power["exact_sealed_batch"]["kept"][3]["metrics"]["false_feasible"][
            "separation"
        ]
        == 0
    )
    for result in (diversity, power):
        public = json.dumps(result)
        for forbidden in ("synthetic-q3", "c1=", "voltage_v", "t_amb_c", "soc0"):
            assert forbidden not in public


def test_battery_adapter_requires_matching_seal_and_no_write(tmp_path):
    work, journal = _fixture(tmp_path)
    with pytest.raises(tasks.TaskError):
        reports.load_bank(
            work,
            journal,
            "docs/development/challenge_pipeline/question-laws/proposals.json",
        )
    changed_law = json.loads(reports.Path(LAW).read_text(encoding="utf-8"))
    changed_law["draw"]["soc0"][0] = 0.10
    changed_law["registration_digest"] = tasks.digest(
        {k: v for k, v in changed_law.items() if k != "registration_digest"}
    )
    changed_path = tmp_path / "changed-law.json"
    _private(changed_path, changed_law)
    with pytest.raises(tasks.TaskError):
        reports.load_bank(work, journal, changed_path)
    before = sorted(str(path) for path in work.rglob("*"))
    reports.load_bank(work, journal, LAW)
    assert before == sorted(str(path) for path in work.rglob("*"))
    document = json.loads((work / "quiz.json").read_text(encoding="utf-8"))
    document["panel_version"] += 1
    _private(work / "quiz.json", document)
    with pytest.raises(tasks.TaskError):
        reports.load_bank(work, journal, LAW)


def test_battery_cli_reads_sealed_fixture(tmp_path, capsys):
    work, journal = _fixture(tmp_path)
    common = [
        "--battery-work",
        str(work),
        "--journal",
        str(journal),
        "--law",
        LAW,
        "--bootstrap-seed",
        "11",
        "--replicates",
        "10",
        "--interval-level",
        "0.9",
    ]
    cli_main(["diversity-report", *common])
    assert json.loads(capsys.readouterr().out)["job_identity"] == "battery-q3-v8"
    cli_main(
        [
            "power-report",
            *common,
            "--alpha",
            "0.1",
            "--power-target",
            "0.8",
            "--severity-edge",
            "0.02",
            "--severity-caution",
            "0.02",
            "--severity-sign",
            "0.02",
            "--severity-path",
            "0.02",
        ]
    )
    assert json.loads(capsys.readouterr().out)["report"] == "power"


def test_ev_buyer_job_shape_is_fixture_only():
    """Five-condition EV shape is runnable only with its own future bank."""
    grammar = {
        "schema": tasks.GRAMMAR_SCHEMA,
        "version": "synthetic-ev-fixture",
        "variables": [{"name": "protocol", "type": "enum", "values": ["a", "b"]}],
        "rules": [],
    }
    fixture = tasks.task(
        "synthetic-ev-buyer-job",
        identity={
            "challenge": "synthetic-fixture-only",
            "contract_version": "fixture",
            "action_grammar": grammar,
            "optimizer": {"class": "exhaustive", "version": "v1"},
            "query_budget": 10,
            "seed": 0,
            "observer_version": "fixture",
            "reference_bank": "fixture-only",
        },
        conditions=[{"id": f"c{i}", "stratum": "fixture"} for i in range(5)],
        strata={"fixture": {"p": 1, "q": 1, "w": 1}},
        candidates=["a", "b"],
        actions={"a": {"protocol": "a"}, "b": {"protocol": "b"}},
        objective={
            "quantity": "time",
            "unit": "s",
            "sense": "min",
            "aggregate": "worst",
        },
        limits=[{"quantity": "capacity", "unit": "fraction", "op": ">=", "value": 0.9}],
    )
    assert fixture["schema"] == tasks.RUNNABLE_SCHEMA


def test_v8_reach_projection_preserves_undefined_and_band_edge():
    contract = qs.contract(reports.Path(__file__).resolve().parents[2])
    base = {"temperature_c": [40.0] * 121, "plating_margin_v": 0.01}
    records = [
        {"status": "OK", "outputs": {**base, "voltage_v": [4.0] * 121}},
        {"status": "OK", "outputs": {**base, "voltage_v": [4.1899] * 120 + [4.19]}},
    ]
    assert reports._projection(contract, records[0])["reach_class"] == -1
    assert reports._projection(contract, records[1])["reach_class"] == 0
    assert (
        bd.check(
            contract,
            bd.measure(contract, records[0]["outputs"]),
            contract["reference"]["uncertainty"]["bands"],
        )["reach_cv_in_window"]
        == bd.FAIL
    )
    assert (
        bd.check(
            contract,
            bd.measure(contract, records[1]["outputs"]),
            contract["reference"]["uncertainty"]["bands"],
        )["reach_cv_in_window"]
        == bd.UNRESOLVED
    )
