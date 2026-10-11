"""SUBMISSION-RATE-STUDY-01 analysis (run sheet A.3), on FIXTURES only: the
registered measures give the known answer on synthetic records, refuse what they
must, and a FIXTURE report can never enter the committed evidence tree."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]


def _load(name):
    spec = importlib.util.spec_from_file_location(
        name, REPOSITORY / f"scripts/dev/rate_study/{name}.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


analyze = _load("analyze")
fixtures = _load("fixtures")


def _honest(rate):
    return 0.0


def _study(adversary):
    return fixtures.study(
        {
            "H": _honest,
            "S-sealed": adversary,
            "G-sealed": adversary,
            "S-revealed": lambda rate: 3 * adversary(rate),
        }
    )


def _write(directory, records):
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "records.jsonl").write_text(
        "\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8"
    )


def test_settings_are_batterys_registered_comparison_settings():
    from carbon.battery import exam

    assert analyze.N_BOOT == exam.DEVELOPMENT_RULE["comparison"]["n_boot"] == 4000
    assert analyze.ALPHA == exam.DEVELOPMENT_RULE["comparison"]["alpha"] == 0.05


def test_the_overfitting_index_is_fresh_minus_current_and_checked():
    record = fixtures.run_records("H", 1, 1, windows=1)[0]
    assert analyze.check_record(dict(record)) == record
    with pytest.raises(analyze.RecordRefused, match="d_index"):
        analyze.check_record(dict(record, d_index=record["d_index"] + 0.5))


@pytest.mark.parametrize(
    "mutation, message",
    [
        ({"case_id": "x"}, "outside_the_schema"),
        ({"seed": 1}, "outside_the_schema"),
        ({"arm": "Z"}, "unknown_arm"),
        ({"state": "MAYBE"}, "unknown_state"),
        ({"provenance": "REAL"}, "unknown_provenance"),
        ({"rate": 3}, "unknown_rate"),
    ],
)
def test_records_with_hidden_fields_or_bad_values_are_refused(mutation, message):
    record = dict(fixtures.run_records("H", 1, 1, windows=1)[0], **mutation)
    with pytest.raises(analyze.RecordRefused, match=message):
        analyze.check_record(record)


def test_only_scored_submissions_are_observations_and_the_rest_are_counted():
    records = fixtures.run_records("H", 1, 1, windows=2)
    records.append(dict(records[0], state="UNAVAILABLE", t=99))
    records.append(dict(records[0], state="REPEATED", t=100))
    records.append(dict(records[0], state="NOT_SCORED", t=101))
    assert len(analyze.runs_of(records, "H", 1)[1]) == 6
    assert analyze.excluded_counts(records) == {
        "UNAVAILABLE": 1,
        "WINDOW_USED": 0,
        "REPEATED": 1,
        "NOT_SCORED": 1,
    }


def test_d_at_probes_takes_the_last_scored_submission_at_or_before_p():
    run = fixtures.run_records("H", 1, 1, drift_per_probe=0.5, noise=0.0, windows=2)
    assert analyze.d_at_probes(run, 4) == pytest.approx(2.0)
    assert analyze.d_at_probes(run, 0) is None
    assert analyze.d_at_probes(run, 10**6) == pytest.approx(0.5 * 6)


def test_the_matched_final_probe_count_is_the_smallest_any_run_reached():
    groups = [
        analyze.runs_of(fixtures.run_records("H", 1, 1, windows=4), "H", 1),
        analyze.runs_of(fixtures.run_records("H", 2, 1, windows=4), "H", 2),
    ]
    assert analyze.final_probes(groups) == 12


def test_slope_recovers_the_drift_rate():
    run = fixtures.run_records("S-sealed", 2, 1, drift_per_probe=0.02, noise=0.0)
    assert analyze.slope(run) == pytest.approx(0.02)
    assert analyze.slope(run[:1]) is None


def test_bootstrap_is_deterministic_and_uses_the_registered_settings():
    values = [0.0, 0.1, -0.05, 0.02]
    a = analyze.bootstrap_mean(values, "x")
    assert a == analyze.bootstrap_mean(values, "x")
    assert a["lower"] <= a["mean"] <= a["upper"]
    assert analyze.bootstrap_mean([], "x")["mean"] is None


def test_an_honest_only_world_finds_no_rate_effect_and_every_rate_safe():
    report = analyze.study_report(_study(_honest), per_solve_cpu_s=82.0)
    assert report["provenance"] == "FIXTURE"
    assert report["noise"]["rate_effect"] is False
    assert report["safe_rate"] == 4


def test_drift_that_grows_with_rate_gives_the_known_safe_rate():
    records = _study(lambda rate: 0.0 if rate == 1 else 0.05 * rate)
    report = analyze.study_report(records, per_solve_cpu_s=82.0)
    assert report["safe_rate"] == 1
    assert report["first_distinguishable_probes_at_next_rate"] is not None
    assert report["sealed_vs_revealed"]["2"]["slope_ratio"] == pytest.approx(
        3.0, rel=0.05
    )


def test_drift_at_every_rate_means_no_safe_rate():
    report = analyze.study_report(_study(lambda rate: 0.05), per_solve_cpu_s=82.0)
    assert report["safe_rate"] is None
    if report["p_star"] is None:
        assert all(row["feasible"] is False for row in report["bank_table"]["rows"])


def test_a_missing_realistic_arm_never_yields_a_safe_rate():
    records = fixtures.study({"H": _honest, "S-revealed": lambda rate: 0.05})
    assert analyze.study_report(records, per_solve_cpu_s=82.0)["safe_rate"] is None


def test_rate_effect_in_the_honest_arm_switches_to_per_rate_values():
    records = fixtures.study({"H": lambda rate: 0.0 if rate == 1 else 0.05 * rate})
    noise = analyze.noise_band(records, 12)
    assert noise["rate_effect"] is True
    assert analyze.honest_values(noise, 4) == noise["values"]["per_rate"][4]
    assert analyze.honest_values(noise, 4) != noise["values"]["pooled"]


def test_no_observations_never_read_as_safe():
    records = fixtures.study({"H": _honest})
    noise = analyze.noise_band(records, 12)
    assert analyze.distinguishable(records, "S-sealed", 1, 12, noise) is True


def test_a_null_adversary_is_rarely_flagged_over_independent_draws():
    # Equally noisy arms with no drift, 20 independent replicate draws. The first
    # rules flagged about half (interval upper vs upper) and about 40 percent (mean
    # vs honest band) of null arms; the two-sample difference interval flags a
    # null arm only occasionally.
    flagged = 0
    for seed in range(20):
        records = fixtures.study(
            {"H": _honest, "S-sealed": _honest},
            replicates=4,
            windows=4,
            first_replicate=1 + 10 * seed,
        )
        noise = analyze.noise_band(records, 12)
        flagged += analyze.distinguishable(records, "S-sealed", 1, 12, noise)
    assert flagged <= 3


def test_a_drifting_adversary_is_flagged_in_every_draw():
    for seed in range(5):
        records = fixtures.study(
            {"H": _honest, "S-sealed": lambda rate: 0.05},
            replicates=4,
            windows=4,
            first_replicate=1 + 10 * seed,
        )
        noise = analyze.noise_band(records, 12)
        assert analyze.distinguishable(records, "S-sealed", 1, 12, noise)


def test_bank_table_prices_by_the_stated_formula():
    table = analyze.bank_table(60, (1, 2, 4), (1, 2), 82.0, 3000)
    rows = {(r["m"], r["H"]): r for r in table["rows"]}
    assert rows[(1, 1)]["E"] == 20  # floor(60 / 3)
    assert rows[(4, 2)]["E"] == 2  # floor(60 / 24)
    assert rows[(1, 1)]["solves_per_window"] == 5  # ceil(98 / 20)
    windows = 86400 / (1080 * 12)
    assert rows[(1, 1)]["solves_per_day"] == pytest.approx(windows * 98 / 20)
    assert rows[(1, 1)]["cpu_hours_per_day"] == pytest.approx(
        rows[(1, 1)]["solves_per_day"] * 82.0 / 3600
    )
    assert (
        analyze.bank_table(None, (1,), (1,), 82.0, 3000)["rows"][0]["feasible"] is False
    )
    assert analyze.bank_table(2, (4,), (1,), 82.0, 3000)["rows"][0]["feasible"] is False


def test_stage0_is_arm_h_only_and_reports_noise_and_throughput():
    records = fixtures.study({"H": _honest})
    report = analyze.stage0_report(records)
    assert report["replicates"] == {"1": 4, "2": 4, "4": 4}
    assert report["noise"]["per_rate"][1]["n"] == 4
    assert set(report["throughput"]) == {1, 2, 4}
    with pytest.raises(analyze.RecordRefused):
        analyze.stage0_report(records + fixtures.run_records("S-sealed", 1, 1))


def test_mixed_provenance_is_refused():
    records = fixtures.run_records("H", 1, 1, windows=1)
    records.append(dict(records[0], provenance="STUDY", t=500))
    with pytest.raises(analyze.RecordRefused, match="mixed"):
        analyze.provenance_of(records)


def test_cli_stage0_writes_noise_and_throughput_for_a_fixture_outside_evidence(
    tmp_path,
):
    _write(tmp_path / "records", fixtures.study({"H": _honest}, replicates=2))
    args = [
        "stage0",
        "--records",
        str(tmp_path / "records"),
        "--out",
        str(tmp_path / "out"),
    ]
    assert analyze.main(args) == 0
    noise = json.loads((tmp_path / "out/noise.json").read_text(encoding="utf-8"))
    assert noise["provenance"] == "FIXTURE"
    assert (tmp_path / "out/throughput.json").is_file()


def test_a_fixture_report_is_never_written_into_the_evidence_tree(tmp_path, capsys):
    _write(tmp_path / "records", fixtures.study({"H": _honest}, replicates=2))
    target = analyze.EVIDENCE / "stage0"
    args = ["stage0", "--records", str(tmp_path / "records"), "--out", str(target)]
    assert analyze.main(args) == 2
    assert "FIXTURE" in capsys.readouterr().out
    assert not target.exists()


def test_cli_report_refuses_empty_and_hidden_field_record_sets(tmp_path, capsys):
    (tmp_path / "records").mkdir()
    args = [
        "report",
        "--records",
        str(tmp_path / "records"),
        "--out",
        str(tmp_path / "r.json"),
        "--per-solve-cpu-s",
        "82",
    ]
    assert analyze.main(args) == 2
    bad = dict(fixtures.run_records("H", 1, 1, windows=1)[0], case_id="c1")
    _write(tmp_path / "records", [bad])
    assert analyze.main(args) == 2
    assert "outside_the_schema" in capsys.readouterr().out


def test_the_analysis_reads_no_pool_or_host_state():
    text = (REPOSITORY / "scripts/dev/rate_study/analyze.py").read_text(
        encoding="utf-8"
    )
    for token in ("private_root", "/var/lib", "producer", "deployment"):
        assert token not in text
