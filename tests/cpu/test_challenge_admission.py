"""Adversarial evidence mutations against the admission evidence validator.

The readiness-record wiring (schema v3 records, the `record.py` launch gate and
`--require-admission`) and its record/CLI tests land with #458; this file keeps
every test that does not depend on readiness records.
"""

import hashlib
import json

import pytest

from carbon.challenge_readiness import admission as a


def artifact(root, name, body):
    data = json.dumps(body, sort_keys=True).encode()
    (root / name).write_bytes(data)
    return {"path": name, "sha256": "sha256:" + hashlib.sha256(data).hexdigest()}


PERMISSIONS = "sha256:" + "1" * 64


def expansion(sequence, permissions, at="2026-10-01T00:00:00Z"):
    return {
        "sequence": sequence,
        "recorded_at": at,
        "profile": "FIXTURE_PROFILE",
        "version": "FIXTURE_VERSION",
        "widened": "Fixture widening",
        "permissions": permissions,
    }


def relock(root, block):
    """An attacker or a maintainer re-binds the lock to the current ledgers."""
    study = block["tracks"][a.LEDGER_TRACK]
    ref = study["acceptance"]["decision"]
    decision = json.loads((root / ref["path"]).read_bytes())
    decision["expansions_digest"] = a.ledger_digest(study["expansions"])
    decision["findings_digest"] = a.ledger_digest(study["findings"])
    study["acceptance"]["decision"] = artifact(root, ref["path"], decision)


def accepted(root, cid):
    """Synthetic completeness specimen. It is never production evidence."""
    block = a.pending()
    block["scope"] = {
        "challenge_id": cid,
        "challenge_version": "FIXTURE_ONLY",
        "pins": {k: "sha256:" + "1" * 64 for k in a.PIN_NAMES},
    }
    raw = artifact(root, "raw.json", {"fixture_only": True, "observations": 1})
    for track, study in block["tracks"].items():
        pre = {
            "protocol": a.PROTOCOL,
            "scope": block["scope"],
            "track": track,
            "freeze_commit": "a" * 40,
            "criteria": {k: "Fixture criterion" for k in a.CHECKS[track]},
            "case_policy": "Fixture cases",
            "analysis_policy": "Fixture analysis",
            "budget": "Fixture budget",
        }
        study["preregistration"] = artifact(root, track + "-pre.json", pre)
        report = {
            "protocol": a.PROTOCOL,
            "scope": block["scope"],
            "track": track,
            "preregistration_digest": study["preregistration"]["sha256"],
            "checks": {
                k: {"result": "PASS", "observations": 1, "evidence": [raw]}
                for k in a.CHECKS[track]
            },
            "blockers": [],
            "limitations": ["Fixture only, not acceptance"],
        }
        study["report"] = artifact(root, track + "-report.json", report)
        study["state"] = "ACCEPTED"
        body = {
            "protocol": a.PROTOCOL,
            "scope": block["scope"],
            "track": track,
            "report_digest": study["report"]["sha256"],
            "reviewer": "FIXTURE_REVIEWER",
        }
        if track == a.LEDGER_TRACK:
            # Track A: expansions recorded without review, then one lock.
            study["expansions"] = [expansion(1, PERMISSIONS)]
            body.update(
                disposition="LOCK",
                expansions_digest=a.ledger_digest(study["expansions"]),
                findings_digest=a.ledger_digest(study["findings"]),
                locked_permissions=PERMISSIONS,
            )
        else:
            # Track B: a full review names one of the owner's three triggers.
            body.update(disposition="ACCEPT", trigger="WINNING")
        decision = artifact(root, track + "-decision.json", body)
        study["acceptance"] = {"reviewer": "FIXTURE_REVIEWER", "decision": decision}
    a.validate(block, cid, repository=root)
    return block


def alter_report(
    root, block, mutate, track="construction_integrity", *, renew_acceptance=True
):
    study = block["tracks"][track]
    doc = json.loads((root / study["report"]["path"]).read_bytes())
    mutate(doc)
    study["report"] = artifact(root, study["report"]["path"], doc)
    if renew_acceptance:
        # Attackers can rewrite both assertions. Avoid a false-positive test
        # which rejects only the stale review binding, not the targeted defect.
        ref = study["acceptance"]["decision"]
        decision = json.loads((root / ref["path"]).read_bytes())
        decision["report_digest"] = study["report"]["sha256"]
        study["acceptance"]["decision"] = artifact(root, ref["path"], decision)


