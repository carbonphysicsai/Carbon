"""The attack engine's session reading (OWNER-GRAPHITE-ATTACKER-01, slice AT-C).

Claims tested, with synthetic journals, a stub adapter and one scripted
phase-3 session (no live model, pod, key, network or spend):

- every journalled tool call is an attempt, in run order, under exactly the
  identity `research_loop.tool_identity` names: v2 turns with several calls
  (`-KK`) and staged sessions read one way; a non-canonical or misfiled
  identity is refused, never guessed;
- protected material is checked on every read: a request or result that
  names it is withheld (no content carried), and a result that names it is
  marked as an exposure;
- a timeout, a FAILED_INFRA task, a missing result or an unresolved dispatch
  is infrastructure, never an answer;
- attempts map to the adapter's families through the adapter, a family's own
  matcher, or the neutral default; an attempt no family takes is reported
  UNASSIGNED.

The stub adapter below is the synthetic second Challenge's shape at this
slice's seam; the engine's own adapter registry is slice AT-A's.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

import pytest

from carbon.agent_campaign.attack import analysis
from carbon.agent_campaign.graphite import tools as toolbox
from carbon.development_session.profile import canonical
from carbon.development_session.research_loop import tool_identity
from carbon.development_session.research_tools import PREFIX

DRY = PREFIX + "dry_validate"
INFO = PREFIX + "get_challenge_info"
START = PREFIX + "start_research_task"
RESULT = PREFIX + "get_research_result"
GOOD = {"schema_version": "1.0", "challenge_id": "synthetic", "fins": 12}
FORBIDDEN = {**GOOD, "pretrained_weights": "https://x/w.bin"}
CHECKS = (
    "baseline_and_permission_ablation",
    "artifact_and_dependency_attacks",
    "adaptive_feedback_and_state_attacks",
    "score_exploitation_and_tail_failures",
    "resource_and_failure_accounting",
    "construction_evaluation_isolation",
    "reconstruction_and_recipient_rebuild",
    "fresh_attack_confirmation",
)
MISSING = object()


# -- a stub adapter: a synthetic second Challenge at this slice's seam ---------------------
@dataclass(frozen=True)
class StubFamily:
    name: str
    check: str
    matches: object = None


@dataclass(frozen=True)
class Seam:
    name: str
    reason: str = "participant code: a declared seam, NOT_RUN"


class Unrebuildable(ValueError):
    """The adapter's typed refusal (its class name is what `verify` reads)."""

    def __init__(self, code, issues=()):
        super().__init__(code)
        self.code, self.issues = code, tuple(issues)


@dataclass(frozen=True)
class Rebuilt:
    record: dict


@dataclass(frozen=True)
class OracleResult:
    outcome: str
    condition: str | None = None
    near_miss: bool = False
    evidence: object = None


def _forbidden(construction):
    return "pretrained_weights" in construction


class StubAdapter:
    """A synthetic heat-sink Challenge at Level 0: a construction with a
    `pretrained_weights` field is not rebuildable; the oracle holds
    everything unless told otherwise. Every call is recorded."""

    challenge_id = "synthetic-heat-sink-v1"
    level = 0
    contract_digest = "sha256:" + "5" * 64

    def __init__(self, families=None, *, oracle=None, refuse=None, raises=False):
        self._families = families or tuple(
            StubFamily(check.split("_")[0] + "_family", check) for check in CHECKS
        )
        self._oracle = oracle or (lambda family, attempt: OracleResult("HELD"))
        self._refuse = refuse or (
            lambda c: "pretrained_payload_refused" if _forbidden(c) else None
        )
        self.raises = raises
        self.oracle_calls = []
        self.rebuild_calls = []
        self.controls_calls = []

    def families(self):
        return self._families

    def controls(self, split):
        self.controls_calls.append(split)
        return ()

    def oracle(self, family, attempt):
        self.oracle_calls.append((family, attempt.identity))
        return self._oracle(family, attempt)

    def rebuild(self, construction):
        self.rebuild_calls.append(construction)
        code = self._refuse(construction)
        if code is not None:
            refusal = Unrebuildable(code, [(code, "parameters")])
            if self.raises:
                raise refusal
            return refusal
        return Rebuilt({"recipe": construction, "recipe_digest": "sha256:" + "7" * 64})

    def level_families(self):
        return (Seam("participant_code"),)


