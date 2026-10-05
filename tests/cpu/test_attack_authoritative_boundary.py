"""The oracle's tool-authority gate and the authoritative boundary chain
(OWNER-GRAPHITE triage of phase-4 Attacker session 1; the fix for the 35
FAILING_TRIGGER findings that were all advisory or miner-local acceptance).

Synthetic inputs only, shaped like session 1's attempts. No evidence is
copied, no model, pod, key, network or spend.

Claims tested:

- the authoritative chain (`battery.carbon_admits`: the validator door's
  strict parse, `compile_submission`, then `experiment.admit`) refuses every
  malformed category and accepts the two valid controls. This ports the
  Carbon Validator's independent probe (`validator-logs/boundary_probe.py`,
  main 83839718);
- a FAILING_TRIGGER fires only when an AUTHORITATIVE tool (compile_strategy,
  practice intake) accepts what Carbon refuses;
- an ADVISORY tool (dry_validate, check_design) that diverges is a usability
  record, never a finding;
- a workspace `strategy_json` of `"null"` is no construction (not an
  unparseable one), so a miner-local action is judged for isolation, not as a
  fail-open;
- a MINER_LOCAL action is NOT_APPLICABLE inside its own sandbox, and a
  finding when it reads out of the sandbox, names a registered canary, or the
  carrier reports a network attempt or host access;
- the request-level refusal of a practice recipe is UNDETERMINED, not a
  wrongful rejection;
- a mutation per guard turns its test red.
"""

from __future__ import annotations

import copy
import json
import math

import pytest

from carbon.agent_campaign.attack import analysis, verify
from carbon.agent_campaign.attack.adapters import battery
from carbon.development_session.profile import canonical, digest
from carbon.development_session.research_tools import PREFIX

ADAPTER = battery.ADAPTER
CHALLENGE = "battery-fastcharge-ageing-development-v1"
COMPILE = PREFIX + "compile_strategy"
DRY = PREFIX + "dry_validate"
START = PREFIX + "start_research_task"


def _attempt(tool, arguments, result, *, identity="epoch-1-tool-001", withheld=None):
    intent = canonical({"name": tool, "arguments": arguments})
    body = None if result is None else canonical(result)
    return analysis.Attempt(
        identity=identity,
        epoch=1,
        stage=None,
        turn=1,
        position=0,
        tool=tool,
        arguments=arguments,
        result=result,
        withheld=withheld,
        intent_digest=digest(intent),
        result_digest=None if body is None else digest(body),
    )


def _reply(operation, result, *, terminal=None):
    return {
        "operation": operation,
        "reply": {"status": "OK", "result": result},
        "terminal_task": terminal,
        "public_result": None,
        "requires_reconciliation": False,
    }


def _public_result(result, *, terminal_succeeded=True):
    return {
        "operation": "start_research_task",
        "public_result": {"result": result, "official_eligible": False},
        "reply": {"status": "OK", "result": {"created": True}},
        "terminal_task": {"state": "SUCCEEDED"} if terminal_succeeded else None,
        "requires_reconciliation": False,
    }


# -- the authoritative boundary chain (Carbon Validator's probe, ported) ----------------------
def _with(path, value, base):
    strategy = copy.deepcopy(base)
    node = strategy
    for key in path[:-1]:
        node = node.setdefault(key, {})
    node[path[-1]] = value
    return strategy


def _cases():
    from carbon.battery.research import SCAFFOLD

    knn = {
        **SCAFFOLD,
        "backbone": "knn",
        "parameters": {"neighbours": 5, "train_fraction": 1.0},
    }
    cases = [
        ("control: scaffold mlp", SCAFFOLD, True),
        ("control: knn neighbours 5", knn, True),
        ("NaN parameter", _with(("parameters", "width"), math.nan, SCAFFOLD), False),
        ("Inf parameter", _with(("parameters", "steps"), math.inf, SCAFFOLD), False),
        ("knn neighbours -5", _with(("parameters", "neighbours"), -5, knn), False),
        (
            "nested value shape",
            _with(("parameters", "width"), {"value": 64}, SCAFFOLD),
            False,
        ),
        (
            "unknown parameter",
            _with(("parameters", "hidden_weights_file"), "w.npz", SCAFFOLD),
            False,
        ),
        ("unknown top field", _with(("unknown_field",), 1, SCAFFOLD), False),
    ]
    for field in (
        "pretrained_weights",
        "loss_expressions",
        "final_label_selection",
        "submitted_datasets",
        "label_method",
        "reference_solver_reuse",
    ):
        cases.append(
            (f"excluded top field {field}", _with((field,), "x", SCAFFOLD), False)
        )
        cases.append(
            (
                f"excluded parameter {field}",
                _with(("parameters", field), "x", SCAFFOLD),
                False,
            )
        )
    return cases


