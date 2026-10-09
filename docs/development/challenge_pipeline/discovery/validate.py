"""Read-only checks of the discovery dossier; no solver, network or third-party imports."""
from __future__ import annotations

import json
import math
from pathlib import Path
import re


def close(a: float, b: float) -> None:
    assert math.isclose(a, b, rel_tol=1e-10, abs_tol=1e-10), (a, b)


def main() -> None:
    root = Path(__file__).resolve().parent
    data = json.loads((root / "data.json").read_text(encoding="utf-8"))
    longlist, cards = data["longlist"], data["shortlist"]
    assert len(longlist) == 80 and len(cards) == 15
    assert len({r["domain"] for r in longlist}) == 16
    assert len({r["id"] for r in longlist}) == 80
    assert len({r["id"] for r in cards}) == 15
    sources = {s["id"]: s for s in data["sources"]}
    assert len(sources) == len(data["sources"])
    by_id = {r["id"]: r for r in longlist}
    costs = data["cost_assumptions"]
    assert data["admitted_count"] == data["solver_runs"] == data["spend_eur"] == 0
    assert data["adoption"] == "HUMAN_INPUT"
    assert not data["dispatch_ready"] and not data["protected_material"]
    assert not data["historical_rescore"]
    assert not costs["all_in_bill_verified"]

    def bill(cpu: float, equivalents: int) -> float:
        return (costs["rate_eur_node_h"] *
                (equivalents * cpu * costs["elapsed_to_cpu_ratio"] +
                 costs["setup_idle_fit_node_h"]) *
                costs["tax_stress_multiplier"] + costs["other_reserve_eur"])

    for row in longlist:
        assert row["solver_source"] in sources
        assert row["customer_packet"] == "HUMAN_INPUT" and not row["admitted"]
        assert sorted(row["c1_cpu_h_low_base_high"]) == row["c1_cpu_h_low_base_high"]
        assert min(row["c1_cpu_h_low_base_high"]) > 0
    for i, card in enumerate(cards, 1):
        assert card["id"] in by_id and card["name"] == by_id[card["id"]]["name"]
        assert card["solver"] == by_id[card["id"]]["solver_source"]
        assert all(s in sources for s in card["sources"]) and len(card["sources"]) >= 2
        assert card["computed_base_rank"] == i
        assert not card["admitted"] and not card["dispatch_ready"]
        assert card["earned_credibility"] == "NOT_DEMONSTRATED"
        assert card["p50_cpu_h"] is None and card["p95_cpu_h"] is None
        assert all(v != "PASS" for v in card["gates"].values())
        assert card["gates"]["G6"].startswith("FAIL") == (card["C2_eur"][2] > 100)
        assert card["equivalent_cases"] == (
            card["primary_cases"] + 2 * card["refined_cases"] +
            card["charged_failed"] + 2 * card["witness_pairs"])
        assert card["primary_cases"] == card["designs"] * card["strata"]
        for j in range(3):
            close(card["V2_eur"][j], card["engineer_h"][j] * card["engineer_rate_eur_h"][j])
            close(card["V3_decisions_year"][j], card["teams"][j] * card["decisions_per_team_year"][j])
            close(card["annual_gross_eur"][j], card["V2_eur"][j] * card["V3_decisions_year"][j])
            close(card["C2_eur"][j], bill(card["c1_cpu_h"][j], card["equivalent_cases"]))
            close(card["C3_weekly_eur"][j], card["C2_eur"][j] *
                  costs["weekly_windows_R"][j] / costs["refresh_exposure_E"][j])
        denominators = [card["C2_eur"][j] + 52 * card["C3_weekly_eur"][j] for j in range(3)]
        for j, n, d in [(0, 0, 2), (1, 1, 1), (2, 2, 0)]:
            close(card["VCI_low_base_high"][j], card["annual_gross_eur"][n] / denominators[d])
        if card["conditional_queue_rank"] is not None:
            panel = card["first_panel"]
            assert panel["equivalent_cases"] == (
                panel["primary_cases"] + 2 * panel["refined_cases"] +
                panel["control_cases"] + panel["witness_cases"] + panel["charged_failures"])
            for j in range(3):
                close(panel["eur_low_base_high"][j], bill(card["c1_cpu_h"][j], panel["equivalent_cases"]))
            text = (root / "dossiers" / (card["slug"] + ".md")).read_text(encoding="utf-8")
            numbers = re.findall(r"^## (\d+)\.", text, re.M)
            assert numbers == [str(n) for n in range(1, 14)], card["slug"]
            assert "HUMAN_INPUT" in text and "NONE_FEASIBLE" in text
    order = sorted(cards, key=lambda c: (-c["VCI_low_base_high"][1], -c["excitement_low_base_high"][1]))
    assert [c["slug"] for c in cards] == [c["slug"] for c in order]
    queue = [c for c in cards if c["conditional_queue_rank"] is not None]
    assert [c["conditional_queue_rank"] for c in queue] == list(range(1, 6))
    assert [c["slug"] for c in queue] == [
        "solenoid-pole", "seal-gland", "planar-transformer", "bolted-joint", "compliant-gripper"]
    expected = {
        "README.md", "owner-summary.md", "methodology.md", "sources.md",
        "longlist.md", "shortlist.md", "comparison.md", "data.json", "validate.py",
        *("dossiers/" + c["slug"] + ".md" for c in queue),
    }
    actual = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}
    assert actual == expected, actual ^ expected
    for path in root.rglob("*.md"):
        content = path.read_text(encoding="utf-8")
        for target in re.findall(r"\]\(([^\s)]+)\)", content):
            if target.startswith(("https://", "http://", "#")):
                continue
            resolved = (path.parent / target.split("#", 1)[0]).resolve()
            assert resolved.is_relative_to(root) and resolved.is_file(), (path, target)
    words = len((root / "owner-summary.md").read_text(encoding="utf-8").split())
    assert words <= 550, words
    print("PASS: 80 rows, 16 domains, 15 cards, five complete conditional dossiers; "
          "cost/value/rank/source/link/manifest checks; zero admitted, no dispatch.")


if __name__ == "__main__":
    main()
