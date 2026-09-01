"""Focused repository, commit-identity, and workstation-text hygiene tests."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CHECKER_PATH = REPOSITORY_ROOT / "scripts/dev/check_delivery_hygiene.py"


def _load_checker() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "check_delivery_hygiene", CHECKER_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


checker = _load_checker()


def _git(repository: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *arguments],
        cwd=repository,
        check=False,
        capture_output=True,
        text=True,
    )


def _init(repository: Path, *, email: str = "carbon-test@example.invalid") -> str:
    repository.mkdir()
    for arguments in (
        ("init", "--quiet"),
        ("config", "user.name", "Carbon Test"),
        ("config", "user.email", email),
        ("config", "commit.gpgsign", "false"),
    ):
        process = _git(repository, *arguments)
        assert process.returncode == 0, process.stderr
    (repository / "tracked.txt").write_text("clean\n", encoding="utf-8")
    assert _git(repository, "add", "--all").returncode == 0
    commit = _git(repository, "commit", "--quiet", "-m", "base")
    assert commit.returncode == 0, commit.stderr
    return _git(repository, "rev-parse", "HEAD").stdout.strip()


def _scan(text: str):
    return checker.scan_text(
        text,
        path="fixture.txt",
        source="fixture",
        allowlist=checker.Allowlist(),
    )


def test_paths_cover_posix_windows_unicode_and_slash_variants() -> None:
    values = (
        "/Users/alice/project",
        "/home/josé/src",
        r"C:\Users\Zoë\repo",
        "D:/Users/Δelta/repo",
        r"E:/Users\mixed/repo",
    )
    for value in values:
        findings = _scan(value)
        assert any(item.kind == "host path" for item in findings), value


def test_local_email_and_machine_hostnames_are_rejected() -> None:
    values = (
        "person@buildhost.local",
        "host.local",
        "buildhost.local",
        "nicks-MacBook-Pro-3.local",
        "DESKTOP-A1B2C3",
        "hostname: plainhost.local",
    )
    for value in values:
        assert _scan(value), value


def test_explicit_placeholders_and_nearby_prose_are_not_false_positives() -> None:
    text = (
        "/home/<user>/src/Carbon\n"
        "/Users/<username>/src/Carbon\n"
        "C:\\Users\\<username>\\src\\Carbon\n"
        "https://example.com/users/alice\n"
        "/opt/home/alice\n"
        "home/alice\n"
        "MacBook Pro compatibility is not claimed.\n"
        "dev@example.com\n"
        "threading.local is a program attribute, not a host\n"
        "a config.locality setting and a local variable"
    )
    assert _scan(text) == ()


def test_exact_text_allowlist_does_not_widen_path_or_value() -> None:
    allowed = checker.Allowlist(text=frozenset({("fixture.txt", "/Users/alice")}))
    assert (
        checker.scan_text(
            "/Users/alice/project",
            path="fixture.txt",
            source="fixture",
            allowlist=allowed,
        )
        == ()
    )
    assert checker.scan_text(
        "/Users/alicia/project",
        path="fixture.txt",
        source="fixture",
        allowlist=allowed,
    )
    assert checker.scan_text(
        "/Users/alice/project",
        path="other.txt",
        source="fixture",
        allowlist=allowed,
    )


def test_changed_text_and_optional_all_tree_are_distinct(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    base = _init(repository)
    (repository / "tracked.txt").write_text(
        "legacy /Users/legacy-owner/path\n", encoding="utf-8"
    )
    assert _git(repository, "add", "tracked.txt").returncode == 0
    assert _git(repository, "commit", "--quiet", "-m", "legacy fixture").returncode == 0
    comparison = _git(repository, "rev-parse", "HEAD").stdout.strip()

    assert checker.check_delivery_hygiene(repository, comparison) == ()
    findings = checker.check_delivery_hygiene(repository, comparison, all_tree=True)
    assert any(item.value == "/Users/legacy-owner" for item in findings)
    assert base != comparison


def test_worktree_text_and_introduced_identity_are_checked(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    base = _init(repository)
    assert (
        _git(repository, "config", "user.email", "tester@buildhost.local").returncode
        == 0
    )
    (repository / "tracked.txt").write_text("substantive\n", encoding="utf-8")
    assert _git(repository, "add", "tracked.txt").returncode == 0
    assert (
        _git(repository, "commit", "--quiet", "-m", "substantive change").returncode
        == 0
    )
    (repository / "tracked.txt").write_text(
        "uncommitted /home/workstation-owner/data\n", encoding="utf-8"
    )

    findings = checker.check_delivery_hygiene(repository, base)
    identity_sources = {item.source for item in findings if item.kind == ".local email"}
    assert {"author", "committer"} <= identity_sources
    assert any(item.value == "/home/workstation-owner" for item in findings)


def test_empty_evidence_only_and_forbidden_intent_commits_fail(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    base = _init(repository)
    empty = _git(repository, "commit", "--allow-empty", "--quiet", "-m", "empty")
    assert empty.returncode == 0, empty.stderr
    evidence = repository / ".agent/evidence/wave_b/fixture.md"
    evidence.parent.mkdir(parents=True)
    evidence.write_text("stable fixture\n", encoding="utf-8")
    assert _git(repository, "add", "--all").returncode == 0
    assert _git(repository, "commit", "--quiet", "-m", "evidence only").returncode == 0
    (repository / "tracked.txt").write_text("real change\n", encoding="utf-8")
    assert _git(repository, "add", "tracked.txt").returncode == 0
    assert (
        _git(repository, "commit", "--quiet", "-m", "retrigger validation").returncode
        == 0
    )

    kinds = {item.kind for item in checker.check_delivery_hygiene(repository, base)}
    assert "empty introduced commit" in kinds
    assert "evidence-only introduced commit" in kinds
    assert "forbidden completion-only commit intent" in kinds


def test_substantive_subject_that_mentions_forbidden_phrase_is_allowed(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    base = _init(repository)
    (repository / "tracked.txt").write_text("real change\n", encoding="utf-8")
    assert _git(repository, "add", "tracked.txt").returncode == 0
    commit = _git(
        repository,
        "commit",
        "--quiet",
        "-m",
        "Prevent retrigger validation commits with live metadata",
    )
    assert commit.returncode == 0, commit.stderr

    assert checker.check_delivery_hygiene(repository, base) == ()


def test_ticket_prefixed_completion_only_subject_is_rejected(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    base = _init(repository)
    (repository / "tracked.txt").write_text("real change\n", encoding="utf-8")
    assert _git(repository, "add", "tracked.txt").returncode == 0
    commit = _git(
        repository,
        "commit",
        "--quiet",
        "-m",
        "B-01F: record successful CI",
    )
    assert commit.returncode == 0, commit.stderr

    kinds = {item.kind for item in checker.check_delivery_hygiene(repository, base)}
    assert "forbidden completion-only commit intent" in kinds


def test_commit_allowlist_requires_full_sha_rule_and_reason(tmp_path: Path) -> None:
    allowlist_path = tmp_path / "allowlist.txt"
    commit = "a" * 40
    allowlist_path.write_text(
        f"commit\t{commit}\tempty\tReviewed migration exception.\n",
        encoding="utf-8",
    )
    allowlist = checker.load_allowlist(allowlist_path)
    assert allowlist.allows_commit(commit, "empty")
    assert not allowlist.allows_commit(commit, "message")
