"""The battery v3 kit: Carbon's arm for the battery ambient-map v3 panel
(MODEL-PREDICTIONS-FOR-EVIDENCE-01, option (a)).

Carbon's battery Challenge kit (`carbon.battery`) has inputs `c1` [0.5, 2],
`c2`, `t_amb_c` and `soc0`, and no switch voltage or cooling. The v3 panel's
actions vary both, and `c1` goes down to 0.25. This kit covers the v3 action
space:
- **inputs:** `c1`, `c2`, `switch_v`, `cooling` (categorical x1/x2/x4) and
  `ambient_c` (the panel's band);
- **outputs:** the panel's five observables, directly.

It trains on a registered v3 TRAIN set that Data Collection solves with the
panel's solver, disjoint from the panel. Until that set exists, it runs only
on synthetic fixtures (`SYNTHETIC_FIXTURE`).

**The TRAIN record** (one JSON object per line), `carbon.battery-v3.train-record.v1`:

    {"schema": "carbon.battery-v3.train-record.v1", "case_id": "...",
     "inputs": {"c1", "c2", "switch_v", "cooling", "ambient_c"},
     "outputs": {"charging_t_max_c", "minutes", "plating_min_v",
                 "q30_over_q1", "v_max_v"},
     "fixture": true}

`fixture` is present (true) only for synthetic records. An output that is
not finite excludes its record and is counted, never repaired.

The scaling bounds below are used only to scale the inputs, never to judge
support: support is TRAIN's own observed range. They make no claim about the
population.
"""

from __future__ import annotations

from .carbon_arm import Kit

FAMILY = "battery-v3"
TRAIN_SCHEMA = "carbon.battery-v3.train-record.v1"
OBSERVABLES = (
    "charging_t_max_c",
    "minutes",
    "plating_min_v",
    "q30_over_q1",
    "v_max_v",
)
#: Scaling bounds (the panel's registered action ranges and bands).
INPUTS = (
    ("c1", (0.25, 2.0)),
    ("c2", (0.25, 2.0)),
    ("switch_v", (4.0, 4.15)),
    ("cooling", (1, 4)),
    ("ambient_c", (5.0, 40.0)),
)


def row_inputs(row):
    """An export physical row's inputs: its action and its band (the ambient
    temperature). The row's reference values are never read."""
    action = row["action"]
    return {
        "c1": action["c1"],
        "c2": action["c2"],
        "switch_v": action["switch_v"],
        "cooling": action["cooling"],
        "ambient_c": row["band"],
    }


KIT = Kit(
    kit_id="carbon.battery-v3.kit.v1",
    family=FAMILY,
    train_schema=TRAIN_SCHEMA,
    inputs=INPUTS,
    categorical=frozenset({"cooling"}),
    observables=OBSERVABLES,
    row_inputs=row_inputs,
    model_id="carbon.battery-v3.mlp-default.v1",
)
