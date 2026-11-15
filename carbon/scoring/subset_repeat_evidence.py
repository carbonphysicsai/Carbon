"""The subset repeat: one fresh run of the sealed cells and a secret sample of the other graded rows (Motor 1.8 only).

The owner, Sun 15 Nov 2026 08:19 CST (the Lead session): replace Motor 1.8's two full-bank inference-pair passes with
a keyed subset repeat, as the SAME version (pack and exam key unchanged); and 08:38 CST: "66 rows. But we need a % that
generalizes for challenges". CV-Motor-B's rulings (board, Sun 15 Nov) and Validator-2B's R-1..R-5 bind it
(docs/records/2026-11-15-motor18-subset-repeat.json):

- After the graded predictions are committed, the host re-runs, in ONE fresh worker process (same image, state and
  inputs), ALL the graded bank's sealed cells plus ``k`` rows drawn uniformly over the REST of the bank (Q1 = B,
  STRATIFIED), by a per-GRADE secret key (HMAC of the grading host's K_speed under this module's own domain tag and the
  submission id, so independent of the speed sample). It is kept write-once beside the dual measurement as a
  host-private side file. The rows and the key never reach any public or miner surface.
- ``k`` is derived from the version's registered PROMISE (`registered_promise`): with ``f`` the fraction of rows a model
  may answer differently on a repeat and ``P`` the probability the repeat must catch it, ``k = min(ceil(ln(1 - P) /
  ln(1 - f)), rows outside the sealed cells)``. An absent, null or malformed promise fails closed (the receiver will not
  serve; a grade is Carbon's typed unavailable), never "no repeat".
- The scorer reads the side file (`read`) into one value per graded bank row: the fresh answer on a repeated row, None
  on every row that is not repeat-checked. Each fresh answer must equal the graded answer BIT FOR BIT over the whole row
  (`rows_agree`, Q2). Missing or inconsistent evidence is typed unavailable (`SubsetRepeatRefused`), never a candidate
  verdict; a malformed or non-finite fresh answer is read as such and fails the exact check (the candidate's).

`SUBSET_REPEAT_VERSIONS` is the ONE registry of the versions graded this way: the door and the scorer both read it.
This module is a producer file of Motor 1.8 only (`motor18_dual_pack.FILES`); no other version's producer identity
covers it.
"""

from __future__ import annotations

import hashlib
import hmac
import itertools
import json
import math
import re
from pathlib import Path

#: The versions whose repeat is the keyed subset repeat (every other version keeps the full pair, unchanged).
SUBSET_REPEAT_VERSIONS = frozenset({("electric-motor-magnetics", "1.8")})
#: Each subset version's producer module (its `physical_dual_pack.producer_digest` identity, checked at receiver start).
PRODUCERS = {("electric-motor-magnetics", "1.8"): "carbon.scoring.motor18_dual_pack"}
#: The side file's schema.
SCHEMA = "carbon.scoring.subset-repeat-evidence.v1"
#: The run inside it (`paired_inference.infer_frozen_once`).
RUN_SCHEMA = "carbon.source-free-inference-repeat.v1"
#: The host values file of the owner's promise per version (public rule values; never a drawn row or a key).
VALUES_SCHEMA = "carbon.exam.subset-repeat.v1"
VALUES_PATH = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "validator_host_classes"
    / "subset_repeat.json"
)
_PROMISE_KEYS = {"repeat_fail_fraction", "repeat_detect_prob"}
#: The per-grade key's domain tag (the speed sample's is ``carbon.speed-sample/1``: the two draws are independent).
DOMAIN = b"carbon.subset-repeat/1"
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")
_OPERATION = re.compile(r"operation-[0-9a-f]{64}\Z")
_DOCUMENT = {
    "schema",
    "challenge",
    "challenge_version",
    "evaluation_pack_digest",
    "submission_id",
    "n_rows",
    "sealed_positions",
    "keyed_positions",
    "k",
    "run",
    "scientific_qualification",
    "official_eligible",
}
_RUN = {
    "schema",
    "execution_boundary",
    "recipe_digest",
    "state_digest",
    "inputs_digest",
    "inference_image_id",
    "logical_prediction_rows",
    "elapsed_seconds",
    "repeat",
    "scientific_qualification",
    "official_eligible",
}
_RECEIPT = {
    "schema",
    "recipe_digest",
    "state_digest",
    "inputs_digest",
    "predictions_digest",
}


