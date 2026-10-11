"""A panel member compiled at its OWN construction level (LEVEL-AWARE-PROOF-01).

The decision experiment verifies each retained prediction bundle against the recipe the
frozen panel names: the bundle's `recipe_digest` must be one of the digests its strategy
compiles to under a registered implementation version. That check compiled every member
at Level 0, which refuses a Level 1 to 3 strategy (its widened fields are outside the Level
0 contract). A level member is compiled the way the level's own pod phase compiled it:
`compile_development` under the level's registered variant, then the Level 0 base
(the strategy less the fields the variant widens) for the recipe whose digest the bundle
carries.

Nothing about the decision values changes: they are computed from the bundle's stored
predictions and the sealed references exactly as Level 0's are. The Level 0 path here is
the experiment's old expression, unchanged. DEVELOPMENT only: it imports the variant
module lazily and nothing a miner surface imports imports this module.
"""

from __future__ import annotations

from .panel import CHALLENGE_ID

LEVEL_REFUSED = "level_compile_refused"


class LevelCompileRefused(ValueError):
    """The strategy does not compile at the level its member names."""

    def __init__(self, level, detail):
        super().__init__(f"{LEVEL_REFUSED}: level {level}: {detail}")
        self.level, self.detail = level, detail


def base_strategy(strategy, widened):
    """The strategy less the fields its level widens: its Level 0 base."""
    parameters = strategy.get("parameters")
    if type(parameters) is not dict:
        return dict(strategy)
    return {
        **strategy,
        "parameters": {k: v for k, v in parameters.items() if k not in set(widened)},
    }


def base_for(strategy, level=0, arm=None, *, challenge=CHALLENGE_ID):
    """The Level 0 strategy a member of `level` rebuilds as its recipe: the strategy
    itself at Level 0. Raises `LevelCompileRefused`."""
    if not level:
        return strategy
    from carbon.reconstruction import development_variants as dv
    from carbon.reconstruction.challenge_contracts import SubmissionRefused

    try:
        variant = dv.variant(challenge, level, arm)
        compiled = dv.compile_development(strategy, variant, check_budget=False)
    except (dv.VariantRefused, SubmissionRefused) as refused:
        raise LevelCompileRefused(level, type(refused).__name__) from None
    return base_strategy(strategy, compiled.widened)


def recipe_digests(strategy, *, versions, level=0, arm=None, challenge=CHALLENGE_ID):
    """Every recipe digest a member's bundle may carry: one per registered
    implementation version (a bundle verifies under the version it was made under)."""
    from ..compile import compile_recipe

    base = base_for(strategy, level, arm, challenge=challenge)
    return {
        compile_recipe(base, implementation=version)[1].recipe_digest
        for version in versions
    }
