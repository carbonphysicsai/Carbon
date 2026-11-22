"""Ribbed Bracket 2.0's pool-only adapter, reached only through its version-overlay dispatch (`version_overlay`).

RB 2.0 is POOL-ONLY (model-eval rulings, 22 Nov 2026 04:23:00Z and 04:41:52Z; P1 in `pool_exam.measure_pool`). It has
no sealed grid and no base measure:
- A comes from the pool exam with its physics block, on the class-drawn hidden designs.
- D comes from the RB menus. The owner's C rule caps each set's D by that set's own physics A.

This module holds what is RB-specific (head B2, spec RB20_HEAD_B2_SPEC_20261122 8b514b8c):

- **The 22-wide answer** (`f08_v2_train.GRADED_OUTPUTS`, owner RB20-COLS). `derive` reads it in that order and adds
  ``cad_mass_kg`` from the closed form (`f08_20_mass`), which is never a model output.
- **The physics validity gates G1-G5** (model-eval 04:23:00Z (d); exam-rb facts 05:01:11Z). Each is a mandatory
  admissibility check on one answer row. A failed gate sends the row back by name, and no other output compensates it:
  - G1: every output finite;
  - G2: every frequency > 0;
  - G3: ``first_mode_hz <= modes_hz_1 <= ... <= modes_hz_10`` (non-strict);
  - G4: the three von Mises stresses and the two patch max principals >= 0;
  - G5: ``patch_dynamic_frequency_hz`` inside the registered band (`BAND_HZ`).

  There is no sign rule on the tip vector.
- **The pool roles**:
  - the 12 inputs in the miner order;
  - the 7 geometry inputs as the design box (the RB menus' ``design_names``);
  - the other 5 as per-target conditions;
  - the objective ``cad_mass_kg`` min (the menus' objective).

  The limits ride in the sealed menu tasks, never here (as Motor 1.9).
- **The pool-only pack pieces** P1 leaves to the Challenge:
  - an ALL-pool bank check (`is_pool_bank`);
  - a definition and an applied pack over ZERO sealed rows. The applied pack has no gate of its own; the pool's
    physics / speed / in-range accuracy gates are appended by `pool_version.PoolVariant`. Its leg and value-weight form
    is F08's registered dual pack, read from `f08_sealed_dual_pack.applied_pack`, never retyped.
- **Its exam identity from the overlay entry**: the dispatch ``config`` names the sealed evaluation and the pool set case
  (``pool_versions``), so no exam id is in code and the module lands before the seal.

The pool grade's owner values (`pool_constants.json`: the physics rule, the menu, ``pool_only``) are the version's
registration. Until they are set, `pool_version` refuses (HUMAN_INPUT). No 1.x F08 file moves.

DEVELOPMENT only: no qualification, weight, reward or LIVE authority.
"""

from __future__ import annotations

import hashlib
import math
import sys
from itertools import pairwise

CHALLENGE = "f08-ribbed-bracket"
VERSION = "2.0"
KIND = "f08"
#: The sealed method this module's definition registers (a pool-only version: no grid, no probes).
METHOD = "f08-2.0-pool-only.v1"
#: The receiver pack's name suffix.
PACK_SUFFIX = "-pool-only"
#: ``{VERSION: (sealed evaluation, pool set case)}``, from the overlay entry's dispatch config (`dispatch`); empty until
#: then, so nothing grades 2.0 before its entry is installed.
POOL_VERSIONS: dict = {}
CONFIG_KEYS = frozenset({"pool_versions"})
#: The registered band of the patch's dynamic frequency (Hz): `f08_proof.BAND_HZ` (the deck's *STEADY STATE DYNAMICS
#: step and worst_band_dynamic_stress use it; exam-rb 05:01:11Z). Carried here so a grade reads no scripts file; a test
#: pins it to that constant.
BAND_HZ = (80.0, 600.0)
#: The design box: the RB menus' ``design_names`` (rb20_to_tasks DESIGN), the 7 geometry inputs in the arm's order.
DESIGN_NAMES = (
    "length_mm",
    "width_mm",
    "thickness_mm",
    "rib_height_mm",
    "rib_thickness_mm",
    "relief_length_mm",
    "fillet_radius_mm",
)
OBJECTIVE = "cad_mass_kg"
OUTPUT = {
    "quantity": "f08_2p0_22[deck 7, modes_hz 1-10, patch 3, tip 0-1]",
    "unit": "per output (f08_v2_train.OUTPUT_UNITS)",
}
MINIMUM_LEGS = ("A", "D")
#: 2.0's OWN producer identity: this module and the closed-form mass the derive runs.
FILES = ("f08_20_dual_pack.py", "f08_20_mass.py", "sealed_pack_writer.py")

