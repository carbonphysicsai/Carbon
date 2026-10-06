"""Dedicated zero-spend admission controllers and readiness item A4.

A4-DEDICATED-ADMISSION-CONTROLLERS-01, after the Test Lead's ruling on A4
(2026-10-06): battery, cooling and motor each designate a dedicated admission
controller bound to a zero-spend grant, not a spent run root.

- A zero-spend grant (every amount 0, 0 runs, 0 submissions) is whole or
  refused, and every path that could spend refuses it before anything is
  reserved: `register_campaign`, `launch`, the live model and the phase-3
  provider (`grant_is_zero_spend`).
- `phase3 admission-controller init` creates an empty store bound to the
  Challenge's committed zero-spend grant, refuses an existing store, and
  prints the identity `conditions --identity` then prints for the same root.
- The committed designation has one PENDING entry per Challenge; A4 is
  FAIL while pending (a LOCK is refused), PASS for a DESIGNATED sha256, FAIL for a missing,
  malformed or duplicated entry.

Each guard is switched off once (`MUTATIONS`) and its test shown to fail.
Synthetic grants and temporary roots only: no spend, pod, model or key.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import test_agent_campaign_controller as tc

from carbon.agent_campaign import controller as ctl
from carbon.agent_campaign.fake import FakeProvider
from carbon.agent_campaign.grant import GrantError, SpendingGrant
from carbon.agent_campaign.graphite import grant_binding, phase3
from carbon.agent_campaign.graphite.model import (
    LiveModel,
    ModelAccessRefused,
    ScriptedModel,
)
from carbon.agent_campaign.provider import ProviderUnavailable
from carbon.challenge_pipeline import admission_controllers as designations
from carbon.challenge_pipeline.readiness import checks, model
from carbon.reconstruction.capability_registry import (
    BATTERY_CHALLENGE,
    COLD_PLATE_CHALLENGE,
    MOTOR_CHALLENGE,
)

CHALLENGES = (BATTERY_CHALLENGE, COLD_PLATE_CHALLENGE, MOTOR_CHALLENGE)
ZERO = {
    "monetary_ceiling": "0.00",
    "cleanup_allowance": "0.00",
    "worst_case_run_cost": "0.00",
    "permitted_runs": 0,
    "max_submissions": 0,
}
DIGEST = "sha256:" + "e" * 64


# -- helpers ---------------------------------------------------------------------------
def zero_document(**changes):
    """R2's shape with every spend field zero: a synthetic admission grant."""
    base = {"grant_id": "test-admission-grant", "provider": "graphite", **ZERO}
    return tc.grant_document(**{**base, **changes})


def register_grants(monkeypatch, directory, **documents):
    """Commit (into `directory`) one synthetic zero-spend grant per Challenge
    and point the registry at them; returns `{challenge: grant path}`."""
    paths = {}
    for challenge in CHALLENGES:
        document = documents.get(challenge) or zero_document(
            grant_id="test-admission-" + challenge
        )
        path = Path(directory) / f"grant-{challenge}.json"
        path.write_text(json.dumps(document))
        paths[challenge] = path
    monkeypatch.setattr(
        grant_binding,
        "ADMISSION_CONTROLLER_GRANTS",
        {c: str(p) for c, p in paths.items()},
    )
    return paths


def run(capsys, *argv):
    """`phase3.main(argv)`: (exit code, stdout JSON)."""
    try:
        code = phase3.main(list(argv))
    except SystemExit as stop:
        code = stop.code
    return code, json.loads(capsys.readouterr().out)


def init(capsys, root, grant, challenge):
    return run(
        capsys,
        "admission-controller",
        "init",
        "--root",
        str(root),
        "--challenge",
        challenge,
        "--grant",
        str(grant),
    )


def identity(capsys, root, grant, challenge):
    return run(
        capsys,
        "conditions",
        "--root",
        str(root),
        "--grant",
        str(grant),
        "--challenge",
        challenge,
        "--identity",
    )


def designate(monkeypatch, directory, *entries):
    path = Path(directory) / "admission_controllers.json"
    path.write_text(
        json.dumps({"schema": designations.SCHEMA, "controllers": list(entries)})
    )
    monkeypatch.setattr(designations, "PATH", path)
    return path


def entry(challenge, identity_=None, status=None, level=0, name="admission-l0"):
    return {
        "challenge": challenge,
        "level": level,
        "name": name,
        "identity": identity_,
        "status": status
        or (designations.PENDING if identity_ is None else designations.DESIGNATED),
    }


