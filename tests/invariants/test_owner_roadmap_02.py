from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
POLICY = json.loads(
    (ROOT / ".agent/policies/owner_roadmap_02.json").read_text(encoding="utf-8")
)


def test_deferred_research_is_explicitly_non_blocking() -> None:
    research = POLICY["research_program"]
    assert research["ticket"] == "B-E4"
    assert research["status"] == "DEFERRED"
    assert set(research["disposition"]) == {"OPTIONAL", "NON_BLOCKING"}
    assert research["evidence_status"] == "UNMEASURED"
    assert research["retained_engineering"] is True
    assert research["paid_execution_authorized"] is False
    assert set(POLICY["must_not_gate"]) == {
        "B-GATE",
        "WAVE-C",
        "NETWORK_INTEGRATION",
        "TESTNET",
        "MAINNET",
        "RESEARCH_CONCIERGE",
    }


def test_b_gate_has_no_be4_dependency_or_utility_pass_gate() -> None:
    ticket = (ROOT / ".agent/tickets/B-GATE_closeout.md").read_text(encoding="utf-8")
    depends_line = next(
        line for line in ticket.splitlines() if line.startswith("**Depends on:**")
    )
    assert "B-E4" not in depends_line
    assert "preregistered utility rule passes" not in ticket
    assert "gauntlet evidence blocks closeout" not in ticket
    assert "OPTIONAL / DEFERRED / NON-BLOCKING" in ticket


def test_concierge_release_contract_is_not_research_qualification() -> None:
    concierge = POLICY["concierge"]
    assert concierge["empirical_effectiveness"] == "UNMEASURED"
    assert concierge["network_path_blocking"] is False
    assert concierge["disabled_release_allowed"] is True
    assert concierge["paid_benchmark_required"] is False
    assert concierge["statistical_utility_lift_required"] is False
    assert concierge["independent_research_qualification_required"] is False
    assert len(concierge["required_engineering_controls"]) >= 10