_VON_MISES = (
    "static_fillet_stress_mpa_per_n",
    "dynamic_fillet_stress_mpa_per_n",
    "dynamic_fillet_stress_base_mpa_per_g",
)
_PRINCIPALS = (
    "patch_dynamic_max_principal_at_vm_frequency",
    "patch_static_max_principal",
)
_MODES = ("first_mode_hz", *(f"modes_hz_{i}" for i in range(1, 11)))
_PATCH_FREQUENCY = "patch_dynamic_frequency_hz"
_FREQUENCIES = (*_MODES, _PATCH_FREQUENCY)
#: The physics validity gates, in order (model-eval 04:23:00Z (d)).
GATES = (
    "g1_finite",
    "g2_frequency_positive",
    "g3_modes_non_decreasing",
    "g4_stress_non_negative",
    "g5_patch_frequency_in_band",
)


class Refused(ValueError):
    """A typed refusal of the Challenge's pack (never a candidate's failure); the code names the check, never a value."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _require(condition, code):
    if not condition:
        raise Refused(code)


def _train():
    from carbon.challenge_kit import f08_v2_train

    return f08_v2_train


def input_names(version=VERSION):
    _require(version == VERSION, "f08_20_is_for_2.0_only")
    return tuple(_train().INPUT_NAMES)


def graded_outputs():
    return tuple(_train().GRADED_OUTPUTS)


def condition_names():
    return tuple(n for n in input_names() if n not in DESIGN_NAMES)


def physics_contract():
    """No generated physics contract (None): the pack's own role is the version's registration."""


# -- the 22-wide answer --------------------------------------------------------------------------------------------------


def answer(raw):
    """``{output: value}`` of a whole 22-wide 2.0 answer in `graded_outputs` order, or None (not 22 numbers)."""
    names = graded_outputs()
    try:
        values = [float(v) for v in raw]
    except (TypeError, ValueError):
        return None
    if len(values) != len(names):
        return None
    return dict(zip(names, values, strict=True))


def failed_gates(raw):
    """The sorted names of the G1-G5 gates a raw answer row fails (empty: it passes). A row that is not 22 numbers
    fails G1 only (no later gate can read it)."""
    row = answer(raw)
    if row is None or not all(math.isfinite(v) for v in row.values()):
        return ("g1_finite",)
    failed = []
    if not all(row[name] > 0 for name in _FREQUENCIES):
        failed.append("g2_frequency_positive")
    modes = [row[name] for name in _MODES]
    if any(later < earlier for earlier, later in pairwise(modes)):
        failed.append("g3_modes_non_decreasing")
    if not all(row[name] >= 0 for name in (*_VON_MISES, *_PRINCIPALS)):
        failed.append("g4_stress_non_negative")
    low, high = BAND_HZ
    if not low <= row[_PATCH_FREQUENCY] <= high:
        failed.append("g5_patch_frequency_in_band")
    return tuple(sorted(failed))


def derive_answer(inputs, raw):
    """The 22 outputs of a finite 22-wide answer plus ``cad_mass_kg`` from the inputs, or None (not 22 finite numbers)."""
    from carbon.scoring import f08_20_mass

    row = answer(raw)
    if row is None or not all(math.isfinite(v) for v in row.values()):
        return None
    try:
        mass = f08_20_mass.cad_mass_kg(inputs)
    except f08_20_mass.MassRefused:
        return None  # the inputs are the bank's own rows: a mass refusal is never the candidate's to cause
    return {**row, OBJECTIVE: mass}


# -- the pool binding -----------------------------------------------------------------------------------------------------


def pool_adapter(version=VERSION):
    """2.0's `PoolAdapter`: the 22-wide derive plus the exact mass, the menus' roles, no limit (they ride in the menus)."""
    from carbon.scoring.pool_adapters import PoolAdapter, PoolAdapterRefused

    if version != VERSION:
        raise PoolAdapterRefused("f08_20_pool_adapter_is_for_2.0_only")
    return PoolAdapter(
        kind=KIND,
        version=VERSION,
        input_names=input_names(),
        design_names=DESIGN_NAMES,
        condition_names=condition_names(),
        outputs=(*graded_outputs(), OBJECTIVE),
        objective=OBJECTIVE,
        sense="min",
        limits=(),
        derive=derive_answer,
        registered_u={},
    )


def physics_gates():
    """G1-G5 on every pool answer of 2.0."""
    from carbon.scoring.pool_adapters import PhysicsGates

    return PhysicsGates(KIND, VERSION, GATES, lambda _inputs, raw: failed_gates(raw))


def official_binding():
    """2.0's OFFICIAL pool binding; the proof suite's controls are not part of the official grade, so each refuses."""
    from carbon.scoring import pool_adapters, pool_plugin

    chosen = pool_adapter(VERSION)

    def not_official(*_args, **_kwargs):
        raise pool_adapters.PoolAdapterRefused(
            "proof_suite_input_is_not_part_of_the_official_grade"
        )

    return pool_plugin.ChallengeBinding(
        kind=KIND,
        version=VERSION,
        input_names=chosen.input_names,
        design_names=chosen.design_names,
        derive=chosen.derive,
        raw_u=not_official,
        train_mean_row=not_official,
        serve_good=not_official,
        serve_train=not_official,
        serve_default=not_official,
        train_box=not_official,
        to_model_space=None,
        physics_gates=physics_gates(),
    )


# -- the pool-only pack pieces --------------------------------------------------------------------------------------------


def _sha(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _no_sealed_rows(rest) -> bool:
    """The Challenge's own bank once the pool rows are set aside: for 2.0 it holds NO row (pool-only)."""
    return (
        type(rest) is dict
        and type(rest.get("cohorts")) in (tuple, list)
        and len(rest["cohorts"]) == 0
    )


