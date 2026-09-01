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
                    "exact lowercase 40-character authority snapshot" in error
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
