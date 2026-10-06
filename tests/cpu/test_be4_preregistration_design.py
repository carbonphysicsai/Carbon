"""B-E4 proposed-design binding and non-qualifying analysis regressions."""

from __future__ import annotations

import json
import math
from dataclasses import replace
from pathlib import Path

import pytest
from b07c_fixtures import make_fixture

from carbon.gauntlet import (
    PROTECTED_TARGETS,
    AgentProfile,
    CanonicalIntervention,
    ConditionalLeakageObservation,
    DesignAnalysisClassification,
    DesignDocumentError,
    ExperimentalArm,
    GauntletRecord,
    IntervalBound,
    LeakageTargetBound,
    ProposedGauntletDesign,
    UtilityContrastBound,
    analytic_joint_leakage_clearance,
    analytic_joint_utility_power,
    analyze_intervention_diversity,
    classify_diversity_boundary,
    classify_leakage_boundary,
    classify_utility_boundary,
    complete_block_retention_probability,
    compose_design_analysis_gates,
    fixture_resolution_quality,
    parse_proposed_design,
    required_replicates_per_profile,
    run_nonqualifying_power_analysis,
)

ROOT = Path(__file__).resolve().parents[2]
DESIGN_PATH = ROOT / ".agent" / "preregistrations" / "B-E4_recommended_design_v2.json"
DESIGN_DIGEST = (
    "sha256:e2529e84d9d06882c5296b0a39b3f65219627fac49fbcb278950f753a8b66e37"
)
FIXTURE_DIGEST = "sha256:" + "a" * 64
FLOOR = 0.11767314940627138


def _design_text() -> str:
    return DESIGN_PATH.read_text(encoding="utf-8")


def _design() -> ProposedGauntletDesign:
    return parse_proposed_design(_design_text())


def test_proposed_design_is_content_bound_but_never_ratified() -> None:
    design = _design()
    assert design.design_digest == DESIGN_DIGEST
    assert not design.qualifying_execution_ready
    assert not design.is_verified_owner_ratified
    assert len(design.decision_keys) == 8
    assert "NO_HUMAN_OWNER_HAS_APPROVED_THIS_PROPOSAL" in design.readiness_blockers
    assert repr(design) == "ProposedGauntletDesign(<design-analysis-only>)"

    with pytest.raises(TypeError, match="exact preregistration"):
        GauntletRecord(design, (), (), (), ())  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="exact nominal"):
        ProposedGauntletDesign(
            b"{}",
            "sha256:" + "0" * 64,
            design.decision_keys,
            design.readiness_blockers,
            _factory_token=object(),
        )


def test_any_bound_profile_change_changes_the_design_digest() -> None:
    payload = json.loads(_design_text())
    payload["execution_design"]["agent_profiles"][0]["retry_policy"] += "; changed"
    changed = parse_proposed_design(json.dumps(payload))
    assert changed.design_digest != DESIGN_DIGEST


def test_proposal_rejects_approval_claims_ratifications_and_duplicate_keys() -> None:
    payload = json.loads(_design_text())
    payload["design_inputs"]["utility_estimand"]["status"] = "APPROVED"
    with pytest.raises(DesignDocumentError, match="remain PROPOSED"):
        parse_proposed_design(json.dumps(payload))

    payload = json.loads(_design_text())
    payload["ratifications"] = [{"owner": "SCIENCE"}]
    with pytest.raises(DesignDocumentError, match="cannot contain ratifications"):
        parse_proposed_design(json.dumps(payload))

    duplicate = _design_text().replace(
        "{", '{"status":"PROPOSED_DESIGN_ANALYSIS_ONLY",', 1
    )
    with pytest.raises(DesignDocumentError, match="duplicate JSON key"):
        parse_proposed_design(duplicate)


