"""The f02 kit: Carbon's arm for the transient-heat (burst schedule) panel
(MODEL-PREDICTIONS-FOR-EVIDENCE-01).

f02 has no Carbon Challenge kit. This kit is built on the panel's own axes
(REFERENCE-PACKAGES-01, `f02-menu-v2/registry.json`, and the TRAIN plan
`f02-menu-v2/train-registry.json`, 7d0414ea6):
- **contexts:** the 24 round-one contexts, which are the cooling pair
  (30 C at 2500 W/m2K, or 40 C at 1500 W/m2K) x initial temperature 40/55 C
  x left-source split 0.5/0.8 x waveform rectangular/ramp/two-pulse;
- **actions:** `peak_w` and `on_time_s`;
- **observables:** `peak_top_c` (the die-top maximum over 120 s) and
  `extra_energy_j` (the waveform integral above the 20 W base).

**The export** (Data Collection's names) has one plain question per context.
A row's condition is its context, `c{coolant}-i{initial}-s{split}-{waveform}`
(for example `c40-i55-s0.8-rectangular`), and its action is
`{peak_w, on_time_s}`.

**TRAIN** (`carbon.f02.train-record.v1`) holds 960 seeded cases, 40 per
context:
- **the draw:** peak uniform on [80, 140] W and on-time uniform on [5, 20] s;
- **disjoint from the test menu by construction:** no menu point
  (peak {80, 100, 120, 140} x on-time {5, 10, 15, 20}) is drawn;
- **the outputs** come from the panel's own observer.

Its inputs are `coolant_c`, `h_w_m2_k`, `initial_c`, `left_source_fraction`,
`waveform`, `peak_w` and `on_time_s`; the context axes are one-hot encoded.

**Support is the registered TRAIN domain** (`domain`): a registered context,
with peak and on-time inside the plan's draw ranges. The menu's points lie on
and inside the draw boundary, so a support taken from the observed TRAIN range
would refuse them. The plan's own domain is the honest support instead.
`carbon_arm.domain_gaps` is the check that the plan covers every panel row,
and the run refuses when it does not.

DEVELOPMENT only, with no claim of physical validity, qualification or value.
"""

from __future__ import annotations

import re

from .carbon_arm import ArmRefused, Kit

FAMILY = "f02"
TRAIN_SCHEMA = "carbon.f02.train-record.v1"
OBSERVABLES = ("peak_top_c", "extra_energy_j")
#: The registered axes (`f02-menu-v2/registry.json`).
COOLING = ((30.0, 2500.0), (40.0, 1500.0))
INITIAL_C = (40.0, 55.0)
SPLITS = (0.5, 0.8)
WAVEFORMS = ("rectangular", "ramp", "two-pulse")
#: The TRAIN plan's draw ranges (`f02-menu-v2/train-registry.json`).
PEAK_W = (80.0, 140.0)
ON_TIME_S = (5.0, 20.0)
_CONTEXT = re.compile(
    r"c(?P<c>[0-9.]+)-i(?P<i>[0-9.]+)-s(?P<s>[0-9.]+)-(?P<w>rectangular|ramp|two-pulse)\Z"
)


def context(condition):
    """A context's axes from its condition id; refused when it names no
    registered context."""
    found = _CONTEXT.fullmatch(condition)
    if found is None:
        raise ArmRefused("CONDITION_UNREADABLE")
    coolant = float(found["c"])
    pairs = dict(COOLING)
    if coolant not in pairs:
        raise ArmRefused("CONTEXT_UNREGISTERED")
    return {
        "coolant_c": coolant,
        "h_w_m2_k": pairs[coolant],
        "initial_c": float(found["i"]),
        "left_source_fraction": float(found["s"]),
        "waveform": found["w"],
    }


def row_inputs(row):
    """An export physical row's inputs: its context (from its condition) and
    its action. Reference values are never read."""
    action = row["action"]
    return {
        **context(row["condition"]),
        "peak_w": action["peak_w"],
        "on_time_s": action["on_time_s"],
    }


def domain(inputs):
    """The registered TRAIN domain: a registered context, with peak and
    on-time inside the plan's draw ranges."""
    return (
        (inputs["coolant_c"], inputs["h_w_m2_k"]) in COOLING
        and inputs["initial_c"] in INITIAL_C
        and inputs["left_source_fraction"] in SPLITS
        and inputs["waveform"] in WAVEFORMS
        and PEAK_W[0] <= inputs["peak_w"] <= PEAK_W[1]
        and ON_TIME_S[0] <= inputs["on_time_s"] <= ON_TIME_S[1]
    )


KIT = Kit(
    kit_id="carbon.f02.kit.v1",
    family=FAMILY,
    train_schema=TRAIN_SCHEMA,
    inputs=(("peak_w", PEAK_W), ("on_time_s", ON_TIME_S)),
    categorical=frozenset(),
    observables=OBSERVABLES,
    row_inputs=row_inputs,
    model_id="carbon.f02.mlp-default.v1",
    onehot=(
        ("coolant_c", tuple(c for c, _ in COOLING)),
        ("h_w_m2_k", tuple(h for _, h in COOLING)),
        ("initial_c", INITIAL_C),
        ("left_source_fraction", SPLITS),
        ("waveform", WAVEFORMS),
    ),
    domain=domain,
)
