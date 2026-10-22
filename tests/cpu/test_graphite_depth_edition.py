"""The Graphite miner depth edition (GRAPHITE-DEPTH-REVIEW 2026-10-21).

The Test Lead assigned recommendations A and C of the Graphite Testing
Manager's depth review as a new published miner edition,
`carbon.graphite.miner-edition.v2`:

- settings (A): the Planner reasons at "high" with a 32,768-token output cap
  where the model's recorded context holds the selection's window plus that
  cap (the internal whole-context roles' `output_cap_fits` rule, at the
  selection's window), the Constructor at "medium" at least with its caps and
  window unchanged, the Reader on the selection as it is;
- plan shape (C): three more required texts per hypothesis -
  physics_rationale, architecture_match and ablation - bounded and refused as
  the other texts are, and a required first step that characterises the
  public TRAIN with run_python;
- one-factor ablations before a selection, and the recipe forms this base
  actually serves (catalog and graph sources, miner source bundles closed).

v1 is published and never edited: its digest is pinned unchanged. The
research share stays the launch's own; the budget figure is the owner's.
Nothing here contacts a provider: every selection uses a fixture key path.
"""

from __future__ import annotations

import pytest
from test_graphite_miner_driver import (
    RECIPE,
    STOP_TURN,
    Transport,
    World,
    practice,
    record_plan,
    select,
)

from carbon.agent_campaign.graphite import roles as internal_roles
from carbon.agent_campaign.graphite.miner import driver
from carbon.agent_campaign.graphite.miner import edition as editions
from carbon.agent_campaign.graphite.miner import plan as plans
from carbon.agent_campaign.graphite.miner.toolbox import stage_tools
from carbon.development_session import construction_recipe
from carbon.development_session import model_provider as mp
from carbon.development_session.research_loop import OUTPUT_CAP_HIT

#: v1's digest, as `test_graphite_miner_mutations` pins it: unchanged.
EDITION_V1_DIGEST = (
    "sha256:8423465214e6e368d30673442287b00483c3a341a3c990734c615c8b6fb4f90c"
)
#: The depth edition's digest. Any change to its prompts, manifests, finishing
#: tool, plan schema or role settings is another edition id, never an edit.
EDITION_V2_DIGEST = (
    "sha256:db624dda493fd814876d1f51e7649f73131c076fc3fa5a87e105f3822af2e966"
)
CHALLENGE = {"id": "fixture-challenge", "version": "1"}
KEY = {"kind": "file", "reference": "/nonexistent/fixture.key"}
LADDER = tuple(mp.ENGY_CONTEXT_TOKENS)


def engy(model, **settings):
    return mp.select(
        provider_id="engy-chat", model_id=model, credential=KEY, settings=settings
    )


def depth_hypothesis(**changes):
    item = {
        "hypothesis": "a spectral operator captures the periodic torque ripple",
        "expected_effect": "lower practice error than the kernel baseline",
        "physics_rationale": "TRAIN torque is periodic over the rotor sweep",
        "architecture_match": "a Fourier operator represents periodic structure",
        "ablation": "against the best recipe, only the backbone differs",
        "stopping_rule": "stop after two practices without improvement",
        "recipe_json": None,
        "cites": [],
    }
    item.update(changes)
    return item


def depth_arguments(*items):
    return {"hypotheses": list(items or [depth_hypothesis()]), "pins_considered": []}


def refused(arguments, schema=plans.PLAN_SCHEMA_V2):
    with pytest.raises(plans.PlanInvalid) as caught:
        plans.from_arguments(arguments, challenge=CHALLENGE, schema=schema)
    return caught.value


# --- the published editions ------------------------------------------------------


def test_v1_is_unchanged_and_stays_the_default():
    assert editions.EDITION.digest == EDITION_V1_DIGEST
    assert editions.resolve(editions.EDITION_ID, EDITION_V1_DIGEST) is (
        editions.EDITION
    )
    assert editions.EDITION.plan_record()["schema"] == editions.EDITION_RECORD_SCHEMA
    assert "role_settings" not in editions.EDITION.plan_record()
    assert editions.EDITION.finish is editions.FINISH_TOOL
    assert editions.EDITION.plan_schema == plans.PLAN_SCHEMA
    # The default a new launch freezes did not move.
    assert editions.EDITION_ID == "carbon.graphite.miner-edition.v1"
    assert editions.launch_fields({})["edition"] == editions.EDITION_ID


