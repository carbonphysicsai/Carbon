"""Direct recipe identity does not depend on legacy level or family policy."""

import copy
import json

import pytest

from carbon.development_session.construction_recipe import (
    ConstructionRecipe,
    RecipeRefused,
    bind_recipe,
    graph_envelope_from_workspace,
    graph_workspace,
)


def sha(char):
    return "sha256:" + char * 64


def graph_recipe():
    return {
        "schema": "carbon.construction-recipe.v1",
        "challenge": {
            "id": "battery-example",
            "version": "development-v1",
            "train_digest": sha("a"),
            "interface_digest": sha("b"),
            "construction_limits_digest": sha("c"),
        },
        "source": {"kind": "graph", "submission_digest": sha("d")},
        "procedure": {
            "entrypoint": None,
            "configuration": {"graph_parameters": {"unlisted_topology": [3, 7, 2]}},
            "train_use": {"subset": "all", "order": "recipe_defined"},
            "initial_state": None,
        },
        "output": {"format": "carbon.numeric-graph.v1", "interface_digest": sha("b")},
    }


def bind(value):
    return bind_recipe(
        value,
        challenge_id="battery-example",
        challenge_version="development-v1",
        train_digest=sha("a"),
        interface_digest=sha("b"),
        construction_limits_digest=sha("c"),
    )


def test_non_catalogue_graph_has_stable_direct_identity():
    value = graph_recipe()
    parsed = bind(value)
    assert parsed.to_dict() == value
    assert (
        ConstructionRecipe.from_bytes(
            json.dumps(value, sort_keys=False).encode()
        ).digest
        == parsed.digest
    )
    assert "level" not in parsed.to_dict()
    assert "family" not in parsed.to_dict()
    assert "catalogue" not in parsed.to_dict()
    assert "combination" not in parsed.to_dict()
    with pytest.raises(AttributeError):
        parsed._raw = b"changed"


def test_bundle_source_uses_exact_inert_ref_without_name_permission():
    value = graph_recipe()
    value["source"] = {
        "kind": "bundle",
        "bundle_ref": {
            "schema": "carbon.library-bundle-ref.v1",
            "bundle_digest": sha("d"),
            "language": "python",
            "runtime_profile_id": "some-pinned-runtime",
            "environment_digest": sha("e"),
        },
    }
    value["procedure"]["entrypoint"] = {"module": "candidate.model", "name": "build"}
    assert bind(value).to_dict()["source"] == value["source"]


@pytest.mark.parametrize(
    "field", ["train_digest", "interface_digest", "construction_limits_digest"]
)
def test_registered_identity_mismatch_refuses(field):
    value = graph_recipe()
    value["challenge"][field] = sha("e")
    if field == "interface_digest":
        value["output"]["interface_digest"] = sha("e")
    with pytest.raises(RecipeRefused, match="construction_recipe_binding_mismatch"):
        bind(value)


def test_legacy_permission_and_trained_state_fields_are_not_recipe_fields():
    for key in ("level", "family", "catalogue", "combination", "checkpoint"):
        value = graph_recipe()
        value[key] = "untrusted"
        with pytest.raises(RecipeRefused, match="construction_recipe_malformed"):
            bind(value)


def test_graph_cannot_import_host_entrypoint_and_bundle_needs_one():
    value = graph_recipe()
    value["procedure"]["entrypoint"] = {"module": "candidate", "name": "build"}
    with pytest.raises(RecipeRefused, match="construction_recipe_procedure_invalid"):
        bind(value)


def test_submitted_initial_state_is_forbidden():
    value = graph_recipe()
    value["procedure"]["initial_state"] = sha("f")
    with pytest.raises(
        RecipeRefused, match="construction_recipe_pretrained_state_forbidden"
    ):
        bind(value)
    value["source"] = {
        "kind": "bundle",
        "bundle_ref": {
            "schema": "carbon.library-bundle-ref.v1",
            "bundle_digest": sha("d"),
            "language": "python",
            "runtime_profile_id": "pinned",
            "environment_digest": sha("e"),
        },
    }
    value["procedure"]["entrypoint"] = None
    with pytest.raises(RecipeRefused, match="construction_recipe_procedure_invalid"):
        bind(value)


def test_changed_procedure_changes_digest_and_input_is_copied():
    value = graph_recipe()
    first = bind(value)
    other = copy.deepcopy(value)
    other["procedure"]["train_use"]["order"] = "reverse"
    assert bind(other).digest != first.digest
    value["procedure"]["train_use"]["order"] = "changed_after_parse"
    assert first.to_dict()["procedure"]["train_use"]["order"] == "recipe_defined"


def test_duplicate_json_key_and_nonfinite_number_refuse():
    raw = json.dumps(graph_recipe()).replace(
        '"schema": "carbon.construction-recipe.v1",',
        '"schema": "carbon.construction-recipe.v1", "schema": "carbon.construction-recipe.v1",',
        1,
    )
    with pytest.raises(RecipeRefused, match="construction_recipe_malformed"):
        ConstructionRecipe.from_bytes(raw.encode())
    value = graph_recipe()
    value["procedure"]["configuration"] = {"learning_rate": float("nan")}
    with pytest.raises(RecipeRefused, match="construction_recipe_malformed"):
        bind(value)


def test_graph_bytes_bind_exact_submission_before_semantic_checks():
    from carbon.level4 import staging, submission

    raw = b"{}"
    value = graph_recipe()
    value["source"]["submission_digest"] = submission.name(raw)
    recipe = bind(value)
    assert graph_workspace(recipe, raw, {}, max_bytes=128) == staging.workspace(raw, {})
    with pytest.raises(
        RecipeRefused, match="construction_recipe_graph_digest_mismatch"
    ):
        graph_workspace(recipe, b"{ }", {}, max_bytes=128)
    with pytest.raises(RecipeRefused, match="construction_recipe_graph_bytes_invalid"):
        graph_workspace(recipe, raw, {}, max_bytes=1)


def test_graph_source_resolves_only_the_owner_workspace_and_exact_digest(tmp_path):
    from carbon.development_session.research_ledger import VERSION, CampaignLedger
    from carbon.development_session.research_workspace import ResearchWorkspace
    from carbon.level4 import staging, submission

    ledger = CampaignLedger(tmp_path / "campaign")
    ledger.freeze(
        {
            "schema": VERSION,
            "ceilings": {},
            "elapsed_seconds": None,
            "campaign_id": "direct-graph-workspace-test",
            "implementation": "fixture",
            "objective": "fixture",
            "sampling": "fixture",
            "control": "none",
            "selection": "none",
            "replica_policy": "fixture",
            "provider": "none",
            "owner": "alice",
        }
    )
    raw = b'{"documents":{}}'
    value = graph_recipe()
    value["source"]["submission_digest"] = submission.name(raw)
    recipe = bind(value)
    ResearchWorkspace(ledger, "alice").put(staging.WORKSPACE_MANIFEST, raw)
    envelope = graph_envelope_from_workspace(ledger, "alice", recipe)
    assert staging.from_envelope(json.loads(envelope)) == (
        value["source"]["submission_digest"],
        raw,
        {},
    )
    with pytest.raises(RecipeRefused, match="graph_workspace_missing"):
        graph_envelope_from_workspace(ledger, "bob", recipe)
    wrong = graph_recipe()
    wrong["source"]["submission_digest"] = sha("0")
    with pytest.raises(RecipeRefused, match="graph_digest_mismatch"):
        graph_envelope_from_workspace(ledger, "alice", bind(wrong))
