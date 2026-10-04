"""Carbon's verdict on an attack attempt (OWNER-GRAPHITE-ATTACKER-01 §3, AT-C).

Claims tested, with synthetic journals, the stub adapter of
`test_attack_analysis`, the real campaign controller over the fake provider
and, for specimens, battery's real reconstruction gate and clean rebuild (no
model, pod, key, network or spend):

- Carbon rebuilds every construction an attempt carries; one it cannot
  rebuild is refused typed and never scored (the oracle is not consulted); if
  the path accepted it, that is a FAILING_TRIGGER;
- a construction whose pod build differs from Carbon's own is a
  FAILING_TRIGGER and is not scored;
- a timeout or FAILED_INFRA is never a pass, an exposure is OTHER_SIGNAL, and
  Graphite's own refusal is never counted as the path's;
- findings use only the admission CONDITIONS; a breached specimen is bundled
  and re-checked from the bundle alone, a mismatch adding FAILING_TRIGGER;
- a finding is recorded on the controller, after which it refuses every
  expansion;
- mutations: disabling each of those protections turns its guarding test red.
"""

from __future__ import annotations

import json

import pytest
from test_agent_campaign_controller import make
from test_attack_analysis import (
    DRY,
    FORBIDDEN,
    GOOD,
    INFO,
    MISSING,
    RESULT,
    OracleResult,
    StubAdapter,
    dry,
    path_reply,
    write_call,
)

from carbon.agent_campaign import controller as ctl
from carbon.agent_campaign.attack import analysis, verify
from carbon.agent_campaign.graphite import tools as toolbox
from carbon.challenge_readiness.admission import CONDITIONS

ACCEPTED = path_reply("dry_validate", {"valid": True})
REFUSED = path_reply("dry_validate", {"valid": False})
BATTERY = "battery-fastcharge-ageing-development-v1"


def attempt_of(tmp_path, name=DRY, arguments=None, result=ACCEPTED):
    write_call(tmp_path, name, dry(GOOD) if arguments is None else arguments, result)
    (found,) = analysis.attempts(tmp_path)
    return found


def breaching(condition=None, near_miss=False):
    return lambda family, attempt: OracleResult("BREACHED", condition, near_miss, {})


# -- rebuild or refuse, typed -------------------------------------------------------------------
def test_an_unrebuildable_construction_the_path_accepted_is_a_fail_open(tmp_path):
    adapter = StubAdapter()
    found = attempt_of(tmp_path, arguments=dry(FORBIDDEN))
    verdict = verify.verify(found, adapter)
    assert verdict.rebuild == verify.UNREBUILDABLE
    assert verdict.unrebuildable == "pretrained_payload_refused"
    assert verdict.outcome == verify.BREACHED
    assert verdict.conditions == ("FAILING_TRIGGER",)
    assert verdict.scored is False
    assert adapter.oracle_calls == []  # never scored
    assert adapter.rebuild_calls == [FORBIDDEN]


@pytest.mark.parametrize(
    ("result", "outcome", "refused_by"),
    [
        (REFUSED, "HELD", "path"),
        (path_reply("dry_validate"), "UNDETERMINED", "path"),
    ],
)
def test_an_unrebuildable_construction_the_path_refused_or_left_unclear_is_no_finding(
    tmp_path, result, outcome, refused_by
):
    adapter = StubAdapter(raises=True)  # a raised typed refusal reads the same
    verdict = verify.verify(
        attempt_of(tmp_path, arguments=dry(FORBIDDEN), result=result), adapter
    )
    assert (verdict.outcome, verdict.refused_by) == (outcome, refused_by)
    assert verdict.rebuild == verify.UNREBUILDABLE and not verdict.finding
    assert verdict.scored is False and adapter.oracle_calls == []


def test_an_unrecorded_contract_checks_nothing(tmp_path):
    adapter = StubAdapter(refuse=lambda c: verify.CONTRACT_UNRECORDED)
    verdict = verify.verify(attempt_of(tmp_path), adapter)
    assert verdict.outcome == verify.UNDETERMINED and not verdict.finding
    assert verdict.unrebuildable == verify.CONTRACT_UNRECORDED


