"""Level 4 attack specimens (development only): one per row of the proposal's
§8.1 and §8.3 (`docs/development/graphite/LEVEL4_GRAPH_CONSTRUCTION_PROPOSAL.md`).

Claims tested:

1. Every row of §8.1 and §8.3 has a specimen, or a recorded owner where no
   graph gate can test it (G7, Phase 4, G5/D3, not applicable).
2. Every executed specimen is refused at its expected gate with its
   expected code; cap specimens name the cap they cross.
3. An honest graph under the same fixture caps is admitted (the control).
4. The fixture caps are test values, never the allowlist's caps, which all
   stay HUMAN_INPUT.
"""

from __future__ import annotations

import os

import pytest

pytest.importorskip("jax")
os.environ.setdefault("JAX_PLATFORMS", "cpu")

from carbon.level4 import allowlist as allowlist_module
from carbon.level4 import specimens

#: The proposal's §8.1 and §8.3 rows, by family.
ROWS_8_1 = {
    "Network access, undeclared dependencies",
    "Model loaders, hidden assets",
    "Embedded weights or tables",
    "Child processes, resource escapes",
    "Caches, checkpoints, cross-attempt residue",
    "Run identification, timing feedback",
    "Construction-to-evaluator access, answer-key exfiltration",
    "Hidden preprocessing, inference/solver hybrids",
    "Malformed outputs, nonfinite values, parser abuse",
}
ROWS_8_3 = {
    "Callback smuggling",
    "Constant splitting",
    "Procedural tables",
    "Unbounded loop",
    "Compute under-counting",
    "Compile bomb",
    "Compiler exploit",
    "Trace-time divergence",
    "Nondeterminism",
    "RNG leakage",
    "Interface abuse",
    "Initializer abuse",
}


@pytest.fixture(scope="module")
def suite():
    return specimens.attack_suite(allowlist_module.load(), max_bytes=1 << 26)


def test_every_row_has_a_specimen_or_an_owner(suite):
    families = {(r["section"], r["family"]) for r in suite}
    assert ROWS_8_1 <= {f for s, f in families if s == "8.1"}
    assert ROWS_8_3 == {f for s, f in families if s == "8.3"}
    for row in suite:
        if row["status"] == "recorded":
            assert row["owner"], row


def test_every_executed_specimen_hits_its_gate(suite):
    executed = [r for r in suite if r["status"] != "recorded"]
    assert len(executed) >= 18
    findings = [r for r in executed if r["status"] != "pass"]
    assert findings == [], findings
    caps = [r["observed"] for r in executed if r["observed"].startswith("cap_exceeded")]
    assert caps and all(c.split(":", 1)[1] in allowlist_module.CAPS for c in caps)
    control = [r for r in executed if r["section"] == "control"]
    assert control and control[0]["observed"] == "admitted"


def test_fixture_caps_are_not_the_allowlists():
    assert set(allowlist_module.CAPS.values()) == {allowlist_module.HUMAN_INPUT}
    assert set(specimens.FIXTURE_CAPS) == set(allowlist_module.CAPS)
    assert allowlist_module.HUMAN_INPUT not in specimens.FIXTURE_CAPS.values()