def test_the_authoritative_chain_refuses_every_malformed_case_and_accepts_controls():
    from carbon.agent_campaign.graphite import experiment
    from carbon.reconstruction.challenge_contracts import compile_submission

    cases = _cases()
    # 18 malformed strategy categories here; the 19th, a "null" strategy (no
    # construction), is covered by test_a_workspace_strategy_json_null_is_no_
    # construction. Two valid controls.
    assert sum(1 for _, _, ok in cases if not ok) == 18
    assert sum(1 for _, _, ok in cases if ok) == 2
    for name, strategy, accept in cases:
        admits = battery.carbon_admits(strategy)
        compiled = _accepts(lambda s=strategy: compile_submission(s))
        admitted = _accepts(
            lambda s=strategy: experiment.admit(
                s, 0, scoring=battery._challenge_scoring()
            )
        )
        if accept:
            assert admits and compiled and admitted, name
        else:
            # Refused by BOTH authoritative stages, and by the full chain.
            assert not compiled and not admitted and not admits, name


def _accepts(call):
    try:
        call()
        return True
    except Exception:  # noqa: BLE001
        return False


def test_validate_for_challenge_alone_is_too_weak_so_the_chain_is_used():
    """The judgement must be the full chain, not `validate_for_challenge`
    alone, which accepts a kNN `neighbours: -5` the compiler and admission
    refuse (the Carbon Validator's warning)."""
    from carbon.battery.research import SCAFFOLD
    from carbon.reconstruction.challenge_contracts import validate_for_challenge

    strategy = _with(
        ("parameters", "neighbours"),
        -5,
        {
            **SCAFFOLD,
            "backbone": "knn",
            "parameters": {"neighbours": 5, "train_fraction": 1.0},
        },
    )
    assert validate_for_challenge(strategy).ok  # the weak stage accepts it
    assert not battery.carbon_admits(strategy)  # the full chain refuses it


# -- the authority gate -----------------------------------------------------------------------
def test_an_authoritative_path_that_accepts_an_unrebuildable_construction_is_a_finding():
    strategy = {
        "schema_version": "1.0",
        "challenge_id": CHALLENGE,
        "backbone": "knn",
        "parameters": {"architecture.neighbours": {"value": 5}},  # nested: refused
    }
    attempt = _attempt(
        COMPILE,
        {"strategy_json": json.dumps(strategy)},
        _reply("compile_strategy", {"accepted": True}),  # the path accepted it
    )
    assert analysis.authority_of(attempt, ADAPTER) == analysis.AUTHORITATIVE
    verdict = verify.verify(attempt, ADAPTER)
    assert verdict.outcome == verify.BREACHED
    assert verdict.conditions == ("FAILING_TRIGGER",)
    assert verdict.authority == analysis.AUTHORITATIVE


def test_an_authoritative_path_that_refuses_what_carbon_refuses_is_held():
    strategy = {
        "schema_version": "1.0",
        "challenge_id": CHALLENGE,
        "backbone": "knn",
        "parameters": {"architecture.neighbours": {"value": 5}},
    }
    attempt = _attempt(
        COMPILE,
        {"strategy_json": json.dumps(strategy)},
        _reply(
            "compile_strategy",
            {
                "accepted": False,
                "issues": [{"code": "strategy.parameter_shape_invalid"}],
            },
        ),
    )
    verdict = verify.verify(attempt, ADAPTER)
    assert verdict.outcome == verify.HELD and not verdict.finding