def test_an_unparseable_construction_is_refused_typed_without_a_rebuild(tmp_path):
    adapter = StubAdapter()
    found = attempt_of(tmp_path, arguments={"strategy_json": "{nope"})
    verdict = verify.verify(found, adapter)
    assert verdict.unrebuildable == verify.CONSTRUCTION_UNPARSEABLE
    assert verdict.outcome == verify.BREACHED  # the path said it was valid
    assert adapter.rebuild_calls == [] and adapter.oracle_calls == []


def test_a_rebuildable_construction_is_rebuilt_then_judged_by_the_oracle(tmp_path):
    adapter = StubAdapter()
    verdict = verify.verify(attempt_of(tmp_path), adapter)
    assert verdict.rebuild == verify.REBUILT and verdict.outcome == verify.HELD
    assert verdict.scored is True and not verdict.finding
    assert adapter.oracle_calls == [("artifact_family", "epoch-1-tool-000")]
    assert set(verdict.evidence) == {
        "intent",
        "result",
        "construction",
        "rebuilt",
        "oracle",
    }


def test_a_crash_in_carbons_own_rebuild_or_oracle_is_infrastructure(tmp_path):
    def boom(*_):
        raise RuntimeError("disk full")

    crashing = StubAdapter(refuse=boom)
    verdict = verify.verify(attempt_of(tmp_path), crashing)
    assert verdict.outcome == verify.INFRA and verdict.reason.startswith("rebuild")
    verdict = verify.verify(attempt_of(tmp_path / "b"), StubAdapter(oracle=boom))
    assert verdict.outcome == verify.INFRA and not verdict.scored


def test_other_adapter_result_shapes_read_the_same(tmp_path):
    """The engine's `Rebuilt` may carry its record as `built`, an oracle
    result may be a mapping with `breached`, and a refusal class need only be
    named for Unrebuildable."""

    class Built:
        def __init__(self, record):
            self.built = record

    class ConstructionUnrebuildable(Exception):
        code = "custom_refusal"

    class Shapes(StubAdapter):
        def rebuild(self, construction):
            if "pretrained_weights" in construction:
                return ConstructionUnrebuildable()
            return Built({"recipe": construction})

    adapter = Shapes(oracle=lambda family, attempt: {"breached": True})
    verdict = verify.verify(attempt_of(tmp_path), adapter)
    assert verdict.rebuild == verify.REBUILT and verdict.condition == "FAILING_TRIGGER"
    verdict = verify.verify(
        attempt_of(tmp_path / "b", arguments=dry(FORBIDDEN)), adapter
    )
    assert verdict.unrebuildable == "custom_refusal" and not verdict.scored
    # An oracle outcome Carbon does not know is its own defect: never a pass.
    verdict = verify.verify(
        attempt_of(tmp_path / "c"),
        StubAdapter(oracle=lambda f, a: {"outcome": "PASS"}),
    )
    assert (verdict.outcome, verdict.reason) == ("INFRA", "oracle_crashed:ValueError")


def test_verification_never_reads_held_out_controls(tmp_path):
    adapter = StubAdapter(oracle=breaching())
    for n, arguments in enumerate((dry(GOOD), dry(FORBIDDEN))):
        write_call(tmp_path, DRY, arguments, ACCEPTED, turn=n)
    verdicts = verify.verify_all(analysis.attempts(tmp_path), adapter)
    assert [v.outcome for v in verdicts] == ["BREACHED", "BREACHED"]
    assert adapter.controls_calls == []


# -- pods -----------------------------------------------------------------------------------
def test_a_pod_build_that_differs_from_carbons_is_a_finding_and_never_scored(tmp_path):
    adapter = StubAdapter()
    found = attempt_of(tmp_path)
    same = adapter.rebuild(GOOD).record
    verdict = verify.verify(found, adapter, pods={found.identity: dict(same)})
    assert verdict.outcome == verify.HELD and verdict.scored
    other = {**same, "recipe": {**GOOD, "fins": 13}}
    adapter = StubAdapter()
    verdict = verify.verify(found, adapter, pods=lambda a: other)
    assert verdict.outcome == verify.BREACHED
    assert verdict.conditions == ("FAILING_TRIGGER",)
    assert verdict.reason == "rebuild_mismatch" and not verdict.scored
    assert verdict.evidence["differences"] == ["recipe"]
    assert adapter.oracle_calls == []


