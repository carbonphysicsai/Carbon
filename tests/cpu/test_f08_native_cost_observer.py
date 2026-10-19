"""Native f08 reporting uses case metrics without changing frozen science."""

from __future__ import annotations

import copy
import hashlib
import json

import pytest

from scripts.dev.reference_packages.calculix import f08_near_feasible as pilot

MIB = 2**20


def _observe(tmp_path, monkeypatch, row):
    bulk = tmp_path / "bulk"
    case_dir = bulk / "cases" / "f08" / "pilot-0000" / "work"
    case_dir.mkdir(parents=True)
    # The frozen command can leave these pod-wide totals in a native case.
    (case_dir / "cgroup.txt").write_text(
        "/sys/fs/cgroup/cpu.stat:usage_usec 900000000000000\n"
        "/sys/fs/cgroup/memory.peak:1099511627776\n"
    )
    ledger = bulk / "ledger.jsonl"
    rows = [
        {"event": "STARTED", "family": "f08", "case": "pilot-0000"},
        {"family": "f08", "case": "pilot-0000", **row},
    ]
    ledger.write_text("".join(json.dumps(r) + "\n" for r in rows))
    legacy_cost = pilot.freeze_mod._cost(case_dir, {"pilot-0000": row}, "pilot-0000")
    original = {
        "cases": {
            "pilot-0000": {
                "status": "REFERENCE_DIAGNOSTIC",
                "native_science_marker": {"unchanged": True},
                "cost": legacy_cost,
            }
        }
    }
    monkeypatch.setattr(
        pilot.freeze_mod, "observe_all", lambda *_args: copy.deepcopy(original)
    )
    monkeypatch.setattr(pilot.freeze_mod, "_case_dirs", lambda _bulk: {})
    output = tmp_path / "observed.json"
    observed = pilot.observe(bulk, output)
    assert json.loads(output.read_text()) == observed
    case = observed["cases"]["pilot-0000"]
    actual_row = rows[-1]
    if (
        actual_row.get("executor") == "native"
        and actual_row.get("family") == "f08"
        and actual_row.get("outcome") != "COMPLETED"
    ):
        assert case["status"] == "EXECUTION_FAILED"
        assert "native_science_marker" not in case
    else:
        assert case["status"] == "REFERENCE_DIAGNOSTIC"
        assert case["native_science_marker"] == {"unchanged": True}
    return observed["cases"]["pilot-0000"]["cost"], legacy_cost, ledger


@pytest.mark.parametrize("rss,sampled,expected_mib", [(64, 96, 96), (128, 64, 128)])
def test_native_cost_uses_case_cpu_and_larger_native_memory(
    tmp_path, monkeypatch, rss, sampled, expected_mib
):
    row = {
        "event": "FINISHED",
        "executor": "native",
        "outcome": "COMPLETED",
        "wall_s": 18.5,
        "host_profile": "synthetic-native",
        "rusage_cpu_s": 12.75,
        "rusage_maxrss_bytes": rss * MIB,
        "sampled_group_rss_peak_bytes": sampled * MIB,
    }
    cost, legacy, ledger = _observe(tmp_path, monkeypatch, row)
    assert legacy["cgroup_cpu_s"] == 900000000
    assert legacy["cgroup_memory_peak_mib"] == 1048576
    assert cost["cpu_s"] == cost["rusage_cpu_s"] == 12.75
    assert cost["memory_peak_mib"] == expected_mib
    assert cost["cgroup_cpu_s"] is None
    assert cost["cgroup_memory_peak_mib"] is None
    assert cost["wall_s"] == 18.5
    assert cost["outcome"] == "COMPLETED"
    assert cost["host_profile"] == "synthetic-native"
    provenance = cost["metric_provenance"]
    assert (
        provenance["ledger_sha256"] == hashlib.sha256(ledger.read_bytes()).hexdigest()
    )
    assert provenance["ledger_line"] == 2
    assert provenance["executor"] == "native"
    assert provenance["event"] == "FINISHED"
    assert provenance["case"] == "pilot-0000"
    assert provenance["cgroup"] == "POD_SCOPED_COUNTERS_NOT_USED"


