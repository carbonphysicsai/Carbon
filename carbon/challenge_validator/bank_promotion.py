"""Operator-only promotion from compatible cached bank results.

Raw common scores remain historical data, never accepted bank evidence. The
private operator path recomputes the reviewed core binder from original evidence
and an independently registered source pin, then retains DEVELOPMENT metadata
through the existing PoolStore. Compatibility/reuse is not scientific acceptance
or promotion; no current result from that binder can qualify a winner.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass

from carbon.battery.pool_store import PoolStore, StateError, canonical

from .interface import digest, is_digest

#: A Challenge version's evaluation over its whole pack set
#: (OWNER-FULL-EXAM-BANK-01): derived from the N stored per-batch bindings only.
SET_BINDING = "carbon.scoring.private-evaluation-set-binding.v1"


def _set_evaluation_key(evidence):
    """The lookup key of a set binding: the Challenge version, the exam version,
    the pack-set key, the batch packs and the combined score compatibility. The
    per-batch binding digests bind the evidence but stay out of the key."""
    batches = evidence.get("batches")
    compatibility = evidence.get("score_compatibility")
    if (
        evidence.get("scope") != "PRIVATE_OPERATOR_DEVELOPMENT"
        or evidence.get("status") != "BOUND_DEVELOPMENT_ONLY"
        or evidence.get("official_score") is not False
        or evidence.get("official_eligible") is not False
        or any(
            type(evidence.get(k)) is not str or not evidence[k]
            for k in ("challenge", "challenge_version", "evaluation_version")
        )
        or any(
            not is_digest(evidence.get(k))
            for k in (
                "evaluation_set_key",
                "entry_id",
                "state_digest",
                "source_receipt_sha256",
            )
        )
        or type(batches) is not list
        or not batches
        or any(
            type(b) is not dict
            or set(b)
            != {
                "evaluation_pack_digest",
                "evaluation_key",
                "binding_sha256",
                "case_count",
            }
            or not all(is_digest(v) for k, v in b.items() if k != "case_count")
            or type(b["case_count"]) is not int
            or b["case_count"] < 1
            for b in batches
        )
        or len({b["evaluation_pack_digest"] for b in batches}) != len(batches)
        or len({b["case_count"] for b in batches}) != 1
        or type(compatibility) is not dict
        or set(compatibility)
        != {"score_pack_digest", "scoring_version", "execution_profile_digest"}
        or not is_digest(compatibility["score_pack_digest"])
        or not is_digest(compatibility["execution_profile_digest"])
    ):
        raise StateError("private_evaluation_invalid")
    return digest(
        {
            "challenge": evidence["challenge"],
            "challenge_version": evidence["challenge_version"],
            "evaluation_version": evidence["evaluation_version"],
            "binding_schema": SET_BINDING,
            "score_compatibility": compatibility,
            "evaluation_set_key": evidence["evaluation_set_key"],
            "evaluation_pack_digests": [b["evaluation_pack_digest"] for b in batches],
        }
    )


def _case_count(evidence):
    """How many cases one batch's evaluation covered: its reference coverage."""
    coverage = evidence.get("reference_coverage")
    if type(coverage) is not dict or not all(
        type(v) is int and v >= 0 for v in coverage.values()
    ):
        raise StateError("set_batch_evidence_invalid")
    count = sum(coverage.values())
    if count < 1:
        raise StateError("set_batch_evidence_invalid")
    return count


