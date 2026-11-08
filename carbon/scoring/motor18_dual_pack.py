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

**Back-EMF in 1.8** (the owner, 7 Nov evening, reversing 'Torque-only, EMF in 1.9'; the Carbon Validator: the flux
linkage in TRAIN leaks nothing). TRAIN and the prediction share ONE 240-wide row (`ROW`): the 60-angle torque, then the
three phase flux linkages over the same 60 rotor steps, so there is no TRAIN-vs-prediction split and every route trains
and predicts at TRAIN's width. The torque slice alone feeds Motor's sealed grader, its gates and the pk-pk binding; a
row that is not a whole 240-wide 1.8 answer is the candidate's schema failure, never a refusal.

The two back-EMF cells (`carbon.motor.back_emf.CELLS`: ``back_emf_open_circuit`` on the J = 0 class H-3,
``ke_ll_loaded`` on the load-point classes H-1 / H-2; Carbon Validator-B 7 Nov: in their PARENT families) are pool
outputs like any other, scored as ordinary headroom cells where the sealed admission admits them (mc-exam-B 7 Nov
20:35). Their value is a WAVEFORM, the k_e,ll ab of the predicted linkages, registered with
`pool_grader.register_waveform_output`: the error is `back_emf.shape_error` (each waveform over its own RMS), never
|predicted - true|. A target grading one carries its custody reference k_e,ll waveform per point (derived from the
record-now linkages with `back_emf.ke_line`) and its U of record measured ON k_e,ll: an absolute number above zero,
or the pool refuses to load (the U is the sealed material's, never code). A prediction whose k_e,ll has no shape is
not a valid answer on a target that grades it.
"""

from __future__ import annotations

import sys

from carbon.motor import row18 as _row18
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
#: The two back-EMF cells' outputs (`back_emf.CELLS`), each the predicted k_e,ll ab waveform.
EMF_OUTPUTS = ("back_emf_open_circuit", "ke_ll_loaded")
#: The 1.8 row (`carbon.motor.row18`, public, nothing sealed): torque, then phase linkages A, B, C.
ROW = _row18.ROW


def _width():
    return _row18.WIDTH


split = _row18.split
linkages = _row18.linkages


def ke_ll(raw):
    """The predicted k_e,ll ab waveform (V s / rad, one value per rotor step) of a whole 1.8 row, or None."""
    from carbon.motor import back_emf

    lam = linkages(raw)
    return None if lam is None else tuple(back_emf.ke_line(lam))


def _waveform_valid(value):
    """A k_e,ll waveform `back_emf.shape_error` can grade: one finite value per rotor step, with a shape (RMS > 0)."""
    from carbon.motor import back_emf

    try:
        values = back_emf._waveform(value, "waveform_invalid")
    except back_emf.BackEmfUnavailable:
        return False
    return back_emf._rms(values) > 0


def _waveform_error(predicted, true):
    from carbon.motor import back_emf

    return back_emf.shape_error(predicted, true)


def _waveform_output():
    from carbon.scoring import pool_grader

    return pool_grader.WaveformOutput(valid=_waveform_valid, error=_waveform_error)


def _sealed_rows(outputs, repeats):
    """The sealed grader's 60-angle torque rows of 1.8 answers. If ANY row is not a whole 1.8 answer, every row becomes
    an empty curve: Motor's own schema gate then fails the grade (the candidate's answer, never a refusal), and the physics
    half, which reads the probe rows, is never reached with a malformed one."""
    rows = [split(row) for row in [*outputs, *(r for repeat in repeats for r in repeat)]]
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
    """1.8's TRAIN as Motor's sealed grader reads it (its scales, physics-half response registration and TRAIN
    spread are torque quantities): the same rows and inputs, only the torque slice of each 240-wide target, written with
    the public TRAIN's own writer. The TRAIN pins the shared module adds name the PUBLISHED 1.8 TRAIN, never this view.
    A 1.8 TRAIN that is not the 240-wide row refuses."""
    import io

    import numpy as np

    from carbon.challenge_kit import physical_public_train
    from carbon.motor.domain import ANGLE_STEPS

    with np.load(io.BytesIO(_train()), allow_pickle=False) as data:
        inputs = np.asarray(data["inputs"])
        targets = np.asarray(data["targets"])
    if targets.ndim != 2 or targets.shape[1] != _width():
        raise ValueError("Motor 1.8's TRAIN is not the 240-wide 1.8 row")
    return physical_public_train._npz(
        inputs, np.ascontiguousarray(targets[:, :ANGLE_STEPS])
    )


def definition(*, bank, train_raw):
    del train_raw
    return _sealed.definition(bank=bank, train_raw=_torque_train())


def measure(
    *, bank_rows, outputs, repeats, definition, limits, objective, train_raw, names
):
    """Motor's sealed measurement against 1.8's extended TRAIN, on the torque slice of each 1.8 answer."""
    del train_raw
    if (
        type(outputs) is list
        and type(repeats) in (list, tuple)
        and all(type(r) is list and len(r) == len(outputs) for r in repeats)
    ):
        outputs, repeats = _sealed_rows(outputs, list(repeats))
    return _sealed.measure(
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
    """Motor's applied pack on 1.8's extended TRAIN's torque (when the sealed applied pack reads one)."""
    if "train_raw" in kwargs:
        kwargs = {**kwargs, "train_raw": _torque_train()}
    return _sealed.applied_pack(**kwargs)


# -- the pool binding: absolute pk-pk as a computed quantity -----------------------------------------------------------


def _torque(raw):
    """The 60-angle torque (N.m) of a whole, finite 1.8 row, or None."""
    parts = split(raw)
    return None if parts is None else parts["torque_nm"]


def pool_adapter(version=VERSION):
    """1.8's `PoolAdapter`: from the validity-gated 60-angle torque, its mean and its ABSOLUTE pk-pk ripple (max - min,
    N.m; the Carbon Validator 7 Nov 06:38). No limit is read or set here: the mean-torque floor and the pk-pk ceiling are
    sealed custody values of the D targets and menu records (mc-exam-B 7 Nov (3)), never code or overlay config.
    """
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
        wave = ke_ll(raw)
        return {
            "mean_torque_nm": sum(curve) / len(curve),
            "ripple_pk_pk_nm": max(curve) - min(curve),
            **dict.fromkeys(EMF_OUTPUTS, wave),
        }

    return PoolAdapter(
        kind=KIND,
        version=version,
        input_names=tuple(names),
        design_names=tuple(decision.DESIGN_VARIABLES),
        condition_names=tuple(decision.CONDITION_VARIABLES),
        outputs=("mean_torque_nm", "ripple_pk_pk_nm", *EMF_OUTPUTS),
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
    proof suite's controls are not part of the official grade, so each refuses if asked.
    """
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
    from carbon.scoring import pool_grader, pool_version

    for name in EMF_OUTPUTS:
        pool_grader.register_waveform_output(name, _waveform_output())
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