def a4(challenge, repository, level=0):
    (item,) = [i for i in model.load_items() if i["id"] == "A4"]
    ctx = checks.Context(challenge=challenge, level=level, repository=repository)
    return checks.CHECKS[item["check"]](item, ctx)


def a4_with(tmp_path, challenge, *entries, raw=None):
    """A4 against a designation file holding `entries` (the check reads the
    module's `PATH`, which this swaps for the call only)."""
    path = tmp_path / "admission_controllers.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    body = {"schema": designations.SCHEMA, "controllers": list(entries)}
    path.write_text(raw if raw is not None else json.dumps(body))
    saved = designations.PATH
    designations.PATH = path
    try:
        return a4(challenge, tmp_path)
    finally:
        designations.PATH = saved


# -- the zero-spend grant ------------------------------------------------------------------
def test_a_zero_spend_grant_loads_and_says_so():
    grant = SpendingGrant.from_document(zero_document())
    assert grant.zero_spend
    assert (grant.permitted_runs, grant.max_submissions) == (0, 0)
    assert not SpendingGrant.from_document(tc.grant_document()).zero_spend


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"permitted_runs": 1}, "0 runs and 0 submissions"),
        ({"max_submissions": 1}, "0 runs and 0 submissions"),
        ({"permitted_runs": False}, "0 runs and 0 submissions"),
        ({"monetary_ceiling": "1.00"}, "positive"),
        ({"cleanup_allowance": "0.01"}, "positive"),
        ({"worst_case_run_cost": "0.01"}, "cannot cover"),
    ],
)
def test_a_partly_zero_grant_is_refused(changes, message):
    with pytest.raises(GrantError, match=message):
        SpendingGrant.from_document(zero_document(**changes))


def check_run_refused_before_reservation(tmp_path, _monkeypatch, _capsys):
    """No campaign, no launch, no model, no phase-3 session under a zero-spend
    grant; nothing is reserved or recorded."""
    grant = SpendingGrant.from_document(zero_document(provider="fake"))
    control = ctl.CampaignController(
        root=tmp_path / "store",
        provider=FakeProvider(),
        grant=grant,
        operator="carbon-operator",
        clock=tc.Clock(),
    )
    try:
        with pytest.raises(ctl.ControllerError) as refused:
            tc.register(control)
        assert refused.value.code == ctl.GRANT_ZERO_SPEND
        with pytest.raises(ctl.ControllerError) as refused:
            control.launch(tc.spec(), "run-1")
        assert refused.value.code == ctl.GRANT_ZERO_SPEND
        assert not [e for e in control.ledger() if e["kind"] == "launch_intent"]
        with control._db() as db:
            assert db.execute("SELECT COUNT(*) FROM runs").fetchone()[0] == 0
    finally:
        control.close()
    graphite = SpendingGrant.from_document(zero_document())
    with pytest.raises(ModelAccessRefused, match=ctl.GRANT_ZERO_SPEND):
        LiveModel(grant=graphite, credential_file="unused", provider="graphite")
    with pytest.raises(ProviderUnavailable, match=ctl.GRANT_ZERO_SPEND):
        phase3.Phase3Provider(
            root=tmp_path / "graphite",
            grant=graphite,
            model=ScriptedModel([]),
            pods=phase3.NoPods(),
        )


def test_any_run_under_a_zero_spend_grant_is_refused_before_reservation(
    tmp_path, monkeypatch, capsys
):
    check_run_refused_before_reservation(tmp_path, monkeypatch, capsys)


# -- admission-controller init ----------------------------------------------------------------
def check_init_then_identity(tmp_path, monkeypatch, capsys):
    grants = register_grants(monkeypatch, tmp_path)
    for challenge in CHALLENGES:
        root = tmp_path / ("root-" + challenge)
        code, created = init(capsys, root, grants[challenge], challenge)
        assert code == 0 and created["status"] == "CREATED", created
        assert created["challenge"] == challenge and created["level"] == 0
        digest = created["controller"]["identity"]
        assert designations._DIGEST.fullmatch(digest)
        assert str(tmp_path) not in json.dumps(created["controller"])
        code, read = identity(capsys, root, grants[challenge], challenge)
        assert code == 0 and read["controller"]["identity"] == digest
        # Created once: a second init changes nothing.
        code, again = init(capsys, root, grants[challenge], challenge)
        assert (code, again["reason_code"]) == (2, "controller_store_exists")
        code, read = identity(capsys, root, grants[challenge], challenge)
        assert read["controller"]["identity"] == digest


def test_init_creates_a_controller_whose_identity_conditions_reads_back(
    tmp_path, monkeypatch, capsys
):
    check_init_then_identity(tmp_path, monkeypatch, capsys)


