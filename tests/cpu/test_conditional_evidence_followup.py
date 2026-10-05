"""The Test Lead's review of #577, items 1-5 (GRAPHITE-CONDITIONAL-EXPLORATION-01,
amendment of 2026-10-05; `conditional-evidence.v2`, `repair-attestation.v1`).

Claims tested, on the fake provider and synthetic fixtures (no spend):

1. the report that found a finding is conditional on it and still backs a
   FAIL (and INCONCLUSIVE / NOT_RUN); a tagged result still cannot back a
   PASS, an ACCEPTED report or an ACCEPTED level proposal;
2. the citation check also consults a controller's ledger: a stripped copy, a
   Markdown summary, a YAML-style key and a gzip copy the ledger recorded on
   a result while a finding was open are each refused, whatever their bytes
   say; tagged bytes inside gzip, bzip2, xz and zip copies and YAML keys are
   refused without a ledger;
3. results are not written untagged while a finding is open: a canary
   finding is recorded before the entry that exposed it, and stored evidence
   bytes are refused through the ledger row that is their tag (phase 3 and
   phase 4 sites, which need numpy: `test_conditional_evidence_graphite.py`);
4. a repair is `repair-attestation.v1`: it needs the re-run's identities,
   later results carry `repaired_by_attestation`, and that never unblocks a
   LOCK, a FROZEN level or a frozen run;
5. control entries of the attempt ledger keep schema v1; result entries are
   v2.

Each guard's mutation is shown to fail its test at the end of this module.
Synthetic fixtures only; nothing here is scientific or security acceptance.
"""

from __future__ import annotations

import bz2
import gzip
import io
import json
import lzma
import zipfile

import pytest
import test_agent_campaign_controller as tc
import test_challenge_admission as tca
import test_challenge_pipeline as tcp
import test_conditional_evidence as t
from test_development_variants import install

from carbon.agent_campaign import controller as ctl
from carbon.agent_campaign.controller import CampaignController
from carbon.agent_campaign.fake import FakeProvider
from carbon.challenge_pipeline import ladder, proposals
from carbon.challenge_pipeline.__main__ import main as pipeline_main
from carbon.challenge_pipeline.state import (
    PROTOCOL,
    RECORDS,
    PipelineError,
    validate_record,
)
from carbon.challenge_readiness import admission
from carbon.challenge_readiness import conditional_evidence as ce

OPERATOR = t.OPERATOR
NOTE = t.NOTE
RERUN = t.RERUN
#: The finding a coverage report found (synthetic id and digest).
FOUND = {"id": "f-found-here", "digest": "sha256:" + "8" * 64}


@pytest.fixture(autouse=True)
def fixture_variants(tmp_path_factory, monkeypatch):
    """The synthetic development variants the controller tests record."""
    install(tmp_path_factory.mktemp("variants"), monkeypatch)


def _found_report():
    """The report that found FOUND: conditional on its own finding."""
    return {"report": "coverage", "findings": [FOUND["id"]], **ce.tag([FOUND])}


def _cite_all(cited, result):
    def mutate(document):
        for check in document["checks"].values():
            check.update(result=result, evidence=[cited])
            if result == "NOT_RUN":
                check["observations"] = 0

    return mutate


# --- 1. a finding's own report backs a FAIL ---------------------------------------------


@pytest.mark.parametrize("track", sorted(admission.CHECKS))
def test_the_report_that_found_a_finding_backs_a_fail(tmp_path, track):
    cited = tca.artifact(tmp_path, "found.json", _found_report())
    for result, state in (
        ("FAIL", "FAILED"),
        ("INCONCLUSIVE", "INCONCLUSIVE"),
        ("NOT_RUN", "INCONCLUSIVE"),
    ):
        block = tca.accepted(tmp_path, "fixture")
        tca.alter_report(tmp_path, block, _cite_all(cited, result), track)
        block["tracks"][track].update(state=state, acceptance=None)
        admission.validate(block, "fixture", repository=tmp_path)  # it stands
    # The same report never backs a PASS, in a FAILED report or an ACCEPTED one.
    failed = tca.accepted(tmp_path, "fixture")

    def one_pass(document):
        _cite_all(cited, "FAIL")(document)
        document["checks"][min(document["checks"])]["result"] = "PASS"

    tca.alter_report(tmp_path, failed, one_pass, track)
    failed["tracks"][track].update(state="FAILED", acceptance=None)
    with pytest.raises(admission.AdmissionError, match=ce.CITED):
        admission.validate(failed, "fixture", repository=tmp_path)
    accepted = tca.accepted(tmp_path, "fixture")
    tca.alter_report(tmp_path, accepted, _cite_all(cited, "PASS"), track)
    with pytest.raises(admission.AdmissionError, match=ce.CITED):
        admission.validate(accepted, "fixture", repository=tmp_path)


