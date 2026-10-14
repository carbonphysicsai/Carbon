"""Synthetic block-unit controls, not evidence of physical independence/power."""

from __future__ import annotations

import copy

import pytest

from scripts.dev.score_lab import campaign_blocks as blocks
from scripts.dev.score_lab import core


def _fixture(count=4, size=3, policy="EXCLUDE_COMPLETE_BLOCKS"):
    groups = {f"b-{b}": [f"V-{b:02d}-{q}" for q in range(size)] for b in range(count)}
    questions = {q: {} for group in groups.values() for q in group}
    members = []
    for name, values, error, kind in (
        ("a", (0.0, 4.0, 0.0), 0.1, "MODEL"),
        ("b", (1.0, 0.0, 4.0), 0.2, "MODEL"),
        ("c", (4.0, 1.0, 1.0), 0.3, "MODEL"),
        ("control", (4.0, 4.0, 4.0), 0.4, "PROBE"),
    ):
        members.append(
            {
                "id": name,
                "recipe": name,
                "kind": kind,
                "score_predictions": {"S": {"a": error}},
                "score_row": {"E": error},
                "value_losses": {
                    q: values[b % 3]
                    for b, group in enumerate(groups.values())
                    for q in group
                },
            }
        )
    panel = {
        "schema": core.SCHEMA,
        "scope": "SYNTHETIC_DEVELOPMENT",
        "score_questions": {"S": {}},
        "value_questions": questions,
        "members": members,
        "exact_oracle_losses": {q: 0.0 for q in questions},
    }
    spec = {
        "schema": blocks.SCHEMA,
        "label": "ASSUMPTION: fixture block independence only",
        "groups": groups,
        "missing_policy": policy,
    }
    return panel, spec


def _score(predictions, references, metadata):
    assert set(predictions) == set(references) == {"S"}
    assert set(metadata) == {"score_row"}
    return {
        "score": 1 / (1 + metadata["score_row"]["E"]),
        "admissible": metadata["score_row"]["E"] < 0.4,
    }


def test_default_path_never_calls_block_preparation_and_is_identical(monkeypatch):
    panel, _ = _fixture()
    expected = core.analyze(panel, _score, bootstrap=20, seed=7)

    def forbidden(*args):
        pytest.fail("default path entered synthetic block logic")

    monkeypatch.setattr(blocks, "prepare", forbidden)
    assert (
        core.analyze(panel, _score, bootstrap=20, seed=7, value_blocks=None) == expected
    )


def test_actual_bootstrap_receives_block_columns_and_preserves_point_mean(monkeypatch):
    panel, spec = _fixture()
    before = copy.deepcopy(panel)
    expected = core.analyze(panel, _score, bootstrap=30, seed=7)
    original = core.score_proof.bootstrap
    seen = []

    def spy(scores, base, losses, recipes, members, **kwargs):
        seen.append(copy.deepcopy(losses))
        return original(scores, base, losses, recipes, members, **kwargs)

    monkeypatch.setattr(core.score_proof, "bootstrap", spy)
    result = core.analyze(panel, _score, value_blocks=spec, bootstrap=30, seed=7)
    assert len(seen) == 1
    assert all(len(losses) == 4 for losses in seen[0].values())
    assert sorted(seen[0]["a"]) == [0.0, 0.0, 0.0, 4.0]
    for key in (
        "tau",
        "top1_member",
        "admissibility",
        "ranked_scores",
        "physics_tiers",
    ):
        assert result[key] == expected[key]
    assert result["top1_regret"] == pytest.approx(expected["top1_regret"])
    assert result["admissibility_failures"] == expected["admissibility_failures"] == 1
    assert result["value_questions"] == result["value_questions_offered"] == 12
    assert result["value_resampling_units"] == 4
    assert result["value_block_measurement"]["scored_blocks"] == 4
    assert panel == before


