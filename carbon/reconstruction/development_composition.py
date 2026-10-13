"""One construction contract over the whole 0-4 plan (CONSTRUCTION-CONTRACT-01).

The owner, 2026-10-13: "a construction contract that can rebuild anything at all
on our 0-4 plan." A strategy may use the fields of any development level, in
any combination. Carbon rebuilds it, or refuses it and names what it could not
rebuild. The level is derived from what the strategy uses and reported in plain
words; it never decides what may be submitted.

**A composition, not a new level.** A registered composition document
(`development_compositions/`) names the current variant of each level by its
version and digest. Compiling under it routes every widened field to its own
variant: the variant's bounds, applicability and reconstruction are applied
exactly as `development_variants.compile_development` applies them, so each
field keeps its own containment. Level 1's expressions compile under its
operation set; Level 3's fields stay menu choices; Level 4's graph keeps its
gates. Nothing is widened that a registered variant did not already widen.
The base fields compile once, through `compile_submission`, against the base
contract every composed variant shares.

**The rebuild is the gate.** After the fields compile, the development rebuild
is asked for the construction's record (`development_rebuild.record`). A
combination it cannot rebuild yet is refused with
`construction_rebuild_unavailable`, naming the fields. It is never let through
unrebuilt, and never refused because of its level.

**Compute stays bounded.** A combination is costed as the composed rebuild
trains it (`check_compute_budget(level=COMPOSED)`); a cost that cannot be
calculated is refused, as every development recipe's is.

Registered variants v1-v3 and the base contract are not changed: a composition
is a new, prospective document beside them. DEVELOPMENT only.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from carbon.reconstruction import development_variants as dv

SCHEMA = "carbon.development-composition.v1"
COMPOSED = "composed"
DIRECTORY = Path(__file__).with_name("development_compositions")
UNAVAILABLE = "construction_rebuild_unavailable"
UNREGISTERED = "composition_unregistered"
MALFORMED = "composition_malformed"
_KEYS = {
    "schema",
    "version",
    "challenge",
    "scope",
    "authority",
    "review",
    "participant_code",
    "base_contract",
    "composes",
}

#: Plain words for each field a strategy may change, as a miner would say it.
CHANGES = {
    "loss_expressions": "its own loss expression",
    "muon_spectral": "the SpecMuon optimizer",
    "pool_selection": "a selection from the training-data pool",
    "quasi_newton_family": "a quasi-Newton polish routine",
    "line_search": "a polish line search",
    "composition_graphs": "its own model graph",
}
#: What each derived level means, in plain words (`ladder.py`'s 0-4 plan).
LEVEL_WORDS = {
    0: "the standard recipe settings",
    1: "a bounded loss expression",
    2: "the optimizer or the training data",
    3: "training-time numerics",
    4: "its own architecture, as a graph",
}


@dataclass(frozen=True)
class Composition:
    """A registered composition: the variant of each level it composes."""

    version: str
    challenge: str
    digest: str
    variants: tuple
    base_contract_digest: str
    base_record_sequence: int

    def fields(self):
        """Every widened field, by name: `(variant, widened)`. A field two
        composed variants both widen is a malformed composition."""
        found = {}
        for variant in self.variants:
            for name, widened in variant.fields().items():
                if name in found:
                    raise dv.VariantRefused(MALFORMED, "two variants widen " + name)
                found[name] = (variant, widened)
        return found


def _registry(directory):
    path = Path(directory) / "registry.json"
    registry = json.loads(path.read_text(encoding="utf-8"))
    if set(registry) != {"schema", "versions", "current"}:
        raise dv.VariantRefused(MALFORMED, "registry keys")
    return registry


def load(challenge, version=None, directory=None):
    """The registered composition for `challenge` (its current one, or
    `version`), checked against its registered digest, and every variant it
    names checked as registered, current-or-pinned, and on its base contract."""
    directory = DIRECTORY if directory is None else Path(directory)
    registry = _registry(directory)
    if version is None:
        version = registry["current"].get(challenge)
    if version not in registry["versions"]:
        raise dv.VariantRefused(UNREGISTERED, str(version))
    document = json.loads((directory / (version + ".json")).read_text(encoding="utf-8"))
    digest = dv.digest_of(document)
    if digest != registry["versions"][version]:
        raise dv.VariantRefused(UNREGISTERED, version + ": document changed")
    if set(document) != _KEYS or document["schema"] != SCHEMA:
        raise dv.VariantRefused(MALFORMED, "exact composition keys required")
    if document["version"] != version or document["challenge"] != challenge:
        raise dv.VariantRefused(MALFORMED, "version and challenge")
    if document["scope"] != "DEVELOPMENT" or document["participant_code"] is not False:
        raise dv.VariantRefused(MALFORMED, "scope")
    base = document["base_contract"]
    variants, levels = [], set()
    for entry in document["composes"]:
        found = dv.registered(entry["digest"], challenge)
        if found is None or found.version != entry["version"]:
            raise dv.VariantRefused(UNREGISTERED, str(entry.get("version")))
        if found.level != entry["level"] or found.level in levels:
            raise dv.VariantRefused(MALFORMED, "one variant per level")
        if found.base_contract_digest != base["digest"]:
            raise dv.VariantRefused(
                MALFORMED, found.version + ": another base contract"
            )
        levels.add(found.level)
        variants.append(found)
    composition = Composition(
        version=version,
        challenge=challenge,
        digest=digest,
        variants=tuple(sorted(variants, key=lambda v: v.level)),
        base_contract_digest=base["digest"],
        base_record_sequence=base["record_sequence"],
    )
    composition.fields()  # a field widened twice is malformed
    return composition


def describe(levels_used, names):
    """The derived level and the changes, in plain words. Descriptive only."""
    level = max(levels_used, default=0)
    changes = [CHANGES.get(name, name) for name in sorted(names)]
    if not changes:
        summary = "Level 0: " + LEVEL_WORDS[0] + "."
    else:
        summary = (
            f"Level {level} ({LEVEL_WORDS[level]}): this recipe changes "
            + ", ".join(changes)
            + "."
        )
    return {"level": level, "changes": changes, "summary": summary}


@dataclass(frozen=True)
class CompiledComposition:
    """One strategy compiled under a composition: the base compiled as
    `compile_submission` compiles it, each widened value with Carbon's
    reconstruction of it, and the development record the rebuild trains."""

    challenge: str
    contract_digest: str
    compiled: object
    construction: object
    composition_digest: str
    variants: dict
    widened: dict
    reconstruction: dict
    derived: dict
    record: object = field(default=None)

    @property
    def level(self):
        """The derived level: a label, never a permission."""
        return self.derived["level"]

    @property
    def development(self):
        """The binding a built record carries beside the base fields."""
        return {
            "composition_digest": self.composition_digest,
            "variants": dict(self.variants),
            "level": self.derived["level"],
            "changes": list(self.derived["changes"]),
            "widened_digest": dv.digest_of(
                {"widened": self.widened, "reconstruction": self.reconstruction}
            ),
        }


def compile(strategy, composition=None, *, check_budget=True):
    """Compile `strategy` under `composition` (battery's current one if None).

    Each widened field goes to its own variant's bounds and reconstruction, the
    rest to the base contract, and the rebuild is asked for the record it
    trains. Raises `dv.VariantRefused` (`construction_rebuild_unavailable`
    naming the fields it could not rebuild, or a field's own refusal), or the
    base path's `SubmissionRefused` and `RecipeRejected`."""
    from carbon.battery import composed_worker, development_rebuild
    from carbon.reconstruction.challenge_contracts import compile_submission

    if type(strategy) is not dict:
        raise dv.VariantRefused(dv.PARAMETER_REFUSED, "strategy is an object")
    if composition is None:
        composition = load(strategy.get("challenge_id"))
    if strategy.get("challenge_id") != composition.challenge:
        raise dv.VariantRefused(dv.WRONG_CHALLENGE)
    fields = composition.fields()
    for name, (variant, widened) in fields.items():
        if (composition.challenge, widened.capability_id) not in dv.RECONSTRUCTIONS:
            raise dv.VariantRefused(dv.RECONSTRUCTION_MISSING, widened.capability_id)
    parameters = strategy.get("parameters")
    base, values = dict(strategy), {}
    if type(parameters) is dict:
        values = {k: v for k, v in parameters.items() if k in fields}
        base["parameters"] = {k: v for k, v in parameters.items() if k not in fields}
    issues = []
    backbone = strategy.get("backbone")
    for name in sorted(values):
        _variant, widened = fields[name]
        path = "/parameters/" + name
        if not widened.within(values[name]):
            issues.append(("development.out_of_bounds", path))
        elif widened.applies_to is not None and backbone not in widened.applies_to:
            issues.append(("development.not_applicable", path))
    if issues:
        raise dv.VariantRefused(dv.PARAMETER_REFUSED, issues=issues)
    admitted = compile_submission(
        base, contract_digest=composition.base_contract_digest
    )
    reconstruction, used = {}, {}
    for name in sorted(values):
        variant, widened = fields[name]
        build = dv.RECONSTRUCTIONS[(composition.challenge, widened.capability_id)]
        built = build(values[name], admitted, frozenset(variant.permissions()))
        carried = dv.RECORD_BOUNDS.get(
            (composition.challenge, widened.capability_id), ()
        )
        if carried and isinstance(built, dict):
            bounds = json.loads(widened.bounds_json)
            built = {**built, **{k: bounds[k] for k in carried if k in bounds}}
        reconstruction[widened.capability_id] = built
        used[variant.level] = variant.digest
    try:
        dv._canonical(values)
        dv._canonical(reconstruction)
    except (TypeError, ValueError):
        raise dv.VariantRefused(dv.PARAMETER_REFUSED, "values are plain JSON") from None
    try:
        record = development_rebuild.record(reconstruction)
    except composed_worker.RebuildUnavailable as unavailable:
        names = [name for name in sorted(values) if name in _named(unavailable.fields)]
        raise dv.VariantRefused(
            UNAVAILABLE,
            "Carbon cannot yet rebuild this combination",
            issues=[(UNAVAILABLE, "/parameters/" + name) for name in names],
        ) from None
    if check_budget and values:
        from carbon.reconstruction.challenge_contracts import check_compute_budget

        check_compute_budget(
            dv.CONTRACTS[composition.challenge], strategy, level=COMPOSED
        )
    return CompiledComposition(
        challenge=composition.challenge,
        contract_digest=admitted.contract_digest,
        compiled=admitted.compiled,
        construction=admitted.construction,
        composition_digest=composition.digest,
        variants={str(level): digest for level, digest in sorted(used.items())},
        widened=values,
        reconstruction=reconstruction,
        derived=describe(used, values),
        record=record,
    )


def _named(fields):
    """The recipe field names a refusal's composed part names cover."""
    names = set()
    for item in fields:
        names.update(item.split("/"))
    return names
