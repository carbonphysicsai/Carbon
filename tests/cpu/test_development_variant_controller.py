"""Development is registered, never declared; a LOCK binds more than the study.

GRAPHITE-DEV-VARIANTS-01, the Test Lead's review items for W2
(GRAPHITE-CONDITIONAL-EXPLORATION-01, carbonphysicsai/Carbon#577):

- **Item 2.** "Development" was the caller's say-so: any permissions digest
  passed to `record_development_expansion`, or launched as the development
  profile, was accepted. Now only a registered, pinned variant of
  `development_variants.DEV_VARIANTS` with a development record is accepted;
  anything else is `development_variant_unregistered`.
- **Item 6.** A development entry with `kind` and the tag keys stripped
  validated as a six-key Track A entry, and a LOCK bound only the study's
  ledgers. Now `admission._expansions` refuses an entry whose permissions
  digest names a development variant, and the controller's `check_lock`
  cross-checks the study against its own ledgers: an expansion it recorded as
  development, or a finding the study omits, is refused.
- **The climb nit** (OWNER-GRAPHITE-TEST-WAVE-03 §2). A development climb
  continues past a finding and tags what follows it; the LOCK path's climb
  still stops.

Each guard is switched off once (`MUTATIONS`) and its test shown to fail.
Fake provider and synthetic fixture variants only: no spend, nothing here is
scientific or security acceptance.
"""

from __future__ import annotations

import hashlib
import types

import pytest
import test_agent_campaign_climb as tclimb
import test_agent_campaign_controller as tc
import test_challenge_admission as tca
from test_development_variants import (
    BATTERY,
    FIXTURE_DIGESTS,
    fixture_document,
    install,
)

from carbon.agent_campaign import climb
from carbon.agent_campaign import controller as ctl
from carbon.agent_campaign.controller import CampaignController
from carbon.agent_campaign.fake import FakeProvider
from carbon.challenge_readiness import admission
from carbon.challenge_readiness import conditional_evidence as ce
from carbon.reconstruction import capability_registry as cr

OPERATOR = "carbon-operator"
DEV1, DEV2, DEV3 = (FIXTURE_DIGESTS[level] for level in (1, 2, 3))
ARBITRARY = "sha256:" + "e" * 64
UNREGISTERED = "development_variant_unregistered"
SIX_KEYS = {"sequence", "recorded_at", "profile", "version", "widened", "permissions"}


def develop(controller, permissions, challenge=BATTERY):
    return controller.record_development_expansion(
        challenge=challenge,
        profile="level-1",
        widened="fixture widening",
        permissions=permissions,
        operator=OPERATOR,
    )


def _code(call):
    with pytest.raises(ctl.ControllerError) as refused:
        call()
    return refused.value.code


# --- item 2: development is registered, never declared ------------------------------


def check_record_needs_a_registered_variant(tmp_path, monkeypatch):
    install(tmp_path / "registry", monkeypatch)
    controller = tc.make(tmp_path)
    try:
        for permissions in (ARBITRARY, cr.contract(BATTERY).digest):
            assert _code(lambda p=permissions: develop(controller, p)) == UNREGISTERED
        # A registered variant, named under another Challenge.
        assert (
            _code(lambda: develop(controller, DEV1, cr.BURGERS_CHALLENGE))
            == UNREGISTERED
        )
        assert controller.development_ledger()["expansions"] == []
        entry = develop(controller, DEV1)
        # The entry binds the base record and the variant's development record.
        assert entry["permissions"] == DEV1
        assert f"dev/0000 {DEV1} level 1" in entry["version"]
        assert controller.development_ledger()["expansions"] == [entry]
        assert controller.development_profile() == DEV1
    finally:
        controller.close()


def test_a_development_expansion_needs_a_registered_variant(tmp_path, monkeypatch):
    check_record_needs_a_registered_variant(tmp_path, monkeypatch)


def test_a_registered_but_unrecorded_variant_is_refused(tmp_path, monkeypatch):
    install(tmp_path / "registry", monkeypatch, record=False)
    controller = tc.make(tmp_path)
    assert _code(lambda: develop(controller, DEV1)) == "development_variant_unrecorded"
    controller.close()


def check_launch_needs_a_registered_variant(tmp_path, monkeypatch):
    install(tmp_path / "registry", monkeypatch)
    controller = tc.make(tmp_path, FakeProvider())
    try:
        tc.register(controller)
        controller.register_campaign(
            "c2",
            role=tc.Role.CONSTRUCTION,
            workspace_id="ws-c2",
            credential_ref="cred-c2",
            checkout_digest=tc.CHECKOUT,
            profile_digest=DEV2,
            ceiling="1.00",
        )
        # An arbitrary digest is never a development profile.
        assert (
            _code(lambda: controller.launch(tc.spec(profile_digest=ARBITRARY), "k0"))
            == "profile_not_in_force"
        )
        develop(controller, DEV1)
        assert controller.launch(tc.spec(profile_digest=DEV1), "k1") == "dispatched"
        # A campaign registered under a variant runs it only as the newest
        # development expansion.
        assert (
            _code(lambda: controller.launch(tc.spec("c2", profile_digest=DEV2), "k2"))
            == "profile_not_in_force"
        )
        # Once the registry no longer runs the variant, nothing launches
        # under it, though it stays recorded and refused to miners.
        install(tmp_path / "later", monkeypatch, current=[], record=False)
        assert cr.is_development_variant(DEV1)
        assert (
            _code(lambda: controller.launch(tc.spec(profile_digest=DEV1), "k3"))
            == UNREGISTERED
        )
    finally:
        controller.close()


