"""compile_strategy on a catalog version (M1 E2E 2026-10-22, F2).

Graphite's Build on Motor 1.3 looped dry_validate / compile_strategy on the
legacy Strategy 1.0 shape and never practised: the Level-0 compile refused
every construction recipe and taught the wrong shape. S22 made dry_validate
answer with the version's recipe rule; compile_strategy now does too, and a
recipe that binds is told there is no Level-0 compile and to practise it."""

from __future__ import annotations

from carbon import research
from carbon.challenge_registry.motor import catalog_recipe
from carbon.development_session.research_service import (
    CATALOG_RECIPE_NOT_COMPILED,
    ConstructionRecipeCompilation,
    takes_construction_recipes,
)

KEY = research.ChallengeKey("electric-motor-magnetics", "1.3")
SUPPORT = None


def _compile(strategy):
    request = research.CompileStrategyRequest.__new__(research.CompileStrategyRequest)
    object.__setattr__(request, "challenge_key", KEY)
    object.__setattr__(request, "strategy", strategy)
    return ConstructionRecipeCompilation(KEY).compile_strategy(request)


def test_motor_1_3_takes_construction_recipes():
    assert takes_construction_recipes(KEY)


def test_a_binding_recipe_is_told_to_practise_not_compiled():
    result = _compile(catalog_recipe("neuralop.FNO", version="1.3"))
    assert result.accepted is False
    assert [issue.code for issue in result.issues] == [CATALOG_RECIPE_NOT_COMPILED]
    assert "kind=practice" in result.issues[0].message


def test_a_legacy_strategy_gets_the_recipe_rule_not_the_level_0_shape():
    legacy = {
        "schema_version": "1.0",
        "challenge_id": "electric-motor-magnetics",
        "backbone": "neuralop.fno",
        "parameters": {},
    }
    result = _compile(legacy)
    assert result.accepted is False
    codes = [issue.code for issue in result.issues]
    assert codes and CATALOG_RECIPE_NOT_COMPILED not in codes
    assert all("Strategy schema version" not in i.message for i in result.issues)
