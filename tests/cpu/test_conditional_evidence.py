"""GRAPHITE-CONDITIONAL-EXPLORATION-01: for internal testing, a finding stops
locking, not exploration (OWNER-GRAPHITE-TEST-WAVE-03 §2).

Claims tested, on the fake provider and synthetic fixtures (no spend):

- LOCK is still refused with an open finding, on the campaign controller and
  on the admission path, and a development entry never enters Track A's
  ledger, a LOCK or the profile in force;
- a development expansion proceeds with an open finding and is tagged with
  that finding's id and the canonical digest of its body, under the
  registered policy `conditional-evidence.v1`;
- every result recorded while a finding is open carries the tag: the
  controller's event, artifact and terminal entries and climb reports (attack
  family reports and phase 3 and phase 4 records, which need numpy:
  `test_conditional_evidence_graphite.py`);
- a tagged result is refused as unconditional evidence at each citation site:
  ladder TESTED and FROZEN evidence, an ACCEPTED level proposal, admission
  report evidence and its LOCK, and a pipeline record's frozen run;
- a repaired finding leaves later development expansions untagged; one that
  recurs is open again, and LOCK stays refused throughout.

Synthetic fixtures only; nothing here is scientific or security acceptance.
"""

from __future__ import annotations

import copy
import hashlib
import json

import pytest
import test_agent_campaign_climb as tclimb
import test_agent_campaign_controller as tc
import test_challenge_admission as tca
import test_challenge_pipeline as tcp
from test_development_variants import FIXTURE_DIGESTS, install

from carbon.agent_campaign import climb
from carbon.agent_campaign import controller as ctl
from carbon.agent_campaign.fake import FakeProvider
from carbon.challenge_pipeline import ladder, proposals
from carbon.challenge_pipeline.state import (
    PROTOCOL,
    RECORDS,
    PipelineError,
    validate_record,
)
from carbon.challenge_readiness import admission
from carbon.challenge_readiness import conditional_evidence as ce

BATTERY = "battery-fastcharge-ageing-development-v1"
WIDE = "sha256:" + "e" * 64
WIDER = "sha256:" + "f" * 64
WIDEST = "sha256:" + "d" * 64
OPERATOR = "carbon-operator"
NOTE = "repaired the boundary and re-ran the affected attacks"
#: A development expansion names a registered development variant's digest
#: (GRAPHITE-DEV-VARIANTS-01): the synthetic fixture variants stand in for the
#: three development widenings these tests record.
DEVELOPMENT = {
    WIDE: FIXTURE_DIGESTS[1],
    WIDER: FIXTURE_DIGESTS[2],
    WIDEST: FIXTURE_DIGESTS[3],
}


@pytest.fixture(autouse=True)
def fixture_variants(tmp_path_factory, monkeypatch):
    """A temporary registry of synthetic development variants."""
    install(tmp_path_factory.mktemp("variants"), monkeypatch)


def expand(controller, permissions=WIDE, *, development=False):
    record = (
        controller.record_development_expansion
        if development
        else controller.record_expansion
    )
    return record(
        challenge=BATTERY,
        profile="level-1",
        widened="bounded loss expressions",
        permissions=(
            DEVELOPMENT.get(permissions, permissions) if development else permissions
        ),
        operator=OPERATOR,
    )


def ref(controller, finding_id):
    """The tag a finding should carry, computed here independently: its id and
    the sha256 of its body's canonical JSON."""
    (body,) = [
        f for f in controller.admission_ledgers()["findings"] if f["id"] == finding_id
    ]
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    return {
        "id": finding_id,
        "digest": "sha256:" + hashlib.sha256(canonical).hexdigest(),
    }


def tagged(*refs):
    """A result produced while `refs` were open."""
    return {"result": "synthetic", **ce.tag(refs)}


FINDING = {"id": "f-synthetic", "digest": "sha256:" + "9" * 64}


# --- LOCK is still refused with an open finding ----------------------------------


