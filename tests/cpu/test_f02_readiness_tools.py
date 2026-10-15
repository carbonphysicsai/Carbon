"""f02 readiness tooling: bulk-layout judge input, A5 lineage, nested draws."""

import importlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/dev/reference_packages/elmer"))
readiness = importlib.import_module("f02_readiness")
bank = importlib.import_module("f02_bank")


def test_solved_dir_reads_the_local_and_the_bulk_runner_layouts(tmp_path):
    (tmp_path / "cases/f02/a/work").mkdir(parents=True)
    (tmp_path / "f02/b").mkdir(parents=True)
    assert readiness._solved_dir(tmp_path, "a") == tmp_path / "cases/f02/a/work"
    assert readiness._solved_dir(tmp_path, "b") == tmp_path / "f02/b"


def _judgement(path, peak, crossing="NOT_REACHED", unsolved=False):
    obs = {"x-primary": {"peak_top_c": peak, "first_95c_crossing_s": crossing}}
    obs["y-mesh2"] = {"status": "NOT_SOLVED"} if unsolved else {"peak_top_c": 1.0}
    path.write_text(json.dumps({"observables": obs}))
    return path


def test_lineage_applies_the_a5_band_and_skips_cases_unsolved_on_one_build(tmp_path):
    a = _judgement(tmp_path / "a.json", 90.0, unsolved=True)
    ok = readiness.lineage(a, _judgement(tmp_path / "b.json", 90.005), tmp_path / "o")
    assert ok["pass"] and ok["cases_compared"] == 1
    bad = readiness.lineage(a, _judgement(tmp_path / "c.json", 90.02), tmp_path / "o")
    assert not bad["pass"]
    flag = readiness.lineage(
        a, _judgement(tmp_path / "d.json", 90.0, crossing=12.0), tmp_path / "o"
    )
    assert not flag["pass"]  # a crossing on one build only is a finding


def test_train_draws_are_nested_round_robin_and_avoid_excluded_tuples():
    contexts = {ctx: {"actions": []} for ctx, _ in bank.menu.contexts()}
    big = bank.public_draws(contexts, 7, 4)
    small = bank.public_draws(contexts, 7, 2)
    assert small == big[: len(small)] and len(big) == 4 * len(contexts)
    assert [row[0] for row in big[: len(contexts)]] == list(contexts)
    other = bank.public_draws(contexts, 8, 2, exclude=big)
    assert not {tuple(r) for r in other} & {tuple(r) for r in big}
