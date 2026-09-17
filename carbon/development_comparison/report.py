"""Versioned owner report retaining authentic input identities and lifecycle."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from carbon.development_session.data import write_once
from carbon.development_session.profile import canonical, digest

from .experiment import (
    baseline_for_session,
    check_storage,
    load_contract,
    proposal_seeds,
)
from .metrics import descriptive_metrics, report_document
from .sources import read_json, resolve_source


@dataclass(frozen=True)
class ComparisonRef:
    path: Path
    digest: str


def compute(root: Path, challenger_path: Path):
    contract = load_contract(root)
    baseline = baseline_for_session(root)
    challenger = resolve_source(
        challenger_path,
        retention_root=root,
        quarantine_journal=Path(contract["quarantine_journal"]),
        trusted=contract["challenger_trust"],
        reference_root=Path(contract["reference_root"]),
    )
    if (
        challenger.bindings != contract["shared_bindings"]
        or challenger.manifest != contract["case_manifest"]
    ):
        raise ValueError("incompatible challenge/cohort/measurement/resource versions")
    if (
        challenger.identity["source_digest"] == baseline.identity["source_digest"]
        or challenger.identity["receipt_digest"] == baseline.identity["receipt_digest"]
    ):
        raise ValueError("historical baseline replay is not a new challenger")
    if (
        challenger.identity["authenticated_hotkey"]
        != baseline.identity["authenticated_hotkey"]
    ):
        raise ValueError("comparison session requires the authorized miner identity")
    slots = [
        index
        for index in (1, 2)
        if (root / f"proposal-{index}.json").is_file()
        and read_json(root / f"proposal-{index}.json") == challenger.strategy
    ]
    if len(slots) != 1:
        raise ValueError("challenger lacks a unique retained proposal")
    seeds = proposal_seeds(root, slots[0])
    submission = challenger.identity["binding"]["submission_id"]
    for index, seed in enumerate(seeds):
        path = (
            root
            / "evaluations"
            / submission
            / f"replica-{index}-private-randomness.bin"
        )
        if path.is_symlink() or path.read_bytes() != seed:
            raise ValueError("reconstruction differs from prospective seed commitments")
    expected = {
        role: frozenset(
            row["case_digest"]
            for row in challenger.manifest["cases"]
            if row["role"] == role
        )
        for role in ("EVAL", "STRESS")
    }
    metrics = descriptive_metrics(
        baseline.cohorts, challenger.cohorts, expected_cases=expected
    )
    value = report_document(
        contract_digest=digest(canonical(contract)),
        baseline=baseline.identity,
        challenger=challenger.identity,
        metrics=metrics,
    )
    value.update(
        baseline_strategy=baseline.strategy,
        challenger_strategy=challenger.strategy,
        challenger_source=str(challenger_path),
        baseline_source=contract["baseline_source"],
        proposal_number=slots[0],
        resources={
            "baseline_historical": {
                key: baseline.dossier[key]
                for key in ("reconstruction_observations", "prediction_observations")
            },
            "challenger": {
                key: challenger.dossier[key]
                for key in ("reconstruction_observations", "prediction_observations")
            },
        },
        training={
            "baseline_historical": {
                "runs": 3,
                "updates": baseline.dossier["training_steps"],
            },
            "challenger": {"runs": 3, "updates": challenger.dossier["training_steps"]},
        },
    )
    return value


def write_report(root, challenger_path):
    check_storage(root)
    value = compute(root, challenger_path)
    identity = value["challenger"]["binding"]["submission_id"]
    path = root / f"comparison-{identity}.json"
    write_once(path, canonical(value))
    write_once(root / f"comparison-{identity}.md", markdown(value).encode())
    return ComparisonRef(path, digest(canonical(value)))


def resolve_report(root: Path, ref: ComparisonRef):
    if type(ref) is not ComparisonRef or ref.path.parent != root:
        raise ValueError("nominal comparison report required")
    value = read_json(ref.path)
    if digest(canonical(value)) != ref.digest or canonical(value) != canonical(
        compute(root, Path(value["challenger_source"]))
    ):
        raise ValueError("altered, stale or incompatible comparison report")
    return value


def markdown(value):
    lines = [
        "# Carbon DEVELOPMENT comparison",
        "",
        "**Disposition:** INDETERMINATE_NO_ACCEPTANCE_RULE. No accepted improvement, tie, winner or payment.",
        "",
        f"Historical baseline: `{value['baseline_strategy']}`",
        f"Challenger: `{value['challenger_strategy']}`",
        "",
        "Seen 12 TRAIN / 12 EVAL / 12 STRESS development subset; three replicas per construction. This is descriptive and adaptive, not confirmatory or full Burgers V1 coverage.",
    ]
    for role, cohort in value["cohorts"].items():
        lines += [
            "",
            f"## {role}",
            "",
            "Lower values mean lower observed normalized error/defect on this cohort.",
            "",
            "| Metric | Baseline | Challenger | Difference | Baseline replica SD | Challenger replica SD |",
            "|---|---:|---:|---:|---:|---:|",
        ]
        for metric, observation in cohort["metrics"].items():
            b, c = observation["baseline"], observation["challenger"]
            lines.append(
                f"| {metric} | {b['mean']:.8g} | {c['mean']:.8g} | {observation['difference_challenger_minus_baseline']:+.8g} | {b['replica_mean_sample_sd']:.5g} | {c['replica_mean_sample_sd']:.5g} |"
            )
        lines += [
            "",
            f"Half-time censor counts (36 case-by-replica observations, not independent cases): baseline `{cohort['half_time']['baseline_censor_counts']}`, challenger `{cohort['half_time']['challenger_censor_counts']}`. The timing error is horizon-clipped.",
        ]
    lines += [
        "",
        "## Interpretation and evidence",
        "",
        "Cases and reconstruction replicas are distinct dependence dimensions. Replica means and variation of paired case-mean differences are retained in JSON. Three replicas support only limited descriptive spread; no confidence interval, equivalence claim or scientific qualification is supplied.",
        "",
        f"Baseline source: {value['baseline_source']}",
        f"Challenger source: {value['challenger_source']}",
        f"Contract: `{value['contract_digest']}`",
        "",
        "The exact missing decision is an authorized DEVELOPMENT admissibility, improvement and equivalence rule. Future non-burn competition also needs reward parameters, finalized miner-to-UID mapping, a winner-capable publication profile and distinct transaction approval. This report is ineligible for official score, protected evidence, settlement and the all-burn publisher.",
        "",
    ]
    return "\n".join(lines)
