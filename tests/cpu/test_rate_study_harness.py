"""SUBMISSION-RATE-STUDY-01's harness (VALIDATOR-30).

Slice A: the rate rule variants; the study bank drawn down without top-up;
the fresh sets as their own never-window-drawable bank; and the
non-consuming fresh scorer, which scores every model on the same sealed set
once each.

Slice B: arm H's runner to the consumer contract
(`VALIDATOR_30_CONSUMER_CONTRACT.md`): the closed refusals, fixture mode end
to end, and, with a recording world in place of the producer, route and
scorer (each tested on its own elsewhere), the bank-short window, the probe
counts and the resume.

Synthetic roots and scripted solves only: no container, chain, network or
spend. Not a security audit (AGENTS.md §13).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tests" / "cpu"))

from test_challenge_validator_design_windows import adapter
from test_challenge_validator_producer import scripted_solve

from carbon.battery import exam
from carbon.battery.daemon import rule_digest
from carbon.challenge_validator import rate_study
from carbon.challenge_validator.bank import BankRefused
from carbon.challenge_validator.batch_source import ProducerRefused
from carbon.challenge_validator.battery_bank import BankedBatterySource

RATES = {"v2-bank-rate-1": 360, "v2-bank-rate-2": 180, "v2-bank-rate-4": 90}


def test_the_rate_variants_differ_only_as_the_study_needs():
    base = exam.RULES["v2-bank"]
    digests = {rule_digest(base)}
    for name, window in RATES.items():
        rule = exam.RULES[name]
        assert rule["per_hotkey"]["window_blocks"] == window
        assert rule["study"] == "SUBMISSION-RATE-STUDY-01"
        assert rule["bank"]["pool"]["size"] == 3000
        assert rule["bank"]["pool"]["top_up"] is False
        assert rule["bank"]["pool"]["retire_at"] == 5
        assert exam.disclosure(rule) == exam.disclosure(base)
        digests.add(rule_digest(rule))
    assert len(digests) == 4  # each its own, and none is v2-bank's


def small(rule):
    """A rate rule with a tiny pool, for the test's scripted bank."""
    pool = {**rule["bank"]["pool"], "size": 8, "window_cases": 4}
    return {**rule, "bank": {**rule["bank"], "pool": pool}}


@pytest.fixture
def study(tmp_path):
    rule = small(exam.RULES["v2-bank-rate-1"])
    return BankedBatterySource(
        adapter(tmp_path / "producer-state", rule=rule),
        tmp_path / "bank",
        overlay=tmp_path / "overlay",
        repository=REPOSITORY,
        runner=scripted_solve,
    )


def test_the_study_bank_is_drawn_down_and_never_topped_up(study):
    study.top_up()  # the operator's fill
    drawn = []
    with pytest.raises(ProducerRefused) as refused:
        for slot in range(1, 10):
            drawn.append(study.draw(f"pscreen-S{slot}", kind="screening"))
    assert refused.value.code == "producer_bank_short"
    assert drawn  # some windows drew before the bank ran short
    assert len(study.ledger.tranches("pool")) == 1  # no tranche was added


def test_fresh_sets_are_their_own_bank_and_never_window_drawable(study):
    sealed = study.fresh_fill(2, 5)
    assert [s["tranche"] for s in sealed] == ["bank-fresh-T1", "bank-fresh-T2"]
    assert study.fresh_fill(2, 5) == []  # resumable: nothing to do
    with pytest.raises(BankRefused) as refused:
        study.ledger.draw_window("fresh", 1, {"all": 2}, retire_at=5)
    assert refused.value.code == "bank_not_window_drawable"


def test_a_production_rule_has_no_fresh_sets(tmp_path):
    source = BankedBatterySource(
        adapter(tmp_path / "state", rule=exam.RULES["v2-bank"]),
        tmp_path / "bank",
        repository=REPOSITORY,
        runner=scripted_solve,
    )
    with pytest.raises(ProducerRefused) as refused:
        source.fresh_fill(1, 5)
    assert refused.value.code == "producer_fresh_not_a_study"


