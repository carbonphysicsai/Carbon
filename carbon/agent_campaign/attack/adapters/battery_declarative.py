"""Battery's declarative development levels (2 and 3) for the attack engine.

Levels 2 and 3 widen battery's recipe with Carbon-written, declarative
choices held as data: SpecMuon (`optimizer.muon_spectral`, Level 2,
`battery-l2-spectral-v1`) and the polish numerics menu
(`numerics.quasi_newton_family`, `numerics.line_search`, Level 3,
`battery-l3-numerics-v1`). Nothing here runs participant code, and nothing
is served to a miner.

`adapters.battery_level2` and `adapters.battery_level3` each declare a
`LevelSpec`: their families (the Test Lead's L2/L3 attack design,
2026-10-08) and their seams. This module supplies what both share:

* **The real boundaries** are Carbon's own: the registered variant's compile
  (`development_variants.compile_development`), the miner-facing contract
  (`compile_submission`, which every development field must fail), and the
  rebuild (`battery.worker.DirectBackend.reconstruct` through the shared
  dispatch, `development_rebuild`).
* **The vulnerable specimen** of each family is that boundary without its
  check: a gate that admits everything, the variant in place of the miner
  contract, or a rebuild whose seed is not pinned. A family whose specimen
  does not accept its attacks has a broken detector, never a pass
  (`family_oracle`).
* **Rebuild** compiles a strategy under the level's variant to its record;
  the record's own rebuild label ("CPU-verified only") travels with it.
"""

from __future__ import annotations

import functools
import hashlib
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from carbon.agent_campaign.attack import engine
from carbon.agent_campaign.attack.adapter import (
    Control,
    family_oracle,
    seam_oracle,
)
from carbon.agent_campaign.attack.adapters import battery as b

CHALLENGE_ID = b.CHALLENGE_ID
SPLITS = b.SPLITS
#: The seed of every rebuild here; the specimen's second rebuild uses the next.
SEED = 7


def _dv():
    from carbon.reconstruction import development_variants

    return development_variants


def variant(level):
    return _dv().variant(CHALLENGE_ID, level)


def strategy(base, **parameters):
    return {
        "schema_version": "1.0",
        "challenge_id": CHALLENGE_ID,
        "backbone": "mlp",
        "parameters": {**base, **parameters},
    }


# -- boundaries --------------------------------------------------------------------


def variant_gate(level):
    """The registered variant's compile at `level`: OK or REFUSED with a typed
    code. The variant's own refusals carry their issue codes; the Level 0
    contract and catalog refusals it passes through are typed by Level 0's
    classifier. Anything untyped propagates (the engine records a crash)."""

    def gate(value):
        dv = _dv()
        try:
            dv.compile_development(value, variant(level))
        except dv.VariantRefused as refused:
            return {
                "status": "REFUSED",
                "code": refused.code,
                "issues": sorted({str(i[0]) for i in refused.issues}),
            }
        except Exception as error:
            typed = b._challenge_scoring().refusal(error)
            if typed is None:
                raise
            return {"status": "REFUSED", "code": typed[0]}
        return {"status": "OK"}

    return gate


def miner_contract_gate(value):
    """The miner-facing Level 0 contract, which signs on the Launchpad and
    admits on the validator: every development field must fail it."""
    from carbon.reconstruction.challenge_contracts import (
        SubmissionRefused,
        compile_submission,
    )

    try:
        compile_submission(value)
    except SubmissionRefused as refused:
        return {"status": "REFUSED", "code": type(refused).__name__}
    return {"status": "OK"}


def unchecked_gate(value):
    """The vulnerable specimen: a gate that enforces nothing."""
    del value
    return {"status": "OK"}


def accepted(result):
    return result["status"] == "OK"


@functools.lru_cache(maxsize=1)
def _backend():
    from carbon.agent_campaign.graphite import experiment
    from carbon.battery.worker import DirectBackend

    return DirectBackend(experiment.REPOSITORY)