def build_set_evidence(set_key, bodies):
    """The set binding from the stored per-batch private evaluations of one
    submission (their cache bodies, in the set's order). Derived, never typed:
    every batch must be a bound paired v4 evaluation of the same model on the
    same exam version, and none may be unmeasured (a partial set is refused,
    never a partial mean). A gate failure on any batch makes the set fail the
    gate; otherwise the set total is the equal-weight mean of the batch totals,
    which is the equal-weight mean of A and D (`sealed_exam_common.aggregate`).
    ``entry_id`` is the first batch's, so the baseline's own entry stays a
    leg-minimum source and never contends."""
    if not is_digest(set_key) or type(bodies) not in (list, tuple) or not bodies:
        raise StateError("set_evidence_invalid")
    evidences = []
    for body in bodies:
        evidence = body.get("evidence") if type(body) is dict else None
        if (
            type(evidence) is not dict
            or evidence.get("schema") != PAIRED_BINDING
            or private_evaluation_key(evidence) != body.get("evaluation_key")
        ):
            raise StateError("set_batch_evidence_invalid")
        evidences.append(evidence)
    first = evidences[0]
    common = (
        "challenge",
        "challenge_version",
        "evaluation_version",
        "state_digest",
        "source_receipt_sha256",
    )
    packs = [e["evaluation_pack_digest"] for e in evidences]
    versions = {e["score_compatibility"]["scoring_version"] for e in evidences}
    counts = [_case_count(e) for e in evidences]
    if (
        any(e[k] != first[k] for e in evidences for k in common)
        or len(set(packs)) != len(packs)
        or len(versions) != 1
        # Equal weight per batch is meaningful only for equal-sized batches.
        or len(set(counts)) != 1
    ):
        raise StateError("set_batches_disagree")
    statuses = [e["model_p"]["score_status"] for e in evidences]
    if all(s == SCORED for s in statuses):
        totals = [e["model_p"]["total_score"] for e in evidences]
        if not all(type(t) in (int, float) and math.isfinite(t) for t in totals):
            raise StateError("private_evaluation_invalid")
        status, total = SCORED, math.fsum(totals) / len(totals)
    elif any(s in GATE_FAILED for s in statuses) and all(
        s == SCORED or s in GATE_FAILED for s in statuses
    ):
        status, total = "MANDATORY_GATE_FAILED", None
    else:
        raise StateError("set_batch_not_measured")
    return {
        "schema": SET_BINDING,
        "scope": "PRIVATE_OPERATOR_DEVELOPMENT",
        "status": "BOUND_DEVELOPMENT_ONLY",
        "official_score": False,
        "official_eligible": False,
        "challenge": first["challenge"],
        "challenge_version": first["challenge_version"],
        "evaluation_version": first["evaluation_version"],
        "evaluation_set_key": set_key,
        "batches": [
            {
                "evaluation_pack_digest": e["evaluation_pack_digest"],
                "evaluation_key": body["evaluation_key"],
                "binding_sha256": digest(e),
                "case_count": count,
            }
            for e, body, count in zip(evidences, bodies, counts, strict=True)
        ],
        "entry_id": first["entry_id"],
        "state_digest": first["state_digest"],
        "source_receipt_sha256": first["source_receipt_sha256"],
        "score_compatibility": {
            "score_pack_digest": digest(
                sorted(e["score_compatibility"]["score_pack_digest"] for e in evidences)
            ),
            "scoring_version": versions.pop(),
            "execution_profile_digest": digest(
                sorted(
                    e["score_compatibility"]["execution_profile_digest"]
                    for e in evidences
                )
            ),
        },
        "model_p": {"score_status": status, "total_score": total},
    }


