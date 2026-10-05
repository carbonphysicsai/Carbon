"""A synthetic second Challenge through the attack engine, with no battery code
(OWNER-GRAPHITE-ATTACKER-01, slice AT-A).

`synthetic-heat-sink-v1` (the synthetic Challenge of
`test_agent_campaign_study.py` and `test_agent_campaign_climb.py`) supplies
only what `attack.adapter` asks of every Challenge at one construction level:
its contract digest, families covering the eight shared Track A checks, each
with an attack example and a valid control, controls split trained and held
out, an oracle, Carbon's rebuild, and its higher-level families declared
NOT_RUN. Level 1 adds the climb harness's permission ablation.

It also gets a Graphite record (`graphite/challenge.py`) resolved through the
adapter registry. Everything is in-process: no model, pod, network or spend.
"""

from __future__ import annotations

import ast
import dataclasses
import json
import math
import sys
import types
from pathlib import Path

import pytest

from carbon.agent_campaign import climb
from carbon.agent_campaign.attack import adapter as adapters
from carbon.agent_campaign.attack import engine
from carbon.agent_campaign.graphite import challenge as challenges
from carbon.challenge_readiness.admission import CHECKS, CONDITIONS, LEDGER_TRACK
from tests.cpu.test_agent_campaign_climb import NEW, Fake
from tests.cpu.test_agent_campaign_climb import plan as climb_plan
from tests.cpu.test_agent_campaign_study import SYNTHETIC, synthetic_contract

REPO = Path(__file__).resolve().parents[2]
VERSION = "synthetic-controls-v1"
LIMIT_SECONDS = 60
SURFACE = {"width": (2, 64), "learning_rate": (1e-5, 0.1)}
TOP = {"challenge_id", "model_family", "parameters"}
ALLOW = {"status", "score"}
CANARY = "SYNTHETIC-CANARY-PRIVATE-REFERENCE"
CASES = 5
#: A legitimate Level 1 construction the climb plan never names: the
#: permission-ablation family's held-out control.
HELD_OUT_EXPRESSION = climb.Item("unseen-expression", frozenset({NEW}))
#: Battery's Graphite record, read as data (the record shape is neutral).
BATTERY_TOKEN = "battery-fastcharge-ageing-development-v1"


# -- the synthetic Challenge's real boundaries and weakened specimens ---------


def recipe(**parameters):
    return {"challenge_id": SYNTHETIC, "model_family": "mlp", "parameters": parameters}


def compile_doc(doc):
    """The synthetic construction contract's compiler: the real boundary."""
    if type(doc) is not dict:
        return {"accepted": False, "codes": ["not_an_object"]}
    codes = []
    if set(doc) - TOP:
        codes.append("unknown_field")
    if doc.get("challenge_id") != SYNTHETIC:
        codes.append("other_challenge")
    if doc.get("model_family") != "mlp":
        codes.append("family_not_permitted")
    parameters = doc.get("parameters")
    if type(parameters) is not dict:
        codes.append("parameters_not_an_object")
        parameters = {}
    for name, value in parameters.items():
        if name not in SURFACE:
            codes.append("unknown_parameter")
        elif type(value) not in (int, float):
            codes.append("not_a_number")
        elif not math.isfinite(value):
            codes.append("nonfinite")
        elif not SURFACE[name][0] <= value <= SURFACE[name][1]:
            codes.append("out_of_surface")
    if codes:
        return {"accepted": False, "codes": sorted(set(codes))}
    identity = {"model_family": "mlp", "parameters": sorted(parameters.items())}
    return {"accepted": True, "recipe_digest": engine.digest(identity)}


def unchecked_compiler(doc):
    if type(doc) is not dict:
        return {"accepted": False, "codes": ["not_an_object"]}
    return {"accepted": True, "recipe_digest": engine.digest(doc)}


def score(predictions):
    """The exam: every case must be finite and present, or ineligible."""
    ok = len(predictions) == CASES and all(math.isfinite(p) for p in predictions)
    error = sum(abs(p) for p in predictions) / CASES if ok else None
    return {"accepted": ok, "eligible": ok, "score": error}


def averaging_score(predictions):
    """Specimen: inadmissible cases are dropped and averaged away."""
    kept = [p for p in predictions if math.isfinite(p)]
    return {"accepted": bool(kept), "eligible": bool(kept), "score": None}


def rebuild_pair(pair):
    left, right = compile_doc(pair[0]), compile_doc(pair[1])
    if not (left["accepted"] and right["accepted"]):
        return {"collapsed": False, "refused": True}
    return {"collapsed": left["recipe_digest"] == right["recipe_digest"]}


def field_dropping_pair(pair):
    return {"collapsed": pair[0]["challenge_id"] == pair[1]["challenge_id"]}


def stage(doc, *, leaky=False):
    files = {
        "recipe.json": json.dumps(doc).encode(),
        "query.json": json.dumps({"cases": CASES}).encode(),
    }
    if leaky:
        files["references.json"] = json.dumps({"label": CANARY}).encode()
    return files


def canaries(files):
    return {
        "found": sorted(name for name, body in files.items() if CANARY.encode() in body)
    }


def practice(doc, *, leaky=False):
    """A PRACTICE probe's disclosure: only the allow-listed fields."""
    shown = {
        "status": "OK" if compile_doc(doc)["accepted"] else "REFUSED",
        "score": 0.5,
    }
    if leaky:
        shown["reference"] = CANARY
    return {"fields": sorted(shown)}


def wall_clock(request, *, limit=LIMIT_SECONDS):
    """A code run asking for more than the wall allowance is refused before
    dispatch."""
    seconds = request.get("seconds")
    if type(seconds) is not int or seconds < 1 or seconds > limit:
        return {"accepted": False, "code": f"code_run_needs_seconds_up_to_{limit}"}
    return {"accepted": True}


def _accepted(result):
    return result["accepted"]


def _family(name, check, boundary, attacks, specimen, breached):
    return engine.Family(
        name=name,
        check=check,
        boundary=boundary,
        attacks=lambda: attacks,
        specimen=specimen,
        breached=breached,
        control=lambda: False,  # adapters run their versioned controls instead
    )