class SubsetRepeatRefused(ValueError):
    """Unavailable or inconsistent subset-repeat material: Carbon's gap, never a candidate verdict."""

    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _require(ok, code):
    if not ok:
        raise SubsetRepeatRefused(code)


def is_subset_version(challenge, version) -> bool:
    return (challenge, version) in SUBSET_REPEAT_VERSIONS


# -- the promise and k --------------------------------------------------------------------------------------------------


def _probability(value):
    """A JSON number strictly between 0 and 1 (a float: 0 and 1 are the only integers in range, and both are out)."""
    return type(value) is float and math.isfinite(value) and 0.0 < value < 1.0


def registered_promise(challenge, version, *, path=None):
    """``(repeat_fail_fraction, repeat_detect_prob)`` registered for ``"<challenge> <version>"``. Each must be a JSON
    number strictly between 0 and 1 (finite, never a bool); an absent file, row or value, a null, or any other key
    refuses ``subset_repeat_promise_unregistered`` (fail closed)."""
    try:
        document = json.loads(Path(VALUES_PATH if path is None else path).read_bytes())
    except (OSError, ValueError) as exc:
        raise SubsetRepeatRefused("subset_repeat_promise_unregistered") from exc
    rows = document.get("rows") if type(document) is dict else None
    row = rows.get(f"{challenge} {version}") if type(rows) is dict else None
    _require(
        type(document) is dict
        and document.get("schema") == VALUES_SCHEMA
        and set(document) == {"schema", "rows"}
        and type(row) is dict
        and set(row) == _PROMISE_KEYS
        and all(_probability(row[key]) for key in _PROMISE_KEYS),
        "subset_repeat_promise_unregistered",
    )
    return row["repeat_fail_fraction"], row["repeat_detect_prob"]


def derived_k(fail_fraction, detect_prob, n_rows):
    """The fewest uniformly drawn rows that catch, with probability at least ``detect_prob``, a model that answers a
    ``fail_fraction`` of the rows differently on a repeat (sampling with replacement bounds it from above), capped at
    the graded bank's rows: ``min(ceil(ln(1 - P) / ln(1 - f)), n_rows)``."""
    _require(
        _probability(fail_fraction)
        and _probability(detect_prob)
        and type(n_rows) is int
        and not isinstance(n_rows, bool)
        and n_rows >= 1,
        "subset_repeat_promise_unregistered",
    )
    need = math.ceil(math.log1p(-detect_prob) / math.log1p(-fail_fraction))
    return max(1, min(need, n_rows))


def registered_k(challenge, version, n_rows, *, path=None):
    """``k`` for one grade of ``n_rows`` graded rows, from the registered promise (fail closed)."""
    fail_fraction, detect_prob = registered_promise(challenge, version, path=path)
    return derived_k(fail_fraction, detect_prob, n_rows)


# -- the identities -----------------------------------------------------------------------------------------------------


def run_identity(evaluation_pack_digest, submission_id, *, retry=False):
    """The identity the door gives one subset repeat (its wall retry adds ``-wall-retry``)."""
    return (
        "subset-repeat-"
        + evaluation_pack_digest
        + "-"
        + submission_id
        + ("-wall-retry" if retry else "")
    )


def ledger_identity(identity):
    """The ledger child of a run identity (`paired_inference.repeat_identity`, the same formula; a test holds them
    equal)."""
    return "subset-repeat-" + hashlib.sha256(identity.encode()).hexdigest()


# -- the draw -----------------------------------------------------------------------------------------------------------


def grade_key(k_speed, submission_id):
    """The per-grade draw key: HMAC-SHA256(K_speed, DOMAIN || 0x00 || submission id). Custody's, never the miner's."""
    _require(
        type(k_speed) is bytes
        and len(k_speed) >= 32
        and type(submission_id) is str
        and bool(submission_id),
        "subset_repeat_key_unavailable",
    )
    message = b"\x00".join([DOMAIN, submission_id.encode("utf-8")])
    return hmac.new(k_speed, message, hashlib.sha256).digest()