def test_a_launch_under_a_development_profile_needs_it_registered(
    tmp_path, monkeypatch
):
    check_launch_needs_a_registered_variant(tmp_path, monkeypatch)


# --- item 6: a LOCK binds more than the study's own ledgers -------------------------


def _stripped(entry, sequence=2):
    """A development entry with `kind` and the tag keys removed."""
    drop = {"kind", *ce.TAG_KEYS}
    return dict({k: v for k, v in entry.items() if k not in drop}, sequence=sequence)


def _study_with(tmp_path, entry):
    block = tca.accepted(tmp_path, "fixture")
    study = block["tracks"][admission.LEDGER_TRACK]
    study["expansions"].append(entry)
    tca.relock(tmp_path, block)
    return block


def check_stripped_entry_never_enters_a_lock(tmp_path, monkeypatch):
    install(tmp_path / "registry", monkeypatch)
    controller = tc.make(tmp_path)
    try:
        controller.record_finding("f0", "OTHER_SIGNAL", b"before")
        stripped = _stripped(develop(controller, DEV1))
        assert set(stripped) == SIX_KEYS  # it looks like a Track A entry
        block = _study_with(tmp_path, stripped)
        with pytest.raises(admission.AdmissionError) as refused:
            admission.validate(block, "fixture", repository=tmp_path)
        assert refused.value.args[0] == "admission_development_expansion_refused"
    finally:
        controller.close()


def test_a_stripped_development_entry_never_enters_a_lock(tmp_path, monkeypatch):
    check_stripped_entry_never_enters_a_lock(tmp_path, monkeypatch)


def check_lock_cross_checks_development(tmp_path, monkeypatch):
    install(tmp_path / "registry", monkeypatch)
    controller = tc.make(tmp_path)
    try:
        stripped = _stripped(develop(controller, DEV1))
        # A registry that no longer names the variant at all: the static check
        # cannot see it, so only the controller's own ledger can.
        install(tmp_path / "other", monkeypatch, [fixture_document(2)], record=False)
        assert not cr.is_development_variant(DEV1)
        block = _study_with(tmp_path, stripped)
        admission.validate(block, "fixture", repository=tmp_path)
        with pytest.raises(admission.AdmissionError) as refused:
            controller.check_lock(block, "fixture", repository=tmp_path)
        assert refused.value.args[0] == "admission_development_expansion_refused"
    finally:
        controller.close()


def test_the_lock_cross_checks_the_controllers_development_ledger(
    tmp_path, monkeypatch
):
    check_lock_cross_checks_development(tmp_path, monkeypatch)


def check_lock_cross_checks_findings(tmp_path, monkeypatch):
    install(tmp_path / "registry", monkeypatch)
    controller = tc.make(tmp_path)
    try:
        block = tca.accepted(tmp_path, "fixture")
        assert controller.check_lock(block, "fixture", repository=tmp_path) is block
        controller.record_finding("f1", "FAILING_TRIGGER", b"evidence")
        with pytest.raises(admission.AdmissionError) as refused:
            controller.check_lock(block, "fixture", repository=tmp_path)
        assert refused.value.args[0] == "admission_lock_finding_omitted"
        (tmp_path / "f1.bin").write_bytes(b"evidence")
        ref = {
            "path": "f1.bin",
            "sha256": "sha256:" + hashlib.sha256(b"evidence").hexdigest(),
        }
        study = block["tracks"][admission.LEDGER_TRACK]
        recorded = {
            "id": "f1",
            "condition": "FAILING_TRIGGER",
            "after_expansion": 1,
            "evidence": ref,
        }
        study["findings"] = [dict(recorded, condition="GATE_ANOMALY")]
        tca.relock(tmp_path, block)
        with pytest.raises(admission.AdmissionError) as refused:
            controller.check_lock(block, "fixture", repository=tmp_path)
        assert refused.value.args[0] == "admission_lock_finding_omitted"
        study["findings"] = [recorded]
        tca.relock(tmp_path, block)
        assert controller.check_lock(block, "fixture", repository=tmp_path) is block
    finally:
        controller.close()


def test_the_lock_cross_checks_the_controllers_findings(tmp_path, monkeypatch):
    check_lock_cross_checks_findings(tmp_path, monkeypatch)


# --- the climb nit: a development climb continues and tags ---------------------------


VIOLATION = {("level-1", "attack-0")}
FINDING = {"id": "f-synthetic", "digest": "sha256:" + "9" * 64}


