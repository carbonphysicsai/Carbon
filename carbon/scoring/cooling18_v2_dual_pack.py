"""DRAFT, NOT COMMITTED, NOT WIRED, py_compile only. Intended path carbon/scoring/cooling18_v2_dual_pack.py.

Cooling 1.8's 34-slot sealed adapter as a NEW 1.8-only module (the Motor 1.8 pattern,
carbon/scoring/motor18_dual_pack.py on mcexam-c/cool18-on-main):
  - own FILES tuple (motor18_dual_pack.py `__getattr__`, ~:405-410),
  - `pool_version.register_binding(KIND, VERSION, official_binding)` from `dispatch`
    (motor18_dual_pack.py:380; pool_version.py:864-877), so pool_adapters.py (a live producer FILE of
    F08, f08_sanity_dual_pack.FILES :17) is NEVER edited,
  - everything else delegates to existing modules whose bytes do not move.

Every existing Cooling/F08 producer file stays byte-identical (test_cool18_v2_producer_digests_unchanged).

Replaces, for 1.8 only, the dispatch module of the overlay entry "chip-cold-plate 1.8"
(today carbon.scoring.cooling18_dual_pack). That file is left byte-untouched too.

HUMAN_INPUT (never invented here): U for outlet_c and peak_x_mm, scales, weights, roles in A/D, the 34-wide
baseline, the v2 TRAIN artifact name and its sha256 pins, the sealed evaluation / pool-set ids.
Anything that needs one refuses with a typed code.
"""

from __future__ import annotations

import math
import sys

CHALLENGE = "chip-cold-plate"
VERSION = "1.8"
KIND = "cooling"
WIDTH = 34
#: HUMAN_INPUT: the v2 native / served TRAIN names (new files; v1 TRAIN artifacts are never edited).
NATIVE_TRAIN = None  # e.g. "cooling-dev-train-1p8-v2"
SERVED_TRAIN = None  # e.g. "cooling-dev-train-1p8-v2-encoded"
#: HUMAN_INPUT: the 1.8 v2 sealed evaluation id (a new exam key) and its pool set case.
POOL_VERSIONS = {VERSION: None}
_OWN_FILE = "cooling18_v2_dual_pack.py"