def is_pool_bank(bank) -> bool:
    """Whether ``bank`` is a 2.0 bank: at least one pool row and nothing else (no sealed cell, no probe)."""
    from carbon.scoring import pool_version

    return pool_version.is_pool_bank(bank, _no_sealed_rows)


def definition(*, bank, train_raw):
    """The pool-only definition: the method, the graded outputs and the reference receipt of the batch's records. The
    shared module adds the producer, TRAIN and bank pins; `PoolVariant` passes the bank without its pool rows.
    """
    del train_raw
    evidence = bank.get("solver_evidence") if type(bank) is dict else None
    _require(type(evidence) is bytes and evidence, "f08_20_evidence_unavailable")
    _require(_no_sealed_rows(bank), "f08_20_bank_holds_a_sealed_row")
    return {
        "sealed_method": METHOD,
        "pool_only": True,
        "graded_outputs": list(graded_outputs()),
        "reference_receipt_sha256": _sha(evidence),
    }


def validate_definition(definition, *, native_summary_rule=None):
    """The pool-only definition, checked for every field it carries."""
    del native_summary_rule
    receipt = (
        definition.get("reference_receipt_sha256") if type(definition) is dict else None
    )
    _require(
        type(definition) is dict
        and definition.get("sealed_method") == METHOD
        and definition.get("pool_only") is True
        and definition.get("graded_outputs") == list(graded_outputs())
        and type(receipt) is str
        and receipt.startswith("sha256:")
        and len(receipt) == 71,
        "f08_20_definition",
    )
    return definition


