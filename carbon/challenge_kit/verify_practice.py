"""Practice on the data kit's VERIFY SET, for the versions that use it (owner 7 Nov: "Yes, verify set").

New versions retire the shared public practice bank for data kits (OWNER-MINER-DATA-KITS-LAUNCH-STAPLE-01). Their
practice in the app scores the kit's verify set instead: a small published file of designs with Carbon's own
solved truths, pinned by its receipted sha256. One path, labelled practice, never a grade:

- the query is the verify designs' inputs, in the interface's input order;
- each design is scored by the Challenge's own PRACTICE measurement (the same `score_case` / `aggregate` the public
  practice bank uses), on the verify truths;
- beside it, the kit's own accuracy-within-U check (`local_scorer`), where the verify set carries a U;
- design value, picks and the sealed minimums need Carbon's hidden pools: never computed here, always reported
  "not evaluated locally".

A version uses this only when it is listed in `REGISTRY` with its kit's verify set path and receipted sha256. The
registry is empty until each verify set lands (the version owner builds it; the Validator receipts its digest).
Until then every practice keeps its current path unchanged.

It opens no evaluation pack, seed, sealed or private material. DEVELOPMENT practice feedback only.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LABEL = "practice (kit verify set)"
SOURCE = "kit_verify_set"
NOT_EVALUATED = "not evaluated locally"
MOTOR = "electric-motor-magnetics"

#: (challenge id, version) -> (the verify set's path from the checkout root, its receipted sha256). Switching a
#: version on = one row here, with the kit's file and the Validator-receipted digest. Empty until a set lands.
REGISTRY: dict[tuple[str, str], tuple[str, str]] = {}


class VerifyPracticeRefused(ValueError):
    """The registered verify set is missing, altered or malformed: the practice refuses, never falls back."""


@dataclass(frozen=True)
class VerifySource:
    challenge_id: str
    version: str
    document: dict
    sha256: str

    @property
    def designs(self):
        return self.document["designs"]

    def query(self, input_names):
        """The verify designs' inputs as rows, in the interface's input order."""
        import numpy as np

        return np.asarray(
            [[float(d["inputs"][name]) for name in input_names] for d in self.designs],
            dtype=np.float64,
        )

    @property
    def case_ids(self):
        return [d["case_id"] for d in self.designs]


def registered(challenge_id: str, version: str) -> bool:
    return (challenge_id, version) in REGISTRY


def source(challenge_id: str, version: str, *, root=None, registry=None):
    """This version's verify-set practice source, or None when it keeps its current practice."""
    from carbon.challenge_kit import local_scorer

    table = REGISTRY if registry is None else registry
    entry = table.get((challenge_id, version))
    if entry is None:
        return None
    relative, sha256 = entry
    path = Path(root or ROOT) / relative
    try:
        raw = path.read_bytes()
    except OSError:
        raise VerifyPracticeRefused("verify_set_missing") from None
    names = _input_names(challenge_id)
    try:
        document = local_scorer.load_verify_set(raw, sha256, names)
    except local_scorer.ScorerRefused as refused:
        raise VerifyPracticeRefused("verify_set_invalid: " + str(refused)) from None
    return VerifySource(challenge_id, version, document, sha256)


def _input_names(challenge_id):
    if challenge_id == MOTOR:
        from carbon.motor import domain

        return tuple(domain.INPUTS)
    raise VerifyPracticeRefused("verify_practice_challenge_unsupported")


def score_motor(src: VerifySource, rows, train):
    """Motor practice on the verify set: (predictions by case id, summary, verify block).

    `rows` are the model's 60-angle torque curves for `src.designs`, in order; `train` is the public TRAIN records
    the practice scales come from (`exam.scales_from_train`), as the public practice bank uses them.
    """
    from carbon.challenge_kit import local_scorer
    from carbon.motor import exam

    if src.challenge_id != MOTOR:
        raise VerifyPracticeRefused("verify_practice_challenge_unsupported")
    designs = src.designs
    if len(rows) != len(designs):
        raise VerifyPracticeRefused("verify_practice_row_count")
    scales = exam.scales_from_train(train)
    predictions = {}
    scored = []
    for design, row in zip(designs, rows):
        curve = [float(v) for v in row]
        predictions[design["case_id"]] = {"torque_nm": curve}
        reference = {
            "case_id": design["case_id"],
            "inputs": dict(design["inputs"]),
            "outputs": {"torque_nm": [float(v) for v in design["truth"]["torque_nm"]]},
            "status": "OK",
        }
        scored.append(
            exam.score_case(predictions[design["case_id"]], reference, scales)
        )
    summary = exam.aggregate(scored)
    u = local_scorer._u(src.document)
    checks = [local_scorer._motor_design(d, r, u) for d, r in zip(designs, rows)]
    verify = {
        "label": LABEL,
        "source": SOURCE,
        "verify_set_sha256": src.sha256,
        "aggregate": local_scorer._motor_aggregate(checks, u),
        "design_value": NOT_EVALUATED,
        "minimums": NOT_EVALUATED,
    }
    return predictions, summary, verify