def test_the_depth_edition_is_published_under_its_own_id():
    edition = editions.DEPTH_EDITION
    assert (
        edition.edition_id
        == editions.DEPTH_EDITION_ID
        == ("carbon.graphite.miner-edition.v2")
    )
    assert editions.MINER_EDITIONS[editions.DEPTH_EDITION_ID] is edition
    assert edition.digest == EDITION_V2_DIGEST != EDITION_V1_DIGEST
    assert editions.resolve(editions.DEPTH_EDITION_ID, EDITION_V2_DIGEST) is edition
    with pytest.raises(editions.EditionUnknown):
        editions.resolve(editions.DEPTH_EDITION_ID, EDITION_V1_DIGEST)
    record = edition.plan_record()
    assert record["schema"] == editions.EDITION_RECORD_SCHEMA_V2
    assert record["plan_schema"] == plans.PLAN_SCHEMA_V2
    assert record["local_tools"][editions.FINISH] != (
        editions.EDITION.plan_record()["local_tools"][editions.FINISH]
    )
    # Same roles, tools and actions as v1; only the two prompts differ.
    assert edition.role("reader") is editions.READER
    for name in ("planner", "constructor"):
        assert edition.role(name).tools == editions.EDITION.role(name).tools
        assert edition.role(name).workspace_actions == (
            editions.EDITION.role(name).workspace_actions
        )
        assert edition.role(name).prompt != editions.EDITION.role(name).prompt
    # A launch may name it; the research share stays the launch's own.
    fields = editions.launch_fields({}, edition=editions.DEPTH_EDITION_ID)
    assert fields["edition"] == editions.DEPTH_EDITION_ID
    assert fields["research_share"] == editions.DEFAULT_RESEARCH_SHARE == 0.10


def test_the_role_settings_are_frozen_in_the_edition():
    edition = editions.DEPTH_EDITION
    planner = edition.settings_for("planner")
    assert planner.reasoning_effort_at_least == "high"
    assert planner.max_output_tokens_at_least == 32768
    assert planner.timeout_seconds_at_least == 600
    constructor = edition.settings_for("constructor")
    assert constructor.reasoning_effort_at_least == "medium"
    assert constructor.max_output_tokens_at_least is None
    assert constructor.timeout_seconds_at_least is None
    assert edition.settings_for("reader") is None
    assert edition.plan_record()["role_settings"] == {
        "planner": planner.record(),
        "constructor": constructor.record(),
    }
    with pytest.raises(ValueError):
        editions.RoleSettings(reasoning_effort_at_least="extreme")
    with pytest.raises(ValueError, match="at most once"):
        editions.MinerEdition(
            edition_id="x",
            roles=edition.roles,
            role_settings=(("writer", planner),),
        )


# --- settings per ladder model ---------------------------------------------------


@pytest.mark.parametrize("model", LADDER)
@pytest.mark.parametrize("cap", (4096, 32768))
def test_the_fit_rule_is_internal_graphites_at_a_whole_context_window(model, cap):
    context = mp.ENGY_CONTEXT_TOKENS[model]
    window = min(context, internal_roles.SELECT_MAX_INPUT_TOKENS)
    assert editions.output_cap_fits_window(window, context, cap) == (
        internal_roles.output_cap_fits(model, mp.ENGY_CONTEXT_TOKENS, cap)
    )


def test_output_cap_fits_per_ladder_model():
    # At a whole-context window only kimi-k3 holds 32,768 more (internal
    # Graphite's `MODEL_OUTPUT_CAPS`); at the historical 65,536 every model
    # on the ladder does.
    fits = {
        model: internal_roles.output_cap_fits(model, mp.ENGY_CONTEXT_TOKENS, 32768)
        for model in LADDER
    }
    assert fits == {model: model == "kimi-k3" for model in LADDER}
    assert all(
        editions.output_cap_fits_window(65536, mp.ENGY_CONTEXT_TOKENS[m], 32768)
        for m in LADDER
    )