def test_native_missing_metrics_stay_unknown_even_with_stale_cgroup(
    tmp_path, monkeypatch
):
    cost, _, _ = _observe(
        tmp_path,
        monkeypatch,
        {
            "event": "FINISHED",
            "executor": "native",
            "outcome": "FAILED_INFRA",
            "wall_s": 8.0,
            "cgroup_cpu_s": 999999,
            "cgroup_memory_peak_bytes": 1099511627776,
        },
    )
    assert cost["cpu_s"] is None
    assert cost["memory_peak_mib"] is None
    assert cost["cgroup_cpu_s"] is None
    assert cost["cgroup_memory_peak_mib"] is None
    assert cost["wall_s"] == 8.0
    assert cost["outcome"] == "FAILED_INFRA"


@pytest.mark.parametrize("invalid", [True, -1, float("inf"), float("nan"), "12"])
def test_native_invalid_metrics_do_not_become_zero_or_pod_totals(
    tmp_path, monkeypatch, invalid
):
    cost, _, _ = _observe(
        tmp_path,
        monkeypatch,
        {
            "event": "FINISHED",
            "executor": "native",
            "outcome": "CENSORED_CASE_TIMEOUT",
            "wall_s": 9.0,
            "rusage_cpu_s": invalid,
            "rusage_maxrss_bytes": invalid,
            "sampled_group_rss_peak_bytes": None,
        },
    )
    assert cost["cpu_s"] is None
    assert cost["memory_peak_mib"] is None
    assert cost["outcome"] == "CENSORED_CASE_TIMEOUT"


def test_native_measured_zero_is_retained_and_partial_memory_is_measured(
    tmp_path, monkeypatch
):
    cost, _, _ = _observe(
        tmp_path,
        monkeypatch,
        {
            "event": "FINISHED",
            "executor": "native",
            "outcome": "FAILED_INFRA",
            "wall_s": 0.2,
            "rusage_cpu_s": 0.0,
            "rusage_maxrss_bytes": None,
            "sampled_group_rss_peak_bytes": 0,
        },
    )
    assert cost["cpu_s"] == 0.0
    assert cost["memory_peak_mib"] == 0.0
    assert cost["rusage_maxrss_bytes"] is None
    assert cost["sampled_group_rss_peak_bytes"] == 0


@pytest.mark.parametrize("executor", ["docker", None])
def test_nonnative_legacy_cost_is_unchanged(tmp_path, monkeypatch, executor):
    cost, legacy, _ = _observe(
        tmp_path,
        monkeypatch,
        {
            "event": "FINISHED",
            "executor": executor,
            "outcome": "COMPLETED",
            "wall_s": 18.5,
            "rusage_cpu_s": 12.75,
            "rusage_maxrss_bytes": 64 * MIB,
            "sampled_group_rss_peak_bytes": 96 * MIB,
        },
    )
    assert cost == legacy
    assert "metric_provenance" not in cost


def test_other_family_does_not_rebind_f08_cost(tmp_path, monkeypatch):
    cost, legacy, _ = _observe(
        tmp_path,
        monkeypatch,
        {
            "event": "FINISHED",
            "family": "other-fixture-family",
            "executor": "native",
            "outcome": "COMPLETED",
            "rusage_cpu_s": 5.0,
        },
    )
    assert cost == legacy