def check_development_climb_continues(tmp_path, monkeypatch):
    install(tmp_path / "registry", monkeypatch)
    lock = climb.climb(
        tclimb.plan(challenge=BATTERY), tclimb.Fake(violations=VIOLATION).runners()
    )
    assert lock["status"] == "STOPPED_ON_FINDING"
    assert [s["state"] for s in lock["steps"].values()] == [
        "RUN",
        "RUN",
        "NOT_RUN",
        "NOT_RUN",
        "NOT_RUN",
    ]
    assert "id" not in lock["findings"][0] and "development_variant" not in lock
    report = climb.climb(
        tclimb.plan(challenge=BATTERY, development_variant=DEV1),
        tclimb.Fake(violations=VIOLATION).runners(),
        open_findings=[FINDING],
    )
    assert [s["state"] for s in report["steps"].values()] == ["RUN"] * 5
    assert report["status"] == "COMPLETED_CONDITIONAL"
    assert report["development_variant"] == DEV1
    (finding,) = report["findings"]
    assert finding["id"] == "climb-finding-001"
    own = ce.reference(finding)
    runs = [r for s in report["steps"].values() for r in s["runs"]]
    first = next(
        i
        for i, r in enumerate(runs)
        if (r["profile"], r["item_id"]) == ("level-1", "attack-0")
    )
    # Before and including the run that found it: the run carries no in-climb tag.
    assert not any("conditional_on" in r for r in runs[: first + 1])
    # Everything after it is conditional on it, and on what was open already.
    later = runs[first + 1 :]
    assert later and all(r.get("conditional_on") == [own, FINDING] for r in later)
    assert report["conditional_on"] == [own, FINDING]
    with pytest.raises(ce.ConditionalEvidenceError, match=ce.CITED):
        ce.require_unconditional(report, site="test")
    # A clean development climb is unconditional under the policy.
    clean = climb.climb(
        tclimb.plan(challenge=BATTERY, development_variant=DEV1),
        tclimb.Fake().runners(),
    )
    assert clean["status"] == "COMPLETED" and clean["conditional_on"] == []


def test_a_development_climb_continues_past_a_finding_and_tags_what_follows(
    tmp_path, monkeypatch
):
    check_development_climb_continues(tmp_path, monkeypatch)


def test_a_climb_names_only_a_registered_variant_at_its_level(tmp_path, monkeypatch):
    install(tmp_path / "registry", monkeypatch)
    for variant, code in (
        (ARBITRARY, UNREGISTERED),
        (DEV2, "development_variant_is_another_level"),
    ):
        with pytest.raises(climb.ClimbError) as refused:
            tclimb.plan(challenge=BATTERY, development_variant=variant)
        assert refused.value.code == code
    with pytest.raises(climb.ClimbError) as refused:
        tclimb.plan(development_variant=DEV1)  # the plan's Challenge is another
    assert refused.value.code == UNREGISTERED


# --- switching each guard off fails its test -------------------------------------------


def _accept_any_variant(m):
    def accept(permissions, challenge=None):
        found = types.SimpleNamespace(digest=permissions, level=1)
        return found, {"development_record_sequence": 0}

    m.setattr(CampaignController, "_registered_variant", staticmethod(accept))


def _stop_on_finding(m):
    m.setattr(climb._Record, "stopped", lambda self: bool(self.findings))


MUTATIONS = {
    "item2_record_needs_a_registered_variant": (
        _accept_any_variant,
        check_record_needs_a_registered_variant,
    ),
    "item2_launch_needs_a_registered_variant": (
        _accept_any_variant,
        check_launch_needs_a_registered_variant,
    ),
    "item6_admission_refuses_variant_permissions": (
        lambda m: m.setattr(admission, "_development_permissions", lambda e: False),
        check_stripped_entry_never_enters_a_lock,
    ),
    "item6_lock_cross_checks_development": (
        lambda m: m.setattr(
            CampaignController,
            "_lock_development_check",
            staticmethod(lambda study, development: None),
        ),
        check_lock_cross_checks_development,
    ),
    "item6_lock_cross_checks_findings": (
        lambda m: m.setattr(
            CampaignController,
            "_lock_findings_check",
            staticmethod(lambda study, findings: None),
        ),
        check_lock_cross_checks_findings,
    ),
    "climb_continues_on_a_development_variant": (
        _stop_on_finding,
        check_development_climb_continues,
    ),
    "climb_tags_what_follows_a_finding": (
        lambda m: m.setattr(
            climb._Record, "tag_after_finding", lambda self, entry: entry
        ),
        check_development_climb_continues,
    ),
}


@pytest.mark.parametrize("name", sorted(MUTATIONS))
def test_switching_a_guard_off_fails_its_test(name, tmp_path, monkeypatch):
    disable, guard = MUTATIONS[name]
    intact, mutated = tmp_path / "intact", tmp_path / "mutated"
    intact.mkdir()
    mutated.mkdir()
    guard(intact, monkeypatch)  # holds with the guard in place
    disable(monkeypatch)
    with pytest.raises((AssertionError, pytest.fail.Exception)):
        guard(mutated, monkeypatch)
