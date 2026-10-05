"""Battery's Level-1 attack adapter and climb (GRAPHITE-L1-BUILD-01).

Claims tested:
- the (battery, 1) adapter is registered, attacks the registered variant (its
  contract digest is the variant's), and passes the core's validation;
- every Track A check is a family or a seam; the families' attacks hold at
  the real boundary while their weakened specimens fire;
- the climb over the variant gate: valid against attack panels under Level 0
  and Level 1, one ablation per Level-1 permission, the combined attacks and
  the clean rebuild; a broken ablation is a finding;
- the signed arm runs in the attack panel only;
- every climb run and report carries `rebuild: CPU-verified only`.
"""

from __future__ import annotations

import pytest

from carbon.agent_campaign.attack import adapter as core
from carbon.agent_campaign.attack import adapters
from carbon.agent_campaign.attack.adapters import battery_level1 as atk
from carbon.agent_campaign.graphite import phase4
from carbon.battery import level1
from carbon.challenge_readiness.admission import CHECKS
from carbon.reconstruction import development_variants as dv

A = adapters.load(atk.CHALLENGE_ID, 1)
LABEL = "rebuild: CPU-verified only"


def test_the_level1_adapter_attacks_the_registered_variant():
    variant = dv.variant(atk.CHALLENGE_ID, 1)
    assert A.level == 1 and A.contract_digest == variant.digest
    assert core.validate(A) is A
    found, found_variant = phase4.adapter_for(
        phase4.attack_modules(), atk.CHALLENGE_ID, 1
    )
    assert found is A and found_variant == variant
    assert set(A.checks()) == set(CHECKS[atk.b.TRACK])
    assert all(A.checks().values())
    assert {s.level for s in A.level_families()} == {1}
    surface = A.surface()
    assert surface["rebuild"] == LABEL and surface["permissions"] == list(
        variant.permissions()
    )
    inventory = A.permission_inventory()
    assert inventory["profile"] == "level-1"
    assert {p["id"] for p in inventory["permitted"]} >= set(variant.permissions())
    assert A.deterministic_baseline is None


def test_held_out_controls_differ_from_trained_ones():
    trained = {c.input_digest for c in A.controls("trained")}
    held = {c.input_digest for c in A.controls("held_out")}
    assert trained and held and not trained & held
    for family in A.families():
        names = {c.family for c in A.controls("held_out")}
        assert family.name in names


@pytest.mark.parametrize(
    "family",
    [
        "l1_expression_surface",
        "l1_declarative_only",
        "l1_permission_ablation",
        "l1_rebuild_identity",
    ],
)
def test_gate_families_hold_and_their_specimens_fire(family):
    spec = A.family_spec(family)
    attacks = spec.attacks()
    assert attacks
    breached = [n for n, v in attacks if spec.breached(spec.boundary(v))]
    assert not breached, breached
    silent = [n for n, v in attacks if not spec.breached(spec.specimen(v))]
    assert not silent, silent
    trained = [c for c in A.control_specs("trained") if c.family == family]
    assert trained and all(spec.control_check(c.value()) for c in trained)


@pytest.mark.parametrize("family", ["l1_degenerate_losses", "l1_nonfinite_typing"])
def test_trial_families_hold_and_their_specimens_fire(family):
    spec = A.family_spec(family)
    attacks = spec.attacks()
    results = {n: spec.boundary(v) for n, v in attacks}
    breached = [n for n, r in results.items() if spec.breached(r)]
    assert not breached, {n: results[n] for n in breached}
    silent = [n for n, v in attacks if not spec.breached(spec.specimen(v))]
    assert not silent, silent
    for result in results.values():
        trial = result.get("trial", result)
        assert trial["rebuild"] == LABEL


def test_the_oracle_reads_a_declared_attack_as_held():
    reading = A.assess(
        "l1_expression_surface",
        ("attack_unregistered_term", atk.attack_strategy("attack_unregistered_term")),
    )
    assert reading.reading == atk.b.HELD
    assert A.family_for("mcp__carbon__dry_validate") in (None, "l1_expression_surface")