def test_a_tagged_result_still_cannot_back_an_accepted_proposal():
    protocol = json.loads(PROTOCOL.read_text())
    with pytest.raises(proposals.ProposalError, match=ce.CITED):
        proposals.validate(tcp._proposal(**ce.tag([FOUND])), "p", protocol)
    assert ce.RELIANCE == {"PASS", "ACCEPTED", "TESTED", "FROZEN", "LOCK"}
    assert not any(ce.relies(claim) for claim in ("FAIL", "INCONCLUSIVE", "NOT_RUN"))


# --- 2. the citation check consults the controller's ledger -----------------------------

TAGGED = json.dumps({"coverage": "synthetic", **ce.tag([FOUND])}).encode()
STRIPPED = json.dumps({"coverage": "synthetic"}).encode()
#: Copies of a result produced while a finding was open whose bytes do not
#: say so (or say so in a form JSON parsing does not see).
COPIES = {
    "stripped.json": STRIPPED,
    "summary.md": b"# Session summary\n\nTwo families breached; see the coverage.\n",
    "coverage.yaml": (
        b"coverage: synthetic\nconditional_on:\n  - id: f1\n"
        b"    digest: sha256:" + b"8" * 64 + b"\n"
    ),
    "coverage.json.gz": gzip.compress(STRIPPED, mtime=0),
}


def _ledgered(tmp_path):
    """A controller whose run returned COPIES while finding f1 was open."""
    provider = FakeProvider()
    controller = tc.make(tmp_path, provider)
    tc.register(controller)
    controller.launch(tc.spec(), "k1")
    controller.record_finding("f1", "FAILING_TRIGGER", b"evidence")
    for name, body in COPIES.items():
        provider.export("fake-run-0001", name, body)
    controller.poll("k1")
    return controller


def _tested(repo, evidence):
    token = tcp._challenge(repo, records=1)
    return {
        "challenge": token,
        "level": 0,
        "chosen": None,
        "levels": [tcp._level(token, 0, "TESTED", 0, evidence)],
    }


@pytest.mark.parametrize("name", sorted(COPIES))
def test_a_copy_the_ledger_recorded_while_a_finding_was_open_is_refused(tmp_path, name):
    controller = _ledgered(tmp_path)
    ledger = controller.conditional_ledger()
    controller.close()
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / name).write_bytes(COPIES[name])
    construction = _tested(repo, name)
    with pytest.raises(ladder.LadderError, match=ce.CITED):
        ladder.validate(construction, "synthetic", repo, ledgers=(ledger,))
    # The same, reading the store itself (read-only), as the pipeline CLI does.
    stored = ce.ConditionalLedger.load(tmp_path / "store")
    with pytest.raises(ladder.LadderError, match=ce.CITED):
        ladder.validate(construction, "synthetic", repo, ledgers=(stored,))
    # An unrelated, unconditional result passes with the ledger.
    (repo / name).write_bytes(b"# an unrelated note\n")
    ladder.validate(construction, "synthetic", repo, ledgers=(ledger,))


