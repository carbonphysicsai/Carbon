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
        "a config.locality setting and a local variable"
    )
    assert _scan(text) == ()


def test_all_standalone_local_hosts_require_an_exact_allowance() -> None:
    for value in ("alice.local", "josé.local", "lab.segment.local"):
        assert any(item.kind == "workstation hostname" for item in _scan(value))

    allowed = checker.Allowlist(
        text=frozenset({("fixture.txt", "threading.local")})
    )
    assert (
        checker.scan_text(
            "threading.local is a program attribute",
            path="fixture.txt",
            source="fixture",
            allowlist=allowed,
        )
        == ()
    )


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
    subjects = (
        "Prevent retrigger validation commits with live metadata",
        "record successful CI regression protections",
        "feat: record merge evidence rejection logic",
    )
    for index, subject in enumerate(subjects, start=1):
        (repository / "tracked.txt").write_text(
            f"real change {index}\n",
            encoding="utf-8",
        )
        assert _git(repository, "add", "tracked.txt").returncode == 0
        commit = _git(repository, "commit", "--quiet", "-m", subject)
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


def test_qualified_completion_only_subjects_on_authority_paths_are_rejected(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    base = _init(repository)
    authority = repository / ".agent/WAVE.md"
    authority.parent.mkdir(parents=True)
    subjects = (
        "docs: record successful CI for final head",
        "docs(B-01F): record merge evidence after normal merge",
        "chore: B-01F: retrigger validation for the current PR",
        "record final review evidence on exact head",
        "evidence seal from retained run",
        "docs: record successful CI!",
        "B-01F: evidence seal...",
    )
    for index, subject in enumerate(subjects, start=1):
        authority.write_text(f"stable authority revision {index}\n", encoding="utf-8")
        assert _git(repository, "add", ".agent/WAVE.md").returncode == 0
        commit = _git(repository, "commit", "--quiet", "-m", subject)
        assert commit.returncode == 0, commit.stderr

    findings = checker.check_delivery_hygiene(repository, base)
    completion_findings = [
        item
        for item in findings
        if item.kind == "forbidden completion-only commit intent"
    ]
    assert len(completion_findings) == len(subjects)


def test_cross_scope_rename_is_not_misread_as_evidence_only(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    base = _init(repository)
    destination = repository / ".agent/evidence/wave_b/moved.txt"
    destination.parent.mkdir(parents=True)
    moved = _git(
        repository,
        "mv",
        "tracked.txt",
        ".agent/evidence/wave_b/moved.txt",
    )
    assert moved.returncode == 0, moved.stderr
    assert checker.check_delivery_hygiene(repository, base) == ()

    commit = _git(repository, "commit", "--quiet", "-m", "move stable fixture")
    assert commit.returncode == 0, commit.stderr
    commit_sha = _git(repository, "rev-parse", "HEAD").stdout.strip()
    assert checker._commit_paths(repository, commit_sha) == (
        ".agent/evidence/wave_b/moved.txt",
        "tracked.txt",
    )
    findings = checker.check_delivery_hygiene(repository, base)
    assert not any(item.kind == "evidence-only introduced commit" for item in findings)


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