@pytest.mark.parametrize(
    ("mutate", "match"),
    (
        (
            lambda value: value["execution_design"]["matrix"].__setitem__(
                "planned_runs", 5279
            ),
            "planned run count",
        ),
        (
            lambda value: value["execution_design"]["matrix"].__setitem__(
                "planned_runs", 5280.0
            ),
            "bounded positive integer",
        ),
        (
            lambda value: value["readiness"].__setitem__(
                "qualifying_execution_ready", True
            ),
            "execution-blocked",
        ),
        (
            lambda value: value["execution_design"]["budgets"].__setitem__(
                "numeric_caps_ready", True
            ),
            "must remain unavailable",
        ),
        (
            lambda value: value["execution_design"]["analysis"].__setitem__(
                "effect_floor", 0.2
            ),
            "registered practical_effect_floor contradicts",
        ),
        (
            lambda value: value["execution_design"]["analysis"].__setitem__(
                "leakage_planning_cluster_sd", 0.5
            ),
            "cannot meet the registered clearance",
        ),
        (
            lambda value: value["execution_design"]["analysis"].__setitem__(
                "utility_joint_constraints", 5
            ),
            "requires three and six constraints",
        ),
        (
            lambda value: value["execution_design"]["shadow_campaign"].__setitem__(
                "transcript_cluster_count", 1319
            ),
            "contradict the registered matrix",
        ),
    ),
)
def test_proposal_rejects_structural_and_numerical_contradictions(
    mutate: object, match: str
) -> None:
    payload = json.loads(_design_text())
    mutate(payload)  # type: ignore[operator]
    with pytest.raises(DesignDocumentError, match=match):
        parse_proposed_design(json.dumps(payload))


def test_proposal_rejects_changed_registered_and_computed_values() -> None:
    payload = json.loads(_design_text())
    payload["execution_design"]["analysis"]["effect_floor"] = 0.2
    payload["design_inputs"]["practical_effect_floor"]["registered_value"] = 0.2
    with pytest.raises(DesignDocumentError, match="fixture resolution"):
        parse_proposed_design(json.dumps(payload))

    payload = json.loads(_design_text())
    payload["execution_design"]["matrix"]["replicates_per_profile"] = 268
    payload["execution_design"]["matrix"]["planned_runs"] = 5360
    payload["execution_design"]["matrix"]["maximum_runs"] = 5880
    payload["execution_design"]["resource_estimate"]["fixture_units_planned"] = (
        5360 * 189
    )
    payload["execution_design"]["resource_estimate"][
        "fixture_units_maximum_with_reserves"
    ] = (5880 * 189)
    payload["execution_design"]["shadow_campaign"]["transcript_cluster_count"] = 1340
    registered = payload["design_inputs"]["matched_time_compute_budgets"][
        "registered_value"
    ]
    registered["replicates_per_profile"] = 268
    with pytest.raises(DesignDocumentError, match="replicate count contradicts"):
        parse_proposed_design(json.dumps(payload))

    payload = json.loads(_design_text())
    payload["execution_design"]["analysis"]["leakage_joint_clearance_target"] = (
        math.nextafter(1.0, 0.0)
    )
    with pytest.raises(DesignDocumentError, match="leakage probability design"):
        parse_proposed_design(json.dumps(payload))


@pytest.mark.parametrize(
    "path",
    (
        ("readiness", "blockers", 0),
        ("execution_design", "shadow_campaign", "protected_targets", 0),
    ),
)
def test_hostile_unicode_is_normalized_to_design_error(
    path: tuple[object, ...],
) -> None:
    payload = json.loads(_design_text())
    target: object = payload
    for part in path[:-1]:
        target = target[part]  # type: ignore[index]
    target[path[-1]] = "\ud800"  # type: ignore[index]
    hostile = json.dumps(payload)
    with pytest.raises(DesignDocumentError, match="valid UTF-8"):
        parse_proposed_design(hostile)


def test_fixture_quality_and_power_analysis_are_reproducible() -> None:
    assert fixture_resolution_quality(90.0) == 0.0
    assert fixture_resolution_quality(36.5) == 1.0
    assert fixture_resolution_quality(45.2) == pytest.approx(0.7646537011874572)
    with pytest.raises(ValueError, match="numeric separation"):
        fixture_resolution_quality(
            1e308,
            loss_best=1e308,
            loss_worst=1.0000000000000002e308,
        )

    design = _design()
    first = run_nonqualifying_power_analysis(design=design)
    second = run_nonqualifying_power_analysis(design=design)
    assert first == second
    assert first.replicates_per_profile_unrounded == pytest.approx(261.6356640572783)
    assert first.replicates_per_profile == 264
    assert first.reserve_blocks_per_profile == 26
    assert first.planned_runs == 5280
    assert first.maximum_runs == 5800
    assert first.fixture_units_planned == 997920
    assert first.fixture_units_maximum == 1096200
    assert first.practical_effect_floor == pytest.approx(FLOOR)
    assert first.primary_joint_power_lower_bound == pytest.approx(0.9523378465728866)
    assert first.joint_power_lower_bound == pytest.approx(0.9046756931457731)
    assert first.leakage_sd_ceiling == pytest.approx(0.4323807791419945)
    assert first.leakage_joint_clearance_lower_bound == pytest.approx(0.957111808457316)
    assert first.profile_retention_at_ceiling == pytest.approx(0.9984085742380678)
    assert first.matrix_retention_at_ceiling == pytest.approx(0.9920428711903392)
    assert first.matrix_retention_at_double_ceiling == 0.0
    assert 0.89 < first.simulation_utility_independent < 0.92
    assert 0.91 < first.simulation_utility_shared_correlation < 0.95
    assert 0.005 < first.simulation_floor_false_pass < 0.03
    assert 0.94 < first.simulation_leakage_independent < 0.98
    assert 0.94 < first.simulation_leakage_shared_correlation < 0.99
    assert 0.45 < first.simulation_leakage_over_limit_detection < 0.60
    assert first.simulation_leakage_over_limit_false_clearance < 0.01
    assert (
        0.40
        < 1.0
        - first.simulation_leakage_over_limit_detection
        - first.simulation_leakage_over_limit_false_clearance
        < 0.55
    )