def test_without_a_ledger_only_the_bytes_speak(tmp_path):
    """Why the ledger is needed: a stripped copy and a prose summary carry
    nothing in their bytes. Tagged bytes in any other form are refused."""
    for name in ("stripped.json", "summary.md"):
        ce.require_unconditional_bytes(COPIES[name], site="test")
    for body in (
        COPIES["coverage.yaml"],
        b"conditional_on: [{id: f1, digest: x}]\n",
        b"- conditional_on:\n  - id: f1\n",
        b'# Note\n\n```json\n{\n  "conditional_on": [\n    {"id": "f1"}\n  ]\n}\n```\n',
        gzip.compress(TAGGED, mtime=0),
        bz2.compress(TAGGED),
        lzma.compress(TAGGED),
        _zip({"coverage.json": TAGGED}),
        gzip.compress(_zip({"a/b.yaml": COPIES["coverage.yaml"]}), mtime=0),
        b"\x1f\x8b not really gzip",
    ):
        with pytest.raises(ce.ConditionalEvidenceError, match=ce.CITED):
            ce.require_unconditional_bytes(body, site="test")
    for body in (
        b"coverage: synthetic\nconditional_on: []\n",
        b"coverage: synthetic\nconditional_on:\nnext: 1\n",
        b'# Note\n\n```\n"conditional_on": [\n]\n```\n',
        gzip.compress(STRIPPED, mtime=0),
    ):
        ce.require_unconditional_bytes(body, site="test")


def _zip(members):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, body in members.items():
            archive.writestr(name, body)
    return buffer.getvalue()


def test_the_lock_check_consults_the_controllers_own_ledger(tmp_path):
    controller = _ledgered(tmp_path)
    block = tca.accepted(tmp_path, "fixture")
    cited = {"path": "stripped.json", "sha256": ce._sha256(STRIPPED)}
    (tmp_path / "stripped.json").write_bytes(STRIPPED)

    def cite(document):
        for check in document["checks"].values():
            check["evidence"] = [cited]

    tca.alter_report(tmp_path, block, cite, admission.LEDGER_TRACK)
    admission.validate(block, "fixture", repository=tmp_path)  # bytes alone pass
    with pytest.raises(admission.AdmissionError, match=ce.CITED):
        controller.check_lock(block, "fixture", repository=tmp_path)
    controller.close()


def test_the_pipeline_cli_reads_a_controller_ledger(tmp_path, capsys):
    controller = _ledgered(tmp_path)
    controller.close()
    assert (
        pipeline_main(["validate", "--conditional-ledger", str(tmp_path / "store")])
        == 0
    )
    assert "records valid" in capsys.readouterr().out
    with pytest.raises(ce.ConditionalEvidenceError, match="ledger_unavailable"):
        ce.ConditionalLedger.load(tmp_path / "nowhere")


# --- 3. results are not written untagged while a finding is open -----------------------

CANARY = "CARBON-CANARY-" + "e" * 32


def test_a_canary_finding_is_recorded_before_the_entry_that_exposed_it(tmp_path):
    provider = FakeProvider()
    controller = tc.make(tmp_path, provider)
    tc.register(controller, canaries=(CANARY,))
    controller.launch(tc.spec(), "k1")
    provider.emit("fake-run-0001", {"type": "message", "text": "saw " + CANARY})
    provider.export("fake-run-0001", "leak.txt", b"found " + CANARY.encode())
    controller.poll("k1")
    exposed = [e for e in controller.ledger() if e["disposition"] == "CANARY_EXPOSED"]
    open_now = controller.open_findings()
    assert [e["kind"] for e in exposed] == ["event", "artifact"]
    for entry in exposed:
        canary_id = "canary-" + entry["evidence"][0]["sha256"][7:23]
        assert canary_id in {r["id"] for r in entry["conditional_on"]}
    assert exposed[-1]["conditional_on"] == open_now
    controller.close()


def test_stored_evidence_bytes_are_refused_through_their_ledger_row(tmp_path):
    controller = _ledgered(tmp_path)
    (artifact,) = [
        e
        for e in controller.ledger()
        if e["kind"] == "artifact" and e["artifact_digest"] == ce._sha256(STRIPPED)
    ]
    stored = controller.root / artifact["evidence"][0]["path"]
    assert stored.read_bytes() == STRIPPED  # the bytes carry no tag
    ce.require_unconditional_path(stored, site="test")
    with pytest.raises(ce.ConditionalEvidenceError, match=ce.CITED):
        ce.require_unconditional_path(
            stored, site="test", ledgers=(controller.conditional_ledger(),)
        )
    controller.close()


# --- 4. repair attestation -------------------------------------------------------------