@pytest.mark.parametrize("model", LADDER)
def test_the_planner_gets_high_and_32768_at_the_historical_window(model):
    selection = engy(model, max_input_tokens=65536, max_output_tokens=2048)
    derived, record = editions.role_selection(
        editions.DEPTH_EDITION, "planner", selection
    )
    assert derived.settings.record() == {
        "max_input_tokens": 65536,
        "max_output_tokens": 32768,
        "reasoning_effort": "high",
        "timeout_seconds": 600,
    }
    assert derived.model_id == model and derived.provider_id == "engy-chat"
    assert record["max_output_tokens"]["basis"] == editions.CAP_RAISED
    assert record["reasoning_effort"]["basis"] == editions.EFFORT_RAISED
    # Each call now reserves the larger cap.
    assert derived.reservation_nano > selection.reservation_nano


@pytest.mark.parametrize("model", LADDER)
def test_a_cap_that_does_not_fit_the_window_is_not_applied(model):
    """A miner window of the whole context: only where the recorded context
    holds the window plus 32,768 is the cap raised; elsewhere the selection
    keeps its own cap (never an invalid request), and the record says why."""
    context = mp.ENGY_CONTEXT_TOKENS[model]
    window = min(context, mp.INPUT_TOKEN_BOUNDS[1])
    selection = engy(model, max_input_tokens=window, max_output_tokens=4096)
    derived, record = editions.role_selection(
        editions.DEPTH_EDITION, "planner", selection
    )
    fits = editions.output_cap_fits_window(window, context, 32768)
    assert fits == (model == "kimi-k3")
    assert derived.settings.max_output_tokens == (32768 if fits else 4096)
    assert derived.settings.max_input_tokens == window
    assert record["max_output_tokens"]["basis"] == (
        editions.CAP_RAISED if fits else editions.CAP_DOES_NOT_FIT_CONTEXT
    )
    assert derived.settings.reasoning_effort == "high"


def test_a_larger_cap_and_a_model_without_recorded_context_are_kept():
    # A product launch's default: the model's own maximum, 131,072, is never
    # lowered to the floor.
    product = mp.select(
        provider_id="engy-chat",
        model_id=mp.ENGY_DEFAULT_MODEL,
        credential=KEY,
        output_default=mp.OUTPUT_DEFAULT_V2,
        input_default=mp.INPUT_DEFAULT_V2,
    )
    derived, record = editions.role_selection(
        editions.DEPTH_EDITION, "planner", product
    )
    assert derived.settings.max_output_tokens == 131072
    assert derived.settings.max_input_tokens == product.settings.max_input_tokens
    assert record["max_output_tokens"]["basis"] == editions.CAP_SELECTION_AT_LEAST
    assert derived.settings.reasoning_effort == "high"
    # The historical default records no context: its cap stays 2,048.
    derived, record = editions.role_selection(
        editions.DEPTH_EDITION,
        "planner",
        mp.DEFAULT_SELECTION,
        credential_file="/nonexistent/fixture.key",
    )
    assert derived.settings.max_output_tokens == 2048
    assert record["max_output_tokens"]["basis"] == editions.CAP_NO_RECORDED_CONTEXT
    assert derived.credential.reference == "/nonexistent/fixture.key"


@pytest.mark.parametrize(
    ("effort", "applied"),
    (("minimal", "medium"), ("low", "medium"), ("medium", "medium"), ("high", "high")),
)
def test_the_constructor_reasons_at_medium_at_least(effort, applied):
    selection = engy("kimi-k3", reasoning_effort=effort, max_output_tokens=4096)
    derived, record = editions.role_selection(
        editions.DEPTH_EDITION, "constructor", selection
    )
    assert derived.settings.reasoning_effort == applied
    # Its caps, window and timeout stay the selection's own.
    for key in ("max_input_tokens", "max_output_tokens", "timeout_seconds"):
        assert getattr(derived.settings, key) == getattr(selection.settings, key)
    assert set(record) == {"rule", "role", "reasoning_effort"}


def test_a_selection_that_sends_no_reasoning_keeps_none():
    selection = engy("kimi-k3", reasoning_effort=None)
    for name in ("planner", "constructor"):
        derived, record = editions.role_selection(
            editions.DEPTH_EDITION, name, selection
        )
        assert derived.settings.reasoning_effort is None
        assert record["reasoning_effort"]["basis"] == editions.EFFORT_NONE_SENT