def test_analytic_sensitivities_and_retention_are_dependence_robust() -> None:
    assert required_replicates_per_profile(
        paired_sd=1.0,
        practical_effect_floor=FLOOR,
        true_effect=2.0 * FLOOR,
        familywise_alpha=0.05,
        joint_power_target=0.9,
        simultaneous_contrasts=3,
        joint_constraints=6,
    ) == pytest.approx(261.6356640572783)
    assert analytic_joint_utility_power(
        replicates_per_profile=264,
        paired_sd=1.0,
        joint_constraints=3,
    ) == pytest.approx(0.9523378465728866)
    assert analytic_joint_utility_power(
        replicates_per_profile=264, paired_sd=1.0
    ) == pytest.approx(0.9046756931457731)
    assert analytic_joint_utility_power(
        replicates_per_profile=296,
        paired_sd=1.0,
        simultaneous_contrasts=6,
        joint_constraints=6,
    ) == pytest.approx(0.901224995818356)
    assert analytic_joint_utility_power(
        replicates_per_profile=100, paired_sd=0.6182320680314055
    ) == pytest.approx(0.9)
    assert analytic_joint_leakage_clearance(
        transcript_clusters=1320, cluster_sd=0.4
    ) == pytest.approx(0.957111808457316)

    profile = complete_block_retention_probability(
        required_blocks=264,
        reserve_blocks=26,
        block_failure_probability=0.05,
    )
    assert profile == pytest.approx(0.9984085742380678)
    assert max(0.0, 1.0 - 5.0 * (1.0 - profile)) == pytest.approx(0.9920428711903392)
    assert complete_block_retention_probability(
        required_blocks=1000,
        reserve_blocks=1000,
        block_failure_probability=0.05,
    ) == pytest.approx(1.0)


def test_current_fixture_unit_ceiling_is_derived_from_owner_plans(
    tmp_path: Path,
) -> None:
    fixture = make_fixture(tmp_path)
    quantities: dict[int, int] = {}
    units = set()
    for level in (1, 2):
        request = fixture.request(
            "practice", key=f"be4-resource-level-{level}-00000001"
        )
        strategy = {
            **fixture.strategy,
            "parameters": {"fixture_sampling_level": level},
        }
        request = replace(
            request,
            task_spec=replace(request.task_spec, strategy=strategy),
        )
        started = fixture.provider.start_research_task(request)
        terminal = fixture.provider.run_queued_task(started.task.task_id)
        record = fixture.provider.get_experiment_record(terminal.task_id)
        requirements = record.resolved_strategies[
            0
        ].resolved_plan.static_resource_requirements
        assert len(requirements) == 1
        requirement = requirements[0]
        assert requirement.dimension_id == "abstract_units"
        quantities[level] = requirement.quantity
        units.add(requirement.unit_ref)

    assert len(units) == 1
    assert quantities == {1: 9, 2: 13}
    paired_attempt_units = quantities[1] + quantities[2]
    assert paired_attempt_units == 22
    assert 8 * paired_attempt_units + quantities[2] == 189


def _contrasts(
    *,
    primary: IntervalBound,
    transfer: IntervalBound,
    counts: tuple[int, int, int] = (4, 4, 4),
) -> tuple[UtilityContrastBound, ...]:
    baselines = (
        ExperimentalArm.NO_PRIOR,
        ExperimentalArm.GENERIC_PRIOR,
        ExperimentalArm.V1_DIRECTIVE_PRIOR,
    )
    return tuple(
        UtilityContrastBound(baseline, primary, transfer, count)
        for baseline, count in zip(baselines, counts, strict=True)
    )


