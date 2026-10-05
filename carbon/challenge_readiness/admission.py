"""Evidence completeness for the two challenge-admission studies.

OWNER-CHALLENGE-ADMISSION-01 as amended on 2026-10-01: an internal development
protocol, never mainnet, and not a qualification gate. Miners see only the
final optimized version. Review moves from every change to every finding:

- **Construction integrity (Track A).** Permission expansion proceeds without
  per-change review; every expansion is recorded (`expansions`). A finding
  (`findings`: score-value divergence, a failing trigger, a gate anomaly)
  escalates: no expansion may be recorded after it. Acceptance is one lock
  review of the state reached, bound to both ledgers and to the permissions it
  locks, which must be a recorded state.
- **Engineering value (Track B).** A full review happens only at one of the
  owner's three conditions: STUCK, WINNING or OWNER_REQUEST, named in it.
- **Conditional evidence is never cited as established**
  (OWNER-GRAPHITE-TEST-WAVE-03 §2, `conditional_evidence`). For internal
  testing a finding stops locking, not exploration: development expansions
  live in the campaign controller's own ledger and never in `expansions`,
  and a result tagged with open findings is refused as the evidence of a PASS
  check and at the LOCK (`conditional_evidence_cited_unconditionally`). A
  FAIL, INCONCLUSIVE or NOT_RUN check may cite it: the report that found a
  finding is conditional on that finding and still backs the FAIL
  (conditional-evidence.v2). `validate(..., ledgers=...)` also consults the
  campaign controllers' ledgers, and the LOCK refuses evidence released only
  by an attested repair (`repair-attestation.v1`).

This reads maintainer-held files; it neither executes submissions nor
authenticates reviewers. Structural validity is not scientific or security
acceptance, and no state activates a challenge.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from . import conditional_evidence

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
#: What a finding may record. A run emits these; a person does not conclude
#: them afterwards (`carbon.battery.value.divergence` emits the first two).
CONDITIONS = {
    "SCORE_VALUE_DIVERGENCE",
    "GATE_ANOMALY",
    "FAILING_TRIGGER",
    "OTHER_SIGNAL",
}
#: The only conditions under which Track B's full review happens (amended §4.2).
REVIEW_TRIGGERS = {"STUCK", "WINNING", "OWNER_REQUEST"}
LEDGER_TRACK = "construction_integrity"
ROOT = Path(__file__).resolve().parents[2]
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")
_COMMIT = re.compile(r"[0-9a-f]{40}\Z")


class AdmissionError(ValueError):
    """The admission record cannot support its claimed state."""


def _fields(track):
    base = {"state", "preregistration", "report", "acceptance"}
    return base | {"expansions", "findings"} if track == LEDGER_TRACK else base


def pending():
    tracks = {}
    for track in CHECKS:
        study = {
            "state": "NOT_STARTED",
            "preregistration": None,
            "report": None,
            "acceptance": None,
        }
        if track == LEDGER_TRACK:
            study.update(expansions=[], findings=[])
        tracks[track] = study
    return {"protocol": PROTOCOL, "scope": None, "tracks": tracks}


def ledger_digest(entries):
    """The digest a lock binds: the canonical bytes of an ordered ledger."""
    body = json.dumps(entries, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(body).hexdigest()


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


_TIME = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z")


def _development_permissions(entry):
    """Whether a LOCK-ledger entry widens into a development-only contract
    variant. The campaign controller records a development expansion only
    under a registered variant's digest (GRAPHITE-DEV-VARIANTS-01), so a
    development entry stripped of its `kind` and tag still names one."""
    from carbon.reconstruction.capability_registry import is_development_variant

    return type(entry) is dict and is_development_variant(entry.get("permissions"))


def _expansions(entries):
    """Every widening, in order: what widened, when, under which profile."""
    if type(entries) is not list:
        raise AdmissionError("admission_list_required")
    previous = None
    for index, entry in enumerate(entries, start=1):
        if type(entry) is dict and (
            "kind" in entry
            or {*conditional_evidence.TAG_KEYS, conditional_evidence.ATTESTED}
            & set(entry)
        ):
            # A development expansion never counts toward or enters a LOCK.
            raise AdmissionError("admission_development_expansion_refused")
        if _development_permissions(entry):
            raise AdmissionError("admission_development_expansion_refused")
        _exact(
            entry,
            {"sequence", "recorded_at", "profile", "version", "widened", "permissions"},
        )
        if entry["sequence"] != index or type(entry["sequence"]) is not int:
            raise AdmissionError("admission_expansion_sequence_gap")
        if type(entry["recorded_at"]) is not str or not _TIME.fullmatch(
            entry["recorded_at"]
        ):
            raise AdmissionError("admission_expansion_time_required")
        if previous is not None and entry["recorded_at"] < previous:
            raise AdmissionError("admission_expansion_out_of_order")
        previous = entry["recorded_at"]
        for key in ("profile", "version", "widened"):
            _text(entry[key])
        if type(entry["permissions"]) is not str or not _DIGEST.fullmatch(
            entry["permissions"]
        ):
            raise AdmissionError("admission_unpinned_expansion")


def _findings(entries, expansions, root):
    """A finding escalates: nothing may widen after it."""
    if type(entries) is not list:
        raise AdmissionError("admission_list_required")
    seen = set()
    for entry in entries:
        _exact(entry, {"id", "condition", "after_expansion", "evidence"})
        _text(entry["id"])
        if entry["id"] in seen:
            raise AdmissionError("admission_duplicate_finding")
        seen.add(entry["id"])
        if entry["condition"] not in CONDITIONS:
            raise AdmissionError("admission_unknown_condition")
        after = entry["after_expansion"]
        if type(after) is not int or not 0 <= after <= len(expansions):
            raise AdmissionError("admission_finding_position_invalid")
        if len(expansions) > after:
            raise AdmissionError("admission_expansion_after_finding")
        _artifact(entry["evidence"], root)


def _cited(body, site, *, lock=False, ledgers=()):
    """Evidence a claim relies on is unconditional (conditional-evidence.v2):
    its bytes carry no open finding, no ledger in `ledgers` recorded them on a
    conditional result, and at a LOCK nothing in them was released only by an
    attested repair."""
    try:
        conditional_evidence.require_unconditional_bytes(
            body, site=site, lock=lock, ledgers=ledgers
        )
    except conditional_evidence.ConditionalEvidenceError as exc:
        raise AdmissionError(exc.code) from exc


def _lock(study, scope, root, ledgers=()):
    """Track A's one review: lock a recorded state, bound to both ledgers and
    to unconditional evidence only."""
    _exact(study["acceptance"], {"reviewer", "decision"})
    _text(study["acceptance"]["reviewer"])
    report = _document(study["report"], root)
    for check in report["checks"].values():
        for ref in check["evidence"]:
            _cited(_artifact(ref, root), "LOCK", lock=True, ledgers=ledgers)
    decision = _document(study["acceptance"]["decision"], root)
    _cited(
        _artifact(study["acceptance"]["decision"], root),
        "LOCK decision",
        lock=True,
        ledgers=ledgers,
    )
    _exact(
        decision,
        {
            "protocol",
            "scope",
            "track",
            "report_digest",
            "reviewer",
            "disposition",
            "expansions_digest",
            "findings_digest",
            "locked_permissions",
        },
    )
    recorded = {e["permissions"] for e in study["expansions"]}
    if (
        decision["protocol"] != PROTOCOL
        or decision["scope"] != scope
        or decision["track"] != LEDGER_TRACK
        or decision["disposition"] != "LOCK"
        or decision["reviewer"] != study["acceptance"]["reviewer"]
        or decision["report_digest"] != study["report"]["sha256"]
    ):
        raise AdmissionError("admission_review_scope_mismatch")
    if decision["expansions_digest"] != ledger_digest(study["expansions"]) or decision[
        "findings_digest"
    ] != ledger_digest(study["findings"]):
        raise AdmissionError("admission_lock_ledger_mismatch")
    if (
        decision["locked_permissions"] not in recorded
        or decision["locked_permissions"] != scope["pins"]["permissions"]
    ):
        raise AdmissionError("admission_lock_unrecorded_state")


def _review(track, study, scope, root):
    """Track B's full review: only at STUCK, WINNING or OWNER_REQUEST."""
    _exact(study["acceptance"], {"reviewer", "decision"})
    _text(study["acceptance"]["reviewer"])
    decision = _document(study["acceptance"]["decision"], root)
    _exact(
        decision,
        {
            "protocol",
            "scope",
            "track",
            "report_digest",
            "reviewer",
            "disposition",
            "trigger",
        },
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
    if decision["trigger"] not in REVIEW_TRIGGERS:
        raise AdmissionError("admission_review_without_trigger")


def _study(track, study, scope, root, ledgers=()):
    _exact(study, _fields(track))
    if track == LEDGER_TRACK:
        _expansions(study["expansions"])
        _findings(study["findings"], study["expansions"], root)
    state = study["state"]
    if type(state) is not str or state not in STATES:
        raise AdmissionError("admission_unknown_state")
    if state == "NOT_STARTED":
        if any(
            study[k] is not None for k in ("preregistration", "report", "acceptance")
        ) or (track == LEDGER_TRACK and (study["expansions"] or study["findings"])):
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
            body = _artifact(ref, root)
            # Only a claim that relies on its evidence is checked: the report
            # that found a finding is conditional on it and still backs the
            # FAIL (conditional-evidence.v2, `RELIANCE`).
            if conditional_evidence.relies(check["result"]):
                _cited(body, f"{track} report evidence", ledgers=ledgers)
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
        if track == LEDGER_TRACK:
            _lock(study, scope, root, ledgers)
        else:
            _review(track, study, scope, root)
    elif study["acceptance"] is not None:
        raise AdmissionError("admission_acceptance_before_pass")


def validate(block, challenge_id, *, repository=ROOT, ledgers=()):
    _exact(block, {"protocol", "scope", "tracks"})
    if block["protocol"] != PROTOCOL:
        raise AdmissionError("admission_unsupported_protocol")
    if block["scope"] is not None:
        _scope(block["scope"], challenge_id)
    _exact(block["tracks"], CHECKS)
    for track, study in block["tracks"].items():
        _study(track, study, block["scope"], repository, ledgers)
    return block


def blockers(block):
    """Use only after validate. This is a readiness report, not activation."""
    return [
        name for name, study in block["tracks"].items() if study["state"] != "ACCEPTED"
    ]