def test_common_block_exclusion_includes_controls_and_discloses_lost_resolved_cases():
    panel, spec = _fixture()
    panel["members"][0]["value_losses"]["V-00-0"] = None
    panel["members"][-1]["value_losses"]["V-00-1"] = None
    calls = []

    def score(*args):
        calls.append(1)
        return _score(*args)

    result = core.analyze(panel, score, value_blocks=spec, bootstrap=15)
    assert len(calls) == 4
    assert result["status"] == "MEASURED_DEVELOPMENT"
    assert result["value_questions"] == 9
    assert result["value_questions_offered"] == 12
    assert result["value_resampling_units"] == 3
    receipt = result["value_block_measurement"]
    assert receipt["unresolved_questions"] == 2
    assert receipt["incomplete_blocks"] == 1
    assert receipt["resolved_questions_in_incomplete_blocks"] == 1
    assert receipt["scored_questions"] == 9
    assert receipt["scored_blocks"] == 3
    assert (
        receipt["estimand"]
        == "uniform_questions_conditional_on_complete_equal_size_blocks"
    )
    # Independently analyze the nine retained original cases, not block means.
    retained = copy.deepcopy(panel)
    keep = {q for q in panel["value_questions"] if not q.startswith("V-00-")}
    retained["value_questions"] = {q: retained["value_questions"][q] for q in keep}
    retained["exact_oracle_losses"] = {
        q: retained["exact_oracle_losses"][q] for q in keep
    }
    for member in retained["members"]:
        member["value_losses"] = {q: member["value_losses"][q] for q in keep}
    expected = core.analyze(retained, _score, bootstrap=15)
    assert result["top1_member"] == expected["top1_member"]
    assert result["top1_regret"] == pytest.approx(expected["top1_regret"])
    assert result["tau"] == expected["tau"]


@pytest.mark.parametrize("policy", sorted(blocks.POLICIES))
def test_insufficient_complete_blocks_never_call_the_scorer(policy):
    panel, spec = _fixture(policy=policy)
    panel["members"][0]["value_losses"]["V-00-0"] = None
    panel["members"][1]["value_losses"]["V-01-0"] = None

    def forbidden(*args):
        pytest.fail("insufficient independent units invoked scorer")

    result = core.analyze(panel, forbidden, value_blocks=spec)
    assert result["status"] == "INSUFFICIENT_EVIDENCE"
    assert result["reason"] == "value_blocks_below_planned_range"
    assert "admissibility_failures" not in result
    assert "tau" not in result
    assert result["value_block_measurement"]["complete_blocks_available"] == 2
    assert result["value_block_measurement"]["scored_blocks"] == 0


def test_require_complete_refuses_even_when_three_complete_blocks_remain():
    panel, spec = _fixture(policy="REQUIRE_COMPLETE")
    panel["members"][0]["value_losses"]["V-00-0"] = None

    def forbidden(*args):
        pytest.fail("strict incomplete measurement invoked scorer")

    result = core.analyze(panel, forbidden, value_blocks=spec)
    assert result["reason"] == "value_blocks_incomplete"
    assert result["value_block_measurement"]["complete_blocks_available"] == 3
    assert result["value_block_measurement"]["scored_questions"] == 0


@pytest.mark.parametrize("policy", sorted(blocks.POLICIES))
@pytest.mark.parametrize("missing_blocks", [0, 1, 2])
def test_bootstrap_zero_refuses_consistently_before_scoring(policy, missing_blocks):
    panel, spec = _fixture(policy=policy)
    for index in range(missing_blocks):
        panel["members"][0]["value_losses"][f"V-{index:02d}-0"] = None

    def forbidden(*args):
        pytest.fail("invalid bootstrap count invoked scorer")

    with pytest.raises(core.LabRefused, match="^bootstrap_count$"):
        core.analyze(panel, forbidden, value_blocks=spec, bootstrap=0)
    with pytest.raises(core.LabRefused, match="^bootstrap_count$"):
        core.analyze(panel, forbidden, bootstrap=0)


@pytest.mark.parametrize("policy", sorted(blocks.POLICIES))
def test_valid_bootstrap_keeps_incomplete_measurement_unscored(policy):
    panel, spec = _fixture(policy=policy)
    for index in range(2):
        panel["members"][0]["value_losses"][f"V-{index:02d}-0"] = None

    def forbidden(*args):
        pytest.fail("valid but unresolved block measurement invoked scorer")

    result = core.analyze(panel, forbidden, value_blocks=spec, bootstrap=1)
    assert result["status"] == "INSUFFICIENT_EVIDENCE"
    assert result["value_block_measurement"]["scored_blocks"] == 0


