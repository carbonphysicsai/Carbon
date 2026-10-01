"""Evidence completeness for the two challenge-admission studies.

This reads maintainer-held files; it neither executes submissions nor authenticates
reviewers. Structural validity is not scientific or security acceptance. Only
existing human review authority can accept a study; no state activates a challenge.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

PROTOCOL = "carbon.challenge-admission.v1"
STATES = {"NOT_STARTED", "IN_PROGRESS", "FAILED", "INCONCLUSIVE", "ACCEPTED"}
CHECKS = {
    "construction_integrity": {
        "baseline_and_permission_ablation",
        "artifact_and_dependency_attacks",
        "adaptive_feedback_and_state_attacks",
        "score_exploitation_and_tail_failures",
        "resource_and_failure_accounting",
        "construction_evaluation_isolation",
        "reconstruction_and_recipient_rebuild",
        "fresh_attack_confirmation",
    },
    "engineering_value": {
        "reference_and_decision_contract",
        "independent_model_families",
        "eligibility_before_ranking",
        "coverage_and_unresolved_sensitivity",
        "rank_and_useful_effect_uncertainty",
        "unsafe_and_subgroup_outcomes",
        "adaptive_design_search",
        "untouched_confirmation",
        "customer_evidence_and_limits",
    },
}
PIN_NAMES = {
    "generator",
    "reference",
    "score",
    "construction",
    "environment",
    "permissions",
    "budget",
    "decision_contract",
    "population",
    "feedback",
}
ROOT = Path(__file__).resolve().parents[2]
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")
_COMMIT = re.compile(r"[0-9a-f]{40}\Z")


class AdmissionError(ValueError):
    """The admission record cannot support its claimed state."""


def pending():
    return {
        "protocol": PROTOCOL,
        "scope": None,
        "tracks": {
            track: {
                "state": "NOT_STARTED",
                "preregistration": None,
                "report": None,
                "acceptance": None,
            }
            for track in CHECKS
        },
    }


def _exact(value, keys):
    if type(value) is not dict or set(value) != set(keys):
        raise AdmissionError("admission_exact_keys_required")


def _text(value):
    if (
        type(value) is not str
        or not value.strip()
        or value.strip() in {"HUMAN_INPUT", "TODO"}
    ):
        raise AdmissionError("admission_nonempty_text_required")


def _no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise AdmissionError("admission_duplicate_json_key")
        result[key] = value
    return result


def _artifact(ref, root):
    _exact(ref, {"path", "sha256"})
    _text(ref["path"])
    if type(ref["sha256"]) is not str or not _DIGEST.fullmatch(ref["sha256"]):
        raise AdmissionError("admission_invalid_digest")
    relative = Path(ref["path"])
    root = Path(root).resolve()
    path = (root / relative).resolve()
    if (
        relative.is_absolute()
        or ".." in relative.parts
        or not path.is_relative_to(root)
    ):
        raise AdmissionError("admission_artifact_outside_repository")
    try:
        if path.stat().st_size > 32 * 1024 * 1024:
            raise AdmissionError("admission_artifact_too_large")
        body = path.read_bytes()
    except OSError as exc:
        raise AdmissionError("admission_artifact_unavailable") from exc
    if "sha256:" + hashlib.sha256(body).hexdigest() != ref["sha256"]:
        raise AdmissionError("admission_artifact_digest_mismatch")
    return body


def _document(ref, root):
    try:
        return json.loads(
            _artifact(ref, root),
            object_pairs_hook=_no_duplicates,
            parse_constant=lambda _: (_ for _ in ()).throw(
                AdmissionError("admission_nonfinite_json")
            ),
        )
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise AdmissionError("admission_invalid_json") from exc


def _scope(scope, challenge_id):
    _exact(scope, {"challenge_id", "challenge_version", "pins"})
    if scope["challenge_id"] != challenge_id:
        raise AdmissionError("admission_wrong_challenge")
    _text(scope["challenge_version"])
    _exact(scope["pins"], PIN_NAMES)
    for value in scope["pins"].values():
        if type(value) is not str or not _DIGEST.fullmatch(value):
            raise AdmissionError("admission_unpinned_scope")


def _study(track, study, scope, root):
    _exact(study, {"state", "preregistration", "report", "acceptance"})
    state = study["state"]
    if type(state) is not str or state not in STATES:
        raise AdmissionError("admission_unknown_state")
    if state == "NOT_STARTED":
        if any(
            study[k] is not None for k in ("preregistration", "report", "acceptance")
        ):
            raise AdmissionError("admission_evidence_before_start")
        return
    if scope is None:
        raise AdmissionError("admission_scope_required")
    pre = _document(study["preregistration"], root)
    _exact(
        pre,
        {
            "protocol",
            "scope",
            "track",
            "freeze_commit",
            "criteria",
            "case_policy",
            "analysis_policy",
            "budget",
        },
    )
    if pre["protocol"] != PROTOCOL or pre["scope"] != scope or pre["track"] != track:
        raise AdmissionError("admission_preregistration_scope_mismatch")
    if type(pre["freeze_commit"]) is not str or not _COMMIT.fullmatch(
        pre["freeze_commit"]
    ):
        raise AdmissionError("admission_freeze_commit_required")
    # The commit is the prior scope/criteria commitment, not a self-referential
    # hash of this file. Review checks ancestry and chronology against the ledger.
    _exact(pre["criteria"], CHECKS[track])
    for value in pre["criteria"].values():
        _text(value)
    for key in ("case_policy", "analysis_policy", "budget"):
        _text(pre[key])
    if state == "IN_PROGRESS":
        if study["report"] is not None or study["acceptance"] is not None:
            raise AdmissionError("admission_finished_evidence_during_run")
        return
    report = _document(study["report"], root)
    _exact(
        report,
        {
            "protocol",
            "scope",
            "track",
            "preregistration_digest",
            "checks",
            "blockers",
            "limitations",
        },
    )
    if (
        report["protocol"] != PROTOCOL
        or report["scope"] != scope
        or report["track"] != track
        or report["preregistration_digest"] != study["preregistration"]["sha256"]
    ):
        raise AdmissionError("admission_report_scope_mismatch")
    _exact(report["checks"], CHECKS[track])
    for name in ("blockers", "limitations"):
        if type(report[name]) is not list:
            raise AdmissionError("admission_list_required")
        for value in report[name]:
            _text(value)
    if not report["limitations"]:
        raise AdmissionError("admission_limitations_required")
    all_pass = True
    for check in report["checks"].values():
        _exact(check, {"result", "observations", "evidence"})
        if check["result"] not in ("PASS", "FAIL", "INCONCLUSIVE", "NOT_RUN"):
            raise AdmissionError("admission_unknown_check_result")
        count = check["observations"]
        if type(count) is not int or count < 0:
            raise AdmissionError("admission_invalid_observation_count")
        if type(check["evidence"]) is not list:
            raise AdmissionError("admission_evidence_list_required")
        for ref in check["evidence"]:
            _artifact(ref, root)
        if check["result"] in ("PASS", "FAIL") and (
            count == 0 or not check["evidence"]
        ):
            raise AdmissionError("admission_conclusion_without_observations")
        if check["result"] == "NOT_RUN" and count != 0:
            raise AdmissionError("admission_not_run_with_observations")
        all_pass &= check["result"] == "PASS"
    if state == "ACCEPTED":
        if not all_pass or report["blockers"]:
            raise AdmissionError("admission_accepted_with_gaps")
        _exact(study["acceptance"], {"reviewer", "decision"})
        _text(study["acceptance"]["reviewer"])
        decision = _document(study["acceptance"]["decision"], root)
        _exact(
            decision,
            {"protocol", "scope", "track", "report_digest", "reviewer", "disposition"},
        )
        if (
            decision["protocol"] != PROTOCOL
            or decision["scope"] != scope
            or decision["track"] != track
            or decision["disposition"] != "ACCEPT"
            or decision["reviewer"] != study["acceptance"]["reviewer"]
            or decision["report_digest"] != study["report"]["sha256"]
        ):
            raise AdmissionError("admission_review_scope_mismatch")
    elif study["acceptance"] is not None:
        raise AdmissionError("admission_acceptance_before_pass")


def validate(block, challenge_id, *, repository=ROOT):
    _exact(block, {"protocol", "scope", "tracks"})
    if block["protocol"] != PROTOCOL:
        raise AdmissionError("admission_unsupported_protocol")
    if block["scope"] is not None:
        _scope(block["scope"], challenge_id)
    _exact(block["tracks"], CHECKS)
    for track, study in block["tracks"].items():
        _study(track, study, block["scope"], repository)
    return block


def blockers(block):
    """Use only after validate. This is a readiness report, not activation."""
    return [
        name for name, study in block["tracks"].items() if study["state"] != "ACCEPTED"
    ]
