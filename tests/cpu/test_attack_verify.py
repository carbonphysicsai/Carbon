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


class RecordedUnrebuildable:
    """A typed refusal that still carries a record (as a refusal's detail may):
    only the refusal type keeps it from being read as rebuilt."""

    code = "pretrained_payload_refused"
    issues = ()

    def __init__(self):
        self.record = {"recipe": FORBIDDEN, "recipe_digest": "sha256:" + "7" * 64}


def test_a_refusal_carrying_a_record_is_still_never_scored(tmp_path):
    class Refusing(StubAdapter):
        def rebuild(self, construction):
            self.rebuild_calls.append(construction)
            return RecordedUnrebuildable()

    adapter = Refusing(oracle=breaching())
    found = attempt_of(tmp_path, arguments=dry(FORBIDDEN))
    verdict = verify.verify(found, adapter)
    assert adapter.oracle_calls == []  # never scored
    assert verdict.rebuild == verify.UNREBUILDABLE and not verdict.scored
    assert verdict.unrebuildable == "pretrained_payload_refused"


def test_the_unrebuildable_guard_is_what_keeps_the_oracle_away(tmp_path, monkeypatch):
    """The mutation reaches the oracle: with the refusal type no longer
    recognised, the refused construction is rebuilt from its record and
    scored, so the guard above fails for the named reason."""
    monkeypatch.setattr(verify, "is_unrebuildable", lambda value: False)

    class Refusing(StubAdapter):
        def rebuild(self, construction):
            return RecordedUnrebuildable()

    adapter = Refusing(oracle=breaching())
    verdict = verify.verify(attempt_of(tmp_path, arguments=dry(FORBIDDEN)), adapter)
    assert adapter.oracle_calls == [("artifact_family", "epoch-1-tool-000")]
    assert verdict.scored and verdict.rebuild == verify.REBUILT


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


@pytest.mark.parametrize(
    ("said", "outcome", "conditions", "reason", "scored"),
    [
        ({"verdict": "EXPOSURE"}, "BREACHED", ("OTHER_SIGNAL",), "oracle_exposure", 1),
        (
            {"verdict": "EXPOSURE", "condition": "OTHER_SIGNAL"},
            "BREACHED",
            ("OTHER_SIGNAL",),
            "oracle_exposure",
            1,
        ),
        ({"verdict": "TIMEOUT"}, "INFRA", (), "oracle_no_answer:TIMEOUT", 0),
        ({"verdict": "FAILED_INFRA"}, "INFRA", (), "oracle_no_answer:FAILED_INFRA", 0),
        ({"verdict": "CRASHED"}, "INFRA", (), "oracle_no_answer:CRASHED", 0),
        ({"verdict": "NOT_RUN"}, "NOT_APPLICABLE", (), "oracle_not_run", 0),
        ({"verdict": "INCONCLUSIVE"}, "UNDETERMINED", (), "oracle_inconclusive", 0),
        ({"outcome": "UNDETERMINED"}, "UNDETERMINED", (), None, 0),
    ],
)
def test_every_oracle_verdict_the_adapters_speak_is_read(
    tmp_path, said, outcome, conditions, reason, scored
):
    """The engine adapter's NO_ANSWER, INCONCLUSIVE and NOT_RUN, and
    battery's EXPOSURE. Only HELD or BREACHED is scored."""
    adapter = StubAdapter(oracle=lambda family, attempt: said)
    verdict = verify.verify(attempt_of(tmp_path), adapter)
    assert (verdict.outcome, verdict.conditions, verdict.reason) == (
        outcome,
        conditions,
        reason,
    )
    assert verdict.scored is bool(scored)