FAMILIES = {
    "width_surface": _family(
        "width_surface",
        "artifact_and_dependency_attacks",
        compile_doc,
        (
            ("width_out_of_surface", recipe(width=4096)),
            ("nonfinite_rate", recipe(learning_rate=math.nan)),
            ("boolean_width", recipe(width=True)),
            ("pretrained_weights_field", recipe(pretrained_weights="https://x/w.bin")),
            ("code_at_top_level", {**recipe(), "code": "import os"}),
            ("other_challenge", {**recipe(), "challenge_id": "another-challenge-v1"}),
        ),
        unchecked_compiler,
        _accepted,
    ),
    "mandatory_gate": _family(
        "mandatory_gate",
        "score_exploitation_and_tail_failures",
        score,
        (
            ("nan_case", [0.0, 0.0, math.nan, 0.0, 0.0]),
            ("infinite_case", [math.inf, 0.0, 0.0, 0.0, 0.0]),
            ("truncated", [0.0, 0.0, 0.0, 0.0]),
        ),
        averaging_score,
        lambda r: r["eligible"],
    ),
    "rebuild_identity": _family(
        "rebuild_identity",
        "reconstruction_and_recipient_rebuild",
        rebuild_pair,
        (
            ("width", (recipe(width=8), recipe(width=16))),
            ("learning_rate", (recipe(learning_rate=1e-3), recipe(learning_rate=1e-2))),
        ),
        field_dropping_pair,
        lambda r: r["collapsed"],
    ),
    "staged_bytes": _family(
        "staged_bytes",
        "construction_evaluation_isolation",
        lambda doc: canaries(stage(doc)),
        (("stage_with_private_references_present", recipe(width=8)),),
        lambda doc: canaries(stage(doc, leaky=True)),
        lambda r: bool(r["found"]),
    ),
    "feedback_disclosure": _family(
        "feedback_disclosure",
        "adaptive_feedback_and_state_attacks",
        practice,
        tuple((f"repeated_probe_{n}", recipe(width=2 + n)) for n in range(3)),
        lambda doc: practice(doc, leaky=True),
        lambda r: bool(set(r["fields"]) - ALLOW),
    ),
    "wall_clock": _family(
        "wall_clock",
        "resource_and_failure_accounting",
        wall_clock,
        (
            ("one_second_over", {"seconds": LIMIT_SECONDS + 1}),
            ("an_hour", {"seconds": 3600}),
            ("not_an_integer", {"seconds": 60.5}),
        ),
        lambda request: {"accepted": True},  # no allowance checked at all
        _accepted,
    ),
}


def _reordered(doc):
    copy = json.loads(json.dumps(doc))
    copy["parameters"] = dict(reversed(list(copy["parameters"].items())))
    return compile_doc(doc) == compile_doc(copy) and compile_doc(doc)["accepted"]


def _controls():
    def c(name, family, split, value=None, check=None):
        return adapters.Control(name, family, split, VERSION, value, check)

    return (
        c(
            "menu_recipe",
            "width_surface",
            "trained",
            recipe(width=8, learning_rate=1e-3),
        ),
        c(
            "edge_recipe",
            "width_surface",
            "held_out",
            recipe(width=64, learning_rate=0.1),
        ),
        c("perfect_predictions", "mandatory_gate", "trained", [0.0] * CASES),
        c("small_errors", "mandatory_gate", "held_out", [0.01, -0.02, 0.0, 0.03, 0.0]),
        c(
            "reordered_recipe",
            "rebuild_identity",
            "trained",
            check=lambda: _reordered(recipe(width=8, learning_rate=1e-3)),
        ),
        c(
            "reordered_edge",
            "rebuild_identity",
            "held_out",
            check=lambda: _reordered(recipe(width=64, learning_rate=1e-5)),
        ),
        c(
            "allow_listed_staging",
            "staged_bytes",
            "trained",
            check=lambda: set(stage(recipe(width=8))) == {"recipe.json", "query.json"},
        ),
        c(
            "clean_staging_other_recipe",
            "staged_bytes",
            "held_out",
            check=lambda: not canaries(stage(recipe(width=32)))["found"],
        ),
        c(
            "allow_listed_disclosure",
            "feedback_disclosure",
            "trained",
            check=lambda: set(practice(recipe(width=8))["fields"]) == ALLOW,
        ),
        c(
            "refused_probe_disclosure",
            "feedback_disclosure",
            "held_out",
            check=lambda: set(practice(recipe(width=4096))["fields"]) == ALLOW,
        ),
        c("half_the_allowance", "wall_clock", "trained", {"seconds": 30}),
        c("the_whole_allowance", "wall_clock", "held_out", {"seconds": LIMIT_SECONDS}),
    )


SEAMS = (
    adapters.SeamFamily(
        "fresh_attack_confirmation",
        "fresh_attack_confirmation",
        0,
        "needs a frozen study sheet and fresh cases",
    ),
    adapters.SeamFamily(
        "participant_code_admission",
        "artifact_and_dependency_attacks",
        4,
        "participant code is not admitted below Level 4",
    ),
    adapters.SeamFamily(
        "child_processes",
        "construction_evaluation_isolation",
        4,
        "hostile code execution needs the security owner's isolation decision",
    ),
    adapters.SeamFamily(
        "solver_hybrids",
        "construction_evaluation_isolation",
        5,
        "custom inference runs only in an isolated stage, not built",
    ),
)


def rebuild(construction):
    if type(construction) is not dict:
        return adapters.Unrebuildable("not_declarative")
    if "loss_expression" in construction.get("parameters", {}):
        return adapters.Unrebuildable("outside_level", "objective.loss_expressions")
    compiled = compile_doc(construction)
    if not compiled["accepted"]:
        return adapters.Unrebuildable(
            "refused_by_contract", ",".join(compiled["codes"])
        )
    return adapters.Rebuilt(engine.digest(construction), compiled["recipe_digest"])


def session(level):
    return types.SimpleNamespace(
        permission_inventory=lambda: {
            "schema": "carbon.agent-campaign.permission-inventory.v1",
            "challenge": SYNTHETIC,
            "profile": f"level-{level}",
            "permitted": [{"id": "architecture.width"}],
            "not_permitted": ["objective.loss_expressions"],
        },
        public_identity=lambda: {"id": SYNTHETIC, "version": "1"},
        admission_refusals=lambda strategy: compile_doc(strategy).get("codes", []),
        code_run_seconds=lambda: LIMIT_SECONDS,
        recipe_outside_contract=lambda: {**recipe(), "model_family": "transolver"},
    )


