"""Trusted fresh-cohort binding for the existing C-03/C-05/C-07 final path.

No agent tool constructs this object or supplies its private root. The research
profile changes construction/cohort scope, never balanced-v2 mathematics.
"""

from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass
from pathlib import Path

from .data import write_once
from .profile import canonical, digest
from .research_carrier import _numerical_lease
from .research_catalog import research_contracts
from .research_data import decode_public_case
from .research_profile import _context, document


class CampaignFinalBudget:
    def __init__(self, ledger, owner):
        self.ledger, self.owner = ledger, owner

    def run_worker(self, identity, operation):
        # Existing fixed C-03/C-04/C-05 controllers use 600 productive seconds,
        # then bounded validation/cleanup. Count all of it against the 6h total.
        resources = {"numerical_milliseconds": 720000, "retained_bytes": 384 * 1024**2}
        if "-train-" in identity:
            resources["final_replicas"] = 1
        with _numerical_lease(self.ledger):
            admitted = self.ledger.reserve(
                "final-" + identity,
                owner=self.owner,
                phase="final",
                request={
                    "operation": identity,
                    "productive_seconds": 600,
                    "cleanup_validation_seconds": 120,
                },
                resources=resources,
            )
            if not admitted["dispatch"]:
                raise ValueError(
                    "final operation retained; reconcile domain journals without reexecution"
                )
            started = time.monotonic()
            before = sum(
                p.stat().st_size for p in self.ledger.root.rglob("*") if p.is_file()
            )
            result = operation()
            elapsed = math.ceil((time.monotonic() - started) * 1000)
            after = sum(
                p.stat().st_size for p in self.ledger.root.rglob("*") if p.is_file()
            )
            self.ledger.finish(
                "final-" + identity,
                owner=self.owner,
                state="SUCCEEDED",
                actual={
                    **resources,
                    "numerical_milliseconds": elapsed,
                    "retained_bytes": max(0, after - before),
                },
                result={
                    "owner_result_type": type(result).__name__,
                    "numerical_outcome": "retained in original domain journal",
                },
            )
            return result


@dataclass(frozen=True)
class ResearchEvaluationInputs:
    root: Path
    role_root: Path
    epoch: int
    ledger: object
    owner: str
    strategy_digest: str

    def verify(self, strategy):
        if (
            self.epoch not in (1, 2)
            or not self.root.is_absolute()
            or self.root.is_symlink()
        ):
            raise ValueError("private final execution binding required")
        if not self.root.resolve().is_relative_to(self.ledger.root.resolve()):
            raise ValueError("final root outside campaign accounting")
        if digest(canonical(strategy)) != self.strategy_digest:
            raise ValueError("recipe differs from prospective final freeze")
        freeze = json.loads((self.root / "final-construction-freeze.json").read_bytes())
        expected = {
            "schema": "carbon.autoresearch.final-construction.v1",
            "epoch": self.epoch,
            "strategy_digest": self.strategy_digest,
            "profile_digest": self.profile_digest,
            "cohort_digest": self.cohort_digest,
            "randomness_digests": [digest(x) for x in self.randomness],
        }
        if freeze != expected:
            raise ValueError("final construction freeze conflict")

    @property
    def profile_document(self):
        return document()

    @property
    def profile_digest(self):
        return digest(canonical(document()))

    @property
    def resource_document(self):
        return document()["final_worker"]

    @property
    def context(self):
        return _context(self.role_root, "final-epoch-" + str(self.epoch))

    @property
    def cohort_digest(self):
        role = "final-epoch-" + str(self.epoch)
        manifest = json.loads(
            (self.role_root / "private-role-manifest.json").read_bytes()
        )
        payload = (self.role_root / (role + "-cases.json")).read_bytes()
        if digest(payload) != manifest[role]["digest"]:
            raise ValueError("frozen final cohort changed")
        return digest(payload)

    @property
    def cases(self):
        _verified_cohort = self.cohort_digest
        values = json.loads(
            (
                self.role_root / ("final-epoch-" + str(self.epoch) + "-cases.json")
            ).read_bytes()
        )
        cases = tuple(decode_public_case(v) for v in values)
        keys = {(case.coordinates.role.value, case.coordinates.cell) for case in cases}
        if len(cases) != 24 or keys != {
            (role, cell) for role in ("EVAL", "STRESS") for cell in range(12)
        }:
            raise ValueError("complete fresh final cohort required")
        return cases

    @property
    def randomness(self):
        values = tuple(
            (self.root / f"final-randomness-{i}.bin").read_bytes() for i in range(3)
        )
        if any(len(value) != 32 for value in values) or len(set(values)) != 3:
            raise ValueError("three distinct frozen final construction seeds required")
        return values

    @property
    def contracts(self):
        return research_contracts()

    @property
    def budget(self):
        return CampaignFinalBudget(self.ledger, self.owner)