def test_a_pod_scored_attempt_without_its_build_record_is_a_mismatch(tmp_path):
    scored = {"status": "SCORED", "proposal_id": "p-1", "authority_granted": False}
    found = attempt_of(tmp_path, result=scored)
    verdict = verify.verify(found, StubAdapter(), pods={})
    assert verdict.evidence["differences"] == ["built_record_missing"]
    assert verdict.condition == "FAILING_TRIGGER"


# -- exposure, Graphite's refusals, infrastructure ------------------------------------------
def test_an_exposure_is_other_signal(tmp_path):
    withheld = toolbox.refusal(toolbox.REFUSED_RESULT, "protected_material_in_result")
    verdict = verify.verify(attempt_of(tmp_path, INFO, {}, withheld), StubAdapter())
    assert verdict.outcome == verify.BREACHED
    assert verdict.conditions == ("OTHER_SIGNAL",)
    leaked = path_reply("get_challenge_info", {"note": "a draw_id"})
    verdict = verify.verify(attempt_of(tmp_path / "b", INFO, {}, leaked), StubAdapter())
    assert verdict.conditions == ("OTHER_SIGNAL",)


def test_graphites_own_refusal_is_never_the_paths_defense(tmp_path):
    adapter = StubAdapter()
    refused = toolbox.refusal(toolbox.REFUSED_MANIFEST, "tool_not_in_role_manifest")
    verdict = verify.verify(attempt_of(tmp_path, result=refused), adapter)
    assert (verdict.outcome, verdict.refused_by) == ("HELD", "graphite")
    asked = {"strategy_json": json.dumps({**GOOD, "x": "derived_seed"})}
    protected = toolbox.refusal(
        toolbox.REFUSED_PROTECTED, "protected_material_requested"
    )
    verdict = verify.verify(attempt_of(tmp_path / "b", DRY, asked, protected), adapter)
    assert (verdict.outcome, verdict.refused_by) == ("HELD", "graphite")
    assert adapter.rebuild_calls == [] and adapter.oracle_calls == []


@pytest.mark.parametrize(
    "result",
    [
        path_reply("get_research_result", terminal={"state": "FAILED_INFRA"}),
        {"status": "FAILED_INFRA", "reason_code": "interrupted_not_rerun"},
        MISSING,
    ],
)
def test_failed_infra_and_timeouts_are_never_a_pass(tmp_path, result):
    adapter = StubAdapter()
    arguments = {"task_id": "t", "poll_sequence": 0}
    verdict = verify.verify(attempt_of(tmp_path, RESULT, arguments, result), adapter)
    assert verdict.outcome == verify.INFRA
    assert verdict.outcome != verify.HELD and not verdict.scored
    assert not verdict.finding and adapter.oracle_calls == []


def test_an_attempt_no_family_takes_is_not_applicable(tmp_path):
    found = attempt_of(tmp_path, "graphite_unknown_tool", {}, path_reply("x"))
    adapter = StubAdapter()
    verdict = verify.verify(found, adapter)
    assert verdict.family == analysis.UNASSIGNED
    assert verdict.outcome == verify.NOT_APPLICABLE and adapter.oracle_calls == []


# -- conditions -------------------------------------------------------------------------------
@pytest.mark.parametrize("condition", sorted(CONDITIONS))
def test_an_oracle_breach_keeps_its_condition(tmp_path, condition):
    adapter = StubAdapter(oracle=breaching(condition, near_miss=True))
    verdict = verify.verify(attempt_of(tmp_path), adapter)
    assert verdict.conditions == (condition,) and verdict.near_miss


def test_a_breach_without_a_condition_is_a_failing_trigger(tmp_path):
    verdict = verify.verify(attempt_of(tmp_path), StubAdapter(oracle=breaching()))
    assert verdict.conditions == ("FAILING_TRIGGER",)


def test_a_finding_outside_the_conditions_vocabulary_is_refused(tmp_path):
    adapter = StubAdapter(oracle=breaching("SECURITY_BREACH"))
    with pytest.raises(ValueError, match="finding_condition_outside_conditions"):
        verify.verify(attempt_of(tmp_path), adapter)
    with pytest.raises(ValueError, match="finding_condition_outside_conditions"):
        verify.Verdict("a", "f", verify.REBUILT, verify.BREACHED, ("EXPLOIT",))