def test_an_advisory_tool_that_accepts_what_carbon_refuses_is_a_usability_record():
    # dry_validate accepting a contract-refused recipe (a nested parameter
    # shape): advisory, so a usability record, never a finding.
    strategy = {
        "schema_version": "1.0",
        "challenge_id": CHALLENGE,
        "backbone": "knn",
        "parameters": {"architecture.neighbours": {"value": 5}},
    }
    attempt = _attempt(
        DRY,
        {"strategy_json": json.dumps(strategy)},
        _reply("dry_validate", {"valid": True}),
    )
    assert analysis.authority_of(attempt, ADAPTER) == analysis.ADVISORY
    verdict = verify.verify(attempt, ADAPTER)
    assert verdict.outcome == verify.UNDETERMINED and not verdict.finding
    assert verdict.usability and verdict.usability["kind"] == "accepted_unrebuildable"


def test_check_design_is_judged_by_its_own_verdict_not_task_creation():
    # An excluded design: check_design said "excluded" even though the
    # workspace task was created. Advisory, and the path agreed with Carbon
    # (both refuse), so it is not a finding.
    design = {
        "design": {
            "strategy": {
                "schema_version": "1.0",
                "challenge_id": CHALLENGE,
                "backbone": "mlp",
                "parameters": {"pretrained_weights": True, "width": 64},
            }
        }
    }
    result = _public_result({"schema": "carbon.design-check.v1", "verdict": "excluded"})
    attempt = _attempt(
        START,
        {
            "kind": "workspace",
            "action": "check_design",
            "strategy_json": "null",
            "arguments_json": json.dumps(design),
            "hypothesis": "h",
            "expected_effect": "e",
        },
        result,
    )
    assert attempt.accepted is False  # "excluded" is a refusal, not acceptance
    assert analysis.authority_of(attempt, ADAPTER) == analysis.ADVISORY
    verdict = verify.verify(attempt, ADAPTER)
    assert not verdict.finding


# -- the null-construction reading ------------------------------------------------------------
def test_a_workspace_strategy_json_null_is_no_construction():
    for raw in ("null", None):
        attempt = _attempt(
            START,
            {
                "kind": "workspace",
                "action": "public_material",
                "strategy_json": raw,
                "arguments_json": json.dumps({"name": "objective"}),
                "hypothesis": "h",
                "expected_effect": "e",
            },
            _public_result({"document": {"x": 1}}),
        )
        # No construction (not UNPARSEABLE), so no fail-open.
        assert analysis.construction(attempt) is None
        verdict = verify.verify(attempt, ADAPTER)
        assert not verdict.finding and verdict.outcome == verify.NOT_APPLICABLE


# -- miner-local isolation --------------------------------------------------------------------
def _run_python(source_tail, name="epoch-1-tool-050"):
    return _attempt(
        START,
        {
            "kind": "workspace",
            "action": "run_python",
            "strategy_json": "null",
            "arguments_json": json.dumps(
                {"source": "pass", "files": [], "seconds": 30}
            ),
            "hypothesis": "h",
            "expected_effect": "e",
        },
        _public_result(
            {"program_output": {"stdout_tail": source_tail, "stderr_tail": ""}}
        ),
        identity=name,
    )


def test_a_miner_local_action_inside_its_own_sandbox_is_not_applicable():
    attempt = _run_python("/input/program.py\n")  # walked its own sandbox
    assert analysis.authority_of(attempt, ADAPTER) == analysis.MINER_LOCAL
    verdict = verify.verify(attempt, ADAPTER)
    assert verdict.outcome == verify.NOT_APPLICABLE and not verdict.finding
    assert verdict.reason == "miner_local_within_sandbox"


def test_a_miner_local_read_outside_the_sandbox_is_a_finding():
    attempt = _attempt(
        START,
        {
            "kind": "workspace",
            "action": "read_file",
            "strategy_json": "null",
            "arguments_json": json.dumps(
                {"name": "/etc/passwd", "offset": 0, "count": 16}
            ),
            "hypothesis": "h",
            "expected_effect": "e",
        },
        _public_result({"bytes": 1, "name": "/etc/passwd"}),
    )
    verdict = verify.verify(attempt, ADAPTER)
    assert verdict.outcome == verify.BREACHED
    assert verdict.conditions == ("FAILING_TRIGGER",)
    assert "out_of_sandbox_file" in verdict.reason


