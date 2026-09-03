#!/usr/bin/env python3
"""Validate Carbon's exact-head manual Codex/GPT review receipt."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

SHA_PATTERN = re.compile(r"[0-9a-f]{40}\Z")
MODEL_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9 ._:/+\-]{0,119}\Z")
EXPECTED_REPOSITORY = "carbonphysicsai/Carbon"
RECEIPT_FIELDS = (
    "CARBON_CODEX_GPT_REVIEW_RECEIPT",
    "REVIEWED_HEAD",
    "REVIEWED_TREE",
    "REVIEW_MODEL",
    "REVIEW_CONTEXT",
    "REVIEW_SCOPE",
    "FINDINGS_TOTAL",
    "VALID_FINDINGS_REPAIRED",
    "INVALID_FINDINGS_DISPOSITIONED",
    "UNRESOLVED_FINDINGS",
    "OUTCOME",
)


class ReviewGateError(RuntimeError):
    """The manual review evidence does not satisfy the delivery contract."""


def _load_json(path: Path, label: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ReviewGateError(f"cannot read {label}: {exc}") from exc


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ReviewGateError(f"{label} must be a JSON object")
    return value


def _sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or SHA_PATTERN.fullmatch(value) is None:
        raise ReviewGateError(f"{label} must be a lowercase 40-character SHA")
    return value


def _login(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 100:
        raise ReviewGateError(f"{label} must be a non-empty GitHub login")
    return value


def _user(value: Any, label: str) -> dict[str, Any]:
    user = _mapping(value, label)
    if user.get("type") != "User":
        raise ReviewGateError(f"{label} must be a human GitHub user")
    return user


def _actor(value: Any, label: str) -> dict[str, Any]:
    actor = _mapping(value, label)
    if actor.get("type") not in {"User", "Bot"}:
        raise ReviewGateError(f"{label} must be a GitHub user or bot")
    return actor


def _repository(record: Mapping[str, Any], label: str) -> None:
    repository = _mapping(record.get("repo"), f"{label} repository")
    if repository.get("full_name") != EXPECTED_REPOSITORY:
        raise ReviewGateError(f"{label} repository must be {EXPECTED_REPOSITORY}")


def _parse_receipt(body: Any) -> dict[str, str]:
    if not isinstance(body, str):
        raise ReviewGateError("approved review body must be text")
    lines = [line.strip() for line in body.splitlines()]
    starts = [
        index
        for index, line in enumerate(lines)
        if line == "CARBON_CODEX_GPT_REVIEW_RECEIPT: 1"
    ]
    if len(starts) != 1:
        raise ReviewGateError("approved review must contain exactly one v1 receipt")
    start = starts[0]
    block = lines[start : start + len(RECEIPT_FIELDS)]
    if len(block) != len(RECEIPT_FIELDS):
        raise ReviewGateError("Codex/GPT review receipt is incomplete")
    values: dict[str, str] = {}
    for expected, line in zip(RECEIPT_FIELDS, block, strict=True):
        prefix = f"{expected}: "
        if not line.startswith(prefix):
            raise ReviewGateError(
                f"Codex/GPT review receipt field order requires {expected}"
            )
        value = line[len(prefix) :]
        if not value:
            raise ReviewGateError(f"Codex/GPT review receipt field {expected} is empty")
        values[expected] = value
    return values


def _count(value: str, label: str) -> int:
    if not value.isascii() or not value.isdecimal():
        raise ReviewGateError(f"{label} must be a non-negative decimal integer")
    parsed = int(value)
    if str(parsed) != value:
        raise ReviewGateError(f"{label} must use canonical decimal form")
    return parsed


def _receipt_matches(values: Mapping[str, str], *, head: str, tree: str) -> None:
    if values["CARBON_CODEX_GPT_REVIEW_RECEIPT"] != "1":
        raise ReviewGateError("unsupported Codex/GPT review receipt version")
    if values["REVIEWED_HEAD"] != head or values["REVIEWED_TREE"] != tree:
        raise ReviewGateError("review receipt does not bind the live head and tree")
    if MODEL_PATTERN.fullmatch(values["REVIEW_MODEL"]) is None:
        raise ReviewGateError("REVIEW_MODEL is malformed")
    if values["REVIEW_CONTEXT"] != "FRESH_READ_ONLY":
        raise ReviewGateError("review must use a fresh read-only context")
    if values["REVIEW_SCOPE"] != "COMPLETE_PR_DIFF":
        raise ReviewGateError("review must cover the complete pull-request diff")
    total = _count(values["FINDINGS_TOTAL"], "FINDINGS_TOTAL")
    repaired = _count(values["VALID_FINDINGS_REPAIRED"], "VALID_FINDINGS_REPAIRED")
    dispositioned = _count(
        values["INVALID_FINDINGS_DISPOSITIONED"],
        "INVALID_FINDINGS_DISPOSITIONED",
    )
    unresolved = _count(values["UNRESOLVED_FINDINGS"], "UNRESOLVED_FINDINGS")
    if total != repaired + dispositioned:
        raise ReviewGateError("every review finding must have one disposition")
    if unresolved != 0:
        raise ReviewGateError("review receipt must report zero unresolved findings")
    if values["OUTCOME"] != "PASS":
        raise ReviewGateError("review outcome must be PASS")


def validate_review_gate(
    pull_request: Any, reviews: Any, commit: Any
) -> tuple[int, str, str, str]:
    """Return the accepted review id, reviewer, live head, and live tree."""

    pull = _mapping(pull_request, "pull request")
    if pull.get("state") != "open" or pull.get("draft") is not False:
        raise ReviewGateError("pull request must be open and non-draft")
    base = _mapping(pull.get("base"), "pull request base")
    if base.get("ref") != "main":
        raise ReviewGateError("pull request must target main")
    _repository(base, "pull request base")
    head_record = _mapping(pull.get("head"), "pull request head")
    _repository(head_record, "pull request head")
    head = _sha(head_record.get("sha"), "pull request head SHA")
    author = _login(
        _actor(pull.get("user"), "pull request author").get("login"),
        "pull request author",
    )

    commit_record = _mapping(commit, "head commit")
    if _sha(commit_record.get("sha"), "head commit SHA") != head:
        raise ReviewGateError("commit record does not match the live pull-request head")
    tree = _sha(
        _mapping(
            _mapping(commit_record.get("commit"), "head commit payload").get("tree"),
            "head commit tree",
        ).get("sha"),
        "head tree SHA",
    )

    if not isinstance(reviews, list):
        raise ReviewGateError("pull-request reviews must be a JSON array")
    failures: list[str] = []
    candidates: list[tuple[int, str]] = []
    for raw in reviews:
        if not isinstance(raw, dict) or raw.get("state") != "APPROVED":
            continue
        try:
            review_id = raw.get("id")
            if type(review_id) is not int or review_id <= 0:
                raise ReviewGateError("approved review has no positive id")
            reviewer = _login(
                _user(raw.get("user"), "approved reviewer").get("login"),
                "approved reviewer",
            )
            if reviewer.casefold() == author.casefold():
                raise ReviewGateError("pull-request author cannot approve the review")
            if _sha(raw.get("commit_id"), "approved review commit") != head:
                raise ReviewGateError("approved review is stale")
            values = _parse_receipt(raw.get("body"))
            _receipt_matches(values, head=head, tree=tree)
            candidates.append((review_id, reviewer))
        except ReviewGateError as exc:
            failures.append(str(exc))
    if not candidates:
        detail = "; ".join(sorted(set(failures))) or "no APPROVED review exists"
        raise ReviewGateError(
            "no non-author exact-head approval carries a valid Codex/GPT receipt: "
            + detail
        )
    review_id, reviewer = max(candidates)
    return review_id, reviewer, head, tree


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pull-request", type=Path, required=True)
    parser.add_argument("--reviews", type=Path, required=True)
    parser.add_argument("--commit", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        review_id, reviewer, head, tree = validate_review_gate(
            _load_json(args.pull_request, "pull request"),
            _load_json(args.reviews, "reviews"),
            _load_json(args.commit, "head commit"),
        )
    except ReviewGateError as exc:
        print(f"GPT review gate rejected the candidate: {exc}", file=sys.stderr)
        return 2
    print(
        "GPT review gate accepted exact-head review "
        f"{review_id} by {reviewer}: head {head}, tree {tree}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