# -- journals ---------------------------------------------------------------------------------
def path_reply(operation, result=None, status="OK", terminal=None, **extra):
    """A dispatched result in the miner path's shape."""
    return {
        "protocol": "carbon_research_v2",
        "operation": operation,
        "reply": {"status": status, "result": result or {}},
        "terminal_task": terminal,
        "public_result": None,
        "requires_reconciliation": False,
        **extra,
    }


def dry(strategy):
    return {"strategy_json": json.dumps(strategy)}


def write_call(
    run_dir, name, arguments, result=MISSING, *, epoch=1, turn=0, position=0, stage=None
):
    """Journal one tool call exactly as `research_loop.run_epoch` does."""
    folder = run_dir / "ledger" / f"epoch-{epoch}"
    if stage is not None:
        folder = folder / stage
    folder.mkdir(parents=True, exist_ok=True)
    identity = tool_identity(epoch, turn, position, stage)
    intent = {"name": name, "arguments": arguments, "call_id": "call-" + identity}
    (folder / (identity + "-intent.json")).write_bytes(canonical(intent))
    if result is not MISSING:
        (folder / (identity + "-result.json")).write_bytes(canonical(result))
    return identity


def one(tmp_path, name, arguments, result=MISSING):
    write_call(tmp_path, name, arguments, result)
    (found,) = analysis.attempts(tmp_path)
    return found


# -- reading the journal ----------------------------------------------------------------------
def test_every_call_is_an_attempt_in_run_order_under_its_tool_identity(tmp_path):
    accepted = path_reply("dry_validate", {"valid": True})
    write_call(tmp_path, INFO, {}, path_reply("get_challenge_info"), turn=1)
    write_call(tmp_path, DRY, dry(GOOD), accepted, turn=0, position=0)
    write_call(tmp_path, DRY, dry(FORBIDDEN), accepted, turn=0, position=2)
    write_call(tmp_path, DRY, dry(GOOD), accepted, turn=0, position=1)
    write_call(tmp_path, INFO, {}, path_reply("get_challenge_info"), stage="attack")
    write_call(tmp_path, INFO, {}, path_reply("get_challenge_info"), epoch=2, turn=3)
    found = analysis.attempts(tmp_path)
    assert [a.identity for a in found] == [
        "epoch-1-tool-000",
        "epoch-1-tool-000-01",
        "epoch-1-tool-000-02",
        "epoch-1-tool-001",
        "epoch-1-attack-tool-000",
        "epoch-2-tool-003",
    ]
    for a in found:
        assert tool_identity(a.epoch, a.turn, a.position, a.stage) == a.identity
    assert found[4].stage == "attack" and found[0].stage is None
    assert found[2].arguments == dry(FORBIDDEN) and found[2].accepted is True
    assert analysis.attempts(tmp_path, stage=None, epoch=1) == found[:4]
    assert analysis.attempts(tmp_path, stage="attack") == [found[4]]
    # The run directory and its ledger root read the same.
    assert analysis.attempts(tmp_path / "ledger") == found


@pytest.mark.parametrize(
    "identity",
    ["epoch-1-tool-000-00", "epoch-1-tool-0", "epoch-1-tool-001-1", "epoch-1-Tool-001"],
)
def test_a_non_canonical_identity_is_refused_never_guessed(tmp_path, identity):
    folder = tmp_path / "ledger" / "epoch-1"
    folder.mkdir(parents=True)
    (folder / (identity + "-intent.json")).write_bytes(canonical({"name": INFO}))
    with pytest.raises(ValueError, match="journal_identity"):
        analysis.attempts(tmp_path)


