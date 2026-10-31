"""OWNER-CROWN-MULTI-REBUILD-AVERAGE-01: the crown's N-rebuild mean (pure decision logic).

Claims: N is a registered config value, never a code constant (and the committed registry registers no margin yet,
so the rule answers UNAVAILABLE until the owner confirms N and the margins are registered); the seeds come from
the host-private K_crown, are distinct, never 0 and never appear in a miner-facing view; the trigger fires only
for a crown-changing screening grade; all N rebuilds must be scored, else no takeover (`unstable_across_seeds`);
an infrastructure failure is retried and never counted against the miner; the means decide, with a tie inside
margin_N keeping the king; a host-fault pair that does not reproduce is FAILED_INFRA and moves nothing; the
margins the Validator tabled are `2 * SD / sqrt(N)` of today's registered 2-SD margins.
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path

import pytest

from carbon.challenge_validator import bank_promotion as bp
from carbon.challenge_validator import crown_average as ca
from carbon.challenge_validator.interface import digest

ROOT = Path(__file__).resolve().parents[2]
CHALLENGE = "electric-motor-magnetics"
KEY = bytes(range(64))
NOISE = 0.0
MARGIN = 0.00251  # Motor at N = 10
MEASUREMENT = digest("margin measurement")


def _document(**changes):
    document = {
        "schema": ca.SCHEMA,
        "rule_version": "crown-average-v1",
        "n": 10,
        "challenge_n": {},
        "seed_range": 2147483647,
        "margins": {
            CHALLENGE: {"value": MARGIN, "n": 10, "measurement_digest": MEASUREMENT}
        },
    }
    document.update(changes)
    return document


def _rule(tmp_path, **changes):
    path = tmp_path / "crown_average.json"
    path.write_text(json.dumps(_document(**changes)))
    return ca.load_rule(path)


def _grade(total, status=bp.SCORED, sid="c"):
    return {
        "submission_id": sid,
        "evidence": {
            "model_p": {"score_status": status, "total_score": total},
            "score_compatibility": {"score_pack_digest": digest("pack")},
        },
    }


# --- the registry: N is config ---------------------------------------------------------------------------


def test_the_committed_registry_registers_n_but_no_margin_yet():
    rule = ca.load_rule()
    assert rule.n_for(CHALLENGE) == 10 and rule.seed_range == 2147483647
    # no margin is registered: the owner confirms N first, so the rule is UNAVAILABLE, never guessed
    assert all(
        rule.margin_for(c) is None for c in ("f02", "chip-cold-plate", CHALLENGE)
    )
    assert (ROOT / "scripts/validator_host_classes/crown_average.json").is_file()


def test_n_is_read_from_config_and_a_per_challenge_override_wins(tmp_path):
    rule = _rule(tmp_path, n=5, challenge_n={"f02": 7})
    assert (rule.n_for(CHALLENGE), rule.n_for("f02")) == (5, 7)


def test_a_margin_measured_at_another_n_is_not_used(tmp_path):
    rule = _rule(tmp_path, n=5)  # the registered margin was measured at N = 10
    assert rule.margin_for(CHALLENGE) is None
    assert _rule(tmp_path).margin_for(CHALLENGE) == MARGIN


@pytest.mark.parametrize(
    "changes",
    [
        {"n": 1},
        {"n": True},
        {"n": 2000},
        {"n": 10.0},
        {"seed_range": 100},
        {"seed_range": "big"},
        {"challenge_n": {"unknown-challenge": 5}},
        {"challenge_n": {CHALLENGE: 1}},
        {
            "margins": {
                CHALLENGE: {"value": -0.1, "n": 10, "measurement_digest": MEASUREMENT}
            }
        },
        {"margins": {CHALLENGE: {"value": 0.1, "n": 10}}},
        {"margins": {CHALLENGE: {"value": 0.1, "n": 10, "measurement_digest": "x"}}},
        {
            "margins": {
                "unknown-challenge": {
                    "value": 0.1,
                    "n": 10,
                    "measurement_digest": MEASUREMENT,
                }
            }
        },
        {"schema": "other"},
        {"extra": 1},
    ],
)
def test_a_malformed_registry_is_refused(tmp_path, changes):
    path = tmp_path / "crown_average.json"
    path.write_text(json.dumps(_document(**changes)))
    with pytest.raises(ca.CrownAverageInvalid):
        ca.load_rule(path)


# --- the seeds -------------------------------------------------------------------------------------------


def test_seeds_are_distinct_never_zero_in_range_and_deterministic():
    seeds = ca.derive_seeds(KEY, CHALLENGE, "sub-1", 10, 2147483647)
    assert seeds == ca.derive_seeds(KEY, CHALLENGE, "sub-1", 10, 2147483647)
    assert len(set(seeds)) == 10 and all(1 <= s < 2147483647 for s in seeds)
    assert 0 not in seeds  # the official seed is never one of the N
    # a prefix property: asking for more rebuilds extends, never reshuffles
    assert ca.derive_seeds(KEY, CHALLENGE, "sub-1", 5, 2147483647) == seeds[:5]


def test_seeds_depend_on_the_key_the_challenge_and_the_submission():
    base = ca.derive_seeds(KEY, CHALLENGE, "sub-1", 10, 2147483647)
    assert base != ca.derive_seeds(KEY[::-1], CHALLENGE, "sub-1", 10, 2147483647)
    assert base != ca.derive_seeds(KEY, "f02", "sub-1", 10, 2147483647)
    assert base != ca.derive_seeds(KEY, CHALLENGE, "sub-2", 10, 2147483647)


def test_a_zero_or_a_collision_takes_the_next_candidate(monkeypatch):
    calls = []
    real = ca._mac

    def forced(key, domain, challenge_id, submission_id, *parts):
        calls.append(parts)
        if domain == ca.SEED_DOMAIN and parts[1] == 0 and parts[0] in (0, 1):
            return (
                b"\x00" * 32
            )  # seed 1 for both candidates: a collision, then the next attempt
        return real(key, domain, challenge_id, submission_id, *parts)

    monkeypatch.setattr(ca, "_mac", forced)
    seeds = ca.derive_seeds(KEY, CHALLENGE, "sub-1", 3, 2147483647)
    assert len(set(seeds)) == 3 and 0 not in seeds


@pytest.mark.parametrize("key", [b"short", None, "text", b""])
def test_a_short_or_missing_key_is_refused(key):
    with pytest.raises(ca.CrownAverageInvalid):
        ca.derive_seeds(key, CHALLENGE, "sub-1", 10, 2147483647)


def test_the_host_fault_index_is_one_of_the_seeds_and_secret():
    index = ca.host_fault_index(KEY, CHALLENGE, "sub-1", 10)
    assert 0 <= index < 10
    assert index == ca.host_fault_index(KEY, CHALLENGE, "sub-1", 10)
    chosen = {ca.host_fault_index(KEY, CHALLENGE, f"s{i}", 10) for i in range(60)}
    assert len(chosen) > 3  # not a fixed position


@pytest.mark.skipif(os.name == "nt", reason="POSIX owner-only modes")
def test_the_key_file_must_be_an_exact_private_regular_file(tmp_path):
    good = tmp_path / "k"
    good.write_bytes(KEY)
    good.chmod(0o600)
    assert ca.read_crown_key(str(good)) == KEY
    for bad in (
        "relative/path",
        str(tmp_path / "missing"),
        None,
    ):
        with pytest.raises(ca.CrownAverageInvalid):
            ca.read_crown_key(bad)
    open_mode = tmp_path / "open"
    open_mode.write_bytes(KEY)
    open_mode.chmod(0o644)
    with pytest.raises(ca.CrownAverageInvalid):
        ca.read_crown_key(str(open_mode))
    short = tmp_path / "short"
    short.write_bytes(b"x" * 8)
    short.chmod(0o600)
    with pytest.raises(ca.CrownAverageInvalid):
        ca.read_crown_key(str(short))
    link = tmp_path / "link"
    link.symlink_to(good)
    with pytest.raises(ca.CrownAverageInvalid):
        ca.read_crown_key(str(link))


# --- seeds never reach a miner surface ----------------------------------------------------------------------


MINER_SURFACES = (
    "scripts/dev/miner_launchpad",
    "carbon/miner_mcp",
    "carbon/dashboard",
    "carbon/challenge_validator/koth_public.py",
    "carbon/challenge_validator/launch_board.py",
    "carbon/challenge_validator/launch_board_file.py",
    "carbon/challenge_validator/grade_feedback.py",
    "carbon/scoring/grade_feedback.py",
)


def test_no_miner_surface_names_the_crown_average_or_its_key():
    names = ("crown_average", "K_crown", "derive_seeds", "host_fault_index")
    offenders = []
    for entry in MINER_SURFACES:
        base = ROOT / entry
        files = (
            [base]
            if base.is_file()
            else sorted(base.rglob("*.py")) + sorted(base.rglob("*.mjs"))
        )
        for file in files:
            text = file.read_text(encoding="utf-8", errors="ignore")
            offenders += [f"{file.name}:{n}" for n in names if n in text]
    assert offenders == []


def test_the_public_view_is_the_outcome_and_reason_only():
    result = {
        "outcome": bp.CHALLENGER,
        "reason": ca.MEAN_EXCEEDS,
        "private": {"seeds": [1, 2], "totals": [0.5], "mean": 0.5, "margin": 0.1},
        "alert": {"x": 1},
    }
    assert ca.public_view(result) == {
        "outcome": bp.CHALLENGER,
        "reason": ca.MEAN_EXCEEDS,
    }


# --- the trigger -----------------------------------------------------------------------------------------


def test_the_trigger_fires_only_for_a_crown_changing_screening_grade():
    assert ca.triggered(0.70, king_mean=0.60, baseline_floor=0.26, margin=0.01)
    assert not ca.triggered(0.60, king_mean=0.60, baseline_floor=0.26, margin=0.01)
    assert not ca.triggered(
        0.61, king_mean=0.60, baseline_floor=0.26, margin=0.01
    )  # at the bar
    assert ca.triggered(0.30, king_mean=None, baseline_floor=0.26, margin=0.01)
    assert not ca.triggered(0.27, king_mean=None, baseline_floor=0.26, margin=0.01)
    assert not ca.triggered(0.9, king_mean=None, baseline_floor=None, margin=0.01)
    assert not ca.triggered(float("nan"), 0.6, 0.26, 0.01)


# --- the decision ----------------------------------------------------------------------------------------


class Builds:
    """Duck-typed rebuild functions that record what they were asked."""

    def __init__(self, totals, statuses=None, infra=None, mismatch=False):
        self.totals, self.statuses = totals, statuses or {}
        self.infra = dict(infra or {})
        self.mismatch = mismatch
        self.asked, self.again_asked = [], []
        self.order = {}

    def rebuild(self, seed):
        self.asked.append(seed)
        index = self.order.setdefault(seed, len(self.order))
        if self.infra.get(seed, 0) > 0:
            self.infra[seed] -= 1
            raise ca.RebuildInfra("host busy")
        return _grade(self.totals[index], self.statuses.get(index, bp.SCORED))

    def rebuild_again(self, seed):
        self.again_asked.append(seed)
        first = self.order[seed]
        total = self.totals[first] + (0.0123 if self.mismatch else 0.0)
        return _grade(total)


def _run(
    tmp_path, builds, *, king_mean=0.60, baseline_floor=0.26, tolerance=NOISE, **rule
):
    return ca.run_average(
        key=KEY,
        challenge_id=CHALLENGE,
        submission_id="sub-1",
        rule=_rule(tmp_path, **rule),
        rebuild=builds.rebuild,
        rebuild_again=builds.rebuild_again,
        king_mean=king_mean,
        baseline_floor=baseline_floor,
        tolerance=tolerance,
    )


def test_all_n_rebuilds_pass_and_the_mean_beats_the_king_by_the_margin_is_a_takeover(
    tmp_path,
):
    builds = Builds([0.70] * 10)
    result = _run(tmp_path, builds)
    assert (result["outcome"], result["reason"]) == (bp.CHALLENGER, ca.MEAN_EXCEEDS)
    assert result["private"]["mean"] == pytest.approx(0.70)
    expected = ca.derive_seeds(KEY, CHALLENGE, "sub-1", 10, 2147483647)
    assert builds.asked == expected  # exactly the derived seeds, in order
    assert 0 not in builds.asked  # seed 0 is excluded
    assert result["private"]["seeds"] == expected


def test_the_seeds_and_totals_are_private_to_the_decision(tmp_path):
    result = _run(tmp_path, Builds([0.70] * 10))
    assert set(ca.public_view(result)) == {"outcome", "reason"}
    text = json.dumps(ca.public_view(result))
    assert not any(str(seed) in text for seed in result["private"]["seeds"])


def test_one_gated_or_minimum_failed_seed_is_no_takeover(tmp_path):
    for status in (
        "MANDATORY_GATE_FAILED",
        "REQUIRED_LEG_MINIMUM_FAILED",
        "CANDIDATE_INVALID",
    ):
        builds = Builds([0.99] * 10, statuses={4: status})
        result = _run(tmp_path, builds)
        assert (result["outcome"], result["reason"]) == (
            bp.INCUMBENT_KEEPS,
            ca.UNSTABLE,
        )
        assert (
            builds.again_asked == []
        )  # no host-fault pair is spent on an inadmissible model
    # with no king, an unstable challenger is NO_WINNER, not a first crown
    none = _run(
        tmp_path,
        Builds([0.99] * 10, statuses={0: "MANDATORY_GATE_FAILED"}),
        king_mean=None,
    )
    assert (none["outcome"], none["reason"]) == (bp.NO_WINNER, ca.UNSTABLE)


def test_an_infrastructure_failure_is_retried_and_never_counted_against_the_miner(
    tmp_path,
):
    seeds = ca.derive_seeds(KEY, CHALLENGE, "sub-1", 10, 2147483647)
    builds = Builds([0.70] * 10, infra={seeds[3]: 2})
    result = _run(tmp_path, builds)
    assert result["outcome"] == bp.CHALLENGER
    assert builds.asked.count(seeds[3]) == 3  # two failures then the grade
    # a seed whose grade is FAILED_INFRA (not an exception) is also retried, not an inadmissible rebuild
    again = Builds([0.70] * 10, statuses={})
    original = again.rebuild
    state = {"n": 0}

    def flaky(seed):
        state["n"] += 1
        return _grade(None, "FAILED_INFRA") if state["n"] == 2 else original(seed)

    again.rebuild = flaky
    assert _run(tmp_path, again)["outcome"] == bp.CHALLENGER


def test_infrastructure_that_never_recovers_is_unavailable_not_a_loss(tmp_path):
    seeds = ca.derive_seeds(KEY, CHALLENGE, "sub-1", 10, 2147483647)
    result = _run(tmp_path, Builds([0.70] * 10, infra={seeds[0]: 99}))
    assert (result["outcome"], result["reason"]) == (
        bp.UNAVAILABLE,
        ca.REBUILD_UNAVAILABLE,
    )


def test_a_mean_inside_the_margin_is_a_tie_and_the_king_keeps_the_crown(tmp_path):
    inside = _run(tmp_path, Builds([0.60 + MARGIN / 2] * 10))
    assert (inside["outcome"], inside["reason"]) == (bp.INCUMBENT_KEEPS, ca.MEAN_WITHIN)
    at = _run(
        tmp_path, Builds([0.60 + MARGIN] * 10)
    )  # exactly the margin is not beyond it
    assert at["outcome"] == bp.INCUMBENT_KEEPS
    beyond = _run(tmp_path, Builds([0.60 + MARGIN + 0.0001] * 10))
    assert beyond["outcome"] == bp.CHALLENGER


def test_the_mean_not_a_good_seed_decides(tmp_path):
    # nine very good seeds and one poor one: the mean is below the king's
    result = _run(tmp_path, Builds([0.95] * 9 + [0.0]), king_mean=0.90)
    assert result["private"]["mean"] == pytest.approx(0.855)
    assert result["outcome"] == bp.INCUMBENT_KEEPS


def test_a_host_fault_pair_that_does_not_reproduce_is_failed_infra_and_moves_nothing(
    tmp_path,
):
    builds = Builds([0.70] * 10, mismatch=True)
    result = _run(tmp_path, builds)
    assert (result["outcome"], result["reason"]) == (
        bp.FAILED_INFRA,
        bp.REPEAT_MISMATCH,
    )
    assert result["alert"]["code"] == bp.REPEAT_MISMATCH
    assert result["alert"]["action"] == "recheck_validator_host"
    assert "0.7" not in json.dumps(result["alert"])  # ids only, no grade values
    # exactly one of the N seeds, the secretly chosen one, was rebuilt a second time
    chosen = ca.host_fault_index(KEY, CHALLENGE, "sub-1", 10)
    assert builds.again_asked == [builds.asked[chosen]]


def test_a_second_build_that_cannot_run_is_unavailable(tmp_path):
    builds = Builds([0.70] * 10)

    def broken(seed):
        raise OSError("down")

    builds.rebuild_again = broken
    result = _run(tmp_path, builds)
    assert (result["outcome"], result["reason"]) == (
        bp.UNAVAILABLE,
        bp.REPEAT_UNAVAILABLE,
    )


def test_with_no_king_the_baseline_floor_plus_the_margin_is_the_bar(tmp_path):
    beat = _run(tmp_path, Builds([0.26 + MARGIN + 0.001] * 10), king_mean=None)
    assert (beat["outcome"], beat["reason"]) == (
        bp.FIRST_INCUMBENT,
        ca.FIRST_BEATS_BASELINE,
    )
    within = _run(tmp_path, Builds([0.26 + MARGIN / 2] * 10), king_mean=None)
    assert (within["outcome"], within["reason"]) == (bp.NO_WINNER, ca.WITHIN_BASELINE)
    floorless = _run(tmp_path, Builds([0.9] * 10), king_mean=None, baseline_floor=None)
    assert floorless["outcome"] == bp.UNAVAILABLE


def test_no_registered_margin_or_tolerance_is_unavailable_never_a_guess(tmp_path):
    builds = Builds([0.99] * 10)
    unregistered = _run(tmp_path, builds, margins={})
    assert (unregistered["outcome"], unregistered["reason"]) == (
        bp.UNAVAILABLE,
        ca.MARGIN_UNREGISTERED,
    )
    no_noise = _run(tmp_path, builds, tolerance=None)
    assert (no_noise["outcome"], no_noise["reason"]) == (
        bp.UNAVAILABLE,
        bp.REPEAT_TOLERANCE_UNREGISTERED,
    )
    assert builds.asked == []  # nothing was rebuilt without a registered rule


def test_n_follows_the_config_not_a_constant(tmp_path):
    builds = Builds([0.70] * 5)
    result = _run(
        tmp_path,
        builds,
        n=5,
        margins={
            CHALLENGE: {"value": 0.0035, "n": 5, "measurement_digest": MEASUREMENT}
        },
    )
    assert result["outcome"] == bp.CHALLENGER and len(builds.asked) == 5
    assert result["private"]["n"] == 5


# --- the margins the Validator tabled -----------------------------------------------------------------------

#: Today's registered 2-SD margins (`koth_rebuild_noise.json`) and the tabled `2 * SD / sqrt(N)` values.
TABLE = {
    "f08-ribbed-bracket": (0.006062541759314569, {3: 0.00350, 5: 0.00271, 10: 0.00192}),
    "electric-motor-magnetics": (
        0.007923678234807158,
        {3: 0.00457, 5: 0.00354, 10: 0.00251},
    ),
    "f02": (0.04726369864563663, {3: 0.02729, 5: 0.02114, 10: 0.01495}),
    "chip-cold-plate": (0.01570813655321609, {3: 0.00907, 5: 0.00702, 10: 0.00497}),
}


@pytest.mark.parametrize("challenge", sorted(TABLE))
@pytest.mark.parametrize("n", [3, 5, 10])
def test_margin_n_matches_the_tabled_values(challenge, n):
    today, tabled = TABLE[challenge]
    seed_sd = (
        today / 2
    )  # the registered margin is 2 x SD and sigma is 0, so the floor does not bind
    assert ca.margin_n(seed_sd, n) == pytest.approx(today / math.sqrt(n))
    assert round(ca.margin_n(seed_sd, n), 5) == tabled[n]


def test_the_rebuild_noise_floor_binds_when_it_is_larger():
    assert ca.margin_n(0.001, 10, sigma=0.01) == pytest.approx(0.05)
    assert ca.margin_n(0.1, 10, sigma=0.0) == pytest.approx(0.2 / math.sqrt(10))
    for bad in (-1, float("nan"), True, None):
        with pytest.raises(ca.CrownAverageInvalid):
            ca.margin_n(bad, 10)