def _state_digest(value, level, seed):
    from carbon.battery import development_rebuild

    found = _dv().compile_development(value, variant(level))
    record = development_rebuild.record(found.reconstruction)
    state, _stats = _backend().reconstruct(None, found.construction, seed, record)
    return hashlib.sha256(state).hexdigest()


def rebuilds_identically(level):
    """Carbon's rebuild, twice, same recipe and seed: SAME when the two
    states are bit-identical (CPU), DIFFERENT otherwise."""

    def boundary(value):
        first = _state_digest(value, level, SEED)
        second = _state_digest(value, level, SEED)
        return {"status": "SAME" if first == second else "DIFFERENT"}

    return boundary


def unpinned_seed(level):
    """The specimen: a rebuild that does not pin the seed."""

    def boundary(value):
        first = _state_digest(value, level, SEED)
        second = _state_digest(value, level, SEED + 1)
        return {"status": "SAME" if first == second else "DIFFERENT"}

    return boundary


def different(result):
    return result["status"] == "DIFFERENT"


def same(result):
    return result["status"] == "SAME"


# -- the level's declaration --------------------------------------------------------


@dataclass(frozen=True)
class FamilyRow:
    """One run family: its Track A check, the boundary in words, its attacks
    (`() -> ((name, value), ...)`), the real boundary and its specimen, what
    a breach is, what a passing control is, and the two control inputs."""

    check: str
    words: str
    attacks: Callable
    boundary: Callable
    specimen: Callable
    breached: Callable
    control_ok: Callable
    trained: Mapping
    held_out: Mapping


@dataclass(frozen=True)
class LevelSpec:
    level: int
    version: str
    adapter_version: str
    controls_version: str
    rebuild_label: Callable
    families: Callable
    seams: tuple


