"""Adversarial evidence mutations against the prospective readiness gate."""

import copy
import hashlib
import json

import pytest

from carbon.challenge_readiness import admission as a
from carbon.challenge_readiness import record as r
from carbon.challenge_readiness.__main__ import main


def artifact(root, name, body):
    data = json.dumps(body, sort_keys=True).encode()
    (root / name).write_bytes(data)
    return {"path": name, "sha256": "sha256:" + hashlib.sha256(data).hexdigest()}


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
        decision = artifact(
            root,
            track + "-decision.json",
            {
                "protocol": a.PROTOCOL,
                "scope": block["scope"],
                "track": track,
                "report_digest": study["report"]["sha256"],
                "reviewer": "FIXTURE_REVIEWER",
                "disposition": "ACCEPT",
            },
        )
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


def test_missing_track_and_schema_downgrade_cannot_skip_tests(tmp_path):
    block = accepted(tmp_path, "fixture")
    del block["tracks"]["engineering_value"]
    with pytest.raises(a.AdmissionError):
        a.validate(block, "fixture", repository=tmp_path)
    doc = copy.deepcopy(r.load_all()[0][0])
    doc["schema"] = "carbon.challenge-readiness.v2"
    with pytest.raises(r.ReadinessError, match="unsupported_schema"):
        r.validate(doc)


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


def test_existing_readiness_launch_path_requires_both_tracks(tmp_path):
    doc = copy.deepcopy(r.load_all()[0][0])
    for review in doc["reviews"].values():
        review.update(state="APPROVED", authority="FIXTURE_REVIEWER")
    doc["training_budget_study"] = {
        "state": "COMPLETE",
        "result": "fixture-report",
        "decision": "fixture-decision",
    }
    with pytest.raises(
        r.ReadinessError, match="launch_approved_before_admission_tests"
    ):
        r.validate(doc)
    doc["admission_tests"] = accepted(tmp_path, doc["challenge_id"])
    r.validate(doc, repository=tmp_path)
    for track in a.CHECKS:
        broken = copy.deepcopy(doc)
        broken["admission_tests"]["tracks"][track] = a.pending()["tracks"][track]
        with pytest.raises(
            r.ReadinessError, match="launch_approved_before_admission_tests"
        ):
            r.validate(broken, repository=tmp_path)


def test_existing_challenges_are_not_silently_accepted():
    for doc, _ in r.load_all():
        assert set(a.blockers(doc["admission_tests"])) == set(a.CHECKS)
        assert doc["admission_tests"]["scope"] is None


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


def test_cli_cannot_treat_empty_or_pending_portfolio_as_admitted(tmp_path, capsys):
    assert main(["validate", "--require-admission"]) == 2
    out = json.loads(capsys.readouterr().out)
    assert out["records_examined"] == 4
    assert len(out["blockers"]) == 4
    assert main(["validate", "--records", str(tmp_path), "--require-admission"]) == 2
    assert json.loads(capsys.readouterr().out)["records_examined"] == 0
