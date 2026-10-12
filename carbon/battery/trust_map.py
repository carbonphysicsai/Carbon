"""Battery's public/released DEVELOPMENT trust-map adapter and offline CLI.

    python -m carbon.battery.trust_map --panel disclosed-panel.json --out DIR

The caller supplies an explicitly disclosed projection and accepted reference
verification evidence. No solver, model training, protected store or score
selection is reachable here. JSON/SVG outputs contain aggregates only.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from carbon.trust_map.core import MapRefused, build_maps, write_maps


def battery_spec():
    """Display bins from public bounds; near-limit values reuse the public domain.

    Bin widths and SOC thirds are visualization choices, not population strata,
    scientific gates, tolerances or qualification thresholds.
    """
    from carbon.battery.domain import (
        CAPACITY_CYCLES,
        GRID_POINTS,
        INPUT_BOUNDS,
        PLATING_BAND_V,
        T_IMPORTANT_C,
    )

    def edges(name, bins):
        low, high = INPUT_BOUNDS[name]
        return [low + (high - low) * i / bins for i in range(bins + 1)]

    return {
        "axes": [
            {"name": "c1", "edges": edges("c1", 6)},
            {"name": "t_amb_c", "edges": edges("t_amb_c", 7)},
        ],
        "bands": {"name": "soc0", "edges": edges("soc0", 3)},
        "marginalized": ["c2"],
        "outputs": {
            "voltage_v": {"length": GRID_POINTS, "unit": "V"},
            "temperature_c": {"length": GRID_POINTS, "unit": "C"},
            "plating_margin_v": {"length": 1, "unit": "V"},
            "capacity_ah": {"length": len(CAPACITY_CYCLES), "unit": "Ah"},
        },
        "near_limit": [
            {
                "output": "plating_margin_v",
                "statistic": "abs_min",
                "operator": "le",
                "value": PLATING_BAND_V,
            },
            {
                "output": "temperature_c",
                "statistic": "max",
                "operator": "ge",
                "value": T_IMPORTANT_C,
            },
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--panel", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    panel = json.loads(args.panel.read_text(encoding="utf-8"))
    maps = build_battery_maps(panel)
    print(json.dumps({"maturity": "DEVELOPMENT", "maps": write_maps(maps, args.out)}))
    return 0


def build_battery_maps(panel):
    """Require the pooled input to remain within battery's public bounds too."""
    from carbon.battery.domain import INPUT_BOUNDS

    maps = build_maps(panel, battery_spec())
    low, high = INPUT_BOUNDS["c2"]
    for case in panel["cases"]:
        value = case["inputs"]["c2"]
        if (
            type(value) not in (int, float)
            or not math.isfinite(value)
            or not low <= value <= high
        ):
            raise MapRefused("c2_outside_public_bounds")
    return maps


if __name__ == "__main__":
    raise SystemExit(main())
