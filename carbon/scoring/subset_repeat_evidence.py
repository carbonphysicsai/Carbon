"""The keyed subset repeat: one fresh run of a secret sample of the graded rows (Motor 1.8 only).

The owner, Sun 15 Nov 2026 08:19 CST (the Lead session): replace Motor 1.8's two full-bank inference-pair passes with
a keyed subset repeat, as the SAME version (pack and exam key unchanged); and 08:38 CST: "66 rows. But we need a % that
generalizes for challenges". CV-Motor-B's ruling (board ~08:2x) and Validator-2B's R-1..R-5 bind it
(docs/records/2026-11-15-motor18-subset-repeat.json):

- After the graded predictions are committed, a per-GRADE secret key (HMAC of the grading host's K_speed under this
  module's own domain tag and the submission id, so it is independent of the speed sample) draws ``k`` distinct rows
  uniformly over the delivered graded query. The host re-predicts exactly those rows in ONE fresh worker process (same
  image, state and inputs), kept write-once beside the dual measurement as a host-private side file. The rows and the
  key never reach any public or miner surface.
- ``k`` is derived from the version's registered PROMISE (`registered_promise`): with ``f`` the fraction of rows a model
  may answer differently on a repeat and ``P`` the probability the repeat must catch it, ``k = min(ceil(ln(1 - P) /
  ln(1 - f)), rows)``. An absent, null or malformed promise fails closed (the receiver will not serve; a grade is
  Carbon's typed unavailable), never "no repeat".
- The scorer reads the side file (`read`) into one value per graded bank row: the fresh answer on a sampled row, None on
  every other row. Missing or inconsistent evidence is typed unavailable (`SubsetRepeatRefused`), never a candidate
  verdict.

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
_LEDGER = re.compile(r"subset-repeat-[0-9a-f]{64}\Z")
_DOCUMENT = {
    "schema",
    "challenge",
    "challenge_version",
    "n_rows",
    "k",
    "positions",
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


def draw(key, n_rows, k):
    """``k`` distinct row positions of ``n_rows``, uniformly (a keyed partial Fisher-Yates shuffle), ascending."""
    _require(
        type(key) is bytes
        and len(key) == 32
        and type(n_rows) is int
        and type(k) is int
        and 1 <= k <= n_rows,
        "subset_repeat_draw_invalid",
    )
    below = _uniform(key)
    rows = list(range(n_rows))
    for i in range(k):
        j = i + below(n_rows - i)
        rows[i], rows[j] = rows[j], rows[i]
    return sorted(rows[:k])


# -- the side file ------------------------------------------------------------------------------------------------------


def canonical(value):
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"
    ).encode("utf-8")


def side_file(*, challenge, version, n_rows, positions, run):
    """The host-private side file of one keyed subset repeat (canonical JSON bytes)."""
    return canonical(
        {
            "schema": SCHEMA,
            "challenge": challenge,
            "challenge_version": version,
            "n_rows": n_rows,
            "k": len(positions),
            "positions": list(positions),
            "run": run,
            "scientific_qualification": False,
            "official_eligible": False,
        }
    )


def _sha(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def read(
    raw,
    *,
    registered_sha256,
    challenge,
    version,
    graded_inputs,
    output_shape,
    recipe_digest,
    state_digest,
    inference_image_id,
    graded_operation,
):
    """The fresh answer per graded bank row: a tuple of floats on a sampled row, None on every other row.

    The side file must be exactly the registered bytes and bind the graded run: its recipe, state and image, inputs that
    are exactly the graded query's rows at its positions, and an operation that is not the graded one, settled in the
    ledger. ``output_shape`` is the graded query's full output shape (rows first). Anything else refuses, typed.
    """
    import numpy as np

    from carbon.development_session.bundle_construction_worker import _tensors
    from carbon.scoring import inference_pair_evidence as pair
    from carbon.scoring import pair_read_bound

    try:
        n_rows = int(output_shape[0])
        rest = [int(v) for v in output_shape[1:]]
        width = math.prod(rest)
        limit = 2 * pair_read_bound.pair_bytes(n_rows, width)
    except (TypeError, ValueError, IndexError) as exc:
        raise SubsetRepeatRefused("subset_repeat_expected_shape") from exc
    _require(
        type(registered_sha256) is str
        and _DIGEST.fullmatch(registered_sha256) is not None,
        "subset_repeat_registered_digest",
    )
    _require(
        type(raw) is bytes and 0 < len(raw) <= limit, "subset_repeat_evidence_bytes"
    )
    _require(_sha(raw) == registered_sha256, "subset_repeat_registered_digest")
    try:
        document = pair._parse(raw, limit, "subset_repeat")
        _require(
            type(document) is dict
            and set(document) == _DOCUMENT
            and canonical(document) == raw,
            "subset_repeat_shape",
        )
        _require(
            document["schema"] == SCHEMA
            and document["challenge"] == challenge
            and document["challenge_version"] == version
            and is_subset_version(challenge, version)
            and document["scientific_qualification"] is False
            and document["official_eligible"] is False,
            "subset_repeat_identity",
        )
        positions, k = document["positions"], document["k"]
        _require(
            document["n_rows"] == n_rows
            and type(k) is int
            and 1 <= k <= n_rows
            and type(positions) is list
            and len(positions) == k
            and all(type(p) is int and 0 <= p < n_rows for p in positions)
            and all(a < b for a, b in itertools.pairwise(positions)),
            "subset_repeat_positions",
        )
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
            and run["logical_prediction_rows"] == k
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
        predictions_raw = pair._original(
            originals["predictions.json"],
            pair_read_bound.predictions_bytes(k, width),
        )
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
            type(ledger) is str and _LEDGER.fullmatch(ledger) is not None,
            "subset_repeat_accounting_identity",
        )
        pair._accounting(accounting, ledger, operation, originals)
        try:
            flat = pair._flat(
                pair._parse(
                    predictions_raw,
                    pair_read_bound.predictions_bytes(k, width),
                    "prediction",
                ),
                [k, *rest],
            )
        except RecursionError as exc:
            raise SubsetRepeatRefused("subset_repeat_prediction_shape") from exc
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
    twins = [None] * n_rows
    for i, position in enumerate(positions):
        twins[position] = tuple(flat[i * width : (i + 1) * width])
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
    "draw",
    "grade_key",
    "is_subset_version",
    "read",
    "registered_k",
    "registered_promise",
    "side_file",
]