class V2Refused(ValueError):
    """A typed refusal; `.code` is the stable string."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _enc():
    # LAZY (see cooling18_dual_pack._enc): the overlay arms dispatch on import of the sealed module.
    from carbon.scoring import cooling_encoded_dual_pack

    return cooling_encoded_dual_pack


def _v2():
    from carbon.cold_plate import output_encoding_v2

    return output_encoding_v2


def _require_version(version):
    if version != VERSION:
        raise V2Refused("cooling18_v2_is_for_1.8_only")


def _require_v2_token():
    """Fail closed through the SINGLE resolver (output_encoding_v2.arm -> encoding_for_token); no string compare here."""
    _v2().arm(CHALLENGE, VERSION)


# -- the 34-slot derive and gates (mirror of pool_adapters._cooling / _cooling_gates, kept HERE) ----


def _finite_row(raw):
    try:
        row = [float(v) for v in raw]
    except (TypeError, ValueError):
        return None
    return row if all(math.isfinite(v) for v in row) else None


def _decode_native(raw):
    """A 34-value encoded row as the native 34-value row, or None (malformed / refused decode)."""
    row = _finite_row(raw)
    if row is None or len(row) != WIDTH:
        return None
    try:
        return _v2().decode_flat(row)
    except ValueError:
        return None


def _binding_parts(version):
    from carbon.cold_plate import customer_decision as decision
    from carbon.scoring import pool_adapters

    _chosen, limits, objective, names = pool_adapters._roles(KIND, version)
    return decision, limits, objective, names


def derive(version=VERSION):
    """Mirror of pool_adapters._cooling's derive (pool_adapters.py:147-170): the decision quantities use only
    peak/profile/pressure, so they read the 32-value native prefix of the decoded 34-value row.
    """
    _require_version(version)
    decision, _limits, objective, _names = _binding_parts(version)
    contract = objective["decision_contract"]

    def one(inputs, raw):
        native = _decode_native(raw)
        if native is None:
            return None
        try:
            quantities = decision.quantities(
                contract,
                dict(inputs),
                {
                    "peak_c": native[0],
                    "profile_c": list(native[1:31]),
                    "pressure_drop_pa": native[31],
                },
            )
        except (decision.DecisionError, ValueError, OverflowError):
            return None
        return {
            "die_peak_c": quantities["die_peak_c"],
            "hydraulic_w": quantities["hydraulic_w"],
        }

    return one


def gates(version=VERSION):
    """Mirror of pool_adapters._cooling_gates (pool_adapters.py:357-372) on the 32-value native prefix."""
    _require_version(version)
    from carbon.cold_plate import exam
    from carbon.scoring.pool_adapters import PhysicsGates

    names = tuple(g.gate_id for g in exam.GATES if g.gate_id != "paired_repeat")

    def failed(inputs, raw):
        native = _decode_native(raw)
        if native is None:
            return ("schema_finite",)
        prediction = {
            "peak_c": native[0],
            "profile_c": list(native[1:31]),
            "pressure_drop_pa": native[31],
        }
        verdicts = exam.gates(prediction, dict(inputs))
        return tuple(sorted(n for n, v in verdicts.items() if v == exam.FAIL))

    return PhysicsGates(KIND, version, names, failed)


def bounded_derive(box, version=VERSION):
    """Region-aware 34-slot derive: mirror of cooling_region.bounded_derive (cooling_region.py:118-148) for the 34-wide
    row. Reuses by import `cooling_region.check_inputs` (the region box in place of INPUT_BOUNDS) and
    `cooling_region.die_peak_c`, neither of which assumes a row width. cooling_region.py is byte-unchanged.
    """
    _require_version(version)
    from carbon.cold_plate import customer_decision as decision
    from carbon.cold_plate import exam
    from carbon.cold_plate.domain import derived
    from carbon.scoring import cooling_region

    def one(inputs, raw):
        native = _decode_native(
            raw
        )  # None unless 34 finite values that decode (v2 refusals included)
        if native is None:
            return None
        try:
            outputs = {
                "peak_c": native[0],
                "profile_c": list(native[1:31]),
                "pressure_drop_pa": native[31],
            }
            # the law gates first, on the 32-value native prefix (outlet_c / peak_x_mm have no gate)
            if set(outputs) != set(exam.SHAPES):
                return None
            verdicts = exam.gates(outputs, dict(inputs))
            if any(verdict == exam.FAIL for verdict in verdicts.values()):
                return None
            case = cooling_region.check_inputs(dict(inputs), box)
            hydraulic = outputs["pressure_drop_pa"] * derived(case)["flow_m3_s"]
            die = cooling_region.die_peak_c(case, outputs)
        except (decision.DecisionError, ValueError, OverflowError):
            return None
        return {"die_peak_c": die, "hydraulic_w": hydraulic}

    return one


def bounded_binding(binding, document):
    """`cooling_region.bounded_binding` for the 34-wide binding: the same replace, with `bounded_derive` above.
    Registered for 1.8 with `pool_version.register_region_bound` in `dispatch` (fff36693), so a region grade uses this
    34-wide derive, not cooling_region's 32-wide one."""
    import dataclasses

    from carbon.scoring import cooling_region

    return dataclasses.replace(
        binding,
        derive=bounded_derive(cooling_region.bounds(document), binding.version),
    )


def raw_u(version=VERSION):
    """Per-element U for the 34 slots (mirror of pool_adapters.cooling_raw_u, :467-506).
    Slots 0-31 follow the v1 rule; slots 32 (outlet_c) and 33 (peak_x_mm) are HUMAN_INPUT: refused until
    the owner registers their U. The die-peak U is never reused for them."""
    _require_version(version)
    raise V2Refused("HUMAN_INPUT_u_for_outlet_c_and_peak_x_mm")


def to_model_space(version=VERSION):
    """Native 34-value reference row -> encoded 34-value model-space row (v2 encode)."""
    _require_version(version)

    def convert(reference_row):
        import numpy as np

        return [
            float(v)
            for v in _v2().encode_targets(np.asarray([reference_row], dtype=float))[0]
        ]

    return convert


