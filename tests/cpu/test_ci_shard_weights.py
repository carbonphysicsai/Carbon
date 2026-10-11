"""CI-SHARD-BALANCE-01: the shard weights come from measured CI seconds, and the balance
they give is checkable.

The shards balance by measured seconds per test file. A weights file that lags the suite
balances badly (the six canonical shards ran 14 to 44 minutes), so the weights are
regenerated from CI logs by a documented command that invents no duration. These tests
keep that command honest and the committed weights balanced; the exclusive-and-exhaustive
and reproducibility properties are in test_ci_shard.py and are repeated here against the
committed weights.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.dev import ci_shard
from scripts.dev import ci_shard_weights as csw

REPOSITORY = Path(__file__).resolve().parents[2]
COUNT = 6


def log(digest, seconds, shard=0):
    return (
        "2026-10-11T00:00:00Z noise\n"
        f"CARBON_TEST_SHARD {shard}/6: 2 of 4 files, 5 of 9 tests, partition {digest}\n"
        f"2026-10-11T00:00:01Z CARBON_SHARD_SECONDS {json.dumps(seconds)}\n"
    )


def test_a_shard_log_yields_its_digest_and_per_file_seconds():
    digest, seconds = csw.parse_log(
        log("0123456789abcdef", {"tests/cpu/test_a.py": 1.5})
    )
    assert digest == "0123456789abcdef" and seconds == {"tests/cpu/test_a.py": 1.5}


@pytest.mark.parametrize(
    "text",
    [
        "no lines here",
        "CARBON_SHARD_SECONDS {}\n",  # no partition line
        log("0123456789abcdef", {"not a path": 1}),
        log("0123456789abcdef", {"tests/cpu/test_a.py": -1}),
        log("0123456789abcdef", {"tests/cpu/test_a.py": True}),
        "partition 0123456789abcdef\nCARBON_SHARD_SECONDS [1]\n",
        "partition 0123456789abcdef\nCARBON_SHARD_SECONDS {nope}\n",
    ],
)
def test_a_log_that_does_not_hold_measured_seconds_is_refused(text):
    with pytest.raises(ValueError):
        csw.parse_log(text)


def test_runs_are_averaged_per_file_and_nothing_is_invented():
    first = [
        log("a" * 16, {"tests/cpu/test_a.py": 10.0}, 0),
        log("a" * 16, {"tests/cpu/test_b.py": 4.0}, 1),
    ]
    second = [log("b" * 16, {"tests/cpu/test_a.py": 20.0, "tests/cpu/test_c.py": 6.0})]
    merged = csw.merge_runs([*first, *second])
    assert merged == {
        "tests/cpu/test_a.py": 15.0,
        "tests/cpu/test_b.py": 4.0,
        "tests/cpu/test_c.py": 6.0,
    }


def test_a_file_on_two_shards_of_one_run_is_refused():
    both = [log("a" * 16, {"tests/cpu/test_a.py": 1}, 0)] * 2
    with pytest.raises(ValueError, match="two shards"):
        csw.merge_runs(both)


def test_a_rebuilt_document_keeps_the_lane_data_and_sorts_its_files(tmp_path):
    previous = tmp_path / "old.json"
    previous.write_text(
        json.dumps(
            {"lane_source": "x", "lane_seconds": {"0": 5}, "seconds": {"a.py": 1}}
        ),
        encoding="utf-8",
    )
    document = csw.build_document({"tests/cpu/test_z.py": 1.0}, "runs 1", previous)
    assert document["lane_seconds"] == {"0": 5} and document["lane_source"] == "x"
    assert document["source"] == "runs 1" and document["seconds"]
    again = csw.build_document({"tests/cpu/test_z.py": 1.0}, "runs 1", previous)
    assert json.dumps(document) == json.dumps(again)


def test_build_writes_a_document_the_shard_plugin_accepts(tmp_path):
    logs = [tmp_path / f"{n}.log" for n in range(2)]
    logs[0].write_text(log("a" * 16, {"tests/cpu/test_a.py": 3.0}, 0), encoding="utf-8")
    logs[1].write_text(log("a" * 16, {"tests/cpu/test_b.py": 5.0}, 1), encoding="utf-8")
    out = tmp_path / "weights.json"
    assert (
        csw.main(["build", *map(str, logs), "--source", "fixture", "--out", str(out)])
        == 0
    )
    assert ci_shard.load_measured(out) == {
        "tests/cpu/test_a.py": 3.0,
        "tests/cpu/test_b.py": 5.0,
    }


# -- the committed weights ---------------------------------------------------------------------
def committed():
    return ci_shard.load_measured(ci_shard.WEIGHTS_PATH)


def test_every_measured_file_lands_on_exactly_one_shard_and_the_partition_repeats():
    seconds = committed()
    lanes = ci_shard.load_lanes(ci_shard.WEIGHTS_PATH)
    first = ci_shard.partition(
        ci_shard.file_weights({p: 1 for p in seconds}, seconds), COUNT, lanes
    )
    second = ci_shard.partition(
        ci_shard.file_weights({p: 1 for p in seconds}, seconds), COUNT, lanes
    )
    assert first == second
    flat = [path for shard in first for path in shard]
    assert sorted(flat) == sorted(seconds) and len(flat) == len(set(flat))
    assert all(first)  # no empty shard


def test_an_unmeasured_file_gets_a_deterministic_assignment_without_moving_the_rest():
    seconds = committed()
    lanes = ci_shard.load_lanes(ci_shard.WEIGHTS_PATH)
    counts = {p: 1 for p in seconds}
    extra = {**counts, "tests/cpu/test_brand_new_unmeasured.py": 7}
    plans = [
        ci_shard.partition(ci_shard.file_weights(extra, seconds), COUNT, lanes)
        for _ in range(2)
    ]
    assert plans[0] == plans[1]
    assert sum("tests/cpu/test_brand_new_unmeasured.py" in s for s in plans[0]) == 1
    assert ci_shard.partition_digest(plans[0]) == ci_shard.partition_digest(plans[1])


def test_the_committed_weights_balance_the_six_shards():
    result = csw.simulate(ci_shard.WEIGHTS_PATH, None, COUNT)
    assert result["measured_by_assigned"] == result["files"] > 600
    # The measured critical path is within a tenth of the ideal split.
    assert result["critical_path_minutes"] <= result["ideal_minutes"] * 1.1
    assert result["spread"] <= 1.15


def test_the_old_weights_balance_worse_than_the_refreshed_ones(tmp_path):
    """The simulation separates what a lagging file gives from what a fresh one does:
    a file with only a tenth of the suite measured cannot reach the ideal."""
    fresh = committed()
    old = tmp_path / "old.json"
    names = sorted(fresh)
    old.write_text(
        json.dumps(
            {
                "lane_seconds": ci_shard.load_lanes(ci_shard.WEIGHTS_PATH) or {},
                "seconds": {p: fresh[p] for p in names[::10]},
            }
        ),
        encoding="utf-8",
    )
    lagging = csw.simulate(ci_shard.WEIGHTS_PATH, old, COUNT)
    current = csw.simulate(ci_shard.WEIGHTS_PATH, None, COUNT)
    assert lagging["measured_by_assigned"] < current["measured_by_assigned"]
    assert lagging["critical_path_minutes"] >= current["critical_path_minutes"]


def test_the_shard_log_reports_how_many_files_had_no_measurement(tmp_path):
    from test_ci_shard import _run, _suite

    run = _run(_suite(tmp_path), "0/3")
    assert run.returncode == 0, run.stdout + run.stderr
    [line] = [
        x for x in run.stdout.splitlines() if x.startswith("CARBON_SHARD_UNMEASURED ")
    ]
    assert " of 6 files had no measured seconds" in line