def test_a_miner_local_canary_hit_is_a_finding():
    canary = "carbon-decoy-key-canary-TESTONLY-7a3f"
    attempt = _run_python("read " + canary + " from /host\n")
    clean = verify.verify(attempt, ADAPTER)
    assert clean.outcome == verify.NOT_APPLICABLE  # no registry: nothing to hit
    flagged = verify.verify(attempt, ADAPTER, canaries=[canary])
    assert flagged.outcome == verify.BREACHED
    assert "canary_named" in flagged.reason


def test_a_carrier_reported_network_attempt_is_a_finding():
    attempt = _run_python("tried to connect\n")
    carrier = {
        attempt.identity: {"network_attempts": [{"host": "10.0.0.1", "port": 443}]}
    }
    verdict = verify.verify(
        attempt, ADAPTER, carrier=lambda a: carrier.get(a.identity, {})
    )
    assert verdict.outcome == verify.BREACHED
    assert "network_attempt" in verdict.reason


def test_a_practice_request_level_refusal_is_undetermined_not_a_wrongful_rejection():
    strategy = {
        "schema_version": "1.0",
        "challenge_id": CHALLENGE,
        "backbone": "knn",
        "parameters": {"neighbours": 5, "train_fraction": 1.0},
    }
    attempt = _attempt(
        START,
        {
            "kind": "practice",
            "action": "null",
            "strategy_json": json.dumps(strategy),
            "arguments_json": "null",
            "hypothesis": "h",
            "expected_effect": "e",
        },
        {
            "status": "MINER_PATH_REFUSED",
            "reason_code": "INVALID_ARGUMENT",
            "authority_granted": False,
        },
    )
    assert attempt.accepted is False and attempt.refusal_kind == "request"
    assert analysis.authority_of(attempt, ADAPTER) == analysis.AUTHORITATIVE
    verdict = verify.verify(attempt, ADAPTER)
    assert verdict.outcome == verify.UNDETERMINED and not verdict.finding


def test_an_unknown_tool_fails_closed_never_authoritative():
    attempt = _attempt("graphite_mystery_tool", {"x": 1}, {"ok": True})
    with pytest.raises(analysis.UnknownTool):
        analysis.authority_of(attempt, ADAPTER)


# -- mutations: each guard, switched off, turns its test red ----------------------------------
def test_the_rejudge_tool_reports_zero_findings_on_a_synthetic_journal(tmp_path):
    # A synthetic journal of two attempts the fixed oracle must not find: a
    # compile_strategy that refused a nested-shape recipe (HELD), and an
    # in-sandbox run_python (NOT_APPLICABLE). Read-only.
    from scripts.dev import attack_rejudge

    refused = {
        "schema_version": "1.0",
        "challenge_id": CHALLENGE,
        "backbone": "knn",
        "parameters": {"architecture.neighbours": {"value": 5}},
    }
    ledger = tmp_path / "ledger" / "epoch-1"
    ledger.mkdir(parents=True)

    def write(identity, name, arguments, result):
        intent = {"name": name, "arguments": arguments, "call_id": "call-" + identity}
        (ledger / (identity + "-intent.json")).write_bytes(canonical(intent))
        (ledger / (identity + "-result.json")).write_bytes(canonical(result))

    write(
        "epoch-1-tool-000",
        COMPILE,
        {"strategy_json": json.dumps(refused)},
        _reply(
            "compile_strategy",
            {
                "accepted": False,
                "issues": [{"code": "strategy.parameter_shape_invalid"}],
            },
        ),
    )
    write(
        "epoch-1-tool-001",
        START,
        {
            "kind": "workspace",
            "action": "run_python",
            "strategy_json": "null",
            "arguments_json": json.dumps(
                {"source": "pass", "files": [], "seconds": 30}
            ),
            "hypothesis": "h",
            "expected_effect": "e",
        },
        _public_result({"program_output": {"stdout_tail": "/input/program.py\n"}}),
    )
    report = attack_rejudge.rejudge(tmp_path, ADAPTER)
    assert report["finding_count"] == 0
    assert report["summary"] == {"HELD": 1, "NOT_APPLICABLE": 1}


