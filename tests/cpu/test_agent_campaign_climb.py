"""The climb harness (GRAPHITE-ADMISSION-01 slice B; handoff §8), with fake runs.

No model, pod or worker runs: every construction, attack and rebuild is a fake
whose outcome the test sets.
"""

from __future__ import annotations

import hashlib

import pytest

from carbon.agent_campaign import climb
from carbon.battery import level1_draft as l1
from carbon.reconstruction import capability_registry as cr

EARLIER = frozenset({"architecture.width", "optimizer.learning_rate"})
NEW = "objective.loss_expressions"


def _digest(*parts):
    return "sha256:" + hashlib.sha256("|".join(parts).encode()).hexdigest()


class Fake:
    """Fake runners. A run needing an absent permission is REFUSED unless the
    profile's boundary is `leaky`."""

    def __init__(self, *, violations=(), mismatches=(), infra=(), leaky=()):
        self.violations, self.mismatches = set(violations), set(mismatches)
        self.infra, self.leaky = set(infra), set(leaky)
        self.calls = []

    def _status(self, profile, item):
        self.calls.append((profile.name, item.item_id))
        if (profile.name, item.item_id) in self.infra:
            return "FAILED_INFRA"
        if not item.uses <= profile.permissions and profile.name not in self.leaky:
            return "REFUSED"
        return "OK"

    def construct(self, profile, item):
        status = self._status(profile, item)
        out = {"status": status}
        if status == "OK":
            out["artifact_digest"] = _digest(profile.digest, item.item_id)
        return out

    def attack(self, profile, item):
        status = self._status(profile, item)
        return {
            "status": status,
            "violation_reproduced": status == "OK"
            and (profile.name, item.item_id) in self.violations,
            "evidence_digest": _digest("evidence", profile.name, item.item_id),
        }

    def rebuild(self, run):
        return {
            "status": "OK",
            "matches": run["item_id"] not in self.mismatches,
            "rebuilt_digest": run["outcome"]["artifact_digest"],
        }

    def runners(self):
        return climb.Runners(self.construct, self.attack, self.rebuild)


def plan(*, attacks=None, budget=None, combined=None, **changes):
    previous = climb.profile("level-0", base="sha256:" + "c" * 64, permissions=EARLIER)
    expanded = climb.profile(
        "level-1", base="sha256:" + "c" * 64, permissions=EARLIER | {NEW}
    )
    attacks = (
        attacks
        if attacks is not None
        else tuple(
            climb.Item(f"attack-{n}", frozenset({NEW}), "a high score for a bad model")
            for n in range(3)
        )
    )
    combined = (
        combined
        if combined is not None
        else (
            climb.Item(
                "combined-lr-loss",
                frozenset({NEW, "optimizer.learning_rate"}),
                "the two permissions together reach a forbidden state",
            ),
        )
    )
    fields = {
        "challenge": "synthetic-heat-sink-v1",
        "level": 1,
        "previous": previous,
        "expanded": expanded,
        "new_permissions": (NEW,),
        "panel": (
            climb.Item("menu", frozenset({"architecture.width"})),
            climb.Item("expression", frozenset({NEW})),
        ),
        "attacks": attacks,
        "attack_budget": len(attacks) if budget is None else budget,
        "combined": combined,
        "promising": lambda run: run["item_id"] == "expression",
    }
    return climb.ClimbPlan(**{**fields, **changes})


def test_a_clean_climb_runs_every_step_with_matched_budgets():
    fake = Fake()
    report = climb.climb(plan(), fake.runners())
    assert report["status"] == "COMPLETED" and report["findings"] == []
    assert {s: v["state"] for s, v in report["steps"].items()} == dict.fromkeys(
        climb.STEPS, "RUN"
    )
    attacks = report["steps"]["matched_attacks"]["runs"]
    per_profile = {
        p: sum(r["profile"] == p for r in attacks) for p in ("level-0", "level-1")
    }
    assert per_profile == {"level-0": 3, "level-1": 3}
    # The new permission is refused where it is absent, and runs where it is.
    by = {(r["profile"], r["item_id"]): r for r in report["steps"]["valid"]["runs"]}
    assert by[("level-0", "expression")]["status"] == "REFUSED"
    assert by[("level-0", "expression")]["expected_refusal"] is True
    assert by[("level-1", "expression")]["status"] == "OK"
    ablated = report["steps"]["ablation"]["runs"]
    assert {r["profile"] for r in ablated} == {f"ablated:{NEW}"}
    assert all(r["status"] == "REFUSED" for r in ablated if r["item_id"] != "menu")
    assert report["interaction_coverage"] == {NEW: ["combined-lr-loss"]}
    (rebuilt,) = report["steps"]["reconstruction"]["runs"]
    assert rebuilt["item_id"] == "expression" and rebuilt["outcome"]["matches"]
    assert set(report["profiles"]) == {"level-0", "level-1", f"ablated:{NEW}"}
    assert len(set(report["profiles"].values())) == 3
    assert not any(report["claims"].values())


