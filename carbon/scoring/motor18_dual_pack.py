"""Motor 1.8's sealed adapter, reached only through its version-overlay dispatch (`version_overlay`).

Motor 1.8 grades Motor's sealed measurement under a NEW sealed evaluation (a new exam key: no king carries over), with
two changes (mc-exam-B 7 Nov contract; the Carbon Validator 7 Nov 06:38):

- **Its own TRAIN.** Every TRAIN-relative part of the measurement (the definition's TRAIN pin, the measure, the applied
  pack) reads 1.8's extended TRAIN (`physical_public_train.load_extended_train("motor-dev-train-1p8-v1")`), never
  TRAIN 150. The loader refuses until the Mon freeze, so this version refuses to grade until then.
- **Absolute pk-pk ripple.** The pool binding derives the mean torque and the ABSOLUTE peak-to-peak ripple (max - min of
  the predicted 60-angle torque, N.m), never the ripple fraction. The floor and ceiling the D side checks it against are
  sealed custody values (the D targets / menu records), never code or overlay config. The binding is registered with
  `pool_version.register_binding`, so `pool_adapters.py` (a live producer FILE of Ribbed Bracket,
  `f08_sanity_dual_pack.FILES`) is never edited (Validator-2B 7 Nov 13:27).

Everything else delegates UNCHANGED to `motor_sealed_dual_pack`, whose bytes (so every earlier Motor producer digest) do
not move. The pool grade (A by the pool exam, its headroom `physics` block and the menu D) comes from `pool_version` and
the version's `pool_constants.json` entry: until every owner value there is set, it refuses (HUMAN_INPUT).

**Torque only** (the owner, 7 Nov: 'Torque-only, EMF in 1.9'). The model's prediction row is the 60-angle torque, the
Motor 1.6 interface shape. Back-EMF and the k_e,ll cells are NOT part of 1.8: nothing here imports `carbon.motor.back_emf`
or reads a flux linkage; they ship in 1.9 with the TRAIN-vs-prediction interface split.
"""

from __future__ import annotations

import sys

from carbon.scoring import motor_sealed_dual_pack as _sealed

CHALLENGE = _sealed.CHALLENGE
VERSION = "1.8"
KIND = "motor"
#: The extended TRAIN every TRAIN-relative leg of this version reads.
TRAIN = "motor-dev-train-1p8-v1"
#: Motor 1.8's sealed evaluation (a new exam key) and its pool set case. The name is the Validator's to confirm.
POOL_VERSIONS = {VERSION: ("motor-pool-sealed-v3", "motor-sealed-pool-set")}
#: 1.8's OWN producer identity covers the sealed grader and this module (its pk-pk decision lives here).
FILES = (*_sealed.FILES, "motor18_dual_pack.py")
def _train():
    from carbon.challenge_kit import physical_public_train

    return physical_public_train.load_extended_train(TRAIN, CHALLENGE)["train"]


def definition(*, bank, train_raw):
    del train_raw
    return _sealed.definition(bank=bank, train_raw=_train())


def measure(
    *, bank_rows, outputs, repeats, definition, limits, objective, train_raw, names
):
    """Motor's sealed measurement against 1.8's extended TRAIN."""
    del train_raw
    return _sealed.measure(
        bank_rows=bank_rows,
        outputs=outputs,
        repeats=repeats,
        definition=definition,
        limits=limits,
        objective=objective,
        train_raw=_train(),
        names=names,
    )


def applied_pack(**kwargs):
    """Motor's applied pack on 1.8's extended TRAIN (when the sealed applied pack reads one)."""
    if "train_raw" in kwargs:
        kwargs = {**kwargs, "train_raw": _train()}
    return _sealed.applied_pack(**kwargs)


# -- the pool binding: absolute pk-pk as a computed quantity -----------------------------------------------------------

def _torque(raw):
    """One prediction row: exactly the 60-angle torque (N.m), finite, or None."""
    from carbon.motor.domain import ANGLE_STEPS
    from carbon.scoring import pool_adapters

    row = pool_adapters._finite_row(raw)
    return row if row is not None and len(row) == ANGLE_STEPS else None