def test_the_reader_and_every_v1_role_run_on_the_selection_itself():
    selection = engy("glm-5.2", max_input_tokens=65536)
    assert editions.role_selection(editions.DEPTH_EDITION, "reader", selection) == (
        selection,
        None,
    )
    for role in ("reader", "planner", "constructor"):
        found, record = editions.role_selection(editions.EDITION, role, selection)
        assert found is selection and record is None


def test_the_research_share_check_reserves_the_planners_cap():
    selection = engy("kimi-k3", max_input_tokens=65536, max_output_tokens=2048)
    planner = editions.role_selection(editions.DEPTH_EDITION, "planner", selection)[0]
    ceilings = {
        "provider_attempts": 100,
        "provider_nanodollars": selection.reservation_nano * 10,
    }
    v1 = editions.launch_fields({})
    v2 = editions.launch_fields({}, edition=editions.DEPTH_EDITION_ID)
    assert driver.research_share_shortfall(v1, ceilings, selection) is None
    short = driver.research_share_shortfall(v2, ceilings, selection)
    assert short == {
        "stage": driver.PLAN,
        "dimension": "provider_nanodollars",
        "share_cap": selection.reservation_nano,
        "per_call": planner.reservation_nano,
    }


# --- the plan's three more fields ------------------------------------------------


def test_a_v2_plan_records_the_three_fields():
    plan = plans.from_arguments(
        depth_arguments(), challenge=CHALLENGE, schema=plans.PLAN_SCHEMA_V2
    )
    assert plan["schema"] == plans.PLAN_SCHEMA_V2
    item = plan["hypotheses"][0]
    for name in editions.DEPTH_FIELDS:
        assert item[name] == depth_hypothesis()[name]
    assert plans.check_shape(plan) is plan
    # An edit keeps the schema and the fields.
    edited = plans.new_version(plan, parent=plans.plan_digest(plan))
    assert edited["schema"] == plans.PLAN_SCHEMA_V2
    assert edited["hypotheses"][0]["ablation"] == item["ablation"]
    ok, refusal = plans.validate_plan(
        plan, library=None, curation={"pins": [], "bans": []}
    )
    assert ok and refusal is None


@pytest.mark.parametrize("name", editions.DEPTH_FIELDS)
def test_each_field_is_required(name):
    item = depth_hypothesis()
    del item[name]
    error = refused(depth_arguments(item))
    assert (error.code, error.field) == (plans.PLAN_INVALID, "hypotheses[0]")
    assert name in error.reason
    assert error.refusal()["status"] == "REJECTED_BEFORE_DISPATCH"


@pytest.mark.parametrize("name", editions.DEPTH_FIELDS)
@pytest.mark.parametrize("value", ("", "   ", "x" * (plans.MAX_TEXT + 1), None, 3))
def test_an_empty_or_over_bound_field_is_refused(name, value):
    error = refused(depth_arguments(depth_hypothesis(**{name: value})))
    assert error.code == plans.PLAN_INVALID
    assert error.field == "hypotheses[0]." + name
    assert error.reason == f"hypotheses[0].{name} must be text of 1 to 2000 characters"


def test_the_bound_is_inclusive_and_shared_with_the_other_texts():
    text = "x" * plans.MAX_TEXT
    plan = plans.from_arguments(
        depth_arguments(depth_hypothesis(ablation=text)),
        challenge=CHALLENGE,
        schema=plans.PLAN_SCHEMA_V2,
    )
    assert plan["hypotheses"][0]["ablation"] == text
    # A stored v2 plan that lost a field is refused by its shape check.
    broken = {**plan, "hypotheses": [dict(plan["hypotheses"][0])]}
    del broken["hypotheses"][0]["physics_rationale"]
    with pytest.raises(plans.PlanInvalid):
        plans.check_shape(broken)


def test_v1_plans_keep_their_shape():
    # v1 refuses the new fields and accepts its own.
    error = refused(depth_arguments(), schema=plans.PLAN_SCHEMA)
    assert error.reason == (
        "a hypothesis has hypothesis, expected_effect, stopping_rule, "
        "recipe_json and cites"
    )
    item = depth_hypothesis()
    for name in editions.DEPTH_FIELDS:
        del item[name]
    plan = plans.from_arguments(depth_arguments(item), challenge=CHALLENGE)
    assert plan["schema"] == plans.PLAN_SCHEMA
    assert not set(editions.DEPTH_FIELDS) & set(plan["hypotheses"][0])
    with pytest.raises(ValueError):
        plans.from_arguments(depth_arguments(), challenge=CHALLENGE, schema="v9")


