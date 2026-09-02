#!/usr/bin/env python3
"""Fast standard-library regression tests for Development Hub validation."""

from __future__ import annotations

import copy
import json
import os
import subprocess
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import render_hub
import validate_hub

BASE_SHA = "b86daa5d8b0f8b3e86bb82c2661f405747a200df"
REPOSITORY_URL = "https://github.com/carbonphysicsai/Carbon"
REPO_ROOT = Path(__file__).resolve().parents[4]
HUB_DATA_PATH = REPO_ROOT / "docs/development/carbon_hub/data/hub_data_v2.json"
INITIAL_INTEGRATION_DECLARATION = (
    "HUB_UPDATE_REQUIRED: SYSTEM/DEVELOPMENT-HUB; added source data, change "
    "events, generated orientation outputs, agent maintenance requirements, PR "
    "declaration, CI drift/coverage checks, and optional publication workflow."
)


def delivery_body(
    base: str,
    head: str,
    tree: str,
    *,
    hub_declaration: str | None = None,
) -> str:
    hub_declaration = hub_declaration or (
        "HUB_IMPACT_NONE: Only the pull-request declaration changed; the "
        "repository tree and Development Hub orientation semantics remain unchanged."
    )
    return f"""## Delivery mode

DELIVERY_MODE: SINGLE_TICKET_PR
SEPARATE_CONTRACT_PR_REASON: NOT_APPLICABLE

## Exact candidate

BASE: {base}
FINAL_HEAD: {head}
FINAL_TREE: {tree}

## Canonical validation

CHANGE_SCOPE: RUNTIME_FULL
CANONICAL_LOCAL_VALIDATION: PENDING
MERGE_GATE: PENDING
CODEX_GPT_REVIEW_RECEIPT: PENDING
HUMAN_APPROVAL_REVIEW: PENDING
GPT_REVIEW_GATE: PENDING
UNRESOLVED_THREADS: PENDING
BLOCKING_DIRECTION: NONE

## Completion receipt

DYNAMIC_COMPLETION_EVIDENCE: EXTERNAL
COMPLETION_RECEIPT_LOCATION: PR completion comment after merge

## Development Hub impact

{hub_declaration}

## Throughput observations

CODE_BEARING_COMMITS: 1
POST_FREEZE_TREE_CHANGES: 0
FULL_CI_RUNS: 1
AVOIDABLE_RERUN_REASON: No avoidable rerun was required.
"""


class DiffValidator(validate_hub.Validator):
    """Deterministic Git seam proving deletion filters and capture."""

    def __init__(self) -> None:
        super().__init__(Path("."))
        self.commands: list[tuple[str, ...]] = []

    def git(
        self, *args: str, allow_failure: bool = False
    ) -> subprocess.CompletedProcess[str]:
        del allow_failure
        self.commands.append(args)
        if args[:2] == ("rev-parse", "--verify"):
            return subprocess.CompletedProcess(args, 0, BASE_SHA + "\n", "")
        if args and args[0] == "diff":
            output = (
                ".agent/evidence/wave_b/removed.md\0"
                if "--diff-filter=D" in args
                else ""
            )
            return subprocess.CompletedProcess(args, 0, output, "")
        if args and args[0] == "ls-files":
            return subprocess.CompletedProcess(args, 0, "", "")
        if args and args[0] == "show":
            return subprocess.CompletedProcess(args, 128, "", "missing in base")
        raise AssertionError(f"Unexpected Git command: {args}")


class PushDiffValidator(validate_hub.Validator):
    """Git seam for a Hub-neutral direct-push comparison."""

    def __init__(self) -> None:
        super().__init__(Path("."))

    def git(
        self, *args: str, allow_failure: bool = False
    ) -> subprocess.CompletedProcess[str]:
        del allow_failure
        if args[:2] == ("rev-parse", "--verify"):
            return subprocess.CompletedProcess(args, 0, BASE_SHA + "\n", "")
        if args and args[0] == "diff":
            output = "carbon/runtime.py\0" if "...HEAD" in " ".join(args) else ""
            return subprocess.CompletedProcess(args, 0, output, "")
        if args and args[0] == "ls-files":
            return subprocess.CompletedProcess(args, 0, "", "")
        if args and args[0] == "show":
            target = args[1]
            if target.endswith("data/change_events.json"):
                return subprocess.CompletedProcess(args, 0, '{"events": []}', "")
            if target.endswith("data/hub_data_v2.json"):
                return subprocess.CompletedProcess(args, 0, json.dumps(self.data), "")
        raise AssertionError(f"Unexpected Git command: {args}")


