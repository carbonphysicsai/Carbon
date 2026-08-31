#!/usr/bin/env python3
"""Fast standard-library regression tests for Development Hub validation."""

from __future__ import annotations

import os
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

import validate_hub

BASE_SHA = "b86daa5d8b0f8b3e86bb82c2661f405747a200df"
REPOSITORY_URL = "https://github.com/carbonphysicsai/Carbon"
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


class ValidatorContractTests(unittest.TestCase):
    def test_collect_diff_includes_and_captures_deletions(self) -> None:
        validator = DiffValidator()
        validator.data = {}
        with patch.dict(os.environ, {"HUB_BASE_SHA": BASE_SHA}, clear=False):
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
        validator.data = {"current": {"wave": "B"}}
        expected = {
            ".agent/INVARIANTS.md": "SYSTEM/GOVERNANCE",
            ".agent/CODE_AUTHORITY.toml": "SYSTEM/AGENT-EXECUTION",
            "docs/context/SCIENTIFIC_REFERENCE_CANON_V4_MASTER.md": "SYSTEM/SCIENTIFIC-CANON",
            "docs/context/IMPLEMENTED_VS_SPECIFIED_CURRENT.md": "SYSTEM/MATURITY",
        }
        self.assertEqual(
            {path: validator.impact_ref(path) for path in expected}, expected
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


if __name__ == "__main__":
    unittest.main()