def _definitions(families, level):
    examples = {name: f.attacks()[0][1] for name, f in families.items()}
    out = [
        adapters.FamilyDef(
            name=name,
            check=family.check,
            boundary="the synthetic contract's " + name.replace("_", " "),
            attack_example=examples[name],
            control_example=f"{name} valid control",
            family=family,
        )
        for name, family in families.items()
    ]
    if level == 0:
        out.append(
            adapters.FamilyDef(
                name="permission_ablation",
                check="baseline_and_permission_ablation",
                boundary="Level 0 has no permission to ablate; the climb runs at Level 1",
                attack_example="a Level 1 permission used at Level 0",
                control_example="a Level 0 panel construction",
                evidence=(
                    (
                        "tests/cpu/test_agent_campaign_climb.py::"
                        "test_a_removed_permission_that_still_runs_is_a_finding"
                    ),
                ),
            )
        )
    return tuple(out)


def synthetic_adapter(
    level=0, *, families=None, controls=None, runners=None, seams=SEAMS
):
    families = dict(FAMILIES if families is None else families)
    controls = _controls() if controls is None else controls
    if level == 1:
        plan = climb_plan()
        families["permission_ablation"] = adapters.ablation_family(
            plan,
            runners or Fake().runners(),
            Fake(leaky={f"ablated:{NEW}"}).runners(),
        )
        menu, _ = plan.panel
        controls = (
            *controls,
            adapters.Control(
                "menu_construction", "permission_ablation", "trained", VERSION,
                (plan.expanded, menu),
            ),
            # Held out from the engine: outside the panel and the attacks.
            adapters.Control(
                "unseen_expression_construction", "permission_ablation", "held_out",
                VERSION, (plan.expanded, HELD_OUT_EXPRESSION),
            ),
        )  # fmt: skip
    return adapters.DeclaredAdapter(
        challenge_id=SYNTHETIC,
        level=level,
        contract_digest=synthetic_contract().digest,
        family_defs=_definitions(families, level),
        control_set=tuple(controls),
        seams=seams,
        rebuilder=rebuild,
        session=session(level),
    )


def mutate(name, **changes):
    """The families with one family's parts replaced: a mutation."""
    return {**FAMILIES, name: dataclasses.replace(FAMILIES[name], **changes)}


@pytest.fixture
def registered():
    """The registry with the synthetic adapters, removed afterwards."""
    keys = [adapters.register(synthetic_adapter(level)) for level in (0, 1)]
    yield keys
    for key in keys:
        adapters.unregister(*key)


# -- the engine runs it end to end --------------------------------------------


@pytest.mark.parametrize("level", [0, 1])
def test_the_engine_runs_a_second_challenge_end_to_end(level):
    adapter = adapters.validate(synthetic_adapter(level))
    runs = adapters.run_adapter(adapter)
    states = {run.family: engine.family_state(run) for run in runs}
    expected = set(FAMILIES) | ({"permission_ablation"} if level else set())
    assert set(states) == expected
    assert set(states.values()) == {"IN_PROGRESS"}, states
    assert engine.findings(runs) == []
    for run in runs:
        assert {(r["challenge"], r["profile"]) for r in run.records} == {
            (SYNTHETIC, f"level-{level}")
        }
        controls = [r for r in run.records if r["role"] == "control"]
        assert controls and all(r["verdict"] == engine.PASSED for r in controls)


def test_every_track_a_check_is_supplied_by_a_family_or_a_seam():
    adapter = synthetic_adapter(0)
    cover = adapters.coverage(adapter)
    assert set(cover) == CHECKS[LEDGER_TRACK]
    assert tuple(cover) == adapters.TRACK_A_CHECKS
    for check, entry in cover.items():
        assert entry["run"] or entry["evidence"] or entry["not_run"], check
    assert cover["fresh_attack_confirmation"] == {
        "run": [],
        "evidence": [],
        "not_run": ["fresh_attack_confirmation"],
    }
    assert cover["baseline_and_permission_ablation"]["evidence"] == [
        "permission_ablation"
    ]
    at_one = adapters.coverage(synthetic_adapter(1))
    assert at_one["baseline_and_permission_ablation"]["run"] == ["permission_ablation"]


def test_higher_level_families_are_declared_seams_and_never_run():
    adapter = synthetic_adapter(0)
    seams = adapter.level_families()
    assert {s.state for s in seams} == {adapters.NOT_RUN}
    assert {s.name for s in seams if s.level > adapter.level} == {
        "participant_code_admission",
        "child_processes",
        "solver_hybrids",
    }
    verdict = adapter.oracle("child_processes", adapters.AttackInput("fork", "fork()"))
    assert verdict.verdict == adapters.NOT_RUN and verdict.condition is None
    with pytest.raises(adapters.AdapterError, match="a_seam_is_not_run"):
        adapters.SeamFamily("x", "fresh_attack_confirmation", 0, "why", state="PASS")


def test_the_oracle_re_runs_an_attempt_against_the_real_boundary():
    adapter = synthetic_adapter(0)
    held = adapter.oracle(
        "width_surface", adapters.AttackInput("wide", recipe(width=999))
    )
    assert held.verdict == engine.HELD and held.condition is None
    weak = synthetic_adapter(
        0, families=mutate("width_surface", boundary=unchecked_compiler)
    )
    breach = weak.oracle(
        "width_surface", adapters.AttackInput("wide", recipe(width=999))
    )
    assert breach.verdict == engine.BREACHED
    assert breach.condition == "FAILING_TRIGGER" and breach.condition in CONDITIONS
    with pytest.raises(adapters.AdapterError, match="oracle_for_an_unknown"):
        adapter.oracle("no_such_family", adapters.AttackInput("a", 1))
    with pytest.raises(TypeError):
        adapter.oracle(
            "width_surface", recipe(width=999)
        )  # a bare value is not an attempt
    assert held.specimen == engine.FIRED and breach.specimen == engine.FIRED


