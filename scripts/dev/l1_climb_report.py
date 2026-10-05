"""Run battery's Level-1 climb over the registered variants and write its report.

GRAPHITE-L1-BUILD-01. CPU only: the climb's trials are Carbon's pod phase run
locally with a short step budget (`battery_level1.trial`). No pod, no GPU, no
spend, no live run. The report claims no level TESTED and opens nothing.

    JAX_PLATFORMS=cpu python scripts/dev/l1_climb_report.py OUT.json
"""

from __future__ import annotations

import json
import os
import sys
import time

os.environ.setdefault("JAX_PLATFORMS", "cpu")


def _summary(report):
    return {
        "status": report["status"],
        "findings": report["findings"],
        "steps": {
            name: {
                "state": step["state"],
                "runs": len(step["runs"]),
                "by_profile_and_status": sorted(
                    {(r["profile"], r["status"]) for r in step["runs"]}
                ),
            }
            for name, step in report["steps"].items()
        },
        "interaction_coverage": report["interaction_coverage"],
        "infrastructure_failures": report["infrastructure_failures"],
        "claims": report["claims"],
        "development_variant": report.get("development_variant"),
        "rebuild": report["rebuild"],
    }


def main(path):
    from carbon.agent_campaign.attack.adapters import battery_level1 as l1

    started = time.time()
    out = {
        "schema": "carbon.battery.level1-climb-evidence.v1",
        "rebuild": l1.REBUILD_LABEL,
        "trial_steps": l1.TRIAL_STEPS,
        "platform": "cpu",
        "identity": "OWNER-GRAPHITE-TEST-WAVE-04 section 1: nothing here is keyed "
        "on an expression digest",
        "alignment": "U1 and U2 are alignment findings for a live climb "
        "(OWNER-GRAPHITE-TEST-WAVE-04 section 2); this gate-and-trial climb does "
        "not measure them",
        "arms": {},
    }
    for arm in (None, l1.SIGNED_ARM):
        report = l1.climb_report(arm=arm)
        out["arms"][arm or "valid"] = {"summary": _summary(report), "report": report}
    out["seconds"] = round(time.time() - started)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(out, handle, indent=1, sort_keys=True, default=repr)
        handle.write("\n")
    for arm, body in out["arms"].items():
        summary = body["summary"]
        print(arm, summary["status"], len(summary["findings"]), "findings")
    print("seconds", out["seconds"])


if __name__ == "__main__":
    main(sys.argv[1])
