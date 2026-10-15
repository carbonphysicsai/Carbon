"""Temporary public-fixture evidence only; never writes repository cells."""

from __future__ import annotations

import copy
import hashlib
import io
import json
from types import SimpleNamespace

import pytest

from scripts.dev.launchpad_acceptance import __main__ as cli
from scripts.dev.launchpad_acceptance import cell, matrix, release_check, status

REVISION = "a" * 40
DIGEST = "sha256:" + "b" * 64
FOLDER = "docs/development/evidence/launchpad-acceptance-2026-01-01"


def document(identity="F08", result="PASS", **changes):
    return {
        "schema": release_check.SCHEMA,
        "cell": identity,
        "result": result,
        "date": "2026-01-01",
        "revision": REVISION,
        "machine_kind": "TEMPORARY_UNIT_FIXTURE",
        "actor": "UNIT_FIXTURE_ONLY",
        "within_cap": True,
        "refusal_code": None,
        "evidence": {"backend": "CPU", "feedback_digest": DIGEST},
        **changes,
    }


def raw_record(repository, identity, result="PASS", **changes):
    value = document(identity, result, **changes)
    path = (
        repository
        / FOLDER
        / "cells"
        / (
            identity
            + "-"
            + str(value.get("attempt", 0))
            + "-"
            + value["date"]
            + ".json"
        )
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8", newline="\n")
    return path


def test_covering_design_is_explicit_and_deferred_scope_is_separate():
    assert len(matrix.MATRIX) == len(matrix.BY_CELL) == 43
    assert {entry.family for entry in matrix.MATRIX} == {
        "flow",
        "compute",
        "inference",
        "agent",
        "level",
        "security",
    }
    assert all(
        entry.pass_means and entry.required_evidence_fields for entry in matrix.MATRIX
    )
    assert matrix.BY_CELL["F15"].base_required
    assert not matrix.BY_CELL["C10"].base_required
    assert "Torch" in matrix.BY_CELL["C10"].pass_means
    assert "driver" in matrix.BY_CELL["C11"].option
    assert "practice_result_required" in matrix.BY_CELL["F13"].refusal_codes
    assert all(
        entry.blocked_reason == matrix.D5 and not entry.base_required
        for entry in matrix.LEVELS
    )
    assert matrix.BY_CELL["LA-F17"].blocked_reason == matrix.D1


def test_writer_preserves_validated_bytes_and_refuses_replacement(tmp_path):
    original = document()
    checked = cell.validate_cell(original)
    checked["evidence"]["backend"] = "CHANGED"
    assert original["evidence"]["backend"] == "CPU"
    reference = cell.write_cell(original, tmp_path)
    path = tmp_path / reference
    before = path.read_bytes()
    assert release_check.load_cells(tmp_path).status("F08")["revision"] == REVISION
    with pytest.raises(ValueError, match="ALREADY_RECORDED"):
        cell.write_cell(
            document(
                evidence={"backend": "CPU", "feedback_digest": "sha256:" + "c" * 64}
            ),
            tmp_path,
        )
    assert path.read_bytes() == before
    assert not list(path.parent.glob("*.pending"))


@pytest.mark.parametrize(
    "evidence",
    [
        {"nested": [{"secret_key": "not public"}]},
        {"nested": {"remote_address": "203.0.113.7"}},
        {"nested": [{"balance": 10}]},
        {"profile": {"anything": True}},
        {"profile_digest": "not a digest"},
        {"profile_loaded": {"contents": "not public"}},
        {"profile_loaded": "ghp_" + "a" * 36},
        {"stale_profile_present": {"contents": "not public"}},
        {"stale_profile_present": "ghp_" + "a" * 36},
        {"result_code": "sk-proj-SECRET_FIXTURE"},
        {"result_code": "A" * 64},
        {"backend": "203.0.113.7"},
        {"backend": "ssh://fixture.example"},
        {"message": "arbitrary provider output with a credential"},
        {"source": "docs/development/evidence/protected-pool/anything.json"},
        {
            "source": "docs/development/evidence/launchpad-acceptance-2026-01-01/../private.json"
        },
        {"cost": 0},
        {"fee_total": 123},
        {"fee_total": {"block": 123}},
        {"total_rao": {"cleanup_confirmed": True}},
        {"source": {"fee_total": {"block": 123}}},
        {"nested": {"total_rao": 123}},
        {"nested": [{"unregistered_flag": True}]},
        {"ghp_" + "a" * 36: {}},
        {"ghp_" + "a" * 36: {"backend": "CPU"}},
        {"source": {"backend": "CPU"}},
        {
            "source": "docs/development/evidence/launchpad-acceptance-2026-01-01/FINDINGS.md#ghp_"
            + "a" * 36
        },
        {
            "source": "docs/development/evidence/launchpad-acceptance-2026-01-01/github_pat_"
            + "b" * 40
            + ".md"
        },
        {"score": 0.5},
    ],
)
def test_nested_nonpublic_evidence_is_refused_before_any_write(tmp_path, evidence):
    with pytest.raises(ValueError):
        cell.write_cell(document("F08", "FAIL", evidence=evidence), tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_profile_digest_is_allowed_but_contents_are_not():
    accepted = document(
        "F05",
        evidence={
            "image_digests": [DIGEST],
            "profile_digest": DIGEST,
            "profile_loaded": True,
        },
    )
    assert cell.validate_cell(accepted) == accepted
    accepted["evidence"]["nested"] = {"profile_contents": {"anything": True}}
    with pytest.raises(ValueError):
        cell.validate_cell(accepted)


def test_unregistered_scalar_evidence_cannot_bypass_the_disclosure_allowlist(tmp_path):
    value = document()
    value["evidence"]["fee_total"] = 123
    with pytest.raises(ValueError, match="UNREGISTERED_PUBLIC_EVIDENCE_FIELD"):
        cell.write_cell(value, tmp_path)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "changes",
    [
        {"revision": None},
        {"revision": "short"},
        {"within_cap": False},
        {"within_cap": "true"},
        {"cell": "UNKNOWN"},
        {"cell": "L1"},
        {"cell": "LA-F17"},
        {"date": "2026-01-01/../other"},
        {"attempt": True},
        {"extra": True},
        {"refusal_code": {"anything": True}},
        {"evidence": {"backend": "CPU"}},
    ],
)
def test_invalid_or_deferred_pass_is_not_constructible(changes):
    with pytest.raises(ValueError):
        cell.validate_cell(document(**changes))


@pytest.mark.parametrize(
    "before,after", [(REVISION, "c" * 40), ("git:" + REVISION, "git:" + "c" * 40)]
)
def test_f02_records_real_revision_strings(before, after):
    value = document(
        "F02",
        evidence={
            "before_revision": before,
            "after_revision": after,
            "image_digests": [DIGEST],
            "stale_profile_present": True,
            "refusal_code": "REFUSED",
        },
    )
    assert cell.validate_cell(value) == value


def f01():
    return document(
        "F01",
        evidence={
            "installer_exit_code": 0,
            "image_digests": [DIGEST, "sha256:" + "c" * 64, "sha256:" + "d" * 64],
            "after_install_code": "ACCEPTED",
            "controller_started": True,
        },
    )


def f11():
    return document(
        "F11",
        evidence={
            "submission_id": "bsub-" + "c" * 64,
            "response_code": 202,
            "receiver_pair_matches": True,
        },
    )


def test_real_installer_and_http_numeric_observations_remain_valid():
    assert cell.validate_cell(f01()) == f01()
    assert cell.validate_cell(f11()) == f11()
    assert (
        cell.validate_cell(
            document("F01", "FAIL", evidence={"installer_exit_code": 126})
        )["result"]
        == "FAIL"
    )
    assert (
        cell.validate_cell(document("F11", "FAIL", evidence={"response_code": 503}))[
            "result"
        ]
        == "FAIL"
    )


@pytest.mark.parametrize(
    "field,bad",
    [
        ("installer_exit_code", value)
        for value in (True, False, -1, 256, None, [], {}, "0")
    ]
    + [
        ("response_code", value)
        for value in (True, False, 99, 600, None, [], {}, "202")
    ],
)
def test_numeric_observation_fields_reject_bool_container_and_out_of_domain(field, bad):
    with pytest.raises(ValueError, match="INVALID_NUMERIC_OBSERVATION_CODE"):
        cell.validate_cell(document("F08", "FAIL", evidence={field: bad}))


def test_numeric_pass_observations_cannot_state_failed_install_or_wrong_submit_status(
    tmp_path,
):
    install = f01()
    install["evidence"]["installer_exit_code"] = 126
    with pytest.raises(ValueError, match="PASS_CONTRADICTS_OBSERVATION"):
        cell.validate_cell(install)
    for change in (
        {"response_code": 200},
        {"receiver_pair_matches": False},
    ):
        submit = f11()
        submit["evidence"].update(change)
        with pytest.raises(ValueError, match="PASS_CONTRADICTS_OBSERVATION"):
            cell.validate_cell(submit)
    submit = f11()
    submit["evidence"]["receiver_pair_matches"] = 1
    with pytest.raises(ValueError, match="INVALID_PUBLIC_BOOLEAN"):
        cell.write_cell(submit, tmp_path)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("bad", [1, True, None, [], {}, "short", "ghp_" + "a" * 36])
def test_revision_fields_do_not_accept_typed_observations_or_credentials(bad):
    with pytest.raises(ValueError, match="INVALID_EVIDENCE_REVISION"):
        cell.validate_cell(document("F08", "FAIL", evidence={"before_revision": bad}))


def f15():
    return document(
        "F15",
        evidence={
            "target_count": 2,
            "receiver_pairs_match": True,
            "admitted_journal_digest": DIGEST,
            "refused_journal_digest": "sha256:" + "c" * 64,
            "admit_code": "ADMITTED",
            "refusal_code": "commitment_required",
            "verdicts_averaged": False,
        },
    )


def test_f15_pass_records_two_paired_targets_separate_journals_and_no_averaging():
    value = f15()
    assert cell.validate_cell(value) == value


@pytest.mark.parametrize("identity", ["C3", "C4"])
def test_remote_records_keep_actual_public_identity_and_refusal_codes(identity):
    container = identity == "C4"
    evidence = {
        "transport": "ssh-container" if container else "ssh-docker",
        "verification_code": "build-identity" if container else "image-id",
        "practice_count": 2,
        "backend": "REMOTE_GPU",
        "cleanup_confirmed": True,
        "unreachable_refusal_code": "ssh_unreachable",
        "missing_worker_refusal_code": (
            "no_worker_runtime" if container else "no_worker_image"
        ),
    }
    if container:
        evidence.update(machine_code="RUNPOD_POD", build_digest=DIGEST)
    value = document(identity, evidence=evidence)
    assert cell.validate_cell(value) == value


def test_c11_records_actual_device_request_vocabulary_without_raw_device_identity():
    value = document(
        "C11",
        evidence={
            "requested_device_code": "gpu",
            "observed_device_code": "gpu",
            "driver_code": "nvidia",
            "cleanup_confirmed": True,
        },
    )
    assert cell.validate_cell(value) == value
    for field in ("requested_device_code", "observed_device_code", "driver_code"):
        bad = copy.deepcopy(value)
        bad["evidence"][field] = "ghp_" + "a" * 36
        with pytest.raises(ValueError):
            cell.validate_cell(bad)


def test_existing_lifecycle_states_can_be_observed_without_becoming_f07_pass():
    flow = document(
        "F14",
        evidence={
            "transition_codes": ["RUNNING", "PAUSED", "RUNNING"],
            "journal_digest": DIGEST,
            "paid_call_repeated": False,
        },
    )
    assert cell.validate_cell(flow) == flow
    launch = document("F07", "FAIL", evidence={"final_state": "STOPPED"})
    assert cell.validate_cell(launch) == launch
    launch = document(
        "F07",
        evidence={
            "campaign_id": "c" * 32,
            "final_state": "COMPLETED",
            "first_turn_calls": 3,
            "journal_digest": DIGEST,
            "settlement_code": "SETTLED",
        },
    )
    assert cell.validate_cell(launch) == launch
    launch["evidence"]["final_state"] = "STOPPED"
    with pytest.raises(ValueError, match="PASS_CONTRADICTS_OBSERVATION"):
        cell.validate_cell(launch)


def test_a5_requires_working_block_independently_of_optional_command_support():
    value = document(
        "A5",
        evidence={
            "client_version_code": "HERMES_0_1_0",
            "snippet_digest": DIGEST,
            "connect_code": "UNSUPPORTED",
        },
    )
    with pytest.raises(ValueError, match="PASS_REQUIRES_WORKING_HERMES_BLOCK"):
        cell.validate_cell(value)
    value["result"] = "BLOCKED"
    assert cell.validate_cell(value) == value
    value["result"] = "PASS"
    value["evidence"]["connect_code"] = "VERIFIED"
    value["evidence"]["optional_command_code"] = "UNSUPPORTED"
    assert cell.validate_cell(value) == value


@pytest.mark.parametrize("code", ["REFUSED", "REJECTED", "SUPPORTED", "ACCEPTED"])
def test_a5_capability_or_nonworking_block_does_not_become_a_pass(code):
    value = document(
        "A5",
        evidence={
            "client_version_code": "HERMES_0_1_0",
            "snippet_digest": DIGEST,
            "connect_code": code,
        },
    )
    with pytest.raises(ValueError, match="PASS_REQUIRES_WORKING_HERMES_BLOCK"):
        cell.validate_cell(value)


@pytest.mark.parametrize(
    "field",
    [
        "controller_started",
        "stale_profile_present",
        "profile_loaded",
        "next_steps_present",
        "tty_confirmed",
        "finalized",
        "receiver_pair_matches",
        "sealed",
        "paid_call_repeated",
        "receiver_pairs_match",
        "cleanup_confirmed",
        "verdicts_averaged",
    ],
)
def test_declared_boolean_observations_reject_integer_or_text_substitutes(field):
    assert (
        cell.validate_cell(document("F08", "FAIL", evidence={field: False}))["result"]
        == "FAIL"
    )
    for wrong in (0, 1, "true", []):
        with pytest.raises(ValueError):
            cell.validate_cell(document("F08", "FAIL", evidence={field: wrong}))


@pytest.mark.parametrize(
    "field",
    ["first_turn_calls", "block", "target_count", "practice_count", "tool_count"],
)
def test_declared_counts_reject_boolean_or_text_substitutes(field):
    assert (
        cell.validate_cell(document("F08", "FAIL", evidence={field: 2}))["result"]
        == "FAIL"
    )
    for wrong in (True, False, -1, "2", []):
        with pytest.raises(ValueError, match="INVALID_PUBLIC_COUNT"):
            cell.validate_cell(document("F08", "FAIL", evidence={field: wrong}))


@pytest.mark.parametrize(
    "change",
    [
        {"target_count": 1},
        {"target_count": True},
        {"target_count": 2.0},
        {"receiver_pairs_match": False},
        {"receiver_pairs_match": 1},
        {"verdicts_averaged": True},
        {"verdicts_averaged": 0},
        {"refused_journal_digest": DIGEST},
        {"admit_code": "REFUSED"},
        {"refusal_code": "ADMITTED"},
        {"refusal_code": "evaluation_failed_infra"},
    ],
)
def test_f15_pass_cannot_contradict_owner_d6(change):
    value = f15()
    value["evidence"].update(change)
    with pytest.raises(ValueError):
        cell.validate_cell(value)


@pytest.mark.parametrize(
    "token", ["ghp_" + "a" * 36, "github_pat_" + "b" * 40, "otherprovider_" + "c" * 32]
)
def test_non_openai_credentials_have_no_code_or_metadata_escape(token):
    for evidence in (
        {"backend": token, "feedback_digest": DIGEST},
        {"nested": {"result_code": token}},
        {"nested": [{"check_code": token}]},
        {"backend": {"nested_code": token}},
    ):
        with pytest.raises(ValueError):
            cell.validate_cell(document("F08", "FAIL", evidence=evidence))
    for field in ("actor", "machine_kind"):
        with pytest.raises(ValueError, match="INVALID_PUBLIC_METADATA"):
            cell.validate_cell(document(**{field: token}))


def test_duplicate_and_nonfinite_json_are_not_accepted():
    for raw in ('{"cell":"F08","cell":"F01"}', '{"evidence":NaN}'):
        with pytest.raises(ValueError):
            cell.decode_cell(raw)


def test_chain_hash_is_explicitly_typed_without_inventing_its_algorithm():
    value = document(
        "F10",
        evidence={
            "commitment_digest": DIGEST,
            "extrinsic_digest": "chain:" + "c" * 64,
            "block": 1,
            "tty_confirmed": True,
            "finalized": True,
        },
    )
    assert cell.validate_cell(value) == value
    value["evidence"]["extrinsic_digest"] = "0x" + "c" * 64
    with pytest.raises(ValueError, match="INVALID_EVIDENCE_DIGEST"):
        cell.validate_cell(value)


def test_partial_publication_leaves_no_json_or_pending_file(tmp_path, monkeypatch):
    def fail(*_args, **_kwargs):
        raise OSError("synthetic publication failure")

    monkeypatch.setattr(cell.os, "link", fail)
    with pytest.raises(OSError):
        cell.write_cell(document(), tmp_path)
    assert not list(tmp_path.rglob("*.json"))
    assert not list(tmp_path.rglob("*.pending"))


def test_symlink_directory_never_reaches_its_target(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    try:
        (tmp_path / "docs").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("symlink capability is not available on this host")
    with pytest.raises(ValueError, match="UNSAFE_CELL_DIRECTORY"):
        cell.write_cell(document(), tmp_path)
    assert list(outside.iterdir()) == []


def test_history_reuses_shared_validator_and_keeps_original_failure(tmp_path):
    raw_record(tmp_path, "F01", "FAIL", revision=None, attempt=1)
    raw_record(tmp_path, "F01", "PASS", attempt=2)
    raw_record(tmp_path, "F03")
    raw_record(tmp_path, "F07", "FAIL", evidence={"secret": "NEVER_DISCLOSE"})
    report = status.scoreboard(tmp_path)
    rows = {row["cell"]: row for row in report["cells"]}
    assert (rows["F01"]["result"], rows["F03"]["result"], rows["F07"]["result"]) == (
        "PASS",
        "PASS",
        "FAIL",
    )
    assert rows["F01"]["revision"] == REVISION
    assert len(report["history"]) == 4 and report["history_usable"]
    assert any(
        row["cell"] == "F01" and row["result"] == "FAIL" and row["revision"] is None
        for row in report["history"]
    )
    assert "NEVER_DISCLOSE" not in json.dumps(report)
    assert report["recorded_predicate"] == "UNMET"
    assert not report["qualification"] and not report["launch_authorized"]


def test_merged_backfill_remains_original_evidence_without_rewriting():
    report = status.scoreboard()
    history = {
        row["evidence"].rsplit("/", 1)[-1]: row
        for row in report["history"]
        if row["evidence"].startswith(
            "docs/development/evidence/launchpad-acceptance-2026-10-07/cells/"
        )
    }
    original_revision = "f1dd652debdfc7a6875c38ef988b1fd3c0ccb26b"
    assert history["F01-run1.json"]["result"] == "FAIL"
    assert history["F01-run1.json"]["revision"] is None
    for name in ("F01-run2.json", "F03.json", "F07.json"):
        assert history[name]["revision"] == original_revision
    assert history["F01-run2.json"]["result"] == history["F03.json"]["result"] == "PASS"
    assert history["F07.json"]["result"] == "FAIL"
    assert not report["qualification"] and not report["launch_authorized"]


def test_conflicting_history_and_forged_level_pass_do_not_become_ready(tmp_path):
    raw_record(tmp_path, "L1")
    raw_record(tmp_path, "F08")
    other = tmp_path / FOLDER / "cells" / "F08-conflict.json"
    other.write_text(
        json.dumps(document("F08", "FAIL")), encoding="utf-8", newline="\n"
    )
    report = status.scoreboard(tmp_path)
    assert not report["evidence_usable"] and not report["history_usable"]
    assert report["recorded_predicate"] == "UNMET"
    level = next(row for row in report["cells"] if row["cell"] == "L1")
    assert level["result"] == "BLOCKED" and level["status"] == "UNTESTED"


@pytest.fixture
def complete_recorded_fixture(tmp_path):
    for definition in matrix.MATRIX:
        if definition.family not in ("level", "security"):
            raw_record(tmp_path, definition.cell)
    register = tmp_path / FOLDER / "FINDINGS.md"
    register.write_text(
        "## LA-F1: fixture finding\nFixture disposition only.\n## LA-F17: separate security path\n",
        encoding="utf-8",
        newline="\n",
    )
    proof = {
        "reference": register.relative_to(tmp_path).as_posix(),
        "sha256": hashlib.sha256(register.read_bytes()).hexdigest(),
    }
    evidence = {
        "schema": "carbon.launchpad.completion-evidence.v1",
        "source_revision": REVISION,
        "findings": {"LA-F1": {"disposition": "FIXED", "proof": proof}},
    }
    clients = [
        {
            "id": name,
            "verified": "UNIT_FIXTURE_ONLY",
            "snippets": [{"text": "fixture command"}],
            "unverified": [],
        }
        for name in ("claude-code", "codex", "hermes")
    ]
    cells = release_check.load_cells(tmp_path)
    surfaces = {}
    for surface, name in release_check._SURFACES.items():
        payload = release_check.project({"clients": clients}, name, cells=cells)
        surfaces[surface] = (
            {
                "payload": payload,
                "acceptance_status": payload["acceptance_status"],
                "acceptance_choices": payload["acceptance_choices"],
            }
            if surface.startswith("MCP:")
            else payload
        )
    capture = {
        "schema": "carbon.launchpad.door-label-capture.v1",
        "source_revision": REVISION,
        "surfaces": surfaces,
    }
    return tmp_path, capture, evidence


def test_seven_recorded_predicates_have_basis_without_granting_authority(
    complete_recorded_fixture,
):
    root, capture, evidence = complete_recorded_fixture
    report = status.scoreboard(
        root, revision=REVISION, door_capture=capture, completion_evidence=evidence
    )
    assert len(report["completion"]) == 7
    assert all(
        row["result"] == "PASS" and row["examined"] and row["owner"]
        for row in report["completion"]
    )
    assert report["recorded_predicate"] == "PASS"
    assert not report["qualification"] and not report["launch_authorized"]
    assert (
        next(row for row in report["cells"] if row["cell"] == "LA-F17")["result"]
        == "BLOCKED"
    )


@pytest.mark.parametrize(
    ("identity", "line"), [("F15", 1), ("C3", 2), ("I2", 3), ("A4", 4)]
)
def test_each_required_cell_predicate_has_a_failure_control(
    complete_recorded_fixture, identity, line
):
    root, capture, evidence = complete_recorded_fixture
    raw_record(root, identity, "FAIL", date="2026-01-02")
    report = status.scoreboard(
        root, revision=REVISION, door_capture=capture, completion_evidence=evidence
    )
    assert report["completion"][line - 1]["result"] == "UNMET"
    assert identity in report["completion"][line - 1]["missing"]
    assert report["recorded_predicate"] == "UNMET"


def test_snippets_dispositions_and_revision_capture_cannot_be_success_flags(
    complete_recorded_fixture,
):
    root, capture, evidence = complete_recorded_fixture
    changed = copy.deepcopy(capture)
    changed["surfaces"]["HTTP:/api/v1/setup"]["clients"][0]["unverified"] = [
        "UNVERIFIED: fixture long call"
    ]
    report = status.scoreboard(
        root, revision=REVISION, door_capture=changed, completion_evidence=evidence
    )
    assert report["completion"][4]["result"] == "UNMET"
    assert (
        status.scoreboard(
            root,
            revision=REVISION,
            door_capture=capture,
            completion_evidence={"passed": True},
        )["completion"][5]["result"]
        == "UNKNOWN"
    )
    changed = copy.deepcopy(evidence)
    changed["findings"]["LA-F1"]["proof"]["sha256"] = "0" * 64
    assert (
        status.scoreboard(
            root, revision=REVISION, door_capture=capture, completion_evidence=changed
        )["completion"][5]["result"]
        == "UNMET"
    )
    changed = copy.deepcopy(capture)
    changed["source_revision"] = "c" * 40
    assert (
        status.scoreboard(
            root, revision=REVISION, door_capture=changed, completion_evidence=evidence
        )["completion"][6]["result"]
        == "UNMET"
    )


def test_key_block_requires_actual_named_owner_acknowledgment(
    complete_recorded_fixture,
):
    root, _capture, evidence = complete_recorded_fixture
    raw_record(
        root, "I3", "BLOCKED", date="2026-01-02", refusal_code="OWNER_KEY_UNAVAILABLE"
    )
    ack = root / ".agent/decisions/OWNER-FIXTURE.md"
    ack.parent.mkdir(parents=True)
    ack.write_text(
        "UNIT FIXTURE ONLY: I3 owner key unavailable acknowledgment.\n",
        encoding="utf-8",
        newline="\n",
    )
    evidence["key_blocks"] = {
        "I3": {
            "reason": "OWNER_KEY_UNAVAILABLE",
            "owner_acknowledgment": {
                "reference": ".agent/decisions/OWNER-FIXTURE.md",
                "sha256": hashlib.sha256(ack.read_bytes()).hexdigest(),
            },
        }
    }
    report = status.scoreboard(root, revision=REVISION, completion_evidence=evidence)
    assert report["completion"][2]["result"] == "PASS"
    ack.write_text(
        "UNIT FIXTURE ONLY: I30 is a different identity.\n",
        encoding="utf-8",
        newline="\n",
    )
    evidence["key_blocks"]["I3"]["owner_acknowledgment"]["sha256"] = hashlib.sha256(
        ack.read_bytes()
    ).hexdigest()
    assert (
        status.scoreboard(root, revision=REVISION, completion_evidence=evidence)[
            "completion"
        ][2]["result"]
        == "UNMET"
    )


def test_cli_prints_full_matrix_and_seven_unmet_lines(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(
        cli, "scoreboard", lambda **kwargs: status.scoreboard(tmp_path, **kwargs)
    )
    assert cli.main(["status"]) == 0
    printed = capsys.readouterr().out
    assert all(
        name in printed
        for name in ("F15", "C10", "C11", "LA-F17", "Plan 3.6", "qualification=false")
    )
    assert all(f"  {number}." in printed for number in range(1, 8))
    assert cli.main(["status", "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert len(report["cells"]) == 43 and report["recorded_predicate"] == "UNMET"
    assert cli.main(["status", "--revision", "sk-proj-DO_NOT_ECHO"]) == 2
    assert "DO_NOT_ECHO" not in capsys.readouterr().err


def test_public_inputs_cannot_follow_arbitrary_or_protected_paths(tmp_path):
    for path in (
        "../outside.json",
        "C:/fixture/private.json",
        "docs/development/evidence/protected-pool/data.json",
    ):
        with pytest.raises(ValueError):
            status.read_public_json(path, tmp_path)


def test_stdin_commands_validate_before_writing_and_never_echo_rejection(
    tmp_path, monkeypatch, capsys
):
    def stdin(value):
        monkeypatch.setattr(
            cli.sys,
            "stdin",
            SimpleNamespace(buffer=io.BytesIO(json.dumps(value).encode())),
        )

    stdin(document())
    assert cli.main(["validate"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "VALID_PUBLIC_CELL"
    monkeypatch.setattr(
        cli, "write_cell", lambda value: cell.write_cell(value, tmp_path)
    )
    stdin(document())
    assert cli.main(["write"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "RECORDED"
    stdin(document(evidence={"secret_key": "NEVER_ECHO_THIS_SECRET"}))
    assert cli.main(["write"]) == 2
    output = capsys.readouterr()
    assert not output.out and "NEVER_ECHO_THIS_SECRET" not in output.err