def private_evaluation_key(evidence):
    """Shared evaluated source plus explicit score/execution compatibility.

    Used only on core-produced or privately retained records. This key is a
    lookup identity, not an acceptance capability. Candidate gates and model
    identity deliberately remain outside it.
    """
    if type(evidence) is dict and evidence.get("schema") == SET_BINDING:
        return _set_evaluation_key(evidence)
    if (
        type(evidence) is not dict
        or type(evidence.get("schema")) is not str
        or evidence.get("schema")
        not in {
            "carbon.scoring.private-evaluation-binding.v1",
            "carbon.scoring.private-evaluation-binding.v2",
            "carbon.scoring.private-evaluation-binding.v3",
            "carbon.scoring.private-evaluation-binding.v4",
        }
        or evidence.get("scope") != "PRIVATE_OPERATOR_DEVELOPMENT"
        or evidence.get("status") != "BOUND_DEVELOPMENT_ONLY"
        or any(
            not is_digest(evidence.get(k))
            for k in (
                "source_receipt_sha256",
                "evaluation_version_digest",
                "entry_id",
                "state_digest",
                "model_result_digest",
                "score_result_digest",
            )
        )
        or any(
            type(evidence.get(k)) is not str or not evidence[k]
            for k in (
                "challenge",
                "challenge_version",
                "evaluation_version",
            )
        )
    ):
        raise StateError("private_evaluation_invalid")
    paired = evidence["schema"] == "carbon.scoring.private-evaluation-binding.v4"
    dual = evidence["schema"] in {
        "carbon.scoring.private-evaluation-binding.v3",
        "carbon.scoring.private-evaluation-binding.v4",
    }
    if not is_digest(
        evidence.get(
            "dual_measurement_receipt_sha256" if dual else "benchmark_result_digest"
        )
    ):
        raise StateError("private_evaluation_invalid")
    pack_bound = evidence["schema"] != "carbon.scoring.private-evaluation-binding.v1"
    if pack_bound:
        if not is_digest(evidence.get("evaluation_pack_digest")):
            raise StateError("evaluation_pack_pin_missing")
    elif "evaluation_pack_digest" in evidence:
        raise StateError("evaluation_pack_source_version")
    compatibility = evidence.get("score_compatibility")
    if (
        type(compatibility) is not dict
        or set(compatibility)
        != {
            "score_pack_digest",
            "scoring_version",
            "execution_profile_digest",
        }
        or not is_digest(compatibility["score_pack_digest"])
        or not is_digest(compatibility["execution_profile_digest"])
        or compatibility["scoring_version"]
        != (
            "carbon.scoring.dual-benchmark-pack.v4"
            if dual
            else "carbon.scoring.solver-benchmark-pack.v3"
        )
    ):
        raise StateError("score_compatibility_unavailable")
    dual_identity = {}
    if dual:
        fields = (
            "registration_digest",
            "measurement_contract_digest",
            "producer_digest",
            "common_mask_digest",
            "ordered_query_material_digest",
            "reference_rows_digest",
            "reference_coverage_digest",
        )
        coverage = evidence.get("reference_coverage")
        if (
            evidence.get("official_score") is not False
            or evidence.get("official_eligible") is not False
            or any(not is_digest(evidence.get(field)) for field in fields)
            or type(coverage) is not dict
            or set(coverage) != {"RESOLVED", "UNRESOLVED", "FAILED_INFRA"}
            or any(type(count) is not int or count < 0 for count in coverage.values())
            or sum(coverage.values()) == 0
        ):
            raise StateError("private_evaluation_invalid")
        dual_identity = {
            "binding_schema": evidence["schema"],
            "source_receipt_sha256": evidence["source_receipt_sha256"],
            "reference_coverage": coverage,
            **{field: evidence[field] for field in fields},
        }
        # v4 requires the paired-inference receipt, but like the dual
        # measurement receipt it belongs to one model's run: it stays bound in
        # the retained evidence and out of the key. A key is the shared
        # evaluation context, so a compatible incumbent and contender meet
        # under the same key; `binding_schema` keeps v3 and v4 apart.
        if paired and not is_digest(evidence.get("inference_pair_sha256")):
            raise StateError("private_evaluation_invalid")
    return digest(
        {
            "challenge": evidence["challenge"],
            "challenge_version": evidence["challenge_version"],
            "evaluation_version": evidence["evaluation_version"],
            "evaluation_version_digest": evidence["evaluation_version_digest"],
            "score_compatibility": compatibility,
            **(
                {"evaluation_pack_digest": evidence["evaluation_pack_digest"]}
                if pack_bound
                else {}
            ),
            **dual_identity,
        }
    )


def carry_identity(evidence):
    """The exam a paired dual evaluation measured, without its construction
    version: the evaluation version, the score pack and execution profile, and
    the measurement's registration, contract, producer, mask, ordered queries,
    reference rows and coverage. A carried king meets a challenger of a new
    construction version only where these are equal
    (OWNER-KOTH-CARRY-ACROSS-VERSIONS-01). None for evidence that is not a
    paired dual binding (the only kind the comparator accepts).

    Left out are only the fields that name the construction version or its
    pack wrapper: `challenge_version`, `evaluation_version_digest` (the source
    registration names the version, its TRAIN, interface and job), the source
    receipt pin (a receipt of that registration; a carried king's own pin is
    the carry record's, registered by the operator at the carry) and
    `evaluation_pack_digest` (a version's pack manifest names the version)."""
    private_evaluation_key(evidence)  # validates, or refuses
    if evidence["schema"] != PAIRED_BINDING:
        return None
    fields = (
        "registration_digest",
        "measurement_contract_digest",
        "producer_digest",
        "common_mask_digest",
        "ordered_query_material_digest",
        "reference_rows_digest",
        "reference_coverage_digest",
    )
    identity = {
        "challenge": evidence["challenge"],
        "evaluation_version": evidence["evaluation_version"],
        "score_compatibility": evidence["score_compatibility"],
        "binding_schema": evidence["schema"],
        "reference_coverage": evidence["reference_coverage"],
        **{field: evidence[field] for field in fields},
    }
    return digest({"schema": "carbon.koth.carry-identity.v1", **identity})