@pytest.mark.parametrize(
    "mutate,reason",
    [
        (lambda d, k: d["checks"].pop(k), "exact_keys_required"),
        (
            lambda d, k: d["checks"][k].update(observations=0),
            "conclusion_without_observations",
        ),
        (
            lambda d, k: d["checks"][k].update(observations=True),
            "invalid_observation_count",
        ),
        (
            lambda d, k: d["checks"][k].update(evidence=[]),
            "conclusion_without_observations",
        ),
        (
            lambda d, k: d["checks"][k].update(result="INCONCLUSIVE"),
            "accepted_with_gaps",
        ),
        (lambda d, k: d["checks"][k].update(result="FAIL"), "accepted_with_gaps"),
        (
            lambda d, k: d["blockers"].append("Unresolved defect"),
            "accepted_with_gaps",
        ),
        (lambda d, k: d.update(limitations=[]), "limitations_required"),
        (
            lambda d, k: d["scope"].update(challenge_version="a-different-version"),
            "report_scope_mismatch",
        ),
        (
            lambda d, k: d.update(preregistration_digest="sha256:" + "9" * 64),
            "report_scope_mismatch",
        ),
    ],
)
@pytest.mark.parametrize("track", sorted(a.CHECKS))
def test_acceptance_cannot_hide_failed_skipped_empty_or_foreign_evidence(
    tmp_path, mutate, reason, track
):
    block = accepted(tmp_path, "fixture")
    check = min(a.CHECKS[track])
    alter_report(tmp_path, block, lambda doc: mutate(doc, check), track)
    with pytest.raises(a.AdmissionError, match=reason):
        a.validate(block, "fixture", repository=tmp_path)


def test_missing_track_cannot_skip_tests(tmp_path):
    # The schema-downgrade half of this test needs readiness v3 records and
    # moves with that wiring (#458).
    block = accepted(tmp_path, "fixture")
    del block["tracks"]["engineering_value"]
    with pytest.raises(a.AdmissionError):
        a.validate(block, "fixture", repository=tmp_path)


@pytest.mark.parametrize("pin", sorted(a.PIN_NAMES))
def test_each_material_change_invalidates_prior_evidence(tmp_path, pin):
    block = accepted(tmp_path, "fixture")
    block["scope"]["pins"][pin] = "sha256:" + "2" * 64
    with pytest.raises(a.AdmissionError, match="scope_mismatch"):
        a.validate(block, "fixture", repository=tmp_path)


def test_evidence_tampering_is_detected_even_with_unchanged_success_fields(tmp_path):
    block = accepted(tmp_path, "fixture")
    (tmp_path / "raw.json").write_text('{"observations": 0}')
    with pytest.raises(a.AdmissionError, match="digest_mismatch"):
        a.validate(block, "fixture", repository=tmp_path)