def test_lock_is_still_refused_with_an_open_finding_on_the_controller(tmp_path):
    controller = tc.make(tmp_path)
    first = expand(controller)
    controller.record_finding("f1", "FAILING_TRIGGER", b"evidence")
    with pytest.raises(ctl.ControllerError, match="admission_expansion_after_finding"):
        expand(controller, WIDER)
    expand(controller, WIDER, development=True)  # exploration continues
    with pytest.raises(ctl.ControllerError, match="admission_expansion_after_finding"):
        expand(controller, WIDEST)
    controller.record_repair("f1", operator=OPERATOR, note=NOTE, evidence=b"rerun")
    with pytest.raises(ctl.ControllerError, match="admission_expansion_after_finding"):
        expand(controller, WIDEST)  # a repair never reopens the LOCK path
    ledgers = controller.admission_ledgers()
    assert ledgers["expansions"] == [first]
    assert controller.current_profile() == WIDE
    controller.close()


def test_lock_is_still_refused_with_an_open_finding_on_the_admission_path(tmp_path):
    block = tca.accepted(tmp_path, "fixture")
    study = block["tracks"][admission.LEDGER_TRACK]
    evidence = tca.artifact(tmp_path, "finding.json", {"condition": "fixture"})
    study["findings"] = [
        {
            "id": "F1",
            "condition": "FAILING_TRIGGER",
            "after_expansion": 1,
            "evidence": evidence,
        }
    ]
    tca.relock(tmp_path, block)
    admission.validate(block, "fixture", repository=tmp_path)
    study["expansions"].append(
        tca.expansion(2, tca.PERMISSIONS, "2026-10-02T00:00:00Z")
    )
    tca.relock(tmp_path, block)
    with pytest.raises(admission.AdmissionError, match="expansion_after_finding"):
        admission.validate(block, "fixture", repository=tmp_path)


def test_a_development_entry_never_enters_a_lock(tmp_path):
    controller = tc.make(tmp_path)
    controller.record_finding("f1", "GATE_ANOMALY", b"evidence")
    entry = expand(controller, development=True)
    # Never in the controller's Track A ledger or the profile in force.
    assert controller.admission_ledgers()["expansions"] == []
    assert controller.current_profile() is None
    controller.close()
    block = tca.accepted(tmp_path, "fixture")
    study = block["tracks"][admission.LEDGER_TRACK]
    # Injected into the LOCK ledger, it is refused even with the lock renewed:
    # tagged, with an empty tag, or marked development without one.
    bare = {k: v for k, v in entry.items() if k not in ce.TAG_KEYS}
    for injected in (
        dict(entry, sequence=2),
        dict(entry, sequence=2, conditional_on=[]),
        dict(bare, sequence=2),
    ):
        study["expansions"] = [study["expansions"][0], injected]
        tca.relock(tmp_path, block)
        with pytest.raises(admission.AdmissionError, match="development_expansion"):
            admission.validate(block, "fixture", repository=tmp_path)
    # A LOCK of the development state is refused: it is not a recorded state.
    study["expansions"] = [study["expansions"][0]]
    tca.relock(tmp_path, block)
    reference = study["acceptance"]["decision"]
    decision = json.loads((tmp_path / reference["path"]).read_bytes())
    decision["locked_permissions"] = entry["permissions"]
    study["acceptance"]["decision"] = tca.artifact(
        tmp_path, reference["path"], decision
    )
    with pytest.raises(admission.AdmissionError, match="lock_unrecorded_state"):
        admission.validate(block, "fixture", repository=tmp_path)


# --- a development expansion proceeds, tagged ---------------------------------------


def test_a_development_expansion_proceeds_and_is_tagged(tmp_path):
    controller = tc.make(tmp_path)
    clean = expand(controller, development=True)
    assert clean["conditional_on"] == []
    controller.record_finding("f1", "FAILING_TRIGGER", b"evidence")
    entry = expand(controller, WIDER, development=True)
    assert entry["kind"] == "development"
    assert entry["conditional_on"] == [ref(controller, "f1")]
    assert entry["conditional_policy"] == ce.identity()
    assert entry["conditional_policy"]["policy"] == "conditional-evidence.v1"
    ledger = controller.development_ledger()
    assert ledger["expansions"] == [clean, entry]
    assert ledger["open_findings"] == [ref(controller, "f1")]
    recorded = [e for e in controller.ledger() if e["kind"] == "development_expansion"]
    assert [e["disposition"] for e in recorded] == ["RECORDED", "RECORDED_CONDITIONAL"]
    # Track A sees none of it; the development profile is the newest widening.
    assert controller.admission_ledgers()["expansions"] == []
    assert controller.current_profile() is None
    assert controller.development_profile() == DEVELOPMENT[WIDER]
    with pytest.raises(ctl.ControllerError, match="operator_required"):
        controller.record_development_expansion(
            challenge=BATTERY,
            profile="level-2",
            widened="schedules",
            permissions=WIDEST,
            operator="agent",
        )
    controller.close()