@dataclass(frozen=True)
class BankVersion:
    """Exact exam, bank, rule and score-pack identity; never miner supplied."""

    evaluation_digest: str
    pack_digest: str
    rule_digest: str
    pool_version: int
    references: tuple[tuple[str, str], ...]

    def __post_init__(self):
        if (
            not all(
                is_digest(v)
                for v in (self.evaluation_digest, self.pack_digest, self.rule_digest)
            )
            or type(self.pool_version) is not int
            or self.pool_version < 0
            or type(self.references) is not tuple
            or not self.references
            or any(
                type(p) is not tuple or len(p) != 2 or not all(is_digest(v) for v in p)
                for p in self.references
            )
            or tuple(sorted(set(self.references))) != self.references
            or len({p[0] for p in self.references}) != len(self.references)
        ):
            raise ValueError("bank_version_invalid")

    @property
    def identity(self):
        return digest(asdict(self))

    @classmethod
    def current(cls, store, *, evaluation_digest, pack_digest):
        pool = store.pool()
        if pool is None or pool["status"] != "OPEN":
            raise StateError("bank_unavailable")
        identities = store.identities()
        if identities is None:
            raise StateError("not_bound")
        references = []
        for fingerprint in pool["active"]:
            batch = store.batch(fingerprint)
            if batch["references_state"] != "COMPLETE":
                raise StateError("bank_unavailable")
            references.append((fingerprint, batch["references_digest"]))
        return cls(
            evaluation_digest,
            pack_digest,
            identities["rule_digest"],
            pool["version"],
            tuple(sorted(references)),
        )


@dataclass(frozen=True)
class BankResult:
    """Historical v3 score plus claimed bank labels; never accepted evidence.

    Keeping this document readable preserves eef80 cache interpretation. A
    matching pack or retained model does not prove which bank was measured.
    """

    submission_id: str
    version: BankVersion
    artifact_digest: str
    result_json: str

    def __post_init__(self):
        if (
            type(self.submission_id) is not str
            or not self.submission_id
            or type(self.version) is not BankVersion
            or not is_digest(self.artifact_digest)
            or type(self.result_json) is not str
        ):
            raise ValueError("bank_result_invalid")
        body = json.loads(self.result_json)
        if (
            type(body) is not dict
            or body.get("schema") != "carbon.scoring.solver-benchmark-score.v3"
            or body.get("pack_digest") != self.version.pack_digest
            or canonical(body) != self.result_json
        ):
            raise ValueError("bank_result_binding")
        rows = body.get("models")
        if (
            type(rows) is not list
            or any(
                type(row) is not dict or not is_digest(row.get("artifact_digest"))
                for row in rows
            )
            or len({row.get("artifact_digest") for row in rows}) != len(rows)
        ):
            raise ValueError("bank_result_models")

    @classmethod
    def from_common_score(cls, submission_id, version, artifact_digest, result):
        """Read the raw score without asserting that its bank labels are true."""
        return cls(submission_id, version, artifact_digest, canonical(result))

    @property
    def ready(self):
        # Neither the raw v3 score nor the existing benchmark aggregate
        # carries the exact reference/coverage binding. Do not infer it from
        # a caller-supplied BankVersion, including during old cache replay.
        return False

    @property
    def identity(self):
        return digest(asdict(self))

    def document(self):
        return asdict(self)

    @classmethod
    def from_document(cls, body):
        version = dict(body["version"])
        version["references"] = tuple(tuple(p) for p in version["references"])
        return cls(
            body["submission_id"],
            BankVersion(**version),
            body["artifact_digest"],
            body["result_json"],
        )


