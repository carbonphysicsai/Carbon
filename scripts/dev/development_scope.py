"""OWNER-CW1-DEVELOPMENT-CI-01: finite non-paying DEVELOPMENT acceptance manifest.

No prefix-based runtime exemption. Shared scientific/official, worker, reference,
reward-core, lifecycle and dependency changes retain their existing full scopes.
"""

DEVELOPMENT_RUNTIME = frozenset(
    {
        "carbon/audit/derivation.py",
        "carbon/audit/signing.py",
        "carbon/scoring/development.py",
        "carbon/measurement_runtime/development.py",
        "carbon/measurement_runtime/development_controls.py",
        "carbon/orchestration/development_feedback.py",
        "carbon/development_comparison/__init__.py",
        "carbon/development_comparison/__main__.py",
        "carbon/development_comparison/acceptance.py",
        "carbon/development_comparison/experiment.py",
        "carbon/development_comparison/metrics.py",
        "carbon/development_comparison/numerical.py",
        "carbon/development_comparison/numerical_worker.py",
        "carbon/development_comparison/owner.py",
        "carbon/development_comparison/report.py",
        "carbon/development_comparison/reward.py",
        "carbon/development_comparison/scoring_operator.py",
        "carbon/development_comparison/simulation.py",
        "carbon/development_comparison/sources.py",
        "carbon/development_session/__init__.py",
        "carbon/development_session/__main__.py",
        "carbon/development_session/agent.py",
        "carbon/development_session/budget.py",
        "carbon/development_session/contracts.py",
        "carbon/development_session/data.py",
        "carbon/development_session/evaluation.py",
        "carbon/development_session/handoff.py",
        "carbon/development_session/prediction.py",
        "carbon/development_session/profile.py",
        "carbon/development_session/service.py",
    }
)

DEVELOPMENT_TESTS = (
    "tests/cpu/test_cw1_development_scoring.py",
    "tests/cpu/test_cw1_development_comparison.py",
    "tests/cpu/test_cw1_burgers_session.py",
    "tests/cpu/test_cw1_development_testnet.py",
    "tests/cpu/test_cw1_development_testnet_operator.py",
    "tests/cpu/test_c03_worker_contract.py",
    "tests/cpu/test_c04_burgers_reference.py",
    "tests/cpu/test_c05_burgers_measurement.py",
    "tests/cpu/test_c06_signed_development_evidence.py",
    "tests/cpu/test_c07_development_orchestration.py",
    "tests/cpu/test_c08_authenticated_miner_mcp.py",
    "tests/cpu/test_c10_independent_reexecution.py",
    "tests/cpu/test_reward_core.py",
    "tests/cpu/test_reward_ledger.py",
    "tests/cpu/test_scoring_engine.py",
)

DEVELOPMENT_SUPPORT = frozenset(
    {
        "tests/invariants/test_c1_dependency_contract_boundaries.py",
        "tests/invariants/test_c05_measurement_runtime_boundaries.py",
        "tests/invariants/test_c06_audit_boundaries.py",
        "tests/invariants/test_c07_orchestration_boundaries.py",
    }
)

DEVELOPMENT_DOCS = frozenset(
    {
        "docs/development/CW1_DEVELOPMENT_SCORING_RULE.md",
        "docs/development/CW1_DEVELOPMENT_SCORING_LEARNING.md",
        "docs/development/CW1_DEVELOPMENT_SCORING_RESULTS.md",
        "docs/development/CW1_DEVELOPMENT_SCORING_NEXT_EXPERIMENT.md",
    }
)

# The existing canonical job independently validates these public source pins.
DEVELOPMENT_PUBLIC_DATA = frozenset(
    {
        "website/ask-carbon/knowledge/public-knowledge.v1.json",
    }
)