def test_evidence_cannot_escape_repository_through_path_or_symlink(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    outside = artifact(tmp_path, "outside.json", {})
    outside["path"] = "../outside.json"
    with pytest.raises(a.AdmissionError, match="outside_repository"):
        a._artifact(outside, root)
    (root / "link.json").symlink_to(tmp_path / "outside.json")
    outside["path"] = "link.json"
    with pytest.raises(a.AdmissionError, match="outside_repository"):
        a._artifact(outside, root)


@pytest.mark.parametrize("payload", ['{"key": 1, "key": 2}', '{"key": NaN}'])
def test_ambiguous_evidence_json_is_rejected(tmp_path, payload):
    raw = payload.encode()
    (tmp_path / "bad.json").write_bytes(raw)
    with pytest.raises(a.AdmissionError):
        a._document(
            {"path": "bad.json", "sha256": "sha256:" + hashlib.sha256(raw).hexdigest()},
            tmp_path,
        )


def test_a_rewritten_report_cannot_reuse_an_old_acceptance(tmp_path):
    block = accepted(tmp_path, "fixture")
    alter_report(
        tmp_path,
        block,
        lambda d: d["limitations"].append("Changed scope analysis"),
        renew_acceptance=False,
    )
    with pytest.raises(a.AdmissionError, match="review_scope_mismatch"):
        a.validate(block, "fixture", repository=tmp_path)


# --- OWNER-CHALLENGE-ADMISSION-01 as amended: expand freely, escalate on a finding


def test_expansion_needs_no_per_change_review(tmp_path):
    block = a.pending()
    block["scope"] = accepted(tmp_path, "fixture")["scope"]
    study = block["tracks"][a.LEDGER_TRACK]
    pre = accepted(tmp_path, "fixture")["tracks"][a.LEDGER_TRACK]["preregistration"]
    study.update(state="IN_PROGRESS", preregistration=pre)
    study["expansions"] = [
        expansion(1, "sha256:" + "3" * 64),
        expansion(2, "sha256:" + "4" * 64, "2026-10-01T01:00:00Z"),
    ]
    # No review exists, and none is required while widening.
    a.validate(block, "fixture", repository=tmp_path)


def test_an_unrecorded_or_reordered_expansion_is_refused(tmp_path):
    block = accepted(tmp_path, "fixture")
    study = block["tracks"][a.LEDGER_TRACK]
    study["expansions"].append(expansion(3, PERMISSIONS, "2026-10-02T00:00:00Z"))
    with pytest.raises(a.AdmissionError, match="sequence_gap"):
        a.validate(block, "fixture", repository=tmp_path)
    study["expansions"][-1] = expansion(2, PERMISSIONS, "2026-09-01T00:00:00Z")
    with pytest.raises(a.AdmissionError, match="out_of_order"):
        a.validate(block, "fixture", repository=tmp_path)


def test_a_finding_stops_widening_even_when_the_lock_is_renewed(tmp_path):
    block = accepted(tmp_path, "fixture")
    study = block["tracks"][a.LEDGER_TRACK]
    evidence = artifact(tmp_path, "finding.json", {"condition": "fixture"})
    study["findings"] = [
        {
            "id": "F1",
            "condition": "SCORE_VALUE_DIVERGENCE",
            "after_expansion": 1,
            "evidence": evidence,
        }
    ]
    relock(tmp_path, block)
    a.validate(block, "fixture", repository=tmp_path)  # specimen: locked after it
    study["expansions"].append(expansion(2, PERMISSIONS, "2026-10-02T00:00:00Z"))
    relock(tmp_path, block)
    with pytest.raises(a.AdmissionError, match="expansion_after_finding"):
        a.validate(block, "fixture", repository=tmp_path)


def test_a_finding_after_the_lock_voids_it(tmp_path):
    block = accepted(tmp_path, "fixture")
    evidence = artifact(tmp_path, "finding.json", {"condition": "fixture"})
    block["tracks"][a.LEDGER_TRACK]["findings"] = [
        {
            "id": "F2",
            "condition": "GATE_ANOMALY",
            "after_expansion": 1,
            "evidence": evidence,
        }
    ]
    with pytest.raises(a.AdmissionError, match="lock_ledger_mismatch"):
        a.validate(block, "fixture", repository=tmp_path)


def test_a_finding_must_name_an_emitted_condition_and_real_evidence(tmp_path):
    block = accepted(tmp_path, "fixture")
    study = block["tracks"][a.LEDGER_TRACK]
    study["findings"] = [
        {
            "id": "F3",
            "condition": "SOMEONE_NOTICED",
            "after_expansion": 1,
            "evidence": artifact(tmp_path, "f.json", {}),
        }
    ]
    relock(tmp_path, block)
    with pytest.raises(a.AdmissionError, match="unknown_condition"):
        a.validate(block, "fixture", repository=tmp_path)
    study["findings"][0]["condition"] = "FAILING_TRIGGER"
    study["findings"][0]["evidence"]["sha256"] = "sha256:" + "0" * 64
    relock(tmp_path, block)
    with pytest.raises(a.AdmissionError, match="digest_mismatch"):
        a.validate(block, "fixture", repository=tmp_path)


def test_the_lock_must_lock_a_recorded_state(tmp_path):
    block = accepted(tmp_path, "fixture")
    study = block["tracks"][a.LEDGER_TRACK]
    ref = study["acceptance"]["decision"]
    decision = json.loads((tmp_path / ref["path"]).read_bytes())
    decision["locked_permissions"] = "sha256:" + "5" * 64
    study["acceptance"]["decision"] = artifact(tmp_path, ref["path"], decision)
    with pytest.raises(a.AdmissionError, match="lock_unrecorded_state"):
        a.validate(block, "fixture", repository=tmp_path)


def test_track_b_review_names_one_of_the_three_triggers(tmp_path):
    block = accepted(tmp_path, "fixture")
    study = block["tracks"]["engineering_value"]
    ref = study["acceptance"]["decision"]
    for trigger in sorted(a.REVIEW_TRIGGERS):
        decision = json.loads((tmp_path / ref["path"]).read_bytes())
        decision["trigger"] = trigger
        study["acceptance"]["decision"] = artifact(tmp_path, ref["path"], decision)
        a.validate(block, "fixture", repository=tmp_path)
    decision["trigger"] = "ROUTINE_CHANGE"
    study["acceptance"]["decision"] = artifact(tmp_path, ref["path"], decision)
    with pytest.raises(a.AdmissionError, match="review_without_trigger"):
        a.validate(block, "fixture", repository=tmp_path)