def test_the_fresh_scorer_is_non_consuming_and_scores_each_model_once(
    study, tmp_path, monkeypatch
):
    study.fresh_fill(1, 6)
    target = study.adapter.target
    calls = []

    def predict(sid, inputs, tag, namespace=None):
        calls.append((sid, namespace))
        _ids, _inputs, refs = rate_study.fresh_set(study.ledger, 1)
        return {c: refs[c].get("outputs") for c in inputs}

    monkeypatch.setattr(target, "_quiz_predictions", predict)
    state = tmp_path / "run"
    state.mkdir(mode=0o700)
    first = rate_study.fresh_score(target, study.ledger, "s1", 1, state)
    again = rate_study.fresh_score(target, study.ledger, "s1", 1, state)
    other = rate_study.fresh_score(target, study.ledger, "s2", 1, state)
    assert first["state"] == "SCORED" and again == first
    assert other["state"] == "SCORED"  # the same set, never consumed
    assert calls == [("s1", "fresh/"), ("s2", "fresh/")]
    with pytest.raises(rate_study.StudyRefused) as refused:
        rate_study.fresh_score(target, study.ledger, "s1", 2, state)
    assert refused.value.code == "study_fresh_set_not_sealed"


# --- slice B: arm H's runner -------------------------------------------------


def study_config(tmp_path, **over):
    config = {
        "schema": rate_study.CONFIG_SCHEMA,
        "fixture": True,
        "roots": {name: str(tmp_path / name) for name in rate_study.ROOTS},
        "rules": {str(m): f"v2-bank-rate-{m}" for m in rate_study.RATES},
        "library": {"path": "library-v2.json", "digest": None},
        "order_seed": "SUBMISSION-RATE-STUDY-01/arm-H/library-v2",
        "windows": 2,
        "clock": {"mode": "simulated", "start_block": 1_000_000},
        "hotkey": "study-hotkey-1",
        "bank": {
            "name": "study",
            "cases": 3000,
            "sacrificial": True,
            "top_up": "off",
            "tranche_roots": [],
        },
        "fresh": {"name": "fresh", "windows": 12, "cases_per_window": 98, "roots": {}},
        "records_dir": str(tmp_path / "records"),
        **over,
    }
    path = tmp_path / "rate-study.json"
    path.write_text(json.dumps(config))
    return path


def records(tmp_path, rate=1, replicate=1):
    path = tmp_path / "records" / "H" / str(rate) / f"{replicate}.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines()]


def test_the_refusals_are_closed_and_typed():
    assert len(set(rate_study.REFUSALS)) == len(rate_study.REFUSALS) == 21


def test_a_fixture_run_writes_exactly_the_record_schema(tmp_path, capsys):
    config = study_config(tmp_path)
    assert rate_study.check(config) is None
    argv = ["run", "--config", str(config), "--arm", "H", "--rate", "2"]
    argv += ["--replicate", "1"]
    assert rate_study.main(argv) == 0
    found = records(tmp_path, rate=2)
    assert [r["t"] for r in found] == list(range(1, 13))  # 3m x 2 windows
    assert all(sorted(r) == sorted(rate_study.FIELDS) for r in found)
    assert all(r["state"] == "SCORED" and r["provenance"] == "FIXTURE" for r in found)
    assert all(r["d_index"] == r["s_fresh"] - r["s_current"] for r in found)
    manifest = json.loads(
        (tmp_path / "records" / "H" / "2" / "1.manifest.json").read_text()
    )
    assert manifest["counts"]["scored"] == 12
    assert manifest["rule"] == "v2-bank-rate-2"
    capsys.readouterr()
    assert rate_study.main(argv) == 2  # complete: nothing duplicated
    assert capsys.readouterr().out.strip() == "refused: replicate_already_complete"
    assert records(tmp_path, rate=2) == found


OTHER_RULES = {"1": "v2-bank-rate-2", "2": "v2-bank-rate-2", "4": "v2-bank-rate-4"}


@pytest.mark.parametrize(
    "over, arm, code",
    [
        ({"freeze_manifest": None}, "S-sealed", "freeze_manifest_required"),
        ({"freeze_manifest": "/tmp/f.json"}, "S-sealed", "arm_not_built"),
        (
            {"library": {"path": "library-v2.json", "digest": "sha256:" + "0" * 64}},
            "H",
            "library_digest_mismatch",
        ),
        ({"rules": OTHER_RULES}, "H", "rule_window_blocks_mismatch"),
        ({"rules": {**OTHER_RULES, "1": "v9"}}, "H", "rule_unknown"),
        ({"schema": "carbon.rate-study.config.v0"}, "H", "config_schema_mismatch"),
    ],
)
def test_check_refuses_with_a_closed_code(tmp_path, over, arm, code):
    assert rate_study.check(study_config(tmp_path, **over), arm) == code
    assert code in rate_study.REFUSALS


