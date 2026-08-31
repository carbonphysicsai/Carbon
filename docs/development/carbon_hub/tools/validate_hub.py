#!/usr/bin/env python3
"""Validate the Carbon Development Hub and its repository integration.

Only Python's standard library is used. The two JSON records are source; the
YAML indexes/templates and all presentation artifacts are validated output.
"""

from __future__ import annotations

import argparse
import contextlib
import importlib.util
import io
import json
import os
import re
import subprocess
import sys
import urllib.parse
from collections.abc import Iterable
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from typing import Any

HUB_RELATIVE = Path("docs/development/carbon_hub")
EXPECTED_WAVES = list("ABCDEFGHIJKLMN")
EXPECTED_TICKETS = [
    "A-1",
    "A0",
    "A1",
    "A2",
    "A3",
    "A4",
    "A5",
    "A6",
    "A7",
    "A8",
    "A9",
    "A10",
    "A11",
    "A12",
    "B-01",
    "B-01E",
    "B-02A",
    "B-02B",
    "B-02C",
    "B-03",
    "B-04",
    "B-05",
    "B-06",
    "B-07R",
    "B-07S",
    "B-07A",
    "B-07B",
    "B-07C",
    "B-07D1",
    "B-07D2",
    "B-07D3",
    "B-07E",
    "B-07F",
    "B-07G",
    "B-E1",
    "B-E2",
    "B-E3",
    "B-E4",
    "B-GATE",
]
EXPECTED_WAVE_A_DIRECT_DEPENDENCIES = {
    "A-1": [],
    "A0": ["A-1"],
    "A1": ["A0"],
    "A2": ["A0", "A1"],
    "A3": ["A0", "A1", "A2"],
    "A4": ["A0", "A1", "A3"],
    "A5": ["A0", "A1", "A2", "A3", "A4"],
    "A6": ["A5"],
    "A7": ["A2", "A3", "A4", "A5", "A6"],
    "A8": ["A4", "A5", "A7"],
    "A9": ["A2", "A3", "A6", "A7"],
    "A10": ["A3", "A5", "A6", "A7"],
    "A11": ["A5", "A6", "A7", "A8", "A9", "A10"],
    "A12": ["A4", "A5", "A6", "A7", "A8", "A9", "A10", "A11"],
}
EXPECTED_WAVE_A_CONTEXT_DEPENDENCIES = {"A9": ["A8"]}
EXPECTED_ROUTES = [
    "new-challenge",
    "model-architecture",
    "miner-prior",
    "reference-truth",
    "measurement-scoring",
    "protocol-defect",
    "commercial-private",
]
EXPECTED_MATURITY = [
    "specified",
    "implemented",
    "tested",
    "scientifically_qualified",
    "security_qualified",
    "network_qualified",
    "commercially_validated",
    "production_qualified",
]
WAVE_STATUSES = {"closed", "active", "planned"}
TICKET_STATUSES = {"todo", "in_progress", "done", "blocked"}
EVENT_TYPES = {"decision", "adjustment", "bug", "blocker", "risk", "evidence"}
BASELINE_EVENT_IDS = {"B-03-E1", "HUB-BUG-001", "HUB-ADJ-001"}
EVENT_STATUSES = {
    "proposed",
    "active",
    "blocked",
    "implemented",
    "superseded",
    "closed",
}
STATIC_SECTIONS = {
    "start",
    "current",
    "waves",
    "tickets",
    "changes",
    "decisions",
    "events",
    "maturity",
    "glossary",
    "sources",
    "publication",
}
AUTOLOAD_ATTRIBUTES = {
    "audio": {"src"},
    "body": {"background"},
    "embed": {"src"},
    "iframe": {"src", "srcdoc"},
    "img": {"src", "srcset"},
    "input": {"src"},
    "link": {"href"},
    "object": {"data"},
    "script": {"src"},
    "source": {"src", "srcset"},
    "track": {"src"},
    "video": {"src", "poster"},
}
CURRENT_POSITION_FIELDS = {
    "wave",
    "wave_title",
    "wave_status",
    "ticket",
    "ticket_title",
    "ticket_status",
    "stage",
    "closed_wave",
    "completed_b_tickets",
    "recent_dependencies",
    "other_completed_context",
    "downstream_handoffs",
    "parallel_context",
    "next_selected_ticket",
    "fail_closed",
    "maturity_ceiling",
    "decision_series_status",
    "technical_decision_route",
    "owner_decision_route",
    "decision_series",
}
VAGUE_DECLARATIONS = {
    "done",
    "complete",
    "completed",
    "handled",
    "hub updated",
    "no impact",
    "no hub impact",
    "none",
    "not needed",
    "not applicable",
    "updated",
    "yes",
}
KNOWN_SYSTEM_MAP_REFS = {
    "SYSTEM/AGENT-EXECUTION",
    "SYSTEM/CI",
    "SYSTEM/DEVELOPMENT-HUB",
    "SYSTEM/DEVELOPMENT-HUB/INTERACTIVE",
    "SYSTEM/DEVELOPMENT-HUB/VALIDATION",
    "SYSTEM/GOVERNANCE",
    "SYSTEM/MATURITY",
    "SYSTEM/PR-MAINTENANCE",
    "SYSTEM/PUBLICATION",
    "SYSTEM/SCIENTIFIC-CANON",
}


class SimpleYamlError(ValueError):
    """The file is outside the deliberately small hub YAML subset."""


def _yaml_scalar(text: str, line_number: int) -> Any:
    if text == "[]":
        return []
    if text == "{}":
        return {}
    if text in {"null", "Null", "NULL", "~"}:
        return None
    if text in {"true", "True", "TRUE"}:
        return True
    if text in {"false", "False", "FALSE"}:
        return False
    if text.startswith(('"', "'")):
        if not text.startswith('"'):
            raise SimpleYamlError(
                f"line {line_number}: only JSON-style double-quoted scalars are supported"
            )
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise SimpleYamlError(
                f"line {line_number}: invalid quoted scalar: {exc.msg}"
            ) from exc
    if re.fullmatch(r"-?(?:0|[1-9][0-9]*)", text):
        return int(text)
    if re.fullmatch(r"-?(?:0|[1-9][0-9]*)\.[0-9]+", text):
        return float(text)
    if not text:
        raise SimpleYamlError(f"line {line_number}: missing scalar")
    return text


def load_simple_yaml(path: Path) -> Any:
    """Parse the mapping/list/scalar subset emitted and consumed by the hub."""
    logical: list[tuple[int, str, int]] = []
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        prefix = raw[: len(raw) - len(raw.lstrip(" "))]
        if "\t" in prefix:
            raise SimpleYamlError(f"line {number}: tabs are not valid indentation")
        indent = len(prefix)
        if indent % 2:
            raise SimpleYamlError(
                f"line {number}: indentation must use two-space levels"
            )
        logical.append((indent, raw[indent:].rstrip(), number))
    if not logical:
        raise SimpleYamlError("document is empty")

    def parse_block(index: int, indent: int) -> tuple[Any, int]:
        if index >= len(logical) or logical[index][0] != indent:
            line = logical[index][2] if index < len(logical) else "EOF"
            raise SimpleYamlError(f"line {line}: expected indentation {indent}")
        first_content, first_number = logical[index][1], logical[index][2]
        if (
            first_content != "-"
            and not first_content.startswith("- ")
            and ":" not in first_content
        ):
            return _yaml_scalar(first_content, first_number), index + 1
        is_list = logical[index][1] == "-" or logical[index][1].startswith("- ")
        container: Any = [] if is_list else {}
        while index < len(logical):
            current_indent, content, number = logical[index]
            if current_indent < indent:
                break
            if current_indent > indent:
                raise SimpleYamlError(f"line {number}: unexpected indentation")
            current_is_list = content == "-" or content.startswith("- ")
            if current_is_list != is_list:
                raise SimpleYamlError(
                    f"line {number}: cannot mix mapping and list entries"
                )
            if is_list:
                value_text = content[1:].strip()
                if value_text:
                    container.append(_yaml_scalar(value_text, number))
                    index += 1
                else:
                    if index + 1 >= len(logical) or logical[index + 1][0] <= indent:
                        raise SimpleYamlError(f"line {number}: list item has no value")
                    value, index = parse_block(index + 1, logical[index + 1][0])
                    container.append(value)
                continue
            if ":" not in content:
                raise SimpleYamlError(f"line {number}: mapping entry has no colon")
            key, value_text = content.split(":", 1)
            key, value_text = key.strip(), value_text.strip()
            if not key or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", key):
                raise SimpleYamlError(f"line {number}: invalid mapping key {key!r}")
            if key in container:
                raise SimpleYamlError(f"line {number}: duplicate mapping key {key!r}")
            if value_text:
                container[key] = _yaml_scalar(value_text, number)
                index += 1
            else:
                if index + 1 >= len(logical) or logical[index + 1][0] <= indent:
                    raise SimpleYamlError(f"line {number}: mapping entry has no value")
                value, index = parse_block(index + 1, logical[index + 1][0])
                container[key] = value
        return container, index

    result, final_index = parse_block(0, logical[0][0])
    if logical[0][0] != 0:
        raise SimpleYamlError(
            f"line {logical[0][2]}: document root must not be indented"
        )
    if final_index != len(logical):
        raise SimpleYamlError(f"line {logical[final_index][2]}: unparsed content")
    return result


class HubHtmlParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tags: list[tuple[str, dict[str, str | None]]] = []
        self.ids: set[str] = set()
        self.duplicate_ids: set[str] = set()
        self.anchors: list[str] = []
        self.visible: list[str] = []
        self.script_blocks: list[str] = []
        self.doctype = False
        self._ignored: list[str] = []
        self._script_depth = 0

    def handle_decl(self, decl: str) -> None:
        self.doctype |= decl.lower().strip() == "doctype html"

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        values = {key.lower(): value for key, value in attrs}
        self.tags.append((tag, values))
        element_id = values.get("id")
        if element_id:
            if element_id in self.ids:
                self.duplicate_ids.add(element_id)
            self.ids.add(element_id)
        anchor_name = values.get("name") if tag == "a" else None
        if anchor_name:
            self.ids.add(anchor_name)
        if tag == "a" and values.get("href") is not None:
            self.anchors.append(values["href"] or "")
        if tag in {"script", "style", "template", "noscript"}:
            self._ignored.append(tag)
        if tag == "script":
            self._script_depth += 1
            self.script_blocks.append("")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "script" and self._script_depth:
            self._script_depth -= 1
        if self._ignored and self._ignored[-1] == tag:
            self._ignored.pop()

    def handle_data(self, data: str) -> None:
        if self._script_depth and self.script_blocks:
            self.script_blocks[-1] += data
        if not self._ignored and data.strip():
            self.visible.append(data)