def test_a_development_run_launches_under_its_profile_and_its_results_are_tagged(
    tmp_path,
):
    provider = FakeProvider()
    controller = tc.make(tmp_path, provider)
    tc.register(controller)
    controller.record_finding("f1", "FAILING_TRIGGER", b"evidence")
    expand(controller, WIDE, development=True)
    with pytest.raises(ctl.ControllerError, match="profile_not_in_force"):
        controller.launch(tc.spec(profile_digest=WIDER), "k0")
    with pytest.raises(ctl.ControllerError, match="profile_not_in_force"):
        controller.launch(tc.spec(profile_digest=DEVELOPMENT[WIDER]), "k0")
    development = DEVELOPMENT[WIDE]
    assert controller.launch(tc.spec(profile_digest=development), "k1") == "dispatched"
    provider.export("fake-run-0001", "out.json", b"{}")
    controller.poll("k1")
    (artifact,) = [e for e in controller.ledger() if e["kind"] == "artifact"]
    assert artifact["profile_digest"] == development
    assert artifact["conditional_on"] == [ref(controller, "f1")]
    controller.close()


# --- every result produced while a finding is open carries the tag ---------------------


def test_every_controller_result_recorded_while_a_finding_is_open_is_tagged(tmp_path):
    provider = FakeProvider()
    controller = tc.make(tmp_path, provider)
    tc.register(controller)
    controller.launch(tc.spec(), "k1")
    provider.export("fake-run-0001", "before.json", b"{}")
    controller.poll("k1")
    controller.record_finding("f1", "SCORE_VALUE_DIVERGENCE", b"evidence")
    provider.emit("fake-run-0001", {"type": "message", "text": "after"})
    provider.export("fake-run-0001", "after.json", b"[]")
    controller.poll("k1")
    provider.finish("fake-run-0001")
    controller.poll("k1")
    entries = controller.ledger()
    results = [e for e in entries if e["kind"] in ("event", "artifact", "terminal")]
    assert [e.get("conditional_on") for e in results] == [
        [],
        [ref(controller, "f1")],
        [ref(controller, "f1")],
        [ref(controller, "f1")],
    ]
    assert all(e.get("conditional_policy") == ce.identity() for e in results)
    others = [e for e in entries if e not in results]
    assert others and not any("conditional_on" in e for e in others)
    assert controller.verify_ledger()["consistent"] is True
    controller.close()


def test_a_climb_report_carries_the_tag():
    """The attack family report's tag is tested with the Graphite records
    (`test_conditional_evidence_graphite.py`), which need numpy."""
    plan = tclimb.plan()
    untagged = climb.climb(plan, tclimb.Fake().runners())
    assert untagged["conditional_on"] == []
    assert untagged["conditional_policy"] == ce.identity()
    conditional = climb.climb(plan, tclimb.Fake().runners(), open_findings=[FINDING])
    assert conditional["conditional_on"] == [FINDING]
    assert conditional["conditional_policy"] == ce.identity()
    with pytest.raises(ce.ConditionalEvidenceError, match=ce.CITED):
        ce.require_unconditional(conditional, site="test")


# --- the registered policy ------------------------------------------------------------