def _utility_classification(
    *,
    primary: IntervalBound,
    transfer: IntervalBound,
    counts: tuple[int, int, int] = (4, 4, 4),
    complete: bool = True,
) -> DesignAnalysisClassification:
    return classify_utility_boundary(
        contrasts=_contrasts(primary=primary, transfer=transfer, counts=counts),
        practical_effect_floor=FLOOR,
        complete_blocks_available=complete,
    )


def test_utility_rule_boundaries_missingness_and_heterogeneity() -> None:
    assert (
        _utility_classification(
            primary=IntervalBound(FLOOR + 0.001, FLOOR + 0.02),
            transfer=IntervalBound(-FLOOR + 0.001, 0.02),
        )
        is DesignAnalysisClassification.PASS_CONDITION
    )
    assert (
        _utility_classification(
            primary=IntervalBound(FLOOR, FLOOR + 0.02),
            transfer=IntervalBound(-FLOOR + 0.001, 0.02),
        )
        is DesignAnalysisClassification.INDETERMINATE_CONDITION
    )
    assert (
        _utility_classification(
            primary=IntervalBound(FLOOR - 0.02, FLOOR),
            transfer=IntervalBound(-FLOOR + 0.001, 0.02),
        )
        is DesignAnalysisClassification.FAIL_CONDITION
    )
    assert (
        _utility_classification(
            primary=IntervalBound(FLOOR + 0.001, FLOOR + 0.02),
            transfer=IntervalBound(-FLOOR + 0.001, 0.02),
            counts=(4, 3, 4),
        )
        is DesignAnalysisClassification.INDETERMINATE_CONDITION
    )
    assert (
        _utility_classification(
            primary=IntervalBound(FLOOR + 0.001, FLOOR + 0.02),
            transfer=IntervalBound(-FLOOR + 0.001, 0.02),
            complete=False,
        )
        is DesignAnalysisClassification.INDETERMINATE_CONDITION
    )

    valid = _contrasts(
        primary=IntervalBound(0.2, 0.3), transfer=IntervalBound(0.0, 0.1)
    )
    with pytest.raises(TypeError, match="utility boundary"):
        classify_utility_boundary(
            contrasts=(valid[0], valid[0], valid[2]),
            practical_effect_floor=FLOOR,
            complete_blocks_available=True,
        )


def _leakage_bounds(interval: IntervalBound) -> tuple[LeakageTargetBound, ...]:
    return tuple(LeakageTargetBound(target, interval) for target in PROTECTED_TARGETS)


def test_leakage_rule_exact_below_above_and_target_substitution() -> None:
    limit = 0.05
    assert (
        classify_leakage_boundary(
            _leakage_bounds(IntervalBound(-0.01, limit)),
            expected_targets=PROTECTED_TARGETS,
            limit=limit,
        )
        is DesignAnalysisClassification.PASS_CONDITION
    )
    assert (
        classify_leakage_boundary(
            _leakage_bounds(IntervalBound(0.049, 0.051)),
            expected_targets=PROTECTED_TARGETS,
            limit=limit,
        )
        is DesignAnalysisClassification.INDETERMINATE_CONDITION
    )
    assert (
        classify_leakage_boundary(
            _leakage_bounds(IntervalBound(0.050001, 0.06)),
            expected_targets=PROTECTED_TARGETS,
            limit=limit,
        )
        is DesignAnalysisClassification.FAIL_CONDITION
    )

    valid = _leakage_bounds(IntervalBound(-0.01, limit))
    with pytest.raises(TypeError, match="leakage boundary"):
        classify_leakage_boundary(
            (valid[0], valid[0], valid[2], valid[3]),
            expected_targets=PROTECTED_TARGETS,
            limit=limit,
        )


def test_gate_composition_preserves_failure_and_indeterminacy() -> None:
    passed = DesignAnalysisClassification.PASS_CONDITION
    failed = DesignAnalysisClassification.FAIL_CONDITION
    unknown = DesignAnalysisClassification.INDETERMINATE_CONDITION
    assert (
        compose_design_analysis_gates(utility=passed, diversity=passed, leakage=passed)
        is passed
    )
    assert (
        compose_design_analysis_gates(utility=unknown, diversity=passed, leakage=passed)
        is unknown
    )
    assert (
        compose_design_analysis_gates(utility=unknown, diversity=failed, leakage=passed)
        is failed
    )


def test_raw_conditional_leakage_statistic_retains_signed_estimates() -> None:
    observation = ConditionalLeakageObservation(0.2, 0.3, -0.1, FIXTURE_DIGEST)
    assert observation.conditional_leakage_statistic == -0.1
    with pytest.raises(ValueError, match="finite float"):
        ConditionalLeakageObservation(0.2, 0.3, float("nan"), FIXTURE_DIGEST)