def _unique(values: Iterable[Any]) -> bool:
    materialized = list(values)
    return len(materialized) == len(set(materialized))


def _clean_markdown(value: str) -> str:
    return " ".join(value.replace("`", "").replace("**", "").split())


def _inside(root: Path, candidate: Path) -> bool:
    try:
        candidate.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


class Validator:
    def __init__(self, repo_root: Path, *, skip_pr_contract: bool = False) -> None:
        self.repo_root = repo_root.resolve()
        self.hub_root = (self.repo_root / HUB_RELATIVE).resolve()
        self.skip_pr_contract = skip_pr_contract
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.data: dict[str, Any] = {}
        self.events: list[dict[str, Any]] = []
        self.event_bundle: dict[str, Any] = {}
        self.html_cache: dict[Path, HubHtmlParser] = {}
        self.github_event: dict[str, Any] | None = None
        self.changed_paths: set[str] | None = None
        self.deleted_paths: set[str] = set()
        self.new_event_ids: set[str] = set()
        self.base_sha: str | None = None
        self.base_hub_data: dict[str, Any] | None = None
        self.semantic_data_changed = False
        self.captured_at: datetime | None = None

    def fail(self, message: str) -> None:
        self.errors.append(message)

    def warn(self, message: str) -> None:
        self.warnings.append(message)

    def load_json_object(self, path: Path, label: str) -> dict[str, Any]:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            self.fail(f"{label} is not valid UTF-8 JSON: {exc}")
            return {}
        if not isinstance(value, dict):
            self.fail(f"{label} must contain a JSON object")
            return {}
        return value

    def require_keys(self, value: Any, keys: Iterable[str], label: str) -> bool:
        if not isinstance(value, dict):
            self.fail(f"{label} must be an object")
            return False
        missing = [key for key in keys if key not in value]
        if missing:
            self.fail(f"{label} is missing required keys: {', '.join(missing)}")
            return False
        return True

    @staticmethod
    def semantic_data_view(value: Any, path: tuple[str, ...] = ()) -> Any:
        """Remove snapshot-only pins while retaining orientation semantics."""
        if isinstance(value, dict):
            return {
                key: Validator.semantic_data_view(child, (*path, key))
                for key, child in value.items()
                if not (
                    path == ("meta",)
                    and key in {"captured_at_utc", "commit", "commit_short"}
                )
            }
        if isinstance(value, list):
            return [Validator.semantic_data_view(child, path) for child in value]
        if isinstance(value, str):
            return re.sub(
                r"(/(?:blob|commit)/)[0-9a-f]{40}(?=/|$)",
                r"\1{SNAPSHOT_COMMIT}",
                value,
            )
        return value

    def validate_https_url(self, value: Any, label: str) -> bool:
        if not isinstance(value, str) or not value:
            self.fail(f"{label} must be a non-empty HTTPS URL")
            return False
        decoded = urllib.parse.unquote(value)
        forbidden = {'"', "'", "%", "&", "<", ">", "`", "\\"}
        if (
            not value.isascii()
            or any(
                character.isspace() or ord(character) < 32 or ord(character) == 127
                for character in value
            )
            or any(character in forbidden for character in value)
            or any(
                character.isspace()
                or character in forbidden
                or ord(character) < 32
                or ord(character) == 127
                for character in decoded
            )
            or re.search(r"%(?![0-9A-Fa-f]{2})", value)
        ):
            self.fail(f"{label} contains unsafe URL characters")
            return False
        try:
            parsed = urllib.parse.urlsplit(value)
            port = parsed.port
        except ValueError:
            self.fail(f"{label} is not a structurally valid URL")
            return False
        if (
            parsed.scheme != "https"
            or parsed.hostname != "github.com"
            or port is not None
            or parsed.username is not None
            or parsed.password is not None
            or parsed.netloc != "github.com"
            or not (
                parsed.path == "/carbonphysicsai/Carbon"
                or parsed.path.startswith("/carbonphysicsai/Carbon/")
            )
            or parsed.query
            or not re.fullmatch(
                r"/[A-Za-z0-9._~/-]+", urllib.parse.unquote(parsed.path)
            )
            or (
                parsed.fragment
                and not re.fullmatch(
                    r"[A-Za-z0-9._~:/-]+", urllib.parse.unquote(parsed.fragment)
                )
            )
            or ".." in PurePosixPath(urllib.parse.unquote(parsed.path)).parts
        ):
            self.fail(
                f"{label} must be a credential-free https://github.com/carbonphysicsai/Carbon URL"
            )
            return False
        return True

    def validate_data_urls(self) -> None:
        meta = self.data.get("meta", {})
        if isinstance(meta, dict):
            repository = meta.get("repository")
            self.validate_https_url(repository, "meta.repository")
            if repository != "https://github.com/carbonphysicsai/Carbon":
                self.fail(
                    "meta.repository must exactly equal "
                    "https://github.com/carbonphysicsai/Carbon"
                )
        sources = self.data.get("sources", {})
        if not isinstance(sources, dict):
            self.fail("sources must be an object of labeled repository URLs")
        else:
            for source_id, source in sources.items():
                if not isinstance(source, dict):
                    self.fail(f"sources.{source_id} must be an object")
                    continue
                if (
                    not isinstance(source.get("label"), str)
                    or not source.get("label", "").strip()
                ):
                    self.fail(f"sources.{source_id}.label must be non-empty")
                self.validate_https_url(source.get("url"), f"sources.{source_id}.url")
        for collection in ("waves", "tickets", "change_paths"):
            records = self.data.get(collection, [])
            if not isinstance(records, list):
                continue
            for index, record in enumerate(records):
                if not isinstance(record, dict):
                    continue
                links = record.get("repo_links", [])
                if not isinstance(links, list):
                    self.fail(f"{collection}[{index}].repo_links must be a list")
                    continue
                for link_index, link in enumerate(links):
                    label = f"{collection}[{index}].repo_links[{link_index}]"
                    if not isinstance(link, dict):
                        self.fail(f"{label} must be an object")
                        continue
                    if (
                        not isinstance(link.get("label"), str)
                        or not link.get("label", "").strip()
                    ):
                        self.fail(f"{label}.label must be non-empty")
                    self.validate_https_url(link.get("url"), f"{label}.url")

    def load_sources(self) -> None:
        self.data = self.load_json_object(
            self.hub_root / "data/hub_data_v2.json", "data/hub_data_v2.json"
        )
        self.event_bundle = self.load_json_object(
            self.hub_root / "data/change_events.json", "data/change_events.json"
        )
        events = self.event_bundle.get("events", [])
        if not isinstance(events, list) or not all(
            isinstance(item, dict) for item in events
        ):
            self.fail("data/change_events.json must contain an events array of objects")
            self.events = []
        else:
            self.events = events
        if self.event_bundle.get("schema_version") != "1.0":
            self.fail("data/change_events.json schema_version must be '1.0'")

        for relative in ("data/hub_index_v2.yaml", "data/change_event_template.yaml"):
            try:
                parsed = load_simple_yaml(self.hub_root / relative)
            except (OSError, UnicodeError, SimpleYamlError) as exc:
                self.fail(f"{relative} is not valid hub-subset YAML: {exc}")
                continue
            if not isinstance(parsed, dict):
                self.fail(f"{relative} must contain a YAML mapping")
            elif relative.endswith("hub_index_v2.yaml"):
                self.validate_yaml_index(parsed)
            else:
                self.validate_event_template(parsed)

    def validate_yaml_index(self, index: dict[str, Any]) -> None:
        required = {
            "meta",
            "current",
            "waves",
            "tickets",
            "change_paths",
            "events",
            "event_schema",
        }
        missing = sorted(required - set(index))
        if missing:
            self.fail(f"data/hub_index_v2.yaml is missing keys: {', '.join(missing)}")
            return

        def source_ids(section: str, key: str) -> list[Any]:
            records = self.data.get(section, [])
            if not isinstance(records, list) or not all(
                isinstance(item, dict) for item in records
            ):
                return []
            return [item.get(key) for item in records]

        comparisons = (
            ("waves", "id", source_ids("waves", "id")),
            (
                "tickets",
                "id",
                source_ids("tickets", "id"),
            ),
            (
                "change_paths",
                "id",
                source_ids("change_paths", "id"),
            ),
            ("events", "event_id", [item.get("event_id") for item in self.events]),
        )
        for section, key, expected in comparisons:
            records = index.get(section)
            if not isinstance(records, list) or not all(
                isinstance(item, dict) for item in records
            ):
                self.fail(
                    f"data/hub_index_v2.yaml {section} must be a list of mappings"
                )
                continue
            if [item.get(key) for item in records] != expected:
                self.fail(
                    f"data/hub_index_v2.yaml {section} IDs do not match JSON source order"
                )

    def validate_event_template(self, template: dict[str, Any]) -> None:
        keys = {
            "map_ref",
            "event_type",
            "event_id",
            "owner_lane",
            "status",
            "summary",
            "primary_detail",
            "affects",
            "supersedes",
        }
        missing = sorted(keys - set(template))
        if missing:
            self.fail(
                f"data/change_event_template.yaml is missing keys: {', '.join(missing)}"
            )
        if template.get("event_type") not in EVENT_TYPES:
            self.fail(
                "data/change_event_template.yaml event_type default is outside the event enum"
            )
        if template.get("status") not in EVENT_STATUSES:
            self.fail(
                "data/change_event_template.yaml status default is outside the event enum"
            )
        if not isinstance(template.get("affects"), list):
            self.fail("data/change_event_template.yaml affects must be a list")

    def validate_model(self) -> None:
        top_keys = {
            "meta",
            "current",
            "sources",
            "authority_ceilings",
            "waves",
            "tickets",
            "maturity",
            "change_paths",
            "glossary",
            "event_schema",
        }
        if not self.require_keys(self.data, top_keys, "data/hub_data_v2.json"):
            return
        self.validate_data_urls()
        meta = self.data.get("meta")
        if self.require_keys(
            meta,
            (
                "title",
                "version",
                "captured_at_utc",
                "repository",
                "branch",
                "commit",
                "commit_short",
                "purpose",
                "authority_notice",
            ),
            "meta",
        ):
            if meta.get("version") != "2.1":
                self.fail("meta.version must be '2.1'")
            if not re.fullmatch(r"[0-9a-f]{40}", str(meta.get("commit", ""))):
                self.fail("meta.commit must be a lowercase 40-character Git commit ID")
            if str(meta.get("commit_short", "")) != str(meta.get("commit", ""))[:8]:
                self.fail(
                    "meta.commit_short must be the first eight characters of meta.commit"
                )
            captured_at = meta.get("captured_at_utc")
            if not isinstance(captured_at, str):
                self.fail("meta.captured_at_utc must be an exact UTC timestamp string")
            else:
                try:
                    self.captured_at = datetime.strptime(
                        captured_at, "%Y-%m-%dT%H:%M:%SZ"
                    ).replace(tzinfo=UTC)
                except ValueError:
                    self.fail(
                        "meta.captured_at_utc must use exact YYYY-MM-DDTHH:MM:SSZ format"
                    )
            if meta.get("branch") != "main":
                self.fail("meta.branch must identify the intended source branch 'main'")

        current = self.data.get("current")
        if self.require_keys(current, CURRENT_POSITION_FIELDS, "current"):
            for field in (
                "completed_b_tickets",
                "recent_dependencies",
                "other_completed_context",
                "downstream_handoffs",
                "parallel_context",
                "fail_closed",
                "decision_series",
            ):
                value = current.get(field)
                if not isinstance(value, list) or not all(
                    isinstance(item, str) and item.strip() for item in value
                ):
                    self.fail(f"current.{field} must be a list of non-empty strings")
                elif not _unique(value):
                    self.fail(f"current.{field} contains duplicate entries")

        waves = self.data.get("waves")
        tickets = self.data.get("tickets")
        routes = self.data.get("change_paths")
        maturity = self.data.get("maturity")
        if not isinstance(waves, list) or not all(
            isinstance(item, dict) for item in waves
        ):
            self.fail("waves must be a list of objects")
            waves = []
        if not isinstance(tickets, list) or not all(
            isinstance(item, dict) for item in tickets
        ):
            self.fail("tickets must be a list of objects")
            tickets = []
        if not isinstance(routes, list) or not all(
            isinstance(item, dict) for item in routes
        ):
            self.fail("change_paths must be a list of objects")
            routes = []
        if not isinstance(maturity, list) or not all(
            isinstance(item, dict) for item in maturity
        ):
            self.fail("maturity must be a list of objects")
            maturity = []

        wave_ids = [item.get("id") for item in waves]
        ticket_ids = [item.get("id") for item in tickets]
        route_ids = [item.get("id") for item in routes]
        maturity_ids = [item.get("id") for item in maturity]
        for label, actual, expected in (
            ("wave", wave_ids, EXPECTED_WAVES),
            ("ticket", ticket_ids, EXPECTED_TICKETS),
            ("change route", route_ids, EXPECTED_ROUTES),
            ("maturity", maturity_ids, EXPECTED_MATURITY),
        ):
            if not _unique(actual):
                self.fail(f"{label} IDs must be unique")
            if actual != expected:
                self.fail(f"Expected stable {label} IDs {expected}; found {actual}")
        if len(self.events) < len(BASELINE_EVENT_IDS):
            self.fail(
                f"Expected at least {len(BASELINE_EVENT_IDS)} change events; "
                f"found {len(self.events)}"
            )
        event_ids = {
            item.get("event_id")
            for item in self.events
            if isinstance(item.get("event_id"), str)
        }
        missing_baseline = sorted(BASELINE_EVENT_IDS - event_ids)
        if missing_baseline:
            self.fail(f"Baseline change events are missing: {missing_baseline}")

        wave_set, ticket_set = set(wave_ids), set(ticket_ids)
        for index, wave in enumerate(waves):
            label = f"waves[{index}]"
            if not self.require_keys(
                wave,
                (
                    "id",
                    "title",
                    "status",
                    "one_line",
                    "what",
                    "why",
                    "success",
                    "unlocks",
                    "does_not",
                    "objects",
                    "ticket_ids",
                    "predecessor",
                    "successor",
                    "authority_ceiling",
                    "repo_links",
                ),
                label,
            ):
                continue
            if wave.get("status") not in WAVE_STATUSES:
                self.fail(f"{label}.status has invalid value {wave.get('status')!r}")
            expected_predecessor = EXPECTED_WAVES[index - 1] if index else None
            expected_successor = (
                EXPECTED_WAVES[index + 1] if index + 1 < len(EXPECTED_WAVES) else None
            )
            if wave.get("predecessor") != expected_predecessor:
                self.fail(
                    f"{label}.predecessor must be {expected_predecessor!r}; "
                    f"found {wave.get('predecessor')!r}"
                )
            if wave.get("successor") != expected_successor:
                self.fail(
                    f"{label}.successor must be {expected_successor!r}; "
                    f"found {wave.get('successor')!r}"
                )
            if not isinstance(wave.get("authority_ceiling"), str) or not wave.get(
                "authority_ceiling"
            ):
                self.fail(f"{label}.authority_ceiling must be a non-empty string")
            captured = wave.get("ticket_ids")
            if not isinstance(captured, list) or any(
                item not in ticket_set for item in captured
            ):
                self.fail(f"{label}.ticket_ids must reference captured tickets")
            elif any(
                next(
                    (
                        ticket.get("wave")
                        for ticket in tickets
                        if ticket.get("id") == item
                    ),
                    None,
                )
                != wave.get("id")
                for item in captured
            ):
                self.fail(f"{label}.ticket_ids contains a ticket owned by another wave")
            explainer = (
                self.hub_root
                / f"explainers/waves/wave_{str(wave.get('id', '')).lower()}.md"
            )
            if not explainer.is_file():
                self.fail(
                    f"Missing generated wave explainer: {explainer.relative_to(self.hub_root).as_posix()}"
                )

        for index, ticket in enumerate(tickets):
            label = f"tickets[{index}]"
            required = (
                "id",
                "wave",
                "title",
                "status",
                "one_line",
                "what",
                "why",
                "adds",
                "does_not",
                "depends_on",
                "owner",
                "reviewer",
                "target",
                "repo_path",
                "repo_links",
                "unlocks",
            )
            if not self.require_keys(ticket, required, label):
                continue
            ticket_id = ticket.get("id")
            if ticket.get("wave") not in wave_set:
                self.fail(f"{ticket_id} references unknown wave {ticket.get('wave')!r}")
            if ticket.get("status") not in TICKET_STATUSES:
                self.fail(f"{ticket_id} has invalid status {ticket.get('status')!r}")
            for field in ("depends_on", "unlocks", "unlocks_context"):
                if field not in ticket:
                    continue
                refs = ticket.get(field)
                if not isinstance(refs, list) or not all(
                    isinstance(item, str) for item in refs
                ):
                    self.fail(f"{ticket_id}.{field} must be a list of ticket IDs")
                else:
                    unknown = [item for item in refs if item not in ticket_set]
                    if unknown:
                        self.fail(
                            f"{ticket_id}.{field} has unknown ticket references: {unknown}"
                        )
                    if not _unique(refs):
                        self.fail(f"{ticket_id}.{field} contains duplicate references")
            context = ticket.get("depends_on_context", [])
            if not isinstance(context, list) or not all(
                isinstance(item, str) and item for item in context
            ):
                self.fail(
                    f"{ticket_id}.depends_on_context must be a list of non-empty "
                    "ticket IDs or authority-context statements"
                )
            elif not _unique(context):
                self.fail(f"{ticket_id}.depends_on_context contains duplicates")
            if ticket_id in EXPECTED_WAVE_A_DIRECT_DEPENDENCIES:
                expected_direct = EXPECTED_WAVE_A_DIRECT_DEPENDENCIES[ticket_id]
                if ticket.get("depends_on") != expected_direct:
                    self.fail(
                        f"{ticket_id}.depends_on must preserve the ticket-owned "
                        f"direct contract dependencies {expected_direct!r}"
                    )
                expected_context = EXPECTED_WAVE_A_CONTEXT_DEPENDENCIES.get(
                    ticket_id, []
                )
                if ticket.get("depends_on_context", []) != expected_context:
                    self.fail(
                        f"{ticket_id}.depends_on_context must preserve the Wave-A "
                        f"sequencing context {expected_context!r}"
                    )
            self.validate_ticket_paths(ticket)

        for index, route in enumerate(routes):
            label = f"change_paths[{index}]"
            required = (
                "id",
                "title",
                "summary",
                "start",
                "waves",
                "tickets",
                "why_route",
                "decisions",
                "human_reserved",
                "repo_flow",
                "warning",
            )
            if not self.require_keys(route, required, label):
                continue
            for field, known in (("waves", wave_set), ("tickets", ticket_set)):
                refs = route.get(field)
                if not isinstance(refs, list) or not all(
                    isinstance(item, str) for item in refs
                ):
                    self.fail(f"{route.get('id')}.{field} must be a list")
                else:
                    unknown = [item for item in refs if item not in known]
                    if unknown:
                        self.fail(
                            f"{route.get('id')}.{field} has unknown references: {unknown}"
                        )
                    if not _unique(refs):
                        self.fail(
                            f"{route.get('id')}.{field} contains duplicate references"
                        )
        reverse_dependencies = {
            ticket_id: [
                candidate.get("id")
                for candidate in tickets
                if isinstance(candidate.get("depends_on"), list)
                and ticket_id in candidate.get("depends_on", [])
            ]
            for ticket_id in ticket_ids
        }
        for ticket in tickets:
            ticket_id = ticket.get("id")
            expected_unlocks = reverse_dependencies.get(ticket_id, [])
            if ticket.get("unlocks") != expected_unlocks:
                self.fail(
                    f"{ticket_id}.unlocks must be the ordered reverse dependency "
                    f"set {expected_unlocks!r}; found {ticket.get('unlocks')!r}"
                )
        for index, item in enumerate(maturity):
            self.require_keys(
                item,
                ("id", "label", "meaning", "proof", "not_implied"),
                f"maturity[{index}]",
            )
        self.validate_events(wave_set, ticket_set)

    def validate_ticket_paths(self, ticket: dict[str, Any]) -> None:
        ticket_id = str(ticket.get("id", "unknown"))
        raw = ticket.get("repo_path")
        if not isinstance(raw, str) or not raw:
            self.fail(f"{ticket_id}.repo_path must be a non-empty relative path")
            return
        pure = PurePosixPath(raw)
        if (
            pure.is_absolute()
            or "\\" in raw
            or ".." in pure.parts
            or pure.parts[:2] != (".agent", "tickets")
        ):
            self.fail(
                f"{ticket_id}.repo_path must remain under .agent/tickets: {raw!r}"
            )
            return
        target = (self.repo_root / Path(*pure.parts)).resolve()
        if not _inside(self.repo_root, target) or not target.is_file():
            self.fail(
                f"{ticket_id}.repo_path does not resolve to a repository file: {raw}"
            )
        name = ticket_id.lower().replace("-", "_") + ".md"
        if not (self.hub_root / "explainers/tickets" / name).is_file():
            self.fail(f"Missing generated ticket explainer: explainers/tickets/{name}")

    def valid_map_ref(
        self, value: Any, wave_set: set[Any], ticket_set: set[Any], label: str
    ) -> None:
        if not isinstance(value, str):
            self.fail(f"{label} must be a string map reference")
            return
        wave_match = re.fullmatch(r"WAVE-([A-N])(?:/([A-Z0-9-]+))?", value)
        if wave_match:
            wave, ticket = wave_match.groups()
            if wave not in wave_set:
                self.fail(f"{label} references unknown wave {wave}")
            if ticket and ticket not in ticket_set:
                self.fail(f"{label} references unknown ticket {ticket}")
            if ticket:
                actual = next(
                    (
                        item.get("wave")
                        for item in self.data.get("tickets", [])
                        if item.get("id") == ticket
                    ),
                    None,
                )
                if actual != wave:
                    self.fail(
                        f"{label} places {ticket} in Wave {wave}, but it belongs to Wave {actual}"
                    )
            return
        if re.fullmatch(r"SYSTEM/[A-Z0-9-]+(?:/[A-Z0-9-]+)*", value):
            return
        self.fail(
            f"{label} is not a stable WAVE-* or SYSTEM/* map reference: {value!r}"
        )

    def validate_events(self, wave_set: set[Any], ticket_set: set[Any]) -> None:
        ids = [item.get("event_id") for item in self.events]
        if not _unique(ids):
            self.fail("Change-event IDs must be unique")
        positions = {
            event_id: index
            for index, event_id in enumerate(ids)
            if isinstance(event_id, str)
        }
        for index, event in enumerate(self.events):
            label = f"events[{index}]"
            required = (
                "map_ref",
                "event_type",
                "event_id",
                "owner_lane",
                "status",
                "summary",
                "primary_detail",
                "affects",
                "supersedes",
            )
            if not self.require_keys(event, required, label):
                continue
            event_id = event.get("event_id")
            if not isinstance(event_id, str) or not re.fullmatch(
                r"[A-Z0-9]+(?:-[A-Z0-9]+)+", event_id
            ):
                self.fail(
                    f"{label}.event_id is not a stable uppercase identifier: {event_id!r}"
                )
            if event.get("event_type") not in EVENT_TYPES:
                self.fail(
                    f"{event_id}.event_type has invalid value {event.get('event_type')!r}"
                )
            if event.get("status") not in EVENT_STATUSES:
                self.fail(
                    f"{event_id}.status has invalid value {event.get('status')!r}"
                )
            owner_lane = event.get("owner_lane")
            if not isinstance(owner_lane, str) or not re.fullmatch(
                r"[a-z][a-z0-9_]{2,63}", owner_lane
            ):
                self.fail(
                    f"{event_id}.owner_lane must be a meaningful lower_snake_case lane"
                )
            summary = event.get("summary")
            if (
                not isinstance(summary, str)
                or len(summary.strip()) < 24
                or len(re.findall(r"[A-Za-z0-9]+", summary)) < 5
            ):
                self.fail(
                    f"{event_id}.summary must be a meaningful sentence of at least five words"
                )
            self.valid_map_ref(
                event.get("map_ref"), wave_set, ticket_set, f"{event_id}.map_ref"
            )
            affects = event.get("affects")
            if not isinstance(affects, list) or not all(
                isinstance(item, str) for item in affects
            ):
                self.fail(f"{event_id}.affects must be a list of map references")
            else:
                if not _unique(affects):
                    self.fail(f"{event_id}.affects contains duplicate references")
                for affected in affects:
                    self.valid_map_ref(
                        affected, wave_set, ticket_set, f"{event_id}.affects"
                    )
            supersedes = event.get("supersedes")
            if supersedes is not None and (
                not isinstance(supersedes, str)
                or not re.fullmatch(r"[A-Z0-9]+(?:-[A-Z0-9]+)+", supersedes)
            ):
                self.fail(f"{event_id}.supersedes must be null or a stable event ID")
            elif isinstance(supersedes, str):
                if supersedes not in positions:
                    self.fail(
                        f"{event_id}.supersedes references unknown event {supersedes}"
                    )
                elif positions[supersedes] >= index:
                    self.fail(
                        f"{event_id}.supersedes must reference an earlier immutable event"
                    )
            detail = event.get("primary_detail")
            if not isinstance(detail, str) or not detail.strip():
                self.fail(f"{event_id}.primary_detail must be a non-empty URL or path")
                continue
            if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", detail):
                self.validate_https_url(detail, f"{event_id}.primary_detail")
            else:
                target = self.resolve_repo_relative(
                    detail, f"{event_id}.primary_detail"
                )
                if target is not None and not target.is_file():
                    self.fail(f"{event_id}.primary_detail does not exist: {detail}")

    def resolve_repo_relative(self, raw: str, label: str) -> Path | None:
        if (
            not raw.isascii()
            or re.search(r"%(?![0-9A-Fa-f]{2})", raw)
            or any(
                character.isspace()
                or ord(character) < 32
                or ord(character) == 127
                or character in {'"', "'", "%", "&", "<", ">", "`", "\\"}
                for character in raw
            )
        ):
            self.fail(f"{label} contains unsafe repository-link characters")
            return None
        path_text, separator, fragment = raw.partition("#")
        decoded_path = urllib.parse.unquote(path_text)
        decoded_fragment = urllib.parse.unquote(fragment)
        if not re.fullmatch(r"[A-Za-z0-9._/-]+", decoded_path) or (
            separator and not re.fullmatch(r"[A-Za-z0-9._:-]+", decoded_fragment)
        ):
            self.fail(f"{label} is not a safe repository-relative link: {raw!r}")
            return None
        pure = PurePosixPath(decoded_path)
        if pure.is_absolute() or ".." in pure.parts:
            self.fail(f"{label} must be a confined repository-relative path: {raw!r}")
            return None
        target = (self.repo_root / Path(*pure.parts)).resolve()
        if not _inside(self.repo_root, target):
            self.fail(f"{label} escapes the repository root: {raw!r}")
            return None
        return target

    def parse_html(self, path: Path) -> tuple[str, HubHtmlParser] | None:
        try:
            raw = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            self.fail(
                f"Cannot read {path.relative_to(self.repo_root).as_posix()}: {exc}"
            )
            return None
        parser = HubHtmlParser()
        try:
            parser.feed(raw)
            parser.close()
        except (AssertionError, TypeError, ValueError) as exc:
            self.fail(
                f"Cannot parse {path.relative_to(self.repo_root).as_posix()} as HTML: {exc}"
            )
            return None
        self.html_cache[path.resolve()] = parser
        if parser.duplicate_ids:
            self.fail(f"{path.name} has duplicate IDs: {sorted(parser.duplicate_ids)}")
        if not parser.doctype:
            self.fail(f"{path.name} must declare <!doctype html>")
        return raw, parser

    def validate_no_autoload(self, path: Path, raw: str, parser: HubHtmlParser) -> None:
        for tag, attrs in parser.tags:
            for attribute in AUTOLOAD_ATTRIBUTES.get(tag, set()):
                value = attrs.get(attribute)
                inert_favicon = (
                    tag == "link"
                    and attribute == "href"
                    and value == "data:,"
                    and "icon" in str(attrs.get("rel", "")).lower().split()
                )
                if value and not inert_favicon:
                    self.fail(
                        f"{path.name} auto-loads a resource through <{tag} {attribute}=...>"
                    )
            if tag == "meta" and str(attrs.get("http-equiv", "")).lower() == "refresh":
                self.fail(f"{path.name} contains an automatic meta refresh")
            if re.search(
                r"(?:@import|url\s*\()", attrs.get("style") or "", flags=re.IGNORECASE
            ):
                self.fail(f"{path.name} contains an auto-loading inline CSS reference")
        for css in re.findall(
            r"<style\b[^>]*>(.*?)</style>", raw, flags=re.IGNORECASE | re.DOTALL
        ):
            if re.search(r"(?:@import|url\s*\()", css, flags=re.IGNORECASE):
                self.fail(f"{path.name} contains an auto-loading CSS reference")

    def validate_html_links(self, source: Path, parser: HubHtmlParser) -> None:
        for href in parser.anchors:
            if not href:
                self.fail(f"{source.name} contains an empty hyperlink")
                continue
            parsed = urllib.parse.urlsplit(href)
            if parsed.scheme:
                if parsed.scheme.lower() not in {"http", "https", "mailto"}:
                    self.fail(
                        f"{source.name} contains forbidden link scheme in {href!r}"
                    )
                continue
            if parsed.netloc or parsed.path.startswith("/") or "\\" in parsed.path:
                self.fail(f"{source.name} contains an unconfined local link: {href!r}")
                continue
            target = (
                (source.parent / urllib.parse.unquote(parsed.path)).resolve()
                if parsed.path
                else source.resolve()
            )
            if not _inside(self.repo_root, target):
                self.fail(f"{source.name} link escapes the repository root: {href!r}")
            elif not target.is_file():
                self.fail(f"{source.name} has a missing internal link target: {href!r}")
            elif (
                parsed.fragment
                and not parsed.fragment.startswith("/")
                and target.suffix.lower() in {".html", ".htm"}
            ):
                target_parser = self.html_cache.get(target)
                if target_parser is None:
                    parsed_target = self.parse_html(target)
                    target_parser = parsed_target[1] if parsed_target else None
                if (
                    target_parser is not None
                    and urllib.parse.unquote(parsed.fragment) not in target_parser.ids
                ):
                    self.fail(
                        f"{source.name} link has a missing anchor target: {href!r}"
                    )

    def validate_html(self) -> None:
        static_path = self.hub_root / "index.html"
        interactive_path = self.hub_root / "interactive.html"
        parsed_static = self.parse_html(static_path)
        if parsed_static:
            raw, parser = parsed_static
            tag_names = {tag for tag, _ in parser.tags}
            semantics = {
                "html",
                "head",
                "body",
                "header",
                "nav",
                "main",
                "section",
                "footer",
                "h1",
                "h2",
            }
            missing = sorted(semantics - tag_names)
            if missing:
                self.fail(
                    f"index.html is missing semantic elements: {', '.join(missing)}"
                )
            if parser.script_blocks or "script" in tag_names:
                self.fail("index.html must contain zero <script> elements")
            missing_sections = sorted(STATIC_SECTIONS - parser.ids)
            if missing_sections:
                self.fail(
                    f"index.html is missing required semantic section IDs: {', '.join(missing_sections)}"
                )
            if "main-content" not in parser.ids:
                self.fail("index.html is missing the #main-content landmark")
            visible = " ".join(" ".join(parser.visible).split())
            if len(visible) < 10_000:
                self.fail(
                    f"index.html has only {len(visible)} visible characters; expected at least 10000"
                )
            for phrase in (
                "Carbon Development Hub",
                "Wave A through Wave N",
                "Wave B",
                "B-03",
                "Eight maturity dimensions",
                "Protocol-change router",
            ):
                if phrase not in visible:
                    self.fail(f"index.html visible content is missing {phrase!r}")
            self.validate_no_autoload(static_path, raw, parser)
            self.validate_html_links(static_path, parser)

        parsed_interactive = self.parse_html(interactive_path)
        if parsed_interactive:
            raw, parser = parsed_interactive
            missing = sorted(
                {"view", "globalSearch", "sidebar", "menuBtn"} - parser.ids
            )
            if missing:
                self.fail(
                    f"interactive.html is missing application IDs: {', '.join(missing)}"
                )
            scripts = [block for block in parser.script_blocks if block.strip()]
            if not scripts:
                self.fail(
                    "interactive.html must contain a tested inline application script"
                )
            elif sum(len(block) for block in scripts) < 1_000:
                self.fail("interactive.html application script is unexpectedly small")
            if not re.search(
                r"<noscript\b[\s\S]*?href=[\"']index\.html[\"'][\s\S]*?</noscript>",
                raw,
                flags=re.IGNORECASE,
            ):
                self.fail("interactive.html must provide a noscript link to index.html")
            self.validate_no_autoload(interactive_path, raw, parser)
            self.validate_html_links(interactive_path, parser)

    def validate_renderer_drift(self) -> None:
        renderer_path = self.hub_root / "tools/render_hub.py"
        try:
            spec = importlib.util.spec_from_file_location(
                "carbon_hub_renderer_validation", renderer_path
            )
            if spec is None or spec.loader is None:
                raise ImportError("cannot construct module specification")
            renderer = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(renderer)
            if Path(renderer.ROOT).resolve() != self.hub_root:
                raise RuntimeError("renderer ROOT does not match the validated hub")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                result = renderer.run(
                    check=True,
                    data_path=(self.hub_root / "data/hub_data_v2.json").resolve(),
                    events_path=(self.hub_root / "data/change_events.json").resolve(),
                )
            if result != 0:
                self.fail(
                    "Generated-output drift detected by tools/render_hub.py --check: "
                    + " ".join(output.getvalue().split())
                )
        except SystemExit as exc:
            self.fail(f"Renderer drift check exited unexpectedly: {exc}")
        # The imported renderer is repository-controlled, but any import-time or
        # drift-check failure must become a validation error instead of a traceback.
        except Exception as exc:  # noqa: BLE001
            self.fail(f"Renderer drift check could not run safely: {exc}")

    def parse_wave_b_table(self, text: str) -> dict[str, dict[str, str]]:
        rows: dict[str, dict[str, str]] = {}
        headers: list[str] | None = None
        for line in text.splitlines():
            if not line.strip().startswith("|"):
                if headers and rows:
                    break
                continue
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            expected_head = [
                "ID",
                "Deliverable",
                "Status",
                "Evidence",
                "Driver",
                "Accountable reviewer",
                "Depends on",
            ]
            if cells[:7] == expected_head:
                headers = cells
                continue
            if headers is None or all(re.fullmatch(r":?-+:?", cell) for cell in cells):
                continue
            if len(cells) != len(headers):
                self.fail(f".agent/WAVE_B.md has a malformed board row: {line}")
                continue
            record = dict(zip(headers, cells))
            ticket_id = _clean_markdown(record["ID"])
            if ticket_id in rows:
                self.fail(f".agent/WAVE_B.md contains duplicate row {ticket_id}")
            rows[ticket_id] = record
        if headers is None:
            self.fail(".agent/WAVE_B.md is missing the controlling ticket table")
        return rows

    def validate_repository_authority(self) -> None:
        try:
            wave_text = (self.repo_root / ".agent/WAVE.md").read_text(encoding="utf-8")
            board_text = (self.repo_root / ".agent/WAVE_B.md").read_text(
                encoding="utf-8"
            )
        except (OSError, UnicodeError) as exc:
            self.fail(f"Cannot read current wave authority: {exc}")
            return
        wave_match = re.search(
            r"^\*\*Current wave:\*\*\s*(.+?)\s*$", wave_text, flags=re.MULTILINE
        )
        state_match = re.search(
            r"^\*\*State:\*\*\s*(.+?)\s*$", wave_text, flags=re.MULTILINE
        )
        ticket_match = re.search(
            r"^\*\*Selected ticket:\*\*\s*([A-Z0-9-]+)\s*[—-]+\s*`([^`]+)`\s*$",
            wave_text,
            flags=re.MULTILINE,
        )
        if not (wave_match and state_match and ticket_match):
            self.fail(
                ".agent/WAVE.md is missing parseable current wave, state, or selected ticket fields"
            )
            return
        authoritative_wave = _clean_markdown(wave_match.group(1))
        authoritative_state = _clean_markdown(state_match.group(1))
        authoritative_ticket, authoritative_status = ticket_match.groups()
        current = self.data.get("current", {})
        for label, actual, expected in (
            ("current.wave", current.get("wave"), authoritative_wave),
            ("current.wave_status", current.get("wave_status"), authoritative_state),
            ("current.ticket", current.get("ticket"), authoritative_ticket),
            (
                "current.ticket_status",
                current.get("ticket_status"),
                authoritative_status,
            ),
        ):
            if actual != expected:
                self.fail(
                    f"{label} is {actual!r}, but .agent/WAVE.md says {expected!r}"
                )
        wave_record = next(
            (
                item
                for item in self.data.get("waves", [])
                if item.get("id") == authoritative_wave
            ),
            None,
        )
        if wave_record is None or wave_record.get("status") != "active":
            self.fail(
                f"Current Wave {authoritative_wave} must be the one active hub wave"
            )
        active_waves = [
            item.get("id")
            for item in self.data.get("waves", [])
            if item.get("status") == "active"
        ]
        if active_waves != [authoritative_wave]:
            self.fail(
                f"Exactly the authoritative current wave must be active; found {active_waves}"
            )
        if wave_record is not None and current.get("wave_title") != wave_record.get(
            "title"
        ):
            self.fail(
                f"current.wave_title must match Wave {authoritative_wave}'s captured title"
            )
        closed_match = re.search(
            r"^\*\*Wave\s+([A-N]):\*\*\s*closed\b",
            wave_text,
            flags=re.MULTILINE | re.IGNORECASE,
        )
        if not closed_match:
            self.fail(".agent/WAVE.md is missing a parseable closed-wave field")
        elif current.get("closed_wave") != closed_match.group(1).upper():
            self.fail(
                f"current.closed_wave is {current.get('closed_wave')!r}; "
                f".agent/WAVE.md says {closed_match.group(1).upper()!r}"
            )
        else:
            closed_record = next(
                (
                    item
                    for item in self.data.get("waves", [])
                    if item.get("id") == current.get("closed_wave")
                ),
                None,
            )
            if closed_record is None or closed_record.get("status") != "closed":
                self.fail("current.closed_wave must identify a captured closed wave")

        board_rows = self.parse_wave_b_table(board_text)
        data_rows = {
            item.get("id"): item
            for item in self.data.get("tickets", [])
            if item.get("wave") == "B"
        }
        expected_b = [ticket for ticket in EXPECTED_TICKETS if ticket.startswith("B-")]
        if list(board_rows) != expected_b:
            self.fail(
                f"Wave B board row order/IDs differ from the stable hub set: {list(board_rows)}"
            )
        for ticket_id in expected_b:
            board, ticket = board_rows.get(ticket_id), data_rows.get(ticket_id)
            if board is None or ticket is None:
                continue
            for board_field, data_field in (
                ("Status", "status"),
                ("Driver", "owner"),
                ("Accountable reviewer", "reviewer"),
            ):
                expected = _clean_markdown(board[board_field])
                actual = _clean_markdown(str(ticket.get(data_field, "")))
                if actual != expected:
                    self.fail(
                        f"{ticket_id}.{data_field} is {actual!r}; Wave B board says {expected!r}"
                    )
            dependency_text = _clean_markdown(board["Depends on"])
            pieces = [piece.strip() for piece in dependency_text.split(",")]
            if pieces and all(piece in EXPECTED_TICKETS for piece in pieces):
                if ticket.get("depends_on") != pieces:
                    self.fail(
                        f"{ticket_id}.depends_on is {ticket.get('depends_on')!r}; Wave B board says {pieces!r}"
                    )
            elif ticket_id == "B-01":
                context = ticket.get("depends_on_context")
                if not isinstance(context, list) or not context:
                    self.fail(
                        "B-01 must preserve the board's prose activation dependency as depends_on_context"
                    )
            else:
                self.fail(
                    f"{ticket_id} has a non-structured dependency cell that cannot be checked exactly: {dependency_text!r}"
                )

        completed_b = [
            ticket_id
            for ticket_id, row in board_rows.items()
            if _clean_markdown(row.get("Status", "")) == "done"
        ]
        captured_completed = current.get("completed_b_tickets", [])
        if set(captured_completed) != set(completed_b):
            self.fail(
                "current.completed_b_tickets must contain exactly the Wave B board's "
                f"done tickets {completed_b!r}; found {captured_completed!r}"
            )

        selected = data_rows.get(authoritative_ticket)
        if selected is None:
            self.fail(
                f"Selected ticket {authoritative_ticket} is not captured in hub ticket data"
            )
            return
        if selected.get("status") != authoritative_status:
            self.fail(
                f"Selected ticket data status differs from .agent/WAVE.md: {selected.get('status')!r}"
            )
        if current.get("ticket_title") != selected.get("title"):
            self.fail("current.ticket_title must match the selected ticket title")
        stage_tokens = re.findall(r"[a-z0-9]+", str(current.get("stage", "")).lower())
        selected_stage_tokens = re.findall(
            r"[a-z0-9]+", str(selected.get("current_stage", "")).lower()
        )
        if not selected_stage_tokens or stage_tokens != selected_stage_tokens:
            self.fail(
                "current.stage must preserve the selected ticket's captured current_stage claim"
            )

        selected_dependencies = selected.get("depends_on", [])
        if current.get("recent_dependencies") != selected_dependencies:
            self.fail(
                "current.recent_dependencies must exactly match the selected ticket's "
                f"direct dependencies {selected_dependencies!r}"
            )
        incomplete_dependencies = [
            dependency
            for dependency in selected_dependencies
            if next(
                (
                    item.get("status")
                    for item in self.data.get("tickets", [])
                    if item.get("id") == dependency
                ),
                None,
            )
            != "done"
        ]
        if incomplete_dependencies:
            self.fail(
                f"Selected ticket has non-done direct dependencies: {incomplete_dependencies}"
            )
        other_expected = set(completed_b) - set(selected_dependencies)
        if set(current.get("other_completed_context", [])) != other_expected:
            self.fail(
                "current.other_completed_context must contain the other completed "
                f"Wave B tickets {sorted(other_expected)!r}"
            )
        if current.get("downstream_handoffs") != selected.get("unlocks"):
            self.fail(
                "current.downstream_handoffs must exactly match the selected ticket's "
                f"reverse dependencies {selected.get('unlocks')!r}"
            )

        known_tickets = {
            str(item.get("id")): item for item in self.data.get("tickets", [])
        }
        parallel_refs: set[str] = set()
        for statement in current.get("parallel_context", []):
            parallel_refs.update(
                ticket_id
                for ticket_id in known_tickets
                if re.search(
                    rf"(?<![A-Z0-9-]){re.escape(ticket_id)}(?![A-Z0-9-])",
                    statement,
                )
            )
        if not parallel_refs:
            self.fail("current.parallel_context must name at least one captured ticket")
        for parallel_id in sorted(parallel_refs):
            record = known_tickets[parallel_id]
            if parallel_id == authoritative_ticket or record.get("status") != "todo":
                self.fail(
                    f"current.parallel_context may only name unselected todo tickets; found {parallel_id}"
                )
            unresolved = [
                dependency
                for dependency in record.get("depends_on", [])
                if known_tickets.get(dependency, {}).get("status") != "done"
            ]
            if unresolved:
                self.fail(
                    f"current.parallel_context names {parallel_id} with unresolved dependencies {unresolved}"
                )

        next_match = re.search(
            r"^\*\*Next selected ticket:\*\*\s*([A-Z0-9-]+|none)\s*$",
            wave_text,
            flags=re.MULTILINE | re.IGNORECASE,
        )
        expected_next = (
            None
            if next_match is None or next_match.group(1).lower() == "none"
            else next_match.group(1).upper()
        )
        if current.get("next_selected_ticket") != expected_next:
            self.fail(
                f"current.next_selected_ticket must be {expected_next!r} from .agent/WAVE.md"
            )

        repository_url = str(self.data.get("meta", {}).get("repository", "")).rstrip(
            "/"
        )
        if current.get("technical_decision_route") != f"{repository_url}/issues/42":
            self.fail(
                "current.technical_decision_route must be the repository's issue #42"
            )
        if current.get("owner_decision_route") != f"{repository_url}/issues/41":
            self.fail("current.owner_decision_route must be the repository's issue #41")

        maturity_text = str(current.get("maturity_ceiling", ""))
        maturity_lower = maturity_text.lower()
        if not (
            "specified" in maturity_lower
            and "runtime implementation" in maturity_lower
            and (
                "not yet captured" in maturity_lower or "not captured" in maturity_lower
            )
            and "qualification" in maturity_lower
            and "unearned" in maturity_lower
        ):
            self.fail(
                "current.maturity_ceiling must preserve the selected ticket's "
                "SPECIFIED-only, runtime-unimplemented, qualification-unearned ceiling"
            )
        fail_closed_text = " ".join(current.get("fail_closed", [])).lower()
        for marker in ("human_input", "scientific", "security", "production", "live"):
            if marker not in fail_closed_text:
                self.fail(
                    f"current.fail_closed is missing required boundary marker {marker!r}"
                )

        try:
            decisions_text = (self.repo_root / ".agent/DECISIONS.md").read_text(
                encoding="utf-8"
            )
        except (OSError, UnicodeError) as exc:
            self.fail(
                f"Cannot read .agent/DECISIONS.md for current decision series: {exc}"
            )
            decisions_text = ""
        decision_series = current.get("decision_series", [])
        for decision_id in decision_series:
            if not str(decision_id).startswith(f"{authoritative_ticket}-D"):
                self.fail(
                    f"current.decision_series entry {decision_id!r} does not belong to the selected ticket"
                )
            if not re.search(
                rf"^##\s+.*\b{re.escape(str(decision_id))}:?\s*",
                decisions_text,
                flags=re.MULTILINE,
            ):
                self.fail(
                    f"current.decision_series entry {decision_id!r} has no decision-log heading"
                )
        series_status = str(current.get("decision_series_status", ""))
        if decision_series and (
            decision_series[0] not in series_status
            or decision_series[-1] not in series_status
            or "runtime implementation" not in series_status.lower()
        ):
            self.fail(
                "current.decision_series_status must identify the series range and runtime boundary"
            )
        source_path = self.repo_root / str(selected.get("repo_path", ""))
        try:
            source_text = source_path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            self.fail(f"Cannot read selected ticket source {source_path}: {exc}")
            return
        source_status = re.search(
            r"^\*\*Status:\*\*\s*`?([a-z_]+)`?\s*$", source_text, flags=re.MULTILINE
        )
        if not source_status:
            self.fail(
                f"Selected ticket source {selected.get('repo_path')} has no parseable Status field"
            )
        elif source_status.group(1) != authoritative_status:
            self.fail(
                f"Selected ticket source status is {source_status.group(1)!r}; current authority says {authoritative_status!r}"
            )

    def validate_root_integration(self) -> None:
        checks = {
            "README.md": (
                "## Development Hub",
                "docs/development/carbon_hub/index.html",
                "docs/development/carbon_hub/orientation/AGENT_MAINTENANCE_CONTRACT.md",
            ),
            "AGENTS.md": (
                "docs/development/carbon_hub/orientation/AGENT_MAINTENANCE_CONTRACT.md",
                "map_ref",
                "hub impact",
            ),
            "agent_pack/EXECUTION_PROTOCOL.md": (
                "docs/development/carbon_hub/orientation/AGENT_MAINTENANCE_CONTRACT.md",
                "map_ref",
                "hub impact",
            ),
            f"{HUB_RELATIVE.as_posix()}/AGENTS.md": (
                "Carbon Development Hub — scoped agent instructions",
                "data/hub_data_v2.json",
                "data/change_events.json",
                "Generated files — do not hand-edit",
                "validate_hub.py --repo-root .",
            ),
        }
        for relative, markers in checks.items():
            path = self.repo_root / relative
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeError) as exc:
                self.fail(
                    f"Cannot read required Development Hub integration file {relative}: {exc}"
                )
                continue
            missing = [
                marker for marker in markers if marker.lower() not in text.lower()
            ]
            if missing:
                self.fail(
                    f"{relative} is missing Development Hub integration markers: {missing}"
                )

    def git(
        self, *args: str, allow_failure: bool = False
    ) -> subprocess.CompletedProcess[str]:
        command = [
            "git",
            "-c",
            f"safe.directory={self.repo_root.as_posix()}",
            "-C",
            str(self.repo_root),
            *args,
        ]
        result = subprocess.run(
            command,
            check=False,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
        )
        if result.returncode and not allow_failure:
            raise RuntimeError(
                result.stderr.strip()
                or result.stdout.strip()
                or f"git exited {result.returncode}"
            )
        return result

    def validate_snapshot_metadata(self) -> None:
        meta = self.data.get("meta", {})
        commit = str(meta.get("commit", ""))
        if not re.fullmatch(r"[0-9a-f]{40}", commit):
            return
        try:
            resolved = self.git("rev-parse", "--verify", f"{commit}^{{commit}}")
            resolved_commit = resolved.stdout.strip().lower()
            if resolved_commit != commit:
                self.fail(
                    f"meta.commit resolves to {resolved_commit}, not the recorded exact commit {commit}"
                )
                return
            show = self.git("show", "-s", "--format=%cI%n%s", commit)
            lines = show.stdout.splitlines()
            if len(lines) < 2:
                self.fail("Could not read snapshot commit timestamp and subject")
                return
            commit_time = datetime.fromisoformat(lines[0]).astimezone(UTC)
            subject = lines[1]
        except (RuntimeError, ValueError) as exc:
            self.fail(f"Cannot resolve meta.commit as a repository commit: {exc}")
            return

        if self.captured_at is not None and self.captured_at < commit_time:
            self.fail(
                "meta.captured_at_utc predates the recorded snapshot commit's commit time"
            )
        if self.captured_at is not None and self.captured_at > datetime.now(
            UTC
        ).replace(microsecond=0):
            self.fail("meta.captured_at_utc cannot be in the future")

        playbook_path = self.hub_root / "orientation/HUB_UPDATE_PLAYBOOK.md"
        try:
            playbook = playbook_path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            self.fail(f"Cannot read the Hub snapshot playbook: {exc}")
        else:
            expected_line = (
                f"Current snapshot: `{commit}`, reconciled "
                f"{meta.get('captured_at_utc')}."
            )
            if expected_line not in playbook:
                self.fail(
                    "HUB_UPDATE_PLAYBOOK.md snapshot commit/time does not match metadata"
                )

        serialized = json.dumps(self.data, ensure_ascii=True, sort_keys=True)
        pinned_shas = set(re.findall(r"/blob/([0-9a-f]{40})/", serialized))
        if pinned_shas != {commit}:
            self.fail(
                f"All pinned Carbon blob URLs must use meta.commit; found {sorted(pinned_shas)}"
            )

        comparison_sha = self.base_sha
        comparison_label = "HUB_BASE_SHA"
        if comparison_sha is None:
            for ref in ("refs/remotes/origin/main", "refs/heads/main"):
                candidate = self.git(
                    "rev-parse", "--verify", f"{ref}^{{commit}}", allow_failure=True
                )
                if candidate.returncode == 0:
                    comparison_sha = candidate.stdout.strip().lower()
                    comparison_label = ref
                    break
        if comparison_sha is not None:
            ancestry = self.git(
                "merge-base",
                "--is-ancestor",
                commit,
                comparison_sha,
                allow_failure=True,
            )
            if ancestry.returncode == 1:
                self.fail(
                    f"meta.commit is not an ancestor of the intended source base {comparison_label}"
                )
            elif ancestry.returncode != 0:
                self.fail(
                    f"Could not establish snapshot ancestry against {comparison_label}"
                )

        structural = bool(
            self.changed_paths
            and any(self.impact_ref(path) is not None for path in self.changed_paths)
        )
        if (
            self.base_sha is not None
            and (self.semantic_data_changed or structural)
            and commit != self.base_sha
        ):
            self.fail(
                "Semantic/structural hub reconciliation must pin meta.commit to "
                "the exact HUB_BASE_SHA source base"
            )

        merged_pr = re.search(r"Merge pull request #(\d+)\b", subject)
        stage_pr = re.search(
            r"\bPR #(\d+)\b", str(self.data.get("current", {}).get("stage", ""))
        )
        if merged_pr and stage_pr and merged_pr.group(1) != stage_pr.group(1):
            self.fail(
                "current.stage PR evidence does not match the recorded snapshot merge commit"
            )

    def load_github_event(self) -> None:
        event_path = os.environ.get("GITHUB_EVENT_PATH")
        if not event_path:
            return
        try:
            value = json.loads(Path(event_path).read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            self.fail(f"GITHUB_EVENT_PATH is not readable JSON: {exc}")
            return
        if not isinstance(value, dict):
            self.fail("GITHUB_EVENT_PATH must contain a JSON object")
        else:
            self.github_event = value

    def collect_diff(self) -> None:
        base = os.environ.get("HUB_BASE_SHA")
        if not base and self.github_event:
            base = (
                str(
                    self.github_event.get("pull_request", {})
                    .get("base", {})
                    .get("sha", "")
                )
                or None
            )
        if not base:
            self.warn(
                "HUB_BASE_SHA is unavailable; structural diff/change-event coverage was skipped"
            )
            return
        if not re.fullmatch(r"[0-9a-fA-F]{7,64}", base):
            self.fail("HUB_BASE_SHA must be a hexadecimal Git object ID")
            return
        try:
            resolved_base = self.git("rev-parse", "--verify", f"{base}^{{commit}}")
            self.base_sha = resolved_base.stdout.strip().lower()
            changed: set[str] = set()
            commands = (
                (
                    "diff",
                    "--name-only",
                    "-z",
                    "--diff-filter=ACDMRTUXB",
                    f"{self.base_sha}...HEAD",
                ),
                ("diff", "--name-only", "-z", "--diff-filter=ACDMRTUXB"),
                (
                    "diff",
                    "--cached",
                    "--name-only",
                    "-z",
                    "--diff-filter=ACDMRTUXB",
                ),
                ("ls-files", "--others", "--exclude-standard", "-z"),
            )
            for command in commands:
                result = self.git(*command)
                changed.update(
                    line.strip().replace("\\", "/")
                    for line in result.stdout.split("\0")
                    if line.strip()
                )
            self.changed_paths = changed
            deletion_commands = (
                (
                    "diff",
                    "--name-only",
                    "-z",
                    "--diff-filter=D",
                    f"{self.base_sha}...HEAD",
                ),
                ("diff", "--name-only", "-z", "--diff-filter=D"),
                ("diff", "--cached", "--name-only", "-z", "--diff-filter=D"),
            )
            for command in deletion_commands:
                result = self.git(*command)
                self.deleted_paths.update(
                    line.strip().replace("\\", "/")
                    for line in result.stdout.split("\0")
                    if line.strip()
                )
            self.changed_paths.update(self.deleted_paths)
            prior = self.git(
                "show",
                f"{self.base_sha}:{HUB_RELATIVE.as_posix()}/data/change_events.json",
                allow_failure=True,
            )
            prior_events: dict[str, dict[str, Any]] = {}
            if prior.returncode == 0:
                try:
                    prior_value = json.loads(prior.stdout)
                    prior_events = {
                        str(item["event_id"]): item
                        for item in prior_value.get("events", [])
                        if isinstance(item, dict)
                        and isinstance(item.get("event_id"), str)
                    }
                except (json.JSONDecodeError, AttributeError):
                    self.fail("Base change_events.json is not valid JSON")
            current_events = {
                str(item["event_id"]): item
                for item in self.events
                if isinstance(item.get("event_id"), str)
            }
            prior_ids = set(prior_events)
            current_ids = set(current_events)
            removed_ids = sorted(prior_ids - current_ids)
            if removed_ids:
                self.fail(
                    "Historical change-event IDs are immutable; missing from current "
                    f"ledger: {removed_ids}"
                )
            rewritten_ids = sorted(
                event_id
                for event_id in prior_ids & current_ids
                if prior_events[event_id] != current_events[event_id]
            )
            if rewritten_ids:
                self.fail(
                    "Historical change events are immutable; append a superseding "
                    f"event instead of rewriting: {rewritten_ids}"
                )
            self.new_event_ids = current_ids - prior_ids

            prior_data = self.git(
                "show",
                f"{self.base_sha}:{HUB_RELATIVE.as_posix()}/data/hub_data_v2.json",
                allow_failure=True,
            )
            if prior_data.returncode == 0:
                try:
                    parsed_base_data = json.loads(prior_data.stdout)
                except json.JSONDecodeError:
                    self.fail("Base hub_data_v2.json is not valid JSON")
                else:
                    if not isinstance(parsed_base_data, dict):
                        self.fail("Base hub_data_v2.json must contain an object")
                    else:
                        self.base_hub_data = parsed_base_data
            self.semantic_data_changed = (
                self.base_hub_data is None
                or self.semantic_data_view(self.base_hub_data)
                != self.semantic_data_view(self.data)
            )
        except RuntimeError as exc:
            self.fail(f"Cannot evaluate HUB_BASE_SHA structural diff: {exc}")

    def impact_ref(self, path: str) -> str | None:
        current_wave = str(self.data.get("current", {}).get("wave", "B"))
        if path in {"AGENTS.md", "agent_pack/EXECUTION_PROTOCOL.md"}:
            return "SYSTEM/AGENT-EXECUTION"
        if path in {"CONSTITUTION.md", ".agent/INVARIANTS.md"}:
            return "SYSTEM/GOVERNANCE"
        if path == ".agent/CODE_AUTHORITY.toml":
            return "SYSTEM/AGENT-EXECUTION"
        if path == "docs/context/SCIENTIFIC_REFERENCE_CANON_V4_MASTER.md":
            return "SYSTEM/SCIENTIFIC-CANON"
        if path == "docs/context/IMPLEMENTED_VS_SPECIFIED_CURRENT.md":
            return "SYSTEM/MATURITY"
        # Hub presentation, tools, and generated artifacts are not structural by
        # path alone. Their PR declaration still records impact, while a material
        # repository-authority change below requires source data plus an event.
        if path == "README.md" or path.startswith(f"{HUB_RELATIVE.as_posix()}/"):
            return None
        if path == ".github/pull_request_template.md":
            return "SYSTEM/PR-MAINTENANCE"
        if path.startswith(".github/workflows/"):
            return "SYSTEM/PUBLICATION" if "page" in path.lower() else "SYSTEM/CI"
        if path == ".agent/WAVE.md":
            return f"WAVE-{current_wave}"
        match = re.fullmatch(r"\.agent/WAVE_([A-N])\.md", path)
        if match:
            return f"WAVE-{match.group(1)}"
        if path.startswith((".agent/tickets/", ".agent/plans/", ".agent/evidence/")):
            name = Path(path).name.upper()
            for ticket in sorted(EXPECTED_TICKETS, key=len, reverse=True):
                if name == ticket or name.startswith((ticket + "_", ticket + ".")):
                    wave = next(
                        (
                            item.get("wave")
                            for item in self.data.get("tickets", [])
                            if item.get("id") == ticket
                        ),
                        ticket[0],
                    )
                    return f"WAVE-{wave}/{ticket}"
            return f"WAVE-{current_wave}"
        if path in {
            ".agent/DECISIONS.md",
            ".agent/DELEGATED_DECISION_PROTOCOL.md",
        } or path.startswith("Design_Specs/"):
            return f"WAVE-{current_wave}"
        if path.startswith(("Business/", "docs/publications/")):
            return "WAVE-G"
        return None

    @staticmethod
    def ref_covered(expected: str, actual: set[str]) -> bool:
        return any(
            value == expected
            or value.startswith(expected + "/")
            or expected.startswith(value + "/")
            for value in actual
        )

    def validate_structural_diff(self) -> None:
        if self.changed_paths is None:
            return
        impacts = {
            path: ref
            for path in self.changed_paths
            if (ref := self.impact_ref(path)) is not None
        }
        if not impacts and not self.semantic_data_changed:
            return
        hub_data_path = f"{HUB_RELATIVE.as_posix()}/data/hub_data_v2.json"
        events_path = f"{HUB_RELATIVE.as_posix()}/data/change_events.json"
        if impacts and hub_data_path not in self.changed_paths:
            self.fail(
                "Structural repository changes require an updated data/hub_data_v2.json"
            )
        if impacts and events_path not in self.changed_paths:
            self.fail(
                "Structural repository changes require an updated data/change_events.json"
            )
        if self.semantic_data_changed and hub_data_path not in self.changed_paths:
            self.fail(
                "Semantic hub-data reconciliation differs from HUB_BASE_SHA but "
                "data/hub_data_v2.json is not in the diff"
            )
        if self.semantic_data_changed and events_path not in self.changed_paths:
            self.fail(
                "Semantic hub_data_v2.json changes require an appended immutable "
                "change event"
            )
        if not self.new_event_ids:
            self.fail(
                "Structural or semantic hub changes require at least one new immutable "
                "change event relative to HUB_BASE_SHA"
            )
            return
        new_events = [
            item for item in self.events if item.get("event_id") in self.new_event_ids
        ]
        covered = {str(item.get("map_ref")) for item in new_events}
        covered.update(
            str(ref)
            for item in new_events
            for ref in item.get("affects", [])
            if isinstance(ref, str)
        )
        missing = sorted(
            {ref for ref in impacts.values() if not self.ref_covered(ref, covered)}
        )
        if missing:
            self.fail(
                f"New change events do not cover structural map references: {missing}"
            )

    def validate_pr_declaration(self) -> None:
        if self.skip_pr_contract:
            return
        if self.github_event is None:
            self.warn(
                "GITHUB_EVENT_PATH is unavailable; PR hub-impact declaration was skipped"
            )
            return
        pull_request = self.github_event.get("pull_request")
        if not isinstance(pull_request, dict):
            self.warn(
                "GitHub event is not a pull_request event; PR hub-impact declaration was skipped"
            )
            return
        body = pull_request.get("body")
        if not isinstance(body, str):
            self.fail(
                "Pull request body is missing; exactly one completed hub-impact declaration is required"
            )
            return
        token_count = len(
            re.findall(r"\b(?:HUB_UPDATE_REQUIRED|HUB_IMPACT_NONE)\s*:", body)
        )
        matches = re.findall(
            r"^\s*(HUB_UPDATE_REQUIRED|HUB_IMPACT_NONE)\s*:\s*(.*?)\s*$",
            body,
            flags=re.MULTILINE,
        )
        if token_count != 1 or len(matches) != 1:
            self.fail(
                "PR body must contain exactly one declaration line: HUB_UPDATE_REQUIRED: ... or HUB_IMPACT_NONE: ..."
            )
            return
        kind, detail = matches[0]
        normalized_detail = " ".join(detail.lower().split())
        placeholder = not detail or bool(
            re.fullmatch(
                r"(?:TODO|TBD|N/?A|NONE|<.*>|\[.*\]|<!--.*-->)",
                detail.strip(),
                flags=re.IGNORECASE,
            )
        )
        vague = (
            normalized_detail in VAGUE_DECLARATIONS
            or len(detail.strip()) < 20
            or len(re.findall(r"[A-Za-z0-9]+", detail)) < 4
        )
        if placeholder or vague:
            self.fail(
                f"{kind} declaration must include a specific, non-placeholder explanation"
            )
        if kind == "HUB_UPDATE_REQUIRED" and re.search(
            r"\b(?:updated|handled|completed)\s+as\s+requested\b",
            detail,
            flags=re.IGNORECASE,
        ):
            self.fail(
                "HUB_UPDATE_REQUIRED must describe concrete coverage, not only state "
                "that an update was requested"
            )
        if self.changed_paths is None:
            return
        structural = sorted(
            path for path in self.changed_paths if self.impact_ref(path) is not None
        )
        hub_data_path = f"{HUB_RELATIVE.as_posix()}/data/hub_data_v2.json"
        events_path = f"{HUB_RELATIVE.as_posix()}/data/change_events.json"
        source_records = {hub_data_path, events_path}
        if kind == "HUB_IMPACT_NONE" and structural:
            self.fail(
                "HUB_IMPACT_NONE is forbidden when these structural paths change: "
                + ", ".join(structural)
            )
        if kind == "HUB_IMPACT_NONE" and source_records & self.changed_paths:
            self.fail(
                "HUB_IMPACT_NONE cannot accompany changes to the hub's semantic "
                "data or event source records"
            )
        if kind == "HUB_IMPACT_NONE":
            reason_markers = re.compile(
                r"\b(?:because|only|limited to|unchanged|does not|no change|"
                r"outside|presentation|formatting|styling|typo|tests?|comments?|"
                r"generated|implementation detail)\b",
                flags=re.IGNORECASE,
            )
            if (
                len(detail.strip()) < 40
                or len(re.findall(r"[A-Za-z0-9]+", detail)) < 7
                or not reason_markers.search(detail)
            ):
                self.fail(
                    "HUB_IMPACT_NONE must state a concrete scoped reason the hub "
                    "semantics remain accurate"
                )
        if kind == "HUB_UPDATE_REQUIRED":
            hub_changes = {
                path
                for path in self.changed_paths
                if path.startswith(f"{HUB_RELATIVE.as_posix()}/")
            }
            if not hub_changes:
                self.fail(
                    "HUB_UPDATE_REQUIRED must include at least one Development Hub file"
                )
            declared_map_refs = set(
                re.findall(
                    r"\b(?:WAVE-[A-N](?:/[A-Z0-9-]+)?|SYSTEM/[A-Z0-9-]+(?:/[A-Z0-9-]+)*)\b",
                    detail,
                )
            )
            declared_event_ids = {
                str(event.get("event_id"))
                for event in self.events
                if isinstance(event.get("event_id"), str)
                and re.search(
                    rf"(?<![A-Z0-9-]){re.escape(str(event.get('event_id')))}(?![A-Z0-9-])",
                    detail,
                )
            }
            raw_declared_hub_paths = re.findall(
                r"(?:docs/development/carbon_hub/)?(?:data/)?(?:hub_data_v2\.json|"
                r"change_events\.json|change_event_template\.yaml)|"
                r"docs/development/carbon_hub/[A-Za-z0-9_./-]+",
                detail,
            )
            declared_hub_paths: set[str] = set()
            for raw_path in raw_declared_hub_paths:
                path = raw_path.rstrip(".,;:)")
                if path.startswith(f"{HUB_RELATIVE.as_posix()}/"):
                    declared_hub_paths.add(path)
                elif path.startswith("data/"):
                    declared_hub_paths.add(f"{HUB_RELATIVE.as_posix()}/{path}")
                else:
                    declared_hub_paths.add(f"{HUB_RELATIVE.as_posix()}/data/{path}")
            declared_new_event_ids = declared_event_ids & self.new_event_ids
            initial_integration_declaration = (
                self.base_hub_data is None
                and source_records <= self.changed_paths
                and "SYSTEM/DEVELOPMENT-HUB" in declared_map_refs
                and re.search(r"\bsource data\b", detail, flags=re.IGNORECASE)
                is not None
                and re.search(r"\bchange events\b", detail, flags=re.IGNORECASE)
                is not None
            )
            known_map_refs = set(KNOWN_SYSTEM_MAP_REFS)
            known_map_refs.update(
                f"WAVE-{item.get('id')}"
                for item in self.data.get("waves", [])
                if isinstance(item, dict) and isinstance(item.get("id"), str)
            )
            known_map_refs.update(
                f"WAVE-{item.get('wave')}/{item.get('id')}"
                for item in self.data.get("tickets", [])
                if isinstance(item, dict)
                and isinstance(item.get("wave"), str)
                and isinstance(item.get("id"), str)
            )
            for event in self.events:
                map_ref = event.get("map_ref")
                if isinstance(map_ref, str):
                    known_map_refs.add(map_ref)
                affects = event.get("affects")
                if isinstance(affects, list):
                    known_map_refs.update(
                        ref for ref in affects if isinstance(ref, str)
                    )
            known_map_refs.update(
                ref for path in structural if (ref := self.impact_ref(path)) is not None
            )
            unknown_map_refs = sorted(declared_map_refs - known_map_refs)
            if unknown_map_refs:
                self.fail(
                    "HUB_UPDATE_REQUIRED names unknown map references: "
                    + ", ".join(unknown_map_refs)
                )
            unchanged_declared_paths = sorted(declared_hub_paths - hub_changes)
            if unchanged_declared_paths:
                self.fail(
                    "HUB_UPDATE_REQUIRED names Development Hub paths that are not "
                    "changed in this PR: " + ", ".join(unchanged_declared_paths)
                )
            if (
                (structural or self.semantic_data_changed)
                and declared_event_ids
                and not declared_new_event_ids
                and not initial_integration_declaration
            ):
                self.fail(
                    "Structural or semantic HUB_UPDATE_REQUIRED declarations may "
                    "name only a newly appended change-event ID as event coverage"
                )
            if not (
                declared_map_refs
                or declared_new_event_ids
                or declared_hub_paths & hub_changes
                or initial_integration_declaration
            ):
                self.fail(
                    "HUB_UPDATE_REQUIRED must name a concrete map_ref, event ID, "
                    "or changed Development Hub source/path"
                )
            if (
                structural
                and not declared_new_event_ids
                and not initial_integration_declaration
            ):
                impacted_refs = {
                    ref
                    for path in structural
                    if (ref := self.impact_ref(path)) is not None
                }
                if not any(
                    self.ref_covered(expected, declared_map_refs)
                    for expected in impacted_refs
                ):
                    self.fail(
                        "HUB_UPDATE_REQUIRED must name an affected structural "
                        "map_ref or a concrete change-event ID"
                    )
            if self.semantic_data_changed and not (
                initial_integration_declaration
                or declared_new_event_ids
                or (declared_map_refs and bool(source_records & declared_hub_paths))
            ):
                self.fail(
                    "Semantic hub-data updates must declare an event ID or both "
                    "a map_ref and changed semantic source record"
                )
            missing = sorted(source_records - self.changed_paths)
            if structural and missing:
                self.fail(
                    "Structural repository changes require both hub source records; "
                    "missing: " + ", ".join(missing)
                )

    def run(self) -> int:
        if not self.repo_root.is_dir():
            self.fail(f"Repository root does not exist: {self.repo_root}")
        elif not (self.repo_root / ".git").exists():
            self.fail(f"Repository root has no .git entry: {self.repo_root}")
        if not self.hub_root.is_dir() or not _inside(self.repo_root, self.hub_root):
            self.fail(f"Hub root is missing or unconfined: {self.hub_root}")
        if self.errors:
            return self.report()

        self.load_sources()
        self.validate_model()
        # Downstream authority and renderer checks consume the validated model.
        # Stop here on malformed source shapes so hostile input fails closed with
        # structured validation errors instead of triggering secondary tracebacks.
        if self.errors:
            return self.report()
        self.validate_html()
        self.validate_renderer_drift()
        self.validate_repository_authority()
        self.validate_root_integration()
        self.load_github_event()
        self.collect_diff()
        self.validate_snapshot_metadata()
        self.validate_structural_diff()
        self.validate_pr_declaration()
        return self.report()

    def report(self) -> int:
        print(
            f"Waves: {len(self.data.get('waves', [])) if isinstance(self.data, dict) else 0}"
        )
        print(
            f"Tickets: {len(self.data.get('tickets', [])) if isinstance(self.data, dict) else 0}"
        )
        print(
            f"Change routes: {len(self.data.get('change_paths', [])) if isinstance(self.data, dict) else 0}"
        )
        print(f"Change events: {len(self.events)}")
        print(
            f"Maturity states: {len(self.data.get('maturity', [])) if isinstance(self.data, dict) else 0}"
        )
        print(f"Warnings: {len(self.warnings)}")
        for warning in self.warnings:
            print(f"WARN: {warning}")
        print(f"Errors: {len(self.errors)}")
        for error in self.errors:
            print(f"ERROR: {error}")
        if self.errors:
            return 1
        print("Validation passed.")
        return 0


def main(argv: list[str] | None = None) -> int:
    default_repo = Path(__file__).resolve().parents[4]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=default_repo,
        help="Carbon repository root (default: inferred from this script)",
    )
    parser.add_argument(
        "--skip-pr-contract",
        action="store_true",
        help="skip the pull-request body declaration check (for owner-controlled publication workflows)",
    )
    args = parser.parse_args(argv)
    return Validator(args.repo_root, skip_pr_contract=args.skip_pr_contract).run()


if __name__ == "__main__":
    sys.exit(main())