# --- the climb --------------------------------------------------------------------------
def _fast(monkeypatch):
    """A smaller panel so the climb's shape is tested quickly; the full climb
    is `scripts/dev/l1_climb_report.py`."""
    monkeypatch.setattr(
        atk,
        "VALID",
        {
            k: atk.VALID[k]
            for k in (
                "valid_late_voltage",
                "valid_huber_like",
                "valid_plating_emphasis",
            )
        },
    )
    monkeypatch.setattr(
        atk,
        "ATTACKS",
        {
            k: atk.ATTACKS[k]
            for k in ("attack_adversarial_denominator", "attack_constant_loss")
        },
    )
    monkeypatch.setattr(atk, "COMBINED", {"combined_width": {"width": 128}})


def _owned(construction, arm=None):
    return {
        "stage": "trained",
        "exit": 0,
        "failed_infra": 0,
        "eligible": False,
        "rebuild": LABEL,
    }


def check_the_climb_holds(monkeypatch):
    _fast(monkeypatch)
    assert_holds(atk.climb_report(trial_fn=_owned))


def assert_holds(report):
    assert report["status"] == "COMPLETED", report["findings"]
    assert report["rebuild"] == LABEL
    assert report["development_variant"] == dv.variant(atk.CHALLENGE_ID, 1).digest
    assert report["claims"] == {
        "level_tested": False,
        "level_open_to_miners": False,
        "qualification": False,
    }
    steps = report["steps"]
    assert all(s["state"] == "RUN" for s in steps.values())
    # Every valid construction is refused at Level 0 and admitted at Level 1.
    for run in steps["valid"]["runs"]:
        assert run["status"] == ("REFUSED" if run["profile"] == "level-0" else "OK"), (
            run
        )
    # Each ablation refuses exactly the valid constructions that use it.
    for run in steps["ablation"]["runs"]:
        if run["kind"] == "construction":
            assert (run["status"] == "REFUSED") == run["expected_refusal"], run
    assert all(cov != "NOT_RUN" for cov in report["interaction_coverage"].values())
    assert all(
        r["outcome"]["rebuild"] == LABEL for r in steps["matched_attacks"]["runs"]
    )
    assert steps["reconstruction"]["runs"] and all(
        r["outcome"]["matches"] for r in steps["reconstruction"]["runs"]
    )


def test_the_climb_over_the_variant_gate_holds(monkeypatch):
    check_the_climb_holds(monkeypatch)


def test_the_signed_arm_runs_in_the_attack_panel_only(monkeypatch):
    report = atk.climb_report(arm=atk.SIGNED_ARM, trial_fn=_owned)
    assert report["status"] == "COMPLETED", report["findings"]
    panel = {r["item_id"] for r in report["steps"]["valid"]["runs"]}
    assert panel == {"panel_baseline"}
    attacks = {r["item_id"] for r in report["steps"]["matched_attacks"]["runs"]}
    assert attacks == set(atk.SIGNED_ATTACKS)
    assert report["arm"] == atk.SIGNED_ARM
    # A trial typed as infrastructure failure is a finding the climb keeps.
    report = atk.climb_report(
        arm=atk.SIGNED_ARM,
        trial_fn=lambda c, arm=None: {"stage": "trained", "exit": 0, "failed_infra": 3},
    )
    assert report["status"] == "COMPLETED_CONDITIONAL"
    assert {f["kind"] for f in report["findings"]} == {"attack_violation_reproduced"}


def test_an_ablation_the_gate_ignores_is_a_finding(monkeypatch):
    real = dv.compile_development

    def ignoring(strategy, variant_, *, without=()):
        return real(strategy, variant_)

    monkeypatch.setattr(dv, "compile_development", ignoring)
    _fast(monkeypatch)
    report = atk.climb_report(trial_fn=_owned)
    with pytest.raises(AssertionError):
        assert_holds(report)
    assert "permission_not_enforced" in {f["kind"] for f in report["findings"]}
    # A development climb continues past the finding and tags what follows.
    assert report["status"] == "COMPLETED_CONDITIONAL"


def test_the_climb_plan_names_every_level1_permission():
    items, _constructions, _judges = atk._items()
    plan = level1.climb_plan(
        panel=items["panel"],
        attacks=items["attacks"],
        attack_budget=len(items["attacks"]),
        combined=items["combined"],
        promising=lambda run: False,
    )
    assert plan.new_permissions == (level1.CORE, *level1.FAMILIES)
    assert plan.development_variant == dv.variant(atk.CHALLENGE_ID, 1).digest
    assert plan.ablated(level1.TIME).permissions == plan.expanded.permissions - {
        level1.TIME
    }
