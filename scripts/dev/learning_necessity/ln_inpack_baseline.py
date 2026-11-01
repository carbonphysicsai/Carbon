"""The learning-necessity reference: the in-pack learned baseline, run exactly as the pack runs it (Validator ruling, 1 Nov
15:30 CST).

The pack's learned baseline is `carbon.learned_baseline` (plain Gaussian kernel ridge), and the pack's own entry point for
it on a pool-graded version is ``carbon.scoring.pool_baseline.fit(kind, version)``, the TRAIN-fit model of the version's
sealed pool evaluation. That entry point:

- scales the inputs to [-1, 1] by the Challenge's declared input box (``pool_baseline.declared_bounds``);
- standardizes each output column on TRAIN (``learned_baseline.KernelRidge``), in the served models' output space;
- Motor (and F08) take their registered (length, ridge) (``pool_baseline.REGISTERED``); F02 and Cooling pick theirs with
  ``learned_baseline.select`` over its declared grid, each point fitted on TRAIN and scored on the version's pinned public
  practice bank by the Challenge's own practice total (``practice_dual.feedback_v2``);
- is deterministic: a Cholesky solve, no seed.

The entry point reads its TRAIN itself (``pool_baseline._train``). The harness hands a contender its TRAIN, so ``builder``
calls the unchanged entry point with that one seam pointed at the TRAIN it is given, and restores it after: the scaling,
the selection and the solve are the pack's own code, not a copy of it. Nothing is tuned beyond what the pack does: the
configuration and train-use must be empty, and the seed is unused.

The grid pins ``implementation_digest()``: the sha256 of every file that runs the baseline (the KRR and the pack's entry
point), each read with CRLF as LF as the score producer's identity is, so a Windows checkout of the same commit gives the
same digest. The harness refuses a grid whose pin differs from the files on disk before anything trains.

Data: public TRAIN (handed in) and, for a selecting Challenge, the version's digest-pinned public practice bank, read by the
pack's own grader. Running the entry point imports the pack's grading modules (some named for the sealed pool they also
grade); none of them reads a sealed, pool, custody or store file here (the test records every file the run opens).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]

#: The grid's contender kind and the identifier its records carry in place of a catalog id.
KIND = "inpack_baseline"
CONTENDER_ID = "inpack.learned_baseline"
#: Its builds are numpy only; they run in the jax worker's record, beside the physics-prior KRR the reference role used to
#: name, so a merged torch + jax result holds it exactly once.
RUNTIME = "jax"
#: The pack's kind for each Challenge the harness trains.
KINDS = {
    "f02": "f02",
    "electric-motor-magnetics": "motor",
    "chip-cold-plate": "cooling",
}
#: Every file that runs the in-pack baseline, relative to the repository.
FILES = ("carbon/learned_baseline.py", "carbon/scoring/pool_baseline.py")
DIGEST_SCHEMA = "carbon.ln-inpack-baseline-implementation.v1"


class Refused(ValueError):
    """The in-pack baseline cannot run here as the pack runs it; the message is a typed code."""


def implementation_digest():
    """The pinned identity of the in-pack baseline's implementation: the CRLF-as-LF sha256 of each of ``FILES``."""
    files = {
        name: "sha256:"
        + hashlib.sha256((ROOT / name).read_bytes().replace(b"\r\n", b"\n")).hexdigest()
        for name in FILES
    }
    document = {"schema": DIGEST_SCHEMA, "files": files}
    raw = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def pack_kind(challenge_id):
    if challenge_id not in KINDS:
        raise Refused("inpack_baseline_not_registered_for_this_challenge")
    return KINDS[challenge_id]


def fit(challenge_id, version, inputs, targets):
    """``(predict_rows, choice)`` from the pack's own ``pool_baseline.fit`` on the TRAIN given."""
    from carbon.scoring import pool_baseline

    kind = pack_kind(challenge_id)
    train = (np.asarray(inputs, dtype=float), np.asarray(targets, dtype=float))
    own = pool_baseline._train
    pool_baseline._train = lambda _kind, _version: train
    try:
        return pool_baseline.fit(kind, version)
    finally:
        pool_baseline._train = own


def builder(challenge_id, version):
    """A build callable with the catalog builders' signature, for the harness."""
    pack_kind(challenge_id)

    def build(train_inputs, train_targets, *, seed, configuration, train_use):
        del seed  # deterministic: the pack's solve takes none
        if configuration or train_use:
            raise Refused("inpack_baseline_takes_no_setting")
        predict_rows, choice = fit(challenge_id, version, train_inputs, train_targets)

        def apply(_parameters, inputs):
            rows = np.asarray(inputs, dtype=float).tolist()
            return np.asarray(predict_rows(rows), dtype=np.float64)

        return {
            "framework": "numpy",
            "apply": apply,
            "parameters": None,
            "inpack_choice": choice,
        }

    return build
