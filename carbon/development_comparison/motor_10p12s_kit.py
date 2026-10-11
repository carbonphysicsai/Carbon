"""The motor 10p/12s kit: Carbon's arm for the MOTOR-FEASIBILITY-02 panel
(MODEL-PREDICTIONS-FOR-EVIDENCE-01).

The panel's machine is a 10-pole, 12-slot, double-layer machine. Carbon's
motor Challenge kit (`carbon.motor`) is another machine (the GRUCAD 8-pole,
24-slot, single-layer frame), so it cannot predict this panel. This kit is
the panel machine's.

**The model** predicts the signed torque curve of one 2D slice: 48 samples at
0.25 degrees over 12 degrees (`t00` to `t47`). Its inputs are the design's six
grammar coordinates, the current density `j_a_mm2` and the current angle
`gamma_deg`.

**The observables** follow Data Collection's registered observer (the
sidecar's `skew` text), for a panel row with condition `J{j}-g{gamma}` and
action skew `s`. The step skew has three equal slices at mechanical offsets
d in {-s/2, 0, +s/2}:
- **each loaded slice** is the curve at current angle gamma - 5d (5 pole
  pairs), read at rotor angle theta + d;
- **the stack curve** is the mean of the three slices;
- **cogging** is the same mean of pure shifts of the J = 0 curve;
- **the observables** are the sampled-curve reductions
  (`cheap_baselines.curve_observables`).

A shift must be a whole number of samples. This reduction reproduces the
panel's own observables from the sidecar's curves exactly; that is a check of
the observer, not of a model.

**The panel's designs.** An export action names a bank index. The sidecar's
design with tag `s1-dNN` is index NN. Only its grammar coordinates are read,
never its cases.

**TRAIN**, `carbon.motor-10p12s.train-record.v1`, holds one record per
solved case:

    {"schema": ..., "case_id", "inputs": {six coordinates, "j_a_mm2",
     "gamma_deg"}, "outputs": {"t00", ..., "t47"}, "source": ...}

- **Until the registered TRAIN set lands,** `train_from_sidecar` builds
  DEVELOPMENT records from the sidecar's study designs. These are the 19
  designs with no `s1-` tag, which Data Collection confirmed are disjoint
  from the panel. Each record's `source` says so.
- **A 96-sample curve** is read at every other sample.
- **A case that is not OK** is excluded.

The scaling bounds are used only to scale the inputs. Support is TRAIN's own
observed range. DEVELOPMENT only, with no claim of physical validity,
qualification or value.
"""

from __future__ import annotations

import json
import re

import numpy as np

from .carbon_arm import ArmRefused, Kit, sha256

FAMILY = "motor"
TRAIN_SCHEMA = "carbon.motor-10p12s.train-record.v1"
SIDECAR_SCHEMA = "carbon.motor.curve-sidecar.v1"
SAMPLES, STEP_DEG = 48, 0.25
POLE_PAIRS = 5
OBSERVABLES = ("cogging_nm", "mean_nm", "pk_pk_nm", "ripple_fraction")
OUTPUTS = tuple(f"t{i:02d}" for i in range(SAMPLES))
GRAMMAR = (
    "magnet_mm",
    "coverage",
    "airgap_mm",
    "tooth_frac",
    "opening_frac",
    "slot_bottom_mm",
)
#: Scaling bounds only (generous ranges around the sidecar's grammar).
INPUTS = (
    ("magnet_mm", (1.5, 4.0)),
    ("coverage", (0.6, 0.95)),
    ("airgap_mm", (0.3, 1.0)),
    ("tooth_frac", (0.2, 0.45)),
    ("opening_frac", (0.03, 0.12)),
    ("slot_bottom_mm", (34.0, 42.0)),
    ("j_a_mm2", (0.0, 15.0)),
    ("gamma_deg", (-15.0, 15.0)),
)
PANEL_TAG = "s1-d"
STUDY_SOURCE = (
    "DEVELOPMENT stand-in: the sidecar's 19 study designs, disjoint from the "
    "panel (Data Collection); the registered TRAIN set replaces it"
)
_CONDITION = re.compile(r"J(?P<j>[0-9]+(?:\.[0-9]+)?)-g(?P<g>-?[0-9]+(?:\.[0-9]+)?)\Z")


def _sidecar(data):
    sidecar = json.loads(data)
    if type(sidecar) is not dict or sidecar.get("schema") != SIDECAR_SCHEMA:
        raise ArmRefused("SIDECAR_SCHEMA")
    return sidecar


def _panel_index(design):
    indices = [
        int(t[len(PANEL_TAG) :]) for t in design["tags"] if t.startswith(PANEL_TAG)
    ]
    return indices[0] if indices else None