@pytest.mark.parametrize(
    "changes, code",
    [
        ({"budget": 2}, "attack_budget_must_match_the_attack_set"),
        ({"new_permissions": ("architecture.width",)}, "new_permissions_are_new"),
        ({"level": 0}, "level_is_1_to_5"),
        ({"panel": ()}, "a_legitimate_panel_is_required"),
        (
            {"attacks": (climb.Item("silent", frozenset({NEW})),)},
            "an_attack_declares_its_violation",
        ),
    ],
)
def test_a_malformed_plan_is_refused(changes, code):
    with pytest.raises(climb.ClimbError, match=code):
        plan(**changes)


def test_a_reproduced_violation_stops_the_climb():
    fake = Fake(violations={("level-1", "attack-1")})
    report = climb.climb(plan(), fake.runners())
    assert report["status"] == "STOPPED_ON_FINDING"
    (finding,) = report["findings"]
    assert finding["kind"] == "attack_violation_reproduced"
    assert finding["declared_violation"] == "a high score for a bad model"
    # The step in progress completed, matched; later steps did not run.
    assert report["steps"]["matched_attacks"]["state"] == "RUN"
    for step in ("ablation", "interactions", "reconstruction"):
        assert report["steps"][step] == {
            "state": "NOT_RUN",
            "reason": "stopped_on_finding",
            "runs": [],
        }
    assert report["interaction_coverage"] == {NEW: "NOT_RUN"}


def test_a_removed_permission_that_still_runs_is_a_finding():
    fake = Fake(leaky={f"ablated:{NEW}"})
    report = climb.climb(plan(), fake.runners())
    assert report["status"] == "STOPPED_ON_FINDING"
    kinds = {f["kind"] for f in report["findings"]}
    assert kinds == {"permission_not_enforced"}
    assert {f["profile"] for f in report["findings"]} == {f"ablated:{NEW}"}


def test_a_rebuild_that_does_not_match_is_a_finding():
    report = climb.climb(plan(), Fake(mismatches={"expression"}).runners())
    assert report["status"] == "STOPPED_ON_FINDING"
    (finding,) = report["findings"]
    assert finding["kind"] == "reconstruction_mismatch"


def test_an_infrastructure_failure_is_recorded_never_a_finding():
    fake = Fake(infra={("level-1", "attack-0"), ("level-0", "menu")})
    report = climb.climb(plan(), fake.runners())
    assert report["status"] == "COMPLETED" and report["findings"] == []
    assert report["infrastructure_failures"] == 2
    # It still counted against the matched budget: no retry was made.
    attacks = report["steps"]["matched_attacks"]["runs"]
    assert sum(r["profile"] == "level-1" for r in attacks) == 3


def test_an_unexercised_interaction_is_not_run_never_passed():
    report = climb.climb(plan(combined=()), Fake().runners())
    assert report["interaction_coverage"] == {NEW: "NOT_RUN"}
    assert report["steps"]["interactions"]["runs"] == []


def test_battery_level1_plan_pins_its_profiles_and_opens_nothing():
    digest_before = cr.contract(cr.BATTERY_CHALLENGE).digest
    attacks = (
        climb.Item(
            "score-shaping", frozenset({l1.PERMISSION}), "a loss that games rule v2"
        ),
        climb.Item(
            "degenerate-division",
            frozenset({l1.PERMISSION}),
            "a nonfinite fit accepted",
        ),
    )
    battery = l1.climb_plan(
        panel=(
            climb.Item("menu-h1", frozenset({"objective.h1_weight"})),
            climb.Item("expression-log1p", frozenset({l1.PERMISSION})),
        ),
        attacks=attacks,
        attack_budget=2,
        combined=(
            climb.Item(
                "expression-with-hard-examples",
                frozenset({l1.PERMISSION, "training_data.hard_example_weight"}),
                "the two together overweight the scored region",
            ),
        ),
        promising=lambda run: run["item_id"].startswith("expression"),
    )
    assert l1.PERMISSION not in battery.previous.permissions
    assert battery.expanded.permissions == battery.previous.permissions | {
        l1.PERMISSION
    }
    report = climb.climb(battery, Fake().runners())
    assert report["challenge"] == cr.BATTERY_CHALLENGE and report["level"] == 1
    assert report["status"] == "COMPLETED"
    assert report["interaction_coverage"] == {
        l1.PERMISSION: ["expression-with-hard-examples"]
    }
    assert cr.contract(cr.BATTERY_CHALLENGE).digest == digest_before
    assert not any(report["claims"].values())