def test_repair_attestation_is_a_registered_policy_the_v2_policy_records():
    rules = ce.REPAIR_POLICIES["repair-attestation.v1"]
    identity = ce.repair_identity()
    assert identity["policy"] == "repair-attestation.v1"
    assert identity["digest"] == ce._sha256(ce.canonical(rules))
    assert ce.CONDITIONAL_EVIDENCE_V2["repair_attestation"] == {
        "policy": "repair-attestation.v1",
        "digest": identity["digest"],
    }
    assert ce.identity()["policy"] == "conditional-evidence.v2"
    assert "conditional-evidence.v1" in ce.POLICIES  # kept for v1 results
    target = rules["v2_target"]
    assert "after the repair time" in target and "contains the fix" in target
    with pytest.raises(ce.ConditionalEvidenceError, match="policy_unknown"):
        ce.repair_identity("repair-attestation.v0")


@pytest.mark.parametrize(
    "changes, code",
    [
        ({"rerun": []}, "repair_rerun_identities_required"),
        ({"rerun": [""]}, "repair_rerun_identities_required"),
        ({"rerun": ["   "]}, "repair_rerun_identities_required"),
        ({"rerun": None}, "repair_rerun_identities_required"),
        ({"rerun": "attempt-0001"}, "repair_rerun_identities_required"),
        ({"rerun": ["a", "a"]}, "repair_rerun_identities_required"),
        ({"code_ref": ""}, "repair_code_ref_required"),
        ({"code_ref": None}, "repair_code_ref_required"),
        ({"code_ref": "main"}, "repair_code_ref_required"),
        ({"operator": ""}, "operator_required"),
    ],
)
def test_a_repair_needs_every_rerun_identity(tmp_path, changes, code):
    controller = tc.make(tmp_path)
    controller.record_finding("f1", "FAILING_TRIGGER", b"one")
    arguments = {"operator": OPERATOR, "note": NOTE, "evidence": b"rerun", **RERUN}
    arguments.update(changes)
    with pytest.raises(ctl.ControllerError, match=code):
        controller.record_repair("f1", **arguments)
    assert controller.open_findings() == [t.ref(controller, "f1")]
    controller.close()


def _repaired(tmp_path):
    """f1 recorded, then repaired by attestation; a run returns a result."""
    provider = FakeProvider()
    controller = tc.make(tmp_path, provider)
    tc.register(controller)
    controller.record_finding("f1", "FAILING_TRIGGER", b"one")
    body = controller.record_repair(
        "f1", operator=OPERATOR, note=NOTE, evidence=b"rerun", **RERUN
    )
    controller.launch(tc.spec(), "k1")
    provider.export("fake-run-0001", "after.json", STRIPPED)
    controller.poll("k1")
    return controller, body


def test_results_after_a_repair_carry_its_attestation(tmp_path):
    controller, body = _repaired(tmp_path)
    assert body["rerun"] == RERUN["rerun"] and body["code_ref"] == RERUN["code_ref"]
    assert body["operator"] == OPERATOR
    assert body["attestation"] == ce.repair_identity()
    assert body["repair_id"] == CampaignController._repair_id(body)
    (artifact,) = [e for e in controller.ledger() if e["kind"] == "artifact"]
    assert artifact["conditional_on"] == []
    assert artifact.get(ce.ATTESTED) == [body["repair_id"]]
    entry = t.expand(controller, development=True)
    assert entry.get(ce.ATTESTED) == [body["repair_id"]]
    assert controller.conditional_tag().get(ce.ATTESTED) == [body["repair_id"]]
    # A recurrence reopens the finding: it is conditional again, not attested.
    controller.record_finding("f1", "FAILING_TRIGGER", b"one")
    assert ce.ATTESTED not in controller.conditional_tag()
    assert controller.conditional_tag()["conditional_on"] == [t.ref(controller, "f1")]
    controller.close()