def _accept_everything(doc):
    return {"accepted": True, "recipe_digest": engine.digest(doc)}


@pytest.mark.parametrize(
    "changes, specimen",
    [
        # The specimen is the real boundary: the detector never fires.
        ({"specimen": compile_doc}, engine.SILENT),
        # A detector that cannot fire, whatever the boundary does.
        (
            {"boundary": _accept_everything, "breached": lambda result: False},
            engine.SILENT,
        ),
        # The specimen does not answer.
        ({"specimen": lambda doc: (_ for _ in ()).throw(TimeoutError())}, "TIMEOUT"),
    ],
)
def test_mutation_a_blind_detector_never_yields_held_from_the_oracle(changes, specimen):
    """Mutation: the per-attempt oracle counting a hold the detector cannot
    vouch for as HELD. The engine's run says INCONCLUSIVE; so must the oracle."""
    adapter = synthetic_adapter(0, families=mutate("width_surface", **changes))
    attempt = adapters.AttackInput("wide", recipe(width=999))
    verdict = adapter.oracle("width_surface", attempt)
    assert verdict.verdict == adapters.INCONCLUSIVE != engine.HELD
    assert verdict.condition is None and verdict.specimen == specimen
    (run,) = [r for r in adapters.run_adapter(adapter) if r.family == "width_surface"]
    assert engine.family_state(run) == "INCONCLUSIVE"
    with pytest.raises(adapters.AdapterError, match="a_hold_needs_a_specimen"):
        adapters.OracleResult(
            "width_surface", "wide", engine.HELD, verdict.evidence_digest,
            specimen=engine.SILENT,
        )  # fmt: skip


def test_the_oracle_reports_a_boundary_that_did_not_answer():
    def fails(doc):
        raise engine.InfrastructureFailure("pod lost")

    adapter = synthetic_adapter(0, families=mutate("width_surface", boundary=fails))
    verdict = adapter.oracle("width_surface", adapters.AttackInput("w", recipe()))
    assert verdict.verdict == engine.FAILED_INFRA and verdict.condition is None


def test_carbon_rebuilds_or_refuses_typed():
    adapter = synthetic_adapter(0)
    rebuilt = adapter.rebuild(recipe(width=8))
    assert type(rebuilt) is adapters.Rebuilt
    assert rebuilt.rebuilt_digest == compile_doc(recipe(width=8))["recipe_digest"]
    for construction, code in (
        ("print('hi')", "not_declarative"),
        (recipe(width=4096), "refused_by_contract"),
        (recipe(loss_expression="mse*0"), "outside_level"),
    ):
        refused = adapter.rebuild(construction)
        assert type(refused) is adapters.Unrebuildable and refused.code == code
        assert refused.code in adapters.UNREBUILDABLE_CODES
    with pytest.raises(adapters.AdapterError, match="unrebuildable_code_unknown"):
        adapters.Unrebuildable("because")


# -- the boundaries each family guards: mutations turn them red ---------------


@pytest.mark.parametrize(
    "name, changes",
    [
        # The compiler accepts an unknown field.
        ("width_surface", {"boundary": unchecked_compiler}),
        # An averaging scorer.
        ("mandatory_gate", {"boundary": averaging_score}),
        # A field dropped from the rebuilt identity.
        ("rebuild_identity", {"boundary": field_dropping_pair}),
        # A leaky stager.
        ("staged_bytes", {"boundary": lambda doc: canaries(stage(doc, leaky=True))}),
        # A feedback field added to the disclosure.
        ("feedback_disclosure", {"boundary": lambda doc: practice(doc, leaky=True)}),
        # The wall allowance lifted.
        ("wall_clock", {"boundary": lambda r: wall_clock(r, limit=10**9)}),
    ],
)
def test_mutation_a_weakened_boundary_is_a_finding(name, changes):
    adapter = synthetic_adapter(0, families=mutate(name, **changes))
    runs = {run.family: run for run in adapters.run_adapter(adapter)}
    assert engine.family_state(runs[name]) == "FINDING"
    found = engine.findings([runs[name]])
    assert found and {f.condition for f in found} == {"FAILING_TRIGGER"}
    others = [engine.family_state(r) for n, r in runs.items() if n != name]
    assert set(others) == {"IN_PROGRESS"}


@pytest.mark.parametrize("name", sorted(FAMILIES))
def test_mutation_silent_specimen_makes_the_family_inconclusive(name):
    """Mutation: a specimen that is the real boundary counted as a pass."""
    family = FAMILIES[name]
    adapter = synthetic_adapter(0, families=mutate(name, specimen=family.boundary))
    (run,) = [r for r in adapters.run_adapter(adapter) if r.family == name]
    assert engine.family_state(run) == "INCONCLUSIVE"


def test_mutation_a_removed_permission_that_still_runs_is_a_finding():
    """Level 1: the climb's rule. A removed permission must come back
    REFUSED; the engine's ablation family and the climb report agree."""
    leaky = Fake(leaky={f"ablated:{NEW}"})
    adapter = synthetic_adapter(1, runners=leaky.runners())
    runs = {run.family: run for run in adapters.run_adapter(adapter)}
    assert engine.family_state(runs["permission_ablation"]) == "FINDING"
    found = engine.findings([runs["permission_ablation"]])
    assert {f.attempt for f in found} == {f"{NEW}:expression"} | {
        f"{NEW}:attack-{n}" for n in range(3)
    }
    report = climb.climb(climb_plan(), leaky.runners())
    assert {f["kind"] for f in report["findings"]} == {"permission_not_enforced"}
    clean = adapters.run_adapter(synthetic_adapter(1))
    assert {engine.family_state(r) for r in clean} == {"IN_PROGRESS"}


def test_an_infrastructure_failure_in_the_climb_is_never_a_pass():
    plan = climb_plan()
    infra = Fake(infra={(f"ablated:{NEW}", "expression")})
    adapter = synthetic_adapter(1, runners=infra.runners())
    (run,) = [
        r for r in adapters.run_adapter(adapter) if r.family == "permission_ablation"
    ]
    verdicts = {
        r["attempt"]: r["verdict"] for r in run.records if r["role"] == "attack"
    }
    assert verdicts[f"{NEW}:expression"] == engine.FAILED_INFRA
    assert engine.family_state(run) == "INCONCLUSIVE"
    assert engine.findings([run]) == []
    assert plan.level == 1