def test_the_tagging_rule_is_a_registered_versioned_policy():
    rules = ce.POLICIES["conditional-evidence.v1"]
    identity = ce.identity()
    assert identity == {
        "policy": "conditional-evidence.v1",
        "status": rules["status"],
        "authority": rules["authority"],
        "digest": "sha256:"
        + hashlib.sha256(
            json.dumps(rules, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
    }
    assert "OWNER-GRAPHITE-TEST-WAVE-03" in identity["authority"]
    with pytest.raises(ce.ConditionalEvidenceError, match="policy_unknown"):
        ce.tag([FINDING], policy="conditional-evidence.v0")
    altered = dict(identity, digest="sha256:" + "0" * 64)
    for value in (
        {"conditional_on": [], "conditional_policy": altered},
        {"conditional_on": [{"id": "f"}], "conditional_policy": identity},
        {"conditional_on": [FINDING, FINDING], "conditional_policy": identity},
        {"conditional_on": "f1", "conditional_policy": identity},
    ):
        with pytest.raises(ce.ConditionalEvidenceError):
            ce.require_unconditional(value, site="test")
    ce.require_unconditional(
        {"conditional_on": [], "conditional_policy": identity}, site="test"
    )


# --- a tagged result is never cited as unconditional ---------------------------------


def _write(path, value):
    path.write_text(json.dumps(value))
    return path


@pytest.mark.parametrize("state", ["TESTED", "FROZEN"])
@pytest.mark.parametrize("form", ["json", "jsonl", "markdown", "directory"])
def test_the_ladder_refuses_conditional_level_evidence(tmp_path, state, form):
    token = tcp._challenge(tmp_path, records=1)
    evidence = "tagged.json"
    body = tagged(FINDING)
    if form == "json":
        _write(tmp_path / evidence, {"climb": body})
    elif form == "jsonl":
        evidence = "log.jsonl"
        (tmp_path / evidence).write_text(
            json.dumps({"ok": 1}) + "\n" + json.dumps(body) + "\n"
        )
    elif form == "markdown":
        evidence = "status.md"
        (tmp_path / evidence).write_text(
            "# Status\n\n```\n" + json.dumps(body) + "\n```\n"
        )
    else:
        evidence = "bundle"
        (tmp_path / evidence).mkdir()
        _write(tmp_path / evidence / "a.json", {"clean": True})
        _write(tmp_path / evidence / "b.json", body)
    construction = {
        "challenge": token,
        "level": 0,
        "chosen": 0 if state == "FROZEN" else None,
        "levels": [tcp._level(token, 0, state, 0, evidence)],
    }
    with pytest.raises(ladder.LadderError, match=ce.CITED):
        ladder.validate(construction, "synthetic", tmp_path)
    clean = dict(construction["levels"][0], evidence="evidence.md")
    ladder.validate(dict(construction, levels=[clean]), "synthetic", tmp_path)


def test_an_accepted_proposal_cannot_be_conditional():
    protocol = json.loads(PROTOCOL.read_text())
    tag = ce.tag([FINDING])
    proposals.validate(tcp._proposal(status="PROPOSED", **tag), "p", protocol)
    proposals.validate(tcp._proposal(**ce.tag([])), "p", protocol)
    with pytest.raises(proposals.ProposalError, match=ce.CITED):
        proposals.validate(tcp._proposal(**tag), "p", protocol)
    for broken in (
        {"conditional_on": [FINDING]},
        {"conditional_on": "f1", "conditional_policy": ce.identity()},
    ):
        with pytest.raises(proposals.ProposalError):
            proposals.validate(
                tcp._proposal(status="PROPOSED", **broken), "p", protocol
            )


@pytest.mark.parametrize("track", sorted(admission.CHECKS))
def test_admission_evidence_and_the_lock_refuse_a_conditional_result(tmp_path, track):
    block = tca.accepted(tmp_path, "fixture")
    cited = tca.artifact(tmp_path, "cited.json", tagged(FINDING))

    def cite(document):
        for check in document["checks"].values():
            check["evidence"] = [cited]

    tca.alter_report(tmp_path, block, cite, track)
    with pytest.raises(admission.AdmissionError, match=ce.CITED):
        admission.validate(block, "fixture", repository=tmp_path)
    # Not only at acceptance: a FAILED report cites its evidence as observed.
    failed = tca.accepted(tmp_path, "fixture")
    study = failed["tracks"][track]

    def fail(document):
        cite(document)
        for check in document["checks"].values():
            check["result"] = "FAIL"

    tca.alter_report(tmp_path, failed, fail, track)
    study.update(state="FAILED", acceptance=None)
    with pytest.raises(admission.AdmissionError, match=ce.CITED):
        admission.validate(failed, "fixture", repository=tmp_path)


def test_the_lock_refuses_conditional_evidence_it_binds(tmp_path):
    """The LOCK checks the evidence it binds itself, not only through the
    report check before it."""
    block = tca.accepted(tmp_path, "fixture")
    cited = tca.artifact(tmp_path, "cited.json", tagged(FINDING))

    def cite(document):
        for check in document["checks"].values():
            check["evidence"] = [cited]

    tca.alter_report(tmp_path, block, cite, admission.LEDGER_TRACK)
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(admission, "_cited", lambda body, site: None)
        admission.validate(block, "fixture", repository=tmp_path)  # specimen
    with pytest.raises(admission.AdmissionError, match=ce.CITED):
        admission._lock(
            block["tracks"][admission.LEDGER_TRACK], block["scope"], tmp_path
        )


def test_a_frozen_run_cannot_cite_conditional_evidence(tmp_path):
    protocol = json.loads(PROTOCOL.read_text())
    battery = json.loads((RECORDS / "f05.json").read_text())
    _write(tmp_path / "frozen.json", tagged(FINDING))
    evidence = dict.fromkeys(battery["evidence"])
    record = dict(battery, evidence=dict(evidence, frozen="frozen.json"))
    with pytest.raises(PipelineError, match=ce.CITED):
        validate_record(record, protocol, {"f05"}, root=tmp_path)
    # The same record citing untagged evidence passes this check and fails
    # later, on its construction refs, which are not in this temporary root.
    _write(tmp_path / "frozen.json", {"result": "synthetic"})
    with pytest.raises(PipelineError) as later:
        validate_record(record, protocol, {"f05"}, root=tmp_path)
    assert ce.CITED not in str(later.value)


# --- repair: later development expansions are untagged ---------------------------------


def test_a_repaired_finding_leaves_later_development_expansions_untagged(tmp_path):
    controller = tc.make(tmp_path)
    controller.record_finding("f1", "FAILING_TRIGGER", b"one")
    consumed = controller.consume_conditions(tc.EV2_CONDITIONS)
    first = expand(controller, WIDE, development=True)
    assert [r["id"] for r in first["conditional_on"]] == sorted(["f1", *consumed])
    with pytest.raises(ctl.ControllerError, match="operator_required"):
        controller.record_repair("f1", operator="agent", note=NOTE, evidence=b"rerun")
    with pytest.raises(ctl.ControllerError, match="say what was repaired"):
        controller.record_repair("f1", operator=OPERATOR, note="fixed", evidence=b"x")
    with pytest.raises(ctl.ControllerError, match="repair_evidence_required"):
        controller.record_repair("f1", operator=OPERATOR, note=NOTE, evidence=b"")
    with pytest.raises(ctl.ControllerError, match="no_such_finding"):
        controller.record_repair("nope", operator=OPERATOR, note=NOTE, evidence=b"x")
    controller.record_repair("f1", operator=OPERATOR, note=NOTE, evidence=b"rerun")
    with pytest.raises(ctl.ControllerError, match="finding_already_repaired"):
        controller.record_repair("f1", operator=OPERATOR, note=NOTE, evidence=b"x")
    second = expand(controller, WIDER, development=True)
    assert [r["id"] for r in second["conditional_on"]] == sorted(consumed)
    for finding_id in consumed:
        controller.record_repair(
            finding_id, operator=OPERATOR, note=NOTE, evidence=b"rerun"
        )
    third = expand(controller, WIDEST, development=True)
    assert third["conditional_on"] == []
    # Tags stay on the results they were recorded with; findings stay too.
    assert controller.development_ledger()["expansions"][:2] == [first, second]
    assert len(controller.admission_ledgers()["findings"]) == 1 + len(consumed)
    controller.close()


def test_a_repaired_finding_that_recurs_is_open_again(tmp_path):
    controller = tc.make(tmp_path)
    controller.record_finding("f1", "FAILING_TRIGGER", b"one")
    controller.record_repair("f1", operator=OPERATOR, note=NOTE, evidence=b"rerun")
    assert controller.open_findings() == []
    controller.record_finding("f1", "FAILING_TRIGGER", b"one")  # it recurred
    assert controller.open_findings() == [ref(controller, "f1")]
    entry = expand(controller, development=True)
    assert entry["conditional_on"] == [ref(controller, "f1")]
    kinds = [e["kind"] for e in controller.ledger()]
    assert kinds.count("finding") == 1
    assert "finding_repaired" in kinds and "finding_recurred" in kinds
    controller.close()


def test_the_development_ledger_is_validated(tmp_path):
    controller = tc.make(tmp_path)
    entry = expand(controller, development=True)
    for broken, code in (
        (dict(entry, kind="lock"), "kind_required"),
        (dict(entry, sequence=2), "sequence_gap"),
        ({k: v for k, v in entry.items() if k != "conditional_on"}, "exact_keys"),
        (dict(entry, permissions="level-1"), "unpinned"),
        (dict(entry, conditional_policy=None), "policy_unknown"),
    ):
        with pytest.raises(ce.ConditionalEvidenceError, match=code):
            ce.validate_development_ledger([copy.deepcopy(broken)])
    controller.close()