def prepare_final_inputs(
    *,
    root,
    role_root,
    epoch,
    ledger,
    owner,
    strategy,
    randomness,
    public_data,
    final_data,
    image,
):
    """Controller only, after recipe selection, using already committed cases."""
    from carbon.generators.burgers_dynamics import (
        canonical_public_case_bytes,
        requested_times,
    )
    from carbon.reference_runtime.model import (
        BurgersReferenceRole,
        build_reference_request,
        runtime_environment_digest,
    )

    from .research_catalog import compile_recipe

    compile_recipe(strategy)
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    if (
        type(randomness) is not tuple
        or len(randomness) != 3
        or any(type(x) is not bytes or len(x) != 32 for x in randomness)
    ):
        raise ValueError("prospectively fixed reconstruction seeds required")
    for i, value in enumerate(randomness):
        write_once(root / f"final-randomness-{i}.bin", value)
    bound = ResearchEvaluationInputs(
        root, role_root, epoch, ledger, owner, digest(canonical(strategy))
    )
    write_once(
        root / "final-construction-freeze.json",
        canonical(
            {
                "schema": "carbon.autoresearch.final-construction.v1",
                "epoch": epoch,
                "strategy_digest": bound.strategy_digest,
                "profile_digest": bound.profile_digest,
                "cohort_digest": bound.cohort_digest,
                "randomness_digests": [digest(x) for x in bound.randomness],
            }
        ),
    )
    bound.verify(strategy)
    training, train_metadata = public_data.prepare("research-train")
    write_once(root / "public-train.npz", training)
    write_once(root / "profile.json", canonical(bound.profile_document))
    rows = []
    if final_data.phase != "final":
        raise ValueError("final reference accounting required")
    for case in bound.cases:
        name = case.coordinates.role.value.lower() + f"-{case.coordinates.cell:02d}"
        request = build_reference_request(
            case,
            BurgersReferenceRole.CANDIDATE_PRIMARY,
            output_points=64,
            requested_times=requested_times(case, 4),
            environment_digest=runtime_environment_digest(),
        )
        _values, record = final_data._reference(case)
        record = {
            **record,
            "solution_path": str(ledger.root / record["snapshot"] / "solution.f64le"),
        }
        write_once(
            root / (name + "-reference-request.json"), canonical(request.document())
        )
        write_once(root / (name + "-reference-result.json"), canonical(record))
        payload = canonical_public_case_bytes(case)
        write_once(root / (name + "-case.json"), payload)
        rows.append(
            {
                "name": name,
                "role": case.coordinates.role.value,
                "case_digest": digest(payload),
                "reference_request_digest": request.request_digest,
            }
        )
    manifest = {
        "schema": "carbon.autoresearch.final-cases.v1",
        "profile_digest": bound.profile_digest,
        "worker_image": image.image_id,
        "cases": rows,
        "epoch": epoch,
        "training_archive_digest": train_metadata["archive_digest"],
        "training_parents": train_metadata["parents"],
    }
    write_once(root / "case-manifest.json", canonical(manifest))
    write_once(
        root / "preparation.json",
        canonical(
            {
                "schema": "carbon.autoresearch.final-preparation.v1",
                "profile_digest": bound.profile_digest,
                "case_manifest_digest": digest(canonical(manifest)),
                "train_archive_digest": digest(training),
            }
        ),
    )
    return bound