def test_a_misfiled_identity_is_refused(tmp_path):
    folder = tmp_path / "ledger" / "epoch-1"
    folder.mkdir(parents=True)
    identity = tool_identity(1, 0, 0, "attack")
    (folder / (identity + "-intent.json")).write_bytes(canonical({"name": INFO}))
    with pytest.raises(ValueError, match="journal_identity_misfiled"):
        analysis.attempts(tmp_path)


def test_other_journal_files_are_not_attempts(tmp_path):
    write_call(tmp_path, INFO, {}, path_reply("get_challenge_info"))
    folder = tmp_path / "ledger" / "epoch-1"
    (folder / "epoch-1-provider-000-turn.json").write_bytes(b"{}")
    (folder / "epoch-1-provider-000-calls.json").write_bytes(b"{}")
    (folder / "plan.json").write_bytes(b"{}")
    assert [a.identity for a in analysis.attempts(tmp_path)] == ["epoch-1-tool-000"]


def test_a_scripted_v2_session_journal_reads_as_its_calls(tmp_path):
    """A real phase-3 session (scripted model, recording miner tools): a turn
    with several calls journals `-KK` identities, and every one reads back
    with its arguments and result."""
    from graphite_fixtures import RecordingMinerTools
    from graphite_phase3_fixtures import ScriptedPods, run_id, session, text, tool

    from carbon.agent_campaign.graphite.model import tools

    answers = {DRY: path_reply("dry_validate", {"valid": True})}
    miner = RecordingMinerTools(answers)
    script = [
        tools(tool(DRY, dry(GOOD)), tool(DRY, dry(FORBIDDEN)), tool(INFO, {})),
        tool(INFO, {}),
        text("done"),
    ]
    result, graphite, _ = session(tmp_path, script, ScriptedPods(), miner=miner)
    assert result["provider_state"] == "succeeded"
    found = analysis.attempts(graphite._dir(run_id()))
    assert [(a.identity, a.tool) for a in found] == [
        ("epoch-1-tool-000", DRY),
        ("epoch-1-tool-000-01", DRY),
        ("epoch-1-tool-000-02", INFO),
        ("epoch-1-tool-001", INFO),
    ]
    assert [c[2] for c in miner.calls] == [a.identity for a in found]
    assert found[1].arguments == dry(FORBIDDEN)
    assert found[1].accepted is True and found[1].refused_by == "path"
    assert analysis.construction(found[1]) == FORBIDDEN


# -- protected material -----------------------------------------------------------------------
def test_a_request_naming_protected_material_is_withheld_and_graphites(tmp_path):
    asked = {"strategy_json": json.dumps({**GOOD, "note": "the official_seed"})}
    refusal = toolbox.refusal(toolbox.REFUSED_PROTECTED, "protected_material_requested")
    found = one(tmp_path, DRY, asked, refusal)
    assert toolbox.protected(asked)
    assert found.withheld == analysis.WITHHELD_REQUEST
    assert found.arguments == {} and not toolbox.protected(found.result)
    assert found.refused_by == "graphite"
    assert analysis.construction(found) is None


def test_a_withheld_result_is_an_exposure_marker(tmp_path):
    refusal = toolbox.refusal(toolbox.REFUSED_RESULT, "protected_material_in_result")
    found = one(tmp_path, INFO, {}, refusal)
    assert found.withheld == analysis.WITHHELD_RESULT
    assert found.infra is None


def test_protected_material_in_the_journal_is_never_carried(tmp_path):
    leaked = path_reply("get_challenge_info", {"hidden_case": "c-17"})
    found = one(tmp_path, INFO, {}, leaked)
    assert found.withheld == analysis.WITHHELD_JOURNAL
    assert found.result is None and found.arguments == {}
    assert found.result_digest is not None  # bound by digest, never read on
    assert not toolbox.protected(found.record())