def test_an_equal_budget_applies_to_every_family():
    runs = adapters.run_adapter(synthetic_adapter(1), budget=1)
    assert all(run.attempted == 1 and run.budget == 1 for run in runs)
    longer = {name for name, f in FAMILIES.items() if len(f.attacks()) > 1}
    assert {run.family for run in runs if run.exhausted} == longer | {
        "permission_ablation"
    }


# -- held-out controls --------------------------------------------------------


class _Spy:
    """An adapter whose held-out controls fail the test if read."""

    def __init__(self, inner):
        self.inner = inner
        self.challenge_id, self.level = inner.challenge_id, inner.level
        self.contract_digest = inner.contract_digest
        self.splits = []

    def controls(self, split):
        self.splits.append(split)
        if split == "held_out":
            raise AssertionError("the engine read a held-out control")
        return self.inner.controls(split)

    def __getattr__(self, name):
        return getattr(self.inner, name)


def test_mutation_the_engine_never_reads_held_out_controls():
    spy = _Spy(synthetic_adapter(1))
    adapters.validate(spy, held_out=False)
    runs = adapters.run_adapter(spy)
    assert runs and set(spy.splits) == {"trained"}
    # A run fed every control would be refused.
    family = FAMILIES["width_surface"]
    with pytest.raises(engine.HeldOutControlRefused):
        engine.run_family(family, controls=synthetic_adapter(0).controls("held_out"))


def test_held_out_controls_measure_wrongful_rejection():
    outcomes = adapters.held_out_outcomes(synthetic_adapter(1))
    rates = adapters.wrongful_rejection(outcomes)
    assert set(rates) == set(FAMILIES) | {"permission_ablation"}
    assert {r["rate"] for r in rates.values()} == {0.0}
    # A boundary narrower than its contract refuses the held-out edge recipe
    # though the trained control still passes: only held-out controls see it.
    narrow = lambda doc: (
        {"accepted": False, "codes": ["too_wide"]}
        if doc.get("parameters", {}).get("width", 0) > 32
        else compile_doc(doc)
    )
    adapter = synthetic_adapter(0, families=mutate("width_surface", boundary=narrow))
    (run,) = [r for r in adapters.run_adapter(adapter) if r.family == "width_surface"]
    assert engine.family_state(run) == "IN_PROGRESS"
    rates = adapters.wrongful_rejection(adapters.held_out_outcomes(adapter))
    assert rates["width_surface"] == {
        "status": "MEASURED",
        "refused": 1,
        "total": 1,
        "no_answer": 0,
        "not_measured": 0,
        "rate": 1.0,
    }


def test_a_relabelled_held_out_control_is_refused_by_its_registered_identity():
    """The engine refuses a held-out control by its registered identity (its
    family and input digest), not by its split label: relabelling it
    `trained` (or renaming or re-versioning it) does not get it run."""
    adapter = adapters.validate(synthetic_adapter(0))
    context = adapters.run_context(adapter)
    (held,) = [c for c in adapter.controls("held_out") if c.family == "width_surface"]
    family = FAMILIES["width_surface"]
    for disguise in (
        dataclasses.replace(held, split="trained"),
        dataclasses.replace(held, split="trained", name="fresh_name", version="v9"),
    ):
        assert disguise.identity == held.identity
        with pytest.raises(engine.HeldOutControlRefused):
            engine.run_family(family, controls=(disguise,), context=context)
    # A genuinely trained control still runs.
    (trained,) = [c for c in adapter.controls("trained") if c.family == "width_surface"]
    assert engine.run_family(family, controls=(trained,), context=context).records


def test_the_held_out_registry_is_scoped_per_adapter_and_never_only_grows():
    """One adapter's held-out identities refuse controls in its own runs
    only: another Challenge (or level) runs the same input as a trained
    control, a run with no Challenge context is not refused by any adapter's
    registration, and re-registering an adapter's split replaces its scope's
    set instead of growing a process-wide one."""
    adapter = adapters.validate(synthetic_adapter(0))
    (held,) = [c for c in adapter.controls("held_out") if c.family == "width_surface"]
    disguise = dataclasses.replace(held, split="trained")
    family = FAMILIES["width_surface"]
    other = engine.RunContext(challenge="another-challenge-v1", profile="level-0")
    assert engine.run_family(family, controls=(disguise,), context=other).records
    assert engine.run_family(family, controls=(disguise,)).records
    scope = adapters.held_out_scope(adapter)
    assert engine.is_registered_held_out(disguise, scope=scope)
    assert not engine.is_registered_held_out(disguise)
    # A new registration for the scope replaces it.
    engine.register_held_out((), scope=scope)
    assert not engine.is_registered_held_out(disguise, scope=scope)
    adapters.register_held_out_identities(adapter)
    assert engine.is_registered_held_out(disguise, scope=scope)
    engine.clear_held_out(scope)
    assert not engine.is_registered_held_out(disguise, scope=scope)
    adapters.validate(adapter)  # registers it again for the tests after


def test_mutation_a_label_only_check_lets_a_relabelled_held_out_control_run(
    monkeypatch,
):
    test_a_relabelled_held_out_control_is_refused_by_its_registered_identity()
    monkeypatch.setattr(engine, "is_registered_held_out", lambda *a, **k: False)
    with pytest.raises((AssertionError, pytest.fail.Exception)):
        test_a_relabelled_held_out_control_is_refused_by_its_registered_identity()


def test_a_held_out_control_identical_to_a_trained_one_is_refused():
    """Held-out and trained controls must be canonically distinct: a
    key-reordered copy of a trained value measures nothing new."""
    trained = adapters.Control(
        "menu", "width_surface", "trained", VERSION, recipe(width=8, learning_rate=1e-3)
    )
    reordered = dict(reversed(list(recipe(width=8, learning_rate=1e-3).items())))
    copy = adapters.Control("copy", "width_surface", "held_out", VERSION, reordered)
    assert trained.identity == copy.identity
    controls = tuple(c for c in _controls() if c.family != "width_surface") + (
        trained,
        copy,
    )
    with pytest.raises(adapters.AdapterError) as refused:
        adapters.validate(synthetic_adapter(0, controls=controls))
    assert refused.value.code == "held_out_control_is_canonically_a_trained_one"


