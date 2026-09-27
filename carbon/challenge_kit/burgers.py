"""The Burgers challenge's own generator and reference solvers, for training.

What this is: the exact public generator (`carbon.generators.burgers_dynamics`)
and the C-04 reference implementations (`carbon.reference_runtime.model`),
shipped into the miner's research image byte-identical to the files the
validator runs. It lets a miner draw as many cases as they like from the
challenge's public law - with seed roots of their own - and label them with the
trusted primary (Cole-Hopf Fourier quadrature), the finite-volume witness or the
ETDRK4 cross-check.

What it is not: the exam. Final evaluation cases come from private roots that
never leave the controller, and nothing here can produce them; what it shares
with the exam is the published law, which was already public. Everything a
miner computes with it is self-reported. The validator keeps its own pinned copy
and reconstructs every submission independently.

Not to be confused with `carbon_jax_lab.reference.generate_splits`, which is a
demonstration population with a different domain, horizon and mode count - it
says so itself - and is not this challenge's law.

    python -m carbon.challenge_kit.burgers generate --root-hex <64 hex> \\
        --count 1000 --out train.npz [--role train|eval|stress] [--method cole_hopf]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from carbon.generators.burgers_dynamics import (
    BurgersCaseCoordinates,
    PublicDevelopmentRole,
    evaluate_initial_field,
    generate_development_case,
    requested_times,
)
from carbon.registry import ChallengeKey
from carbon.seeding import EvaluationBinding, MockContext, MockEntropy, SeedPin

#: The seed pin the challenge's own profile uses, baked at image build and
#: checked against the controller's by the repository tests.
PIN = json.loads((Path(__file__).parent / "burgers_pin.json").read_text())

ROLES = {
    "train": PublicDevelopmentRole.TRAIN,
    "eval": PublicDevelopmentRole.EVAL,
    "stress": PublicDevelopmentRole.STRESS,
}
METHODS = ("cole_hopf", "finite_volume", "etdrk4")
OUTPUT_POINTS = 64
TIME_INTERVALS = 4  # 13 requested times per case, as the challenge's own data


def context(root: bytes) -> MockContext:
    """A generation context for the miner's own 32-byte root."""
    if type(root) is not bytes or len(root) != 32:
        raise ValueError("a seed root is exactly 32 bytes")
    return MockContext(
        MockEntropy(root),
        SeedPin(
            ChallengeKey(PIN["challenge_id"], PIN["challenge_version"]),
            PIN["generator_version"],
            PIN["generator_digest"],
            PIN["scoring_version"],
            PIN["scoring_digest"],
            EvaluationBinding(bytes.fromhex(PIN["evaluation_binding"])),
        ),
    )


def generate(root: bytes, count: int, *, role: str = "train", build: int = 0):
    """`count` cases from the public law, cycling the 12 strata cells."""
    if role not in ROLES or type(count) is not int or count < 1:
        raise ValueError("a role of train, eval or stress and a positive count")
    ctx = context(root)
    return [
        generate_development_case(
            ctx, BurgersCaseCoordinates(ROLES[role], i % 12, i // 12, build)
        )
        for i in range(count)
    ]


def inputs(case) -> dict:
    """The model's inputs for one case: grid, initial field, viscosity, times."""
    import numpy as np

    positions = tuple(
        float(2.0 * np.pi * i / OUTPUT_POINTS) for i in range(OUTPUT_POINTS)
    )
    return {
        "positions": np.asarray(positions),
        "initial": np.asarray(evaluate_initial_field(case, positions)),
        "viscosity": float(case.viscosity),
        "times": np.asarray(requested_times(case, TIME_INTERVALS)),
    }


def solve(case, method: str = "cole_hopf"):
    """Label one case with a registered C-04 reference method: (times, points)."""
    import numpy as np

    from carbon.reference_runtime.model import (
        BurgersReferenceRole,
        ReferenceRunOutcome,
        build_reference_request,
        execute_reference,
        runtime_environment_digest,
    )

    role = {
        "cole_hopf": BurgersReferenceRole.CANDIDATE_PRIMARY,
        "finite_volume": BurgersReferenceRole.INDEPENDENT_WITNESS,
        "etdrk4": BurgersReferenceRole.DEVELOPMENT_CROSSCHECK,
    }.get(method)
    if role is None:
        raise ValueError("method must be one of: " + ", ".join(METHODS))
    run = execute_reference(
        build_reference_request(
            case,
            role,
            output_points=OUTPUT_POINTS,
            requested_times=requested_times(case, TIME_INTERVALS),
            environment_digest=runtime_environment_digest(),
        )
    )
    if run.outcome is not ReferenceRunOutcome.SUPPORTED:
        raise ValueError(f"{method} did not support this case: {run.failure_reason}")
    return np.frombuffer(run.artifact.payload, dtype=run.artifact.dtype).reshape(
        run.artifact.shape
    )


def dataset(root: bytes, count: int, *, role="train", method="cole_hopf") -> dict:
    """Stacked arrays for `count` labelled cases, ready to train on."""
    import numpy as np

    cases = generate(root, count, role=role)
    rows = [inputs(case) for case in cases]
    return {
        "positions": rows[0]["positions"],
        "initial": np.stack([row["initial"] for row in rows]),
        "viscosity": np.asarray([row["viscosity"] for row in rows]),
        "times": np.stack([row["times"] for row in rows]),
        "solution": np.stack([solve(case, method) for case in cases]),
    }


def main(argv=None) -> int:
    import numpy as np

    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    make = commands.add_parser("generate", help="Draw and label cases into an .npz")
    make.add_argument("--root-hex", required=True)
    make.add_argument("--count", type=int, required=True)
    make.add_argument("--role", choices=tuple(ROLES), default="train")
    make.add_argument("--method", choices=METHODS, default="cole_hopf")
    make.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    data = dataset(
        bytes.fromhex(args.root_hex), args.count, role=args.role, method=args.method
    )
    np.savez(args.out, **data)
    print(json.dumps({k: list(v.shape) for k, v in data.items()}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