def _curve(case):
    torque = np.asarray(case["torque_nm"], float)
    angles = np.asarray(case["angle_deg"], float)
    stride = len(torque) // SAMPLES
    if (
        stride < 1
        or len(torque) != SAMPLES * stride
        or not np.allclose(angles[::stride], np.arange(SAMPLES) * STEP_DEG)
    ):
        raise ArmRefused("SIDECAR_CURVE_GRID")
    return torque[::stride]


def train_from_sidecar(data):
    """DEVELOPMENT TRAIN records (JSONL bytes) from the sidecar's study
    designs; the panel's designs are never included."""
    sidecar = _sidecar(data)
    lines = []
    for key in sorted(sidecar["designs"]):
        design = sidecar["designs"][key]
        if _panel_index(design) is not None:
            continue
        for case in design["cases"]:
            if case.get("status") != "OK":
                continue
            curve = _curve(case)
            lines.append(
                json.dumps(
                    {
                        "schema": TRAIN_SCHEMA,
                        "case_id": key + ":" + case["case_id"],
                        "inputs": {
                            **{n: design["grammar"][n] for n in GRAMMAR},
                            "j_a_mm2": case["j_a_mm2"],
                            "gamma_deg": case["gamma_deg"],
                        },
                        "outputs": {o: float(v) for o, v in zip(OUTPUTS, curve)},
                        "source": STUDY_SOURCE,
                    },
                    sort_keys=True,
                )
            )
    return ("\n".join(lines) + "\n").encode()


def _shift(degrees):
    k = degrees / STEP_DEG
    if abs(k - round(k)) > 1e-9:
        raise ArmRefused("SKEW_NOT_ON_THE_SAMPLE_GRID")
    return round(k)


def kit(geometry):
    """The kit, given each panel design's grammar coordinates by bank index."""

    def condition(row):
        found = _CONDITION.fullmatch(row["condition"])
        if found is None:
            raise ArmRefused("CONDITION_UNREADABLE")
        return float(found["j"]), float(found["g"])

    def offsets(row):
        s = float(row["action"]["skew_deg"])
        return (-s / 2, 0.0, s / 2)

    def queries(row):
        index = row["action"]["design"]
        if index not in geometry:
            raise ArmRefused("PANEL_DESIGN_UNKNOWN")
        j, gamma = condition(row)
        base = dict(geometry[index])
        loaded = [
            {**base, "j_a_mm2": j, "gamma_deg": gamma - POLE_PAIRS * d}
            for d in offsets(row)
        ]
        return [*loaded, {**base, "j_a_mm2": 0.0, "gamma_deg": 0.0}]

    def reduce(row, predicted):
        from . import cheap_baselines as cb

        curves = [np.asarray([p[o] for o in OUTPUTS]) for p in predicted]
        shifts = [_shift(d) for d in offsets(row)]
        loaded = np.mean([np.roll(c, -k) for c, k in zip(curves[:3], shifts)], 0)
        cogging = np.mean([np.roll(curves[3], -k) for k in shifts], 0)
        try:
            return cb.curve_observables(loaded, cogging)
        except (ValueError, cb.Unsupported):
            raise ArmRefused("CURVE_OBSERVABLES_UNDEFINED") from None

    return Kit(
        kit_id="carbon.motor-10p12s.kit.v1",
        family=FAMILY,
        train_schema=TRAIN_SCHEMA,
        inputs=INPUTS,
        categorical=frozenset(),
        observables=OBSERVABLES,
        row_inputs=lambda row: queries(row)[1],
        model_id="carbon.motor-10p12s.mlp-default.v1",
        outputs=OUTPUTS,
        queries=queries,
        reduce=reduce,
    )


def kit_from_bytes(material):
    """The kit from the sidecar's bytes: the panel designs' grammar only."""
    if material is None:
        raise ArmRefused("MATERIAL_REQUIRED")
    sidecar = _sidecar(material)
    geometry = {}
    for design in sidecar["designs"].values():
        index = _panel_index(design)
        if index is not None:
            geometry[index] = {n: design["grammar"][n] for n in GRAMMAR}
    return kit(geometry)


def main(argv=None):
    """Write the DEVELOPMENT TRAIN records from a pinned sidecar."""
    import argparse
    from pathlib import Path

    parser = argparse.ArgumentParser(description=main.__doc__)
    parser.add_argument("--sidecar", required=True)
    parser.add_argument("--sidecar-sha256", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    data, out = Path(args.sidecar).read_bytes(), Path(args.out)
    if sha256(data) != args.sidecar_sha256:
        print(json.dumps({"status": "REFUSED", "reason": "SIDECAR_SHA256_MISMATCH"}))
        return 2
    if out.exists():
        print(json.dumps({"status": "REFUSED", "reason": "OUTPUT_EXISTS"}))
        return 2
    body = train_from_sidecar(data)
    out.write_bytes(body)
    print(json.dumps({"status": "COMPLETED", "sha256": sha256(body)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
