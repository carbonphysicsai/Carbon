from scripts.dev.battery.v3_rule_robustness import report


def test_synthetic_attacks_use_registered_rule_and_stay_synthetic():
    result = report()
    assert result["evidence_class"] == "SYNTHETIC_ONLY"
    assert result["rule"] == "G-FEAS/A-Q@0.05"
    cases = result["cases"]
    assert cases["regret_tail"]["raw_score_delta"] == 0
    assert (
        cases["regret_tail"]["attack"]["max_q3_regret"]
        > cases["regret_tail"]["baseline"]["max_q3_regret"]
    )
    assert cases["unnecessary_abstention"]["raw_score_delta"] > 0
    assert cases["unnecessary_abstention"]["synthetic_loss_delta"] > 0
    assert cases["feasibility_edge"]["attack"]["eligible_under_gate"]
    assert cases["feasibility_edge"]["raw_score_delta"] == 0
    assert cases["accuracy_regret_tradeoff"]["raw_score_delta"] > 0
    assert cases["accuracy_regret_tradeoff"]["synthetic_loss_delta"] > 0


def test_missing_gate_is_not_eligible():
    from carbon.battery.value import score_tuning
    from scripts.dev.battery.v3_rule_robustness import REGISTRY, _member

    candidate = score_tuning.load_registry(REGISTRY)[0]["G-FEAS/A-Q@0.05"]
    row = _member(candidate, accuracy=0.8, regrets=[0.1], false_feasible=None, loss=0.1)
    assert not row["eligible_under_gate"]


def test_gate_boundary_uses_current_scorer_strictness():
    from carbon.battery.value import score_tuning
    from scripts.dev.battery.v3_rule_robustness import REGISTRY, _member

    candidate = score_tuning.load_registry(REGISTRY)[0]["G-FEAS/A-Q@0.05"]
    at_cutoff = _member(
        candidate, accuracy=0.8, regrets=[0.1], false_feasible=1 / 20, loss=0.1
    )
    below_cutoff = _member(
        candidate, accuracy=0.8, regrets=[0.1], false_feasible=1 / 21, loss=0.1
    )
    assert at_cutoff["gate"] == "FAIL"
    assert below_cutoff["gate"] == "PASS"