def _interventions(
    family_counts: tuple[tuple[str, int], ...],
    *,
    profiles: tuple[AgentProfile, ...] = tuple(AgentProfile),
) -> tuple[CanonicalIntervention, ...]:
    return tuple(
        CanonicalIntervention(
            profile,
            ExperimentalArm.V2_TEST_ONLY_PRIOR,
            replicate,
            family,
            f"semantic-{family}",
            f"lineage-{profile.value}-{family}-{replicate}",
            True,
        )
        for profile in profiles
        for family, count in family_counts
        for replicate in range(count)
    )


def _diversity(
    values: tuple[CanonicalIntervention, ...], *, complete: bool = True
) -> object:
    return analyze_intervention_diversity(
        values,
        expected_replicates_per_profile=20,
        minimum_profile_prevalence=0.10,
        matrix_complete=complete,
    )


def test_diversity_collapses_duplicates_and_resists_concentration() -> None:
    balanced = _interventions((("family-a", 4), ("family-b", 3), ("family-c", 3)))
    analysis = _diversity(balanced)
    assert analysis.observed_families == 3
    assert analysis.supported_families == 3
    assert analysis.maximum_family_share == pytest.approx(0.4)
    assert analysis.inverse_simpson == pytest.approx(1.0 / 0.34)
    assert analysis.guarded_effective_diversity == pytest.approx(1.0 / 0.34)

    duplicate_spam = tuple(
        item
        for item in balanced
        if item.family_identity == "family-a"
        for _ in range(20)
    )
    assert _diversity((*balanced, *duplicate_spam)) == analysis

    dominant = _interventions((("family-a", 16), ("family-b", 2), ("family-c", 2)))
    dominated = _diversity(dominant)
    assert dominated.maximum_family_share == pytest.approx(0.8)
    assert dominated.guarded_effective_diversity == 0.0

    assert (
        classify_diversity_boundary(
            balanced,
            expected_replicates_per_profile=20,
            minimum_profile_prevalence=0.10,
            matrix_complete=True,
            floor=2.0,
        )
        is DesignAnalysisClassification.PASS_CONDITION
    )


def test_diversity_rejects_aliases_lineage_conflicts_and_rare_family_spam() -> None:
    base = _interventions((("family-a", 2), ("family-b", 2), ("family-c", 2)))
    base_analysis = _diversity(base)
    rare = tuple(
        CanonicalIntervention(
            AgentProfile.PLANNER,
            ExperimentalArm.V2_TEST_ONLY_PRIOR,
            replicate % 20,
            f"rare-{replicate}",
            f"rare-semantic-{replicate}",
            f"rare-lineage-{replicate}",
            True,
        )
        for replicate in range(20)
    )
    spammed = _diversity((*base, *rare))
    assert (
        spammed.guarded_effective_diversity < base_analysis.guarded_effective_diversity
    )

    alias = replace(
        base[0],
        family_identity="family-alias",
        lineage_root_identity="new-lineage",
    )
    with pytest.raises(ValueError, match="semantic bucket"):
        _diversity((*base, alias))

    lineage_conflict = replace(
        base[0],
        family_identity="family-other",
        semantic_bucket_identity="semantic-other",
    )
    with pytest.raises(ValueError, match="lineage"):
        _diversity((*base, lineage_conflict))

    with pytest.raises(TypeError, match="exact nominal"):
        CanonicalIntervention(
            AgentProfile.PLANNER,
            ExperimentalArm.NO_PRIOR,
            0,
            "family-a",
            "semantic-a",
            "lineage-a",
            True,
        )


def test_diversity_distinguishes_missing_matrix_from_observed_failure() -> None:
    planner_only = _interventions(
        (("family-a", 2), ("family-b", 2), ("family-c", 2)),
        profiles=(AgentProfile.PLANNER,),
    )
    assert (
        classify_diversity_boundary(
            planner_only,
            expected_replicates_per_profile=20,
            minimum_profile_prevalence=0.10,
            matrix_complete=False,
            floor=2.0,
        )
        is DesignAnalysisClassification.INDETERMINATE_CONDITION
    )
    assert (
        classify_diversity_boundary(
            planner_only,
            expected_replicates_per_profile=20,
            minimum_profile_prevalence=0.10,
            matrix_complete=True,
            floor=2.0,
        )
        is DesignAnalysisClassification.FAIL_CONDITION
    )
