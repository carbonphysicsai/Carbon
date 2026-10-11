"""OWNER-RATE-STUDY-TOKENS-01: SUBMISSION-RATE-STUDY-01's grant spends only
through its study.

Claims tested:
- the registered binding carries exactly the committed grant's limits
  (ceiling USD 30.00, USD 4.91 a run, 6 runs, 39,600 s, 144 submissions), and
  the grant is tokens-only;
- an unbound study run is refused `grant_is_not_bound_to_study`: no study
  named, an unregistered study, or another grant under the study;
- the study's grant outside its study, as a plain phase-3 grant, is refused
  `grant_is_bound_to_a_study`;
- another Challenge, any changed limit, or a submission cap that is not a
  frozen arm cap is refused, typed, before the main-blob check;
- the runner refuses an unbound study run before anything opens.

No live run, key, network or spend.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from carbon.agent_campaign.grant import SpendingGrant
from carbon.agent_campaign.graphite import grant_binding, phase3
from carbon.reconstruction.capability_registry import (
    BATTERY_CHALLENGE,
    COLD_PLATE_CHALLENGE,
)

REPOSITORY = Path(__file__).resolve().parents[2]
GRANTS = REPOSITORY / grant_binding.GRANTS_DIR
STUDY = "SUBMISSION-RATE-STUDY-01"
GRANT_ID = "GRAPHITE-GRANT-RATE-STUDY-TOKENS"
GRANT_FILE = GRANTS / (GRANT_ID + ".json")


def _document(**changes):
    document = json.loads(GRANT_FILE.read_bytes())
    return {**document, "expires_at": "2099-01-01T00:00:00Z", **changes}


def _grant(**changes):
    return SpendingGrant.from_document(_document(**changes))


def _refusal(capsys, call):
    with pytest.raises(SystemExit):
        call()
    return json.loads(capsys.readouterr().out.strip().splitlines()[-1])["reason_code"]


def _check(grant, *, study=STUDY, challenge=BATTERY_CHALLENGE, cap=36, repository):
    return grant_binding.check_study_grant(
        GRANT_FILE,
        grant,
        study=study,
        challenge=challenge,
        submission_cap=cap,
        repository=repository,
    )


def test_the_binding_is_the_committed_grants_limits_and_tokens_only():
    entry = grant_binding.STUDY_GRANTS[STUDY]
    grant = SpendingGrant.from_document(json.loads(GRANT_FILE.read_bytes()))
    assert entry.grant_id == grant.grant_id == GRANT_ID
    assert entry.challenge == BATTERY_CHALLENGE
    assert entry.grant_file == grant_binding.GRANTS_DIR + "/" + GRANT_FILE.name
    assert (
        (
            grant.monetary_ceiling,
            grant.worst_case_run_cost,
            grant.permitted_runs,
            grant.max_runtime_s,
            grant.max_submissions,
        )
        == (
            entry.monetary_ceiling,
            entry.worst_case_run_cost,
            entry.permitted_runs,
            entry.max_runtime_s,
            entry.max_submissions,
        )
        == (Decimal("30.00"), Decimal("4.91"), 6, 39600, 144)
    )
    assert grant.provider == "graphite"
    assert grant_binding.tokens_only(grant)
    assert max(entry.submission_caps) <= entry.max_submissions


def test_an_unbound_study_run_is_refused(tmp_path, capsys):
    grant = _grant()
    for study in (None, "", "SUBMISSION-RATE-STUDY-02", 1):
        code = _refusal(
            capsys, lambda s=study: _check(grant, study=s, repository=tmp_path)
        )
        assert code == grant_binding.STUDY_UNBOUND, study
    other = _grant(grant_id="GRAPHITE-GRANT-PHASE3-R4")
    code = _refusal(capsys, lambda: _check(other, repository=tmp_path))
    assert code == grant_binding.STUDY_UNBOUND


def test_the_study_grant_is_refused_outside_its_study(capsys):
    grant = _grant()
    for challenge in (BATTERY_CHALLENGE, COLD_PLATE_CHALLENGE):
        code = _refusal(
            capsys,
            lambda c=challenge: grant_binding.check_phase3_grant(
                GRANT_FILE, grant, challenge=c
            ),
        )
        assert code == grant_binding.STUDY_GRANT_OUTSIDE


def test_another_challenge_is_refused(tmp_path, capsys):
    code = _refusal(
        capsys,
        lambda: _check(_grant(), challenge=COLD_PLATE_CHALLENGE, repository=tmp_path),
    )
    assert code == "grant_is_for_another_challenge"


@pytest.mark.parametrize(
    "change",
    [
        {"monetary_ceiling": "31.00"},
        {"worst_case_run_cost": "5.00"},
        {"permitted_runs": 7},
        {"max_runtime_s": 43200},
        {"max_submissions": 288},
    ],
)
def test_a_grant_with_other_limits_is_refused(tmp_path, capsys, change):
    code = _refusal(capsys, lambda: _check(_grant(**change), repository=tmp_path))
    assert code == grant_binding.STUDY_LIMITS_DIFFER


@pytest.mark.parametrize("cap", [None, 0, 1, 50, 288, "36", 36.0, True])
def test_a_submission_cap_that_is_not_a_frozen_arm_cap_is_refused(
    tmp_path, capsys, cap
):
    code = _refusal(capsys, lambda: _check(_grant(), cap=cap, repository=tmp_path))
    assert code == grant_binding.STUDY_CAP_REFUSED


@pytest.mark.parametrize("cap", [36, 72, 144])
def test_a_bound_run_goes_on_to_the_main_blob_check(tmp_path, capsys, cap):
    """Every arm cap passes the binding; `tmp_path` is no repository, so the
    run is then refused at the committed-blob check."""
    code = _refusal(capsys, lambda: _check(_grant(), cap=cap, repository=tmp_path))
    assert code == "study_grant_not_committed"


def test_the_runner_refuses_an_unbound_study_run_before_anything_opens(
    tmp_path, capsys
):
    path = tmp_path / "grant.json"
    path.write_text(json.dumps(_document(grant_id="GRAPHITE-GRANT-PHASE3-R4")))
    root = tmp_path / "root"
    code = _refusal(
        capsys,
        lambda: phase3.main(
            [
                "run",
                "--root",
                str(root),
                "--challenge",
                BATTERY_CHALLENGE,
                "--grant",
                str(path),
                "--study",
                STUDY,
                "--study-submission-cap",
                "36",
                "--credential-env",
                "ENGY_API_KEY",
                "--runpod-key-env",
                "RUNPOD_API_KEY",
                "--code-ref",
                "0" * 40,
            ]
        ),
    )
    assert code == grant_binding.STUDY_UNBOUND
    assert not any(root.iterdir())