def _complete_ladders(tmp_path, monkeypatch, *, outcome, executor="native"):
    bulk = tmp_path / "bulk"
    bulk.mkdir()
    rows = [{"event": "RUN_START", "docker": {"executor": executor}}]
    dirs, cases = {}, {}
    bad_name = "pilot-0000-h1.7"
    for i in range(8):
        stem = f"pilot-{i:04d}"
        for suffix in ("", "-h2.25", "-h1.7"):
            name = stem + suffix
            work = bulk / "cases" / "f08" / name / "work"
            work.mkdir(parents=True)
            (work / "case.dat").write_text("synthetic parseable observer output\n")
            (work / "cgroup.txt").write_text(
                "/sys/fs/cgroup/cpu.stat:usage_usec 900000000000000\n"
            )
            dirs[name] = work
            cases[name] = {
                "verdict": "PASS",
                "status": "REFERENCE_DIAGNOSTIC",
                "cost": {"cgroup_cpu_s": 900000000},
            }
            row = {
                "event": "FINISHED",
                "family": "f08",
                "case": name,
                "executor": executor,
                "outcome": outcome if name == bad_name else "COMPLETED",
                "wall_s": 12.0,
                "rusage_cpu_s": 7.0,
                "rusage_maxrss_bytes": 64 * MIB,
                "sampled_group_rss_peak_bytes": 96 * MIB,
            }
            if name == bad_name and outcome is None:
                row["event"] = "STARTED"  # Output exists without a FINISHED receipt.
                row.pop("outcome")
            rows.append(row)
    (bulk / "ledger.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
    monkeypatch.setattr(
        pilot.freeze_mod, "observe_all", lambda *_args: {"cases": copy.deepcopy(cases)}
    )
    monkeypatch.setattr(pilot.freeze_mod, "_case_dirs", lambda _bulk: dirs)
    read_cases = []

    def parsed(work):
        read_cases.append(work.parent.name)
        return {"synthetic_parseable": True}

    monkeypatch.setattr(pilot.deck, "observe", parsed)
    monkeypatch.setattr(
        pilot.deck,
        "convergence",
        lambda _rungs: {
            "rungs": {"h3": {"verdict": "PASS"}, "h2.25": {"verdict": "PASS"}}
        },
    )
    output = tmp_path / "observed.json"
    summary = pilot.observe(bulk, output)
    assert json.loads(output.read_text()) == summary
    return summary, bad_name, read_cases


@pytest.mark.parametrize(
    "outcome", ["FAILED_INFRA", "CENSORED_CASE_TIMEOUT", "CENSORED_FAMILY_CAP", None]
)
def test_parseable_native_failed_or_missing_finish_never_passes_convergence(
    tmp_path, monkeypatch, outcome
):
    summary, name, reads = _complete_ladders(tmp_path, monkeypatch, outcome=outcome)
    expected = "INCOMPLETE_NATIVE_EXECUTION" if outcome is None else "EXECUTION_FAILED"
    assert summary["cases"][name]["status"] == expected
    assert "verdict" not in summary["cases"][name]
    assert summary["cases"][name]["execution_outcome"] == outcome
    assert summary["convergence"]["pilot-0000"]["status"] == expected
    assert "rungs" not in summary["convergence"]["pilot-0000"]
    assert summary["bank_mesh"]["status"] == "UNRESOLVED_INCOMPLETE_WITNESSES"
    assert summary["bank_mesh"]["h_mm"] is None
    assert not {"pilot-0000", "pilot-0000-h2.25", name}.intersection(reads)
    cost = summary["cases"][name]["cost"]
    assert cost["cpu_s"] == (None if outcome is None else 7.0)
    assert cost["metric_provenance"]["event"] == (
        "MISSING_FINISHED" if outcome is None else "FINISHED"
    )


def test_native_completed_ladders_retain_frozen_convergence_behavior(
    tmp_path, monkeypatch
):
    summary, _, reads = _complete_ladders(tmp_path, monkeypatch, outcome="COMPLETED")
    assert len(reads) == 24
    assert summary["bank_mesh"] == {"h_mm": 3.0, "status": "PASS"}
    assert all("rungs" in row for row in summary["convergence"].values())


def test_nonnative_rung_admission_behavior_is_unchanged(tmp_path, monkeypatch):
    summary, name, reads = _complete_ladders(
        tmp_path, monkeypatch, outcome="FAILED_INFRA", executor="docker"
    )
    assert len(reads) == 24
    assert summary["cases"][name]["verdict"] == "PASS"
    assert summary["bank_mesh"] == {"h_mm": 3.0, "status": "PASS"}
    assert "cpu_s" not in summary["cases"][name]["cost"]