def test_an_attested_repair_never_unblocks_lock_frozen_or_a_frozen_run(tmp_path):
    controller, _body = _repaired(tmp_path)
    # The LOCK path stays closed on the controller.
    with pytest.raises(ctl.ControllerError, match="admission_expansion_after_finding"):
        t.expand(controller)
    attested = {"result": "synthetic", **controller.conditional_tag()}
    ledger = controller.conditional_ledger()
    controller.close()
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "attested.json").write_bytes(json.dumps(attested).encode())
    (repo / "stripped.json").write_bytes(STRIPPED)
    tested = _tested(repo, "attested.json")
    ladder.validate(tested, "synthetic", repo, ledgers=(ledger,))  # TESTED: ok
    for evidence in ("attested.json", "stripped.json"):
        frozen = dict(tested, chosen=0)
        frozen["levels"] = [
            dict(tested["levels"][0], state="FROZEN", evidence=evidence)
        ]
        with pytest.raises(ladder.LadderError, match=ce.ATTESTED_AT_LOCK):
            ladder.validate(frozen, "synthetic", repo, ledgers=(ledger,))
    # A frozen run.
    protocol = json.loads(PROTOCOL.read_text())
    battery = json.loads((RECORDS / "f05.json").read_text())
    record = dict(
        battery,
        evidence=dict(dict.fromkeys(battery["evidence"]), frozen="attested.json"),
    )
    with pytest.raises(PipelineError, match=ce.ATTESTED_AT_LOCK):
        validate_record(record, protocol, {"f05"}, root=repo)
    # The LOCK.
    block = tca.accepted(tmp_path, "fixture")
    cited = tca.artifact(tmp_path, "attested.json", attested)

    def cite(document):
        for check in document["checks"].values():
            check["evidence"] = [cited]

    tca.alter_report(tmp_path, block, cite, admission.LEDGER_TRACK)
    with pytest.raises(admission.AdmissionError, match=ce.ATTESTED_AT_LOCK):
        admission.validate(block, "fixture", repository=tmp_path)
    # Track B's evidence is not a LOCK: an attested result may back its PASS.
    other = tca.accepted(tmp_path, "fixture")
    tca.alter_report(tmp_path, other, cite, "engineering_value")
    admission.validate(other, "fixture", repository=tmp_path)


# --- 5. attempt-ledger schema by kind ------------------------------------------------


def test_control_entries_keep_schema_v1_and_results_are_v2(tmp_path):
    provider = FakeProvider()
    controller = tc.make(tmp_path, provider)
    tc.register(controller)
    controller.launch(tc.spec(), "k1")
    provider.export("fake-run-0001", "out.json", b"{}")
    controller.poll("k1")
    entries = controller.ledger()
    controller.close()
    by_schema = {}
    for entry in entries:
        by_schema.setdefault(entry["schema"], set()).add(entry["kind"])
    assert ctl.ATTEMPT_SCHEMA_V1 == "carbon.agent-campaign.attempt.v1"
    assert by_schema[ctl.ATTEMPT_SCHEMA] <= ctl.RESULT_KINDS
    assert by_schema[ctl.ATTEMPT_SCHEMA_V1].isdisjoint(ctl.RESULT_KINDS)
    for entry in entries:
        tagged = set(ce.TAG_KEYS) <= set(entry)
        assert tagged == (entry["schema"] == ctl.ATTEMPT_SCHEMA)


# --- mutations: switching off each guard fails its test ---------------------------------


def _old_ingest_order(self, db, row, ref, hits, **entry):
    self._append(db, **entry)
    if hits:
        self._exposure(db, row, ref)