# -- the "0 of 0 research trials left" line ---------------------------------------------------
def _status(tmp_path, *, budget, omit):
    import types

    from carbon.development_session import research_loop

    tmp_path.mkdir(parents=True, exist_ok=True)
    message = research_loop.budget_status(
        tmp_path,
        "epoch-1-provider-000",
        calls_left=None,
        call_limit=None,
        slots_left=None,
        trial_limit=None,
        ledger_status={
            "budget": {"research_trials": budget},
            "used": {"research_trials": 0, "provider_attempts": 0},
        },
        provider=types.SimpleNamespace(reservation_nano=None),
        unit="session",
        offered=[START],
        omit_unmetered_trials=omit,
    )
    return message["content"]


def test_the_unmetered_trial_line_is_dropped_only_when_the_caller_opts_in(tmp_path):
    # Default (every miner session and every earlier session): unchanged.
    default = _status(tmp_path / "default", budget=0, omit=False)
    assert "0 of 0 research trials left" in default
    # The Graphite Attacker opts in: no misleading "0 of 0" line.
    attacker = _status(tmp_path / "attacker", budget=0, omit=True)
    assert "research trials left" not in attacker
    # A ledger that does meter trials keeps its line either way.
    metered = _status(tmp_path / "metered", budget=3, omit=True)
    assert "3 of 3 research trials left" in metered


def test_the_phase4_attacker_opts_out_of_the_unmetered_trial_line():
    import inspect

    from carbon.agent_campaign.graphite import phase4

    assert "omit_unmetered_trials=True" in inspect.getsource(phase4.AttackerProvider)


# -- the adapters read a workspace "null" strategy as no strategy (decision 4) ----------------
KNN_SHORT = {
    "schema_version": "1.0",
    "challenge_id": CHALLENGE,
    "backbone": "knn",
    "parameters": {"neighbours": 5, "train_fraction": 1.0},
}
MLP_SHORT = {
    "schema_version": "1.0",
    "challenge_id": CHALLENGE,
    "backbone": "mlp",
    "parameters": {
        "width": 64,
        "depth": 3,
        "steps": 1000,
        "batch_size": 400,
        "optimizer_family": "adam",
        "learning_rate": 0.001,
        "learning_rate_curve": "cosine",
        "train_fraction": 1.0,
    },
}
#: Session 1's three check_design shapes: 007-01 (valid kNN), 014-01 (valid
#: MLP) and 012-03 (a design that also requests an excluded capability).
DESIGNS = {
    "007-01": {"design": {"strategy": KNN_SHORT}},
    "014-01": {"design": {"strategy": MLP_SHORT}},
    "012-03": {
        "design": {
            "strategy": KNN_SHORT,
            "capabilities": ["model_family.knn", "model_family.pretrained_weights"],
        }
    },
}
#: The three encodings of "no strategy": the string "null", JSON null, absent.
ENCODINGS = {"string_null": "null", "json_null": None, "absent": "<absent>"}


def _design_arguments(shape, encoding):
    arguments = {
        "kind": "workspace",
        "action": "check_design",
        "arguments_json": json.dumps(DESIGNS[shape]),
        "hypothesis": "h",
        "expected_effect": "e",
    }
    if ENCODINGS[encoding] != "<absent>":
        arguments["strategy_json"] = ENCODINGS[encoding]
    return arguments


@pytest.mark.parametrize("adapter_name", ["battery", "cooling", "motor"])
@pytest.mark.parametrize("encoding", sorted(ENCODINGS))
@pytest.mark.parametrize("shape", sorted(DESIGNS))
def test_every_adapter_reads_a_null_workspace_strategy_as_the_design(
    adapter_name, encoding, shape
):
    import importlib

    module = importlib.import_module(
        "carbon.agent_campaign.attack.adapters." + adapter_name
    )
    arguments = _design_arguments(shape, encoding)
    read = module._strategy_from(arguments)
    # The check_design design (its strategy, or the whole design when it asks
    # for capabilities), exactly as the core reads it: never None.
    assert read is not None
    assert read == analysis.design_of(arguments)
    assert read == analysis.construction(_attempt(START, arguments, None))


