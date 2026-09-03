from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "dev" / "check_gpt_review_gate.py"
SPEC = importlib.util.spec_from_file_location("check_gpt_review_gate", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
review_gate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(review_gate)

HEAD = "a" * 40
TREE = "b" * 40
REPOSITORY = {"full_name": "carbonphysicsai/Carbon"}


def _pull() -> dict[str, object]:
    return {
        "number": 75,
        "state": "open",
        "draft": False,
        "user": {"login": "implementer", "type": "User"},
        "base": {"ref": "main", "sha": "c" * 40, "repo": REPOSITORY},
        "head": {"sha": HEAD, "repo": REPOSITORY},
    }


def _commit() -> dict[str, object]:
    return {"sha": HEAD, "commit": {"tree": {"sha": TREE}}}


def _receipt(**changes: object) -> str:
    values: dict[str, object] = {
        "CARBON_CODEX_GPT_REVIEW_RECEIPT": 1,
        "REVIEWED_HEAD": HEAD,
        "REVIEWED_TREE": TREE,
        "REVIEW_MODEL": "GPT-5 Codex",
        "REVIEW_CONTEXT": "FRESH_READ_ONLY",
        "REVIEW_SCOPE": "COMPLETE_PR_DIFF",
        "FINDINGS_TOTAL": 3,
        "VALID_FINDINGS_REPAIRED": 2,
        "INVALID_FINDINGS_DISPOSITIONED": 1,
        "UNRESOLVED_FINDINGS": 0,
        "OUTCOME": "PASS",
    }
    values.update(changes)
    lines = [f"{field}: {values[field]}" for field in review_gate.RECEIPT_FIELDS]
    return "Manual review completed.\n\n" + "\n".join(lines)


def _review(**changes: object) -> dict[str, object]:
    value: dict[str, object] = {
        "id": 123,
        "state": "APPROVED",
        "commit_id": HEAD,
        "user": {"login": "human-reviewer", "type": "User"},
        "body": _receipt(),
    }
    value.update(changes)
    return value


def test_accepts_non_author_exact_head_receipt() -> None:
    assert review_gate.validate_review_gate(_pull(), [_review()], _commit()) == (
        123,
        "human-reviewer",
        HEAD,
        TREE,
    )


def test_accepts_bot_pull_request_author() -> None:
    pull = _pull()
    pull["user"] = {"login": "Copilot", "type": "Bot"}
    assert review_gate.validate_review_gate(pull, [_review()], _commit()) == (
        123,
        "human-reviewer",
        HEAD,
        TREE,
    )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ({"state": "closed"}, "open and non-draft"),
        ({"draft": True}, "open and non-draft"),
        (
            {"base": {"ref": "develop", "repo": REPOSITORY}},
            "target main",
        ),
        ({"head": {"sha": "bad", "repo": REPOSITORY}}, "head SHA"),
    ],
)
def test_rejects_invalid_pull_request(
    mutation: dict[str, object], message: str
) -> None:
    pull = _pull()
    pull.update(mutation)
    with pytest.raises(review_gate.ReviewGateError, match=message):
        review_gate.validate_review_gate(pull, [_review()], _commit())


def test_rejects_commit_or_tree_mismatch() -> None:
    commit = _commit()
    commit["sha"] = "c" * 40
    with pytest.raises(review_gate.ReviewGateError, match="commit record"):
        review_gate.validate_review_gate(_pull(), [_review()], commit)


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"state": "COMMENTED"}, "no APPROVED"),
        ({"commit_id": "c" * 40}, "stale"),
        (
            {"user": {"login": "IMPLEMENTER", "type": "User"}},
            "author cannot approve",
        ),
        (
            {"user": {"login": "review-bot", "type": "Bot"}},
            "human GitHub user",
        ),
        ({"id": 0}, "positive id"),
        ({"body": ""}, "exactly one v1 receipt"),
    ],
)
def test_rejects_ineligible_approval(changes: dict[str, object], message: str) -> None:
    with pytest.raises(review_gate.ReviewGateError, match=message):
        review_gate.validate_review_gate(_pull(), [_review(**changes)], _commit())


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("REVIEWED_HEAD", "c" * 40, "live head and tree"),
        ("REVIEWED_TREE", "c" * 40, "live head and tree"),
        ("REVIEW_MODEL", "bad\nmodel", "field order"),
        ("REVIEW_CONTEXT", "IMPLEMENTING_CONTEXT", "fresh read-only"),
        ("REVIEW_SCOPE", "PARTIAL", "complete pull-request diff"),
        ("FINDINGS_TOTAL", 4, "every review finding"),
        ("UNRESOLVED_FINDINGS", 1, "zero unresolved"),
        ("OUTCOME", "CHANGE", "must be PASS"),
    ],
)
def test_rejects_invalid_receipt(field: str, value: object, message: str) -> None:
    review = _review(body=_receipt(**{field: value}))
    with pytest.raises(review_gate.ReviewGateError, match=message):
        review_gate.validate_review_gate(_pull(), [review], _commit())


def test_rejects_duplicate_or_reordered_receipt() -> None:
    duplicate = _receipt() + "\n\n" + _receipt()
    with pytest.raises(review_gate.ReviewGateError, match="exactly one"):
        review_gate.validate_review_gate(_pull(), [_review(body=duplicate)], _commit())
    lines = _receipt().splitlines()
    lines[-1], lines[-2] = lines[-2], lines[-1]
    with pytest.raises(review_gate.ReviewGateError, match="field order"):
        review_gate.validate_review_gate(
            _pull(), [_review(body="\n".join(lines))], _commit()
        )


def test_ignores_unrelated_reviews_and_selects_latest_valid_id() -> None:
    older = _review(id=123)
    newer = _review(id=456, user={"login": "second-human", "type": "User"})
    unrelated = _review(id=999, state="COMMENTED", body="not a receipt")
    assert review_gate.validate_review_gate(
        _pull(), [older, unrelated, newer], _commit()
    )[:2] == (456, "second-human")


@pytest.mark.parametrize("side", ["base", "head"])
def test_rejects_cross_repository_pull_request(side: str) -> None:
    pull = _pull()
    record = copy.deepcopy(pull[side])
    assert isinstance(record, dict)
    record["repo"] = {"full_name": "attacker/Fork"}
    pull[side] = record
    with pytest.raises(review_gate.ReviewGateError, match="repository must be"):
        review_gate.validate_review_gate(pull, [_review()], _commit())


def test_main_reads_files_and_reports_safe_failure(
    tmp_path: Path, capsys: object
) -> None:
    paths = {}
    for name, value in (
        ("pull", _pull()),
        ("reviews", [_review()]),
        ("commit", _commit()),
    ):
        path = tmp_path / f"{name}.json"
        path.write_text(json.dumps(value), encoding="utf-8")
        paths[name] = path
    assert (
        review_gate.main(
            [
                "--pull-request",
                str(paths["pull"]),
                "--reviews",
                str(paths["reviews"]),
                "--commit",
                str(paths["commit"]),
            ]
        )
        == 0
    )
    bad_reviews = copy.deepcopy([_review()])
    bad_reviews[0]["body"] = "secret provider text"
    paths["reviews"].write_text(json.dumps(bad_reviews), encoding="utf-8")
    assert (
        review_gate.main(
            [
                "--pull-request",
                str(paths["pull"]),
                "--reviews",
                str(paths["reviews"]),
                "--commit",
                str(paths["commit"]),
            ]
        )
        == 2
    )
    captured = capsys.readouterr()
    assert "secret provider text" not in captured.err
