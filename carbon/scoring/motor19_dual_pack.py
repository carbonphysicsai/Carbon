"""Motor 1.9's sealed adapter, reached only through its version-overlay dispatch (`version_overlay`).

Motor 1.9 is Motor 1.8's exam (`motor18_dual_pack`, whose bytes do not move) with ONE interface change and its own exam
identity:

- **The 241-wide row** (`carbon.motor.row19`): 1.8's 240 columns, then ``magnet_min_b_t`` (T) at column 240 (owner MAGNET
  CELLS MOTOR, 21 Nov 2026). TRAIN, the prediction and the grade share it. The torque slice alone still feeds Motor's
  sealed grader, its gates and the pk-pk binding; a row that is not a whole 241-wide 1.9 answer is the candidate's schema
  failure, never a refusal.
- **Its own TRAIN** (`motor-dev-train-1p9-v1`: 1.8's 194 public designs with the magnet column; NOT grown). Every
  TRAIN-relative leg of the measurement reads its torque slice.
- **A scalar pool output** ``magnet_min_b_t``, beside 1.8's ``mean_torque_nm``, ``ripple_pk_pk_nm`` and the two back-EMF
  waveforms. Which (class, output) cells are scored, gated or recorded only is the version's REGISTERED physics rule
  (`pool_constants.json`: ``report_only_outputs`` / ``report_only_cells`` with POOL output names), never code here.
- **Its exam identity from the overlay entry**: the dispatch ``config`` names the sealed evaluation and the pool set case
  (``pool_versions``), so this module carries no exam id and lands before the seal. A ``subset_repeat`` block in the same
  config is case-procs' registry's (`subset_repeat_registry`, new-exam prep #11), read there, never here.

Everything else delegates UNCHANGED to `motor_sealed_dual_pack` and reuses 1.8's helpers (gates, the open-circuit
applicability, the waveform output), so 1.9's producer identity lists `motor18_dual_pack.py` too. The pool grade (A by
the pool exam, its physics block and the menu D) comes from `pool_version` and the version's `pool_constants.json`
entry: until every owner value there is set, it refuses (HUMAN_INPUT).
"""

from __future__ import annotations

import sys

from carbon.motor import row19 as _row19

#: The sealed module this version extends, imported LAZILY (`_sl`): the overlay arms its dispatch on that module's import.
_SEALED = "carbon.scoring.motor_sealed_dual_pack"

CHALLENGE = "electric-motor-magnetics"
VERSION = "1.9"
KIND = "motor"
#: The TRAIN every TRAIN-relative leg of this version reads (194 rows, 241 targets).
TRAIN = "motor-dev-train-1p9-v1"
#: ``{VERSION: (sealed evaluation, pool set case)}``, from the overlay entry's dispatch config (`dispatch`); empty until
#: then, so nothing grades 1.9 before its entry is installed.
POOL_VERSIONS: dict = {}
#: The keys a dispatch config may carry: this module's, and the subset-repeat registry's (read there, never here).
CONFIG_KEYS = frozenset({"pool_versions", "subset_repeat"})
#: 1.9's OWN producer identity: the sealed grader's files, 1.8's module (its helpers run here), this one, the pair bound,
#: the keyed subset repeat's readers, and the successor rows a version registered from now on reads.
_OWN_FILE = "motor19_dual_pack.py"
_HELPER_FILE = "motor18_dual_pack.py"
_BOUND_FILE = "pair_read_bound.py"
_SUBSET_FILES = (
    "subset_repeat_evidence.py",
    "subset_repeat_produce.py",
    "subset_repeat_registry.py",
    "producer_successor_v2.py",
)
#: The pool outputs of a 1.9 answer: 1.8's four, then the magnet scalar.
SCALAR_OUTPUTS = ("magnet_min_b_t",)


def _sl():
    from carbon.scoring import motor_sealed_dual_pack

    return motor_sealed_dual_pack


def _m18():
    from carbon.scoring import motor18_dual_pack

    return motor18_dual_pack


#: The two back-EMF cells' outputs (as 1.8), each the predicted k_e,ll ab waveform.
EMF_OUTPUTS = ("back_emf_open_circuit", "ke_ll_loaded")
ROW = _row19.ROW
split = _row19.split
linkages = _row19.linkages


def _width():
    return _row19.WIDTH


def ke_ll(raw):
    """The predicted k_e,ll ab waveform (V s / rad, one value per rotor step) of a whole 1.9 row, or None."""
    from carbon.motor import back_emf

    lam = linkages(raw)
    return None if lam is None else tuple(back_emf.ke_line(lam))