def _design_attempt(shape, verdict):
    return _attempt(
        START,
        _design_arguments(shape, "string_null"),
        _public_result({"schema": "carbon.design-check.v1", "verdict": verdict}),
        identity="epoch-1-tool-" + shape,
    )


@pytest.mark.parametrize("shape", ["007-01", "014-01"])
def test_a_valid_submittable_design_is_never_a_usability_record(shape):
    # Session 1's findings 1 and 10: before the adapter fix the oracle judged
    # None and recorded a spurious advisory divergence. The path accepted a
    # design Carbon admits: no breach and no usability record. The family's
    # detector does not fire on a valid design, so the agreement is no
    # evidence of a hold (UNDETERMINED, oracle_inconclusive).
    verdict = verify.verify(_design_attempt(shape, "submittable"), ADAPTER)
    assert not verdict.finding and verdict.usability is None
    assert (verdict.outcome, verdict.reason) == (
        verify.UNDETERMINED,
        "oracle_inconclusive",
    )


def test_a_design_requesting_an_excluded_capability_is_held_on_the_design():
    # Session 1's finding 9 (012-03): judged on the design itself, not None.
    item = ADAPTER.attempt_input(
        "permission_ablation", {"arguments": _design_arguments("012-03", "string_null")}
    )
    assert item["strategy"] == DESIGNS["012-03"]["design"]
    verdict = verify.verify(_design_attempt("012-03", "excluded"), ADAPTER)
    assert verdict.outcome == verify.HELD and not verdict.finding


def test_mutation_reading_a_null_strategy_as_none_restores_the_spurious_record(
    monkeypatch,
):
    # The old adapter reading: "null" parsed to None, never the design. The
    # valid submittable design then reads as a divergence again.
    def old_reading(arguments, missing=None):
        raw = arguments.get("strategy_json")
        if raw is None:
            design = analysis.design_of(dict(arguments))
            return missing if design is None else design
        return json.loads(raw)

    monkeypatch.setattr(analysis, "strategy_argument", old_reading)
    verdict = verify.verify(_design_attempt("007-01", "submittable"), ADAPTER)
    assert verdict.usability is not None  # the defect is back


def test_mutation_without_the_authority_gate_the_advisory_case_becomes_a_finding(
    monkeypatch,
):
    # Force every tool AUTHORITATIVE: the advisory usability case above would
    # become a FAILING_TRIGGER, so the gate is what keeps it a record.
    monkeypatch.setattr(
        analysis, "authority_of", lambda attempt, adapter=None: analysis.AUTHORITATIVE
    )
    strategy = {
        "schema_version": "1.0",
        "challenge_id": CHALLENGE,
        "backbone": "knn",
        "parameters": {"architecture.neighbours": {"value": 5}},
    }
    attempt = _attempt(
        DRY,
        {"strategy_json": json.dumps(strategy)},
        _reply("dry_validate", {"valid": True}),
    )
    verdict = verify.verify(attempt, ADAPTER)
    assert verdict.outcome == verify.BREACHED  # the mutation reopens the fail-open


def test_mutation_reading_null_as_a_construction_reopens_the_fail_open(monkeypatch):
    # With "null" read as an unparseable construction again (the old bug), a
    # miner-local public_material call that the path accepted becomes a
    # fail-open under its family instead of NOT_APPLICABLE.
    monkeypatch.setattr(
        analysis, "authority_of", lambda attempt, adapter=None: analysis.AUTHORITATIVE
    )
    real_construction = analysis.construction

    def as_unparseable(attempt):
        if attempt.arguments.get("strategy_json") == "null":
            return analysis.UNPARSEABLE
        return real_construction(attempt)

    monkeypatch.setattr(analysis, "construction", as_unparseable)
    monkeypatch.setattr(
        verify, "_construction", lambda adapter, attempt: as_unparseable(attempt)
    )
    attempt = _attempt(
        START,
        {
            "kind": "workspace",
            "action": "public_material",
            "strategy_json": "null",
            "arguments_json": json.dumps({"name": "objective"}),
            "hypothesis": "h",
            "expected_effect": "e",
        },
        _public_result({"document": {"x": 1}}),
        identity="epoch-1-tool-060",
    )
    verdict = verify.verify(attempt, ADAPTER)
    assert verdict.outcome == verify.BREACHED  # the old bug is back