def test_the_finishing_tool_requires_the_three_fields():
    items = editions.FINISH_TOOL_V2["parameters"]["properties"]["hypotheses"]["items"]
    for name in editions.DEPTH_FIELDS:
        assert name in items["required"]
        assert items["properties"][name]["type"] == "string"
    v1 = editions.FINISH_TOOL["parameters"]["properties"]["hypotheses"]["items"]
    assert not set(editions.DEPTH_FIELDS) & set(v1["required"])
    assert editions.FINISH_TOOL_V2["name"] == editions.FINISH_TOOL["name"]
    # The Planner's stage offers the edition's own finishing tool.
    offered = stage_tools(
        editions.PLANNER_V2, [], finish_tool=editions.DEPTH_EDITION.finish
    )
    finish = next(t for t in offered if t["name"] == editions.FINISH)
    assert finish == editions.FINISH_TOOL_V2
    offered = stage_tools(editions.PLANNER, [])
    assert next(t for t in offered if t["name"] == editions.FINISH) == (
        editions.FINISH_TOOL
    )


# --- prompts ---------------------------------------------------------------------


def _flat(text):
    return " ".join(text.split())


def test_the_planner_prompt_requires_characterising_train_first():
    prompt = _flat(editions.PLANNER_PROMPT_V2)
    assert (
        "Before writing hypotheses, characterise the public TRAIN with "
        "run_python: input and output dimensions, scale and units, smoothness "
        "and regime changes, symmetries or conservation the targets show. Base "
        "every hypothesis on what you found."
    ) in prompt
    assert prompt.index("characterise the public TRAIN") < prompt.index(
        "Search the literature"
    )
    for name in editions.DEPTH_FIELDS:
        assert name in prompt
    assert "run_python" in editions.PLANNER_ACTIONS
    assert "characterise" not in editions.PLANNER_PROMPT


def test_the_constructor_prompt_asks_for_one_factor_ablations():
    prompt = _flat(editions.CONSTRUCTOR_PROMPT_V2)
    assert (
        "Compare each hypothesis against the current best recipe by changing "
        "one factor at a time at equal practice budget; select only a recipe "
        "whose advantage survives its ablation, and cite the practice runs that "
        "show it."
    ) in prompt
    assert "ablation" not in editions.CONSTRUCTOR_PROMPT


def test_the_constructor_prompt_describes_the_recipe_forms_served():
    prompt = _flat(editions.CONSTRUCTOR_PROMPT_V2)
    for text in (
        "carbon.construction-recipe.v1",
        '{"kind": "catalog", "catalog_id", "catalog_digest"}',
        "procedure.configuration and procedure.train_use",
        '{"kind": "graph", "submission_digest"}',
        "where the Challenge serves graphs",
        "Miner source bundles stay closed",
        "declarative JSON (schema_version, challenge_id, backbone, parameters)",
    ):
        assert text in prompt, text
    # Each kind the prompt names is one the recipe door parses, and the bundle
    # kind it says is closed exists there too.
    assert {"catalog", "graph", "bundle"} == set(construction_recipe.SOURCE_KINDS)
    # The old prompt's one recipe language is gone from the depth edition only.
    assert "A recipe is declarative JSON" not in prompt
    assert "is declarative JSON" in _flat(editions.CONSTRUCTOR_PROMPT)


def test_the_depth_prompts_keep_the_miner_edition_terms():
    for role in editions.DEPTH_EDITION.roles:
        for _, text in role.prompts:
            if role.name != "reader":
                assert "running for the miner" in text
            assert "Carbon's internal" not in text and "Engy" not in text


# --- the driver ------------------------------------------------------------------


def depth_plan():
    name, arguments = record_plan(("arxiv-2401.00002", "shared"))
    item = arguments["hypotheses"][0]
    for field in editions.DEPTH_FIELDS:
        item[field] = depth_hypothesis()[field]
    return name, arguments


