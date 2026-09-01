#!/usr/bin/env python3
"""Validate the Carbon Development Hub and its repository integration.

Only Python's standard library is used. The two JSON records are source; the
YAML indexes/templates and all presentation artifacts are validated output.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import html
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
HISTORICAL_WAVE_A_TICKET_IDS_V1 = [
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
]
HISTORICAL_WAVE_A_DIRECT_DEPENDENCIES_V1 = {
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
HISTORICAL_WAVE_A_CONTEXT_DEPENDENCIES_V1 = {"A9": ["A8"]}
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
    "controlling_register",
    "controlling_register_version",
    "controlling_board_fingerprint",
    "stage",
    "most_recent_closed_wave",
    "completed_wave_tickets",
    "recent_dependencies",
    "other_completed_wave_context",
    "downstream_handoffs",
    "parallel_context",
    "next_selected_ticket",
    "fail_closed",
    "maturity_states",
    "maturity_summary",
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
    "SYSTEM/BUSINESS-AUTHORITY",
    "SYSTEM/CI",
    "SYSTEM/DEVELOPMENT-HUB",
    "SYSTEM/DEVELOPMENT-HUB/INTERACTIVE",
    "SYSTEM/DEVELOPMENT-HUB/VALIDATION",
    "SYSTEM/DEVELOPMENT-SEQUENCING",
    "SYSTEM/GOVERNANCE",
    "SYSTEM/MATURITY",
    "SYSTEM/PR-MAINTENANCE",
    "SYSTEM/PROTOCOL-AUTHORITY",
    "SYSTEM/PUBLICATION",
    "SYSTEM/PUBLICATION-AUTHORITY",
    "SYSTEM/SCIENTIFIC-CANON",
}
IMPACT_CLASSES = {"map_structural", "mapped_detail", "unmapped_authority"}
REQUIRED_AUTHORITY_ROOTS = {
    ".agent/",
    ".github/",
    "agent_pack/",
    "Business/",
    "Design_Specs/",
    "docs/context/",
    "docs/publications/",
}
MATURITY_EARNED_STATES = {"earned", "unearned"}
REQUIRED_IMPACT_RULE_IDS = {
    "root-agent-instructions",
    "root-spec",
    "legacy-code-index",
    "constitution",
    "always-on-invariants",
    "current-wave-register",
    "wave-board",
    "ticket-record",
    "ticket-plan",
    "ticket-evidence",
    "business-detail",
    "publication-detail",
    "protocol-detail",
    "hub-validation-workflow",
}
REQUIRED_DELIVERY_FIELDS = (
    "DELIVERY_MODE",
    "SEPARATE_CONTRACT_PR_REASON",
    "BASE",
    "FINAL_HEAD",
    "FINAL_TREE",
    "CHANGE_SCOPE",
    "CANONICAL_LOCAL_VALIDATION",
    "MERGE_GATE",
    "GREPTILE",
    "UNRESOLVED_THREADS",
    "BLOCKING_DIRECTION",
    "DYNAMIC_COMPLETION_EVIDENCE",
    "COMPLETION_RECEIPT_LOCATION",
    "CODE_BEARING_COMMITS",
    "POST_FREEZE_TREE_CHANGES",
    "FULL_CI_RUNS",
    "AVOIDABLE_RERUN_REASON",
)
DELIVERY_STATUS_ENUMS = {
    "CANONICAL_LOCAL_VALIDATION": {
        "PENDING",
        "PASSED",
        "SUCCESS",
        "SUCCEEDED",
        "FAILED",
        "UNAVAILABLE",
        "NOT_REQUIRED",
    },
    "MERGE_GATE": {"PENDING", "PASSED", "SUCCESS", "SUCCEEDED", "FAILED"},
    "GREPTILE": {"PENDING", "PASSED", "SUCCESS", "SUCCEEDED", "FAILED"},
    "BLOCKING_DIRECTION": {
        "NONE",
        "PENDING",
        "CHANGE",
        "BLOCKED",
        "REQUEST_CHANGES",
    },
}
DELIVERY_CHANGE_SCOPES = {
    "RUNTIME_FULL",
    "CONTRACT_AUTHORITY",
    "DERIVED_DOCUMENTATION",
}
SEPARATE_CONTRACT_REASON_CODES = {
    "CONTRACT_ONLY_TICKET",
    "CONCURRENT_DOWNSTREAM_IMMUTABLE_CONTRACT",
    "CROSS_DOMAIN_PUBLIC_INTERFACE_FREEZE",
}
ALWAYS_CURRENT_SEQUENCING_AUTHORITIES = {
    ".agent/WAVE.md",
    "Design_Specs/Agentic_Development_Master_Plan.md",
    "Design_Specs/Build_Out.md",
}
AUTHORITATIVE_SEQUENCING_REASON = re.compile(
    r"^AUTHORITATIVE_SEQUENCING \| AUTHORITY: ([A-Za-z0-9._/-]+) " r"\| DETAILS: (.+)$"
)
TICKET_SIZE_REASON = re.compile(
    r"\b(?:ticket(?: s)? size|size of (?:the )?ticket|"
    r"(?:large|big|oversized?) ticket|"
    r"ticket (?:is )?(?:too )?(?:large|big|oversized?)|"
    r"too (?:large|big) (?:a )?ticket)\b"
)
SEQUENCING_DETAILS_FORBIDDEN = re.compile(r"[<>&*`_]")


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


def _normalize_delivery_prose(value: str) -> str:
    rendered = _clean_markdown(html.unescape(value)).casefold()
    return " ".join(re.sub(r"[\W_]+", " ", rendered).split())


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
        self.historical_github_event: dict[str, Any] | None = None
        self.github_event: dict[str, Any] | None = None
        self.live_pr_loaded = False
        self.changed_paths: set[str] | None = None
        self.deleted_paths: set[str] = set()
        self.new_event_ids: set[str] = set()
        self.diff_base_sha: str | None = None
        self.base_hub_data: dict[str, Any] | None = None
        self.semantic_data_changed = False
        self.captured_at: datetime | None = None
        self.impact_cache: dict[str, dict[str, str] | None] = {}

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

    @classmethod
    def semantic_data_view(
        cls,
        value: Any,
        path: tuple[str, ...] = (),
        snapshot_commits: frozenset[str] | None = None,
        normalized_ticket_revisions: dict[str, frozenset[str]] | None = None,
        normalized_wave_revisions: dict[str, frozenset[str]] | None = None,
        record_kind: str | None = None,
        record_id: str | None = None,
    ) -> Any:
        """Remove current-role pins while retaining historical identities."""
        if path == () and isinstance(value, dict):
            meta = value.get("meta")
            candidate = (
                meta.get("authority_snapshot_commit")
                if isinstance(meta, dict)
                else None
            )
            if (
                snapshot_commits is None
                and isinstance(candidate, str)
                and re.fullmatch(r"[0-9a-f]{40}", candidate)
            ):
                snapshot_commits = frozenset({candidate})
            current = value.get("current")
            if normalized_ticket_revisions is None:
                selected = current.get("ticket") if isinstance(current, dict) else None
                normalized_ticket_revisions = dict.fromkeys(
                    [selected] if isinstance(selected, str) else [],
                    snapshot_commits or frozenset(),
                )
            if normalized_wave_revisions is None:
                active = current.get("wave") if isinstance(current, dict) else None
                normalized_wave_revisions = dict.fromkeys(
                    [active] if isinstance(active, str) else [],
                    snapshot_commits or frozenset(),
                )
        normalized_ticket_revisions = normalized_ticket_revisions or {}
        normalized_wave_revisions = normalized_wave_revisions or {}
        if isinstance(value, dict):
            return {
                key: cls.semantic_data_view(
                    child,
                    (*path, key),
                    snapshot_commits,
                    normalized_ticket_revisions,
                    normalized_wave_revisions,
                    record_kind,
                    record_id,
                )
                for key, child in value.items()
                if not (
                    path == ("meta",)
                    and key
                    in {
                        "captured_at_utc",
                        "authority_snapshot_commit",
                        "hub_build_commit",
                    }
                )
            }
        if isinstance(value, list):
            result = []
            for child in value:
                child_kind = record_kind
                child_id = record_id
                if isinstance(child, dict) and path == ("tickets",):
                    child_kind = "ticket"
                    candidate_id = child.get("id")
                    child_id = candidate_id if isinstance(candidate_id, str) else None
                elif isinstance(child, dict) and path == ("waves",):
                    child_kind = "wave"
                    candidate_id = child.get("id")
                    child_id = candidate_id if isinstance(candidate_id, str) else None
                result.append(
                    cls.semantic_data_view(
                        child,
                        path,
                        snapshot_commits,
                        normalized_ticket_revisions,
                        normalized_wave_revisions,
                        child_kind,
                        child_id,
                    )
                )
            return result
        role_revisions = frozenset()
        if path:
            if path[0] in {"sources", "current", "authority_source_checks"}:
                role_revisions = snapshot_commits or frozenset()
            elif record_kind == "ticket" and "repo_links" in path:
                role_revisions = normalized_ticket_revisions.get(
                    record_id or "", frozenset()
                )
            elif record_kind == "wave" and "repo_links" in path:
                role_revisions = normalized_wave_revisions.get(
                    record_id or "", frozenset()
                )
        if isinstance(value, str) and role_revisions:
            for snapshot_commit in sorted(role_revisions):
                value = re.sub(
                    rf"(/(?:blob|commit)/){re.escape(snapshot_commit)}(?=/|$)",
                    r"\1{SNAPSHOT_COMMIT}",
                    value,
                )
        return value

    @staticmethod
    def authority_snapshot(value: Any) -> str | None:
        if not isinstance(value, dict):
            return None
        meta = value.get("meta")
        candidate = (
            meta.get("authority_snapshot_commit") if isinstance(meta, dict) else None
        )
        if isinstance(candidate, str) and re.fullmatch(r"[0-9a-f]{40}", candidate):
            return candidate
        return None

    @classmethod
    def paired_semantic_data_views(cls, base: Any, current: Any) -> tuple[Any, Any]:
        """Normalize both comparison snapshots without erasing ancestor changes."""
        base_snapshot = cls.authority_snapshot(base)
        current_snapshot = cls.authority_snapshot(current)
        snapshots = frozenset(
            snapshot
            for snapshot in (base_snapshot, current_snapshot)
            if snapshot is not None
        )

        def current_identity(value: Any, field: str) -> str | None:
            if not isinstance(value, dict):
                return None
            current_record = value.get("current")
            candidate = (
                current_record.get(field) if isinstance(current_record, dict) else None
            )
            return candidate if isinstance(candidate, str) else None

        def record_revisions(value: Any, collection: str, record_id: str) -> set[str]:
            if not isinstance(value, dict):
                return set()
            records = value.get(collection)
            if not isinstance(records, list):
                return set()
            record = next(
                (
                    item
                    for item in records
                    if isinstance(item, dict) and item.get("id") == record_id
                ),
                None,
            )
            if not isinstance(record, dict):
                return set()
            links = record.get("repo_links")
            if not isinstance(links, list):
                return set()
            revisions: set[str] = set()
            for link in links:
                if not isinstance(link, dict):
                    continue
                url = link.get("url")
                if not isinstance(url, str):
                    continue
                revisions.update(
                    re.findall(r"/(?:blob|commit)/([0-9a-f]{40})(?=/|$)", url)
                )
            return revisions

        def role_revisions(field: str, collection: str) -> dict[str, frozenset[str]]:
            base_id = current_identity(base, field)
            current_id = current_identity(current, field)
            result: dict[str, frozenset[str]] = {}
            # A retiring role may retain its old exact pins, but it must not adopt
            # the new snapshot after becoming historical. A newly current role may
            # replace any of its prior historical pins with the current snapshot.
            if base_id is not None:
                revisions = record_revisions(base, collection, base_id)
                if base_snapshot is not None:
                    revisions.add(base_snapshot)
                if base_id == current_id and current_snapshot is not None:
                    revisions.add(current_snapshot)
                result[base_id] = frozenset(revisions)
            if current_id is not None and current_id != base_id:
                revisions = record_revisions(base, collection, current_id)
                if current_snapshot is not None:
                    revisions.add(current_snapshot)
                result[current_id] = frozenset(revisions)
            return result

        ticket_revisions = role_revisions("ticket", "tickets")
        wave_revisions = role_revisions("wave", "waves")
        return (
            cls.semantic_data_view(
                base,
                snapshot_commits=snapshots,
                normalized_ticket_revisions=ticket_revisions,
                normalized_wave_revisions=wave_revisions,
            ),
            cls.semantic_data_view(
                current,
                snapshot_commits=snapshots,
                normalized_ticket_revisions=ticket_revisions,
                normalized_wave_revisions=wave_revisions,
            ),
        )

    @classmethod
    def semantic_data_changed_between(cls, base: Any, current: Any) -> bool:
        base_view, current_view = cls.paired_semantic_data_views(base, current)
        return base_view != current_view

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

    @staticmethod
    def carbon_blob_target(value: Any) -> tuple[str, str] | None:
        if not isinstance(value, str):
            return None
        try:
            parsed = urllib.parse.urlsplit(value)
        except ValueError:
            return None
        prefix = "/carbonphysicsai/Carbon/blob/"
        if (
            parsed.scheme != "https"
            or parsed.netloc != "github.com"
            or not parsed.path.startswith(prefix)
            or parsed.query
            or parsed.fragment
        ):
            return None
        remainder = parsed.path[len(prefix) :]
        if "/" not in remainder:
            return "", ""
        revision, path = remainder.split("/", 1)
        return revision, urllib.parse.unquote(path)

    @staticmethod
    def carbon_dynamic_route(value: Any) -> bool:
        """Return whether a Carbon link is an allowed dynamic issue/PR route."""
        if not isinstance(value, str):
            return False
        try:
            parsed = urllib.parse.urlsplit(value)
        except ValueError:
            return False
        return (
            parsed.scheme == "https"
            and parsed.netloc == "github.com"
            and not parsed.query
            and not parsed.fragment
            and re.fullmatch(
                r"/carbonphysicsai/Carbon/(?:issues|pull)/[1-9][0-9]*",
                parsed.path,
            )
            is not None
        )

    def current_authority_target(
        self, value: Any, commit: str, label: str
    ) -> tuple[str, str] | None:
        """Require a current authority link or permit an explicit dynamic route."""
        if self.carbon_dynamic_route(value):
            return None
        target = self.carbon_blob_target(value)
        if target is None:
            self.fail(
                f"{label} must be an exact current-snapshot Carbon blob URL or an "
                "issue/PR dynamic route"
            )
            return None
        revision, path = target
        pure = PurePosixPath(path)
        if (
            revision != commit
            or not path
            or path == "."
            or pure.is_absolute()
            or ".." in pure.parts
            or "\\" in path
            or pure.as_posix() != path
            or any(
                character.isspace() or ord(character) < 32 or ord(character) == 127
                for character in path
            )
        ):
            self.fail(f"{label} must pin meta.authority_snapshot_commit at a safe path")
            return None
        return target

    def validate_authority_source_checks(self) -> None:
        checks = self.data.get("authority_source_checks")
        if (
            not isinstance(checks, list)
            or not checks
            or not all(isinstance(item, dict) for item in checks)
        ):
            self.fail("authority_source_checks must be a non-empty list of objects")
            return
        ids: list[str] = []
        paths: list[str] = []
        for index, check in enumerate(checks):
            label = f"authority_source_checks[{index}]"
            if not self.require_keys(check, ("id", "path", "required_markers"), label):
                continue
            check_id = check.get("id")
            if not isinstance(check_id, str) or not re.fullmatch(
                r"[a-z0-9]+(?:-[a-z0-9]+)*", check_id
            ):
                self.fail(f"{label}.id must be stable lowercase kebab-case")
            else:
                ids.append(check_id)
            path = check.get("path")
            if (
                not isinstance(path, str)
                or not path
                or path.startswith(("/", "\\"))
                or "\\" in path
                or ".." in PurePosixPath(path).parts
            ):
                self.fail(f"{label}.path must be a safe repository-relative file")
            else:
                paths.append(path)
            markers = check.get("required_markers")
            if (
                not isinstance(markers, list)
                or not markers
                or not all(
                    isinstance(marker, str) and marker.strip() for marker in markers
                )
            ):
                self.fail(f"{label}.required_markers must be non-empty strings")
            elif not _unique(markers):
                self.fail(f"{label}.required_markers contains duplicates")
        if not _unique(ids):
            self.fail("authority_source_checks contains duplicate IDs")
        if not _unique(paths):
            self.fail("authority_source_checks contains duplicate paths")

        current = self.data.get("current", {})
        selected_id = current.get("ticket") if isinstance(current, dict) else None
        selected = next(
            (
                item
                for item in self.data.get("tickets", [])
                if isinstance(item, dict) and item.get("id") == selected_id
            ),
            None,
        )
        required_paths = {".agent/WAVE.md"}
        register = (
            current.get("controlling_register") if isinstance(current, dict) else None
        )
        if isinstance(register, str):
            required_paths.add(register)
        if isinstance(selected, dict):
            repo_path = selected.get("repo_path")
            if isinstance(repo_path, str):
                required_paths.add(repo_path)
            for link in selected.get("repo_links", []):
                if not isinstance(link, dict):
                    continue
                if "evidence" in str(link.get("label", "")).lower():
                    target = self.carbon_blob_target(link.get("url"))
                    if target is not None and target[1]:
                        required_paths.add(target[1])
        if isinstance(current, dict) and current.get("decision_series"):
            required_paths.add(".agent/DECISIONS.md")
        missing_paths = sorted(required_paths - set(paths))
        if missing_paths:
            self.fail(
                "authority_source_checks is missing current-state proof paths: "
                + ", ".join(missing_paths)
            )

    def validate_impact_policy(self) -> None:
        policy = self.data.get("impact_policy")
        if not self.require_keys(
            policy,
            (
                "schema_version",
                "classes",
                "system_map_refs",
                "authority_roots",
                "rules",
            ),
            "impact_policy",
        ):
            return
        if policy.get("schema_version") != "1.0":
            self.fail("impact_policy.schema_version must be '1.0'")
        classes = policy.get("classes")
        if not isinstance(classes, list) or set(classes) != IMPACT_CLASSES:
            self.fail(
                "impact_policy.classes must define map_structural, mapped_detail, "
                "and unmapped_authority"
            )
        system_refs = policy.get("system_map_refs")
        if not isinstance(system_refs, list) or not all(
            isinstance(value, str)
            and re.fullmatch(r"SYSTEM/[A-Z0-9-]+(?:/[A-Z0-9-]+)*", value)
            for value in system_refs
        ):
            self.fail("impact_policy.system_map_refs must be stable SYSTEM/* refs")
            system_refs = []
        elif not _unique(system_refs):
            self.fail("impact_policy.system_map_refs contains duplicates")
        missing_system_refs = sorted(KNOWN_SYSTEM_MAP_REFS - set(system_refs))
        if missing_system_refs:
            self.fail(
                "impact_policy.system_map_refs is missing required refs: "
                + ", ".join(missing_system_refs)
            )
        roots = policy.get("authority_roots")
        if not isinstance(roots, list) or not all(
            isinstance(value, str)
            and value.endswith("/")
            and not value.startswith(("/", "\\"))
            and ".." not in PurePosixPath(value).parts
            and "\\" not in value
            for value in roots
        ):
            self.fail(
                "impact_policy.authority_roots must be safe repository-relative prefixes"
            )
            roots = []
        elif not _unique(roots):
            self.fail("impact_policy.authority_roots contains duplicates")
        missing_authority_roots = sorted(REQUIRED_AUTHORITY_ROOTS - set(roots))
        if missing_authority_roots:
            self.fail(
                "impact_policy.authority_roots is missing required protected roots: "
                + ", ".join(missing_authority_roots)
            )
        rules = policy.get("rules")
        if not isinstance(rules, list) or not all(
            isinstance(rule, dict) for rule in rules
        ):
            self.fail("impact_policy.rules must be a list of objects")
            return
        rule_ids: list[str] = []
        for index, rule in enumerate(rules):
            label = f"impact_policy.rules[{index}]"
            if not self.require_keys(
                rule,
                ("id", "match_type", "path", "impact_class", "map_ref"),
                label,
            ):
                continue
            rule_id = rule.get("id")
            if not isinstance(rule_id, str) or not re.fullmatch(
                r"[a-z0-9]+(?:-[a-z0-9]+)*", rule_id
            ):
                self.fail(f"{label}.id must be a stable lowercase kebab-case ID")
            else:
                rule_ids.append(rule_id)
            if rule.get("match_type") not in {
                "exact",
                "prefix",
                "wave_board",
                "ticket_record",
            }:
                self.fail(f"{label}.match_type is unsupported")
            path = rule.get("path")
            if (
                not isinstance(path, str)
                or not path
                or path.startswith(("/", "\\"))
                or "\\" in path
                or ".." in PurePosixPath(path).parts
            ):
                self.fail(f"{label}.path must be a safe repository-relative value")
            if rule.get("impact_class") not in IMPACT_CLASSES - {"unmapped_authority"}:
                self.fail(
                    f"{label}.impact_class must be map_structural or mapped_detail"
                )
            map_ref = rule.get("map_ref")
            if (
                map_ref
                not in {
                    "CURRENT_WAVE",
                    "WAVE_FROM_PATH",
                    "TICKET_FROM_PATH",
                }
                and map_ref not in set(system_refs)
                and (
                    not isinstance(map_ref, str)
                    or not re.fullmatch(r"WAVE-[A-N](?:/[A-Z0-9-]+)?", map_ref)
                )
            ):
                self.fail(f"{label}.map_ref is not a supported stable owner")
            structural_when = rule.get("structural_when")
            if structural_when not in {
                None,
                "wave_register_fields_change",
                "ticket_board_fields_change",
                "ticket_record_fields_change",
            }:
                self.fail(f"{label}.structural_when is unsupported")
            if structural_when and rule.get("impact_class") != "mapped_detail":
                self.fail(
                    f"{label}.structural_when requires a mapped_detail default class"
                )
        if not _unique(rule_ids):
            self.fail("impact_policy.rules contains duplicate IDs")
        missing_rules = sorted(REQUIRED_IMPACT_RULE_IDS - set(rule_ids))
        if missing_rules:
            self.fail(
                "impact_policy.rules is missing required ownership rules: "
                + ", ".join(missing_rules)
            )

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
            "authority_source_checks",
            "authority_ceilings",
            "impact_policy",
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
        self.validate_authority_source_checks()
        self.validate_impact_policy()
        meta = self.data.get("meta")
        if self.require_keys(
            meta,
            (
                "title",
                "version",
                "captured_at_utc",
                "repository",
                "branch",
                "authority_snapshot_commit",
                "hub_build_commit",
                "purpose",
                "authority_notice",
            ),
            "meta",
        ):
            if meta.get("version") != "2.1":
                self.fail("meta.version must be '2.1'")
            if not re.fullmatch(
                r"[0-9a-f]{40}", str(meta.get("authority_snapshot_commit", ""))
            ):
                self.fail(
                    "meta.authority_snapshot_commit must be a lowercase "
                    "40-character Git commit ID"
                )
            if meta.get("hub_build_commit") is not None:
                self.fail(
                    "meta.hub_build_commit must remain null in source to avoid "
                    "self-referential build identity"
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
                "completed_wave_tickets",
                "recent_dependencies",
                "other_completed_wave_context",
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
            maturity_states = current.get("maturity_states")
            if not isinstance(maturity_states, dict):
                self.fail("current.maturity_states must be an object")
            else:
                if list(maturity_states) != EXPECTED_MATURITY:
                    self.fail(
                        "current.maturity_states must contain the eight maturity "
                        f"dimensions in canonical order {EXPECTED_MATURITY!r}"
                    )
                invalid_states = {
                    str(value)
                    for value in maturity_states.values()
                    if value not in MATURITY_EARNED_STATES
                }
                if invalid_states:
                    self.fail(
                        "current.maturity_states values must be earned or unearned; "
                        f"found {sorted(invalid_states)!r}"
                    )
            if (
                not isinstance(current.get("maturity_summary"), str)
                or not current.get("maturity_summary", "").strip()
            ):
                self.fail("current.maturity_summary must be a non-empty string")
            if not re.fullmatch(
                r"[0-9a-f]{64}", str(current.get("controlling_board_fingerprint", ""))
            ):
                self.fail(
                    "current.controlling_board_fingerprint must be a lowercase "
                    "SHA-256 digest of the parsed controlling board"
                )

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
            ("change route", route_ids, EXPECTED_ROUTES),
            ("maturity", maturity_ids, EXPECTED_MATURITY),
        ):
            if not _unique(actual):
                self.fail(f"{label} IDs must be unique")
            if actual != expected:
                self.fail(f"Expected stable {label} IDs {expected}; found {actual}")
        if not _unique(ticket_ids):
            self.fail("ticket IDs must be unique")
        captured_wave_a = [
            item.get("id") for item in tickets if item.get("wave") == "A"
        ]
        if captured_wave_a != HISTORICAL_WAVE_A_TICKET_IDS_V1:
            self.fail(
                "Wave A historical closeout v1 ticket IDs changed: expected "
                f"{HISTORICAL_WAVE_A_TICKET_IDS_V1!r}; found {captured_wave_a!r}"
            )
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
            if ticket_id == current.get("ticket"):
                selected_maturity = ticket.get("maturity_states")
                if not isinstance(selected_maturity, dict):
                    self.fail(
                        f"Selected ticket {ticket_id} must define structured maturity_states"
                    )
                elif selected_maturity != current.get("maturity_states"):
                    self.fail(
                        "current.maturity_states must exactly match the selected "
                        f"ticket {ticket_id} maturity_states"
                    )
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
            if ticket_id in HISTORICAL_WAVE_A_DIRECT_DEPENDENCIES_V1:
                expected_direct = HISTORICAL_WAVE_A_DIRECT_DEPENDENCIES_V1[ticket_id]
                if ticket.get("depends_on") != expected_direct:
                    self.fail(
                        f"{ticket_id}.depends_on must preserve the ticket-owned "
                        f"direct contract dependencies {expected_direct!r}"
                    )
                expected_context = HISTORICAL_WAVE_A_CONTEXT_DEPENDENCIES_V1.get(
                    ticket_id, []
                )
                if ticket.get("depends_on_context", []) != expected_context:
                    self.fail(
                        f"{ticket_id}.depends_on_context must preserve the Wave-A "
                        f"sequencing context {expected_context!r}"
                    )
            self.validate_ticket_paths(ticket)

        ticket_partition = [
            ticket_id
            for wave in waves
            for ticket_id in (
                wave.get("ticket_ids", [])
                if isinstance(wave.get("ticket_ids"), list)
                else []
            )
        ]
        if ticket_partition != ticket_ids:
            self.fail(
                "Wave ticket_ids must partition captured tickets in canonical wave order; "
                f"found {ticket_partition!r} versus {ticket_ids!r}"
            )

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
            policy = self.data.get("impact_policy", {})
            allowed = (
                policy.get("system_map_refs", []) if isinstance(policy, dict) else []
            )
            if value not in allowed:
                self.fail(
                    f"{label} references SYSTEM owner not declared by impact_policy: {value!r}"
                )
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
            current = self.data.get("current", {})
            current_wave = str(current.get("wave", ""))
            current_ticket = str(current.get("ticket", ""))
            for phrase in (
                "Carbon Development Hub",
                "Wave A through Wave N",
                f"Wave {current_wave}",
                current_ticket,
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

    def parse_current_authority(
        self, text: str, source_label: str
    ) -> dict[str, Any] | None:
        patterns = {
            "wave": r"^\*\*Current wave:\*\*\s*([A-N])\s*$",
            "state": r"^\*\*State:\*\*\s*(.+?)\s*$",
            "register": (
                r"^\*\*Controlling register:\*\*\s*`([^`]+)`\s+version\s+"
                r"([A-Za-z0-9._-]+)\s*$"
            ),
            "ticket": (
                r"^\*\*Selected ticket:\*\*\s*([A-Z0-9-]+)\s*[—-]+\s*"
                r"`(todo|in_progress|done|blocked)`\s*$"
            ),
        }
        matches = {
            key: re.search(pattern, text, flags=re.MULTILINE)
            for key, pattern in patterns.items()
        }
        missing = [key for key, match in matches.items() if match is None]
        if missing:
            self.fail(
                f"{source_label} is missing parseable authority fields: {missing}"
            )
            return None
        register_path = str(matches["register"].group(1))
        pure = PurePosixPath(register_path)
        if (
            pure.is_absolute()
            or "\\" in register_path
            or ".." in pure.parts
            or pure.parts[:1] != (".agent",)
            or pure.suffix.lower() != ".md"
        ):
            self.fail(
                f"{source_label} controlling register is not a safe .agent Markdown path: "
                f"{register_path!r}"
            )
            return None
        next_match = re.search(
            r"^\*\*Next selected ticket:\*\*\s*`?([A-Z0-9-]+|none)`?\s*$",
            text,
            flags=re.MULTILINE | re.IGNORECASE,
        )
        next_ticket = None
        if next_match and next_match.group(1).lower() != "none":
            next_ticket = next_match.group(1).upper()
        closed_waves = tuple(
            value.upper()
            for value in re.findall(
                r"^\*\*Wave\s+([A-N]):\*\*\s*closed\b",
                text,
                flags=re.MULTILINE | re.IGNORECASE,
            )
        )
        return {
            "wave": matches["wave"].group(1),
            "state": _clean_markdown(matches["state"].group(1)),
            "register": register_path,
            "register_version": matches["register"].group(2),
            "ticket": matches["ticket"].group(1),
            "ticket_status": matches["ticket"].group(2),
            "next_ticket": next_ticket,
            "closed_waves": closed_waves,
        }

    def parse_ticket_board(
        self, text: str, source_label: str
    ) -> tuple[str | None, dict[str, dict[str, Any]]]:
        version_match = re.search(
            r"^\*\*Version:\*\*\s*([A-Za-z0-9._-]+)\s*$",
            text,
            flags=re.MULTILINE,
        )
        version = version_match.group(1) if version_match else None
        if version is None:
            self.fail(f"{source_label} is missing a parseable Version field")
        required_headers = {
            "ID",
            "Deliverable",
            "Status",
            "Driver",
            "Accountable reviewer",
            "Depends on",
        }
        lines = text.splitlines()
        headers: list[str] | None = None
        start = 0
        for index, line in enumerate(lines):
            if not line.strip().startswith("|"):
                continue
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            if required_headers <= set(cells):
                headers = cells
                start = index + 1
                break
        if headers is None:
            self.fail(f"{source_label} is missing the controlling ticket table")
            return version, {}
        rows: dict[str, dict[str, Any]] = {}
        ticket_pattern = re.compile(
            r"(?<![A-Z0-9-])([A-N](?:-\d+[A-Z]?\d*|\d+|-[A-Z][A-Z0-9]*))"
            r"(?![A-Z0-9-])"
        )
        for line in lines[start:]:
            if not line.strip().startswith("|"):
                if rows:
                    break
                continue
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            if all(re.fullmatch(r":?-+:?", cell) for cell in cells):
                continue
            if len(cells) != len(headers):
                self.fail(f"{source_label} has a malformed board row: {line}")
                continue
            raw_record = dict(zip(headers, cells))
            ticket_id = _clean_markdown(raw_record["ID"])
            if not re.fullmatch(
                r"[A-N](?:-\d+[A-Z]?\d*|\d+|-[A-Z][A-Z0-9]*)", ticket_id
            ):
                self.fail(f"{source_label} has invalid ticket ID {ticket_id!r}")
                continue
            if ticket_id in rows:
                self.fail(f"{source_label} contains duplicate row {ticket_id}")
                continue
            status = _clean_markdown(raw_record["Status"])
            if status not in TICKET_STATUSES:
                self.fail(
                    f"{source_label} row {ticket_id} has invalid status {status!r}"
                )
            dependency_text = _clean_markdown(raw_record["Depends on"])
            blocking_dependency_text = "; ".join(
                clause
                for clause in dependency_text.split(";")
                if not re.search(r"\bnon[- ]blocking\b", clause, flags=re.IGNORECASE)
            )
            dependencies = [
                match.group(1)
                for match in ticket_pattern.finditer(blocking_dependency_text)
            ]
            rows[ticket_id] = {
                "id": ticket_id,
                "deliverable": _clean_markdown(raw_record["Deliverable"]),
                "status": status,
                "owner": _clean_markdown(raw_record["Driver"]),
                "reviewer": _clean_markdown(raw_record["Accountable reviewer"]),
                "depends_on": dependencies,
                "dependency_context": dependency_text,
            }
        return version, rows

    @staticmethod
    def board_signature(
        version: str | None, rows: dict[str, dict[str, Any]]
    ) -> tuple[Any, ...]:
        return (
            version,
            tuple(
                (
                    ticket_id,
                    row.get("deliverable"),
                    row.get("status"),
                    row.get("owner"),
                    row.get("reviewer"),
                    tuple(row.get("depends_on", [])),
                )
                for ticket_id, row in rows.items()
            ),
        )

    @classmethod
    def board_fingerprint(
        cls, version: str | None, rows: dict[str, dict[str, Any]]
    ) -> str:
        payload = json.dumps(
            cls.board_signature(version, rows),
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    @staticmethod
    def ticket_record_fields(text: str) -> dict[str, str]:
        def normalize(value: str) -> str:
            return _clean_markdown(value.replace("<br>", " ")).casefold()

        def field(*names: str) -> str:
            alternatives = "|".join(re.escape(name) for name in names)
            match = re.search(
                rf"^\*\*(?:{alternatives}):\*\*\s*(.+?)\s*$",
                text,
                flags=re.IGNORECASE | re.MULTILINE,
            )
            return normalize(match.group(1)) if match else ""

        def section(name: str) -> str:
            match = re.search(
                rf"^##\s+{re.escape(name)}\s*$\n(.*?)(?=^##\s+|\Z)",
                text,
                flags=re.IGNORECASE | re.MULTILINE | re.DOTALL,
            )
            return normalize(match.group(1)) if match else ""

        heading = re.search(r"^#\s+(.+?)\s*$", text, flags=re.MULTILINE)
        return {
            "title": normalize(heading.group(1)) if heading else "",
            "purpose": section("Goal"),
            "boundary": section("Must not"),
            "wave": field("Wave"),
            "status": field("Status"),
            "depends_on": field("Depends on"),
            "owner": field("Owner", "Driver"),
            "reviewer": field("Accountable reviewer", "Reviewer"),
            "authority": field("Authority", "Authority ceiling"),
            "contract": field("Working contract", "Primary contract", "Contract"),
            "plan": field("Plan", "Implementation plan"),
            "evidence": field("Evidence", "Evidence record"),
        }

    def read_authority_text(
        self, relative: str, source_label: str, revision: str | None = None
    ) -> str | None:
        pure = PurePosixPath(relative)
        if pure.is_absolute() or "\\" in relative or ".." in pure.parts:
            self.fail(f"{source_label} requested unsafe authority path {relative!r}")
            return None
        if revision is not None:
            result = self.git("show", f"{revision}:{relative}", allow_failure=True)
            if result.returncode != 0:
                self.fail(
                    f"{source_label} cannot read {relative} at authority snapshot {revision}"
                )
                return None
            return result.stdout
        target = (self.repo_root / Path(*pure.parts)).resolve()
        if not _inside(self.repo_root, target):
            self.fail(
                f"{source_label} authority path escapes the repository: {relative}"
            )
            return None
        try:
            return target.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            self.fail(f"{source_label} cannot read {relative}: {exc}")
            return None

    def load_authority_view(
        self, source_label: str, revision: str | None = None
    ) -> dict[str, Any] | None:
        wave_text = self.read_authority_text(".agent/WAVE.md", source_label, revision)
        if wave_text is None:
            return None
        authority = self.parse_current_authority(
            wave_text, f"{source_label} .agent/WAVE.md"
        )
        if authority is None:
            return None
        board_text = self.read_authority_text(
            authority["register"], source_label, revision
        )
        if board_text is None:
            return None
        board_version, board_rows = self.parse_ticket_board(
            board_text, f"{source_label} {authority['register']}"
        )
        selected = next(
            (
                item
                for item in self.data.get("tickets", [])
                if item.get("id") == authority["ticket"]
            ),
            None,
        )
        selected_source = None
        if selected is not None:
            selected_source = self.read_authority_text(
                str(selected.get("repo_path", "")), source_label, revision
            )
        decisions_text = self.read_authority_text(
            ".agent/DECISIONS.md", source_label, revision
        )
        return {
            "authority": authority,
            "wave_text": wave_text,
            "board_version": board_version,
            "board_rows": board_rows,
            "selected_source": selected_source,
            "decisions_text": decisions_text or "",
        }

    def validate_authority_view(self, view: dict[str, Any], source_label: str) -> None:
        authority = view["authority"]
        authoritative_wave = authority["wave"]
        authoritative_ticket = authority["ticket"]
        authoritative_status = authority["ticket_status"]
        current = self.data.get("current", {})
        for label, actual, expected in (
            ("current.wave", current.get("wave"), authoritative_wave),
            ("current.wave_status", current.get("wave_status"), authority["state"]),
            ("current.ticket", current.get("ticket"), authoritative_ticket),
            (
                "current.ticket_status",
                current.get("ticket_status"),
                authoritative_status,
            ),
            (
                "current.controlling_register",
                current.get("controlling_register"),
                authority["register"],
            ),
            (
                "current.controlling_register_version",
                current.get("controlling_register_version"),
                authority["register_version"],
            ),
        ):
            if actual != expected:
                self.fail(
                    f"{source_label}: {label} is {actual!r}, but authority says {expected!r}"
                )
        if view.get("board_version") != authority["register_version"]:
            self.fail(
                f"{source_label}: controlling-register version {authority['register_version']!r} "
                f"does not match board version {view.get('board_version')!r}"
            )
        board_fingerprint = self.board_fingerprint(
            view.get("board_version"), view.get("board_rows", {})
        )
        if current.get("controlling_board_fingerprint") != board_fingerprint:
            self.fail(
                f"{source_label}: current.controlling_board_fingerprint does not "
                "match the parsed controlling-board inventory"
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
                f"{source_label}: current Wave {authoritative_wave} must be the active hub wave"
            )
            return
        active_waves = [
            item.get("id")
            for item in self.data.get("waves", [])
            if item.get("status") == "active"
        ]
        if active_waves != [authoritative_wave]:
            self.fail(
                f"{source_label}: exactly the authoritative wave must be active; found {active_waves}"
            )
        if current.get("wave_title") != wave_record.get("title"):
            self.fail(
                f"{source_label}: current.wave_title must match Wave {authoritative_wave}"
            )
        predecessor = wave_record.get("predecessor")
        if current.get("most_recent_closed_wave") != predecessor:
            self.fail(
                f"{source_label}: current.most_recent_closed_wave must be {predecessor!r}"
            )
        if predecessor is not None and predecessor not in authority["closed_waves"]:
            self.fail(
                f"{source_label}: .agent/WAVE.md does not mark predecessor Wave {predecessor} closed"
            )
        board_rows = view["board_rows"]
        expected_active_ids = list(board_rows)
        captured_active_ids = wave_record.get("ticket_ids")
        if captured_active_ids != expected_active_ids:
            self.fail(
                f"{source_label}: Wave {authoritative_wave} ticket_ids must match the "
                f"controlling board {expected_active_ids!r}; found {captured_active_ids!r}"
            )
        data_rows = {
            item.get("id"): item
            for item in self.data.get("tickets", [])
            if item.get("wave") == authoritative_wave
        }
        if list(data_rows) != expected_active_ids:
            self.fail(
                f"{source_label}: captured Wave {authoritative_wave} ticket records "
                f"must match active board order {expected_active_ids!r}; found {list(data_rows)!r}"
            )
        known_ticket_ids = {
            str(item.get("id")) for item in self.data.get("tickets", [])
        }
        for ticket_id, board in board_rows.items():
            ticket = data_rows.get(ticket_id)
            if ticket is None:
                continue
            if not ticket_id.startswith(authoritative_wave):
                self.fail(
                    f"{source_label}: active board row {ticket_id} does not belong to Wave {authoritative_wave}"
                )
            for data_field in ("status", "owner", "reviewer"):
                actual = _clean_markdown(str(ticket.get(data_field, "")))
                expected = board[data_field]
                if actual != expected:
                    self.fail(
                        f"{source_label}: {ticket_id}.{data_field} is {actual!r}; "
                        f"controlling board says {expected!r}"
                    )
            unknown_dependencies = [
                dependency
                for dependency in board["depends_on"]
                if dependency not in known_ticket_ids
            ]
            if unknown_dependencies:
                self.fail(
                    f"{source_label}: {ticket_id} board dependencies are not captured: "
                    f"{unknown_dependencies!r}"
                )
            if ticket.get("depends_on") != board["depends_on"]:
                self.fail(
                    f"{source_label}: {ticket_id}.depends_on is {ticket.get('depends_on')!r}; "
                    f"controlling board says {board['depends_on']!r}"
                )
        completed = [
            ticket_id
            for ticket_id, row in board_rows.items()
            if row["status"] == "done"
        ]
        if current.get("completed_wave_tickets") != completed:
            self.fail(
                f"{source_label}: current.completed_wave_tickets must be {completed!r}; "
                f"found {current.get('completed_wave_tickets')!r}"
            )
        selected = data_rows.get(authoritative_ticket)
        if selected is None:
            self.fail(
                f"{source_label}: selected ticket {authoritative_ticket} is not captured"
            )
            return
        if selected.get("status") != authoritative_status:
            self.fail(
                f"{source_label}: selected ticket status is {selected.get('status')!r}; "
                f"authority says {authoritative_status!r}"
            )
        if current.get("ticket_title") != selected.get("title"):
            self.fail(
                f"{source_label}: current.ticket_title must match selected ticket"
            )
        stage_tokens = re.findall(r"[a-z0-9]+", str(current.get("stage", "")).lower())
        selected_stage_tokens = re.findall(
            r"[a-z0-9]+", str(selected.get("current_stage", "")).lower()
        )
        if not selected_stage_tokens or stage_tokens != selected_stage_tokens:
            self.fail(
                f"{source_label}: current.stage must match selected ticket current_stage"
            )
        selected_dependencies = selected.get("depends_on", [])
        if current.get("recent_dependencies") != selected_dependencies:
            self.fail(
                f"{source_label}: current.recent_dependencies must be {selected_dependencies!r}"
            )
        all_tickets = {
            str(item.get("id")): item for item in self.data.get("tickets", [])
        }
        incomplete_dependencies = [
            dependency
            for dependency in selected_dependencies
            if all_tickets.get(dependency, {}).get("status") != "done"
        ]
        if incomplete_dependencies:
            self.fail(
                f"{source_label}: selected ticket has non-done dependencies {incomplete_dependencies!r}"
            )
        other_expected = [
            ticket_id
            for ticket_id in completed
            if ticket_id not in set(selected_dependencies)
        ]
        if current.get("other_completed_wave_context") != other_expected:
            self.fail(
                f"{source_label}: current.other_completed_wave_context must be "
                f"{other_expected!r}; found {current.get('other_completed_wave_context')!r}"
            )
        if current.get("downstream_handoffs") != selected.get("unlocks"):
            self.fail(
                f"{source_label}: current.downstream_handoffs must match selected ticket unlocks"
            )
        parallel_statements = current.get("parallel_context", [])
        parallel_refs: set[str] = set()
        for statement in parallel_statements:
            parallel_refs.update(
                ticket_id
                for ticket_id in expected_active_ids
                if re.search(
                    rf"(?<![A-Z0-9-]){re.escape(ticket_id)}(?![A-Z0-9-])",
                    statement,
                )
            )
        if parallel_statements and not parallel_refs:
            self.fail(
                f"{source_label}: non-empty current.parallel_context must name an active-board ticket"
            )
        for parallel_id in sorted(parallel_refs):
            record = data_rows[parallel_id]
            if parallel_id == authoritative_ticket or record.get("status") != "todo":
                self.fail(
                    f"{source_label}: parallel context may only name unselected todo tickets; "
                    f"found {parallel_id}"
                )
            unresolved = [
                dependency
                for dependency in record.get("depends_on", [])
                if all_tickets.get(dependency, {}).get("status") != "done"
            ]
            if unresolved:
                self.fail(
                    f"{source_label}: parallel ticket {parallel_id} has unresolved "
                    f"dependencies {unresolved!r}"
                )
        if current.get("next_selected_ticket") != authority["next_ticket"]:
            self.fail(
                f"{source_label}: current.next_selected_ticket must be "
                f"{authority['next_ticket']!r}"
            )
        repository_url = str(self.data.get("meta", {}).get("repository", "")).rstrip(
            "/"
        )
        if current.get("technical_decision_route") != f"{repository_url}/issues/42":
            self.fail(
                f"{source_label}: current.technical_decision_route must be issue #42"
            )
        if current.get("owner_decision_route") != f"{repository_url}/issues/41":
            self.fail(f"{source_label}: current.owner_decision_route must be issue #41")
        decisions_text = view["decisions_text"]
        for decision_id in current.get("decision_series", []):
            if not str(decision_id).startswith(f"{authoritative_ticket}-D"):
                self.fail(
                    f"{source_label}: decision {decision_id!r} does not belong to selected ticket"
                )
            if not re.search(
                rf"^##\s+.*\b{re.escape(str(decision_id))}:?\s*",
                decisions_text,
                flags=re.MULTILINE,
            ):
                self.fail(
                    f"{source_label}: decision {decision_id!r} has no decision-log heading"
                )
        source_text = view.get("selected_source")
        if source_text is None:
            return
        source_fields = self.ticket_record_fields(source_text)
        source_status = re.search(
            r"^\*\*Status:\*\*\s*`?([a-z_]+)`?\s*$",
            source_text,
            flags=re.MULTILINE,
        )
        if not source_status:
            self.fail(
                f"{source_label}: selected ticket source has no parseable Status field"
            )
        elif source_status.group(1) != authoritative_status:
            self.fail(
                f"{source_label}: selected ticket source status is "
                f"{source_status.group(1)!r}; authority says {authoritative_status!r}"
            )
        source_dependencies = re.findall(
            r"\b[A-N](?:-[A-Z0-9]+|[0-9]+)\b",
            source_fields.get("depends_on", "").upper(),
        )
        board_dependency_context = str(
            board_rows[authoritative_ticket].get("dependency_context", "")
        )
        board_source_dependencies = re.findall(
            r"\b[A-N](?:-[A-Z0-9]+|[0-9]+)\b",
            board_dependency_context.split(";", 1)[0].upper(),
        )
        if (
            source_fields.get("depends_on")
            and source_dependencies != board_source_dependencies
        ):
            self.fail(
                f"{source_label}: selected ticket source dependencies are "
                f"{source_dependencies!r}; the controlling board's leading "
                f"dependency clause says {board_source_dependencies!r}"
            )
        for source_field, board_field in (("owner", "owner"), ("reviewer", "reviewer")):
            source_value = source_fields.get(source_field, "")
            if (
                source_value
                and source_value
                != board_rows[authoritative_ticket][board_field].casefold()
            ):
                self.fail(
                    f"{source_label}: selected ticket source {source_field} is "
                    f"{source_value!r}; controlling board says "
                    f"{board_rows[authoritative_ticket][board_field]!r}"
                )

    def validate_repository_authority(self) -> None:
        snapshot = str(self.data.get("meta", {}).get("authority_snapshot_commit", ""))
        snapshot_view = self.load_authority_view(
            "authority snapshot",
            snapshot if re.fullmatch(r"[0-9a-f]{40}", snapshot) else None,
        )
        if snapshot_view is not None:
            self.validate_authority_view(snapshot_view, "authority snapshot")
        candidate_view = self.load_authority_view("candidate HEAD")
        if candidate_view is not None:
            self.validate_authority_view(candidate_view, "candidate HEAD")

    def validate_root_integration(self) -> None:
        checks = {
            "README.md": (
                "## Development Hub",
                "docs/development/carbon_hub/orientation/START_HERE.md",
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
        commit = str(meta.get("authority_snapshot_commit", ""))
        if not re.fullmatch(r"[0-9a-f]{40}", commit):
            return
        try:
            resolved = self.git("rev-parse", "--verify", f"{commit}^{{commit}}")
            resolved_commit = resolved.stdout.strip().lower()
            if resolved_commit != commit:
                self.fail(
                    "meta.authority_snapshot_commit resolves to "
                    f"{resolved_commit}, not the recorded exact commit {commit}"
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
            self.fail(
                "Cannot resolve meta.authority_snapshot_commit as a repository "
                f"commit: {exc}"
            )
            return

        ancestry = self.git(
            "merge-base", "--is-ancestor", commit, "HEAD", allow_failure=True
        )
        if ancestry.returncode == 1:
            self.fail(
                "meta.authority_snapshot_commit must be an ancestor of candidate HEAD"
            )
        elif ancestry.returncode != 0:
            self.fail(
                "Could not establish authority-snapshot ancestry against candidate HEAD"
            )

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
                f"Current authority snapshot: `{commit}`, reconciled "
                f"{meta.get('captured_at_utc')}."
            )
            if expected_line not in playbook:
                self.fail(
                    "HUB_UPDATE_PLAYBOOK.md authority snapshot/time does not match metadata"
                )

        pinned_links: list[tuple[str, str]] = []
        invalid_blob_links: list[str] = []

        def collect_links(value: Any) -> None:
            if isinstance(value, dict):
                for child in value.values():
                    collect_links(child)
            elif isinstance(value, list):
                for child in value:
                    collect_links(child)
            elif isinstance(value, str):
                target = self.carbon_blob_target(value)
                if target is None:
                    return
                revision, path = target
                pure = PurePosixPath(path)
                if (
                    not re.fullmatch(r"[0-9a-f]{40}", revision)
                    or not path
                    or pure.is_absolute()
                    or ".." in pure.parts
                    or "\\" in path
                ):
                    invalid_blob_links.append(value)
                    return
                pinned_links.append((revision, path))

        collect_links(self.data)
        collect_links(self.event_bundle)
        if invalid_blob_links:
            self.fail(
                "Carbon blob URLs must use an exact lowercase 40-character commit "
                "and a safe repository path: "
                + ", ".join(sorted(set(invalid_blob_links)))
            )
        pinned_shas = {sha for sha, _ in pinned_links}
        paths_by_revision: dict[str, set[str]] = {}
        for revision in sorted(pinned_shas):
            resolved_pin = self.git(
                "rev-parse",
                "--verify",
                f"{revision}^{{commit}}",
                allow_failure=True,
            )
            if (
                resolved_pin.returncode != 0
                or resolved_pin.stdout.strip().lower() != revision
            ):
                self.fail(
                    f"Pinned Carbon blob revision does not resolve exactly: {revision}"
                )
                continue
            pin_ancestry = self.git(
                "merge-base",
                "--is-ancestor",
                revision,
                commit,
                allow_failure=True,
            )
            if pin_ancestry.returncode == 1:
                self.fail(
                    "Pinned Carbon blob revisions must equal or precede "
                    f"meta.authority_snapshot_commit: {revision}"
                )
                continue
            if pin_ancestry.returncode != 0:
                self.fail(
                    "Could not establish pinned Carbon blob ancestry for " f"{revision}"
                )
                continue
            tree = self.git(
                "ls-tree",
                "-r",
                "-z",
                "--name-only",
                revision,
                allow_failure=True,
            )
            if tree.returncode != 0:
                self.fail(f"Cannot read pinned Carbon blob tree {revision}")
                continue
            paths_by_revision[revision] = {
                path for path in tree.stdout.split("\0") if path
            }
        missing_pins = sorted(
            f"{sha}:{path}"
            for sha, path in set(pinned_links)
            if path not in paths_by_revision.get(sha, set())
        )
        if missing_pins:
            self.fail(
                "Pinned Carbon blob URLs do not resolve at their exact revisions: "
                + ", ".join(missing_pins)
            )

        linked_paths = {
            path
            for sha, path in pinned_links
            if sha == commit and path in paths_by_revision.get(sha, set())
        }
        sources = self.data.get("sources", {})
        current = self.data.get("current", {})

        if isinstance(sources, dict):
            for source_id, source in sources.items():
                self.current_authority_target(
                    source.get("url") if isinstance(source, dict) else None,
                    commit,
                    f"sources.{source_id}",
                )

        def source_target(source_id: str) -> str | None:
            source = sources.get(source_id, {}) if isinstance(sources, dict) else {}
            target = self.carbon_blob_target(
                source.get("url") if isinstance(source, dict) else None
            )
            return target[1] if target is not None else None

        if source_target("current_wave") != ".agent/WAVE.md":
            self.fail("sources.current_wave must pin .agent/WAVE.md")
        controlling_register = (
            current.get("controlling_register") if isinstance(current, dict) else None
        )
        if source_target("controlling_board") != controlling_register:
            self.fail("sources.controlling_board must pin current.controlling_register")

        selected_ticket = str(current.get("ticket", ""))
        selected = next(
            (
                item
                for item in self.data.get("tickets", [])
                if item.get("id") == selected_ticket
            ),
            None,
        )
        if selected is not None:
            for index, link in enumerate(selected.get("repo_links", [])):
                if isinstance(link, dict):
                    self.current_authority_target(
                        link.get("url"),
                        commit,
                        f"selected ticket repo_links[{index}]",
                    )
            repo_ticket_targets = {
                target[1]
                for link in selected.get("repo_links", [])
                if isinstance(link, dict)
                and "repo ticket" in str(link.get("label", "")).lower()
                and (target := self.carbon_blob_target(link.get("url"))) is not None
            }
            if repo_ticket_targets != {selected.get("repo_path")}:
                self.fail(
                    "Selected-ticket Repo ticket link must pin the selected repo_path"
                )
        active_wave = next(
            (
                item
                for item in self.data.get("waves", [])
                if item.get("id") == current.get("wave")
            ),
            None,
        )
        if isinstance(active_wave, dict):
            for index, link in enumerate(active_wave.get("repo_links", [])):
                if isinstance(link, dict):
                    self.current_authority_target(
                        link.get("url"),
                        commit,
                        f"active wave repo_links[{index}]",
                    )
            if controlling_register:
                wave_link_paths = {
                    target[1]
                    for link in active_wave.get("repo_links", [])
                    if isinstance(link, dict)
                    and (target := self.carbon_blob_target(link.get("url"))) is not None
                }
                if controlling_register not in wave_link_paths:
                    self.fail(
                        "The active wave record must link to current.controlling_register"
                    )

        content_cache: dict[tuple[str, str], str | None] = {}

        def revision_content(revision: str, path: str) -> str | None:
            key = (revision, path)
            if key not in content_cache:
                result = self.git("show", f"{revision}:{path}", allow_failure=True)
                content_cache[key] = result.stdout if result.returncode == 0 else None
            return content_cache[key]

        for check in self.data.get("authority_source_checks", []):
            path = str(check.get("path", ""))
            check_id = str(check.get("id", path))
            if path not in linked_paths:
                self.fail(
                    f"authority source check {check_id} path is not represented by a "
                    "blob link pinned to authority_snapshot_commit"
                )
                continue
            snapshot_content = revision_content(commit, path)
            head_content = revision_content("HEAD", path)
            if snapshot_content is None:
                self.fail(
                    f"authority source check {check_id} cannot read {path} at the snapshot"
                )
                continue
            if head_content is None:
                self.fail(
                    f"authority source check {check_id} cannot read {path} at candidate HEAD"
                )
                continue
            for marker in check.get("required_markers", []):
                if marker not in snapshot_content:
                    self.fail(
                        f"authority source check {check_id} marker is absent from "
                        f"{path} at authority_snapshot_commit: {marker!r}"
                    )
                if marker not in head_content:
                    self.fail(
                        f"authority source check {check_id} marker is absent from "
                        f"{path} at candidate HEAD: {marker!r}"
                    )

        post_snapshot = self.git(
            "diff",
            "--no-renames",
            "--name-only",
            "-z",
            "--diff-filter=ACDMRTUXB",
            f"{commit}..HEAD",
        )
        post_snapshot_paths = {
            path.replace("\\", "/") for path in post_snapshot.stdout.split("\0") if path
        }
        stale_structural: list[str] = []
        stale_unmapped: list[str] = []
        for path in post_snapshot_paths:
            impact = self.classify_impact(path, comparison_base=commit)
            if impact is None:
                continue
            if impact["impact_class"] == "map_structural":
                stale_structural.append(path)
            elif impact["impact_class"] == "unmapped_authority":
                stale_unmapped.append(path)
        if stale_structural:
            self.fail(
                "Map-structural authority changed after authority_snapshot_commit; "
                "create a new authority commit and repin the Hub: "
                + ", ".join(sorted(stale_structural))
            )
        if stale_unmapped:
            self.fail(
                "Unmapped authority changed after authority_snapshot_commit; add an "
                "explicit impact-policy owner, create a new authority commit, and "
                "repin the Hub: " + ", ".join(sorted(stale_unmapped))
            )
        if selected is not None:
            for link in selected.get("repo_links", []):
                if not isinstance(link, dict):
                    continue
                label = str(link.get("label", "")).lower()
                if "repo ticket" not in label and "evidence" not in label:
                    continue
                parsed = urllib.parse.urlsplit(str(link.get("url", "")))
                match = re.fullmatch(
                    r"/carbonphysicsai/Carbon/blob/([0-9a-f]{40})/(.+)",
                    parsed.path,
                )
                if not match or match.group(1) != commit:
                    self.fail(
                        f"Selected-ticket {label} link is not pinned to the authority snapshot"
                    )
                    continue
                detail = self.git(
                    "show", f"{commit}:{match.group(2)}", allow_failure=True
                )
                if detail.returncode != 0 or selected_ticket not in detail.stdout:
                    self.fail(
                        f"Selected-ticket {label} link does not resolve to content "
                        f"describing {selected_ticket} at the authority snapshot"
                    )

        merged_pr = re.search(r"Merge pull request #(\d+)\b", subject)
        stage_pr = re.search(
            r"\bPR #(\d+)\b", str(self.data.get("current", {}).get("stage", ""))
        )
        if merged_pr and stage_pr and merged_pr.group(1) != stage_pr.group(1):
            self.fail(
                "current.stage PR evidence does not match the recorded snapshot merge commit"
            )

    @staticmethod
    def env_enabled(name: str) -> bool:
        return os.environ.get(name, "").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

    def load_json_file(self, path: Path, label: str) -> dict[str, Any] | None:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            self.fail(f"{label} is not readable JSON: {exc}")
            return None
        if not isinstance(value, dict):
            self.fail(f"{label} must contain a JSON object")
            return None
        return value

    def validate_live_pr_checkout(self, pull_request: dict[str, Any]) -> None:
        """Bind live declaration validation to the exact checked-out PR head."""
        head = pull_request.get("head")
        base = pull_request.get("base")
        head_sha = head.get("sha") if isinstance(head, dict) else None
        base_sha = base.get("sha") if isinstance(base, dict) else None
        invalid_identity = False
        if not isinstance(head_sha, str) or not re.fullmatch(r"[0-9a-f]{40}", head_sha):
            self.fail(
                "Live pull request head.sha must be an exact lowercase commit SHA"
            )
            invalid_identity = True
        if not isinstance(base_sha, str) or not re.fullmatch(r"[0-9a-f]{40}", base_sha):
            self.fail(
                "Live pull request base.sha must be an exact lowercase commit SHA"
            )
            invalid_identity = True
        if invalid_identity:
            return
        try:
            checked_out = self.git("rev-parse", "--verify", "HEAD^{commit}")
        except RuntimeError as exc:
            self.fail(f"Cannot resolve candidate HEAD for live PR validation: {exc}")
            return
        candidate_head = checked_out.stdout.strip().lower()
        if candidate_head != head_sha:
            self.fail(
                "Candidate HEAD does not equal the current live pull request head: "
                f"HEAD={candidate_head}, live={head_sha}"
            )

    def load_github_event(self) -> None:
        live_required = self.env_enabled("HUB_REQUIRE_LIVE_PR") or (
            self.env_enabled("GITHUB_ACTIONS")
            and os.environ.get("GITHUB_EVENT_NAME") == "pull_request"
        )
        event_path = os.environ.get("GITHUB_EVENT_PATH")
        if not event_path:
            if live_required:
                self.fail(
                    "Live pull request validation requires GITHUB_EVENT_PATH to "
                    "authenticate the pull request identity"
                )
            return
        value = self.load_json_file(Path(event_path), "GITHUB_EVENT_PATH")
        if value is None:
            return
        self.historical_github_event = value
        self.github_event = value
        historical_pr = value.get("pull_request")
        if not isinstance(historical_pr, dict):
            if live_required:
                self.fail(
                    "Live pull request validation requires a pull_request object "
                    "in GITHUB_EVENT_PATH"
                )
            return

        live_path = os.environ.get("HUB_LIVE_PR_PATH")
        if not live_path:
            if live_required:
                self.fail(
                    "Live pull request metadata is required; fetch the current GitHub "
                    "pull request and set HUB_LIVE_PR_PATH"
                )
            return
        live_value = self.load_json_file(Path(live_path), "HUB_LIVE_PR_PATH")
        if live_value is None:
            return
        live_pr = live_value.get("pull_request", live_value)
        if not isinstance(live_pr, dict):
            self.fail(
                "HUB_LIVE_PR_PATH must contain a GitHub pull request object or a "
                "pull_request wrapper"
            )
            return
        event_number = value.get("number")
        nested_number = historical_pr.get("number")
        valid_event_numbers = [
            number
            for number in (event_number, nested_number)
            if isinstance(number, int) and not isinstance(number, bool) and number > 0
        ]
        if not valid_event_numbers:
            self.fail(
                "GITHUB_EVENT_PATH must contain an exact positive numeric pull "
                "request identity before live metadata can be trusted"
            )
            return
        if len(set(valid_event_numbers)) != 1:
            self.fail("GITHUB_EVENT_PATH contains conflicting pull request identities")
            return
        historical_number = valid_event_numbers[0]
        live_number = live_pr.get("number")
        if (
            not isinstance(live_number, int)
            or isinstance(live_number, bool)
            or live_number <= 0
        ):
            self.fail(
                "Live pull request metadata must include its exact positive "
                "numeric number"
            )
            return
        if historical_number != live_number:
            self.fail(
                "Live pull request metadata does not match the workflow event: "
                f"event=#{historical_number}, live=#{live_number}"
            )
            return
        historical_head = historical_pr.get("head")
        historical_head_sha = (
            historical_head.get("sha") if isinstance(historical_head, dict) else None
        )
        if not isinstance(historical_head_sha, str) or not re.fullmatch(
            r"[0-9a-f]{40}", historical_head_sha
        ):
            self.fail(
                "GITHUB_EVENT_PATH pull_request.head.sha must be an exact lowercase "
                "commit SHA before a live declaration can be attached to the run"
            )
            return
        live_head = live_pr.get("head")
        live_head_sha = live_head.get("sha") if isinstance(live_head, dict) else None
        if not isinstance(live_head_sha, str) or not re.fullmatch(
            r"[0-9a-f]{40}", live_head_sha
        ):
            self.fail(
                "Live pull request head.sha must be an exact lowercase commit SHA"
            )
            return
        if historical_head_sha != live_head_sha:
            self.fail(
                "Workflow event head does not equal the current live pull request "
                f"head: event={historical_head_sha}, live={live_head_sha}"
            )
            return
        self.github_event = {**value, "pull_request": live_pr}
        self.live_pr_loaded = True
        self.validate_live_pr_checkout(live_pr)

    def collect_diff(self) -> None:
        base = None if self.live_pr_loaded else os.environ.get("HUB_DIFF_BASE_SHA")
        if self.github_event and (not base or self.live_pr_loaded):
            pull_request = self.github_event.get("pull_request", {})
            if isinstance(pull_request, dict):
                base_record = pull_request.get("base", {})
                if isinstance(base_record, dict):
                    base = str(base_record.get("sha", "")) or None
            if not base:
                before = self.github_event.get("before")
                base = str(before) if isinstance(before, str) and before else None
        if not base:
            self.warn(
                "HUB_DIFF_BASE_SHA is unavailable; diff/change-event coverage was skipped"
            )
            return
        if not re.fullmatch(r"[0-9a-fA-F]{7,64}", base):
            self.fail("HUB_DIFF_BASE_SHA must be a hexadecimal Git object ID")
            return
        try:
            resolved_base = self.git("rev-parse", "--verify", f"{base}^{{commit}}")
            self.diff_base_sha = resolved_base.stdout.strip().lower()
            changed: set[str] = set()
            commands = (
                (
                    "diff",
                    "--no-renames",
                    "--name-only",
                    "-z",
                    "--diff-filter=ACDMRTUXB",
                    f"{self.diff_base_sha}...HEAD",
                ),
                (
                    "diff",
                    "--no-renames",
                    "--name-only",
                    "-z",
                    "--diff-filter=ACDMRTUXB",
                ),
                (
                    "diff",
                    "--cached",
                    "--no-renames",
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
                    "--no-renames",
                    "--name-only",
                    "-z",
                    "--diff-filter=D",
                    f"{self.diff_base_sha}...HEAD",
                ),
                ("diff", "--no-renames", "--name-only", "-z", "--diff-filter=D"),
                (
                    "diff",
                    "--cached",
                    "--no-renames",
                    "--name-only",
                    "-z",
                    "--diff-filter=D",
                ),
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
                f"{self.diff_base_sha}:{HUB_RELATIVE.as_posix()}/data/change_events.json",
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
                f"{self.diff_base_sha}:{HUB_RELATIVE.as_posix()}/data/hub_data_v2.json",
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
                or self.semantic_data_changed_between(self.base_hub_data, self.data)
            )
        except RuntimeError as exc:
            self.fail(f"Cannot evaluate HUB_DIFF_BASE_SHA diff coverage: {exc}")

    def authority_semantics_changed(
        self, path: str, selector: str, comparison_base: str | None = None
    ) -> bool:
        base = comparison_base or self.diff_base_sha
        if base is None:
            return True
        prior = self.git("show", f"{base}:{path}", allow_failure=True)
        current_path = self.repo_root / Path(*PurePosixPath(path).parts)
        if prior.returncode != 0 or not current_path.is_file():
            return True
        try:
            current = current_path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            return True
        if selector == "wave_register_fields_change":
            before = self.parse_current_authority(prior.stdout, f"diff-base {path}")
            after = self.parse_current_authority(current, f"candidate {path}")
            if before is None or after is None:
                return True
            keys = (
                "wave",
                "state",
                "register",
                "register_version",
                "ticket",
                "ticket_status",
                "next_ticket",
                "closed_waves",
            )
            return tuple(before[key] for key in keys) != tuple(
                after[key] for key in keys
            )
        if selector == "ticket_board_fields_change":
            before_version, before_rows = self.parse_ticket_board(
                prior.stdout, f"diff-base {path}"
            )
            after_version, after_rows = self.parse_ticket_board(
                current, f"candidate {path}"
            )

            return self.board_signature(
                before_version, before_rows
            ) != self.board_signature(after_version, after_rows)
        if selector == "ticket_record_fields_change":
            return self.ticket_record_fields(prior.stdout) != self.ticket_record_fields(
                current
            )
        return True

    def classify_impact(
        self, path: str, *, comparison_base: str | None = None
    ) -> dict[str, str] | None:
        if comparison_base is None and path in self.impact_cache:
            return self.impact_cache[path]
        policy = self.data.get("impact_policy", {})
        rules = policy.get("rules", []) if isinstance(policy, dict) else []
        for rule in rules:
            if not isinstance(rule, dict):
                continue
            match_type = rule.get("match_type")
            pattern = str(rule.get("path", ""))
            matched = False
            if match_type == "exact":
                matched = path == pattern
            elif match_type == "prefix":
                matched = path.startswith(pattern)
            elif match_type == "wave_board":
                matched = re.fullmatch(r"\.agent/WAVE_([A-N])\.md", path) is not None
            elif match_type == "ticket_record":
                matched = path.startswith(pattern)
            if not matched:
                continue
            raw_ref = str(rule.get("map_ref", ""))
            map_ref = raw_ref
            if raw_ref == "CURRENT_WAVE":
                current_wave = str(self.data.get("current", {}).get("wave", ""))
                map_ref = f"WAVE-{current_wave}" if current_wave else ""
            elif raw_ref == "WAVE_FROM_PATH":
                match = re.fullmatch(r"\.agent/WAVE_([A-N])\.md", path)
                map_ref = f"WAVE-{match.group(1)}" if match else ""
            elif raw_ref == "TICKET_FROM_PATH":
                name = Path(path).name.upper()
                map_ref = ""
                tickets = [
                    item
                    for item in self.data.get("tickets", [])
                    if isinstance(item, dict) and isinstance(item.get("id"), str)
                ]
                for ticket in sorted(
                    tickets, key=lambda item: len(str(item.get("id"))), reverse=True
                ):
                    ticket_id = str(ticket["id"])
                    if name == ticket_id or name.startswith(
                        (ticket_id + "_", ticket_id + ".")
                    ):
                        map_ref = f"WAVE-{ticket.get('wave')}/{ticket_id}"
                        break
            if not map_ref:
                result = {
                    "impact_class": "unmapped_authority",
                    "map_ref": "",
                    "rule_id": str(rule.get("id", "unknown")),
                }
                if comparison_base is None:
                    self.impact_cache[path] = result
                return result
            impact_class = str(rule.get("impact_class", ""))
            selector = rule.get("structural_when")
            if isinstance(selector, str) and self.authority_semantics_changed(
                path, selector, comparison_base
            ):
                impact_class = "map_structural"
            result = {
                "impact_class": impact_class,
                "map_ref": map_ref,
                "rule_id": str(rule.get("id", "unknown")),
            }
            if comparison_base is None:
                self.impact_cache[path] = result
            return result
        roots = policy.get("authority_roots", []) if isinstance(policy, dict) else []
        if any(isinstance(root, str) and path.startswith(root) for root in roots):
            result = {
                "impact_class": "unmapped_authority",
                "map_ref": "",
                "rule_id": "unmapped-authority-root",
            }
            if comparison_base is None:
                self.impact_cache[path] = result
            return result
        if comparison_base is None:
            self.impact_cache[path] = None
        return None

    def impact_ref(self, path: str) -> str | None:
        impact = self.classify_impact(path)
        if impact is None or impact["impact_class"] == "unmapped_authority":
            return None
        return impact["map_ref"]

    def semantic_change_map_refs(self) -> set[str]:
        """Return map owners whose Hub semantics differ from the diff base."""
        if self.base_hub_data is None:
            return set()
        base = self.base_hub_data
        current = self.data
        base_view, current_view = self.paired_semantic_data_views(base, current)
        refs: set[str] = set()
        base_current = base_view.get("current", {})
        now_current = current_view.get("current", {})
        if base_current != now_current:
            wave = now_current.get("wave") if isinstance(now_current, dict) else None
            ticket = (
                now_current.get("ticket") if isinstance(now_current, dict) else None
            )
            if isinstance(wave, str) and isinstance(ticket, str):
                refs.add(f"WAVE-{wave}/{ticket}")
            elif isinstance(wave, str):
                refs.add(f"WAVE-{wave}")

        def records_by_id(value: Any) -> dict[str, Any]:
            if not isinstance(value, list):
                return {}
            return {
                str(item["id"]): item
                for item in value
                if isinstance(item, dict) and isinstance(item.get("id"), str)
            }

        base_waves = records_by_id(base_view.get("waves"))
        now_waves = records_by_id(current_view.get("waves"))
        for wave_id in set(base_waves) | set(now_waves):
            if base_waves.get(wave_id) != now_waves.get(wave_id):
                refs.add(f"WAVE-{wave_id}")
        base_tickets = records_by_id(base_view.get("tickets"))
        now_tickets = records_by_id(current_view.get("tickets"))
        for ticket_id in set(base_tickets) | set(now_tickets):
            if base_tickets.get(ticket_id) == now_tickets.get(ticket_id):
                continue
            record = now_tickets.get(ticket_id) or base_tickets.get(ticket_id) or {}
            wave = record.get("wave") if isinstance(record, dict) else None
            if isinstance(wave, str):
                refs.add(f"WAVE-{wave}/{ticket_id}")

        system_sections = {
            "meta": "SYSTEM/DEVELOPMENT-HUB",
            "sources": "SYSTEM/DEVELOPMENT-HUB",
            "authority_source_checks": "SYSTEM/DEVELOPMENT-HUB",
            "authority_ceilings": "SYSTEM/MATURITY",
            "impact_policy": "SYSTEM/DEVELOPMENT-HUB/VALIDATION",
            "maturity": "SYSTEM/MATURITY",
            "change_paths": "SYSTEM/DEVELOPMENT-HUB",
            "glossary": "SYSTEM/DEVELOPMENT-HUB",
            "event_schema": "SYSTEM/DEVELOPMENT-HUB/VALIDATION",
        }
        for section, ref in system_sections.items():
            if base_view.get(section) != current_view.get(section):
                refs.add(ref)
        return refs

    @staticmethod
    def ref_covered(expected: str, actual: set[str]) -> bool:
        return any(
            value == expected
            or value.startswith(expected + "/")
            or expected.startswith(value + "/")
            for value in actual
        )

    def validate_delivery_declaration(self) -> None:
        """Validate the PR template's stable delivery and exact-tree contract."""
        if self.skip_pr_contract or self.github_event is None:
            return
        pull_request = self.github_event.get("pull_request")
        if not isinstance(pull_request, dict):
            return
        body = pull_request.get("body")
        if not isinstance(body, str):
            return

        fields: dict[str, str] = {}
        for field in REQUIRED_DELIVERY_FIELDS:
            field_pattern = (
                rf"^[ \t]*{re.escape(field)}[ \t]*:[ \t]*" r"([^\r\n]*?)[ \t]*\r?$"
            )
            matches = re.findall(
                field_pattern,
                body,
                flags=re.MULTILINE,
            )
            if len(matches) != 1:
                self.fail(f"PR body must contain exactly one completed {field} field")
                continue
            value = matches[0].strip()
            if not value or re.fullmatch(
                r"(?:TODO|TBD|<.*>|\[.*\]|<!--.*-->)",
                value,
                flags=re.IGNORECASE,
            ):
                self.fail(f"PR delivery field {field} must not be a placeholder")
                continue
            fields[field] = value

        for field, allowed in DELIVERY_STATUS_ENUMS.items():
            value = fields.get(field)
            if value is None:
                continue
            status = re.match(r"^([A-Z_]+)(?=$|[ \t:\-—])", value)
            if status is None or status.group(1) not in allowed:
                self.fail(f"{field} must begin with one of {sorted(allowed)!r}")

        mode = fields.get("DELIVERY_MODE")
        separate_reason = fields.get("SEPARATE_CONTRACT_PR_REASON")
        if mode not in {"SINGLE_TICKET_PR", "SEPARATE_CONTRACT_PR"}:
            self.fail("DELIVERY_MODE must be SINGLE_TICKET_PR or SEPARATE_CONTRACT_PR")
        elif mode == "SINGLE_TICKET_PR" and separate_reason != "NOT_APPLICABLE":
            self.fail(
                "SINGLE_TICKET_PR requires SEPARATE_CONTRACT_PR_REASON: "
                "NOT_APPLICABLE"
            )
        elif mode == "SEPARATE_CONTRACT_PR" and separate_reason is not None:
            self.validate_separate_contract_reason(separate_reason)

        for field in ("BASE", "FINAL_HEAD", "FINAL_TREE"):
            value = fields.get(field)
            if value is not None and not re.fullmatch(r"[0-9a-f]{40}", value):
                self.fail(f"{field} must be an exact lowercase 40-character Git ID")

        head = pull_request.get("head")
        base = pull_request.get("base")
        live_head = head.get("sha") if isinstance(head, dict) else None
        live_base = base.get("sha") if isinstance(base, dict) else None
        if isinstance(live_base, str) and fields.get("BASE") != live_base:
            self.fail(
                f"PR body BASE does not match the current live base SHA {live_base}"
            )
        if isinstance(live_head, str) and fields.get("FINAL_HEAD") != live_head:
            self.fail(
                f"PR body FINAL_HEAD does not match the current live head SHA {live_head}"
            )
        try:
            candidate_tree = self.git("rev-parse", "--verify", "HEAD^{tree}")
        except RuntimeError as exc:
            self.fail(f"Cannot resolve candidate FINAL_TREE: {exc}")
        else:
            tree = candidate_tree.stdout.strip().lower()
            if fields.get("FINAL_TREE") != tree:
                self.fail(
                    f"PR body FINAL_TREE does not match candidate HEAD tree {tree}"
                )

        scope = fields.get("CHANGE_SCOPE")
        if scope not in DELIVERY_CHANGE_SCOPES:
            self.fail(
                "CHANGE_SCOPE must be RUNTIME_FULL, CONTRACT_AUTHORITY, or "
                "DERIVED_DOCUMENTATION"
            )
        expected_scope = os.environ.get("HUB_EXPECTED_CHANGE_SCOPE")
        if expected_scope is not None:
            expected_scope = expected_scope.strip()
            if expected_scope not in DELIVERY_CHANGE_SCOPES:
                self.fail(
                    "HUB_EXPECTED_CHANGE_SCOPE must be one of "
                    f"{sorted(DELIVERY_CHANGE_SCOPES)!r}"
                )
            elif scope != expected_scope:
                self.fail(
                    "PR body CHANGE_SCOPE does not match the fail-closed preflight "
                    f"scope {expected_scope}"
                )
        if fields.get("DYNAMIC_COMPLETION_EVIDENCE") != "EXTERNAL":
            self.fail("DYNAMIC_COMPLETION_EVIDENCE must be EXTERNAL")
        receipt_location = fields.get("COMPLETION_RECEIPT_LOCATION")
        if receipt_location not in {None, "PENDING"} and (
            len(re.findall(r"[A-Za-z0-9]+", receipt_location)) < 4
            or re.search(
                r"\b(?:PR|pull(?:[ _-]+request)?|comment|issue(?:comment)?|"
                r"artifact|body)\b",
                receipt_location,
                flags=re.IGNORECASE,
            )
            is None
        ):
            self.fail(
                "COMPLETION_RECEIPT_LOCATION must name a concrete PR body/comment, "
                "issue, or retained artifact"
            )
        unresolved = fields.get("UNRESOLVED_THREADS")
        if unresolved is not None and not re.fullmatch(
            r"(?:0|[1-9][0-9]*|PENDING)", unresolved
        ):
            self.fail("UNRESOLVED_THREADS must be a non-negative integer or PENDING")
        for field in (
            "CODE_BEARING_COMMITS",
            "POST_FREEZE_TREE_CHANGES",
            "FULL_CI_RUNS",
        ):
            value = fields.get(field)
            if value is not None and not re.fullmatch(
                r"(?:0|[1-9][0-9]*|PENDING)", value
            ):
                self.fail(f"{field} must be a non-negative integer or PENDING")
        rerun_reason = fields.get("AVOIDABLE_RERUN_REASON")
        if rerun_reason is not None and (
            rerun_reason.upper() in {"NONE", "N/A", "NA", "NOT_APPLICABLE", "PENDING"}
            or len(re.findall(r"[A-Za-z0-9]+", rerun_reason)) < 4
        ):
            self.fail("AVOIDABLE_RERUN_REASON must be a completed, specific reason")

    def current_sequencing_authority_paths(self) -> set[str]:
        """Return the closed set eligible to authorize exceptional PR sequencing."""
        paths = set(ALWAYS_CURRENT_SEQUENCING_AUTHORITIES)
        current = self.data.get("current", {})
        if isinstance(current, dict):
            register = current.get("controlling_register")
            if isinstance(register, str):
                paths.add(register)
            selected_id = current.get("ticket")
            for ticket in self.data.get("tickets", []):
                if (
                    isinstance(ticket, dict)
                    and ticket.get("id") == selected_id
                    and isinstance(ticket.get("repo_path"), str)
                ):
                    paths.add(str(ticket["repo_path"]))
                    break
        return paths

    def validate_separate_contract_reason(self, reason: str) -> None:
        """Validate one closed separate-contract exception declaration."""
        normalized_size_reason = _normalize_delivery_prose(reason)
        if TICKET_SIZE_REASON.search(normalized_size_reason):
            self.fail("SEPARATE_CONTRACT_PR_REASON cannot use ticket size as rationale")
            return
        if reason in SEPARATE_CONTRACT_REASON_CODES:
            return
        match = AUTHORITATIVE_SEQUENCING_REASON.fullmatch(reason)
        if match is None:
            self.fail(
                "SEPARATE_CONTRACT_PR_REASON must be CONTRACT_ONLY_TICKET, "
                "CONCURRENT_DOWNSTREAM_IMMUTABLE_CONTRACT, "
                "CROSS_DOMAIN_PUBLIC_INTERFACE_FREEZE, or the exact "
                "AUTHORITATIVE_SEQUENCING authority/details form"
            )
            return

        authority_path, details = match.groups()
        if SEQUENCING_DETAILS_FORBIDDEN.search(details):
            self.fail(
                "AUTHORITATIVE_SEQUENCING DETAILS must be plain prose without "
                "Markdown or HTML metacharacters"
            )
            return
        pure = PurePosixPath(authority_path)
        if (
            pure.is_absolute()
            or ".." in pure.parts
            or authority_path != pure.as_posix()
        ):
            self.fail(
                "AUTHORITATIVE_SEQUENCING AUTHORITY must be a normalized "
                "repository-relative path"
            )
            return
        if authority_path not in self.current_sequencing_authority_paths():
            self.fail(
                "AUTHORITATIVE_SEQUENCING AUTHORITY must name a current "
                "sequencing authority file"
            )
            return
        tracked = self.git(
            "ls-files", "--error-unmatch", "--", authority_path, allow_failure=True
        )
        if tracked.returncode != 0 or tracked.stdout.splitlines() != [authority_path]:
            self.fail(
                "AUTHORITATIVE_SEQUENCING AUTHORITY must name a tracked current "
                "sequencing authority file"
            )
            return
        target = (self.repo_root / Path(*pure.parts)).resolve()
        if not _inside(self.repo_root, target) or not target.is_file():
            self.fail(
                "AUTHORITATIVE_SEQUENCING AUTHORITY is missing or escapes the "
                "repository"
            )
            return
        normalized_details = _normalize_delivery_prose(details)
        if len(normalized_details.split()) < 4:
            self.fail(
                "AUTHORITATIVE_SEQUENCING DETAILS must contain at least four words"
            )
            return
        authority_blob = self.git("show", f"HEAD:{authority_path}", allow_failure=True)
        if authority_blob.returncode != 0:
            self.fail(
                "Cannot read AUTHORITATIVE_SEQUENCING AUTHORITY from candidate "
                f"HEAD: {authority_path}"
            )
            return
        exception_markers = re.findall(
            r"^[ \t]*SEPARATE_CONTRACT_PR_EXCEPTION[ \t]*:[ \t]*" r"(.+?)[ \t]*\r?$",
            authority_blob.stdout,
            flags=re.MULTILINE,
        )
        if any(
            SEQUENCING_DETAILS_FORBIDDEN.search(marker) for marker in exception_markers
        ):
            self.fail(
                "SEPARATE_CONTRACT_PR_EXCEPTION marker values must be plain prose "
                "without Markdown or HTML metacharacters"
            )
            return
        normalized_markers = {
            _normalize_delivery_prose(marker) for marker in exception_markers
        }
        if normalized_details not in normalized_markers:
            self.fail(
                "AUTHORITATIVE_SEQUENCING DETAILS must normalize-equal one "
                "complete SEPARATE_CONTRACT_PR_EXCEPTION marker in the named "
                "current sequencing authority file at candidate HEAD"
            )

    def validate_structural_diff(self) -> None:
        if self.changed_paths is None:
            return
        classified = {
            path: impact
            for path in self.changed_paths
            if (impact := self.classify_impact(path)) is not None
        }
        unmapped = sorted(
            path
            for path, impact in classified.items()
            if impact["impact_class"] == "unmapped_authority"
        )
        for path in unmapped:
            self.fail(
                f"Authority path {path} has no explicit Development Hub impact-policy "
                "map owner; add a bounded ownership rule before this change can pass"
            )
        structural = {
            path: impact["map_ref"]
            for path, impact in classified.items()
            if impact["impact_class"] == "map_structural"
        }
        if not structural and not self.semantic_data_changed:
            return
        hub_data_path = f"{HUB_RELATIVE.as_posix()}/data/hub_data_v2.json"
        events_path = f"{HUB_RELATIVE.as_posix()}/data/change_events.json"
        if structural and hub_data_path not in self.changed_paths:
            self.fail(
                "Map-structural repository changes require an updated data/hub_data_v2.json"
            )
        if structural and not self.semantic_data_changed:
            self.fail(
                "Map-structural repository changes require a semantic Hub-data delta; "
                "snapshot pins or timestamps alone are not reconciliation"
            )
        if structural and events_path not in self.changed_paths:
            self.fail(
                "Map-structural repository changes require an updated data/change_events.json"
            )
        if self.semantic_data_changed and hub_data_path not in self.changed_paths:
            self.fail(
                "Semantic hub-data reconciliation differs from HUB_DIFF_BASE_SHA but "
                "data/hub_data_v2.json is not in the diff"
            )
        if self.semantic_data_changed and events_path not in self.changed_paths:
            self.fail(
                "Semantic hub_data_v2.json changes require an appended immutable "
                "change event"
            )
        if not self.new_event_ids:
            self.fail(
                "Map-structural or semantic hub changes require at least one new "
                "immutable change event relative to HUB_DIFF_BASE_SHA"
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
        required_refs = set(structural.values()) | self.semantic_change_map_refs()
        missing = sorted(
            {ref for ref in required_refs if not self.ref_covered(ref, covered)}
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
        classified = {
            path: impact
            for path in self.changed_paths
            if (impact := self.classify_impact(path)) is not None
        }
        structural = sorted(
            path
            for path, impact in classified.items()
            if impact["impact_class"] == "map_structural"
        )
        mapped_details = sorted(
            path
            for path, impact in classified.items()
            if impact["impact_class"] == "mapped_detail"
        )
        unmapped = sorted(
            path
            for path, impact in classified.items()
            if impact["impact_class"] == "unmapped_authority"
        )
        if unmapped:
            self.fail(
                "No PR declaration can bypass unmapped authority paths: "
                + ", ".join(unmapped)
            )
        declared_map_refs = set(
            re.findall(
                r"\b(?:WAVE-[A-N](?:/[A-Z0-9-]+)?|SYSTEM/[A-Z0-9-]+(?:/[A-Z0-9-]+)*)\b",
                detail,
            )
        )
        mapped_detail_refs = {
            classified[path]["map_ref"]
            for path in mapped_details
            if classified[path]["map_ref"]
        }
        new_event_coverage = {
            ref
            for event in self.events
            if event.get("event_id") in self.new_event_ids
            for ref in [
                event.get("map_ref"),
                *(
                    event.get("affects", [])
                    if isinstance(event.get("affects"), list)
                    else []
                ),
            ]
            if isinstance(ref, str)
        }
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
            missing_detail_refs = sorted(
                expected
                for expected in mapped_detail_refs
                if expected not in declared_map_refs
            )
            if missing_detail_refs:
                self.fail(
                    "HUB_IMPACT_NONE must name the mapped-detail owner refs: "
                    + ", ".join(missing_detail_refs)
                )
        if kind == "HUB_UPDATE_REQUIRED":
            missing_detail_refs = sorted(
                expected
                for expected in mapped_detail_refs
                if expected not in declared_map_refs
                and not self.ref_covered(expected, new_event_coverage)
            )
            if missing_detail_refs:
                self.fail(
                    "HUB_UPDATE_REQUIRED must name or newly event-cover the "
                    "mapped-detail owner refs: " + ", ".join(missing_detail_refs)
                )
            hub_changes = {
                path
                for path in self.changed_paths
                if path.startswith(f"{HUB_RELATIVE.as_posix()}/")
            }
            if not hub_changes:
                self.fail(
                    "HUB_UPDATE_REQUIRED must include at least one Development Hub file"
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
            policy_refs = self.data.get("impact_policy", {}).get("system_map_refs", [])
            if isinstance(policy_refs, list):
                known_map_refs.update(
                    ref for ref in policy_refs if isinstance(ref, str)
                )
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
                    "Map-structural repository changes require both hub source records; "
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
        self.validate_root_integration()
        self.load_github_event()
        self.collect_diff()
        self.validate_snapshot_metadata()
        self.validate_repository_authority()
        self.validate_structural_diff()
        self.validate_delivery_declaration()
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
        help="skip the pull-request body declaration check for non-PR validation workflows",
    )
    args = parser.parse_args(argv)
    return Validator(args.repo_root, skip_pr_contract=args.skip_pr_contract).run()


if __name__ == "__main__":
    sys.exit(main())
