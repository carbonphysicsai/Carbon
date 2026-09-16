"""Non-paying DEVELOPMENT simulation adapter over C-REWARD's existing core."""

from dataclasses import dataclass
from carbon.development_session.profile import canonical, digest
from carbon.rewards.core import (
    DevelopmentTerms,
    Record,
    Holder,
    Q12,
    DAY_MS,
    opening,
    advance_batch,
    targets,
    WinnerStatus,
)
from carbon.scoring.development import rule_digest
from .acceptance import DevelopmentAcceptanceRef, resolve_acceptance


@dataclass(frozen=True)
class SimulationResult:
    context: str
    state: object
    events: tuple[str, ...]
    artifacts: tuple[str, ...]
    targets: object
    clock_ms: int
    provenance: str = "AUTHENTIC_ACCEPTED_DEVELOPMENT_NONPAYING"
    paying: bool = False
    network_eligible: bool = False


def simulate(refs: tuple[DevelopmentAcceptanceRef, ...], *, clock_ms: int):
    if type(refs) is not tuple or not refs:
        raise ValueError("accepted comparison sequence required")
    state = None
    events = []
    artifacts = []
    previous = None
    context = None
    for ref in refs:
        report = resolve_acceptance(
            ref
        )  # ACTIVE/C-10/signature/artifact checks at every downstream use.
        d = report["decision"]
        if (
            report["rule_digest"] != rule_digest()
            or report["prospective"] is not True
            or d["disposition"] != "ACCEPTED_DEVELOPMENT_IMPROVEMENT"
            or d["accepted_improvement"] is not True
            or any(
                d[k] is not False
                for k in (
                    "official_eligible",
                    "protected_eligible",
                    "settlement_eligible",
                    "network_eligible",
                )
            )
        ):
            raise ValueError("eligible prospective DEVELOPMENT improvement required")
        base, challenger = report["baseline"], report["challenger"]
        key = digest(
            canonical(
                {
                    "rule": rule_digest(),
                    "cohort": base["binding"]["sampling_plan_digest"],
                    "training": base["binding"]["training_data_commitment"],
                }
            )
        )[7:]
        if context is not None and key != context:
            raise ValueError("mixed simulation context")
        context = key
        artifact = challenger["binding"]["strategy_digest"][7:]
        if state is None:
            baseline_score = float(d["baseline"]["score"])
            if not 0 <= baseline_score < 1:
                raise ValueError("positive score headroom required")
            state = opening(
                DevelopmentTerms(
                    context,
                    base["receipt_digest"][7:],
                    baseline_score.hex(),
                    "1",
                    0,
                    7 * DAY_MS,
                    14 * DAY_MS,
                    ((0, Q12),),
                )
            )
            previous = base["receipt_digest"]
            artifacts.append(base["binding"]["strategy_digest"][7:])
        if ref.report_digest in events:
            continue  # Query/replay cannot reset activation.
        if artifact in artifacts:
            raise ValueError("copying a construction cannot renew credit")
        if (
            base["receipt_digest"] != previous
            or float(d["baseline"]["score"]).hex() != state.record_hex
        ):
            raise ValueError("comparison is not against current simulation incumbent")
        # Explicit simulation clock is ordered by admitted comparison sequence.
        # No wall-clock, block-time, registration or payment claim is inferred.
        activation = len(events) * 1000
        record = Record(
            ref.report_digest[7:],
            artifact,
            float(d["challenger"]["score"]).hex(),
            Holder(
                challenger["authenticated_hotkey"],
                "NONPAYING_NO_CHAIN_OWNER_ASSERTION",
                0,
            ),
            len(events),
        )
        state = advance_batch(state, (record,), activation)
        events.append(ref.report_digest)
        artifacts.append(artifact)
        previous = challenger["receipt_digest"]
    return SimulationResult(
        context,
        state,
        tuple(events),
        tuple(artifacts),
        targets((state,), clock_ms, {context: WinnerStatus.USABLE}),
        clock_ms,
    )