@pytest.fixture
def depth_world(tmp_path, monkeypatch):
    """The driver's own fixture world, launched under the depth edition, with
    each session's model selection captured."""
    monkeypatch.setattr(editions, "EDITION_ID", editions.DEPTH_EDITION_ID)

    def build(**graphite):
        w = World(tmp_path, monkeypatch, graphite=graphite)
        w.providers = []
        engine = w.engine

        async def capture(ledger, **keywords):
            w.providers.append((keywords.get("stage"), keywords.get("provider")))
            return await engine(ledger, **keywords)

        monkeypatch.setattr(driver, "run_epoch", capture)
        return w

    return build


def test_a_depth_campaign_plans_and_builds_on_its_role_settings(depth_world):
    w = depth_world(mode="BUILD")
    w.engine.scripts = {
        ("plan", 1): [
            # A v1-shaped plan is refused; the stage goes on.
            [record_plan(("arxiv-2401.00002", "shared"))],
            [depth_plan()],
        ],
        (None, 1): [[practice(RECIPE)], [select(RECIPE)]],
        (None, 2): [STOP_TURN],
    }
    w.run(Transport())
    block = w.prepared.manifest["provider"]["graphite"]
    assert block["edition"] == editions.DEPTH_EDITION_ID
    assert block["edition_digest"] == EDITION_V2_DIGEST
    first = next(r for s, n, r in w.engine.results if n == editions.FINISH)
    assert (first["status"], first["code"]) == (
        "REJECTED_BEFORE_DISPATCH",
        "plan_invalid",
    )
    assert "physics_rationale" in first["reason"]
    planned = w.stage("plan")
    assert planned["status"] == "PLANNED"
    assert planned["plan"]["schema"] == plans.PLAN_SCHEMA_V2
    assert (
        planned["plan"]["hypotheses"][0]["ablation"] == depth_hypothesis()["ablation"]
    )
    assert w.library.plan(planned["plan_digest"]) == planned["plan"]
    # The Planner ran at high with a 600 s timeout; the historical default
    # records no context, so its cap stayed 2,048, and the record says so.
    stages = dict(w.providers[:1])
    assert stages["plan"].settings.reasoning_effort == "high"
    assert stages["plan"].settings.timeout_seconds == 600
    assert planned["role_settings"]["max_output_tokens"]["basis"] == (
        editions.CAP_NO_RECORDED_CONTEXT
    )
    # The Planner was offered the depth finishing tool and prompt.
    call = w.engine.stage_calls("plan")[0]
    assert call["instructions"] == editions.PLANNER_V2.prompt
    assert editions.FINISH_TOOL_V2 in call["tools"]
    assert call["finish"]["tool"] == editions.FINISH_TOOL_V2
    # The Constructor ran at medium, its prompt the depth one.
    builds = [p for s, p in w.providers if s is None]
    assert builds and all(p.settings.reasoning_effort == "medium" for p in builds)
    assert w.engine.stage_calls(None)[0]["instructions"] == (
        editions.CONSTRUCTOR_V2.prompt
    )
    assert w.stage("build")["role_settings"]["reasoning_effort"]["applied"] == (
        "medium"
    )


def test_a_v1_campaign_still_runs_on_the_frozen_selection(tmp_path, monkeypatch):
    w = World(tmp_path, monkeypatch, graphite={"mode": "RESEARCH"})
    providers = []
    engine = w.engine

    async def capture(ledger, **keywords):
        providers.append(keywords.get("provider"))
        return await engine(ledger, **keywords)

    monkeypatch.setattr(driver, "run_epoch", capture)
    w.engine.scripts = {("plan", 1): [[record_plan(("arxiv-2401.00002", "shared"))]]}
    w.run(Transport())
    assert w.prepared.manifest["provider"]["graphite"]["edition_digest"] == (
        EDITION_V1_DIGEST
    )
    assert providers == [None]
    planned = w.stage("plan")
    assert planned["plan"]["schema"] == plans.PLAN_SCHEMA
    assert "role_settings" not in planned


def test_a_stop_at_the_output_cap_is_kept_typed_in_the_stage_record():
    outcome = {
        "status": "STOPPED",
        "code": "replies_truncated",
        "cause": OUTPUT_CAP_HIT,
        "agent_decision": False,
        "output_cap": {"cap": 2048, "turns": [{"turn": "t", "output_tokens": 2048}]},
    }
    assert driver._stopped(outcome) == {
        "code": "replies_truncated",
        "cause": "turn_hit_output_cap",
        "output_cap": outcome["output_cap"],
    }
    assert driver._stopped({"code": "x"}) == {"code": "x"}