def test_an_empty_or_evidence_only_held_out_set_is_not_measured():
    """A family with no held-out control that ran reports NOT_MEASURED with
    no rate, never {0, 0, 0}; a family that only cites evidence is listed,
    never silently skipped."""
    adapter = synthetic_adapter(0)
    evidence_only = adapters.Control(
        "panel_member", "permission_ablation", "held_out", VERSION, {"panel": "x"}
    )
    outcomes = adapters.held_out_outcomes(
        dataclasses.replace(adapter, control_set=(*adapter.control_set, evidence_only))
    )
    assert outcomes["permission_ablation"][0]["outcome"] == adapters.NOT_MEASURED
    rates = adapters.wrongful_rejection(outcomes, adapter.families())
    assert rates["permission_ablation"]["status"] == adapters.NOT_MEASURED
    assert rates["permission_ablation"]["rate"] is None
    assert rates["permission_ablation"]["not_measured"] == 1
    bare = adapters.wrongful_rejection({}, adapter.families())
    assert {r["status"] for r in bare.values()} == {adapters.NOT_MEASURED}
    assert {r["rate"] for r in bare.values()} == {None}
    measured = adapters.wrongful_rejection(adapters.held_out_outcomes(adapter))
    assert measured["width_surface"]["status"] == adapters.MEASURED


def test_a_refused_control_finding_binds_the_controls_identity():
    """A wrongly refused control's finding binds its registered identity,
    its input digest and its outcome: two refused controls never share one
    evidence digest (it was a digest of the bare boolean)."""

    def refuse_all(doc):
        return {"accepted": False, "codes": ["closed"]}

    family = dataclasses.replace(FAMILIES["width_surface"], boundary=refuse_all)
    controls = (
        adapters.Control("one", "width_surface", "trained", VERSION, recipe(width=8)),
        adapters.Control("two", "width_surface", "trained", VERSION, recipe(width=16)),
    )
    run = engine.run_family(family, controls=controls)
    found = [f for f in engine.findings([run]) if f.role == "control"]
    assert [f.attempt for f in found] == ["one", "two"]
    assert len({f.evidence_digest for f in found}) == 2
    rows = [r for r in run.records if r["role"] == "control"]
    assert [r["control_identity"] for r in rows] == [c.identity for c in controls]
    assert [r["input_digest"] for r in rows] == [
        engine.digest(c.value) for c in controls
    ]
    assert rows[0]["result_digest"] != engine.digest(False)


def test_the_ablation_familys_held_out_control_is_held_out_from_the_engine():
    """Every climb panel member is an ablation attack input and part of the
    default control, so the held-out control is a construction outside the
    plan; it runs as a construction, never as an attack."""
    plan = climb_plan()
    fake = Fake()
    adapter = synthetic_adapter(1, runners=fake.runners())
    (definition,) = [f for f in adapter.families() if f.name == "permission_ablation"]
    engine_items = {item.item_id for _, (_, item) in definition.family.attacks()}
    engine_items |= {item.item_id for item in plan.panel}
    (held_out,) = [
        c for c in adapter.controls("held_out") if c.family == "permission_ablation"
    ]
    assert held_out.value[1].item_id not in engine_items
    assert held_out.value[1].item_id not in {i.item_id for i in plan.attacks}
    adapters.run_adapter(adapter)
    assert ("level-1", "unseen-expression") not in fake.calls  # never run there
    outcomes = adapters.held_out_outcomes(adapter)["permission_ablation"]
    assert [r["outcome"] for r in outcomes] == [engine.PASSED]
    assert fake.calls[-1] == ("level-1", "unseen-expression")


# -- validation and the registry ----------------------------------------------


def _without(controls, name):
    return tuple(c for c in controls if c.name != name)


@pytest.mark.parametrize(
    "build, code",
    [
        (
            lambda: synthetic_adapter(0, seams=SEAMS[1:]),
            "check_not_supplied",
        ),
        (
            lambda: synthetic_adapter(0, controls=_without(_controls(), "edge_recipe")),
            "family_has_a_held_out_control",
        ),
        (
            lambda: synthetic_adapter(0, controls=_without(_controls(), "menu_recipe")),
            "family_has_a_trained_control",
        ),
        (
            lambda: synthetic_adapter(
                0,
                controls=(
                    *_controls(),
                    adapters.Control(
                        "menu_recipe", "width_surface", "held_out", VERSION, {}
                    ),
                ),
            ),
            "control_names_are_unique_across_splits",
        ),
        (
            lambda: dataclasses.replace(
                synthetic_adapter(0), contract_digest="sha256:0"
            ),
            "contract_digest_is_sha256",
        ),
        (
            lambda: dataclasses.replace(synthetic_adapter(0), level=6),
            "level_is_a_ladder_level",
        ),
        (
            lambda: dataclasses.replace(
                synthetic_adapter(0), challenge_id="Not A Token"
            ),
            "challenge_id_is_a_contract_token",
        ),
        (
            lambda: synthetic_adapter(0, seams=(*SEAMS, SEAMS[1])),
            "family_names_are_unique",
        ),
        (lambda: object(), "adapter_protocol_not_met"),
    ],
)
def test_a_malformed_adapter_is_refused(build, code):
    with pytest.raises(adapters.AdapterError, match=code):
        adapters.validate(build())


def test_definitions_and_controls_are_typed():
    with pytest.raises(
        adapters.AdapterError, match="family_is_run_here_or_cites_evidence"
    ):
        adapters.FamilyDef("x", "fresh_attack_confirmation", "b", "a", "c")
    with pytest.raises(
        adapters.AdapterError, match="engine_family_matches_its_definition"
    ):
        adapters.FamilyDef(
            "other", "artifact_and_dependency_attacks", "b", "a", "c",
            family=FAMILIES["width_surface"],
        )  # fmt: skip
    with pytest.raises(adapters.AdapterError, match="control_is_versioned"):
        adapters.Control("c", "width_surface", "trained", " ")
    with pytest.raises(adapters.AdapterError, match="control_split"):
        adapters.Control("c", "width_surface", "tuning", VERSION)
    with pytest.raises(
        adapters.AdapterError, match="only_a_breach_carries_a_condition"
    ):
        adapters.OracleResult("f", "a", engine.HELD, "sha256:0", "FAILING_TRIGGER")
    with pytest.raises(
        adapters.AdapterError, match="oracle_condition_outside_conditions"
    ):
        adapters.OracleResult("f", "a", engine.BREACHED, "sha256:0", "EXPLOIT")