class ValidatorContractTests(unittest.TestCase):
    @staticmethod
    def load_hub_data() -> dict[str, object]:
        return json.loads(HUB_DATA_PATH.read_text(encoding="utf-8"))

    def test_collect_diff_includes_and_captures_deletions(self) -> None:
        validator = DiffValidator()
        validator.data = {}
        with patch.dict(os.environ, {"HUB_DIFF_BASE_SHA": BASE_SHA}, clear=False):
            validator.collect_diff()
        self.assertIn(".agent/evidence/wave_b/removed.md", validator.deleted_paths)
        self.assertIn(".agent/evidence/wave_b/removed.md", validator.changed_paths)
        self.assertTrue(
            any("--diff-filter=ACDMRTUXB" in command for command in validator.commands)
        )
        self.assertTrue(
            any("--diff-filter=D" in command for command in validator.commands)
        )
        diff_commands = [
            command for command in validator.commands if command[0] == "diff"
        ]
        self.assertEqual(len(diff_commands), 6)
        self.assertTrue(
            all("--no-renames" in command for command in diff_commands),
            diff_commands,
        )

    def test_explicit_authority_files_are_structural(self) -> None:
        validator = validate_hub.Validator(Path("."))
        validator.data = self.load_hub_data()
        expected = {
            ".agent/INVARIANTS.md": "SYSTEM/GOVERNANCE",
            ".agent/CODE_AUTHORITY.toml": "SYSTEM/AGENT-EXECUTION",
            "docs/context/SCIENTIFIC_REFERENCE_CANON_V4_MASTER.md": "SYSTEM/SCIENTIFIC-CANON",
            "docs/context/IMPLEMENTED_VS_SPECIFIED_CURRENT.md": "SYSTEM/MATURITY",
        }
        self.assertEqual(
            {path: validator.impact_ref(path) for path in expected}, expected
        )
        self.assertTrue(
            all(
                validator.classify_impact(path)["impact_class"] == "map_structural"
                for path in expected
            )
        )

    def test_wave_dependency_graph_preserves_post_d_parallel_lanes(self) -> None:
        data = self.load_hub_data()
        actual = {
            str(wave["id"]): (wave["predecessor"], wave["successor"])
            for wave in data["waves"]
        }
        self.assertEqual(actual, validate_hub.EXPECTED_WAVE_LINKS)

    def test_legacy_linear_post_d_wave_graph_is_rejected(self) -> None:
        validator = validate_hub.Validator(REPO_ROOT)
        validator.data = self.load_hub_data()
        validator.events = json.loads(
            (
                REPO_ROOT / "docs/development/carbon_hub/data/change_events.json"
            ).read_text(encoding="utf-8")
        )["events"]
        wave_d = next(wave for wave in validator.data["waves"] if wave["id"] == "D")
        wave_d["successor"] = "E"
        validator.validate_model()
        self.assertTrue(
            any(
                "waves[3].successor must be 'H'" in error for error in validator.errors
            ),
            validator.errors,
        )

    def test_vague_pr_declaration_is_rejected(self) -> None:
        validator = validate_hub.Validator(Path("."))
        validator.github_event = {"pull_request": {"body": "HUB_UPDATE_REQUIRED: done"}}
        validator.changed_paths = set()
        validator.validate_pr_declaration()
        self.assertTrue(any("specific" in error for error in validator.errors))

    def test_specific_semantic_pr_declaration_is_accepted(self) -> None:
        validator = validate_hub.Validator(Path("."))
        validator.events = [{"event_id": "HUB-ADJ-001"}]
        validator.github_event = {
            "pull_request": {
                "body": (
                    "HUB_UPDATE_REQUIRED: SYSTEM/DEVELOPMENT-HUB; "
                    "data/hub_data_v2.json and data/change_events.json; "
                    "event HUB-ADJ-001"
                )
            }
        }
        validator.changed_paths = {
            "docs/development/carbon_hub/data/hub_data_v2.json",
            "docs/development/carbon_hub/data/change_events.json",
        }
        validator.semantic_data_changed = True
        validator.new_event_ids = {"HUB-ADJ-001"}
        validator.validate_pr_declaration()
        self.assertEqual(validator.errors, [])

    def test_exact_initial_integration_declaration_is_accepted(self) -> None:
        validator = validate_hub.Validator(Path("."))
        validator.github_event = {
            "pull_request": {"body": INITIAL_INTEGRATION_DECLARATION}
        }
        validator.data = {"current": {"wave": "B"}}
        validator.base_hub_data = None
        validator.semantic_data_changed = True
        validator.changed_paths = {
            ".github/workflows/development-hub.yml",
            "docs/development/carbon_hub/data/hub_data_v2.json",
            "docs/development/carbon_hub/data/change_events.json",
        }
        validator.validate_pr_declaration()
        self.assertEqual(validator.errors, [])

    def test_live_body_edit_supersedes_old_event_without_commit_or_tree_change(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            self.init_git_fixture(root)
            tracked = root / "tracked.txt"
            tracked.write_text("base\n", encoding="utf-8")
            self.run_git(root, "add", "tracked.txt")
            self.run_git(root, "commit", "-m", "base")
            base = self.run_git(root, "rev-parse", "HEAD")
            tracked.write_text("candidate\n", encoding="utf-8")
            self.run_git(root, "add", "tracked.txt")
            self.run_git(root, "commit", "-m", "candidate")
            head = self.run_git(root, "rev-parse", "HEAD")
            tree = self.run_git(root, "rev-parse", "HEAD^{tree}")
            commit_count = self.run_git(root, "rev-list", "--count", "HEAD")

            event_path = root / "event.json"
            live_path = root / "live.json"
            event_path.write_text(
                json.dumps(
                    {
                        "number": 72,
                        "pull_request": {
                            "number": 72,
                            "body": "HUB_IMPACT_NONE: done",
                            "head": {"sha": head},
                            "base": {"sha": head},
                        },
                    }
                ),
                encoding="utf-8",
            )
            current_body = delivery_body(base, head, tree)
            live_path.write_text(
                json.dumps(
                    {
                        "number": 72,
                        "body": current_body,
                        "head": {"sha": head},
                        "base": {"sha": base},
                    }
                ),
                encoding="utf-8",
            )

            validator = validate_hub.Validator(root)
            validator.data = {}
            validator.events = []
            validator.changed_paths = {"tracked.txt"}
            with patch.dict(
                os.environ,
                {
                    "GITHUB_ACTIONS": "false",
                    "GITHUB_EVENT_PATH": str(event_path),
                    "HUB_LIVE_PR_PATH": str(live_path),
                    "HUB_REQUIRE_LIVE_PR": "true",
                    "HUB_DIFF_BASE_SHA": head,
                },
                clear=False,
            ):
                validator.load_github_event()
                validator.collect_diff()
            validator.validate_delivery_declaration()
            validator.validate_pr_declaration()

            self.assertTrue(validator.live_pr_loaded)
            self.assertEqual(
                validator.historical_github_event["pull_request"]["body"],
                "HUB_IMPACT_NONE: done",
            )
            self.assertEqual(
                validator.github_event["pull_request"]["body"], current_body
            )
            self.assertEqual(validator.diff_base_sha, base)
            self.assertEqual(self.run_git(root, "rev-parse", "HEAD"), head)
            self.assertEqual(self.run_git(root, "rev-parse", "HEAD^{tree}"), tree)
            self.assertEqual(
                self.run_git(root, "rev-list", "--count", "HEAD"), commit_count
            )
            self.assertEqual(validator.errors, [])

    def test_stale_live_declaration_fails_even_when_event_body_was_corrected(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            self.init_git_fixture(root)
            (root / "tracked.txt").write_text("candidate\n", encoding="utf-8")
            self.run_git(root, "add", "tracked.txt")
            self.run_git(root, "commit", "-m", "candidate")
            head = self.run_git(root, "rev-parse", "HEAD")
            tree = self.run_git(root, "rev-parse", "HEAD^{tree}")
            corrected = delivery_body(head, head, tree)
            stale = delivery_body(
                head,
                head,
                tree,
                hub_declaration="HUB_IMPACT_NONE: done",
            )
            event_path = root / "event.json"
            live_path = root / "live.json"
            event_path.write_text(
                json.dumps(
                    {
                        "number": 72,
                        "pull_request": {
                            "number": 72,
                            "body": corrected,
                            "head": {"sha": head},
                            "base": {"sha": head},
                        },
                    }
                ),
                encoding="utf-8",
            )
            live_path.write_text(
                json.dumps(
                    {
                        "number": 72,
                        "body": stale,
                        "head": {"sha": head},
                        "base": {"sha": head},
                    }
                ),
                encoding="utf-8",
            )
            validator = validate_hub.Validator(root)
            validator.changed_paths = {"tracked.txt"}
            with patch.dict(
                os.environ,
                {
                    "GITHUB_ACTIONS": "false",
                    "GITHUB_EVENT_PATH": str(event_path),
                    "HUB_LIVE_PR_PATH": str(live_path),
                    "HUB_REQUIRE_LIVE_PR": "true",
                },
                clear=False,
            ):
                validator.load_github_event()
            validator.validate_delivery_declaration()
            validator.validate_pr_declaration()
            self.assertTrue(
                any("specific" in error for error in validator.errors),
                validator.errors,
            )

    def test_live_pr_validation_fails_closed_on_noncurrent_checkout(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            self.init_git_fixture(root)
            (root / "tracked.txt").write_text("candidate\n", encoding="utf-8")
            self.run_git(root, "add", "tracked.txt")
            self.run_git(root, "commit", "-m", "candidate")
            head = self.run_git(root, "rev-parse", "HEAD")
            tree = self.run_git(root, "rev-parse", "HEAD^{tree}")
            different_head = "0" * 40
            event_path = root / "event.json"
            live_path = root / "live.json"
            event_path.write_text(
                json.dumps(
                    {
                        "number": 72,
                        "pull_request": {
                            "number": 72,
                            "head": {"sha": different_head},
                        },
                    }
                ),
                encoding="utf-8",
            )
            live_path.write_text(
                json.dumps(
                    {
                        "number": 72,
                        "body": delivery_body(head, head, tree),
                        "head": {"sha": different_head},
                        "base": {"sha": head},
                    }
                ),
                encoding="utf-8",
            )
            validator = validate_hub.Validator(root)
            with patch.dict(
                os.environ,
                {
                    "GITHUB_ACTIONS": "false",
                    "GITHUB_EVENT_PATH": str(event_path),
                    "HUB_LIVE_PR_PATH": str(live_path),
                    "HUB_REQUIRE_LIVE_PR": "true",
                },
                clear=False,
            ):
                validator.load_github_event()
            self.assertTrue(
                any(
                    "does not equal the current live pull request head" in error
                    for error in validator.errors
                ),
                validator.errors,
            )

    def test_historical_event_head_cannot_validate_a_newer_live_head(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            self.init_git_fixture(root)
            tracked = root / "tracked.txt"
            tracked.write_text("event head\n", encoding="utf-8")
            self.run_git(root, "add", "tracked.txt")
            self.run_git(root, "commit", "-m", "event head")
            event_head = self.run_git(root, "rev-parse", "HEAD")
            tracked.write_text("live head\n", encoding="utf-8")
            self.run_git(root, "commit", "-am", "live head")
            live_head = self.run_git(root, "rev-parse", "HEAD")
            tree = self.run_git(root, "rev-parse", "HEAD^{tree}")
            event_path = root / "event.json"
            live_path = root / "live.json"
            event_path.write_text(
                json.dumps(
                    {
                        "number": 72,
                        "pull_request": {
                            "number": 72,
                            "head": {"sha": event_head},
                        },
                    }
                ),
                encoding="utf-8",
            )
            live_path.write_text(
                json.dumps(
                    {
                        "number": 72,
                        "body": delivery_body(event_head, live_head, tree),
                        "head": {"sha": live_head},
                        "base": {"sha": event_head},
                    }
                ),
                encoding="utf-8",
            )
            validator = validate_hub.Validator(root)
            with patch.dict(
                os.environ,
                {
                    "GITHUB_EVENT_PATH": str(event_path),
                    "HUB_LIVE_PR_PATH": str(live_path),
                    "HUB_REQUIRE_LIVE_PR": "true",
                },
                clear=True,
            ):
                validator.load_github_event()
            self.assertFalse(validator.live_pr_loaded)
            self.assertTrue(
                any(
                    "Workflow event head does not equal" in error
                    for error in validator.errors
                ),
                validator.errors,
            )

    def test_required_live_pr_rejects_missing_event_path(self) -> None:
        validator = validate_hub.Validator(REPO_ROOT)
        with patch.dict(
            os.environ,
            {
                "GITHUB_ACTIONS": "true",
                "GITHUB_EVENT_NAME": "pull_request",
            },
            clear=True,
        ):
            validator.load_github_event()
        self.assertTrue(
            any("requires GITHUB_EVENT_PATH" in error for error in validator.errors),
            validator.errors,
        )

    def test_required_live_pr_rejects_malformed_or_non_pr_event(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            malformed = root / "malformed.json"
            malformed.write_text("{", encoding="utf-8")
            non_pr = root / "non-pr.json"
            non_pr.write_text(json.dumps({"number": 72}), encoding="utf-8")
            for event_path, expected in (
                (malformed, "not readable JSON"),
                (non_pr, "requires a pull_request object"),
            ):
                with self.subTest(event_path=event_path.name):
                    validator = validate_hub.Validator(REPO_ROOT)
                    with patch.dict(
                        os.environ,
                        {
                            "GITHUB_EVENT_PATH": str(event_path),
                            "HUB_REQUIRE_LIVE_PR": "true",
                        },
                        clear=True,
                    ):
                        validator.load_github_event()
                    self.assertTrue(
                        any(expected in error for error in validator.errors),
                        validator.errors,
                    )

    def test_live_override_cannot_supply_missing_event_pr_identity(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            event_path = root / "event.json"
            live_path = root / "live.json"
            event_path.write_text(
                json.dumps({"pull_request": {"number": "72"}}),
                encoding="utf-8",
            )
            live_path.write_text(
                json.dumps({"number": 72}),
                encoding="utf-8",
            )
            validator = validate_hub.Validator(REPO_ROOT)
            with patch.dict(
                os.environ,
                {
                    "GITHUB_EVENT_PATH": str(event_path),
                    "HUB_LIVE_PR_PATH": str(live_path),
                    "HUB_REQUIRE_LIVE_PR": "true",
                },
                clear=True,
            ):
                validator.load_github_event()
            self.assertFalse(validator.live_pr_loaded)
            self.assertTrue(
                any(
                    "exact positive numeric pull request identity" in error
                    for error in validator.errors
                ),
                validator.errors,
            )

    def test_live_declaration_edit_cannot_substitute_for_required_hub_change(
        self,
    ) -> None:
        validator = validate_hub.Validator(REPO_ROOT)
        validator.data = self.load_hub_data()
        validator.github_event = {
            "pull_request": {
                "body": (
                    "HUB_UPDATE_REQUIRED: WAVE-B; data/hub_data_v2.json and "
                    "data/change_events.json"
                )
            }
        }
        validator.changed_paths = {".agent/WAVE.md"}
        validator.semantic_data_changed = False
        validator.validate_structural_diff()
        validator.validate_pr_declaration()
        self.assertTrue(
            any(
                "require an updated data/hub_data_v2.json" in error
                or "require a semantic Hub-data delta" in error
                for error in validator.errors
            ),
            validator.errors,
        )

    def test_delivery_candidate_fields_must_match_live_base_head_and_tree(
        self,
    ) -> None:
        head = self.run_git(REPO_ROOT, "rev-parse", "HEAD")
        tree = self.run_git(REPO_ROOT, "rev-parse", "HEAD^{tree}")
        stale = "0" * 40
        validator = validate_hub.Validator(REPO_ROOT)
        validator.github_event = {
            "pull_request": {
                "body": delivery_body(stale, stale, stale),
                "head": {"sha": head},
                "base": {"sha": head},
            }
        }
        validator.validate_delivery_declaration()
        self.assertTrue(
            any("BASE does not match" in error for error in validator.errors),
            validator.errors,
        )
        self.assertTrue(
            any("FINAL_HEAD does not match" in error for error in validator.errors),
            validator.errors,
        )
        self.assertTrue(
            any(
                "FINAL_TREE does not match" in error and tree in error
                for error in validator.errors
            ),
            validator.errors,
        )

    def test_separate_contract_delivery_mode_accepts_all_closed_reasons(self) -> None:
        head = self.run_git(REPO_ROOT, "rev-parse", "HEAD")
        tree = self.run_git(REPO_ROOT, "rev-parse", "HEAD^{tree}")
        reasons = (
            "CONTRACT_ONLY_TICKET",
            "CONCURRENT_DOWNSTREAM_IMMUTABLE_CONTRACT",
            "CROSS_DOMAIN_PUBLIC_INTERFACE_FREEZE",
        )
        for reason in reasons:
            with self.subTest(reason=reason):
                body = delivery_body(head, head, tree).replace(
                    "DELIVERY_MODE: SINGLE_TICKET_PR\n"
                    "SEPARATE_CONTRACT_PR_REASON: NOT_APPLICABLE",
                    "DELIVERY_MODE: SEPARATE_CONTRACT_PR\n"
                    f"SEPARATE_CONTRACT_PR_REASON: {reason}",
                )
                validator = validate_hub.Validator(REPO_ROOT)
                validator.data = self.load_hub_data()
                validator.github_event = {
                    "pull_request": {
                        "body": body,
                        "head": {"sha": head},
                        "base": {"sha": head},
                    }
                }
                validator.validate_delivery_declaration()
                self.assertEqual(validator.errors, [])

    def test_authoritative_sequencing_accepts_tracked_explicit_marker(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            self.init_git_fixture(root)
            authority = root / ".agent/WAVE.md"
            authority.parent.mkdir(parents=True)
            authority.write_text(
                "# Fixture current wave\r\n\r\n"
                "SEPARATE_CONTRACT_PR_EXCEPTION: Concurrent downstream consumers "
                "require the immutable contract first.\r\n",
                encoding="utf-8",
            )
            self.run_git(root, "add", ".agent/WAVE.md")
            self.run_git(root, "commit", "-m", "record sequencing exception")
            head = self.run_git(root, "rev-parse", "HEAD")
            tree = self.run_git(root, "rev-parse", "HEAD^{tree}")
            reason = (
                "AUTHORITATIVE_SEQUENCING | AUTHORITY: .agent/WAVE.md | DETAILS: "
                "concurrent  downstream consumers require the immutable contract first."
            )
            body = delivery_body(head, head, tree).replace(
                "DELIVERY_MODE: SINGLE_TICKET_PR\n"
                "SEPARATE_CONTRACT_PR_REASON: NOT_APPLICABLE",
                "DELIVERY_MODE: SEPARATE_CONTRACT_PR\n"
                f"SEPARATE_CONTRACT_PR_REASON: {reason}",
            )
            validator = validate_hub.Validator(root)
            validator.github_event = {
                "pull_request": {
                    "body": body,
                    "head": {"sha": head},
                    "base": {"sha": head},
                }
            }
            validator.validate_delivery_declaration()
            self.assertEqual(validator.errors, [])

            incomplete = validate_hub.Validator(root)
            incomplete.validate_separate_contract_reason(
                "AUTHORITATIVE_SEQUENCING | AUTHORITY: .agent/WAVE.md | DETAILS: "
                "Concurrent downstream consumers require the immutable contract"
            )
            self.assertTrue(
                any("normalize-equal" in error for error in incomplete.errors),
                incomplete.errors,
            )

            authority.write_text(
                "# Fixture current wave\n\n"
                "SEPARATE_CONTRACT_PR_EXCEPTION: Concurrent **downstream** "
                "consumers require the immutable contract first.\n",
                encoding="utf-8",
            )
            self.run_git(root, "add", ".agent/WAVE.md")
            self.run_git(root, "commit", "-m", "record invalid marked-up exception")
            marked_up_marker = validate_hub.Validator(root)
            marked_up_marker.validate_separate_contract_reason(
                "AUTHORITATIVE_SEQUENCING | AUTHORITY: .agent/WAVE.md | DETAILS: "
                "Concurrent downstream consumers require the immutable contract first."
            )
            self.assertTrue(
                any(
                    "marker values must be plain prose" in error
                    for error in marked_up_marker.errors
                ),
                marked_up_marker.errors,
            )

    def test_separate_contract_rejects_arbitrary_and_ticket_size_reasons(
        self,
    ) -> None:
        head = self.run_git(REPO_ROOT, "rev-parse", "HEAD")
        tree = self.run_git(REPO_ROOT, "rev-parse", "HEAD^{tree}")
        cases = (
            ("Any arbitrary reason with enough words", "must be CONTRACT_ONLY_TICKET"),
            ("This ticket is too large for one pull request", "ticket size"),
            ("Ticket-size makes this pull request separate", "ticket size"),
            ("Ticket_size makes this pull request separate", "ticket size"),
            ("Ticket–size makes this pull request separate", "ticket size"),
            ("Ticket‑size makes this pull request separate", "ticket size"),
            ("The ticket's size requires another pull request", "ticket size"),
            ("An oversized ticket requires another pull request", "ticket size"),
            ("The ticket **size** requires another pull request", "ticket size"),
            ("The ticket `size` requires another pull request", "ticket size"),
            ("A large **ticket** requires another pull request", "ticket size"),
            ("Ticket&nbsp;size requires another pull request", "ticket size"),
            ("Ticket&#x2011;size requires another pull request", "ticket size"),
            (
                (
                    "AUTHORITATIVE_SEQUENCING | AUTHORITY: .agent/WAVE_B.md | "
                    "DETAILS: ticket size alone is not one."
                ),
                "ticket size",
            ),
        )
        for reason, expected in cases:
            with self.subTest(reason=reason):
                body = delivery_body(head, head, tree).replace(
                    "DELIVERY_MODE: SINGLE_TICKET_PR\n"
                    "SEPARATE_CONTRACT_PR_REASON: NOT_APPLICABLE",
                    "DELIVERY_MODE: SEPARATE_CONTRACT_PR\n"
                    f"SEPARATE_CONTRACT_PR_REASON: {reason}",
                )
                validator = validate_hub.Validator(REPO_ROOT)
                validator.data = self.load_hub_data()
                validator.github_event = {
                    "pull_request": {
                        "body": body,
                        "head": {"sha": head},
                        "base": {"sha": head},
                    }
                }
                validator.validate_delivery_declaration()
                self.assertTrue(
                    any(expected in error for error in validator.errors),
                    validator.errors,
                )

    def test_authoritative_sequencing_reason_fails_closed(self) -> None:
        cases = (
            (
                (
                    "AUTHORITATIVE_SEQUENCING | AUTHORITY: .agent/./WAVE.md | "
                    "DETAILS: runtime work waits for the recorded delivery gate"
                ),
                "normalized repository-relative path",
            ),
            (
                (
                    "AUTHORITATIVE_SEQUENCING | AUTHORITY: .agent/WAVE.md | "
                    "DETAILS: This arbitrary exception is never recorded."
                ),
                "normalize-equal",
            ),
            (
                (
                    "AUTHORITATIVE_SEQUENCING | AUTHORITY: .agent/WAVE.md | "
                    "DETAILS: Current wave"
                ),
                "at least four words",
            ),
        )
        for reason, expected in cases:
            with self.subTest(reason=reason):
                validator = validate_hub.Validator(REPO_ROOT)
                validator.data = self.load_hub_data()
                validator.validate_separate_contract_reason(reason)
                self.assertTrue(
                    any(expected in error for error in validator.errors),
                    validator.errors,
                )

        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            self.init_git_fixture(root)
            tracked = root / "tracked.txt"
            tracked.write_text("fixture\n", encoding="utf-8")
            self.run_git(root, "add", "tracked.txt")
            self.run_git(root, "commit", "-m", "fixture")
            authority = root / "Design_Specs/Build_Out.md"
            authority.parent.mkdir(parents=True)
            authority.write_text(
                "A separate immutable contract is required before implementation.\n",
                encoding="utf-8",
            )
            validator = validate_hub.Validator(root)
            validator.validate_separate_contract_reason(
                "AUTHORITATIVE_SEQUENCING | AUTHORITY: "
                "Design_Specs/Build_Out.md | DETAILS: A separate immutable "
                "contract is required before implementation."
            )
            self.assertTrue(
                any("must name a tracked" in error for error in validator.errors),
                validator.errors,
            )

            authority.write_text("Baseline sequencing authority.\n", encoding="utf-8")
            self.run_git(root, "add", "Design_Specs/Build_Out.md")
            self.run_git(root, "commit", "-m", "track sequencing authority")
            authority.write_text(
                "Baseline sequencing authority.\n"
                "SEPARATE_CONTRACT_PR_EXCEPTION: A separate immutable contract "
                "is required before implementation.\n",
                encoding="utf-8",
            )
            worktree_only = validate_hub.Validator(root)
            worktree_only.validate_separate_contract_reason(
                "AUTHORITATIVE_SEQUENCING | AUTHORITY: "
                "Design_Specs/Build_Out.md | DETAILS: A separate immutable "
                "contract is required before implementation."
            )
            self.assertTrue(
                any("normalize-equal" in error for error in worktree_only.errors),
                worktree_only.errors,
            )

    def test_authoritative_sequencing_rejects_markup_metacharacters(self) -> None:
        values = (
            "The <runtime> contract requires separate sequencing.",
            "The runtime > contract requires separate sequencing.",
            "The runtime & contract requires separate sequencing.",
            "The *runtime* contract requires separate sequencing.",
            "The `runtime` contract requires separate sequencing.",
            "The runtime_contract requires separate sequencing.",
            "Ticket <em>size</em> requires another pull request.",
        )
        for details in values:
            with self.subTest(details=details):
                validator = validate_hub.Validator(REPO_ROOT)
                validator.data = self.load_hub_data()
                validator.validate_separate_contract_reason(
                    "AUTHORITATIVE_SEQUENCING | AUTHORITY: .agent/WAVE.md | "
                    f"DETAILS: {details}"
                )
                self.assertTrue(
                    any("plain prose" in error for error in validator.errors),
                    validator.errors,
                )

    def test_single_ticket_rejects_separate_contract_reason_code(self) -> None:
        head = self.run_git(REPO_ROOT, "rev-parse", "HEAD")
        tree = self.run_git(REPO_ROOT, "rev-parse", "HEAD^{tree}")
        body = delivery_body(head, head, tree).replace(
            "SEPARATE_CONTRACT_PR_REASON: NOT_APPLICABLE",
            "SEPARATE_CONTRACT_PR_REASON: CONTRACT_ONLY_TICKET",
        )
        validator = validate_hub.Validator(REPO_ROOT)
        validator.github_event = {
            "pull_request": {
                "body": body,
                "head": {"sha": head},
                "base": {"sha": head},
            }
        }
        validator.validate_delivery_declaration()
        self.assertTrue(
            any(
                "requires SEPARATE_CONTRACT_PR_REASON" in error
                for error in validator.errors
            ),
            validator.errors,
        )

    def test_throughput_counts_and_rerun_reason_are_machine_validated(self) -> None:
        head = self.run_git(REPO_ROOT, "rev-parse", "HEAD")
        tree = self.run_git(REPO_ROOT, "rev-parse", "HEAD^{tree}")
        body = delivery_body(head, head, tree)
        body = body.replace("CODE_BEARING_COMMITS: 1", "CODE_BEARING_COMMITS: -1")
        body = body.replace(
            "POST_FREEZE_TREE_CHANGES: 0", "POST_FREEZE_TREE_CHANGES: one"
        )
        body = body.replace("FULL_CI_RUNS: 1", "FULL_CI_RUNS: 1.5")
        body = body.replace(
            "AVOIDABLE_RERUN_REASON: No avoidable rerun was required.",
            "AVOIDABLE_RERUN_REASON: NONE",
        )
        validator = validate_hub.Validator(REPO_ROOT)
        validator.github_event = {
            "pull_request": {
                "body": body,
                "head": {"sha": head},
                "base": {"sha": head},
            }
        }
        validator.validate_delivery_declaration()
        for field in (
            "CODE_BEARING_COMMITS",
            "POST_FREEZE_TREE_CHANGES",
            "FULL_CI_RUNS",
            "AVOIDABLE_RERUN_REASON",
        ):
            self.assertTrue(
                any(field in error for error in validator.errors),
                (field, validator.errors),
            )

        pending_body = delivery_body(head, head, tree)
        for field, value in (
            ("CODE_BEARING_COMMITS", "1"),
            ("POST_FREEZE_TREE_CHANGES", "0"),
            ("FULL_CI_RUNS", "1"),
        ):
            pending_body = pending_body.replace(
                f"{field}: {value}", f"{field}: PENDING"
            )
        pending = validate_hub.Validator(REPO_ROOT)
        pending.github_event = {
            "pull_request": {
                "body": pending_body,
                "head": {"sha": head},
                "base": {"sha": head},
            }
        }
        pending.validate_delivery_declaration()
        self.assertEqual(pending.errors, [])

    def test_completion_receipt_accepts_a_concrete_github_pr_comment_url(self) -> None:
        head = self.run_git(REPO_ROOT, "rev-parse", "HEAD")
        tree = self.run_git(REPO_ROOT, "rev-parse", "HEAD^{tree}")
        body = delivery_body(head, head, tree).replace(
            "COMPLETION_RECEIPT_LOCATION: PR completion comment after merge",
            "COMPLETION_RECEIPT_LOCATION: "
            "https://github.com/carbonphysicsai/Carbon/pull/73#issuecomment-1234",
        )
        validator = validate_hub.Validator(REPO_ROOT)
        validator.github_event = {
            "pull_request": {
                "body": body,
                "head": {"sha": head},
                "base": {"sha": head},
            }
        }
        validator.validate_delivery_declaration()
        self.assertEqual(validator.errors, [])

    def test_delivery_fields_cannot_borrow_the_following_line_as_a_value(self) -> None:
        head = self.run_git(REPO_ROOT, "rev-parse", "HEAD")
        tree = self.run_git(REPO_ROOT, "rev-parse", "HEAD^{tree}")
        values = {
            "CANONICAL_LOCAL_VALIDATION": "PENDING",
            "MERGE_GATE": "PENDING",
            "CODEX_GPT_REVIEW_RECEIPT": "PENDING",
            "HUMAN_APPROVAL_REVIEW": "PENDING",
            "GPT_REVIEW_GATE": "PENDING",
            "BLOCKING_DIRECTION": "NONE",
            "COMPLETION_RECEIPT_LOCATION": "PR completion comment after merge",
        }
        for field, value in values.items():
            with self.subTest(field=field):
                body = delivery_body(head, head, tree).replace(
                    f"{field}: {value}", f"{field}:"
                )
                validator = validate_hub.Validator(REPO_ROOT)
                validator.github_event = {
                    "pull_request": {
                        "body": body,
                        "head": {"sha": head},
                        "base": {"sha": head},
                    }
                }
                validator.validate_delivery_declaration()
                self.assertTrue(
                    any(field in error for error in validator.errors),
                    (field, validator.errors),
                )

    def test_delivery_fields_accept_crlf_without_crossing_line_boundaries(self) -> None:
        head = self.run_git(REPO_ROOT, "rev-parse", "HEAD")
        tree = self.run_git(REPO_ROOT, "rev-parse", "HEAD^{tree}")
        validator = validate_hub.Validator(REPO_ROOT)
        validator.github_event = {
            "pull_request": {
                "body": delivery_body(head, head, tree).replace("\n", "\r\n"),
                "head": {"sha": head},
                "base": {"sha": head},
            }
        }
        validator.validate_delivery_declaration()
        self.assertEqual(validator.errors, [])

    def test_delivery_status_fields_use_closed_leading_enums(self) -> None:
        head = self.run_git(REPO_ROOT, "rev-parse", "HEAD")
        tree = self.run_git(REPO_ROOT, "rev-parse", "HEAD^{tree}")
        replacements = {
            "CANONICAL_LOCAL_VALIDATION: PENDING": (
                "CANONICAL_LOCAL_VALIDATION: MAYBE"
            ),
            "MERGE_GATE: PENDING": "MERGE_GATE: GREEN",
            "CODEX_GPT_REVIEW_RECEIPT: PENDING": ("CODEX_GPT_REVIEW_RECEIPT: IGNORED"),
            "HUMAN_APPROVAL_REVIEW: PENDING": "HUMAN_APPROVAL_REVIEW: IGNORED",
            "GPT_REVIEW_GATE: PENDING": "GPT_REVIEW_GATE: IGNORED",
            "BLOCKING_DIRECTION: NONE": "BLOCKING_DIRECTION: SILENCE_MEANS_PASS",
        }
        body = delivery_body(head, head, tree)
        for before, after in replacements.items():
            body = body.replace(before, after)
        validator = validate_hub.Validator(REPO_ROOT)
        validator.github_event = {
            "pull_request": {
                "body": body,
                "head": {"sha": head},
                "base": {"sha": head},
            }
        }
        validator.validate_delivery_declaration()
        for field in (
            "CANONICAL_LOCAL_VALIDATION",
            "MERGE_GATE",
            "CODEX_GPT_REVIEW_RECEIPT",
            "HUMAN_APPROVAL_REVIEW",
            "GPT_REVIEW_GATE",
            "BLOCKING_DIRECTION",
        ):
            self.assertTrue(
                any(field in error for error in validator.errors),
                (field, validator.errors),
            )

    def test_delivery_change_scope_matches_fail_closed_preflight_scope(self) -> None:
        head = self.run_git(REPO_ROOT, "rev-parse", "HEAD")
        tree = self.run_git(REPO_ROOT, "rev-parse", "HEAD^{tree}")
        body = delivery_body(head, head, tree)

        matching = validate_hub.Validator(REPO_ROOT)
        matching.github_event = {
            "pull_request": {
                "body": body,
                "head": {"sha": head},
                "base": {"sha": head},
            }
        }
        with patch.dict(
            os.environ, {"HUB_EXPECTED_CHANGE_SCOPE": "RUNTIME_FULL"}, clear=False
        ):
            matching.validate_delivery_declaration()
        self.assertEqual(matching.errors, [])

        for expected, error_fragment in (
            ("CONTRACT_AUTHORITY", "does not match"),
            ("", "must be one of"),
            ("UNKNOWN", "must be one of"),
        ):
            with self.subTest(expected=expected):
                rejected = validate_hub.Validator(REPO_ROOT)
                rejected.github_event = copy.deepcopy(matching.github_event)
                with patch.dict(
                    os.environ,
                    {"HUB_EXPECTED_CHANGE_SCOPE": expected},
                    clear=False,
                ):
                    rejected.validate_delivery_declaration()
                self.assertTrue(
                    any(error_fragment in error for error in rejected.errors),
                    rejected.errors,
                )

    def test_hub_workflow_has_explicit_live_pr_least_privilege_contract(
        self,
    ) -> None:
        workflow = (REPO_ROOT / ".github/workflows/development-hub.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            "types: [opened, synchronize, reopened, edited, ready_for_review]",
            workflow,
        )
        self.assertIn("contents: read", workflow)
        self.assertIn("pull-requests: read", workflow)
        self.assertNotRegex(workflow, r"(?m)^\s*[a-z-]+:\s*write\s*$")
        self.assertIn(
            'gh api --method GET "repos/${GITHUB_REPOSITORY}/pulls/${PR_NUMBER}"',
            workflow,
        )
        self.assertIn(
            "Historical event head {event_head} no longer equals live head",
            workflow,
        )
        self.assertIn(
            "Refreshed live head {live_head} no longer equals checked-out",
            workflow,
        )
        self.assertIn(
            "ref: ${{ steps.live_pr.outputs.head_sha || github.sha }}", workflow
        )
        self.assertIn("persist-credentials: false", workflow)
        self.assertIn(
            "group: development-hub-${{ github.event_name }}-"
            "${{ github.event.pull_request.number || github.sha }}",
            workflow,
        )
        self.assertIn(
            "cancel-in-progress: ${{ github.event_name == 'pull_request' }}",
            workflow,
        )
        self.assertIn("python3 scripts/dev/classify_changes.py", workflow)
        self.assertIn(
            "HUB_EXPECTED_CHANGE_SCOPE: ${{ steps.change_scope.outputs.change_scope }}",
            workflow,
        )
        self.assertIn(
            "HUB_REQUIRE_LIVE_PR: ${{ github.event_name == 'pull_request' }}",
            workflow,
        )

    def test_current_authority_links_require_exact_blob_or_dynamic_route(self) -> None:
        snapshot = "a" * 40
        valid_blob = f"{REPOSITORY_URL}/blob/{snapshot}/.agent/WAVE.md"
        accepted = validate_hub.Validator(REPO_ROOT)
        self.assertEqual(
            accepted.current_authority_target(valid_blob, snapshot, "fixture"),
            (snapshot, ".agent/WAVE.md"),
        )
        for route in (
            f"{REPOSITORY_URL}/issues/42",
            f"{REPOSITORY_URL}/pull/72",
        ):
            with self.subTest(route=route):
                self.assertIsNone(
                    accepted.current_authority_target(route, snapshot, "fixture")
                )
        self.assertEqual(accepted.errors, [])

        for unsafe in (
            REPOSITORY_URL,
            f"{REPOSITORY_URL}/tree/main/.agent/WAVE.md",
            f"{REPOSITORY_URL}/tree/{snapshot}/.agent/WAVE.md",
            f"{REPOSITORY_URL}/blob/{snapshot}/.agent/../WAVE.md",
            f"{REPOSITORY_URL}/blob/{snapshot}/.agent//WAVE.md",
            f"{REPOSITORY_URL}/blob/{snapshot}/.agent%2f..%2fWAVE.md",
            f"{valid_blob}?plain=1",
            f"{valid_blob}#L1",
            f"{REPOSITORY_URL}/issues/42?notification_referrer_id=1",
            f"{REPOSITORY_URL}/issues/42#issuecomment-1234",
            f"{REPOSITORY_URL}/pull/72?diff=split",
            f"{REPOSITORY_URL}/pull/72#discussion_r1",
            "https://[invalid",
        ):
            with self.subTest(unsafe=unsafe):
                rejected = validate_hub.Validator(REPO_ROOT)
                self.assertIsNone(
                    rejected.current_authority_target(
                        unsafe, snapshot, "fixture current authority"
                    )
                )
                self.assertTrue(rejected.errors)

    def test_hostile_quote_url_is_rejected(self) -> None:
        hostile_suffixes = (
            '" onclick="alert(1)',
            "' onclick='alert(1)",
            "%22",
            "%27",
            "%00",
            "%0A",
            "%7F",
            "%2522",
            "%250A",
            "%C2%80",
            "%E2%80%AE",
            "&quot;",
            "&#34;",
        )
        for suffix in hostile_suffixes:
            hostile_url = f"{REPOSITORY_URL}/{suffix}"
            with self.subTest(hostile_url=hostile_url):
                validator = validate_hub.Validator(Path("."))
                accepted = validator.validate_https_url(hostile_url, "fixture.url")
                self.assertFalse(accepted)
                self.assertTrue(
                    any("unsafe URL characters" in error for error in validator.errors)
                )

    def test_hostile_urls_reach_every_data_link_surface(self) -> None:
        hostile_url = f'{REPOSITORY_URL}/" onclick="alert(1)'
        surfaces = (
            "meta",
            "sources",
            "waves",
            "tickets",
            "change_paths",
        )
        for surface in surfaces:
            with self.subTest(surface=surface):
                data = {
                    "meta": {"repository": REPOSITORY_URL},
                    "sources": {"fixture": {"label": "Fixture", "url": REPOSITORY_URL}},
                    "waves": [
                        {"repo_links": [{"label": "Fixture", "url": REPOSITORY_URL}]}
                    ],
                    "tickets": [
                        {"repo_links": [{"label": "Fixture", "url": REPOSITORY_URL}]}
                    ],
                    "change_paths": [
                        {"repo_links": [{"label": "Fixture", "url": REPOSITORY_URL}]}
                    ],
                }
                if surface == "meta":
                    data["meta"]["repository"] = hostile_url
                elif surface == "sources":
                    data["sources"]["fixture"]["url"] = hostile_url
                else:
                    data[surface][0]["repo_links"][0]["url"] = hostile_url
                validator = validate_hub.Validator(Path("."))
                validator.data = data
                validator.validate_data_urls()
                self.assertTrue(
                    any("unsafe URL characters" in error for error in validator.errors)
                )

    def test_event_url_and_local_fragment_injection_are_rejected(self) -> None:
        details = (
            f'{REPOSITORY_URL}/" onclick="alert(1)',
            'docs/development/carbon_hub/index.html#" onclick="alert(1)',
            "docs/development/carbon_hub/index.html#&quot;onclick",
        )
        for detail in details:
            with self.subTest(detail=detail):
                validator = validate_hub.Validator(Path("."))
                validator.events = [
                    {
                        "map_ref": "SYSTEM/DEVELOPMENT-HUB",
                        "event_type": "bug",
                        "event_id": "HUB-TEST-001",
                        "owner_lane": "documentation_maintenance",
                        "status": "active",
                        "summary": "A meaningful synthetic validator regression event.",
                        "primary_detail": detail,
                        "affects": [],
                        "supersedes": None,
                    }
                ]
                validator.validate_events(set(), set())
                self.assertTrue(
                    any("unsafe" in error.lower() for error in validator.errors)
                )

    def test_meta_repository_must_be_exact(self) -> None:
        validator = validate_hub.Validator(Path("."))
        validator.data = {
            "meta": {"repository": f"{REPOSITORY_URL}/issues/42"},
            "sources": {},
            "waves": [],
            "tickets": [],
            "change_paths": [],
        }
        validator.validate_data_urls()
        self.assertTrue(any("exactly equal" in error for error in validator.errors))

    def test_malformed_url_container_shapes_fail_without_exception(self) -> None:
        validator = validate_hub.Validator(Path("."))
        validator.data = {
            "meta": [],
            "current": [],
            "sources": [],
            "authority_ceilings": {},
            "waves": [None],
            "tickets": [None],
            "maturity": [None],
            "change_paths": [None],
            "glossary": [],
            "event_schema": {},
        }
        validator.validate_model()
        self.assertTrue(validator.errors)

    def test_padded_vague_and_invented_pr_coverage_are_rejected(self) -> None:
        cases = (
            (
                "HUB_UPDATE_REQUIRED: SYSTEM/DEVELOPMENT-HUB updated as requested",
                "requested",
            ),
            (
                "HUB_UPDATE_REQUIRED: SYSTEM/GOVERNANCE/BOGUS updated with detailed static orientation context",
                "unknown map references",
            ),
            (
                "HUB_UPDATE_REQUIRED: docs/development/carbon_hub/does-not-exist.html updated with detailed static orientation content",
                "not changed",
            ),
        )
        for body, expected in cases:
            with self.subTest(body=body):
                validator = validate_hub.Validator(Path("."))
                validator.github_event = {"pull_request": {"body": body}}
                validator.data = {"current": {"wave": "B"}}
                validator.base_hub_data = {}
                validator.changed_paths = {"docs/development/carbon_hub/index.html"}
                validator.validate_pr_declaration()
                self.assertTrue(
                    any(expected in error for error in validator.errors),
                    validator.errors,
                )

    def test_historical_event_cannot_cover_semantic_pr_change(self) -> None:
        validator = validate_hub.Validator(Path("."))
        validator.events = [{"event_id": "HUB-OLD-001"}]
        validator.new_event_ids = {"HUB-NEW-001"}
        validator.github_event = {
            "pull_request": {
                "body": (
                    "HUB_UPDATE_REQUIRED: SYSTEM/DEVELOPMENT-HUB; updated "
                    "data/hub_data_v2.json and data/change_events.json; event "
                    "HUB-OLD-001 documents the semantic reconciliation"
                )
            }
        }
        validator.data = {"current": {"wave": "B"}}
        validator.base_hub_data = {}
        validator.semantic_data_changed = True
        validator.changed_paths = {
            "docs/development/carbon_hub/data/hub_data_v2.json",
            "docs/development/carbon_hub/data/change_events.json",
        }
        validator.validate_pr_declaration()
        self.assertTrue(
            any("newly appended" in error for error in validator.errors),
            validator.errors,
        )

    def test_semantic_hub_data_change_requires_new_event(self) -> None:
        validator = validate_hub.Validator(Path("."))
        validator.changed_paths = {"docs/development/carbon_hub/data/hub_data_v2.json"}
        validator.semantic_data_changed = True
        validator.new_event_ids = set()
        validator.validate_structural_diff()
        self.assertTrue(any("change event" in error for error in validator.errors))

    def test_structural_change_rejects_snapshot_pin_only_hub_delta(self) -> None:
        validator = validate_hub.Validator(REPO_ROOT)
        validator.data = self.load_hub_data()
        validator.changed_paths = {
            "CONSTITUTION.md",
            "docs/development/carbon_hub/data/hub_data_v2.json",
            "docs/development/carbon_hub/data/change_events.json",
        }
        validator.semantic_data_changed = False
        validator.events = [
            {
                "event_id": "HUB-TEST-PIN-ONLY",
                "map_ref": "SYSTEM/GOVERNANCE",
                "affects": [],
            }
        ]
        validator.new_event_ids = {"HUB-TEST-PIN-ONLY"}
        validator.validate_structural_diff()
        self.assertTrue(
            any("semantic Hub-data delta" in error for error in validator.errors),
            validator.errors,
        )

    def test_semantic_ticket_delta_requires_matching_new_event_coverage(self) -> None:
        base_data = self.load_hub_data()
        candidate_data = copy.deepcopy(base_data)
        b03 = next(item for item in candidate_data["tickets"] if item["id"] == "B-03")
        b03["current_stage"] = "A new bounded B-03 fixture stage."
        changed_paths = {
            "docs/development/carbon_hub/data/hub_data_v2.json",
            "docs/development/carbon_hub/data/change_events.json",
        }

        unrelated = validate_hub.Validator(REPO_ROOT)
        unrelated.data = candidate_data
        unrelated.base_hub_data = base_data
        unrelated.changed_paths = changed_paths
        unrelated.semantic_data_changed = True
        unrelated.events = [
            {
                "event_id": "HUB-TEST-UNRELATED",
                "map_ref": "SYSTEM/DEVELOPMENT-HUB",
                "affects": [],
            }
        ]
        unrelated.new_event_ids = {"HUB-TEST-UNRELATED"}
        unrelated.validate_structural_diff()
        self.assertTrue(
            any("WAVE-B/B-03" in error for error in unrelated.errors),
            unrelated.errors,
        )

        matching = validate_hub.Validator(REPO_ROOT)
        matching.data = candidate_data
        matching.base_hub_data = base_data
        matching.changed_paths = changed_paths
        matching.semantic_data_changed = True
        matching.events = [
            {
                "event_id": "HUB-TEST-B03",
                "map_ref": "WAVE-B/B-03",
                "affects": [],
            }
        ]
        matching.new_event_ids = {"HUB-TEST-B03"}
        matching.validate_structural_diff()
        self.assertEqual(matching.errors, [])

    def test_required_update_names_or_newly_event_covers_mapped_detail_owner(
        self,
    ) -> None:
        changed_paths = {
            "Business/Commercial_Operating_Model.md",
            "docs/development/carbon_hub/README.md",
        }

        missing = validate_hub.Validator(REPO_ROOT)
        missing.data = self.load_hub_data()
        missing.github_event = {
            "pull_request": {
                "body": (
                    "HUB_UPDATE_REQUIRED: SYSTEM/DEVELOPMENT-HUB; refreshed the "
                    "Development Hub orientation for this business-authority detail."
                )
            }
        }
        missing.changed_paths = changed_paths
        missing.validate_pr_declaration()
        self.assertTrue(
            any("mapped-detail owner refs" in error for error in missing.errors),
            missing.errors,
        )

        named = validate_hub.Validator(REPO_ROOT)
        named.data = self.load_hub_data()
        named.github_event = {
            "pull_request": {
                "body": (
                    "HUB_UPDATE_REQUIRED: SYSTEM/BUSINESS-AUTHORITY; refreshed the "
                    "Development Hub orientation for the mapped business detail."
                )
            }
        }
        named.changed_paths = changed_paths
        named.validate_pr_declaration()
        self.assertEqual(named.errors, [])

        event_covered = validate_hub.Validator(REPO_ROOT)
        event_covered.data = self.load_hub_data()
        event_covered.events = [
            {
                "event_id": "HUB-TEST-BUSINESS",
                "map_ref": "SYSTEM/BUSINESS-AUTHORITY",
                "affects": [],
            }
        ]
        event_covered.new_event_ids = {"HUB-TEST-BUSINESS"}
        event_covered.github_event = {
            "pull_request": {
                "body": (
                    "HUB_UPDATE_REQUIRED: SYSTEM/DEVELOPMENT-HUB; refreshed the "
                    "Development Hub orientation with newly recorded owner coverage."
                )
            }
        }
        event_covered.changed_paths = changed_paths
        event_covered.validate_pr_declaration()
        self.assertEqual(event_covered.errors, [])

    def test_event_rejects_undeclared_system_owner(self) -> None:
        validator = validate_hub.Validator(REPO_ROOT)
        validator.data = self.load_hub_data()
        validator.events = [
            {
                "map_ref": "SYSTEM/BOGUS",
                "event_type": "bug",
                "event_id": "HUB-TEST-BOGUS",
                "owner_lane": "documentation_maintenance",
                "status": "active",
                "summary": "A synthetic event exercises unknown system owner rejection.",
                "primary_detail": "docs/development/carbon_hub/README.md",
                "affects": [],
                "supersedes": None,
            }
        ]
        wave_set = {item["id"] for item in validator.data["waves"]}
        ticket_set = {item["id"] for item in validator.data["tickets"]}
        validator.validate_events(wave_set, ticket_set)
        self.assertTrue(
            any("SYSTEM owner not declared" in error for error in validator.errors),
            validator.errors,
        )

    @staticmethod
    def board_text(
        rows: list[tuple[str, str, str, str, list[str]]], version: str = "0.1"
    ) -> str:
        lines = [
            "# Fixture board",
            "",
            f"**Version:** {version}",
            "",
            "| ID | Deliverable | Status | Evidence | Driver | Accountable reviewer | Depends on |",
            "|---|---|---|---|---|---|---|",
        ]
        for ticket_id, status, owner, reviewer, dependencies in rows:
            dependency_text = ", ".join(dependencies) if dependencies else "—"
            lines.append(
                f"| {ticket_id} | {ticket_id} deliverable | {status} | fixture | "
                f"{owner} | {reviewer} | {dependency_text} |"
            )
        return "\n".join(lines) + "\n"

    def authority_fixture(
        self,
        *,
        wave: str,
        predecessor: str,
        selected: str,
        rows: list[tuple[str, str, str, str, list[str]]],
        version: str = "0.1",
        parallel_context: list[str] | None = None,
    ) -> tuple[validate_hub.Validator, dict[str, object]]:
        validator = validate_hub.Validator(REPO_ROOT)
        board_version, board_rows = validator.parse_ticket_board(
            self.board_text(rows, version), f"fixture Wave {wave} board"
        )
        tickets: list[dict[str, object]] = []
        for ticket_id, status, owner, reviewer, dependencies in rows:
            tickets.append(
                {
                    "id": ticket_id,
                    "wave": wave,
                    "title": f"{ticket_id} title",
                    "status": status,
                    "owner": owner,
                    "reviewer": reviewer,
                    "depends_on": dependencies,
                    "unlocks": [],
                    "current_stage": "Selected fixture stage.",
                }
            )
        for ticket in tickets:
            ticket["unlocks"] = [
                candidate["id"]
                for candidate in tickets
                if ticket["id"] in candidate["depends_on"]
            ]
        selected_record = next(ticket for ticket in tickets if ticket["id"] == selected)
        completed = [
            ticket_id
            for ticket_id, status, _owner, _reviewer, _dependencies in rows
            if status == "done"
        ]
        selected_dependencies = list(selected_record["depends_on"])
        other_completed = [
            ticket_id
            for ticket_id in completed
            if ticket_id not in set(selected_dependencies)
        ]
        state = "active in bounded fixture scope"
        register = f".agent/WAVE_{wave}.md"
        selected_status = str(selected_record["status"])
        validator.data = {
            "meta": {"repository": REPOSITORY_URL},
            "current": {
                "wave": wave,
                "wave_title": f"Wave {wave} title",
                "wave_status": state,
                "ticket": selected,
                "ticket_title": selected_record["title"],
                "ticket_status": selected_status,
                "controlling_register": register,
                "controlling_register_version": version,
                "controlling_board_fingerprint": validator.board_fingerprint(
                    board_version, board_rows
                ),
                "most_recent_closed_wave": predecessor,
                "completed_wave_tickets": completed,
                "recent_dependencies": selected_dependencies,
                "other_completed_wave_context": other_completed,
                "downstream_handoffs": selected_record["unlocks"],
                "parallel_context": parallel_context or [],
                "next_selected_ticket": None,
                "stage": selected_record["current_stage"],
                "technical_decision_route": f"{REPOSITORY_URL}/issues/42",
                "owner_decision_route": f"{REPOSITORY_URL}/issues/41",
                "decision_series": [],
            },
            "waves": [
                {
                    "id": predecessor,
                    "title": f"Wave {predecessor} title",
                    "status": "closed",
                    "predecessor": None,
                    "ticket_ids": [],
                },
                {
                    "id": wave,
                    "title": f"Wave {wave} title",
                    "status": "active",
                    "predecessor": predecessor,
                    "ticket_ids": [row[0] for row in rows],
                },
            ],
            "tickets": tickets,
        }
        view: dict[str, object] = {
            "authority": {
                "wave": wave,
                "state": state,
                "register": register,
                "register_version": version,
                "ticket": selected,
                "ticket_status": selected_status,
                "next_ticket": None,
                "closed_waves": (predecessor,),
            },
            "board_version": board_version,
            "board_rows": board_rows,
            "selected_source": f"# {selected}\n\n**Status:** {selected_status}\n",
            "decisions_text": "",
        }
        return validator, view

    def test_living_board_b03_and_empty_parallel_context(self) -> None:
        rows = [
            ("B-02A", "done", "owner-a", "reviewer-a", []),
            ("B-03", "in_progress", "owner-b", "reviewer-b", ["B-02A"]),
            ("B-04", "todo", "owner-c", "reviewer-c", ["B-02A"]),
        ]
        validator, view = self.authority_fixture(
            wave="B", predecessor="A", selected="B-03", rows=rows
        )
        validator.validate_authority_view(view, "fixture B-03")
        self.assertEqual(validator.errors, [])

    def test_board_deliverable_change_invalidates_captured_fingerprint(self) -> None:
        rows = [
            ("B-02A", "done", "owner-a", "reviewer-a", []),
            ("B-03", "in_progress", "owner-b", "reviewer-b", ["B-02A"]),
        ]
        validator, view = self.authority_fixture(
            wave="B", predecessor="A", selected="B-03", rows=rows
        )
        view["board_rows"]["B-03"]["deliverable"] = "Changed board deliverable"
        validator.validate_authority_view(view, "fixture deliverable drift")
        self.assertTrue(
            any("controlling_board_fingerprint" in error for error in validator.errors),
            validator.errors,
        )

    def test_board_ignores_ticket_ids_in_semicolon_nonblocking_clauses(self) -> None:
        board = """**Version:** 1.1

| ID | Deliverable | Status | Evidence | Driver | Accountable reviewer | Depends on | MQs | Effort | Target |
|---|---|---|---|---|---|---|---|---|---|
| B-01F | Delivery hardening | done | evidence | Codex | Tech lead | B-01E, ratified B-04 engineering contract | MQ-018 | L | WB-1/2 |
| B-01G | Codegen proof | todo | — | Codex | Tech lead | B-01F; non-blocking for B-04 | MQ-018 | S | future tooling |
| B-GATE | Closeout | todo | — | Codex | Tech lead | B-01F, B-04; B-01G explicitly non-blocking | MQ-018 | M | WB-5 |
"""
        validator = validate_hub.Validator(REPO_ROOT)
        version, rows = validator.parse_ticket_board(board, "fixture board")
        self.assertEqual(version, "1.1")
        self.assertEqual(rows["B-01F"]["depends_on"], ["B-01E", "B-04"])
        self.assertEqual(rows["B-01G"]["depends_on"], ["B-01F"])
        self.assertEqual(rows["B-GATE"]["depends_on"], ["B-01F", "B-04"])
        self.assertEqual(
            rows["B-01G"]["dependency_context"],
            "B-01F; non-blocking for B-04",
        )
        self.assertEqual(validator.errors, [])

    def test_selected_source_matches_leading_board_dependency_clause(self) -> None:
        rows = [
            ("B-02A", "done", "owner-a", "reviewer-a", []),
            ("B-01F", "done", "owner-b", "reviewer-b", []),
            (
                "B-04",
                "in_progress",
                "owner-c",
                "reviewer-c",
                ["B-02A", "B-01F"],
            ),
        ]
        validator, view = self.authority_fixture(
            wave="B", predecessor="A", selected="B-04", rows=rows
        )
        view["board_rows"]["B-04"][
            "dependency_context"
        ] = "B-02A; runtime additionally requires B-01F"
        view["selected_source"] = (
            "# B-04\n\n**Status:** in_progress\n**Depends on:** B-02A\n"
        )
        validator.validate_authority_view(view, "fixture B-04 runtime gate")
        self.assertEqual(validator.errors, [])

    def test_living_board_accepts_next_wave_b_ticket_selection(self) -> None:
        rows = [
            ("B-02A", "done", "owner-a", "reviewer-a", []),
            ("B-03", "done", "owner-b", "reviewer-b", ["B-02A"]),
            ("B-04", "in_progress", "owner-c", "reviewer-c", ["B-02A"]),
        ]
        validator, view = self.authority_fixture(
            wave="B", predecessor="A", selected="B-04", rows=rows
        )
        validator.validate_authority_view(view, "fixture B-04")
        self.assertEqual(validator.errors, [])

    def test_living_board_discovers_new_ticket_without_constant_change(self) -> None:
        rows = [
            ("B-02A", "done", "owner-a", "reviewer-a", []),
            ("B-03", "in_progress", "owner-b", "reviewer-b", ["B-02A"]),
            ("B-08", "todo", "owner-new", "reviewer-new", ["B-02A"]),
        ]
        validator, view = self.authority_fixture(
            wave="B", predecessor="A", selected="B-03", rows=rows
        )
        validator.validate_authority_view(view, "fixture B-08 insertion")
        self.assertEqual(validator.errors, [])
        validator.data["waves"][1]["ticket_ids"].remove("B-08")
        validator.validate_authority_view(view, "fixture missing B-08")
        self.assertTrue(any("B-08" in error for error in validator.errors))

    def test_living_board_supports_wave_c_register(self) -> None:
        rows = [
            ("C-01", "in_progress", "owner-c1", "reviewer-c1", []),
            ("C-02", "todo", "owner-c2", "reviewer-c2", ["C-01"]),
        ]
        validator, view = self.authority_fixture(
            wave="C", predecessor="B", selected="C-01", rows=rows
        )
        validator.validate_authority_view(view, "fixture Wave C")
        self.assertEqual(validator.errors, [])

    def test_loader_follows_named_wave_c_board_without_wave_b_file(self) -> None:
        rows = [("C-01", "in_progress", "owner-c1", "reviewer-c1", [])]
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / ".agent/tickets").mkdir(parents=True)
            wave_text = (
                "# Wave status\n\n"
                "**Current wave:** C\n"
                "**State:** active in bounded fixture scope\n"
                "**Controlling register:** `.agent/WAVE_C.md` version 0.1\n"
                "**Selected ticket:** C-01 — `in_progress`\n"
                "**Wave B:** closed in bounded scope\n"
            )
            (root / ".agent/WAVE.md").write_text(wave_text, encoding="utf-8")
            (root / ".agent/WAVE_C.md").write_text(
                self.board_text(rows), encoding="utf-8"
            )
            (root / ".agent/DECISIONS.md").write_text("# Decisions\n", encoding="utf-8")
            (root / ".agent/tickets/C-01.md").write_text(
                "# C-01\n\n**Status:** in_progress\n", encoding="utf-8"
            )
            validator = validate_hub.Validator(root)
            validator.data = {
                "tickets": [
                    {
                        "id": "C-01",
                        "repo_path": ".agent/tickets/C-01.md",
                    }
                ]
            }
            view = validator.load_authority_view("Wave C fixture")
            self.assertIsNotNone(view)
            self.assertEqual(view["authority"]["register"], ".agent/WAVE_C.md")
            self.assertFalse((root / ".agent/WAVE_B.md").exists())
            self.assertEqual(validator.errors, [])

    def test_data_driven_impact_classes_and_owners(self) -> None:
        validator = validate_hub.Validator(REPO_ROOT)
        validator.data = self.load_hub_data()
        cases = {
            ".agent/WAVE.md": ("map_structural", "WAVE-B"),
            ".agent/WAVE_B.md": ("map_structural", "WAVE-B"),
            ".agent/evidence/wave_b/b-03.md": (
                "mapped_detail",
                "WAVE-B/B-03",
            ),
            ".agent/plans/B-03_generator_burgers_fixture.md": (
                "mapped_detail",
                "WAVE-B/B-03",
            ),
            "Business/Commercial_Operating_Model.md": (
                "mapped_detail",
                "SYSTEM/BUSINESS-AUTHORITY",
            ),
            "docs/publications/example.md": (
                "mapped_detail",
                "SYSTEM/PUBLICATION-AUTHORITY",
            ),
            "launch/Carbon_Testnet_to_Mainnet_Launch_Path_v1.0.4.md": (
                "map_structural",
                "SYSTEM/DEVELOPMENT-SEQUENCING",
            ),
            ".agent/tickets/GOV-NET-01_post_wave_b_bittensor_roadmap.md": (
                "map_structural",
                "SYSTEM/DEVELOPMENT-SEQUENCING",
            ),
            ".agent/plans/GOV-NET-01_post_wave_b_bittensor_roadmap.md": (
                "mapped_detail",
                "SYSTEM/DEVELOPMENT-SEQUENCING",
            ),
            ".agent/evidence/governance/gov-net-01.md": (
                "mapped_detail",
                "SYSTEM/DEVELOPMENT-SEQUENCING",
            ),
            "Design_Specs/Build_Out_Protocol_Extension.md": (
                "map_structural",
                "SYSTEM/DEVELOPMENT-SEQUENCING",
            ),
            "docs/context/MASTER_OPEN_DESIGN_QUESTIONS.md": (
                "map_structural",
                "SYSTEM/GOVERNANCE",
            ),
            "docs/context/Architecture_Rationale.md": (
                "mapped_detail",
                "SYSTEM/PROTOCOL-AUTHORITY",
            ),
            "docs/context/Carbon_Context.md": (
                "mapped_detail",
                "SYSTEM/PROTOCOL-AUTHORITY",
            ),
            "docs/context/DEFENSIBILITY_REGISTER.md": (
                "mapped_detail",
                "SYSTEM/MATURITY",
            ),
            "docs/context/Decisions.md": (
                "mapped_detail",
                "SYSTEM/GOVERNANCE",
            ),
            "SPEC.md": ("mapped_detail", "SYSTEM/PROTOCOL-AUTHORITY"),
            "docs/history/LEGACY_CODE_INDEX.md": (
                "mapped_detail",
                "SYSTEM/AGENT-EXECUTION",
            ),
            ".agent/tickets/UNKNOWN_NEW.md": ("unmapped_authority", ""),
        }
        for path, expected in cases.items():
            with self.subTest(path=path):
                impact = validator.classify_impact(path)
                self.assertIsNotNone(impact)
                self.assertEqual((impact["impact_class"], impact["map_ref"]), expected)

    def test_impact_policy_cannot_remove_protected_authority_root(self) -> None:
        validator = validate_hub.Validator(REPO_ROOT)
        validator.data = self.load_hub_data()
        validator.data["impact_policy"]["authority_roots"].remove(".agent/")

        validator.validate_impact_policy()

        self.assertTrue(
            any(
                "authority_roots is missing required protected roots: .agent/" in error
                for error in validator.errors
            ),
            validator.errors,
        )

    def test_impact_policy_cannot_remove_launch_authority_root(self) -> None:
        validator = validate_hub.Validator(REPO_ROOT)
        validator.data = self.load_hub_data()
        validator.data["impact_policy"]["authority_roots"].remove("launch/")

        validator.validate_impact_policy()

        self.assertTrue(
            any(
                "authority_roots is missing required protected roots: launch/" in error
                for error in validator.errors
            ),
            validator.errors,
        )

    def test_ticket_checklist_is_detail_but_record_fields_are_structural(self) -> None:
        path = ".agent/tickets/B-03_generator_burgers_fixture.md"
        base_text = (
            "# B-03 generator fixture\n\n"
            "**Wave:** B\n"
            "**Status:** in_progress\n"
            "**Depends on:** B-02A\n"
            "**Owner:** owner-a\n"
            "**Accountable reviewer:** reviewer-a\n\n"
            "## Goal\n\nBuild the bounded generator fixture.\n\n"
            "## Must not\n\nWiden scientific authority.\n\n"
            "## Checklist\n\n- [ ] Original checklist item.\n"
        )
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            self.init_git_fixture(root)
            target = root / path
            target.parent.mkdir(parents=True)
            target.write_text(base_text, encoding="utf-8")
            self.run_git(root, "add", path)
            self.run_git(root, "commit", "-m", "ticket base")
            base = self.run_git(root, "rev-parse", "HEAD")

            validator = validate_hub.Validator(root)
            validator.data = self.load_hub_data()
            target.write_text(
                base_text.replace(
                    "- [ ] Original checklist item.",
                    "- [x] Original checklist item.\n- [ ] Added implementation check.",
                ),
                encoding="utf-8",
            )
            checklist = validator.classify_impact(path, comparison_base=base)
            self.assertEqual(checklist["impact_class"], "mapped_detail")
            self.assertEqual(checklist["map_ref"], "WAVE-B/B-03")

            structural_mutations = {
                "depends_on": base_text.replace("B-02A", "B-02B", 1),
                "owner": base_text.replace("owner-a", "owner-b", 1),
                "reviewer": base_text.replace("reviewer-a", "reviewer-b", 1),
            }
            for field, changed_text in structural_mutations.items():
                with self.subTest(field=field):
                    target.write_text(changed_text, encoding="utf-8")
                    impact = validator.classify_impact(path, comparison_base=base)
                    self.assertEqual(impact["impact_class"], "map_structural")
                    self.assertEqual(impact["map_ref"], "WAVE-B/B-03")

    def test_specific_no_impact_declaration_accepts_routine_evidence(self) -> None:
        validator = validate_hub.Validator(REPO_ROOT)
        validator.data = self.load_hub_data()
        validator.github_event = {
            "pull_request": {
                "body": (
                    "HUB_IMPACT_NONE: WAVE-B/B-03; the evidence record adds one "
                    "passing CI run only, while placement, status, dependencies, "
                    "maturity, boundaries, routes, and primary links are unchanged."
                )
            }
        }
        validator.changed_paths = {".agent/evidence/wave_b/b-03.md"}
        validator.validate_pr_declaration()
        self.assertEqual(validator.errors, [])

    def test_unmapped_authority_path_fails_closed(self) -> None:
        validator = validate_hub.Validator(REPO_ROOT)
        validator.data = self.load_hub_data()
        validator.changed_paths = {".agent/UNKNOWN_AUTHORITY.md"}
        validator.validate_structural_diff()
        self.assertTrue(any("no explicit" in error for error in validator.errors))

    def test_renderer_skips_byte_identical_output_write(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "generated.md"
            path.write_bytes(b"stable\n")
            old_timestamp = 1_600_000_000_000_000_000
            os.utime(path, ns=(old_timestamp, old_timestamp))
            self.assertTrue(render_hub.output_matches(path, "stable\n"))
            self.assertFalse(render_hub.write_if_changed(path, "stable\n"))
            self.assertEqual(path.stat().st_mtime_ns, old_timestamp)
            self.assertTrue(render_hub.write_if_changed(path, "changed\n"))
            self.assertEqual(path.read_bytes(), b"changed\n")
            path.write_bytes(b"stable\r\n")
            self.assertEqual(path.read_text(encoding="utf-8"), "stable\n")
            self.assertFalse(render_hub.output_matches(path, "stable\n"))
            self.assertTrue(render_hub.write_if_changed(path, "stable\n"))
            self.assertEqual(path.read_bytes(), b"stable\n")

    def test_b04_to_b05_transition_changes_exact_nine_semantic_outputs(self) -> None:
        baseline = self.load_hub_data()
        events = json.loads(
            (
                REPO_ROOT / "docs/development/carbon_hub/data/change_events.json"
            ).read_text(encoding="utf-8")
        )["events"]
        baseline = copy.deepcopy(baseline)
        b04 = next(ticket for ticket in baseline["tickets"] if ticket["id"] == "B-04")
        b05 = next(ticket for ticket in baseline["tickets"] if ticket["id"] == "B-05")
        baseline["current"].update(
            {
                "ticket": "B-04",
                "ticket_title": b04["title"],
                "ticket_status": "in_progress",
                "stage": "B-04 fixture implementation is selected.",
                "next_selected_ticket": "B-05",
            }
        )
        b04["status"] = "in_progress"
        b04["current_stage"] = "B-04 fixture implementation is selected."
        b05["status"] = "todo"
        b05["current_stage"] = "B-05 remains queued in the fixture."

        advanced = copy.deepcopy(baseline)
        advanced_b04 = next(
            ticket for ticket in advanced["tickets"] if ticket["id"] == "B-04"
        )
        advanced_b05 = next(
            ticket for ticket in advanced["tickets"] if ticket["id"] == "B-05"
        )
        advanced["current"].update(
            {
                "ticket": "B-05",
                "ticket_title": advanced_b05["title"],
                "ticket_status": "in_progress",
                "stage": "B-05 fixture authoring is selected.",
                "next_selected_ticket": "B-06",
            }
        )
        advanced_b04["status"] = "done"
        advanced_b04["current_stage"] = (
            "B-04 is done only in bounded fixture engineering scope."
        )
        advanced_b05["status"] = "in_progress"
        advanced_b05["current_stage"] = "B-05 fixture authoring is selected."

        old_snapshot = baseline["meta"]["authority_snapshot_commit"]
        new_snapshot = "f" * 40 if old_snapshot != "f" * 40 else "e" * 40
        advanced["meta"]["authority_snapshot_commit"] = new_snapshot
        advanced["meta"]["captured_at_utc"] = "2026-09-01T00:00:00Z"

        def repin_url(record: dict[str, object]) -> None:
            url = record.get("url")
            target = validate_hub.Validator.carbon_blob_target(url)
            if (
                isinstance(url, str)
                and target is not None
                and target[0] == old_snapshot
            ):
                record["url"] = url.replace(
                    f"/blob/{old_snapshot}/", f"/blob/{new_snapshot}/"
                )

        def repin_record(record: dict[str, object]) -> None:
            for link in record.get("repo_links", []):
                if isinstance(link, dict):
                    repin_url(link)

        for source in advanced["sources"].values():
            repin_url(source)
        active_wave = next(
            wave
            for wave in advanced["waves"]
            if wave["id"] == advanced["current"]["wave"]
        )
        repin_record(active_wave)
        repin_record(advanced_b05)

        historical_b03 = next(
            ticket for ticket in advanced["tickets"] if ticket["id"] == "B-03"
        )
        historical_revisions = {
            target[0]
            for link in historical_b03["repo_links"]
            if (target := validate_hub.Validator.carbon_blob_target(link["url"]))
            is not None
        }
        self.assertNotIn(new_snapshot, historical_revisions)

        fixture_event = copy.deepcopy(events[-1])
        fixture_event.update(
            {
                "event_id": "HUB-FANOUT-FIXTURE",
                "map_ref": "WAVE-B/B-05",
                "summary": "Fixture transition selects B-05 after B-04 closeout.",
                "primary_detail": (
                    f"{REPOSITORY_URL}/blob/{new_snapshot}/.agent/WAVE_B.md"
                ),
                "affects": ["WAVE-B/B-04", "WAVE-B/B-05"],
                "supersedes": events[-1]["event_id"],
            }
        )
        advanced_events = [*events, fixture_event]

        before = render_hub.collect_outputs(baseline, events)
        after = render_hub.collect_outputs(advanced, advanced_events)
        self.assertEqual(set(before), set(after))
        changed = {
            path.relative_to(render_hub.ROOT).as_posix()
            for path in set(before) | set(after)
            if before.get(path) != after.get(path)
        }
        self.assertEqual(
            changed,
            {
                "index.html",
                "interactive.html",
                "Carbon_Development_Hub_v2.md",
                "README.md",
                "data/hub_index_v2.yaml",
                "orientation/START_HERE.md",
                "explainers/waves/wave_b.md",
                "explainers/tickets/b_04.md",
                "explainers/tickets/b_05.md",
            },
        )

    def test_historical_ancestor_repin_is_semantic_and_requires_reconciliation(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            self.init_git_fixture(root)
            marker = root / "authority.txt"
            revisions = []
            for index in range(3):
                marker.write_text(f"authority {index}\n", encoding="utf-8")
                self.run_git(root, "add", "authority.txt")
                self.run_git(root, "commit", "-m", f"authority {index}")
                revisions.append(self.run_git(root, "rev-parse", "HEAD"))
            ancestor_a, ancestor_b, snapshot = revisions

            def pinned_ticket(ticket_id: str, revision: str) -> dict[str, object]:
                return {
                    "id": ticket_id,
                    "wave": "B",
                    "repo_links": [
                        {
                            "label": "Historical authority",
                            "url": (f"{REPOSITORY_URL}/blob/{revision}/authority.txt"),
                        }
                    ],
                }

            base = {
                "meta": {"authority_snapshot_commit": snapshot},
                "tickets": [
                    pinned_ticket("B-01", ancestor_a),
                    pinned_ticket("B-02", ancestor_b),
                ],
            }
            unchanged_mixed = copy.deepcopy(base)
            self.assertEqual(
                validate_hub.Validator.semantic_data_view(base),
                validate_hub.Validator.semantic_data_view(unchanged_mixed),
            )

            repinned = copy.deepcopy(base)
            repinned["tickets"][0]["repo_links"][0][
                "url"
            ] = f"{REPOSITORY_URL}/blob/{ancestor_b}/authority.txt"
            self.assertNotEqual(
                validate_hub.Validator.semantic_data_view(base),
                validate_hub.Validator.semantic_data_view(repinned),
            )

            validator = validate_hub.Validator(root)
            validator.base_hub_data = base
            validator.data = repinned
            validator.semantic_data_changed = True
            validator.changed_paths = {
                "docs/development/carbon_hub/data/hub_data_v2.json"
            }
            self.assertIn("WAVE-B/B-01", validator.semantic_change_map_refs())
            validator.validate_structural_diff()
            self.assertTrue(
                any("change event" in error.lower() for error in validator.errors),
                validator.errors,
            )

    def test_current_snapshot_repin_remains_nonsemantic(self) -> None:
        old_snapshot = "a" * 40
        new_snapshot = "b" * 40
        base = {
            "meta": {
                "authority_snapshot_commit": old_snapshot,
                "captured_at_utc": "2026-01-01T00:00:00Z",
            },
            "sources": {
                "current": {
                    "url": (f"{REPOSITORY_URL}/blob/{old_snapshot}/authority.txt")
                }
            },
        }
        current = copy.deepcopy(base)
        current["meta"]["authority_snapshot_commit"] = new_snapshot
        current["meta"]["captured_at_utc"] = "2026-01-02T00:00:00Z"
        current["sources"]["current"][
            "url"
        ] = f"{REPOSITORY_URL}/blob/{new_snapshot}/authority.txt"
        self.assertFalse(
            validate_hub.Validator.semantic_data_changed_between(base, current)
        )

    def test_paired_snapshot_normalization_preserves_frozen_historical_links(
        self,
    ) -> None:
        snapshot_a = "a" * 40
        ancestor_b = "b" * 40
        snapshot_c = "c" * 40
        ancestor_d = "d" * 40

        def fixture(snapshot: str, link_revision: str) -> dict[str, object]:
            return {
                "meta": {"authority_snapshot_commit": snapshot},
                "current": {"wave": "B", "ticket": "B-01"},
                "tickets": [
                    {
                        "id": "B-01",
                        "wave": "B",
                        "repo_links": [
                            {
                                "label": "Pinned authority",
                                "url": (
                                    f"{REPOSITORY_URL}/blob/{link_revision}/"
                                    "authority.txt"
                                ),
                            }
                        ],
                    }
                ],
            }

        base = fixture(snapshot_a, snapshot_a)
        frozen_former_current = fixture(snapshot_c, snapshot_a)
        advanced_current_pin = fixture(snapshot_c, snapshot_c)
        ancestor_b_base = fixture(snapshot_a, ancestor_b)
        ancestor_d_current = fixture(snapshot_c, ancestor_d)
        repinned_ancestor = fixture(snapshot_c, ancestor_b)

        self.assertFalse(
            validate_hub.Validator.semantic_data_changed_between(
                base, frozen_former_current
            )
        )
        self.assertFalse(
            validate_hub.Validator.semantic_data_changed_between(
                base, advanced_current_pin
            )
        )
        self.assertTrue(
            validate_hub.Validator.semantic_data_changed_between(
                ancestor_b_base, ancestor_d_current
            )
        )
        self.assertTrue(
            validate_hub.Validator.semantic_data_changed_between(
                base, repinned_ancestor
            )
        )

        unchanged = validate_hub.Validator(REPO_ROOT)
        unchanged.base_hub_data = base
        unchanged.data = frozen_former_current
        self.assertEqual(unchanged.semantic_change_map_refs(), set())

        repinned = validate_hub.Validator(REPO_ROOT)
        repinned.base_hub_data = base
        repinned.data = repinned_ancestor
        self.assertEqual(repinned.semantic_change_map_refs(), {"WAVE-B/B-01"})

    def test_noncurrent_former_snapshot_repin_is_semantic(self) -> None:
        snapshot_a = "a" * 40
        snapshot_c = "c" * 40

        def fixture(snapshot: str, historical_revision: str) -> dict[str, object]:
            return {
                "meta": {"authority_snapshot_commit": snapshot},
                "current": {"wave": "B", "ticket": "B-02"},
                "tickets": [
                    {
                        "id": "B-01",
                        "wave": "B",
                        "repo_links": [
                            {
                                "label": "Historical authority",
                                "url": (
                                    f"{REPOSITORY_URL}/blob/{historical_revision}/"
                                    "authority.txt"
                                ),
                            }
                        ],
                    },
                    {"id": "B-02", "wave": "B", "repo_links": []},
                ],
            }

        base = fixture(snapshot_a, snapshot_a)
        mass_repinned = fixture(snapshot_c, snapshot_c)
        self.assertTrue(
            validate_hub.Validator.semantic_data_changed_between(base, mass_repinned)
        )
        validator = validate_hub.Validator(REPO_ROOT)
        validator.base_hub_data = base
        validator.data = mass_repinned
        self.assertEqual(validator.semantic_change_map_refs(), {"WAVE-B/B-01"})

    def test_former_selected_ticket_must_freeze_its_historical_pin(self) -> None:
        snapshot_a = "a" * 40
        snapshot_c = "c" * 40

        def fixture(
            snapshot: str,
            selected: str,
            b04_revision: str,
            b05_revision: str,
        ) -> dict[str, object]:
            def ticket(ticket_id: str, revision: str) -> dict[str, object]:
                return {
                    "id": ticket_id,
                    "wave": "B",
                    "repo_links": [
                        {
                            "label": "Pinned authority",
                            "url": (
                                f"{REPOSITORY_URL}/blob/{revision}/"
                                f".agent/tickets/{ticket_id}.md"
                            ),
                        }
                    ],
                }

            return {
                "meta": {"authority_snapshot_commit": snapshot},
                "current": {"wave": "B", "ticket": selected},
                "tickets": [
                    ticket("B-04", b04_revision),
                    ticket("B-05", b05_revision),
                ],
            }

        base = fixture(snapshot_a, "B-04", snapshot_a, snapshot_a)
        frozen = fixture(snapshot_c, "B-05", snapshot_a, snapshot_c)
        repinned = fixture(snapshot_c, "B-05", snapshot_c, snapshot_c)

        frozen_validator = validate_hub.Validator(REPO_ROOT)
        frozen_validator.base_hub_data = base
        frozen_validator.data = frozen
        self.assertEqual(frozen_validator.semantic_change_map_refs(), {"WAVE-B/B-05"})

        repinned_validator = validate_hub.Validator(REPO_ROOT)
        repinned_validator.base_hub_data = base
        repinned_validator.data = repinned
        self.assertEqual(
            repinned_validator.semantic_change_map_refs(),
            {"WAVE-B/B-04", "WAVE-B/B-05"},
        )

    def test_former_active_wave_must_freeze_its_historical_pin(self) -> None:
        snapshot_a = "a" * 40
        snapshot_c = "c" * 40

        def fixture(
            snapshot: str,
            active: str,
            wave_b_revision: str,
            wave_c_revision: str,
        ) -> dict[str, object]:
            def wave(wave_id: str, revision: str) -> dict[str, object]:
                return {
                    "id": wave_id,
                    "repo_links": [
                        {
                            "label": "Controlling board",
                            "url": (
                                f"{REPOSITORY_URL}/blob/{revision}/"
                                f".agent/WAVE_{wave_id}.md"
                            ),
                        }
                    ],
                }

            return {
                "meta": {"authority_snapshot_commit": snapshot},
                "current": {"wave": active},
                "waves": [
                    wave("B", wave_b_revision),
                    wave("C", wave_c_revision),
                ],
            }

        base = fixture(snapshot_a, "B", snapshot_a, snapshot_a)
        frozen = fixture(snapshot_c, "C", snapshot_a, snapshot_c)
        repinned = fixture(snapshot_c, "C", snapshot_c, snapshot_c)

        frozen_validator = validate_hub.Validator(REPO_ROOT)
        frozen_validator.base_hub_data = base
        frozen_validator.data = frozen
        self.assertEqual(frozen_validator.semantic_change_map_refs(), {"WAVE-C"})

        repinned_validator = validate_hub.Validator(REPO_ROOT)
        repinned_validator.base_hub_data = base
        repinned_validator.data = repinned
        self.assertEqual(
            repinned_validator.semantic_change_map_refs(), {"WAVE-B", "WAVE-C"}
        )

    @staticmethod
    def run_git(root: Path, *args: str) -> str:
        result = subprocess.run(
            ["git", "-C", str(root), *args],
            check=True,
            text=True,
            encoding="utf-8",
            capture_output=True,
        )
        return result.stdout.strip()

    def init_git_fixture(self, root: Path) -> None:
        self.run_git(root, "init", "-b", "main")
        self.run_git(root, "config", "user.name", "Hub Validator Fixture")
        self.run_git(root, "config", "user.email", "hub-validator@example.invalid")

    @staticmethod
    def snapshot_fixture_data(
        snapshot: str,
        *,
        evidence: bool = False,
        authority_source_checks: list[dict[str, object]] | None = None,
    ) -> dict[str, object]:
        links = [
            {
                "label": "Repo ticket",
                "url": f"{REPOSITORY_URL}/blob/{snapshot}/.agent/tickets/B-03.md",
            }
        ]
        if evidence:
            links.append(
                {
                    "label": "Evidence record",
                    "url": f"{REPOSITORY_URL}/blob/{snapshot}/.agent/evidence/B-03.md",
                }
            )
        data: dict[str, object] = {
            "meta": {
                "authority_snapshot_commit": snapshot,
                "captured_at_utc": datetime.now(UTC)
                .replace(microsecond=0)
                .strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
            "current": {"ticket": "B-03", "stage": "Fixture stage."},
            "sources": {
                "current_wave": {
                    "label": "Current wave register",
                    "url": f"{REPOSITORY_URL}/blob/{snapshot}/.agent/WAVE.md",
                }
            },
            "tickets": [
                {
                    "id": "B-03",
                    "repo_path": ".agent/tickets/B-03.md",
                    "repo_links": links,
                }
            ],
        }
        if authority_source_checks is not None:
            data["authority_source_checks"] = authority_source_checks
        return data

    def test_unrelated_main_advance_and_merge_preserve_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            self.init_git_fixture(root)
            (root / ".agent/tickets").mkdir(parents=True)
            (root / ".agent/WAVE.md").write_text(
                "# Fixture wave\n\nSelected ticket B-03.\n", encoding="utf-8"
            )
            (root / ".agent/tickets/B-03.md").write_text(
                "# B-03 authority snapshot\n", encoding="utf-8"
            )
            self.run_git(root, "add", ".agent")
            self.run_git(root, "commit", "-m", "authority snapshot S")
            snapshot = self.run_git(root, "rev-parse", "HEAD")
            self.run_git(root, "switch", "-c", "hub")
            captured = (
                datetime.now(UTC).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")
            )
            playbook = (
                root / "docs/development/carbon_hub/orientation/HUB_UPDATE_PLAYBOOK.md"
            )
            playbook.parent.mkdir(parents=True)
            playbook.write_text(
                f"Current authority snapshot: `{snapshot}`, reconciled {captured}.\n",
                encoding="utf-8",
            )
            self.run_git(root, "add", "docs")
            self.run_git(root, "commit", "-m", "Hub commit H")
            self.run_git(root, "switch", "main")
            (root / "carbon").mkdir()
            (root / "carbon/unrelated.txt").write_text("advance M\n", encoding="utf-8")
            self.run_git(root, "add", "carbon/unrelated.txt")
            self.run_git(root, "commit", "-m", "unrelated main advance M")
            diff_base = self.run_git(root, "rev-parse", "HEAD")
            self.run_git(root, "merge", "--no-ff", "hub", "-m", "merge Hub H")
            validator = validate_hub.Validator(root)
            validator.data = self.snapshot_fixture_data(snapshot)
            validator.data["meta"]["captured_at_utc"] = captured
            validator.captured_at = datetime.strptime(
                captured, "%Y-%m-%dT%H:%M:%SZ"
            ).replace(tzinfo=UTC)
            validator.diff_base_sha = diff_base
            validator.semantic_data_changed = True
            validator.validate_snapshot_metadata()
            self.assertNotEqual(snapshot, diff_base)
            self.assertEqual(validator.errors, [])

    def test_post_merge_structural_main_advance_rejects_stale_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            self.init_git_fixture(root)
            (root / ".agent/tickets").mkdir(parents=True)
            wave_in_progress = (
                "# Fixture wave authority\n\n"
                "**Current wave:** B\n"
                "**State:** active in bounded fixture scope\n"
                "**Controlling register:** `.agent/WAVE_B.md` version 0.1\n"
                "**Selected ticket:** B-03 — `in_progress`\n"
                "**Wave A:** closed in bounded scope\n"
            )
            (root / ".agent/WAVE.md").write_text(wave_in_progress, encoding="utf-8")
            (root / ".agent/tickets/B-03.md").write_text(
                "# B-03 authority at snapshot S\n", encoding="utf-8"
            )
            self.run_git(root, "add", ".agent")
            self.run_git(root, "commit", "-m", "snapshot S")
            snapshot_s = self.run_git(root, "rev-parse", "HEAD")

            self.run_git(root, "switch", "-c", "hub")
            (root / ".agent/tickets/B-03.md").write_text(
                "# B-03 authority commit A\n\nHUB-AUTHORITY-A\n",
                encoding="utf-8",
            )
            self.run_git(root, "add", ".agent/tickets/B-03.md")
            self.run_git(root, "commit", "-m", "Hub authority commit A")
            authority_a = self.run_git(root, "rev-parse", "HEAD")

            captured = (
                datetime.now(UTC).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")
            )
            playbook = (
                root / "docs/development/carbon_hub/orientation/HUB_UPDATE_PLAYBOOK.md"
            )
            playbook.parent.mkdir(parents=True)
            playbook.write_text(
                f"Current authority snapshot: `{authority_a}`, reconciled {captured}.\n",
                encoding="utf-8",
            )
            self.run_git(root, "add", "docs")
            self.run_git(root, "commit", "-m", "Hub build H pinned to A")

            self.run_git(root, "switch", "main")
            (root / ".agent/WAVE.md").write_text(
                wave_in_progress.replace("`in_progress`", "`done`"),
                encoding="utf-8",
            )
            self.run_git(root, "add", ".agent/WAVE.md")
            self.run_git(root, "commit", "-m", "mapped structural main advance M")
            main_advance = self.run_git(root, "rev-parse", "HEAD")
            self.run_git(root, "merge", "--no-ff", "hub", "-m", "merge Hub H")

            validator = validate_hub.Validator(root)
            validator.data = self.snapshot_fixture_data(authority_a)
            validator.data["current"]["wave"] = "B"
            validator.data["impact_policy"] = copy.deepcopy(
                self.load_hub_data()["impact_policy"]
            )
            validator.data["meta"]["captured_at_utc"] = captured
            validator.captured_at = datetime.strptime(
                captured, "%Y-%m-%dT%H:%M:%SZ"
            ).replace(tzinfo=UTC)
            with patch.dict(
                os.environ, {"HUB_DIFF_BASE_SHA": main_advance}, clear=False
            ):
                validator.collect_diff()

            self.assertNotEqual(snapshot_s, authority_a)
            self.assertEqual(validator.diff_base_sha, main_advance)
            self.assertNotIn(".agent/WAVE.md", validator.changed_paths)
            impact = validator.classify_impact(
                ".agent/WAVE.md", comparison_base=authority_a
            )
            self.assertEqual(impact["impact_class"], "map_structural")
            self.assertEqual(impact["map_ref"], "WAVE-B")
            self.assertEqual(validator.errors, [])

            validator.validate_snapshot_metadata()
            self.assertTrue(
                any(
                    "Map-structural authority changed after authority_snapshot_commit"
                    in error
                    and ".agent/WAVE.md" in error
                    for error in validator.errors
                ),
                validator.errors,
            )

    def test_post_merge_unmapped_main_advance_rejects_stale_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            self.init_git_fixture(root)
            (root / ".agent/tickets").mkdir(parents=True)
            (root / ".agent/WAVE.md").write_text(
                "# Fixture wave\n\nSelected ticket B-03.\n", encoding="utf-8"
            )
            (root / ".agent/tickets/B-03.md").write_text(
                "# B-03 authority at snapshot S\n", encoding="utf-8"
            )
            self.run_git(root, "add", ".agent")
            self.run_git(root, "commit", "-m", "snapshot S")

            self.run_git(root, "switch", "-c", "hub")
            (root / ".agent/tickets/B-03.md").write_text(
                "# B-03 authority commit A\n\nHUB-AUTHORITY-A\n",
                encoding="utf-8",
            )
            self.run_git(root, "add", ".agent/tickets/B-03.md")
            self.run_git(root, "commit", "-m", "Hub authority commit A")
            authority_a = self.run_git(root, "rev-parse", "HEAD")

            captured = (
                datetime.now(UTC).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")
            )
            playbook = (
                root / "docs/development/carbon_hub/orientation/HUB_UPDATE_PLAYBOOK.md"
            )
            playbook.parent.mkdir(parents=True)
            playbook.write_text(
                f"Current authority snapshot: `{authority_a}`, reconciled {captured}.\n",
                encoding="utf-8",
            )
            self.run_git(root, "add", "docs")
            self.run_git(root, "commit", "-m", "Hub build H pinned to A")

            self.run_git(root, "switch", "main")
            unknown_path = ".agent/UNMAPPED_AUTHORITY.md"
            (root / unknown_path).write_text(
                "# New authority without a Hub owner\n", encoding="utf-8"
            )
            self.run_git(root, "add", unknown_path)
            self.run_git(root, "commit", "-m", "unmapped authority main advance M")
            main_advance = self.run_git(root, "rev-parse", "HEAD")
            self.run_git(root, "merge", "--no-ff", "hub", "-m", "merge Hub H")

            validator = validate_hub.Validator(root)
            validator.data = self.snapshot_fixture_data(authority_a)
            validator.data["current"]["wave"] = "B"
            validator.data["impact_policy"] = copy.deepcopy(
                self.load_hub_data()["impact_policy"]
            )
            validator.data["meta"]["captured_at_utc"] = captured
            validator.captured_at = datetime.strptime(
                captured, "%Y-%m-%dT%H:%M:%SZ"
            ).replace(tzinfo=UTC)
            with patch.dict(
                os.environ, {"HUB_DIFF_BASE_SHA": main_advance}, clear=False
            ):
                validator.collect_diff()

            self.assertEqual(validator.diff_base_sha, main_advance)
            self.assertNotIn(unknown_path, validator.changed_paths)
            impact = validator.classify_impact(
                unknown_path, comparison_base=authority_a
            )
            self.assertEqual(impact["impact_class"], "unmapped_authority")
            self.assertEqual(impact["rule_id"], "unmapped-authority-root")
            self.assertEqual(validator.errors, [])

            validator.validate_snapshot_metadata()
            self.assertTrue(
                any(
                    "Unmapped authority changed after authority_snapshot_commit"
                    in error
                    and unknown_path in error
                    for error in validator.errors
                ),
                validator.errors,
            )

    def test_authority_rename_preserves_source_path_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            self.init_git_fixture(root)
            (root / ".agent/tickets").mkdir(parents=True)
            (root / ".agent/WAVE.md").write_text(
                "# Fixture wave\n\nSelected ticket B-03.\n", encoding="utf-8"
            )
            (root / ".agent/tickets/B-03.md").write_text(
                "# B-03 authority at snapshot S\n", encoding="utf-8"
            )
            self.run_git(root, "add", ".agent")
            self.run_git(root, "commit", "-m", "snapshot S")
            snapshot_s = self.run_git(root, "rev-parse", "HEAD")

            self.run_git(root, "switch", "-c", "hub")
            (root / ".agent/tickets/B-03.md").write_text(
                "# B-03 authority commit A\n\nHUB-AUTHORITY-A\n",
                encoding="utf-8",
            )
            self.run_git(root, "add", ".agent/tickets/B-03.md")
            self.run_git(root, "commit", "-m", "Hub authority commit A")
            authority_a = self.run_git(root, "rev-parse", "HEAD")

            captured = (
                datetime.now(UTC).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")
            )
            playbook = (
                root / "docs/development/carbon_hub/orientation/HUB_UPDATE_PLAYBOOK.md"
            )
            playbook.parent.mkdir(parents=True)
            playbook.write_text(
                f"Current authority snapshot: `{authority_a}`, reconciled {captured}.\n",
                encoding="utf-8",
            )
            self.run_git(root, "add", "docs")
            self.run_git(root, "commit", "-m", "Hub build H pinned to A")

            self.run_git(root, "switch", "main")
            destination = "outside-authority/WAVE.md"
            (root / "outside-authority").mkdir()
            self.run_git(root, "mv", ".agent/WAVE.md", destination)
            self.run_git(root, "commit", "-m", "rename authority outside root M")
            main_advance = self.run_git(root, "rev-parse", "HEAD")
            self.run_git(root, "merge", "--no-ff", "hub", "-m", "merge Hub H")

            def fixture_validator() -> validate_hub.Validator:
                validator = validate_hub.Validator(root)
                validator.data = self.snapshot_fixture_data(authority_a)
                validator.data["current"]["wave"] = "B"
                validator.data["impact_policy"] = copy.deepcopy(
                    self.load_hub_data()["impact_policy"]
                )
                validator.data["meta"]["captured_at_utc"] = captured
                validator.captured_at = datetime.strptime(
                    captured, "%Y-%m-%dT%H:%M:%SZ"
                ).replace(tzinfo=UTC)
                return validator

            post_merge = fixture_validator()
            with patch.dict(
                os.environ, {"HUB_DIFF_BASE_SHA": main_advance}, clear=False
            ):
                post_merge.collect_diff()
            self.assertNotIn(".agent/WAVE.md", post_merge.changed_paths)
            self.assertEqual(post_merge.errors, [])

            post_merge.validate_snapshot_metadata()
            self.assertTrue(
                any(
                    "Map-structural authority changed after authority_snapshot_commit"
                    in error
                    and ".agent/WAVE.md" in error
                    for error in post_merge.errors
                ),
                post_merge.errors,
            )

            pull_request = fixture_validator()
            with patch.dict(os.environ, {"HUB_DIFF_BASE_SHA": snapshot_s}, clear=False):
                pull_request.collect_diff()
            self.assertIn(".agent/WAVE.md", pull_request.changed_paths)
            self.assertIn(".agent/WAVE.md", pull_request.deleted_paths)
            self.assertIn(destination, pull_request.changed_paths)

            pull_request.validate_structural_diff()
            self.assertTrue(
                any(
                    "Map-structural repository changes require an updated "
                    "data/hub_data_v2.json" in error
                    for error in pull_request.errors
                ),
                pull_request.errors,
            )

    def test_nonselected_blob_main_link_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            self.init_git_fixture(root)
            (root / ".agent/tickets").mkdir(parents=True)
            (root / ".agent/WAVE.md").write_text(
                "# Fixture wave\n\nSelected ticket B-03.\n", encoding="utf-8"
            )
            (root / ".agent/tickets/B-03.md").write_text(
                "# B-03 authority snapshot\n", encoding="utf-8"
            )
            (root / "docs").mkdir()
            (root / "docs/nonselected.md").write_text(
                "# Non-selected detail\n", encoding="utf-8"
            )
            self.run_git(root, "add", ".agent", "docs/nonselected.md")
            self.run_git(root, "commit", "-m", "authority snapshot")
            snapshot = self.run_git(root, "rev-parse", "HEAD")
            captured = (
                datetime.now(UTC).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")
            )
            playbook = (
                root / "docs/development/carbon_hub/orientation/HUB_UPDATE_PLAYBOOK.md"
            )
            playbook.parent.mkdir(parents=True)
            playbook.write_text(
                f"Current authority snapshot: `{snapshot}`, reconciled {captured}.\n",
                encoding="utf-8",
            )
            validator = validate_hub.Validator(root)
            validator.data = self.snapshot_fixture_data(snapshot)
            validator.data["tickets"].append(
                {
                    "id": "B-04",
                    "repo_links": [
                        {
                            "label": "Non-selected detail",
                            "url": (f"{REPOSITORY_URL}/blob/main/docs/nonselected.md"),
                        }
                    ],
                }
            )
            validator.data["meta"]["captured_at_utc"] = captured
            validator.captured_at = datetime.strptime(
                captured, "%Y-%m-%dT%H:%M:%SZ"
            ).replace(tzinfo=UTC)
            validator.validate_snapshot_metadata()
            self.assertTrue(
                any(
                    "exact lowercase 40-character commit" in error
                    for error in validator.errors
                ),
                validator.errors,
            )

    def test_noncurrent_records_may_pin_validated_exact_snapshot_ancestors(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            self.init_git_fixture(root)
            (root / ".agent/tickets").mkdir(parents=True)
            (root / ".agent/WAVE.md").write_text(
                "# Fixture wave\n\nSelected ticket B-03.\n", encoding="utf-8"
            )
            (root / ".agent/tickets/B-03.md").write_text(
                "# B-03 selected ticket\n", encoding="utf-8"
            )
            (root / ".agent/tickets/B-02.md").write_text(
                "# B-02 historical ticket\n", encoding="utf-8"
            )
            self.run_git(root, "add", ".agent")
            self.run_git(root, "commit", "-m", "historical authority")
            ancestor = self.run_git(root, "rev-parse", "HEAD")
            (root / ".agent/tickets/B-03.md").write_text(
                "# B-03 selected ticket at current snapshot\n", encoding="utf-8"
            )
            self.run_git(root, "add", ".agent/tickets/B-03.md")
            self.run_git(root, "commit", "-m", "current authority snapshot")
            snapshot = self.run_git(root, "rev-parse", "HEAD")
            captured = (
                datetime.now(UTC).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")
            )
            playbook = (
                root / "docs/development/carbon_hub/orientation/HUB_UPDATE_PLAYBOOK.md"
            )
            playbook.parent.mkdir(parents=True)
            playbook.write_text(
                f"Current authority snapshot: `{snapshot}`, reconciled {captured}.\n",
                encoding="utf-8",
            )
            validator = validate_hub.Validator(root)
            validator.data = self.snapshot_fixture_data(snapshot)
            validator.data["tickets"].append(
                {
                    "id": "B-02",
                    "repo_links": [
                        {
                            "label": "Historical repo ticket",
                            "url": (
                                f"{REPOSITORY_URL}/blob/{ancestor}/"
                                ".agent/tickets/B-02.md"
                            ),
                        }
                    ],
                }
            )
            validator.data["meta"]["captured_at_utc"] = captured
            validator.captured_at = datetime.strptime(
                captured, "%Y-%m-%dT%H:%M:%SZ"
            ).replace(tzinfo=UTC)
            validator.validate_snapshot_metadata()
            self.assertNotEqual(ancestor, snapshot)
            self.assertEqual(validator.errors, [])

    def test_selected_ticket_remains_pinned_to_current_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            self.init_git_fixture(root)
            (root / ".agent/tickets").mkdir(parents=True)
            (root / ".agent/WAVE.md").write_text(
                "# Fixture wave\n\nSelected ticket B-03.\n", encoding="utf-8"
            )
            (root / ".agent/tickets/B-03.md").write_text(
                "# B-03 historical ticket\n", encoding="utf-8"
            )
            self.run_git(root, "add", ".agent")
            self.run_git(root, "commit", "-m", "historical authority")
            ancestor = self.run_git(root, "rev-parse", "HEAD")
            (root / ".agent/tickets/B-03.md").write_text(
                "# B-03 current ticket\n", encoding="utf-8"
            )
            self.run_git(root, "add", ".agent/tickets/B-03.md")
            self.run_git(root, "commit", "-m", "current authority snapshot")
            snapshot = self.run_git(root, "rev-parse", "HEAD")
            captured = (
                datetime.now(UTC).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")
            )
            playbook = (
                root / "docs/development/carbon_hub/orientation/HUB_UPDATE_PLAYBOOK.md"
            )
            playbook.parent.mkdir(parents=True)
            playbook.write_text(
                f"Current authority snapshot: `{snapshot}`, reconciled {captured}.\n",
                encoding="utf-8",
            )
            validator = validate_hub.Validator(root)
            validator.data = self.snapshot_fixture_data(snapshot)
            validator.data["tickets"][0]["repo_links"][0][
                "url"
            ] = f"{REPOSITORY_URL}/blob/{ancestor}/.agent/tickets/B-03.md"
            validator.data["meta"]["captured_at_utc"] = captured
            validator.captured_at = datetime.strptime(
                captured, "%Y-%m-%dT%H:%M:%SZ"
            ).replace(tzinfo=UTC)
            validator.validate_snapshot_metadata()
            self.assertTrue(
                any(
                    "selected ticket repo_links" in error
                    or "Selected-ticket repo ticket link" in error
                    for error in validator.errors
                ),
                validator.errors,
            )

    def test_two_commit_authority_then_hub_pins_mapped_content(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            self.init_git_fixture(root)
            (root / ".agent/tickets").mkdir(parents=True)
            (root / ".agent/evidence").mkdir(parents=True)
            (root / ".agent/WAVE.md").write_text(
                "# Fixture wave\n\nSelected ticket B-03.\n", encoding="utf-8"
            )
            (root / ".agent/tickets/B-03.md").write_text(
                "# B-03 before mapped change\n", encoding="utf-8"
            )
            (root / ".agent/evidence/B-03.md").write_text(
                "# B-03 earlier evidence\n", encoding="utf-8"
            )
            self.run_git(root, "add", ".agent")
            self.run_git(root, "commit", "-m", "prior authority S")
            prior = self.run_git(root, "rev-parse", "HEAD")
            (root / ".agent/tickets/B-03.md").write_text(
                "# B-03 mapped authority change A\n\nUNIQUE-A-TICKET-MARKER\n",
                encoding="utf-8",
            )
            (root / ".agent/evidence/B-03.md").write_text(
                "# B-03 selected after mapped authority change A\n\n"
                "UNIQUE-A-EVIDENCE-MARKER\n",
                encoding="utf-8",
            )
            self.run_git(root, "add", ".agent")
            self.run_git(root, "commit", "-m", "mapped authority commit A")
            snapshot = self.run_git(root, "rev-parse", "HEAD")
            captured = (
                datetime.now(UTC).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")
            )
            playbook = (
                root / "docs/development/carbon_hub/orientation/HUB_UPDATE_PLAYBOOK.md"
            )
            playbook.parent.mkdir(parents=True)
            playbook.write_text(
                f"Current authority snapshot: `{snapshot}`, reconciled {captured}.\n"
                f"Current authority snapshot: `{prior}`, reconciled {captured}.\n",
                encoding="utf-8",
            )
            self.run_git(root, "add", "docs")
            self.run_git(root, "commit", "-m", "Hub source commit H")
            source_checks = [
                {
                    "id": "current-wave",
                    "path": ".agent/WAVE.md",
                    "required_markers": ["Selected ticket B-03."],
                },
                {
                    "id": "selected-ticket",
                    "path": ".agent/tickets/B-03.md",
                    "required_markers": ["UNIQUE-A-TICKET-MARKER"],
                },
                {
                    "id": "selected-evidence",
                    "path": ".agent/evidence/B-03.md",
                    "required_markers": ["UNIQUE-A-EVIDENCE-MARKER"],
                },
            ]
            validator = validate_hub.Validator(root)
            validator.data = self.snapshot_fixture_data(
                snapshot,
                evidence=True,
                authority_source_checks=source_checks,
            )
            validator.data["meta"]["captured_at_utc"] = captured
            validator.captured_at = datetime.strptime(
                captured, "%Y-%m-%dT%H:%M:%SZ"
            ).replace(tzinfo=UTC)
            validator.validate_authority_source_checks()
            validator.validate_snapshot_metadata()
            self.assertNotEqual(snapshot, self.run_git(root, "rev-parse", "HEAD"))
            self.assertEqual(validator.errors, [])

            stale = validate_hub.Validator(root)
            stale.data = self.snapshot_fixture_data(
                prior,
                evidence=True,
                authority_source_checks=source_checks,
            )
            stale.data["meta"]["captured_at_utc"] = captured
            stale.captured_at = datetime.strptime(
                captured, "%Y-%m-%dT%H:%M:%SZ"
            ).replace(tzinfo=UTC)
            stale.validate_authority_source_checks()
            stale.validate_snapshot_metadata()
            self.assertTrue(
                any(
                    "marker is absent" in error and "authority_snapshot_commit" in error
                    for error in stale.errors
                ),
                stale.errors,
            )

    def test_mapped_wave_advance_rejects_stale_hub(self) -> None:
        b03_rows = [
            ("B-02A", "done", "owner-a", "reviewer-a", []),
            ("B-03", "in_progress", "owner-b", "reviewer-b", ["B-02A"]),
            ("B-04", "todo", "owner-c", "reviewer-c", ["B-02A"]),
        ]
        stale_validator, _stale_view = self.authority_fixture(
            wave="B", predecessor="A", selected="B-03", rows=b03_rows
        )
        advanced_rows = [
            ("B-02A", "done", "owner-a", "reviewer-a", []),
            ("B-03", "done", "owner-b", "reviewer-b", ["B-02A"]),
            ("B-04", "in_progress", "owner-c", "reviewer-c", ["B-02A"]),
        ]
        _advanced_validator, advanced_view = self.authority_fixture(
            wave="B", predecessor="A", selected="B-04", rows=advanced_rows
        )
        stale_validator.validate_authority_view(advanced_view, "candidate HEAD")
        self.assertTrue(
            any("current.ticket" in error for error in stale_validator.errors),
            stale_validator.errors,
        )

    def test_hub_neutral_direct_push_uses_before_as_diff_base(self) -> None:
        validator = PushDiffValidator()
        validator.data = {"marker": "same"}
        validator.events = []
        validator.github_event = {"before": BASE_SHA}
        with patch.dict(os.environ, {"HUB_DIFF_BASE_SHA": ""}, clear=False):
            validator.collect_diff()
        validator.validate_structural_diff()
        self.assertEqual(validator.diff_base_sha, BASE_SHA)
        self.assertEqual(validator.changed_paths, {"carbon/runtime.py"})
        self.assertFalse(validator.semantic_data_changed)
        self.assertEqual(validator.errors, [])


if __name__ == "__main__":
    unittest.main()