# -- answers and infrastructure ---------------------------------------------------------------
@pytest.mark.parametrize(
    ("result", "accepted"),
    [
        (path_reply("dry_validate", {"valid": True}), True),
        (path_reply("dry_validate", {"valid": False}), False),
        (path_reply("dry_validate", status="ERROR"), False),
        ({"status": "REJECTED_BEFORE_DISPATCH", "dispatched": False}, False),
        (path_reply("start_research_task"), True),
        (path_reply("get_research_result", terminal={"state": "SUCCEEDED"}), True),
        (path_reply("get_challenge_info"), None),
        # Phase-3 proposal feedback: it ran on a pod, so the path accepted it.
        ({"status": "SCORED", "proposal_id": "p-1", "scored": True}, True),
        ({"status": "CANDIDATE_FAILED", "reason_code": "program"}, True),
        ({"status": "REFUSED_UNREBUILDABLE", "reason_code": "x"}, False),
    ],
)
def test_the_path_answer_is_read_plainly_or_not_at_all(tmp_path, result, accepted):
    assert one(tmp_path, DRY, dry(GOOD), result).accepted is accepted


def _loop_refusals():
    from carbon.development_session import research_loop as loop

    return [
        loop.rejected_call(
            loop.ARGUMENTS_INVALID, "strategy_json", "not an object", "send one"
        ),
        loop.truncated_call({"reason": "max_output_tokens", "max_output_tokens": 9}),
        {
            "status": "UNAVAILABLE",
            "reason": "epoch research trial ceiling; select retained recipe or stop",
            "authority_granted": False,
        },
    ]


@pytest.mark.parametrize("index", range(3))
def test_the_research_loops_own_refusals_are_graphites(tmp_path, index):
    """The loop's `rejected_call` records (malformed or truncated calls) and
    its trial ceiling never reached the path."""
    found = one(tmp_path, DRY, dry(FORBIDDEN), _loop_refusals()[index])
    assert found.refused_by == "graphite" and found.infra is None


@pytest.mark.parametrize(
    "result",
    [
        # The miner research tools' own contract refusal: the path's.
        {
            "status": "REJECTED_BEFORE_DISPATCH",
            "reason": "contract_incompatibility",
            "detail": "Request does not satisfy the disclosed contract.",
            "authority_granted": False,
        },
        {"operation": "dry_validate", "status": "UNAVAILABLE", "reason": "x"},
        path_reply("dry_validate", status="REFUSED"),
    ],
)
def test_the_paths_own_refusals_stay_the_paths(tmp_path, result):
    found = one(tmp_path, DRY, dry(FORBIDDEN), result)
    assert found.refused_by == "path" and found.accepted is False


def test_an_agent_echo_of_protected_words_is_marked_apart(tmp_path):
    """A finish summary naming a protected case comes back from the loop
    itself: the agent named it, the path exposed nothing."""
    words = {"summary": "the hidden_case answer"}
    found = one(tmp_path, "graphite_finish", words, {"status": "PLANNED", **words})
    assert found.withheld == analysis.WITHHELD_ECHO
    assert found.arguments == {} and found.result is None
    assert not toolbox.protected(found.record())


@pytest.mark.parametrize(
    ("result", "infra"),
    [
        (MISSING, "result_missing"),
        (
            path_reply("start_research_task", requires_reconciliation=True),
            "dispatch_unresolved",
        ),
        (
            path_reply("get_research_result", terminal={"state": "FAILED_INFRA"}),
            "FAILED_INFRA",
        ),
        ({"status": "FAILED_INFRA", "reason_code": "timeout"}, "FAILED_INFRA"),
        (path_reply("get_research_result", {"state": "TIMED_OUT"}), "TIMED_OUT"),
        (path_reply("get_research_result", terminal={"state": "SUCCEEDED"}), None),
    ],
)
def test_infrastructure_is_never_an_answer(tmp_path, result, infra):
    found = one(tmp_path, RESULT, {"task_id": "t", "poll_sequence": 0}, result)
    assert found.infra == infra