def applied_pack(*, bank_rows=(), **_):
    """F08's registered dual pack form (legs, value weight, combination, decision policy) with NO gate of its own: a
    pool-only version has no sealed row to gate. `PoolVariant` appends the pool's physics / speed / in-range accuracy
    gates."""
    from carbon.scoring import f08_sealed_dual_pack

    _require(not list(bank_rows), "f08_20_bank_holds_a_sealed_row")
    return {**f08_sealed_dual_pack.applied_pack(), "hard_gates": []}


def measure(**_):
    """A pool-only version runs no base measure (`pool_exam.measure_pool`, P1): a call here is a wiring fault."""
    raise Refused("f08_20_has_no_base_measure")


# -- the overlay dispatch -------------------------------------------------------------------------------------------------


def sealed_adapter(version):
    """The pool-graded adapter of RB 2.0; None for any other version (or before its entry is installed)."""
    if version != VERSION or VERSION not in POOL_VERSIONS:
        return None
    from carbon.scoring import pool_version

    evaluation, case_id = POOL_VERSIONS[VERSION]
    return pool_version.variant(
        _SELF, VERSION, evaluation, case_id, challenge_id=CHALLENGE
    )


def _adapter_for_bank(bank, version):
    _require(is_pool_bank(bank), "f08_20_bank_population")
    return sealed_adapter(version)


def _writer(root, bank, *, version=VERSION, **platform):
    """RB 2.0's receiver pack: the pool rows only, under this adapter."""
    from carbon.challenge_kit import f08_v2_sealed_pack
    from carbon.scoring import sealed_pack_writer

    if version != VERSION:
        raise ValueError("f08_20_dual_pack writes RB 2.0 packs only")
    adapter = sealed_adapter(VERSION)
    if adapter is None:
        raise ValueError("RB 2.0's overlay entry is not installed")
    return sealed_pack_writer.write(
        adapter,
        f08_v2_sealed_pack,
        root,
        bank,
        challenge=CHALLENGE,
        version=VERSION,
        is_sealed_bank=is_pool_bank,
        refusal=Refused("f08_20_bank_population"),
        pack_suffix=PACK_SUFFIX,
        **platform,
    )


def _pool_versions(config):
    """``(evaluation, case_id)`` from a dispatch config, or ValueError: exactly two non-empty strings."""
    if type(config) is not dict or not config or set(config) - CONFIG_KEYS:
        raise ValueError("RB 2.0's dispatch config is malformed")
    pair = config.get("pool_versions")
    if (
        type(pair) not in (list, tuple)
        or len(pair) != 2
        or not all(type(part) is str and part for part in pair)
    ):
        raise ValueError("RB 2.0's dispatch config needs pool_versions")
    return tuple(pair)


def dispatch(config):
    """The overlay dispatch: registers RB 2.0 in `f08_sealed_dual_pack`'s tables without editing that file, and its pool
    binding in `pool_version` without editing `pool_adapters.py`."""
    pair = _pool_versions(config)
    known = POOL_VERSIONS.get(VERSION)
    if known is not None and known != pair:
        raise ValueError("RB 2.0 is already dispatched with other pool versions")
    POOL_VERSIONS[VERSION] = pair
    from carbon.scoring import pool_grader, pool_version

    # the derive gives every answer the exact mass (the menus' objective); an accuracy target grades only the 22, so
    # the mass is a COMPANION there: dropped, never graded and never an invalid answer (as Motor 1.9's scalars)
    pool_grader.register_companion_output(OBJECTIVE)
    pool_version.register_binding(KIND, VERSION, official_binding)
    return {
        "challenge": CHALLENGE,
        "version": VERSION,
        "pool_versions": pair,
        "adapter": sealed_adapter,
        "adapter_for_bank": _adapter_for_bank,
        "writer": _writer,
    }


def producer_digest():
    from carbon.scoring import physical_dual_pack as physical

    return physical.producer_digest(_SELF)


_SELF = sys.modules[__name__]