def test_a_verdict_cannot_score_what_carbon_did_not_rebuild():
    with pytest.raises(ValueError, match="scored_an_unrebuildable"):
        verify.Verdict("a", "f", verify.UNREBUILDABLE, verify.HELD, scored=True)
    with pytest.raises(ValueError, match="infrastructure_is_never_scored"):
        verify.Verdict("a", "f", verify.REBUILT, verify.INFRA, scored=True)
    with pytest.raises(ValueError, match="breach_without_a_condition"):
        verify.Verdict("a", "f", verify.REBUILT, verify.BREACHED)
    with pytest.raises(ValueError, match="condition_without_a_breach"):
        verify.Verdict("a", "f", verify.REBUILT, verify.HELD, ("FAILING_TRIGGER",))


# -- specimens --------------------------------------------------------------------------------
class SpecimenAdapter(StubAdapter):
    def __init__(self, status, **kw):
        super().__init__(oracle=breaching("SCORE_VALUE_DIVERGENCE"), **kw)
        self.status, self.bundled = status, []

    def bundle_specimen(self, construction, record, folder):
        self.bundled.append((construction, folder))

    def clean_rebuild(self, folder):
        return {"status": self.status, "differences": ["program"]}


def test_a_breached_specimen_is_bundled_and_its_mismatch_is_a_failing_trigger(tmp_path):
    adapter = SpecimenAdapter("REBUILD_MISMATCH")
    verdict = verify.verify(attempt_of(tmp_path), adapter, specimen_dir=tmp_path / "s")
    assert verdict.conditions == ("SCORE_VALUE_DIVERGENCE", "FAILING_TRIGGER")
    assert verdict.specimen["status"] == "REBUILD_MISMATCH"
    assert adapter.bundled[0][0] == GOOD
    adapter = SpecimenAdapter("REBUILT")
    verdict = verify.verify(attempt_of(tmp_path / "b"), adapter, specimen_dir=tmp_path)
    assert verdict.conditions == ("SCORE_VALUE_DIVERGENCE",)
    # Without a specimen directory nothing is bundled.
    adapter = SpecimenAdapter("REBUILD_MISMATCH")
    verdict = verify.verify(attempt_of(tmp_path / "c"), adapter)
    assert verdict.specimen is None and adapter.bundled == []


def test_a_battery_specimen_rebuilds_from_its_bundle_alone(tmp_path):
    """Battery's real gate (`experiment.admit`) and Graphite's clean rebuild
    (`delivery.clean_rebuild`) on a bundled specimen: the same construction
    rebuilds; a record that differs from what Carbon builds does not."""
    from carbon.agent_campaign.graphite import experiment
    from carbon.battery.research import SCAFFOLD

    record = experiment.admit(SCAFFOLD, 7)

    class Battery(StubAdapter):
        def __init__(self, rebuilt):
            super().__init__(oracle=breaching())
            self.rebuilt = rebuilt

        def rebuild(self, construction):
            return dict(self.rebuilt)

    found = attempt_of(tmp_path, arguments=dry(SCAFFOLD))
    verdict = verify.verify(found, Battery(record), specimen_dir=tmp_path / "ok")
    assert verdict.specimen["status"] == "REBUILT"
    assert verdict.conditions == ("FAILING_TRIGGER",)
    forged = {**record, "program": "sha256:" + "0" * 64}
    verdict = verify.verify(found, Battery(forged), specimen_dir=tmp_path / "bad")
    assert verdict.specimen["status"] == "REBUILD_MISMATCH"
    assert verdict.specimen["differences"] == ["program"]
    # Re-verifying writes the same bundle: idempotent.
    again = verify.verify(found, Battery(forged), specimen_dir=tmp_path / "bad")
    assert again.specimen == verdict.specimen


def test_a_specimen_that_names_protected_material_is_never_written(tmp_path):
    adapter = SpecimenAdapter("REBUILT")
    adapter._refuse = lambda c: None
    adapter.construction = lambda attempt: {"note": "hidden_case"}
    verdict = verify.verify(attempt_of(tmp_path), adapter, specimen_dir=tmp_path)
    assert verdict.specimen["status"] == "NOT_BUNDLED" and adapter.bundled == []


