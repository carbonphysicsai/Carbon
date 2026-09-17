"""D4 public research/fresh final sampling contract; no scientific-rule edits."""

from __future__ import annotations

import json
import os
from pathlib import Path

from carbon.generators import burgers_dynamics
from carbon.generators.burgers_dynamics import (
    BurgersCaseCoordinates,
    PublicDevelopmentRole,
    generate_development_case,
)
from carbon.scoring.development import RULE, rule_digest
from carbon.seeding import EvaluationBinding, MockContext, MockEntropy, SeedPin

from .data import write_once
from .profile import CHALLENGE, canonical, digest, profile_document
from .research_ledger import CEILINGS, ELAPSED_SECONDS

PROFILE = "carbon.burgers-autoresearch-development.v1"
ROLE_ROOTS = ("research-train", "research-validation", "final-epoch-1", "final-epoch-2")


def document():
    return {
        "schema": PROFILE,
        "challenge": [CHALLENGE.challenge_id, CHALLENGE.version],
        "physics": profile_document()["physics"],
        "objective_math": json.loads(canonical(RULE)),
        "objective_math_digest": rule_digest(),
        "scope_extension": "same balanced-v2 mathematics and measurement v3; new recipe/resource/cohort identity, not a historical v2 rescore",
        "sampling": {
            "research_train": {
                "domain_role": "TRAIN",
                "builds": [0, 1],
                "ordinals": [0, 1, 2],
                "cells": list(range(12)),
                "parents": 72,
            },
            "research_validation": {
                "domain_roles": ["EVAL", "STRESS"],
                "build": 0,
                "ordinal": 0,
                "cells": list(range(12)),
                "parents": 24,
                "adaptive": True,
            },
            "final_per_epoch": {
                "domain_roles": ["EVAL", "STRESS"],
                "build": 0,
                "ordinal": 0,
                "cells": list(range(12)),
                "parents": 24,
                "adaptive_before_freeze": False,
            },
            "role_roots": list(ROLE_ROOTS),
            "grid_points": 64,
            "intervals_per_phase": 4,
            "weighting": "equal cases within EVAL/STRESS; minimum role score; mean across three constructions",
            "separation": "independent 256-bit roots; disjoint parent physical signatures; no child or label reuse across roles; common generator/reference dependencies remain",
            "coverage": "development subset: full registered TRAIN support, one parent per cell per practice/final role; not full V1 evaluation/stress coverage or industrial validation",
        },
        "selection": "agent freezes one reproducible eligible recipe per epoch using research observations only; every trial retained; no best-replica final selection",
        "replicas": "three new controller-derived independent reconstruction seeds per construction; same fresh final cohort for control/challenger; all replicas retained",
        "budgets": dict(CEILINGS),
        "elapsed_seconds": ELAPSED_SECONDS,
        "final_worker": {
            "cpu": 2,
            "memory_bytes": 4 * 1024**3,
            "swap_bytes": 0,
            "wall_seconds": 600,
        },
        "public_data": "TRAIN and adaptive practice labels may be inspected; final realizations and labels remain controller-only",
        "chain_writes": False,
        "official_eligible": False,
        "protected_eligible": False,
    }


def _context(root, role):
    if role not in ROLE_ROOTS:
        raise ValueError("closed role required")
    private = root / "role-roots"
    private.mkdir(exist_ok=True, mode=0o700)
    path = private / (role + ".bin")
    if not path.exists():
        write_once(path, os.urandom(32))
    if path.is_symlink() or path.stat().st_size != 32:
        raise ValueError("invalid role root")
    binding = digest(canonical(document()))
    pin = SeedPin(
        CHALLENGE,
        "c-auth1-1.0",
        digest(Path(burgers_dynamics.__file__).read_bytes()),
        "balanced-v2-autoresearch-v1",
        rule_digest(),
        EvaluationBinding(bytes.fromhex(binding[7:])),
    )
    return MockContext(MockEntropy(path.read_bytes()), pin)


def _parent_signature(case):
    # Physical parent bytes exclude role/coordinate labels: relabeling the same
    # field and viscosity cannot defeat deduplication. No transformed children.
    return digest(
        canonical(
            [
                case.cosine_coefficients,
                case.sine_coefficients,
                case.mean,
                case.viscosity,
            ]
        )
    )


def freeze_roles(root):
    """Controller-only prospective draws. This is an experiment operation.

    Final draws may be committed before search, but only the final evaluator
    receives their bytes after recipe freeze. No outcome-dependent redraw.
    """
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    write_once(root / "research-profile.json", canonical(document()))
    roots = [_context(root, role) for role in ROLE_ROOTS]
    entropy = [
        (root / "role-roots" / (role + ".bin")).read_bytes() for role in ROLE_ROOTS
    ]
    if len(set(entropy)) != len(entropy):
        raise ValueError("role roots must be distinct")
    seen = set()
    result = {}
    for role, ctx in zip(ROLE_ROOTS, roots, strict=True):
        coordinates = (
            [
                BurgersCaseCoordinates(
                    PublicDevelopmentRole.TRAIN, cell, ordinal, build
                )
                for build in range(2)
                for cell in range(12)
                for ordinal in range(3)
            ]
            if role == "research-train"
            else [
                BurgersCaseCoordinates(domain, cell, 0, 0)
                for domain in (PublicDevelopmentRole.EVAL, PublicDevelopmentRole.STRESS)
                for cell in range(12)
            ]
        )
        cases = [
            generate_development_case(ctx, coordinate) for coordinate in coordinates
        ]
        signatures = [_parent_signature(case) for case in cases]
        if len(set(signatures)) != len(signatures) or seen.intersection(signatures):
            raise ValueError("parent overlap; stop without outcome-selected redraw")
        seen.update(signatures)
        payload = canonical([case.public_record() for case in cases])
        write_once(root / (role + "-cases.json"), payload)
        result[role] = {
            "count": len(cases),
            "digest": digest(payload),
            "parent_signatures": signatures,
        }
    write_once(root / "private-role-manifest.json", canonical(result))
    return result


def public_cases(root, role):
    if role not in {"research-train", "research-validation"}:
        raise ValueError("final cases are not a research capability")
    manifest = json.loads((root / "private-role-manifest.json").read_bytes())
    payload = (root / (role + "-cases.json")).read_bytes()
    if digest(payload) != manifest[role]["digest"]:
        raise ValueError("public case identity changed")
    return json.loads(payload)