def test_the_oracle_is_handed_what_the_path_did(tmp_path):
    seen = []
    adapter = StubAdapter(oracle=lambda f, a: seen.append(a) or OracleResult("HELD"))
    verify.verify(attempt_of(tmp_path), adapter)
    verify.verify(attempt_of(tmp_path / "b", result=REFUSED), adapter)
    accepted, refused = seen
    assert isinstance(accepted, verify.OracleAttempt)
    assert (accepted.name, accepted.identity) == ("epoch-1-tool-000",) * 2
    assert accepted.value == GOOD and accepted.arguments == dry(GOOD)
    assert accepted.tool == DRY and accepted.operation == "dry_validate"
    assert (accepted.path_accepted, refused.path_accepted) == (True, False)
    # Without a construction, the value is the call's arguments.
    verify.verify(attempt_of(tmp_path / "c", INFO, {"topic": "x"}), adapter)
    assert seen[-1].value == {"topic": "x"}

    class Derives(StubAdapter):
        def attempt_input(self, family, attempt):
            return None

    # An adapter that derives its own input is never handed a `value`.
    verify.verify(attempt_of(tmp_path / "d"), Derives(oracle=adapter._oracle))
    assert not hasattr(seen[-1], "value") and seen[-1].arguments == dry(GOOD)
    assert getattr(seen[-1], "value", "absent") == "absent"


def test_a_digest_only_rebuilt_reads_as_its_digests_and_detail(tmp_path):
    """The engine adapter's `Rebuilt(construction_digest, rebuilt_digest,
    detail)`: rebuilt, then judged."""

    class Rebuilt:
        def __init__(self, detail):
            self.construction_digest = "sha256:" + "a" * 64
            self.rebuilt_digest = "sha256:" + "b" * 64
            self.detail = detail

    class Digests(StubAdapter):
        def rebuild(self, construction):
            return Rebuilt({"recipe": construction})

    adapter = Digests()
    verdict = verify.verify(attempt_of(tmp_path), adapter)
    assert verdict.rebuild == verify.REBUILT and verdict.scored
    assert verify.record_of(Rebuilt({})) == {
        "construction_digest": "sha256:" + "a" * 64,
        "rebuilt_digest": "sha256:" + "b" * 64,
    }
    # Battery's: the record Carbon built sits in `detail["record"]`.
    inner = {"recipe_digest": "sha256:" + "c" * 64}
    assert verify.record_of(Rebuilt({"record": inner, "seed": 0})) == inner
    with pytest.raises(TypeError, match="adapter_rebuild_returned_no_record"):
        verify.record_of(object())


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


SCORED = {"status": "SCORED", "proposal_id": "p-1", "authority_granted": False}


@pytest.mark.parametrize("pods", [None, {}])
def test_a_pod_scored_attempt_without_its_build_record_is_undetermined(tmp_path, pods):
    """Carbon's own missing evidence is neither a breach nor a score."""
    adapter = StubAdapter()
    found = attempt_of(tmp_path, result=SCORED)
    verdict = verify.verify(found, adapter, pods=pods)
    assert verdict.outcome == verify.UNDETERMINED and not verdict.finding
    assert verdict.reason == "pod_build_record_not_supplied"
    assert verdict.scored is False and adapter.oracle_calls == []
    # With the record supplied, it is compared and then judged.
    built = adapter.rebuild(GOOD).record
    verdict = verify.verify(found, adapter, pods={found.identity: dict(built)})
    assert verdict.outcome == verify.HELD and verdict.scored


def test_an_unrebuildable_construction_a_pod_scored_is_a_fail_open(tmp_path):
    adapter = StubAdapter()
    found = attempt_of(tmp_path, arguments=dry(FORBIDDEN), result=SCORED)
    assert found.accepted is True
    verdict = verify.verify(found, adapter)
    assert verdict.rebuild == verify.UNREBUILDABLE and verdict.outcome == "BREACHED"
    assert verdict.conditions == ("FAILING_TRIGGER",) and not verdict.scored
    assert adapter.oracle_calls == []


def test_a_crash_comparing_the_pod_build_is_infrastructure(tmp_path):
    class Raising(StubAdapter):
        def rebuild_differences(self, rebuilt, built):
            raise AttributeError("'dict' object has no attribute 'record'")

    adapter = Raising()
    found = attempt_of(tmp_path, result=SCORED)
    verdicts = verify.verify_all([found], adapter, pods={found.identity: {}})
    assert [(v.outcome, v.reason) for v in verdicts] == [
        ("INFRA", "rebuild_compare_crashed:AttributeError")
    ]
    assert not verdicts[0].scored and adapter.oracle_calls == []