class BankPromotion:
    """Refuse current unbound scores before any comparison or persistence.

    The private binder supports DEVELOPMENT provenance and compatible reuse.
    It supplies no accepted ScorePack or registered winner comparator, so
    positive promotion remains unavailable. A new label must never reset the
    reward clock.
    """

    def __init__(self, store, *, registered_source_receipt_sha256=None):
        if type(store) is not PoolStore:
            raise TypeError("a pool store is required")
        self.store = store
        # Trusted operator configuration, never derived from submitted bytes.
        # Absent real registration stays unavailable at the core binder.
        self.registered_source_receipt_sha256 = registered_source_receipt_sha256

    def retain_private(self, submission_id, **original_evidence):
        """Resolve originals through the core and retain DEVELOPMENT metadata.

        Keyword inputs are exactly the private binder's inputs, excluding its
        independently registered pin, supplied at trusted operator composition.
        This is not a miner API and does not run a model or reference solver.
        """
        if "registered_source_receipt_sha256" in original_evidence:
            raise StateError("source_pin_override")
        return self.store.record_private_evaluation(
            submission_id,
            registered_source_receipt_sha256=self.registered_source_receipt_sha256,
            **original_evidence,
        )

    def retain_set(self, submission_id, set_key, batch_pack_digests):
        """File the submission's set evaluation, derived from its stored
        per-batch evaluations (`PoolStore.record_set_evaluation`)."""
        return self.store.record_set_evaluation(
            submission_id,
            registered_source_receipt_sha256=self.registered_source_receipt_sha256,
            set_key=set_key,
            batch_pack_digests=list(batch_pack_digests),
        )

    def private_pair(self, submission_id, evaluation_key):
        """Reuse an incumbent's compatible private evidence, never rank it."""
        return self.store.private_evaluation_pair(
            submission_id,
            evaluation_key,
            registered_source_receipt_sha256=self.registered_source_receipt_sha256,
        )

    def cached(self, submission_id, version):
        body = self.store.bank_result(submission_id, version.identity)
        return None if body is None else BankResult.from_document(body)

    def retain(self, result):
        """Current v3 evidence is unbound and cannot enter the accepted cache."""
        return self.store.record_bank_result(result)

    def consider(self, result):
        if type(result) is dict and result.get("schema") == (
            "carbon.challenge-validator.private-evaluation-cache.v1"
        ):
            raise StateError("accepted_score_unavailable")
        if type(result) is not BankResult:
            raise TypeError("a BankResult is required")
        raise StateError("evaluation_binding_unavailable")

    def consider_private(
        self, submission_id, evaluation_key, comparator, *, sealed=False
    ):
        """King of the hill on one shared evaluation key, DEVELOPMENT only.

        The contender meets the incumbent's retained evidence for the same
        key (`private_pair`); `compare_private_pair` decides. A win moves the
        incumbent with the reason `bank_comparison_development`, which the
        reward layer refuses to pay (`PROMOTION_DEVELOPMENT_ONLY`).

        ``sealed`` is true only when the comparison ran on a pack delivered
        through the answer-key route (`SealedPackStore.delivered`, decided by
        the receiver; never the pack's shape). Its win
        then carries `bank_comparison_sealed_testnet`, which the reward layer
        pays only under a testnet policy (Workstream I5).

        An incumbent not yet regraded on this key (a rotation, or a carried
        king whose regrade is unavailable) gives UNAVAILABLE with nothing
        changed: never a reset, never a win (OWNER-EXAM-CAP-ROTATION-01,
        VALIDATOR-KOTH-CARRY-SCOPE-01).
        """
        reason = SEALED_TESTNET_PROMOTION if sealed else DEVELOPMENT_PROMOTION
        # The comparator is built per exam set: register its baseline total, so the public
        # king route reads this stored aggregate and never the private score pack.
        self.store.record_baseline(
            comparator["challenge"],
            comparator["score_pack_digest"],
            comparator.get("baseline_total"),
        )
        try:
            pair = self.private_pair(submission_id, evaluation_key)
        except StateError as refused:
            if refused.code != "incumbent_evaluation_required":
                raise
            return {
                "outcome": UNAVAILABLE,
                "reason": "incumbent_regrade_required",
                "evaluation_key": evaluation_key,
                "candidate": submission_id,
                "incumbent": (self.store.incumbent() or {}).get("model_id"),
            }
        outcome = compare_private_pair(pair, comparator)
        if outcome["outcome"] in (FIRST_INCUMBENT, CHALLENGER):
            self.store.set_incumbent(
                submission_id,
                reason,
                expected=pair["expected_incumbent"],
            )
        elif outcome["outcome"] == DETHRONED:
            # No valid successor: the Challenge has no winner and its share
            # burns until one exists.
            self.store.vacate_incumbent(
                pair["expected_incumbent"], "incumbent_failed_mandatory_gate"
            )
        return outcome


