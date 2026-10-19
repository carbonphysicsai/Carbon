"""Operator-only promotion from compatible cached bank results.

Raw common scores remain historical data, never accepted bank evidence. The
private operator path recomputes the reviewed core binder from original evidence
and an independently registered source pin, then retains DEVELOPMENT metadata
through the existing PoolStore. Compatibility/reuse is not scientific acceptance
or promotion; no current result from that binder can qualify a winner.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass

from carbon.battery.pool_store import PoolStore, StateError, canonical

from .interface import digest, is_digest


def private_evaluation_key(evidence):
    """Shared evaluated source plus explicit score/execution compatibility.

    Used only on core-produced or privately retained records. This key is a
    lookup identity, not an acceptance capability. Candidate gates and model
    identity deliberately remain outside it.
    """
    if (
        type(evidence) is not dict
        or type(evidence.get("schema")) is not str
        or evidence.get("schema")
        not in {
            "carbon.scoring.private-evaluation-binding.v1",
            "carbon.scoring.private-evaluation-binding.v2",
            "carbon.scoring.private-evaluation-binding.v3",
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
    dual = evidence["schema"] == "carbon.scoring.private-evaluation-binding.v3"
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