def test_an_adapters_own_comparison_gets_what_its_rebuild_returned(tmp_path):
    seen = []

    class Own(StubAdapter):
        def rebuild_differences(self, rebuilt, built):
            seen.append(rebuilt)
            return [] if rebuilt.record == built else ["recipe"]

    adapter = Own()
    found = attempt_of(tmp_path)
    same = adapter.rebuild(GOOD).record
    assert verify.verify(found, adapter, pods={found.identity: same}).scored
    assert type(seen[0]).__name__ == "Rebuilt" and seen[0].record == same
    verdict = verify.verify(found, adapter, pods={found.identity: {"x": 1}})
    assert verdict.conditions == ("FAILING_TRIGGER",)


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


def test_the_loops_own_refusals_are_never_the_paths_defense(tmp_path):
    from test_attack_analysis import _loop_refusals

    adapter = StubAdapter()
    for n, refusal in enumerate(_loop_refusals()):
        found = attempt_of(tmp_path / str(n), arguments=dry(FORBIDDEN), result=refusal)
        verdict = verify.verify(found, adapter)
        assert (verdict.outcome, verdict.refused_by) == ("HELD", "graphite")
        assert not verdict.scored
    assert adapter.rebuild_calls == [] and adapter.oracle_calls == []


def test_an_agent_naming_a_protected_case_is_other_signal_with_its_own_reason(
    tmp_path,
):
    words = {"summary": "the hidden_case answer"}
    found = attempt_of(tmp_path, "graphite_finish", words, {"status": "OK", **words})
    verdict = verify.verify(found, StubAdapter())
    assert verdict.conditions == ("OTHER_SIGNAL",)
    assert verdict.reason == "protected_named_by_agent"


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


# -- the sibling slices' real adapters (run once they are present) ----------------------------
def _engine_adapter(*, weak=False, slow=False, lax_rebuild=False):
    """A synthetic heat-sink Challenge built from the engine's own adapter
    parts (`attack.adapter.DeclaredAdapter`): one run family, the other seven
    checks declared seams. `weak` lets the real boundary through;
    `lax_rebuild` rebuilds every construction."""
    adapters = pytest.importorskip("carbon.agent_campaign.attack.adapter")
    engine = pytest.importorskip("carbon.agent_campaign.attack.engine")

    def real(value):
        if slow:
            raise TimeoutError("boundary")
        payload = "pretrained_weights" in value
        return {"accepted": not payload, "payload": payload}

    def lax(value):
        return {"accepted": True, "payload": "pretrained_weights" in value}

    family = engine.Family(
        "weights_field",
        "artifact_and_dependency_attacks",
        lax if weak else real,
        lambda: (("weights", FORBIDDEN),),
        lax,
        lambda result: result["accepted"] and result["payload"],
        lambda: True,
    )

    def rebuild(construction):
        if "pretrained_weights" in construction and not (weak or lax_rebuild):
            return adapters.Unrebuildable("refused_by_contract", "pretrained_weights")
        return adapters.Rebuilt(
            engine.digest(construction),
            engine.digest({"built": construction}),
            {"recipe": construction},
        )

    return adapters.validate(
        adapters.DeclaredAdapter(
            challenge_id="synthetic-heat-sink-v1",
            level=0,
            contract_digest="sha256:" + "5" * 64,
            family_defs=(
                adapters.FamilyDef(
                    "weights_field",
                    family.check,
                    "the recipe's field allow-list",
                    FORBIDDEN,
                    GOOD,
                    family=family,
                ),
            ),
            control_set=(
                adapters.Control("good", "weights_field", "trained", "v1", GOOD),
                adapters.Control("good_too", "weights_field", "held_out", "v1", GOOD),
            ),
            seams=tuple(
                adapters.SeamFamily(check, check, 0, "declared for this test")
                for check in adapters.TRACK_A_CHECKS
                if check != family.check
            ),
            rebuilder=rebuild,
        )
    )