PAIRED_BINDING = "carbon.scoring.private-evaluation-binding.v4"
COMPARATOR_SCHEMA = "carbon.challenge-validator.bank-comparator.v1"
DEVELOPMENT_PROMOTION = "bank_comparison_development"
#: A crown won on a sealed evaluation pack. The reward layer pays it only
#: under a testnet policy; a mainnet policy refuses it until qualification
#: (invariant 5; frontier promotion stays separate, 7.7).
SEALED_TESTNET_PROMOTION = "bank_comparison_sealed_testnet"
SCORED = "SCORED_DEVELOPMENT_CANDIDATE"
#: Statuses that say nothing about the model: infrastructure or evidence,
#: never a science failure, so they can neither win nor be dethroned.
NOT_MEASURED = frozenset({"FAILED_INFRA", "INDETERMINATE_EVIDENCE"})
#: A measured failure of a mandatory gate (an invalid output is one): it
#: dethrones a king (KOTH-TAKEOVER-RULE-01 §3). Other ineligible statuses are
#: not gate failures and change nothing.
GATE_FAILED = frozenset({"MANDATORY_GATE_FAILED", "CANDIDATE_INVALID"})
DETHRONED = "INCUMBENT_DETHRONED"
FIRST_INCUMBENT = "FIRST_INCUMBENT"
CHALLENGER = "CHALLENGER"
INCUMBENT_KEEPS = "INCUMBENT_KEEPS"
NO_WINNER = "NO_WINNER"
UNAVAILABLE = "UNAVAILABLE"


def _comparator(comparator, evidence):
    """The registered comparison rule. Only DEVELOPMENT rules exist: a payable
    rule needs an adopted score pack (KOTH-TAKEOVER-RULE-01)."""
    noise = comparator.get("rebuild_noise") if type(comparator) is dict else None
    if (
        type(comparator) is not dict
        or set(comparator)
        != {
            "schema",
            "scope",
            "challenge",
            "score_pack_digest",
            "rebuild_noise",
            "ties",
            "minimum_source_entry_ids",
            "baseline_total",
        }
        or comparator["schema"] != COMPARATOR_SCHEMA
        or type(comparator["minimum_source_entry_ids"]) is not list
        or not all(is_digest(e) for e in comparator["minimum_source_entry_ids"])
        or comparator["ties"] != "incumbent_keeps"
        or not (
            comparator["baseline_total"] is None
            or (
                type(comparator["baseline_total"]) in (int, float)
                and math.isfinite(comparator["baseline_total"])
            )
        )
        or not (
            noise is None
            or (
                type(noise) is dict
                and set(noise) == {"value", "measurement_digest"}
                and type(noise["value"]) in (int, float)
                and math.isfinite(noise["value"])
                and noise["value"] >= 0
                and is_digest(noise["measurement_digest"])
            )
        )
    ):
        raise StateError("comparator_invalid")
    if comparator["scope"] != "DEVELOPMENT":
        raise StateError("comparator_scope_unadopted")
    if (
        comparator["challenge"] != evidence["challenge"]
        or comparator["score_pack_digest"]
        != evidence["score_compatibility"]["score_pack_digest"]
    ):
        raise StateError("comparator_not_for_this_evaluation")
    return (
        noise,
        frozenset(comparator["minimum_source_entry_ids"]),
        comparator["baseline_total"],
    )


