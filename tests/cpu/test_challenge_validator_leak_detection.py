"""Answer-key leak detection (owner, 2026-10-07): a hotkey scoring
anomalously better on its scored batches than on fresh, retired or published
ones. Operator-side, descriptive, never a gate.

The detector runs on synthetic profiles. Battery's profile runs on
import-only validators fed signed packages of published development cases and
their PyBaMM references, with `DirectBackend`. No chain, network or spend.
"""

import json
import sys
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tests" / "cpu"))

from test_battery_validator_daemon import refs  # noqa: F401 - fixture
from test_challenge_validator_acceptance import real_package
from test_challenge_validator_answer_key import battery_validator
from test_challenge_validator_rotation import EVERY
from test_graphite_hidden_score import knn

from carbon.challenge_validator import acceptance as acc
from carbon.challenge_validator import answer_key as ak
from carbon.challenge_validator import leak_detection as ld


def profile(sid, current, unseen, hotkey="5H"):
    batches = {f"c{i}": {"class": "current", "score": s} for i, s in enumerate(current)}
    batches.update(
        {f"u{i}": {"class": kind, "score": s} for i, (kind, s) in enumerate(unseen)}
    )
    return {"hotkey": hotkey, "submission_id": sid, "batches": batches}


# -- the detector ---------------------------------------------------------------------------


def test_a_leaker_stands_out_and_an_honest_model_does_not():
    honest = profile("honest", [0.30, 0.31, 0.29], [("fresh", 0.31), ("retired", 0.30)])
    leaker = profile(
        "leaker",
        [0.05, 0.06, 0.05],
        [("fresh", 0.30), ("retired", 0.31), ("published", 0.29)],
    )
    out = ld.report([honest, leaker], lower_is_better=True, seed_band=0.02)
    rows = {r["submission_id"]: r for r in out["rows"]}
    assert rows["leaker"]["advantage"] == pytest.approx(0.25)
    assert rows["leaker"]["in_seed_band"] == pytest.approx(12.5)
    assert abs(rows["honest"]["advantage"]) < 0.02
    assert out["rows"][0]["submission_id"] == "leaker"
    flagged = {c["cutoff"]: c["above"] for c in out["curves"]["in_seed_band"]}
    assert flagged[8.0] == 1 and flagged[0.5] == 1
    # Descriptive only: no gate, no chosen threshold.
    assert (out["descriptive_only"], out["gates"], out["threshold"]) == (
        True,
        "NONE",
        "HUMAN_INPUT",
    )


def test_the_direction_follows_the_challenge():
    higher = profile("h", [0.9], [("fresh", 0.5)])
    row = ld.report([higher], lower_is_better=False)["rows"][0]
    assert row["advantage"] == pytest.approx(0.4)
    assert row["in_seed_band"] is None  # no band given: never a ratio


def test_without_unseen_batches_there_is_no_advantage():
    alone = profile("a", [0.3], [])
    row = ld.report([alone], lower_is_better=True, seed_band=0.1)["rows"][0]
    assert row["advantage"] is None and row["in_seed_band"] is None


# -- battery's profile, on import-only validators -------------------------------------------


def test_a_battery_validator_profiles_its_scored_submissions(
    tmp_path,
    refs,  # noqa: F811
):
    from carbon.agent_campaign.graphite.hidden_score import HiddenPool

    key = ak.ProducerKey.create(tmp_path / "producer.key")
    adapter = battery_validator(tmp_path / "v", import_only=True)
    adapter.target.allow_published_cases = True
    identities = adapter.identities()
    # Slots 1-3 are live at the scoring block; slot 5 starts after it.
    for slot, role in (
        (1, "pscreen-B00"),
        (2, "pscreen-B01"),
        (3, "pscreen-B02"),
        (5, "pscreen-B03"),
    ):
        value = real_package(key, identities, refs, role, slot)
        adapter.import_answer_key(*ak.verify(value, key.public_key))
    adapter.target.store.open_pool()
    block = 3 * EVERY + 5
    view, record = HiddenPool(
        adapter.target, run_id="leak", clock=lambda: block
    ).submit("proposal", knn(7))
    assert view["state"] == "SCORED"
    before = adapter.score_record(record["submission_id"])
    [found] = adapter.leak_profiles()
    classes = sorted(b["class"] for b in found["batches"].values())
    assert classes == ["current", "current", "current", "fresh"]
    assert all(b["score"] is not None for b in found["batches"].values())
    # Leak scoring never touches the score: it still replays exactly.
    assert adapter.score_record(record["submission_id"]) == before
    out = acc.leak_measurement(adapter, seed_band=0.05)
    [row] = out["rows"]
    assert row["n"] == {"current": 3, "fresh": 1, "retired": 0, "published": 0}
    assert row["advantage"] is not None
    text = json.dumps(out)
    for batch in adapter.target.store.batches():
        for case in batch["document"]["cases"]:
            assert case["case_id"] not in text