def test_the_registry_keys_adapters_by_challenge_and_level(registered):
    assert adapters.ADAPTERS[(SYNTHETIC, 0)].level == 0
    assert adapters.get(SYNTHETIC, 1).level == 1
    assert {(SYNTHETIC, 0), (SYNTHETIC, 1)} <= set(adapters.ADAPTERS)
    with pytest.raises(adapters.AdapterError, match="adapter_already_registered"):
        adapters.register(synthetic_adapter(0))
    with pytest.raises(adapters.AdapterError, match="adapter_not_registered"):
        adapters.get(SYNTHETIC, 2)


_BUILTIN = """
from carbon.agent_campaign.attack import adapter
import synthetic_builtin_source

adapter.register(synthetic_builtin_source.ADAPTER)
if synthetic_builtin_source.FAIL:
    raise RuntimeError("the built-in adapter package is broken")
"""


@pytest.fixture
def builtin_package(tmp_path, monkeypatch):
    """A temporary built-in adapters package that registers the synthetic
    Level 0 adapter at import, read by a fresh registry."""
    name = "synthetic_builtin_adapters"
    (tmp_path / f"{name}.py").write_text(_BUILTIN)
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setattr(adapters, "BUILTIN_PACKAGE", name)
    registry = adapters._Registry()
    monkeypatch.setattr(adapters, "ADAPTERS", registry)
    source = types.SimpleNamespace(ADAPTER=synthetic_adapter(0), FAIL=False)
    monkeypatch.setitem(sys.modules, "synthetic_builtin_source", source)
    sys.modules.pop(name, None)
    yield name, registry, source
    sys.modules.pop(name, None)


def test_built_in_adapters_load_on_the_first_read(builtin_package):
    name, registry, source = builtin_package
    assert name not in sys.modules  # nothing imported it yet
    assert adapters.get(SYNTHETIC, 0) is source.ADAPTER  # the first read
    assert name in sys.modules
    assert list(registry) == [(SYNTHETIC, 0)]
    with pytest.raises(adapters.AdapterError, match="adapter_already_registered"):
        adapters.register(synthetic_adapter(0))


def test_a_missing_built_in_package_is_an_empty_registry(monkeypatch):
    monkeypatch.setattr(adapters, "BUILTIN_PACKAGE", "no_such_package_anywhere")
    assert len(adapters._Registry()) == 0


def test_a_built_in_package_that_fails_to_import_is_never_hidden(
    builtin_package, tmp_path, monkeypatch
):
    """Mutation: an import failure leaving an empty registry that reads as
    'adapter_not_registered' for the rest of the process."""
    _, registry, source = builtin_package
    source.FAIL = True
    for read in (len, lambda r: adapters.get(SYNTHETIC, 0), list):
        with pytest.raises(
            adapters.AdapterError, match="builtin_adapters_failed_to_import"
        ) as refused:
            read(registry)
        assert isinstance(refused.value.__cause__, RuntimeError)
    assert dict(registry._entries) == {}  # the partial registration rolled back
    # The Graphite record path keeps the failure's code, not 'not registered'.
    records, pipeline = tmp_path / "challenges", tmp_path / "records"
    records.mkdir()
    pipeline.mkdir()
    (records / f"{SYNTHETIC}.json").write_text(json.dumps(RECORD))
    monkeypatch.setattr(challenges, "RECORDS", records)
    construction = {"challenge": SYNTHETIC, "level": 0, "levels": []}
    (pipeline / "f99.json").write_text(json.dumps({"construction": construction}))
    with pytest.raises(
        challenges.ChallengeError,
        match="attack_adapter_unavailable: builtin_adapters_failed_to_import",
    ):
        challenges.get(SYNTHETIC, pipeline_records=pipeline)
    source.FAIL = False  # repaired: the next read loads it
    assert adapters.get(SYNTHETIC, 0) is source.ADAPTER


# -- the Graphite record ------------------------------------------------------

RECORD = {
    "schema": challenges.SCHEMA,
    "challenge": SYNTHETIC,
    "family": "f99",
    "label": "the synthetic heat sink",
    "suite_report": "synthetic/SUITE_V1_COVERAGE.json",
    "attack_goals": {"A4": "Is the synthetic worker's wall clock enforced?"},
    "attacker_campaign": {
        "campaign": "graphite-synthetic-attacker",
        "workspace": "graphite-synthetic-attacker-workspace",
        "credential_ref": "graphite-synthetic-engy",
        "grant": {"id": "SYNTHETIC-GRANT", "file": "synthetic/SYNTHETIC-GRANT.json"},
        "authority": "synthetic test fixture; no owner value",
    },
}


def test_a_second_challenge_gets_a_graphite_record_through_its_adapter():
    challenge = challenges.from_record(
        RECORD, synthetic_adapter(0), {"challenge": SYNTHETIC, "level": 0, "levels": []}
    )
    assert challenge.level == 0 and challenge.construction_level() == 0
    assert challenge.public_identity() == {"id": SYNTHETIC, "version": "1"}
    assert challenge.code_run_seconds() == LIMIT_SECONDS
    assert challenge.admission_refusals(recipe(width=4096)) == ["out_of_surface"]
    assert challenge.admission_refusals(recipe(width=8)) == []
    assert compile_doc(challenge.recipe_outside_contract())["accepted"] is False