def _scored(body):
    evidence = body["evidence"]
    if evidence.get("schema") not in (PAIRED_BINDING, SET_BINDING):
        raise StateError("comparator_requires_paired_dual")
    model = evidence.get("model_p")
    status = model.get("score_status") if type(model) is dict else None
    if type(status) is not str:
        raise StateError("private_evaluation_invalid")
    total = model.get("total_score")
    if status == SCORED and (
        type(total) not in (int, float) or not math.isfinite(total)
    ):
        raise StateError("private_evaluation_invalid")
    return status, total


def compare_private_pair(pair, comparator):
    """One contender against the incumbent on the same evaluation key.

    - A contender that is not scored never wins.
    - With no incumbent, a scored contender is the first incumbent only if it
      beats Carbon's baseline (the total at the pack's leg minimums) by the
      registered noise; otherwise there is no winner.
    - An incumbent whose evidence is infrastructure or indeterminate is
      UNAVAILABLE: nothing changes. One that measurably fails a mandatory
      gate on this evaluation is dethroned: a scored contender takes the
      crown, otherwise the Challenge has no winner (KOTH-TAKEOVER-RULE-01 §3).
      Any other unscored incumbent status changes nothing.
    - Otherwise the contender must exceed the incumbent's total by the
      Challenge's measured rebuild noise; within it is a tie and the
      incumbent keeps the crown (KOTH-TAKEOVER-RULE-01). No noise registered is
      UNAVAILABLE, never zero.
    """
    candidate = pair["candidate"]
    noise, minimum_sources, floor = _comparator(comparator, candidate["evidence"])
    status, total = _scored(candidate)

    def decided(outcome, reason):
        return {
            "outcome": outcome,
            "reason": reason,
            "evaluation_key": pair["evaluation_key"],
            "candidate": candidate["submission_id"],
            "incumbent": pair["expected_incumbent"],
        }

    incumbent = pair["incumbent"]
    if candidate["evidence"]["entry_id"] in minimum_sources:
        # The baseline run that set the pack's leg minimums sets the bar; it
        # never contends (BASELINE_LEG_MINIMUM_SOURCE_NOT_A_CONTENDER).
        return decided(
            NO_WINNER if incumbent is None else INCUMBENT_KEEPS,
            "leg_minimum_source_not_a_contender",
        )

    def beats_baseline():
        # Carbon's baseline is the unpaid starting king: the first crown, or a
        # crown after a dethrone, must beat it by the margin
        # (OWNER-FIRST-CROWN-BEATS-BASELINE-01).
        if floor is None:
            return UNAVAILABLE, "baseline_floor_unregistered"
        if noise is None:
            return UNAVAILABLE, "rebuild_noise_unregistered"
        if total > floor + noise["value"]:
            return None
        return NO_WINNER, "within_baseline_floor"

    if incumbent is None:
        if status != SCORED:
            return decided(NO_WINNER, "candidate_not_scored")
        held_back = beats_baseline()
        if held_back is not None:
            return decided(*held_back)
        return decided(FIRST_INCUMBENT, "first_scored_contender_beats_baseline")
    if status != SCORED:
        if _scored(incumbent)[0] in GATE_FAILED:
            return decided(DETHRONED, "incumbent_failed_mandatory_gate")
        return decided(INCUMBENT_KEEPS, "candidate_not_scored")
    held, held_total = _scored(incumbent)
    if held in GATE_FAILED:
        held_back = beats_baseline()
        if held_back is not None:
            # The failing king is still dethroned; nobody takes the crown.
            return decided(DETHRONED, "incumbent_failed_mandatory_gate")
        return decided(CHALLENGER, "incumbent_failed_mandatory_gate")
    if held in NOT_MEASURED:
        return decided(UNAVAILABLE, "incumbent_evidence_unavailable")
    if held != SCORED:
        return decided(UNAVAILABLE, "incumbent_not_scored")
    if noise is None:
        return decided(UNAVAILABLE, "rebuild_noise_unregistered")
    if total > held_total + noise["value"]:
        return decided(CHALLENGER, "exceeds_incumbent_beyond_rebuild_noise")
    return decided(INCUMBENT_KEEPS, "within_rebuild_noise_or_tie")
