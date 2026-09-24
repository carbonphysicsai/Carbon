"""Can I submit this design? One verdict per choice, from the registry.

Claims tested: each kind of choice gets the verdict its registry entry implies;
the overall verdict is the most restrictive item's; a design is compiled only
when every choice is rebuildable, and then by the validator's own compiler; text
a miner supplied that Carbon does not recognize is never repeated back; and the
action reaches a miner through the real workspace executor, listed from the one
canonical action list.
"""

import json

import pytest

from carbon.development_session.design_check import check_design
from carbon.development_session.research_catalog import compile_recipe
from carbon.research.model import DEVELOPMENT_WORKSPACE_ACTIONS


def strategy(backbone="fno", **parameters):
    return {
        "schema_version": "1.0",
        "challenge_id": "burgers-dynamics-v1",
        "backbone": backbone,
        "parameters": parameters,
    }


def check(backbone="fno", capabilities=None, **parameters):
    design = {"strategy": strategy(backbone, **parameters)}
    if capabilities is not None:
        design["capabilities"] = capabilities
    return check_design(design)


def test_a_rebuildable_design_is_submittable_with_what_carbon_would_rebuild():
    result = check("transolver", width=32, heads=4)
    assert result["verdict"] == "submittable"
    assert result["qualification"] is False
    rebuild = result["rebuild"]
    assert rebuild["accepted"] is True
    # The canonical design is the validator compiler's own resolution.
    _, profile = compile_recipe(strategy("transolver", width=32, heads=4))
    assert rebuild["implementation"]["profile_digest"] == profile.profile_digest
    assert rebuild["implementation"]["backbone_id"] == "carbon_jax_transolver1d"
    assert rebuild["canonical"]["heads"] == {"value": 4, "source": "selected"}
    assert rebuild["canonical"]["slices"]["source"] == "defaulted"


@pytest.mark.parametrize(
    "capability,verdict,extra",
    [
        ("optimizer.lion", "not_yet_rebuildable", {"blocker": "engineering"}),
        (
            "inference.precision",
            "needs_owner_decision",
            {"trigger": "new_comparison_or_resource_regime"},
        ),
        (
            "model_family.pretrained_weights",
            "excluded",
            {"trigger": "external_data_or_learned_state"},
        ),
        ("architecture.heads", "submittable", {}),
    ],
)
def test_a_requested_capability_is_answered_from_the_registry(
    capability, verdict, extra
):
    result = check("transolver", capabilities=[capability])
    assert result["verdict"] == verdict
    item = result["requested"][0]
    assert item["capability"] == capability
    for key, value in extra.items():
        assert item[key] == value


def test_the_most_restrictive_choice_decides():
    result = check(
        capabilities=[
            "optimizer.lion",
            "inference.precision",
            "model_family.pretrained_weights",
        ]
    )
    assert result["verdict"] == "excluded"
    assert check(capabilities=["optimizer.lion", "inference.precision"])["verdict"] == (
        "needs_owner_decision"
    )


def test_a_research_only_backbone_is_not_compiled_as_something_else():
    result = check("unet1d")
    assert result["verdict"] == "not_yet_rebuildable"
    assert result["backbone"]["capability"] == "model_family.unet1d"
    # Never downgraded to the nearest supported recipe.
    assert "rebuild" not in result


def test_a_field_another_family_owns_names_its_owner():
    field = check("fno", heads=4)["fields"][0]
    assert field["verdict"] == "refused"
    assert field["reason"] == "not_applicable"
    assert field["families"] == ["transolver"]


def test_rebuild_issues_are_named():
    result = check("gino", n_modes=16, latent_points=8)
    assert result["verdict"] == "refused"
    assert result["rebuild"]["issues"] == [
        {"code": "parameter.dependency_unsatisfied", "path": "/parameters/n_modes"}
    ]


def test_unrecognized_text_is_never_repeated_but_is_located_and_suggested():
    marker = "MINER-PRIVATE-NOTE-7f3a"
    result = check("fno", learnin_rate=0.01, **{marker: 1}, capabilities=[marker])
    text = json.dumps(result)
    assert marker not in text
    assert "learnin_rate" not in text
    # Specimen: the same check does repeat a registered name it recognizes, so
    # the absence above is the rule and not a check that never prints keys.
    registered = json.dumps(check("fno", learning_rate=0.01))
    assert "learning_rate" in registered
    fields = {f["position"]: f for f in result["fields"]}
    # Sorted key order: the marker sorts before learnin_rate.
    assert fields[0]["reason"] == "unrecognized" and fields[0]["nearest"] == []
    assert "learning_rate" in fields[1]["nearest"]
    assert result["requested"][0]["reason"] == "unrecognized"


@pytest.mark.parametrize(
    "design",
    [
        None,
        {},
        {"strategy": strategy(), "extra": 1},
        {"strategy": {"backbone": "fno"}},
        {"strategy": strategy(), "capabilities": "optimizer.lion"},
        {"strategy": strategy(), "capabilities": ["x"] * 257},
    ],
)
def test_a_malformed_request_is_refused(design):
    with pytest.raises(ValueError):
        check_design(design)


def test_every_layer_lists_actions_from_the_one_canonical_list():
    from carbon.development_session import research_material, research_tools
    from carbon.development_session.research_tasks import PublicResearchExecutor

    assert "check_design" in DEVELOPMENT_WORKSPACE_ACTIONS
    schema = research_tools.FIELDS["start_research_task"]["action"]["enum"]
    assert schema == [*DEVELOPMENT_WORKSPACE_ACTIONS, None]
    material = research_material.capabilities()["workspace_actions"]
    assert material == list(DEVELOPMENT_WORKSPACE_ACTIONS)
    # The executor has a branch for every listed action.
    import inspect

    source = inspect.getsource(PublicResearchExecutor._workspace_action)
    for action in DEVELOPMENT_WORKSPACE_ACTIONS:
        assert f'"{action}"' in source, action


def test_check_design_runs_through_the_real_workspace_executor(tmp_path):
    from test_cw1_research_tasks import compose, request

    from carbon import research

    f, p, e = compose(tmp_path)
    design = {"strategy": strategy("transolver", width=32, heads=4)}
    task = p.start_research_task(request(f, "check_design", {"design": design})).task
    done = p.run_queued_task(task.task_id)
    assert done.state is research.ResearchTaskState.SUCCEEDED
    assert e.public_result(done)["result"]["verdict"] == "submittable"
    # Compile-only: it charges no research trial and runs nothing.
    assert e.ledger.status(owner="test-miner")["used"].get("research_trials", 0) == 0
    p.close()