def check_init_refuses_other_grants(tmp_path, monkeypatch, capsys):
    grants = register_grants(monkeypatch, tmp_path)
    paid = tmp_path / "paid.json"
    paid.write_text(json.dumps(tc.grant_document(provider="graphite")))
    edited = tmp_path / "edited.json"
    edited.write_text(
        json.dumps(
            zero_document(grant_id="test-admission-" + BATTERY_CHALLENGE)
        ).replace("2099-01-01T00:00:00Z", "2098-01-01T00:00:00Z")
    )
    cases = [
        (paid, BATTERY_CHALLENGE, "admission_grant_must_be_zero_spend"),
        (
            grants[COLD_PLATE_CHALLENGE],
            BATTERY_CHALLENGE,
            "admission_grant_differs_from_the_committed_grant",
        ),
        (edited, BATTERY_CHALLENGE, "admission_grant_differs_from_the_committed_grant"),
    ]
    for index, (grant, challenge, code) in enumerate(cases):
        root = tmp_path / f"refused-{index}"
        out = init(capsys, root, grant, challenge)
        assert out[0] == 2 and out[1]["reason_code"] == code, (index, out)
        assert not (root / "controller").exists()


def test_init_takes_only_the_challenges_committed_zero_spend_grant(
    tmp_path, monkeypatch, capsys
):
    check_init_refuses_other_grants(tmp_path, monkeypatch, capsys)


def test_init_refuses_an_unregistered_or_missing_grant_and_a_repository_root(
    tmp_path, monkeypatch, capsys
):
    grants = register_grants(monkeypatch, tmp_path)
    grant = grants[MOTOR_CHALLENGE]
    monkeypatch.setattr(
        grant_binding,
        "ADMISSION_CONTROLLER_GRANTS",
        {MOTOR_CHALLENGE: str(tmp_path / "absent.json")},
    )
    code, out = init(capsys, tmp_path / "r1", grant, MOTOR_CHALLENGE)
    assert out["reason_code"] == "admission_grant_file_unreadable"
    code, out = init(capsys, tmp_path / "r2", grant, BATTERY_CHALLENGE)
    assert out["reason_code"] == "admission_grant_not_registered_for_challenge"
    code, out = init(capsys, phase3.REPOSITORY / "tmp-root", grant, MOTOR_CHALLENGE)
    assert out["reason_code"] == "root_must_be_outside_the_repository"
    code, out = init(capsys, tmp_path / "r3", grant, "no-such-challenge")
    assert code == 2 and out["status"] == "REFUSED"


def test_the_admission_controller_never_dispatches(tmp_path, monkeypatch, capsys):
    grants = register_grants(monkeypatch, tmp_path)
    root = tmp_path / "root"
    assert init(capsys, root, grants[MOTOR_CHALLENGE], MOTOR_CHALLENGE)[0] == 0
    grant = phase3.load_grant(grants[MOTOR_CHALLENGE])
    control = phase3.admission_controller(root, grant, MOTOR_CHALLENGE)
    try:
        assert not control.capabilities.dispatchable
        with pytest.raises(ctl.ControllerError) as refused:
            control.launch(tc.spec(), "run-1")
        assert refused.value.code == ctl.GRANT_ZERO_SPEND
    finally:
        control.close()
    with pytest.raises(ProviderUnavailable):
        phase3.NoDispatch().start(tc.spec(), "run-1")


def test_the_admission_controller_consumes_conditions_as_the_designated_authority(
    tmp_path, monkeypatch, capsys
):
    grants = register_grants(monkeypatch, tmp_path)
    root = tmp_path / "root"
    code, created = init(capsys, root, grants[BATTERY_CHALLENGE], BATTERY_CHALLENGE)
    digest = created["controller"]["identity"]
    designate(monkeypatch, tmp_path, entry(BATTERY_CHALLENGE, digest))
    code, out = run(
        capsys,
        "conditions",
        "--root",
        str(root),
        "--grant",
        str(grants[BATTERY_CHALLENGE]),
        "--challenge",
        BATTERY_CHALLENGE,
        "--report",
        str(tc.EV2_CONDITIONS),
    )
    assert code == 0 and out["status"] == "CONSUMED", out
    assert out["designation"]["lock_authority"] is True
    assert out["finding_ids"]


# -- the committed designation and A4, per Challenge -----------------------------------------
@pytest.mark.parametrize("challenge", CHALLENGES)
def test_each_challenge_has_exactly_one_pending_dedicated_entry(challenge):
    mine = [
        e for e in designations.load()["controllers"] if e["challenge"] == challenge
    ]
    assert len(mine) == 1
    (only,) = mine
    assert only["level"] == 0 and only["name"].startswith("admission-controller-")
    assert only["status"] == designations.PENDING and only["identity"] is None


