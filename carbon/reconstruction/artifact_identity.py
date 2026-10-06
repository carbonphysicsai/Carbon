"""The build identity of Carbon's rebuilt record: what a construction builds.

OWNER-GRAPHITE-TEST-WAVE-04 §1 (owner, 2026-10-05): anything that counts,
limits, deduplicates or rewards distinct constructions identifies them by the
rebuilt artifact, never by recipe or expression text. Same recipe, same seed
and same pinned trainer give the same artifact.

Carbon's built record (`challenge_validator.scoring.REBUILT_FIELDS`) binds,
besides what the trainer consumes, digests of the submission as written:
`strategy_hash`, `plan_digest` and `recipe_digest` (on the record and in its
`recipe`), and the staged `recipe.json`, which carries `recipe_digest` beside
the family, settings and seed the record already binds. The trainer reads
the recipe's family and settings and the seed (`carbon.battery.worker`:
`recipes.build(family, settings)`, `fit(..., seed)`), never those digests. So
two recipes that differ only in how they are written (a default setting made
explicit, for example) build the same model but carry different record
digests.

`build_identity(record)` is the digest of everything the record binds with
those provenance fields left out: the Challenge, the contract, the recipe's
family and settings, every other staged file, the program, the seed, the
record sequence and any development binding. Challenge-neutral; Graphite's
delivery bundles and the attack engine read it from here, so the miner paths
never reach the attack package to compute it.
"""

from __future__ import annotations

from collections.abc import Mapping

from carbon.development_session.profile import canonical, digest

SCHEMA = "carbon.reconstruction.build-identity.v1"
#: Built-record fields that digest the submission as written, not what is built.
PROVENANCE_FIELDS = ("strategy_hash", "plan_digest", "recipe_digest")
#: Staged files that carry a provenance field beside what the record binds.
PROVENANCE_STAGED = ("recipe.json",)


def build_identity(record):
    """The build identity of Carbon's rebuilt record (module docstring), or
    None when the record does not have the built-record shape (`recipe` and
    `staged` mappings)."""
    if not isinstance(record, Mapping):
        return None
    recipe, staged = record.get("recipe"), record.get("staged")
    if not (isinstance(recipe, Mapping) and isinstance(staged, Mapping)):
        return None
    body = {
        key: value
        for key, value in record.items()
        if key not in PROVENANCE_FIELDS and key not in ("recipe", "staged")
    }
    body["recipe"] = {
        key: value for key, value in recipe.items() if key not in PROVENANCE_FIELDS
    }
    body["staged"] = {
        name: value for name, value in staged.items() if name not in PROVENANCE_STAGED
    }
    return digest(canonical({"schema": SCHEMA, "build": body}))
