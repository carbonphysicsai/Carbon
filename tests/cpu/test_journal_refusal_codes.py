"""Every journal refusal names its specific code and one plain sentence.

M1 S16 (2026-10-21): a Graphite toolbox refusal (reason_code and status, no
correction_code) read "A request refused: no reason recorded", and a research
tool correction read only the generic "contract_incompatibility".
"""

from __future__ import annotations

from scripts.dev.miner_launchpad import campaign_view as view


def _refusal_text(item):
    entries = view.feed({"refusals": [{"sequence": 1, **item}]}, [])["entries"]
    (entry,) = [e for e in entries if e.get("kind") == "refusal"]
    return entry


def test_a_correction_names_its_own_code_and_meaning():
    entry = _refusal_text(
        {
            "operation": "start_research_task",
            "reason": "contract_incompatibility",
            "correction_code": "workspace_recipe_forbidden",
        }
    )
    assert entry["code"] == "workspace_recipe_forbidden"
    assert "refused: workspace_recipe_forbidden. kind=workspace" in entry["text"]
    assert "contract_incompatibility" not in entry["text"]


def test_a_toolbox_refusal_names_its_reason_code_and_meaning():
    entry = _refusal_text(
        {
            "status": "REFUSED_PROTECTED_MATERIAL_IN_RESULT",
            "reason_code": "protected_material_in_result",
        }
    )
    assert entry["code"] == "protected_material_in_result"
    assert "no reason recorded" not in entry["text"]
    assert "withheld this tool result" in entry["text"]


def test_a_generic_reason_still_reads_and_nothing_reads_as_nothing():
    assert _refusal_text({"reason": "contract_incompatibility"})["code"] == (
        "contract_incompatibility"
    )
    entry = _refusal_text({})
    assert entry["text"].endswith("no reason recorded") and "code" not in entry


def test_a_non_code_value_is_never_shown_as_a_code():
    entry = _refusal_text({"reason_code": "Not A Code <script>"})
    assert "code" not in entry and "<script>" not in entry["text"]