def test_the_record_resolves_its_adapter_from_the_registry(
    tmp_path, monkeypatch, registered
):
    records, pipeline = tmp_path / "challenges", tmp_path / "records"
    records.mkdir()
    pipeline.mkdir()
    (records / f"{SYNTHETIC}.json").write_text(json.dumps(RECORD))
    monkeypatch.setattr(challenges, "RECORDS", records)
    construction = {"challenge": SYNTHETIC, "level": 1, "levels": []}
    (pipeline / "f99.json").write_text(json.dumps({"construction": construction}))
    challenge = challenges.get(SYNTHETIC, pipeline_records=pipeline)
    assert challenge.adapter is adapters.ADAPTERS[(SYNTHETIC, 1)]
    assert challenge.construction_level() == 1
    assert challenges.recorded() == [SYNTHETIC]
    (pipeline / "f99.json").write_text(
        json.dumps({"construction": dict(construction, level=3)})
    )
    with pytest.raises(
        challenges.ChallengeError, match="attack_adapter_not_registered"
    ):
        challenges.get(SYNTHETIC, pipeline_records=pipeline)


def test_a_malformed_record_or_mismatched_adapter_is_refused():
    construction = {"challenge": SYNTHETIC, "level": 0}
    campaign = RECORD["attacker_campaign"]
    for bad, code in (
        (
            dict(RECORD, schema="carbon.graphite.challenge.v1"),
            "challenge_record_schema",
        ),
        (dict(RECORD, challenge="Not A Token"), "challenge_is_a_contract_token"),
        (dict(RECORD, attack_goals={"A9": "no such vector"}), "attack_goals_reword"),
        (dict(RECORD, suite_report="../outside.json"), "names_its_suite_report"),
        # A call cap is refused: money and elapsed time bind.
        (
            dict(RECORD, attacker_campaign=dict(campaign, session_turns=34)),
            "attacker_campaign_keys",
        ),
        (
            dict(RECORD, attacker_campaign=dict(campaign, ceiling_usd="5.00")),
            "attacker_campaign_keys",
        ),
        (
            dict(
                RECORD,
                attacker_campaign=dict(
                    campaign, grant={"id": "SYNTHETIC-GRANT", "file": "other.json"}
                ),
            ),
            "attacker_grant_is_id_and_its_file",
        ),
    ):
        with pytest.raises(challenges.ChallengeError, match=code):
            challenges.from_record(bad, synthetic_adapter(0), construction)
    with pytest.raises(
        challenges.ChallengeError, match="for_another_challenge_or_level"
    ):
        challenges.from_record(
            RECORD, synthetic_adapter(0), dict(construction, level=1)
        )
    with pytest.raises(challenges.ChallengeError, match="names_another_contract"):
        challenges.from_record(
            RECORD, synthetic_adapter(0), dict(construction, challenge="x")
        )
    without = dataclasses.replace(synthetic_adapter(0), session=None)
    with pytest.raises(challenges.ChallengeError, match="lacks_the_session_surface"):
        challenges.from_record(RECORD, without, construction)
    with pytest.raises(challenges.ChallengeError, match="attack_adapter_refused"):
        challenges.from_record(
            RECORD, synthetic_adapter(0, seams=SEAMS[1:]), construction
        )
    # The inventory's profile must be the pipeline's level.
    wrong = dataclasses.replace(synthetic_adapter(0), session=session(2))
    challenge = challenges.from_record(RECORD, wrong, construction)
    with pytest.raises(
        challenges.ChallengeError, match="disagrees_with_pipeline_record"
    ):
        challenge.construction_level()


def test_batterys_record_has_the_same_shape_and_the_phase4_grant():
    document = challenges.load_record("battery-fastcharge-ageing-development-v1")
    campaign = document["attacker_campaign"]
    assert campaign["grant"] == {
        "id": "GRAPHITE-GRANT-PHASE4",
        "file": "docs/development/graphite/grants/GRAPHITE-GRANT-PHASE4.json",
    }
    assert "session_turns" not in campaign and "ceiling_usd" not in campaign
    assert (REPO / document["suite_report"]).is_file()
    assert "OWNER-GRAPHITE-ATTACKER-01" in campaign["authority"]


@pytest.mark.parametrize(
    "load", [lambda: RECORD, lambda: challenges.load_record(BATTERY_TOKEN)]
)
def test_only_the_records_brief_fields_reach_an_attacker_brief(load):
    """The campaign block names a credential reference, which Graphite's
    protected-material check refuses; only the brief fields go to a model."""
    from carbon.agent_campaign.graphite import tools

    document = load()
    shown = challenges.brief(document)
    assert set(shown) == set(challenges.BRIEF_KEYS)
    assert "attacker_campaign" not in shown
    assert not tools.protected(shown) and not tools.protected(json.dumps(shown))
    assert tools.protected(json.dumps(document))  # the whole record is refused
    bad = dict(document, attack_goals={"A3": "read the hidden_case answers"})
    with pytest.raises(challenges.ChallengeError, match="brief_names_protected"):
        challenges.check_record(bad)


# -- neutrality ---------------------------------------------------------------


def _named(path):
    tree = ast.parse(path.read_text())
    docstrings = {
        id(node.body[0].value)
        for node in ast.walk(tree)
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.ClassDef))
        and node.body
        and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant)
    }
    named = set()
    for node in ast.walk(tree):
        for attribute in ("id", "attr", "name", "module"):
            value = getattr(node, attribute, None)
            if isinstance(value, str) and "battery" in value.lower():
                named.add(value)
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and id(node) not in docstrings
            and "battery" in node.value.lower()
        ):
            named.add(node.value)
    return named


#: The whole attack package except its per-Challenge adapters
#: (`attack/adapters/`), which are where a Challenge is named.
NEUTRAL_ATTACK_MODULES = sorted(
    str(path.relative_to(REPO))
    for path in (REPO / "carbon/agent_campaign/attack").glob("*.py")
)


def test_the_neutrality_scan_covers_the_whole_attack_package():
    assert {Path(m).name for m in NEUTRAL_ATTACK_MODULES} >= {
        "__init__.py",
        "adapter.py",
        "analysis.py",
        "benchmark.py",
        "engine.py",
        "knowledge.py",
        "report.py",
        "verify.py",
    }


@pytest.mark.parametrize(
    "module",
    [
        *NEUTRAL_ATTACK_MODULES,
        "carbon/agent_campaign/graphite/challenge.py",
        "carbon/challenge_pipeline/suite.py",
    ],
)
def test_the_neutral_core_names_no_challenge(module):
    assert _named(REPO / module) == set()