def pool_adapter(version=VERSION):
    """1.8's `PoolAdapter`: from the validity-gated 60-angle torque, its mean and its ABSOLUTE pk-pk ripple (max - min,
    N.m; the Carbon Validator 7 Nov 06:38). No limit is read or set here: the mean-torque floor and the pk-pk ceiling are
    sealed custody values of the D targets and menu records (mc-exam-B 7 Nov (3)), never code or overlay config."""
    from carbon.motor import customer_decision as decision
    from carbon.motor import exam
    from carbon.scoring import pool_adapters
    from carbon.scoring.pool_adapters import PoolAdapter, PoolAdapterRefused

    if version != VERSION:
        raise PoolAdapterRefused("motor18_pool_adapter_is_for_1.8_only")
    _chosen, _limits, _objective, names = pool_adapters._roles(KIND, version)

    def derive(_inputs, raw):
        curve = _torque(raw)
        if curve is None:
            return None
        outputs = {"torque_nm": curve}
        if exam.FAIL in exam.gates(outputs).values():
            return None
        return {
            "mean_torque_nm": sum(curve) / len(curve),
            "ripple_pk_pk_nm": max(curve) - min(curve),
        }

    return PoolAdapter(
        kind=KIND,
        version=version,
        input_names=tuple(names),
        design_names=tuple(decision.DESIGN_VARIABLES),
        condition_names=tuple(decision.CONDITION_VARIABLES),
        outputs=("mean_torque_nm", "ripple_pk_pk_nm"),
        objective="ripple_pk_pk_nm",
        sense="min",
        limits=(),
        derive=derive,
        registered_u={},
    )


def physics_gates():
    """Motor's physics-contract gates (`pool_adapters`' Motor gates) on the TORQUE slice of a 1.8 row."""
    from carbon.motor import exam
    from carbon.scoring.pool_adapters import PhysicsGates

    names = tuple(g.gate_id for g in exam.GATES if g.gate_id != "paired_repeat")

    def failed(_inputs, raw):
        curve = _torque(raw)
        if curve is None:
            return ("schema_finite",)
        verdicts = exam.gates({"torque_nm": curve})
        return tuple(sorted(n for n, v in verdicts.items() if v == exam.FAIL))

    return PhysicsGates(KIND, VERSION, names, failed)


def official_binding():
    """1.8's OFFICIAL pool binding (`pool_adapters.official_binding`'s shape, with this version's derive and gates): the
    proof suite's controls are not part of the official grade, so each refuses if asked."""
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
    """The pool-graded adapter of Motor 1.8; None for any other version."""
    if version != VERSION:
        return None
    from carbon.scoring import pool_version

    evaluation, case_id = POOL_VERSIONS[VERSION]
    return pool_version.variant(
        _SELF, VERSION, evaluation, case_id, challenge_id=CHALLENGE
    )


def _adapter_for_bank(bank, version):
    if not _sealed.is_pool_bank(bank):
        raise _sealed.Refused("motor_bank_population")
    return sealed_adapter(version)


def _writer(root, bank, *, version=VERSION, **platform):
    """Motor 1.8's receiver pack: the sealed grid, its private probes and the pool rows, under this adapter."""
    from carbon.challenge_kit import motor_sealed_pack
    from carbon.scoring import sealed_pack_writer

    if version != VERSION:
        raise ValueError("motor18_dual_pack writes Motor 1.8 packs only")
    return sealed_pack_writer.write(
        sealed_adapter(VERSION),
        motor_sealed_pack,
        root,
        bank,
        challenge=CHALLENGE,
        version=VERSION,
        is_sealed_bank=_sealed.is_pool_bank,
        refusal=_sealed.Refused("motor_bank_population"),
        pack_suffix=_sealed.PACK_SUFFIX,
        **platform,
    )


def dispatch(config):
    """The overlay dispatch: registers Motor 1.8 in `motor_sealed_dual_pack`'s tables without editing that file, and
    its pk-pk pool binding in `pool_version` without editing `pool_adapters.py`. ``config`` must be empty (1.8 carries no
    public region box here; hidden bounds never enter the overlay)."""
    if config:
        raise ValueError("Motor 1.8's dispatch takes no config")
    from carbon.scoring import pool_version

    pool_version.register_binding(KIND, VERSION, official_binding)
    return {
        "challenge": CHALLENGE,
        "version": VERSION,
        "pool_versions": POOL_VERSIONS[VERSION],
        "adapter": sealed_adapter,
        "adapter_for_bank": _adapter_for_bank,
        "writer": _writer,
    }


def producer_digest():
    from carbon.scoring import physical_dual_pack as physical

    return physical.producer_digest(_SELF)


def __getattr__(name):
    return getattr(_sealed, name)


_SELF = sys.modules[__name__]