@pytest.mark.parametrize("challenge", CHALLENGES)
def test_a_pending_entry_keeps_a4_not_passed(challenge):
    result = a4(challenge, model.REPOSITORY)
    assert result.status == model.FAIL
    assert "pending" in result.detail


def check_a4_pending(tmp_path, _monkeypatch, _capsys):
    for challenge in CHALLENGES:
        result = a4_with(tmp_path, challenge, entry(challenge))
        assert result.status == model.FAIL, challenge


@pytest.mark.parametrize("challenge", CHALLENGES)
def test_a_designated_sha256_passes_a4(tmp_path, challenge):
    result = a4_with(tmp_path, challenge, entry(challenge, DIGEST))
    assert result.status == model.PASS
    assert any(DIGEST in item for item in result.evidence)


def check_a4_refuses_bad_designations(tmp_path, _monkeypatch, _capsys):
    for challenge in CHALLENGES:
        bad = [
            (entry(challenge, "sha256:" + "E" * 64),),
            (entry(challenge, "sha256:" + "e" * 63),),
            (entry(challenge, status=designations.DESIGNATED),),
            (entry(challenge, DIGEST, status=designations.PENDING),),
            (entry(challenge, name="../admission-root"),),
            (entry(challenge, DIGEST), entry(challenge, DIGEST, name="again")),
            (entry("another-challenge", DIGEST),),
        ]
        for entries in bad:
            result = a4_with(tmp_path, challenge, *entries)
            assert result.status == model.FAIL, (challenge, entries)
        assert a4_with(tmp_path, challenge, raw="{").status == model.FAIL


@pytest.mark.parametrize("challenge", CHALLENGES)
def test_a_malformed_or_duplicate_designation_fails_a4(tmp_path, challenge):
    check_a4_refuses_bad_designations(tmp_path, None, None)
    # Another level's entry is not this level's.
    assert a4_with(tmp_path, challenge, entry(challenge, DIGEST, level=1)).status == (
        model.FAIL
    )


@pytest.mark.parametrize("challenge", CHALLENGES)
def test_each_challenge_registers_one_admission_grant_file(challenge):
    relative = grant_binding.ADMISSION_CONTROLLER_GRANTS[challenge]
    assert relative.startswith(grant_binding.GRANTS_DIR + "/")
    assert Path(relative).name.startswith("GRAPHITE-GRANT-ADMISSION-CONTROLLER-")
    assert len(set(grant_binding.ADMISSION_CONTROLLER_GRANTS.values())) == len(
        CHALLENGES
    )
    path = grant_binding.REPOSITORY / relative
    if not path.is_file():
        pytest.skip("the owner-approved grant file is not committed yet")
    grant = SpendingGrant.from_document(json.loads(path.read_bytes()))
    assert grant.zero_spend and grant.grant_id == path.stem
    assert grant_binding.admission_grant_refusal(grant, challenge) is None


# -- switching each guard off fails its test -------------------------------------------------
MUTATIONS = {
    "zero_spend_refused": (
        lambda m: m.setattr(SpendingGrant, "zero_spend", property(lambda s: False)),
        check_run_refused_before_reservation,
    ),
    "init_refuses_an_existing_store": (
        lambda m: m.setattr(phase3, "admission_store_exists", lambda root: False),
        check_init_then_identity,
    ),
    "init_checks_the_grant": (
        lambda m: m.setattr(
            grant_binding, "admission_grant_refusal", lambda *a, **k: None
        ),
        check_init_refuses_other_grants,
    ),
    "a4_pending_is_not_passed": (
        lambda m: m.setattr(designations, "pending", lambda e: False),
        check_a4_pending,
    ),
    "a4_designation_checked": (
        lambda m: m.setattr(designations, "_entry", lambda e: None),
        check_a4_refuses_bad_designations,
    ),
}


@pytest.mark.parametrize("name", sorted(MUTATIONS))
def test_switching_a_guard_off_fails_its_test(name, tmp_path, monkeypatch, capsys):
    disable, guard = MUTATIONS[name]
    intact, mutated = tmp_path / "intact", tmp_path / "mutated"
    intact.mkdir()
    mutated.mkdir()
    guard(intact, monkeypatch, capsys)  # holds with the guard in place
    disable(monkeypatch)
    with pytest.raises((Exception, pytest.fail.Exception)):
        guard(mutated, monkeypatch, capsys)
