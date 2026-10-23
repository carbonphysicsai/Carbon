"""Newcomer fixes (codex-queue/handoff-20261021/EASY_MINER_FIX_LIST_20261023.md)."""

import re
from pathlib import Path

from scripts.dev.miner_launchpad import supervisor

ROOT = Path(__file__).resolve().parents[2]


def test_no_miner_text_says_read_the_code():
    # E9: "Read the code: it names what was refused" was not a step a
    # newcomer could take.
    for entry in (*supervisor.NEXT_ACTIONS.values(), supervisor.FALLBACK_ACTION):
        assert "read the code" not in entry.lower()
    for name in ("app.js", "research_view.js", "index.html"):
        text = (ROOT / "scripts/dev/miner_launchpad" / name).read_text(encoding="utf-8")
        assert not re.search(r"read the code", text, re.IGNORECASE), name


def test_a_code_without_its_own_entry_is_said_in_words():
    words = supervisor.next_action("catalog_setting_unknown_for_example")
    assert words.startswith("Refused: catalog setting unknown for example.")
    assert "Your campaign and any frozen candidate are kept" in words
    # Generic, so it may follow a charge or a used slot: it never says
    # nothing was lost (Validator).
    assert "nothing was lost" not in words.lower()
    # A code with its own entry keeps it.
    assert supervisor.next_action("construction_intake_unavailable") == (
        supervisor.NEXT_ACTIONS["construction_intake_unavailable"]
    )


def test_each_implemented_challenge_says_whether_it_can_be_practised():
    # E11: Battery could not practise, yet was offered like the others.
    from scripts.dev.miner_launchpad import capabilities

    state = {"configured": False, "reason": "profile_unset", "next_action": "-"}
    entries = [e for e in capabilities._challenges(state, None) if e.get("implemented")]
    assert entries
    for entry in entries:
        ready = entry["practise"]["ready"]
        assert ready == bool(entry["example_strategy"] or entry["catalog_recipes"])
        if not ready:
            assert entry["practise"]["plain"].startswith("Coming soon")


def test_codes_that_can_follow_a_submit_have_their_own_step():
    # Validator, E9 follow-up: the codes that can follow a spend first.
    for code in (
        "construction_request_deadline",
        "construction_intake_answer_unrecognised",
        "construction_snapshot_unavailable",
        "construction_intake_contract_mismatch",
        "construction_intake_identity_mismatch",
        "construction_intake_changed_since_submission",
        "construction_contract_not_registered",
        "construction_contract_binding_mismatch",
        "construction_admission_record_required",
        "exam_feedback_unavailable",
        "exam_feedback_reply_invalid",
    ):
        assert code in supervisor.NEXT_ACTIONS, code
        assert "nothing was lost" not in supervisor.NEXT_ACTIONS[code].lower()


def test_an_unknown_catalog_setting_lists_the_settings_that_place_takes():
    # R9-1: an agent put "backbone" into an F02 catalog recipe's configuration
    # and the refusal never said which settings the entry takes.
    import copy

    from carbon.challenge_registry.campaigns import challenge_ref
    from carbon.development_session.research_service import construction_recipe_issues
    from carbon.development_session.research_tools import catalog_setting_choices
    from carbon.registry.model import ChallengeKey
    from scripts.dev.miner_launchpad.toolbox import catalog_recipes

    ref = challenge_ref("f02")
    recipe = copy.deepcopy(catalog_recipes("f02", ref["version"])[0]["recipe"])
    recipe["procedure"]["configuration"] = {
        "backbone": "physicsnemo.FullyConnected",
        "learning_rate": 0.001,
    }
    (issue,) = construction_recipe_issues(recipe, ChallengeKey("f02", ref["version"]))
    assert issue.code == "catalog_setting_unknown"
    assert "learning_rate" in issue.allowed and "backbone" not in issue.allowed
    listable = catalog_setting_choices()
    assert {"setting:" + name for name in issue.allowed} <= listable


def test_a_gpu_host_that_ran_the_cpu_build_says_so_in_words():
    # R9-3: a Motor practice on a GPU pod ran the CPU build and only a
    # buried code said so.
    from carbon.development_session import catalog_gpu

    record = catalog_gpu.backend_record(None, None, "catalog_gpu_build_missing", None)
    assert record["kind"] == "C03_DOCKER"
    assert record["fallback"].startswith(
        "Ran on CPU: this catalog entry has no GPU build yet"
    )
    assert "fallback" not in catalog_gpu.backend_record(None, None, None, None)


def test_a_gpu_build_without_a_receipt_says_so_in_words():
    # Validator, R9-3 note: the build exists but is not offered yet.
    from carbon.backbone_catalog.served import GpuBuildNotOffered
    from carbon.development_session import catalog_gpu

    code = GpuBuildNotOffered.code
    record = catalog_gpu.backend_record(None, None, code, None)
    assert record["fallback"] == (
        "Ran on CPU: the entry's GPU build has no GPU receipt yet."
        " The score is the CPU build's."
    )
