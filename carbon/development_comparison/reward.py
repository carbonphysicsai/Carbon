"""Blocked real handoff plus explicit synthetic tests of existing C-REWARD math."""

from dataclasses import dataclass

from carbon.rewards.core import DevelopmentTerms, Record, advance_batch, opening

from .report import ComparisonRef, resolve_report


def reward_readiness(root, comparison: ComparisonRef):
    value = resolve_report(root, comparison)
    return {
        "schema": "carbon.cw1.development-reward-readiness.v1",
        "comparison_digest": comparison.digest,
        "contract_digest": value["contract_digest"],
        "source_receipts": [
            value["baseline"]["receipt_digest"],
            value["challenger"]["receipt_digest"],
        ],
        "status": "BLOCKED_NO_ACCEPTED_COMPARISON",
        "accepted_improvement": None,
        "score": None,
        "required": [
            "AUTHORIZED_ACCEPTANCE_AND_SCORE_RULE",
            "ELIGIBLE_ACTIVE_NONQUARANTINED_COMPARISON",
            "REWARD_BASELINE_RANGE_WINDOWS_ALLOCATION_POLICY",
            "FINALIZED_MINER_TO_UID_MAPPING",
            "WINNER_CAPABLE_PUBLICATION_PROFILE",
            "SEPARATE_EXACT_TRANSACTION_AUTHORITY",
        ],
        "paying": False,
    }


@dataclass(frozen=True)
class SyntheticAcceptedComparison:
    """Fixture-only interface example, never constructible from a real report."""

    record: Record
    activation_ms: int


def simulate_synthetic(
    terms: DevelopmentTerms, comparisons: tuple[SyntheticAcceptedComparison, ...]
):
    if (
        type(terms) is not DevelopmentTerms
        or type(comparisons) is not tuple
        or any(
            type(item) is not SyntheticAcceptedComparison
            or type(item.record) is not Record
            for item in comparisons
        )
    ):
        raise ValueError("explicit synthetic reward inputs required")
    state = opening(terms)
    states = [state]
    for item in comparisons:
        state = advance_batch(state, (item.record,), item.activation_ms)
        states.append(state)
    return tuple(states)