def _uniform(key):
    """Uniform integers below a bound, from HMAC-SHA256(key, counter) blocks, by rejection (no modulo bias)."""
    counter = 0

    def below(bound):
        nonlocal counter
        limit = (2**64 // bound) * bound
        while True:
            block = hmac.new(
                key, b"draw\x00" + counter.to_bytes(8, "big"), hashlib.sha256
            ).digest()
            counter += 1
            for start in range(0, 32, 8):
                value = int.from_bytes(block[start : start + 8], "big")
                if value < limit:
                    return value % bound

    return below


def keyed_sample(key, candidates, k):
    """``k`` distinct members of ``candidates``, uniformly (a keyed partial Fisher-Yates shuffle), ascending."""
    rows = list(candidates)
    _require(
        type(key) is bytes
        and len(key) == 32
        and type(k) is int
        and 1 <= k <= len(rows),
        "subset_repeat_draw_invalid",
    )
    below = _uniform(key)
    for i in range(k):
        j = i + below(len(rows) - i)
        rows[i], rows[j] = rows[j], rows[i]
    return sorted(rows[:k])


def sealed_positions(cohorts):
    """The graded bank's sealed cells (its rows of the sealed grid cohort), every one re-run on every grade."""
    from carbon.scoring.sealed_grid_common import GRID_COHORT

    return [i for i, cohort in enumerate(cohorts) if cohort == GRID_COHORT]


def plan(key, *, challenge, version, cohorts):
    """``(sealed, keyed)`` positions of one grade's repeat (CV-Motor-B, Q1 = B, STRATIFIED): ALL the sealed cells, plus
    ``k`` keyed rows drawn uniformly over the REST of the graded bank, ``k`` from the registered promise over that rest.
    """
    sealed = sealed_positions(cohorts)
    rest = [i for i in range(len(cohorts)) if i not in set(sealed)]
    _require(bool(sealed) and bool(rest), "subset_repeat_bank_strata")
    k = registered_k(challenge, version, len(rest))
    return sealed, keyed_sample(key, rest, k)


# -- the side file ------------------------------------------------------------------------------------------------------


def canonical(value):
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"
    ).encode("utf-8")


def side_file(
    *,
    challenge,
    version,
    evaluation_pack_digest,
    submission_id,
    n_rows,
    sealed,
    keyed,
    run,
):
    """The host-private side file of one subset repeat (canonical JSON bytes). The run answered the graded rows at
    ``sorted(sealed + keyed)``, in that order."""
    return canonical(
        {
            "schema": SCHEMA,
            "challenge": challenge,
            "challenge_version": version,
            "evaluation_pack_digest": evaluation_pack_digest,
            "submission_id": submission_id,
            "n_rows": n_rows,
            "sealed_positions": list(sealed),
            "keyed_positions": list(keyed),
            "k": len(keyed),
            "run": run,
            "scientific_qualification": False,
            "official_eligible": False,
        }
    )