@pytest.mark.parametrize("count", [3, 30])
def test_planned_block_count_endpoints_and_deterministic_replay(count):
    panel, spec = _fixture(count=count, size=2)
    first = core.analyze(panel, _score, value_blocks=spec, bootstrap=10, seed=13)
    assert first == core.analyze(
        panel, _score, value_blocks=spec, bootstrap=10, seed=13
    )
    assert first["value_questions"] == 2 * count
    assert first["value_resampling_units"] == count


@pytest.mark.parametrize("count", [2, 31])
def test_outside_planned_block_count_range_refuses(count):
    panel, spec = _fixture(count=count)
    with pytest.raises(core.LabRefused, match="value_blocks_spec"):
        core.analyze(panel, _score, value_blocks=spec)


@pytest.mark.parametrize("corruption", ["duplicate", "missing", "unknown", "unequal"])
def test_partition_defects_refuse_instead_of_silently_reweighting(corruption):
    panel, spec = _fixture()
    if corruption == "duplicate":
        spec["groups"]["b-0"][0] = spec["groups"]["b-1"][0]
    elif corruption == "missing":
        spec["groups"]["b-0"].pop()
    elif corruption == "unknown":
        spec["groups"]["b-0"][0] = "V-does-not-exist"
    else:
        spec["groups"]["b-0"].append(spec["groups"]["b-1"].pop())
    with pytest.raises(core.LabRefused, match="value_blocks_(partition|unequal_sizes)"):
        core.analyze(panel, _score, value_blocks=spec)


@pytest.mark.parametrize(
    "change",
    [
        {"schema": "production"},
        {"label": "adopted"},
        {"groups": []},
        {"missing_policy": []},
        {"missing_policy": "PENALIZE"},
        {"weight": 1.0},
    ],
)
def test_unregistered_settings_refuse(change):
    panel, spec = _fixture()
    with pytest.raises(core.LabRefused, match="value_blocks_spec"):
        core.analyze(panel, _score, value_blocks=spec | change)


def test_public_panels_and_nonfinite_data_refuse():
    panel, spec = _fixture()
    panel["scope"] = "PUBLIC_DEVELOPMENT"
    with pytest.raises(core.LabRefused, match="require_synthetic"):
        core.analyze(panel, _score, value_blocks=spec)
    panel["scope"] = "SYNTHETIC_DEVELOPMENT"
    panel["members"][0]["value_losses"]["V-00-0"] = float("nan")
    with pytest.raises(core.LabRefused, match="nonfinite_loss"):
        core.analyze(panel, _score, value_blocks=spec)


@pytest.mark.parametrize("oracle", [None, "partial"])
def test_missing_optional_oracle_is_not_imputed(oracle):
    panel, spec = _fixture()
    if oracle is None:
        panel["exact_oracle_losses"] = None
    else:
        panel["exact_oracle_losses"]["V-00-0"] = None
    result = core.analyze(panel, _score, value_blocks=spec, bootstrap=10)
    assert result["top1_regret_reference"] == "BEST_MEMBER_IN_POOL"


def test_nonfinite_oracle_and_colliding_block_identity_refuse():
    panel, spec = _fixture()
    panel["exact_oracle_losses"]["V-00-0"] = float("inf")
    with pytest.raises(core.LabRefused, match="nonfinite_oracle"):
        core.analyze(panel, _score, value_blocks=spec)
    panel, spec = _fixture()
    unit = "BLOCK-V-" + core.canonical_sha(sorted(spec["groups"]["b-0"]))
    panel["score_questions"][unit] = panel["score_questions"].pop("S")
    for member in panel["members"]:
        member["score_predictions"][unit] = member["score_predictions"].pop("S")
    with pytest.raises(core.LabRefused, match="identity_collision"):
        core.analyze(panel, _score, value_blocks=spec)