MUTATIONS = {
    "1_fail_does_not_rely": (
        lambda m: m.setattr(ce, "relies", lambda claim: True),
        lambda tmp: test_the_report_that_found_a_finding_backs_a_fail(
            tmp, "construction_integrity"
        ),
    ),
    "1_pass_still_relies": (
        lambda m: m.setattr(ce, "relies", lambda claim: False),
        lambda tmp: test_the_report_that_found_a_finding_backs_a_fail(
            tmp, "engineering_value"
        ),
    ),
    "2_ledger_stripped_copy": (
        lambda m: m.setattr(ce.ConditionalLedger, "lookup", lambda self, d: ([], [])),
        lambda tmp: test_a_copy_the_ledger_recorded_while_a_finding_was_open_is_refused(
            tmp, "stripped.json"
        ),
    ),
    "2_ledger_markdown_summary": (
        lambda m: m.setattr(ce.ConditionalLedger, "lookup", lambda self, d: ([], [])),
        lambda tmp: test_a_copy_the_ledger_recorded_while_a_finding_was_open_is_refused(
            tmp, "summary.md"
        ),
    ),
    "2_ledger_gzip_copy": (
        lambda m: m.setattr(ce.ConditionalLedger, "lookup", lambda self, d: ([], [])),
        lambda tmp: test_a_copy_the_ledger_recorded_while_a_finding_was_open_is_refused(
            tmp, "coverage.json.gz"
        ),
    ),
    "2_yaml_key": (
        lambda m: m.setattr(ce, "_embedded", lambda body, key: False),
        lambda tmp: test_without_a_ledger_only_the_bytes_speak(tmp),
    ),
    "2_compressed_copy": (
        lambda m: m.setattr(ce, "_expanded", lambda body, site: None),
        lambda tmp: test_without_a_ledger_only_the_bytes_speak(tmp),
    ),
    "2_lock_check_ledger": (
        lambda m: m.setattr(
            CampaignController,
            "conditional_ledger",
            lambda self: ce.ConditionalLedger(),
        ),
        test_the_lock_check_consults_the_controllers_own_ledger,
    ),
    "3_canary_finding_first": (
        lambda m: m.setattr(CampaignController, "_result_entry", _old_ingest_order),
        test_a_canary_finding_is_recorded_before_the_entry_that_exposed_it,
    ),
    "3_stored_evidence_ledger_row": (
        lambda m: m.setattr(ce, "_ledger_check", lambda *args: None),
        test_stored_evidence_bytes_are_refused_through_their_ledger_row,
    ),
    "4_registered_policy": (
        lambda m: m.setitem(ce.CONDITIONAL_EVIDENCE_V2, "repair_attestation", None),
        lambda tmp: test_repair_attestation_is_a_registered_policy_the_v2_policy_records(),
    ),
    "4_rerun_identities_required": (
        lambda m: m.setattr(
            CampaignController, "_check_attestation", staticmethod(lambda r, c: None)
        ),
        lambda tmp: test_a_repair_needs_every_rerun_identity(
            tmp, {"rerun": []}, "repair_rerun_identities_required"
        ),
    ),
    "4_code_ref_required": (
        lambda m: m.setattr(
            CampaignController, "_check_attestation", staticmethod(lambda r, c: None)
        ),
        lambda tmp: test_a_repair_needs_every_rerun_identity(
            tmp, {"code_ref": ""}, "repair_code_ref_required"
        ),
    ),
    "4_results_carry_the_attestation": (
        lambda m: m.setattr(CampaignController, "_attested_repairs", lambda s, db: []),
        test_results_after_a_repair_carry_its_attestation,
    ),
    "4_attestation_never_unblocks_lock": (
        lambda m: (
            m.setattr(ce, "attested_repairs", lambda value: []),
            m.setattr(CampaignController, "_attested_repairs", lambda s, db: []),
        ),
        test_an_attested_repair_never_unblocks_lock_frozen_or_a_frozen_run,
    ),
    "4_lock_path_stays_closed_after_repair": (
        lambda m: m.setattr(
            CampaignController, "_expansion_blocked", staticmethod(lambda db: False)
        ),
        test_an_attested_repair_never_unblocks_lock_frozen_or_a_frozen_run,
    ),
    "5_control_entries_stay_v1": (
        lambda m: m.setattr(ctl, "ATTEMPT_SCHEMA_V1", ctl.ATTEMPT_SCHEMA),
        test_control_entries_keep_schema_v1_and_results_are_v2,
    ),
}


@pytest.mark.parametrize("name", sorted(MUTATIONS))
def test_disabling_the_guard_fails_its_test(name, tmp_path, monkeypatch):
    disable, guard = MUTATIONS[name]
    intact, mutated = tmp_path / "intact", tmp_path / "mutated"
    intact.mkdir()
    mutated.mkdir()
    guard(intact)  # passes with the guard in place
    disable(monkeypatch)
    with pytest.raises(
        (
            AssertionError,
            pytest.fail.Exception,
            ctl.ControllerError,
            ce.ConditionalEvidenceError,
            admission.AdmissionError,
            ladder.LadderError,
        )
    ):
        guard(mutated)