def _sha(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _ascending(values, n_rows):
    return (
        type(values) is list
        and all(type(p) is int and 0 <= p < n_rows for p in values)
        and all(a < b for a, b in itertools.pairwise(values))
    )


def _answers(raw, rows, rest):
    """The fresh answers, one per repeated row, as flat tuples of floats (non-finite values kept, so the exact check
    fails them), or ``()`` for a row that is not one answer of the registered shape. Never refuses: a malformed fresh
    answer is the candidate's (CV-Motor-B, Q2)."""

    def flat(value, shape):
        if not shape:
            if type(value) in (int, float) and not isinstance(value, bool):
                return [float(value)]
            return None
        if type(value) is not list or len(value) != shape[0]:
            return None
        out = []
        for item in value:
            part = flat(item, shape[1:])
            if part is None:
                return None
            out.extend(part)
        return out

    try:
        parsed = json.loads(raw.decode("utf-8"), parse_constant=float)
    except (UnicodeError, ValueError, RecursionError, OverflowError):
        return [()] * rows
    if type(parsed) is not list or len(parsed) != rows:
        return [()] * rows
    answers = []
    for value in parsed:
        try:
            row = flat(value, rest)
        except RecursionError:
            row = None
        answers.append(() if row is None else tuple(row))
    return answers


def rows_agree(graded, fresh):
    """The subset repeat's decisive rule (CV-Motor-B, Q2): the fresh answer equals the graded answer BIT FOR BIT over the
    whole row. A different value (``0.0`` and ``-0.0`` differ), a non-finite or missing value, or a row of another
    width disagrees."""
    if fresh is None or len(fresh) != len(graded):
        return False
    return all(
        type(b) is float and math.isfinite(b) and float(a).hex() == b.hex()
        for a, b in zip(graded, fresh, strict=True)
    )


#: The carrier's own ceiling on a worker's predictions file (`bundle_construction_worker._infer_state`): every answer
#: the carrier accepted is read, so a large or malformed answer is judged, never turned into Carbon's gap.
_ANSWER_BYTES = 16 * 1024**2


def read(
    raw,
    *,
    registered_sha256,
    challenge,
    version,
    evaluation_pack_digest,
    cohorts,
    graded_inputs,
    output_shape,
    recipe_digest,
    state_digest,
    inference_image_id,
    graded_operation,
):
    """The fresh answer per graded bank row: a tuple on a repeated row (``()`` when it is no answer of the registered
    shape; non-finite values kept), None on every row that is not repeat-checked.

    The side file must be exactly the registered bytes and bind this grade: the served version and evaluation pack;
    ALL the bank's sealed cells (``cohorts``) plus exactly ``k`` keyed rows outside them, ``k`` from the registered
    promise; the graded run's recipe, state and image; inputs that are exactly the graded query's rows at those
    positions; and ONE settled operation that is not the graded one, under the ledger identity the door gives this
    submission's repeat (or its wall retry). ``output_shape`` is the graded query's full output shape. Anything else
    refuses, typed (Carbon's gap, never a verdict)."""
    import numpy as np

    from carbon.development_session.bundle_construction_worker import _tensors
    from carbon.scoring import inference_pair_evidence as pair

    try:
        n_rows = int(output_shape[0])
        rest = [int(v) for v in output_shape[1:]]
        width = math.prod(rest)
    except (TypeError, ValueError, IndexError) as exc:
        raise SubsetRepeatRefused("subset_repeat_expected_shape") from exc
    limit = 4 * (_ANSWER_BYTES + pair._MAX_RECEIPT) // 3 + 2 * 1024**2
    _require(
        type(registered_sha256) is str
        and _DIGEST.fullmatch(registered_sha256) is not None,
        "subset_repeat_registered_digest",
    )
    _require(
        type(raw) is bytes and 0 < len(raw) <= limit, "subset_repeat_evidence_bytes"
    )
    _require(_sha(raw) == registered_sha256, "subset_repeat_registered_digest")
    _require(
        type(cohorts) in (list, tuple) and len(cohorts) == n_rows,
        "subset_repeat_expected_shape",
    )
    try:
        document = pair._parse(raw, limit, "subset_repeat")
        _require(
            type(document) is dict
            and set(document) == _DOCUMENT
            and canonical(document) == raw,
            "subset_repeat_shape",
        )
        submission = document["submission_id"]
        _require(
            document["schema"] == SCHEMA
            and document["challenge"] == challenge
            and document["challenge_version"] == version
            and is_subset_version(challenge, version)
            and document["evaluation_pack_digest"] == evaluation_pack_digest
            and type(submission) is str
            and bool(submission)
            and document["scientific_qualification"] is False
            and document["official_eligible"] is False,
            "subset_repeat_identity",
        )
        sealed, keyed, k = (
            document["sealed_positions"],
            document["keyed_positions"],
            document["k"],
        )
        expected_sealed = sealed_positions(cohorts)
        _require(
            document["n_rows"] == n_rows
            and sealed == expected_sealed
            and _ascending(keyed, n_rows)
            and not set(keyed) & set(sealed)
            and type(k) is int
            and len(keyed) == k
            and k == registered_k(challenge, version, n_rows - len(sealed)),
            "subset_repeat_positions",
        )
        positions = sorted([*sealed, *keyed])
        run = document["run"]
        _require(type(run) is dict and set(run) == _RUN, "subset_repeat_run_shape")
        subset = np.ascontiguousarray(np.asarray(graded_inputs)[positions])
        _require(
            run["schema"] == RUN_SCHEMA
            and run["execution_boundary"] == "C03_DOCKER"
            and run["scientific_qualification"] is False
            and run["official_eligible"] is False
            and run["recipe_digest"] == recipe_digest
            and run["state_digest"] == state_digest
            and run["inference_image_id"] == inference_image_id
            and run["inputs_digest"] == _sha(_tensors(inputs=subset))
            and type(run["logical_prediction_rows"]) is int
            and run["logical_prediction_rows"] == len(positions)
            and type(run["elapsed_seconds"]) in (int, float)
            and math.isfinite(run["elapsed_seconds"])
            and run["elapsed_seconds"] >= 0,
            "subset_repeat_binding",
        )
        phase = run["repeat"]
        _require(
            type(phase) is dict
            and set(phase)
            == {"worker_operation", "controls_digest", "originals", "accounting"},
            "subset_repeat_phase_shape",
        )
        operation = phase["worker_operation"]
        _require(
            type(operation) is str
            and _OPERATION.fullmatch(operation) is not None
            and operation != graded_operation
            and type(phase["controls_digest"]) is str
            and _DIGEST.fullmatch(phase["controls_digest"]) is not None,
            "subset_repeat_not_independent",
        )
        originals = phase["originals"]
        _require(
            type(originals) is dict
            and set(originals) == {"predictions.json", "receipt.json"},
            "subset_repeat_originals_shape",
        )
        predictions_raw = pair._original(originals["predictions.json"], _ANSWER_BYTES)
        receipt_raw = pair._original(originals["receipt.json"], pair._MAX_RECEIPT)
        receipt = pair._parse(receipt_raw, pair._MAX_RECEIPT, "receipt")
        _require(
            type(receipt) is dict
            and set(receipt) == _RECEIPT
            and receipt["schema"] == "carbon.development.bundle-inference.v1"
            and receipt["recipe_digest"] == recipe_digest
            and receipt["state_digest"] == state_digest
            and receipt["inputs_digest"] == run["inputs_digest"]
            and receipt["predictions_digest"] == _sha(predictions_raw),
            "subset_repeat_receipt_binding",
        )
        accounting = phase["accounting"]
        ledger = accounting.get("ledger_identity") if type(accounting) is dict else None
        _require(
            ledger
            in {
                ledger_identity(
                    run_identity(evaluation_pack_digest, submission, retry=retry)
                )
                for retry in (False, True)
            },
            "subset_repeat_accounting_identity",
        )
        pair._accounting(accounting, ledger, operation, originals)
    except pair.PairEvidenceRefused as exc:
        code = (
            exc.code
            if exc.code.startswith("subset_repeat")
            else "subset_repeat_" + exc.code
        )
        raise SubsetRepeatRefused(code) from exc
    except (KeyError, TypeError, ValueError, IndexError) as exc:
        if isinstance(exc, SubsetRepeatRefused):
            raise
        raise SubsetRepeatRefused("subset_repeat_evidence_unreadable") from exc
    answers = _answers(predictions_raw, len(positions), rest)
    twins = [None] * n_rows
    for position, answer in zip(positions, answers, strict=True):
        twins[position] = answer
    del width
    return twins


__all__ = [
    "DOMAIN",
    "PRODUCERS",
    "RUN_SCHEMA",
    "SCHEMA",
    "SUBSET_REPEAT_VERSIONS",
    "VALUES_PATH",
    "VALUES_SCHEMA",
    "SubsetRepeatRefused",
    "derived_k",
    "grade_key",
    "is_subset_version",
    "keyed_sample",
    "ledger_identity",
    "plan",
    "read",
    "registered_k",
    "registered_promise",
    "rows_agree",
    "run_identity",
    "sealed_positions",
    "side_file",
]