def test_the_engine_adapters_real_shapes_verify(tmp_path):
    adapter = _engine_adapter()
    # A valid construction its specimen cannot fire on: the hold is no
    # evidence (the engine oracle's INCONCLUSIVE), never scored.
    blind = verify.verify(attempt_of(tmp_path / "a"), adapter)
    assert (blind.family, blind.rebuild, blind.outcome, blind.reason) == (
        "weights_field",
        "REBUILT",
        "UNDETERMINED",
        "oracle_inconclusive",
    )
    assert not blind.scored and not blind.finding
    held = verify.verify(
        attempt_of(tmp_path / "h", arguments=dry(FORBIDDEN)),
        _engine_adapter(lax_rebuild=True),
    )
    assert (held.rebuild, held.outcome, held.scored) == ("REBUILT", "HELD", True)
    fail_open = verify.verify(
        attempt_of(tmp_path / "b", arguments=dry(FORBIDDEN)), adapter
    )
    assert fail_open.unrebuildable == "refused_by_contract"
    assert fail_open.conditions == ("FAILING_TRIGGER",) and not fail_open.scored
    breach = verify.verify(
        attempt_of(tmp_path / "c", arguments=dry(FORBIDDEN)), _engine_adapter(weak=True)
    )
    assert (breach.rebuild, breach.outcome, breach.conditions) == (
        "REBUILT",
        "BREACHED",
        ("FAILING_TRIGGER",),
    )
    slow = verify.verify(attempt_of(tmp_path / "d"), _engine_adapter(slow=True))
    assert (slow.outcome, slow.reason) == ("INFRA", "oracle_no_answer:TIMEOUT")
    assert not slow.scored and not slow.finding


def test_the_battery_adapters_real_shapes_verify(tmp_path):
    battery = pytest.importorskip("carbon.agent_campaign.attack.adapters.battery")
    from carbon.battery.research import SCAFFOLD

    adapter = battery.ADAPTER
    found = attempt_of(tmp_path / "a", arguments=dry(SCAFFOLD))
    assert analysis.family_of(found, adapter) == "recipe_surface"
    held = verify.verify(found, adapter)
    assert (held.rebuild, held.outcome, held.scored) == ("REBUILT", "HELD", True)
    forged = {**SCAFFOLD, "pretrained_weights": "https://x/w.bin"}
    fail_open = verify.verify(
        attempt_of(tmp_path / "b", arguments=dry(forged)), adapter
    )
    assert fail_open.rebuild == "UNREBUILDABLE" and not fail_open.scored
    assert fail_open.conditions == ("FAILING_TRIGGER",)
    unclear = verify.verify(
        attempt_of(tmp_path / "u", arguments=dry(SCAFFOLD), result=path_reply("x")),
        adapter,
    )
    assert (unclear.outcome, unclear.reason) == ("UNDETERMINED", "oracle_inconclusive")
    assert not unclear.finding and not unclear.scored
    record = verify.record_of(adapter.rebuild(SCAFFOLD))
    assert {"recipe_digest", "contract_digest", "record_sequence"} <= set(record)
    scored = attempt_of(tmp_path / "c", arguments=dry(SCAFFOLD), result=SCORED)
    same = verify.verify(scored, adapter, pods={scored.identity: dict(record)})
    assert same.scored and not same.finding
    tampered = {**record, "program": "sha256:" + "0" * 64}
    bad = verify.verify(scored, adapter, pods={scored.identity: tampered})
    assert (bad.reason, bad.conditions) == ("rebuild_mismatch", ("FAILING_TRIGGER",))
    assert bad.evidence["differences"] == ["program"]


# -- mutations: each protection, switched off, turns its guarding test red -------------------
def _guard(test, *args):
    return lambda tmp: (tmp.mkdir(parents=True), test(tmp, *args))


MUTATIONS = {
    "unrebuildable_is_never_scored": (
        lambda m: m.setattr(verify, "is_unrebuildable", lambda value: False),
        _guard(test_a_refusal_carrying_a_record_is_still_never_scored),
    ),
    "pod_scored_without_a_record_is_undetermined": (
        lambda m: m.setattr(verify, "_pod_scored", lambda result: False),
        _guard(test_a_pod_scored_attempt_without_its_build_record_is_undetermined, {}),
    ),
    "the_loops_refusals_are_graphites": (
        lambda m: m.setattr(analysis, "REFUSAL_CODES", ()),
        _guard(test_the_loops_own_refusals_are_never_the_paths_defense),
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
            verify, "_differences", lambda adapter, rebuilt, record, built: []
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
