"""The common sealed-exam runner (VALIDATOR_EXAM_ARCHITECTURE_COMMON_20261022 section 3): its
configs carry the Challenge's own values, its load/lock guard lives in the runner itself, and
the C8 U-coverage helper plans public exam-law cases, compares the largest rung step to U and
refuses an uncovered panel (re-measure, never widen)."""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
RUNNER = REPOSITORY / "scripts/dev/sealed_exam/run_sealed.sh"
CONFIGS = REPOSITORY / "scripts/dev/sealed_exam/configs"


def _coverage():
    spec = importlib.util.spec_from_file_location(
        "u_coverage", REPOSITORY / "scripts/dev/sealed_exam/u_coverage.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _config(name):
    out = subprocess.run(
        ["bash", "-c", f"set -a; source {CONFIGS / (name + '.env')}; env"],
        capture_output=True, text=True, check=True,
    ).stdout
    return dict(line.split("=", 1) for line in out.splitlines() if "=" in line)


def test_the_f02_config_carries_f02s_own_values():
    from carbon.challenge_validator import f02_hidden as hidden

    config = _config("f02")
    assert config["CID"] == hidden.CHALLENGE_ID == "f02"
    assert config["IMAGE"] == hidden.SOLVER_IMAGE
    assert config["RUNNER"] == str(hidden.RUNNER)
    assert config["RUNNER_IMAGE_VALUE"] == hidden.SOLVER_IMAGE
    assert config["DEPLOYMENT_SCHEMA"] == hidden.DEPLOYMENT_SCHEMA
    assert float(config["PROBE_BOUND"]) == 0.001
    assert float(config["PROBE_EXPECT"]) == 90.78052055710003
    assert (REPOSITORY / config["RUNNER"]).is_file()


def test_the_guard_is_in_the_runner_itself():
    text = RUNNER.read_text()
    assert "flock -n 9" in text  # one sealed run per custody host
    assert re.search(r"nproc\) / 4", text)  # the load guard (C10)
    assert "ALLOW_BUSY" in text
    # custody is append-only (C11): the runner never deletes
    assert not re.search(r"\brm\b|DELETE FROM|shutil\.rmtree", text)


def test_the_coverage_plan_is_eight_public_f02_exam_law_cases():
    module = _coverage()
    import random

    from carbon.f02.population import admitted, draw

    cases, _tries = draw(random.Random(module.SEED), module.CASES)
    assert len(cases) == 8 and module.SEED == 20261022
    assert all(admitted(c) for c in cases)


def _record(case_id, primary, mesh2_shift, dt_shift):
    return {
        "case_id": case_id,
        "status": "OK",
        "rung_peaks_c": {"primary": primary, "mesh2": primary + mesh2_shift, "dt0.5": primary + dt_shift},
    }


def _records(path, shifts):
    path.write_text("".join(json.dumps(_record(f"ucov-{i}", 90.0 + i, s, 0.0001)) + "\n" for i, s in enumerate(shifts)))


def test_a_covered_panel_passes_and_an_uncovered_one_is_refused(tmp_path):
    module = _coverage()
    records, out = tmp_path / "records.jsonl", tmp_path / "u.json"
    _records(records, [-0.004] * 7 + [-0.0114])  # within the registered 0.012
    assert module.compute("f02", str(records), str(out)) == 0
    covered = json.loads(out.read_text())
    assert covered["covered"] is True and covered["u"] == 0.012
    _records(records, [-0.004] * 7 + [-0.0128])  # 1.07 U: re-measure, never widen
    out2 = tmp_path / "u2.json"
    assert module.compute("f02", str(records), str(out2)) == 1
    result = json.loads(out2.read_text())
    assert result["covered"] is False and result["ratio_to_u"] > 1
    assert "never widen" in result["note"]


def test_an_incomplete_or_failed_panel_stops(tmp_path):
    module = _coverage()
    records = tmp_path / "records.jsonl"
    rows = [_record(f"ucov-{i}", 90.0, -0.004, 0.0) for i in range(7)]
    rows.append({"case_id": "ucov-7", "status": "REFERENCE_SOLVER_FAILED"})
    records.write_text("".join(json.dumps(r) + "\n" for r in rows))
    assert module.compute("f02", str(records), str(tmp_path / "u.json")) == 1
    assert json.loads((tmp_path / "u.json").read_text())["stops"]


def test_unknown_challenges_have_no_coverage_config_yet():
    with pytest.raises(SystemExit):
        _coverage()._spec("motor")