# -- families ---------------------------------------------------------------------------------
def _practice(strategy=GOOD):
    return {
        "kind": "practice",
        "strategy_json": json.dumps(strategy),
        "action": None,
        "arguments_json": None,
        "hypothesis": "h",
        "expected_effect": "e",
    }


def _code():
    return {
        "kind": "workspace",
        "strategy_json": None,
        "action": "run_python",
        "arguments_json": json.dumps({"source": "print(1)", "files": []}),
        "hypothesis": "h",
        "expected_effect": "e",
    }


def test_the_neutral_default_maps_operations_to_the_shared_checks(tmp_path):
    calls = [
        (DRY, dry(GOOD)),
        (INFO, {}),
        (START, _practice()),
        (START, _code()),
        (RESULT, {"task_id": "t", "poll_sequence": 0}),
        (PREFIX + "cancel_research_task", {"task_id": "t"}),
        ("graphite_unknown_tool", {}),
    ]
    for turn, (name, arguments) in enumerate(calls):
        write_call(tmp_path, name, arguments, path_reply("x"), turn=turn)
    adapter = StubAdapter()
    mapped = analysis.map_to_families(analysis.attempts(tmp_path), adapter)
    by_family = {k: [a.turn for a in v] for k, v in mapped.items() if v}
    assert by_family == {
        "artifact_family": [0],
        "construction_family": [1, 3],
        "adaptive_family": [2, 4],
        "resource_family": [5],
        analysis.UNASSIGNED: [6],
    }
    # Every family is present, attempted or not.
    assert set(mapped) == {f.name for f in adapter.families()} | {analysis.UNASSIGNED}
    assert analysis.is_code_run(mapped["construction_family"][1])


def test_the_adapter_and_a_familys_matcher_decide_before_the_default(tmp_path):
    write_call(tmp_path, DRY, dry(GOOD), path_reply("dry_validate"))
    (found,) = analysis.attempts(tmp_path)
    families = (
        StubFamily("recipe_surface", "artifact_and_dependency_attacks"),
        StubFamily(
            "rebuild_identity",
            "reconstruction_and_recipient_rebuild",
            matches=lambda a: a.operation == "dry_validate",
        ),
    )
    assert analysis.family_of(found, StubAdapter(families)) == "rebuild_identity"

    class Own(StubAdapter):
        def family_of(self, attempt):
            return "recipe_surface"

    assert analysis.family_of(found, Own(families)) == "recipe_surface"

    class Unknown(StubAdapter):
        def family_of(self, attempt):
            return "not_a_family"

    with pytest.raises(ValueError, match="adapter_named_an_unknown_family"):
        analysis.family_of(found, Unknown(families))


def test_constructions_parse_or_are_marked_unparseable(tmp_path):
    write_call(tmp_path, DRY, {"strategy_json": "{not json"}, path_reply("x"))
    write_call(tmp_path, DRY, {"strategy_json": "[1, 2]"}, path_reply("x"), turn=1)
    write_call(tmp_path, START, _code(), path_reply("x"), turn=2)
    first, second, third = analysis.attempts(tmp_path)
    assert analysis.construction(first) is analysis.UNPARSEABLE
    assert analysis.construction(second) is analysis.UNPARSEABLE
    assert analysis.construction(third) is None


def test_family_names_read_every_family_shape():
    from carbon.battery import track_a

    assert analysis.family_name(track_a.FAMILIES[0]) == "recipe_surface"
    assert (
        analysis.family_check(track_a.FAMILIES[0]) == "artifact_and_dependency_attacks"
    )
    assert analysis.family_name({"name": "x"}) == "x"
    assert analysis.family_name("y") == "y"
    with pytest.raises(ValueError, match="family_without_a_name"):
        analysis.family_name(object())