def test_a_real_run_refuses_any_root_outside_the_study(tmp_path):
    config = study_config(
        tmp_path,
        fixture=False,
        producer_configs={"1": "a", "2": "b", "4": "c"},
        validator_config="/v/{rate}/{replicate}.json",
    )
    config.chmod(0o600)
    assert rate_study.check(config) == "production_root_refused"


class World:
    """A recording world: scripted route answers, no producer or host."""

    provenance = "FIXTURE"

    def __init__(self, short=(), down_at=None):
        self.short, self.down_at, self.submitted = set(short), down_at, []

    def tick(self, window, block):
        return window not in self.short

    def submit(self, strategy, block, window):
        if self.down_at is not None and len(self.submitted) == self.down_at:
            raise rate_study.StudyInfrastructure("route_failed_infra")
        self.submitted.append(block)
        return {
            "state": "SCORED",
            "submission_id": rate_study._sha256(rate_study._canonical(strategy)),
            "s_current": 0.5,
            "batches": {"shared": ["a", "b"], f"w{window}": ["c"]},
            "wall_s": 0.1,
        }

    def fresh(self, submission_id, window):
        return {"state": "SCORED", "s_fresh": 0.75}

    def roots(self):
        return [], {}

    def close(self):
        pass


def test_a_short_bank_makes_its_window_unavailable_never_drift(tmp_path):
    config = study_config(tmp_path, windows=3)
    world = World(short={2})
    assert rate_study.run(config, "H", 1, 1, world=world) == 0
    states = [r["state"] for r in records(tmp_path)]
    assert states == ["SCORED"] * 3 + ["UNAVAILABLE"] * 3 + ["SCORED"] * 3
    assert all(r["d_index"] is None for r in records(tmp_path)[3:6])
    # Spaced at the rule's per-hotkey window, one window per rotation.
    assert world.submitted[1] - world.submitted[0] == 360
    assert world.submitted[3] - world.submitted[0] == 2 * 1080


def test_probes_count_this_hotkeys_scored_submissions(tmp_path):
    config = study_config(tmp_path)
    rate_study.run(config, "H", 1, 1, world=World())
    found = records(tmp_path)
    assert [r["probes_batch"] for r in found] == [1, 2, 3, 4, 5, 6]  # "shared"
    assert [r["probes_case_max"] for r in found] == [1, 2, 3, 4, 5, 6]
    assert all(r["d_index"] == 0.25 for r in found)


def test_infrastructure_exits_1_and_a_rerun_adds_only_the_missing(tmp_path, capsys):
    config = study_config(tmp_path)
    assert rate_study.run(config, "H", 1, 1, world=World(down_at=4)) == 1
    assert capsys.readouterr().out.startswith("failed: route_failed_infra")
    assert [r["t"] for r in records(tmp_path)] == [1, 2, 3, 4]
    again = World()
    assert rate_study.run(config, "H", 1, 1, world=again) == 0
    assert len(again.submitted) == 2  # only t = 5 and 6
    assert [r["t"] for r in records(tmp_path)] == list(range(1, 7))


def test_another_runs_directory_is_refused(tmp_path, capsys):
    config = study_config(tmp_path)
    run_dir = tmp_path / "runs" / "H" / "m1-r1"
    run_dir.mkdir(parents=True)
    (run_dir / "stray.json").write_text("{}")
    assert rate_study.run(config, "H", 1, 1, world=World()) == 2
    assert capsys.readouterr().out.strip() == "refused: run_dir_not_fresh"


def test_a_repeated_submission_is_its_own_line(tmp_path):
    # 14 windows at m = 4 is 168 submissions against library-v2's 146.
    config = study_config(tmp_path, windows=14)
    assert rate_study.run(config, "H", 4, 1) == 0
    found = records(tmp_path, rate=4)
    repeated = [r for r in found if r["state"] == "REPEATED"]
    assert len(found) == 168 and len(repeated) == 168 - 146
    assert all(r["s_fresh"] is None and r["probes_batch"] is None for r in repeated)


def test_the_fresh_command_is_non_consuming(tmp_path, capsys):
    config = study_config(tmp_path)
    argv = ["fresh", "--config", str(config), "--submission", "s1"]
    argv += ["--set", "fresh-w01"]
    assert rate_study.main(argv) == 0
    first = capsys.readouterr().out.strip()
    assert rate_study.main(argv) == 0
    assert capsys.readouterr().out.strip() == first
    assert set(json.loads(first)) == {"state", "s_fresh"}
