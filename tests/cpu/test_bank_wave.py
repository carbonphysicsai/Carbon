"""Motor Specialist Bank wave runner + aggregator (`scripts/dev/bank_wave.py`): run order, resume, STOP, load pause,
typed failure records, and an aggregate that compares each arm with the same recipe's original at the same seed and
says nothing about a cell under 3 recipes. Synthetic wave and a fake retrain only (no training).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "dev"))

import bank_retrain
import bank_wave as wave

from carbon.level4 import staging, submission

SEEDS = [900_000_000, 900_000_001]


def _envelope():
    doc = json.dumps({"graphs": {}}, sort_keys=True).encode()
    files = {submission.name(doc): doc}
    manifest = json.dumps({"documents": {"forward": submission.name(doc)}}).encode()
    return json.dumps(staging.envelope(manifest, files))


def _wave(tmp_path, strata):
    root = tmp_path / "wave"
    root.mkdir()
    for i, (stratum, arms, expect) in enumerate(strata):
        folder = root / f"r{i:02d}"
        folder.mkdir()
        (folder / "recipe.json").write_text(json.dumps({"recipe": i}))
        (folder / "envelope.json").write_text(_envelope())
        (folder / "arms.txt").write_text("\n".join(arms) + "\n")
        (folder / "stratum.txt").write_text(stratum + "\n")
        if expect:
            (folder / "expect.txt").write_text("sha256:" + "a" * 64 + "\n")
    out = tmp_path / "out"
    out.mkdir()
    verify = tmp_path / "verify.json"
    verify.write_text("{}")
    return root, out, verify


def _fake(calls, within=None, fail=None):
    def retrain(
        recipe,
        raw_manifest,
        files,
        verify_bytes,
        verify_sha256,
        *,
        seed,
        arm,
        expect_state_digest,
    ):
        calls.append((recipe["recipe"], arm, seed, expect_state_digest))
        if fail and (recipe["recipe"], arm) in fail:
            raise fail[(recipe["recipe"], arm)]
        n = (within or {}).get((recipe["recipe"], arm), 3)
        return {
            "arm": arm,
            "seed": seed,
            "admission": {"state": "ADMITTED"},
            "fit": {"train_loss": 1.0 + n / 10 + seed % 2 / 100},
            "verify": {"aggregate": {"accuracy_vs_u": {"n_within_u": n}}},
            "reproduced": None if expect_state_digest is None else True,
            "wall_s": 10.0,
        }

    return retrain


def test_run_order_original_at_seed_zero_first_then_every_arm_at_every_seed(tmp_path):
    root, _out, _verify = _wave(
        tmp_path,
        [("S", ["original", "default:steps"], True), ("S", ["original"], False)],
    )
    order = [(f.name, a, s, e is not None) for f, a, s, e in wave.jobs(root, SEEDS)]
    assert order == [
        ("r00", "original", 0, True),
        ("r00", "original", SEEDS[0], False),
        ("r00", "original", SEEDS[1], False),
        ("r00", "default:steps", SEEDS[0], False),
        ("r00", "default:steps", SEEDS[1], False),
        ("r01", "original", 0, False),
        ("r01", "original", SEEDS[0], False),
        ("r01", "original", SEEDS[1], False),
    ]


def test_run_writes_every_report_and_a_rerun_resumes_without_retraining(tmp_path):
    root, out, verify = _wave(tmp_path, [("S", ["original", "defaults_all"], True)])
    calls = []
    kw = {
        "load_max": 32,
        "pause_s": 0,
        "retrain": _fake(calls),
        "load1": lambda: 1.0,
        "sleep": lambda s: None,
    }
    assert wave.run(root, out, verify, "0" * 64, SEEDS, **kw) == 0
    assert len(calls) == 5 and calls[0] == (0, "original", 0, "sha256:" + "a" * 64)
    assert len(list(out.glob("r00__*.json"))) == 5
    assert wave.run(root, out, verify, "0" * 64, SEEDS, **kw) == 0
    assert len(calls) == 5


def test_stop_file_and_load_guard(tmp_path):
    root, out, verify = _wave(tmp_path, [("S", ["original"], False)])
    calls, sleeps = [], []
    loads = iter([40.0, 35.0, 10.0] + [1.0] * 10)
    rc = wave.run(
        root,
        out,
        verify,
        "0" * 64,
        SEEDS,
        load_max=32,
        pause_s=7,
        retrain=_fake(calls),
        load1=lambda: next(loads),
        sleep=sleeps.append,
    )
    assert rc == 0 and sleeps == [7, 7] and len(calls) == 3
    for p in out.glob("*.json"):
        p.unlink()
    (out / "STOP").write_text("")
    assert (
        wave.run(
            root,
            out,
            verify,
            "0" * 64,
            SEEDS,
            load_max=32,
            pause_s=0,
            retrain=_fake(calls),
        )
        == 3
    )
    assert len(calls) == 3


def test_refusals_and_errors_are_typed_records_and_the_wave_goes_on(tmp_path):
    root, out, verify = _wave(
        tmp_path, [("S", ["original", "default:polish_steps", "single_member"], False)]
    )
    calls = []
    fail = {
        (0, "default:polish_steps"): bank_retrain.BankRefused("arm_no_change"),
        (0, "single_member"): MemoryError("secret traceback text"),
    }
    assert (
        wave.run(
            root,
            out,
            verify,
            "0" * 64,
            SEEDS,
            load_max=32,
            pause_s=0,
            retrain=_fake(calls, fail=fail),
            load1=lambda: 0.0,
        )
        == 0
    )
    refused = json.loads(
        (out / wave.report_name("r00", "default:polish_steps", SEEDS[0])).read_text()
    )
    error = json.loads(
        (out / wave.report_name("r00", "single_member", SEEDS[1])).read_text()
    )
    assert refused["admission"] == {"state": "REFUSED", "code": "arm_no_change"}
    assert error["admission"] == {"state": "ERROR", "code": "MemoryError"}
    assert (
        "secret"
        not in (out / wave.report_name("r00", "single_member", SEEDS[1])).read_text()
    )


def test_aggregate_compares_with_the_same_recipe_and_suppresses_small_cells(tmp_path):
    strata = [("S", ["original", "default:steps"], True)] * 3 + [
        ("T", ["original", "default:steps"], False)
    ]
    root, out, verify = _wave(tmp_path, strata)
    within = {
        (0, "default:steps"): 5,
        (1, "default:steps"): 4,
        (2, "default:steps"): 3,
        (3, "default:steps"): 6,
    }
    wave.run(
        root,
        out,
        verify,
        "0" * 64,
        SEEDS,
        load_max=32,
        pause_s=0,
        retrain=_fake([], within=within),
        load1=lambda: 0.0,
    )
    result = wave.aggregate(root, out)
    cell = result["cells"]["S || default:steps"]
    assert cell["recipes"] == 3 and cell["runs"] == 6 and cell["admitted_share"] == 1.0
    assert cell["within_u_delta_median"] == 1
    assert (
        cell["within_u_improved"],
        cell["within_u_same"],
        cell["within_u_worse"],
    ) == (4, 2, 0)
    assert "T || default:steps" not in result["cells"]
    assert result["suppressed"] == 1
    assert result["seed0_reproduction"] == {
        "S": {"equal": 3, "differs": 0, "no_expect": 0}
    }
    assert set(result["seed_spread_train_loss_median"]) == {"S"}
    assert result["cost"]["runs"] == 4 * 5
    text = (out / "aggregate.json").read_text()
    assert "r00" not in text and "recipe" not in text.replace("recipes", "")
    assert "not causal" in result["caveat"]


def test_main_refuses_seed_zero_as_a_wave_seed_and_a_minimum_under_three(
    tmp_path, capsys
):
    root, out, verify = _wave(tmp_path, [("S", ["original"], False)])
    base = [
        "run",
        "--wave",
        str(root),
        "--out",
        str(out),
        "--verify",
        str(verify),
        "--verify-sha256",
        "0" * 64,
    ]
    assert wave.main(base + ["--seeds", "0,900000000", "--load-max", "32"]) == 2
    assert wave.main(base + ["--seeds", "12345", "--load-max", "32"]) == 2
    assert (
        wave.main(
            ["aggregate", "--wave", str(root), "--out", str(out), "--min-recipes", "2"]
        )
        == 2
    )
    assert "refused" in capsys.readouterr().out