def _sealed_rows(outputs, repeats):
    """The sealed grader's 60-angle torque rows of 1.9 answers. If ANY row is not a whole 1.9 answer, every row becomes
    an empty curve: Motor's own schema gate then fails the grade (the candidate's answer, never a refusal).
    """
    rows = [
        split(row) for row in [*outputs, *(r for repeat in repeats for r in repeat)]
    ]
    if any(row is None for row in rows):
        return [[] for _ in outputs], [[[] for _ in repeat] for repeat in repeats]
    torque = [row["torque_nm"] for row in rows]
    n = len(outputs)
    return torque[:n], [
        torque[n + k * n : n + (k + 1) * n] for k in range(len(repeats))
    ]


def _train():
    from carbon.challenge_kit import physical_public_train

    return physical_public_train.load_extended_train(TRAIN, CHALLENGE)["train"]


def _torque_train():
    """1.9's TRAIN as Motor's sealed grader reads it: the same rows and inputs, only the torque slice of each 241-wide
    target. A 1.9 TRAIN that is not the 241-wide row refuses."""
    import io

    import numpy as np

    from carbon.challenge_kit import physical_public_train
    from carbon.motor.domain import ANGLE_STEPS

    with np.load(io.BytesIO(_train()), allow_pickle=False) as data:
        inputs = np.asarray(data["inputs"])
        targets = np.asarray(data["targets"])
    if targets.ndim != 2 or targets.shape[1] != _width():
        raise ValueError("Motor 1.9's TRAIN is not the 241-wide 1.9 row")
    return physical_public_train._npz(
        inputs, np.ascontiguousarray(targets[:, :ANGLE_STEPS])
    )


def definition(*, bank, train_raw):
    del train_raw
    return _sl().definition(bank=bank, train_raw=_torque_train())


def measure(
    *, bank_rows, outputs, repeats, definition, limits, objective, train_raw, names
):
    """Motor's sealed measurement against 1.9's TRAIN, on the torque slice of each 1.9 answer."""
    del train_raw
    if (
        type(outputs) is list
        and type(repeats) in (list, tuple)
        and all(type(r) is list and len(r) == len(outputs) for r in repeats)
    ):
        outputs, repeats = _sealed_rows(outputs, list(repeats))
    return _sl().measure(
        bank_rows=bank_rows,
        outputs=outputs,
        repeats=repeats,
        definition=definition,
        limits=limits,
        objective=objective,
        train_raw=_torque_train(),
        names=names,
    )


def applied_pack(**kwargs):
    """Motor's applied pack on 1.9's TRAIN's torque (when the sealed applied pack reads one)."""
    if "train_raw" in kwargs:
        kwargs = {**kwargs, "train_raw": _torque_train()}
    return _sl().applied_pack(**kwargs)


# -- the pool binding --------------------------------------------------------------------------------------------------


def _torque(raw):
    """The 60-angle torque (N.m) of a whole, finite 1.9 row, or None."""
    parts = split(raw)
    return None if parts is None else parts["torque_nm"]


def pool_adapter(version=VERSION):
    """1.9's `PoolAdapter`: 1.8's derive (validity-gated torque: mean, ABSOLUTE pk-pk; the two k_e,ll waveforms) on the
    1.9 row, plus the magnet scalar. No limit is read or set here (sealed custody values, as 1.8).
    """
    from carbon.motor import customer_decision as decision
    from carbon.motor import exam
    from carbon.scoring import pool_adapters
    from carbon.scoring.pool_adapters import PoolAdapter, PoolAdapterRefused

    if version != VERSION:
        raise PoolAdapterRefused("motor19_pool_adapter_is_for_1.9_only")
    _chosen, _limits, _objective, names = pool_adapters._roles(KIND, version)
    gates = _m18().gates18

    def derive(inputs, raw):
        parts = split(raw)
        if parts is None:
            return None
        curve = parts["torque_nm"]
        if exam.FAIL in gates(curve, inputs).values():
            return None
        wave = ke_ll(raw)
        return {
            "mean_torque_nm": sum(curve) / len(curve),
            "ripple_pk_pk_nm": max(curve) - min(curve),
            **dict.fromkeys(EMF_OUTPUTS, wave),
            **{name: parts[name] for name in SCALAR_OUTPUTS},
        }

    return PoolAdapter(
        kind=KIND,
        version=version,
        input_names=tuple(names),
        design_names=tuple(decision.DESIGN_VARIABLES),
        condition_names=tuple(decision.CONDITION_VARIABLES),
        outputs=("mean_torque_nm", "ripple_pk_pk_nm", *EMF_OUTPUTS, *SCALAR_OUTPUTS),
        objective="ripple_pk_pk_nm",
        sense="min",
        limits=(),
        derive=derive,
        registered_u={},
    )