# -- recording on the controller --------------------------------------------------------------
def test_a_finding_is_recorded_and_stops_every_expansion(tmp_path):
    controller = make(tmp_path)
    adapter = StubAdapter()
    held = verify.verify(attempt_of(tmp_path / "a"), adapter)
    assert verify.record(held, controller) == ()
    controller.record_expansion(
        challenge=BATTERY,
        profile="level-0",
        widened="nothing, a probe before any finding",
        permissions="sha256:" + "e" * 64,
        operator="carbon-operator",
    )
    breached = verify.verify(
        attempt_of(tmp_path / "b", arguments=dry(FORBIDDEN)), adapter
    )
    ids = verify.record(breached, controller)
    assert len(ids) == 1 and ids[0].startswith("attack-failing-trigger-")
    assert verify.record(breached, controller) == ids  # idempotent
    findings = controller.admission_ledgers()["findings"]
    assert [(f["id"], f["condition"]) for f in findings] == [
        (ids[0], "FAILING_TRIGGER")
    ]
    evidence = json.loads(
        (controller.root / findings[0]["evidence"]["path"]).read_bytes()
    )
    assert evidence["verdict"]["attempt"] == breached.attempt
    with pytest.raises(ctl.ControllerError, match="admission_expansion_after_finding"):
        controller.record_expansion(
            challenge=BATTERY,
            profile="level-1",
            widened="bounded loss expressions",
            permissions="sha256:" + "f" * 64,
            operator="carbon-operator",
        )
    controller.close()


def test_evidence_that_would_name_protected_material_is_redacted_not_dropped(tmp_path):
    controller = make(tmp_path)
    verdict = verify.Verdict(
        "epoch-1-tool-000",
        "artifact_family",
        verify.REBUILT,
        verify.BREACHED,
        ("FAILING_TRIGGER",),
        reason="the hidden_case answer",
    )
    (finding_id,) = verify.record(verdict, controller)
    (finding,) = controller.admission_ledgers()["findings"]
    body = (controller.root / finding["evidence"]["path"]).read_bytes()
    assert not toolbox.protected(json.loads(body))
    assert json.loads(body)["redacted"] == "protected_material"
    assert finding["id"] == finding_id
    controller.close()


# -- mutations: each protection, switched off, turns its guarding test red -------------------
def _guard(test, *args):
    return lambda tmp: (tmp.mkdir(parents=True), test(tmp, *args))


MUTATIONS = {
    "unrebuildable_is_never_scored": (
        lambda m: m.setattr(verify, "is_unrebuildable", lambda value: False),
        _guard(test_an_unrebuildable_construction_the_path_accepted_is_a_fail_open),
    ),
    "failed_infra_is_never_a_pass": (
        lambda m: m.setattr(analysis, "INFRA_STATES", frozenset()),
        _guard(
            test_failed_infra_and_timeouts_are_never_a_pass,
            path_reply("get_research_result", terminal={"state": "FAILED_INFRA"}),
        ),
    ),
    "findings_only_in_conditions": (
        lambda m: m.setattr(
            verify, "check_conditions", lambda conditions: tuple(conditions)
        ),
        _guard(test_a_finding_outside_the_conditions_vocabulary_is_refused),
    ),
    "expansion_stops_after_a_finding": (
        lambda m: m.setattr(
            ctl.CampaignController, "_expansion_blocked", staticmethod(lambda db: False)
        ),
        _guard(test_a_finding_is_recorded_and_stops_every_expansion),
    ),
    "pod_rebuild_is_compared": (
        lambda m: m.setattr(
            verify, "_differences", lambda adapter, expected, built: []
        ),
        _guard(
            test_a_pod_build_that_differs_from_carbons_is_a_finding_and_never_scored
        ),
    ),
}


@pytest.mark.parametrize("name", sorted(MUTATIONS))
def test_disabling_the_protection_fails_its_test(name, tmp_path, monkeypatch):
    disable, guard = MUTATIONS[name]
    guard(tmp_path / "intact")  # passes with the protection in place
    disable(monkeypatch)
    with pytest.raises((AssertionError, pytest.fail.Exception)):
        guard(tmp_path / "mutated")