def official_binding():
    """The OFFICIAL pool binding of Cooling 1.8 (34 slots). Mirrors pool_adapters.official_binding
    (:650-676): the proof-suite controls refuse. Registered via pool_version.register_binding.
    """
    _require_version(VERSION)
    _require_v2_token()
    from carbon.scoring import pool_adapters, pool_plugin

    chosen = pool_adapters.adapter(
        KIND, VERSION
    )  # names, limits, objective (decision roles)

    def not_official(*_args, **_kwargs):
        raise pool_adapters.PoolAdapterRefused(
            "proof_suite_input_is_not_part_of_the_official_grade"
        )

    return pool_plugin.ChallengeBinding(
        kind=KIND,
        version=VERSION,
        input_names=chosen.input_names,
        design_names=chosen.design_names,
        derive=derive(VERSION),
        raw_u=not_official,
        train_mean_row=not_official,
        serve_good=not_official,
        serve_train=not_official,
        serve_default=not_official,
        train_box=not_official,
        to_model_space=to_model_space(VERSION),
        physics_gates=gates(VERSION),
    )


# -- the sealed module surface (delegation, as cooling18_dual_pack) ---------------------------------


def _decoded(rows):
    """Each predicted row decoded to the native 34-value row; a malformed row stays 34 NaN so the schema gate
    fails it as the candidate's typed gate failure (as cooling_encoded_dual_pack._decoded, :46-61, for 32).
    """
    return [_decode_native(row) or [math.nan] * WIDTH for row in rows]


def definition(*, bank, train_raw, rule="baseline_legs"):
    raise V2Refused("HUMAN_INPUT_cooling18_v2_measurement_definition")


def measure(**_kwargs):
    # The v2 measurement (scales / weights for outlet_c and peak_x_mm in A and D) is the owner's to define;
    # delegating to the 32-slot measurement would silently drop the two new outputs, so refuse.
    raise V2Refused("HUMAN_INPUT_cooling18_v2_measurement")


def applied_pack(**_kwargs):
    raise V2Refused("HUMAN_INPUT_cooling18_v2_34_wide_baseline")


def sealed_adapter(version):
    """The pool-graded adapter of Cooling 1.8 v2; None for any other version."""
    if version != VERSION:
        return None
    if POOL_VERSIONS[VERSION] is None:
        raise V2Refused("HUMAN_INPUT_cooling18_v2_sealed_evaluation_id")
    from carbon.scoring import pool_version

    evaluation, case_id = POOL_VERSIONS[VERSION]
    return pool_version.variant(
        _SELF, VERSION, evaluation, case_id, challenge_id=CHALLENGE
    )


def dispatch(config):
    """The overlay dispatch (shape: motor18_dual_pack.dispatch, :355-395). Registers the 34-slot binding in
    `pool_version` without editing pool_adapters.py. ``config`` must be empty."""
    if config:
        raise ValueError("Cooling 1.8 v2's dispatch takes no config")
    from carbon.scoring import pool_version

    # DOOR-START ARMING: a bad / mistyped / v1 output_encoding token on the 1.8 entry refuses here, once (the overlay
    # accepts any string). Everything below resolves tokens only through output_encoding_v2.
    _v2().arm(CHALLENGE, VERSION)
    pool_version.register_binding(KIND, VERSION, official_binding)
    # region hook (add-only, door-code head fff36693): used ONLY when a region is passed to official_binding;
    # same fn again is a no-op, a different fn raises ValueError. `bounded_binding` is (binding, region) -> binding
    # and refuses through cooling_region.RegionRefused (bounds()), which official_binding maps to ExamRefused.
    pool_version.register_region_bound(KIND, VERSION, bounded_binding)
    # HUMAN_INPUT / TODO: dev_grid.register(...) for the 34-wide practice grid, as cooling18_dual_pack.dispatch
    return {
        "challenge": CHALLENGE,
        "version": VERSION,
        "pool_versions": POOL_VERSIONS[VERSION],
        "adapter": sealed_adapter,
        # "adapter_for_bank" / "writer": as cooling18_dual_pack once the sealed pack is defined
    }


def producer_digest():
    from carbon.scoring import physical_dual_pack as physical

    return physical.producer_digest(_SELF)


def __getattr__(name):
    if name == "FILES":
        # 1.8 v2's OWN producer identity: the encoded sealed module's files, then this one. Names are carbon/scoring
        # files only (producer_digest reads them beside physical_dual_pack.py); the cold_plate encoding module is not
        # in any FILES today (v1 output_encoding.py is not either) and is pinned by the registry token.
        return (*_enc().FILES, _OWN_FILE)
    return getattr(_enc(), name)


_SELF = sys.modules[__name__]