def physics_gates():
    """Motor's physics-contract gates on the TORQUE slice of a 1.9 row (1.8's gates, J == 0 rule included)."""
    from carbon.motor import exam
    from carbon.scoring.pool_adapters import PhysicsGates

    names = tuple(g.gate_id for g in exam.GATES if g.gate_id != "paired_repeat")
    gates = _m18().gates18

    def failed(inputs, raw):
        curve = _torque(raw)
        if curve is None:
            return ("schema_finite",)
        verdicts = gates(curve, inputs)
        return tuple(sorted(n for n, v in verdicts.items() if v == exam.FAIL))

    return PhysicsGates(KIND, VERSION, names, failed)


def official_binding():
    """1.9's OFFICIAL pool binding (1.8's shape with this version's derive and gates); the proof suite's controls are not
    part of the official grade, so each refuses if asked."""
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
        to_model_space=pool_adapters._to_model_space(KIND, VERSION),
        physics_gates=physics_gates(),
    )


# -- the overlay dispatch ---------------------------------------------------------------------------------------------


def sealed_adapter(version):
    """The pool-graded adapter of Motor 1.9; None for any other version (or before its entry is installed)."""
    if version != VERSION or VERSION not in POOL_VERSIONS:
        return None
    from carbon.scoring import pool_version

    evaluation, case_id = POOL_VERSIONS[VERSION]
    return pool_version.variant(
        _SELF, VERSION, evaluation, case_id, challenge_id=CHALLENGE
    )


def _adapter_for_bank(bank, version):
    if not _sl().is_pool_bank(bank):
        raise _sl().Refused("motor_bank_population")
    return sealed_adapter(version)


def _writer(root, bank, *, version=VERSION, **platform):
    """Motor 1.9's receiver pack: the sealed grid, its private probes and the pool rows, under this adapter."""
    from carbon.challenge_kit import motor_sealed_pack
    from carbon.scoring import sealed_pack_writer

    if version != VERSION:
        raise ValueError("motor19_dual_pack writes Motor 1.9 packs only")
    adapter = sealed_adapter(VERSION)
    if adapter is None:
        raise ValueError("Motor 1.9's overlay entry is not installed")
    return sealed_pack_writer.write(
        adapter,
        motor_sealed_pack,
        root,
        bank,
        challenge=CHALLENGE,
        version=VERSION,
        is_sealed_bank=_sl().is_pool_bank,
        refusal=_sl().Refused("motor_bank_population"),
        pack_suffix=_sl().PACK_SUFFIX,
        **platform,
    )


def _pool_versions(config):
    """``(evaluation, case_id)`` from a dispatch config, or ValueError: exactly two non-empty strings."""
    if type(config) is not dict or not config or set(config) - CONFIG_KEYS:
        raise ValueError("Motor 1.9's dispatch config is malformed")
    pair = config.get("pool_versions")
    if (
        type(pair) not in (list, tuple)
        or len(pair) != 2
        or not all(type(part) is str and part for part in pair)
    ):
        raise ValueError("Motor 1.9's dispatch config needs pool_versions")
    return tuple(pair)


def dispatch(config):
    """The overlay dispatch: registers Motor 1.9 in `motor_sealed_dual_pack`'s tables without editing that file, and its
    pool binding in `pool_version` without editing `pool_adapters.py`. ``config`` names the sealed evaluation and the
    pool set case (``pool_versions``); a ``subset_repeat`` block is the subset-repeat registry's.
    """
    pair = _pool_versions(config)
    known = POOL_VERSIONS.get(VERSION)
    if known is not None and known != pair:
        raise ValueError("Motor 1.9 is already dispatched with other pool versions")
    POOL_VERSIONS[VERSION] = pair
    from carbon.scoring import pair_read_bound, pool_grader, pool_version

    for name in EMF_OUTPUTS:
        pool_grader.register_waveform_output(name, _m18()._waveform_output())
    # 1.9's derive gives every target every output; a target grades only its own (an H-3 target pk-pk and OC; the magnet
    # scalar only where its target carries a reference): an output a target does not grade is dropped from its answer,
    # never graded and never an invalid answer (1.8's sixth seam, 12 Nov)
    for name in ("mean_torque_nm", "ripple_pk_pk_nm", *SCALAR_OUTPUTS):
        pool_grader.register_companion_output(name)
    pair_read_bound.size_produce(CHALLENGE, VERSION)
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


def __getattr__(name):
    if name == "FILES":
        return (
            *_sl().FILES,
            _HELPER_FILE,
            _OWN_FILE,
            _BOUND_FILE,
            *_SUBSET_FILES,
        )
    return getattr(_sl(), name)


_SELF = sys.modules[__name__]