class BatteryDeclarativeAdapter(b.BatteryLevel0Adapter):
    """Battery at a declarative development level, for the attack engine."""

    challenge_id = CHALLENGE_ID
    deterministic_baseline = None

    def __init__(self, spec):
        self.spec = spec
        self.level = spec.level
        self.version = spec.adapter_version
        self.controls_version = spec.controls_version

    @property
    def profile(self):
        return f"level-{self.level}"

    @property
    def contract_digest(self):
        from carbon.reconstruction import capability_registry as cr

        try:
            return cr.development_variant_registry()["versions"][self.spec.version]
        except (RuntimeError, KeyError):
            return "sha256:" + "0" * 64

    def _table(self):
        return self.spec.families()

    def _engine(self, name):
        row = self._table()[name]
        return engine.Family(
            name=name,
            check=row.check,
            boundary=row.boundary,
            attacks=row.attacks,
            specimen=row.specimen,
            breached=row.breached,
            control=lambda: row.control_ok(row.boundary(row.trained)),
            description=row.words,
        )

    def families(self):
        return tuple(
            b.FamilyDef(
                name=name,
                check=row.check,
                boundary=row.words,
                attack_example=row.attacks()[0][0],
                control_example=f"{name}_trained",
                family=self._engine(name),
            )
            for name, row in self._table().items()
        )

    def controls(self, split):
        if split not in SPLITS:
            raise ValueError("split is trained or held_out")
        out = []
        for name, row in self._table().items():
            value = row.trained if split == "trained" else row.held_out
            out.append(
                Control(
                    name=f"{name}_{split}",
                    family=name,
                    split=split,
                    version=self.controls_version,
                    check=lambda v=value, r=row: r.control_ok(r.boundary(v)),
                    input_digest=b._digest(value),
                )
            )
        return tuple(out)

    def oracle(self, family, attempt):
        if family in self._table():
            return family_oracle(self._engine(family), attempt)
        for seam in self.level_families():
            if seam.name == family:
                return seam_oracle(seam, attempt)
        raise ValueError("oracle_for_an_unknown_family: " + str(family))

    def level_families(self):
        return tuple(
            b.SeamFamily(name=name, check=check, level=self.level, reason=reason)
            for name, check, reason in self.spec.seams
        )

    def rebuild(self, construction):
        """The strategy compiled under the level's variant to its record. The
        training itself is `rebuilds_identically` and the CPU practice trial
        (`battery_level1.trial_at`)."""
        dv = _dv()
        value = construction
        if isinstance(construction, Mapping) and "strategy" in construction:
            value = construction["strategy"]
        if b._protected(value):
            return b.Unrebuildable(
                code="protected_material", detail="protected_material_named"
            )
        try:
            found = dv.compile_development(value, variant(self.level))
        except dv.VariantRefused as refused:
            issues = sorted({str(i[0]) for i in refused.issues})
            core = (
                "outside_level"
                if b.OUTSIDE_LEVEL_ISSUES & set(issues)
                else "refused_by_contract"
            )
            return b.Unrebuildable(
                code=core,
                detail=refused.code + (": " + ", ".join(issues) if issues else ""),
            )
        except Exception as failure:  # noqa: BLE001 - Carbon's own, never scored
            return b.Unrebuildable(
                code="rebuild_failed_infra", detail=type(failure).__name__
            )
        return b.Rebuilt(
            construction_digest=b._digest(value),
            rebuilt_digest=b._digest(found.reconstruction),
            detail={
                "record": found.reconstruction,
                "served": True,
                "rebuild": self.spec.rebuild_label(),
            },
        )

    def permission_inventory(self):
        """Level 0's inventory with the variant's permissions added."""
        inventory = dict(super().permission_inventory())
        found = variant(self.level)
        inventory["profile"] = self.profile
        inventory["development_variant"] = found.digest
        inventory["permitted"] = list(inventory["permitted"]) + [
            {
                "id": w.capability_id,
                "surface": None,
                "applies_to": [],
                "planning_level": self.level,
            }
            for w in found.widened
        ]
        inventory["not_permitted"] = [
            p
            for p in inventory["not_permitted"]
            if (p.get("id") if isinstance(p, Mapping) else p) not in found.permissions()
        ]
        return inventory

    def admission_refusals(self, construction):
        made = self.rebuild(construction)
        if isinstance(made, b.Rebuilt):
            return []
        return [self.carbon_code(made)] + [made.code]

    def surface(self):
        found = variant(self.level)
        return {
            "challenge": CHALLENGE_ID,
            "level": self.level,
            "profile": self.profile,
            "contract_digest": self.contract_digest,
            "variant_version": found.version,
            "permissions": list(found.permissions()),
            "adapter_version": self.version,
            "rebuild": self.spec.rebuild_label(),
        }


#: Where the injected non-finite classification is proven (M2, N2).
FAULT_INJECTION_TEST = (
    "tests/cpu/test_attack_battery_level23_adapters.py::"
    "test_injected_nonfinite_is_the_candidates_own"
)


def compute_accounting_seam(level, held=""):
    """The cost calculator's finding, shared by both levels (accepted by the
    Test Lead, 2026-10-08): it compiles every recipe with the Level 0
    contract, so it refuses a development recipe (`parameter.unknown`)
    instead of counting its real cost. Nothing is under-counted, but a
    budget check would refuse every honest recipe at this level. `held` is
    the level's own disposition, stated first."""
    return (
        f"l{level}_compute_accounting",
        "resource_and_failure_accounting",
        (
            held + "the TRAINING-BUDGET-01 cost calculator refuses every development "
            "recipe (parameter.unknown): it compiles with the Level 0 contract, so "
            "this level's real cost (SpecMuon's SVD, dense quasi-Newton memory) is "
            "never counted and a budget check would refuse every honest recipe; "
            "accepted as a blocker for switching the #727 admission check on "
            "(owner: Test Engineer, TRAINING-BUDGET-01)"
        ),
    )


def fresh_cases_seam(level):
    return (
        f"l{level}_fresh_cases_rerun",
        "fresh_attack_confirmation",
        "fresh cases need Phase 3 live runs through the Launchpad (owner, 2026-10-07)",
    )
