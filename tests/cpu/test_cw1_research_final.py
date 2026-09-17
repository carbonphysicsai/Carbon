"""Prospective profile/registration tests; synthetic inputs have no result status."""

import pytest
from test_cw1_research_ledger import ledger

from carbon.development_comparison.acceptance import (
    register_fresh_research,
    registration,
)
from carbon.development_session.profile import canonical, digest
from carbon.development_session.research_final import CampaignFinalBudget
from carbon.development_session.research_profile import document


def prepared(tmp_path):
    roots = (tmp_path / "baseline", tmp_path / "challenger")
    profile = document()
    fingerprint = digest(canonical(profile))
    cases = [{"fixture_case": str(i)} for i in range(24)]
    rows = [
        {
            "name": ("eval" if i < 12 else "stress") + f"-{i%12:02d}",
            "role": "EVAL" if i < 12 else "STRESS",
            "case_digest": digest(canonical(case)),
        }
        for i, case in enumerate(cases)
    ]
    manifest = {
        "schema": "carbon.autoresearch.final-cases.v1",
        "epoch": 1,
        "cases": rows,
        "worker_image": "sha256:" + "a" * 64,
        "training_archive_digest": "sha256:" + "b" * 64,
        "training_parents": 72,
    }
    for root in roots:
        root.mkdir()
        for row, case in zip(rows, cases, strict=True):
            (root / (row["name"] + "-case.json")).write_bytes(canonical(case))
        (root / "profile.json").write_bytes(canonical(profile))
        (root / "case-manifest.json").write_bytes(canonical(manifest))
        (root / "final-construction-freeze.json").write_bytes(
            canonical(
                {
                    "schema": "carbon.autoresearch.final-construction.v1",
                    "epoch": 1,
                    "strategy_digest": "sha256:" + "c" * 64,
                    "profile_digest": fingerprint,
                    "cohort_digest": digest(canonical(cases)),
                    "randomness_digests": ["sha256:" + str(i) * 64 for i in range(3)],
                }
            )
        )
    return roots


def register(tmp_path, roots):
    return register_fresh_research(
        tmp_path / "comparison",
        prepared_roots=roots,
        quarantine_journal=tmp_path / "quarantine.sqlite3",
        reference_root=tmp_path,
        sessions={str(root): {"fixture_trust": "no_source_evidence"} for root in roots},
    )


def test_fresh_registration_freezes_direction_without_claiming_a_result(tmp_path):
    roots = prepared(tmp_path)
    pin = register(tmp_path, roots)
    value, key = registration(tmp_path / "comparison", pin)
    assert value["schema"].endswith(".v2")
    assert value["source_roles"] == {
        "baseline": str(roots[0]),
        "challenger": str(roots[1]),
    }
    assert value["research_profile"] == document()
    assert not (tmp_path / "comparison/development-acceptance.json").exists()
    assert key.public_key


def test_registration_rejects_changed_cases_and_already_started_construction(tmp_path):
    roots = prepared(tmp_path)
    (roots[0] / "evaluations").mkdir()
    with pytest.raises(ValueError, match="before"):
        register(tmp_path, roots)
    (roots[0] / "evaluations").rmdir()
    (roots[0] / "eval-00-case.json").write_bytes(canonical({"fixture_case": "altered"}))
    with pytest.raises(ValueError, match="cohort"):
        register(tmp_path, roots)


def test_final_reconstruction_and_uncertain_failure_consume_separate_counters(tmp_path):
    meter = ledger(tmp_path)
    budget = CampaignFinalBudget(meter, "alice")
    assert (
        budget.run_worker("candidate-train-0", lambda: "synthetic returned object")
        == "synthetic returned object"
    )
    with pytest.raises(ValueError, match="reconcile"):
        budget.run_worker("candidate-train-0", lambda: pytest.fail("duplicate"))

    def fail():
        raise RuntimeError("engineering failure")

    with pytest.raises(RuntimeError):
        budget.run_worker("candidate-predict-0", fail)
    used = meter.status(owner="alice")["used"]
    assert used["final_replicas"] == 1
    assert used["research_trials"] == 0
    assert used["numerical_milliseconds"] >= 720000


def test_registration_checks_generator_canonical_bytes_including_newline(tmp_path):
    import json

    roots = prepared(tmp_path)
    for root in roots:
        manifest = json.loads((root / "case-manifest.json").read_bytes())
        for row in manifest["cases"]:
            path = root / (row["name"] + "-case.json")
            body = path.read_bytes() + b"\n"
            path.write_bytes(body)
            row["case_digest"] = digest(body)
        (root / "case-manifest.json").write_bytes(canonical(manifest))
    assert register(tmp_path, roots)
