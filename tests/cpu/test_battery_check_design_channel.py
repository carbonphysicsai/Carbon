"""`check_design` as a leak-ladder channel (v2 amendment 4, section D3).

`check_design` returns a verdict per choice and, for a fully rebuildable
design, the canonical design Carbon would rebuild. It costs the agent a model
call and no research trial, so it is a nearly free oracle. Amendment 4 records
the structural half of that channel: the answer is a function of the design
and the public construction contract, and the code that answers it loads no
module that holds the exam's pool, seeds, truth or evaluation state.

An absence check proves nothing on its own. The same probe is run on the
battery daemon, which does hold that state, and must find it there.
"""

from __future__ import annotations

import json
import subprocess
import sys

#: Modules that hold or evaluate realized exam material.
EXAM_STATE_MODULES = (
    "carbon.battery.pool_store",
    "carbon.battery.seeds",
    "carbon.battery.truth",
    "carbon.battery.truth_env",
    "carbon.battery.exam",
    "carbon.battery.daemon",
    "carbon.battery.operate",
    "carbon.battery.deployment",
)

_CHECK = """
import json, sys
from carbon.development_session.design_check import check_design
from carbon.reconstruction.capability_registry import BATTERY_CHALLENGE
result = check_design({"strategy": {
    "schema_version": "1.0", "challenge_id": BATTERY_CHALLENGE,
    "backbone": "mlp", "parameters": {"width": 64}}})
print(json.dumps({"verdict": result["verdict"],
                  "accepted": result.get("rebuild", {}).get("accepted"),
                  "modules": sorted(m for m in sys.modules if m.startswith("carbon."))}))
"""

_DAEMON = """
import json, sys
import carbon.battery.daemon
print(json.dumps({"modules": sorted(m for m in sys.modules if m.startswith("carbon."))}))
"""


def _loaded(source):
    """The Carbon modules a fresh interpreter has loaded after `source`."""
    done = subprocess.run(
        [sys.executable, "-c", source], capture_output=True, text=True, check=True
    )
    return json.loads(done.stdout.strip().splitlines()[-1])


def test_check_design_answers_without_loading_exam_state():
    probe = _loaded(_CHECK)
    # The compile path really ran: a battery design was rebuilt, lazily
    # importing the battery compiler, so the absence below covers it.
    assert probe["verdict"] == "submittable"
    assert probe["accepted"] is True
    assert "carbon.battery.compile" in probe["modules"]
    assert not set(EXAM_STATE_MODULES) & set(probe["modules"])


def test_the_probe_finds_exam_state_where_it_is():
    """Specimen: the daemon, which scores the exam, loads the pool, the
    seeds and the exam rule, and the same probe sees them."""
    modules = set(_loaded(_DAEMON)["modules"])
    assert {
        "carbon.battery.pool_store",
        "carbon.battery.seeds",
        "carbon.battery.exam",
        "carbon.battery.daemon",
    } <= modules
