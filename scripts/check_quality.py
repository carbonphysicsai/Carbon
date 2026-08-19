"""Enforce Carbon's no-new-debt Ruff and Black quality ratchet."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any

SCHEMA_VERSION = 1
EXPECTED_TOOL_VERSIONS = {"black": "26.5.1", "ruff": "0.16.3"}
RUFF_ARGS = (
    "check",
    "--isolated",
    "--no-cache",
    "--target-version",
    "py310",
    "--output-format",
    "json",
)
BLACK_ARGS = (
    "--config",
    "/dev/null",
    "--check",
    "--target-version",
    "py310",
    "--no-color",
)
BLACK_REFORMAT = re.compile(r"^would reformat (?P<path>.+)$")
BLACK_PARSE_ERROR = re.compile(
    r"^error: cannot format (?P<path>.+?): "
    r"Cannot parse for target version Python 3\.10: "
    r"(?P<row>\d+):(?P<column>\d+)$"
)
BLACK_SUMMARY = re.compile(
    r"^(?P<body>\d+ files? would "
    r"(?:be reformatted|be left unchanged|fail to reformat)"
    r"(?:, \d+ files? would "
    r"(?:be reformatted|be left unchanged|fail to reformat))*)\.$"
)
BLACK_SUMMARY_PART = re.compile(
    r"(?P<count>\d+) files? would (?P<status>be reformatted|"
    r"be left unchanged|fail to reformat)"
)
COMMIT_SHA = re.compile(r"^[0-9a-f]{40}$")


class QualityGateError(RuntimeError):
    """Raised when the quality tools or ratchet data are not trustworthy."""


def _run(
    command: list[str],
    *,
    cwd: Path,
    expected_returncodes: set[int],
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode not in expected_returncodes:
        rendered = " ".join(command)
        raise QualityGateError(
            f"unexpected exit {result.returncode} from `{rendered}`\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


def _git(repo: Path, *arguments: str) -> str:
    result = _run(
        ["git", *arguments],
        cwd=repo,
        expected_returncodes={0},
    )
    return result.stdout


def _repository_root() -> Path:
    root = _git(Path.cwd(), "rev-parse", "--show-toplevel").strip()
    return Path(root).resolve()


def _tracked_python_files(repo: Path) -> list[str]:
    output = _git(
        repo,
        "ls-files",
        "-z",
        "--cached",
        "--others",
        "--exclude-standard",
        "--",
        "*.py",
    )
    files = sorted(
        path for path in output.split("\0") if path and (repo / path).is_file()
    )
    if not files:
        raise QualityGateError("git reported no tracked Python files")
    return files


def _relative_path(repo: Path, value: str) -> str:
    path = Path(value)
    if not path.is_absolute():
        path = repo / path
    try:
        return path.resolve().relative_to(repo).as_posix()
    except ValueError as exc:
        raise QualityGateError(
            f"tool reported a path outside the repository: {value}"
        ) from exc


def _tool_versions(repo: Path) -> dict[str, str]:
    ruff = _run(["ruff", "--version"], cwd=repo, expected_returncodes={0})
    black = _run(["black", "--version"], cwd=repo, expected_returncodes={0})

    ruff_match = re.search(r"\bruff (?P<version>\S+)", ruff.stdout)
    black_match = re.search(
        r"\bblack, (?P<version>\S+)",
        f"{black.stdout}\n{black.stderr}",
    )
    if ruff_match is None or black_match is None:
        raise QualityGateError("could not parse Ruff or Black version output")
    return {
        "ruff": ruff_match.group("version"),
        "black": black_match.group("version"),
    }


def _ruff_diagnostics(repo: Path, files: list[str]) -> list[dict[str, Any]]:
    result = _run(
        ["ruff", *RUFF_ARGS, *files],
        cwd=repo,
        expected_returncodes={0, 1},
    )
    try:
        raw = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise QualityGateError(f"Ruff did not emit valid JSON: {exc}") from exc
    if not isinstance(raw, list):
        raise QualityGateError("Ruff JSON root is not a list")
    if result.returncode == 0 and raw:
        raise QualityGateError("Ruff returned success with non-empty diagnostics")
    if result.returncode == 1 and not raw:
        raise QualityGateError("Ruff returned failure with no diagnostics")

    diagnostics: list[dict[str, Any]] = []
    for item in raw:
        try:
            diagnostics.append(
                {
                    "path": _relative_path(repo, item["filename"]),
                    "code": item["code"],
                    "row": item["location"]["row"],
                    "column": item["location"]["column"],
                    "end_row": item["end_location"]["row"],
                    "end_column": item["end_location"]["column"],
                    "message": item["message"],
                }
            )
        except (KeyError, TypeError) as exc:
            raise QualityGateError(f"malformed Ruff diagnostic: {item!r}") from exc
    return sorted(diagnostics, key=_fingerprint)


def _black_diagnostics(repo: Path, files: list[str]) -> list[dict[str, Any]]:
    result = _run(
        ["black", *BLACK_ARGS, *files],
        cwd=repo,
        expected_returncodes={0, 1, 123},
    )
    output = f"{result.stdout}\n{result.stderr}"
    diagnostics: list[dict[str, Any]] = []
    unparsed_errors: list[str] = []
    summaries: list[dict[str, int]] = []

    for line in output.splitlines():
        reformat_match = BLACK_REFORMAT.match(line)
        if reformat_match is not None:
            diagnostics.append(
                {
                    "path": _relative_path(repo, reformat_match.group("path")),
                    "status": "would-reformat",
                }
            )
            continue

        parse_match = BLACK_PARSE_ERROR.match(line)
        if parse_match is not None:
            diagnostics.append(
                {
                    "path": _relative_path(repo, parse_match.group("path")),
                    "status": "cannot-parse",
                    "row": int(parse_match.group("row")),
                    "column": int(parse_match.group("column")),
                }
            )
            continue

        if line.startswith("error:"):
            unparsed_errors.append(line)

        summary_match = BLACK_SUMMARY.match(line)
        if summary_match is not None:
            counts = {
                "be reformatted": 0,
                "be left unchanged": 0,
                "fail to reformat": 0,
            }
            for part in BLACK_SUMMARY_PART.finditer(summary_match.group("body")):
                counts[part.group("status")] = int(part.group("count"))
            summaries.append(counts)

    if unparsed_errors:
        raise QualityGateError(
            "Black emitted unclassified errors:\n" + "\n".join(unparsed_errors)
        )

    if len(summaries) != 1:
        raise QualityGateError(
            f"Black emitted {len(summaries)} recognized summary lines; expected one"
        )

    summary = summaries[0]
    reformatted = sum(item["status"] == "would-reformat" for item in diagnostics)
    failed = sum(item["status"] == "cannot-parse" for item in diagnostics)
    if summary["be reformatted"] != reformatted:
        raise QualityGateError("Black reformat detail count does not match its summary")
    if summary["fail to reformat"] != failed:
        raise QualityGateError(
            "Black parse-error detail count does not match its summary"
        )
    if sum(summary.values()) != len(files):
        raise QualityGateError(
            "Black summary does not account for every enumerated Python file"
        )

    statuses = {item["status"] for item in diagnostics}
    if result.returncode == 0 and diagnostics:
        raise QualityGateError("Black returned success with debt diagnostics")
    if result.returncode == 1 and statuses != {"would-reformat"}:
        raise QualityGateError("Black exit 1 did not match formatting-only debt")
    if result.returncode == 123 and "cannot-parse" not in statuses:
        raise QualityGateError("Black exit 123 did not include a parse failure")
    if result.returncode != 0 and not diagnostics:
        raise QualityGateError("Black returned failure with no classified debt")
    return sorted(diagnostics, key=_fingerprint)


def _fingerprint(item: dict[str, Any]) -> str:
    return json.dumps(item, sort_keys=True, separators=(",", ":"))


def _counter(items: list[dict[str, Any]]) -> Counter[str]:
    return Counter(_fingerprint(item) for item in items)


def _expanded(counter: Counter[str]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for fingerprint, count in sorted(counter.items()):
        result.extend(json.loads(fingerprint) for _ in range(count))
    return result


def _changed_python_files(repo: Path, base: str) -> tuple[str, list[str]]:
    if base and set(base) == {"0"}:
        raise QualityGateError("the comparison base cannot be an all-zero SHA")
    merge_base = _git(repo, "merge-base", base, "HEAD").strip()
    changed_output = _git(
        repo,
        "diff",
        "--name-only",
        "-z",
        "--diff-filter=ACMR",
        merge_base,
        "--",
        "*.py",
    )
    untracked_output = _git(
        repo,
        "ls-files",
        "--others",
        "--exclude-standard",
        "-z",
        "--",
        "*.py",
    )
    candidates = {
        path
        for path in (*changed_output.split("\0"), *untracked_output.split("\0"))
        if path and (repo / path).is_file()
    }
    return merge_base, sorted(candidates)


def _strict_changed_checks(repo: Path, files: list[str]) -> dict[str, Any]:
    if not files:
        return {"ruff_exit": 0, "black_exit": 0, "ruff_output": "", "black_output": ""}

    ruff = subprocess.run(
        ["ruff", *RUFF_ARGS[:-2], *files],
        cwd=repo,
        check=False,
        capture_output=True,
        text=True,
    )
    black = subprocess.run(
        ["black", *BLACK_ARGS, *files],
        cwd=repo,
        check=False,
        capture_output=True,
        text=True,
    )
    return {
        "ruff_exit": ruff.returncode,
        "black_exit": black.returncode,
        "ruff_output": f"{ruff.stdout}{ruff.stderr}",
        "black_output": f"{black.stdout}{black.stderr}",
    }


def _capture(repo: Path) -> dict[str, Any]:
    files = _tracked_python_files(repo)
    return {
        "tool_versions": _tool_versions(repo),
        "tracked_python_files": files,
        "ruff_diagnostics": _ruff_diagnostics(repo, files),
        "black_diagnostics": _black_diagnostics(repo, files),
    }


def _load_baseline(path: Path) -> dict[str, Any]:
    try:
        baseline = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise QualityGateError(
            f"could not load quality baseline {path}: {exc}"
        ) from exc
    expected_keys = {
        "schema_version",
        "source_commit",
        "tool_versions",
        "tool_arguments",
        "tracked_python_files",
        "ruff_diagnostics",
        "black_diagnostics",
    }
    if not isinstance(baseline, dict) or set(baseline) != expected_keys:
        raise QualityGateError("quality baseline fields do not match the schema")
    if baseline["schema_version"] != SCHEMA_VERSION:
        raise QualityGateError("unsupported quality baseline schema")
    if not isinstance(baseline["source_commit"], str) or not COMMIT_SHA.fullmatch(
        baseline["source_commit"]
    ):
        raise QualityGateError("quality baseline source is not a full commit SHA")
    expected_arguments = {"ruff": list(RUFF_ARGS), "black": list(BLACK_ARGS)}
    if baseline["tool_arguments"] != expected_arguments:
        raise QualityGateError("quality baseline tool arguments do not match the gate")
    if baseline["tool_versions"] != EXPECTED_TOOL_VERSIONS:
        raise QualityGateError("quality baseline tool versions do not match policy")

    tracked_files = baseline["tracked_python_files"]
    if not isinstance(tracked_files, list) or not tracked_files:
        raise QualityGateError("quality baseline has no Python file inventory")
    if any(not _valid_repository_python_path(item) for item in tracked_files):
        raise QualityGateError("quality baseline contains an invalid Python path")
    if tracked_files != sorted(set(tracked_files)):
        raise QualityGateError(
            "quality baseline Python paths are not sorted and unique"
        )
    tracked_set = set(tracked_files)

    ruff_diagnostics = baseline["ruff_diagnostics"]
    black_diagnostics = baseline["black_diagnostics"]
    if not isinstance(ruff_diagnostics, list) or not isinstance(
        black_diagnostics, list
    ):
        raise QualityGateError("quality baseline diagnostics are not lists")
    for item in ruff_diagnostics:
        _validate_ruff_baseline_item(item, tracked_set)
    for item in black_diagnostics:
        _validate_black_baseline_item(item, tracked_set)
    if ruff_diagnostics != sorted(ruff_diagnostics, key=_fingerprint):
        raise QualityGateError("quality baseline Ruff diagnostics are not canonical")
    if black_diagnostics != sorted(black_diagnostics, key=_fingerprint):
        raise QualityGateError("quality baseline Black diagnostics are not canonical")
    if len({_fingerprint(item) for item in ruff_diagnostics}) != len(ruff_diagnostics):
        raise QualityGateError("quality baseline contains duplicate Ruff diagnostics")
    black_paths = [item["path"] for item in black_diagnostics]
    if len(set(black_paths)) != len(black_paths):
        raise QualityGateError("quality baseline contains duplicate Black paths")
    return baseline


def _valid_repository_python_path(value: Any) -> bool:
    if not isinstance(value, str) or not value.endswith(".py"):
        return False
    path = PurePosixPath(value)
    return bool(value) and not path.is_absolute() and ".." not in path.parts


def _positive_integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 1


def _validate_ruff_baseline_item(item: Any, tracked: set[str]) -> None:
    expected = {
        "path",
        "code",
        "row",
        "column",
        "end_row",
        "end_column",
        "message",
    }
    if not isinstance(item, dict) or set(item) != expected:
        raise QualityGateError("quality baseline contains malformed Ruff data")
    if item["path"] not in tracked:
        raise QualityGateError("quality baseline Ruff path is outside its inventory")
    if not all(isinstance(item[key], str) and item[key] for key in ("code", "message")):
        raise QualityGateError("quality baseline Ruff strings are invalid")
    if not all(
        _positive_integer(item[key])
        for key in ("row", "column", "end_row", "end_column")
    ):
        raise QualityGateError("quality baseline Ruff positions are invalid")


def _validate_black_baseline_item(item: Any, tracked: set[str]) -> None:
    if not isinstance(item, dict) or item.get("path") not in tracked:
        raise QualityGateError("quality baseline contains malformed Black data")
    status = item.get("status")
    if status == "would-reformat":
        if set(item) != {"path", "status"}:
            raise QualityGateError("quality baseline Black format data is malformed")
        return
    if status == "cannot-parse":
        if set(item) != {"path", "status", "row", "column"} or not all(
            _positive_integer(item[key]) for key in ("row", "column")
        ):
            raise QualityGateError("quality baseline Black parse data is malformed")
        return
    raise QualityGateError("quality baseline Black status is invalid")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _update_baseline(repo: Path, path: Path, source_commit: str | None) -> int:
    if _git(repo, "status", "--porcelain"):
        raise QualityGateError("baseline generation requires a clean worktree")
    head = _git(repo, "rev-parse", "HEAD").strip()
    source = source_commit or head
    if source != head:
        raise QualityGateError(
            f"baseline source {source} does not match checked-out HEAD {head}"
        )

    captured = _capture(repo)
    baseline = {
        "schema_version": SCHEMA_VERSION,
        "source_commit": source,
        "tool_versions": captured["tool_versions"],
        "tool_arguments": {"ruff": list(RUFF_ARGS), "black": list(BLACK_ARGS)},
        "tracked_python_files": captured["tracked_python_files"],
        "ruff_diagnostics": captured["ruff_diagnostics"],
        "black_diagnostics": captured["black_diagnostics"],
    }
    _write_json(path, baseline)
    print(
        f"wrote {path}: {len(baseline['ruff_diagnostics'])} Ruff diagnostics, "
        f"{len(baseline['black_diagnostics'])} Black debt entries"
    )
    return 0


def _check(
    repo: Path,
    baseline_path: Path,
    base: str | None,
    report_path: Path | None,
) -> int:
    baseline = _load_baseline(baseline_path)
    captured = _capture(repo)
    if captured["tool_versions"] != baseline["tool_versions"]:
        raise QualityGateError(
            "quality tool versions differ from the committed baseline: "
            f"current={captured['tool_versions']} baseline={baseline['tool_versions']}"
        )

    ruff_current = _counter(captured["ruff_diagnostics"])
    ruff_baseline = _counter(baseline["ruff_diagnostics"])
    black_current = _counter(captured["black_diagnostics"])
    black_baseline = _counter(baseline["black_diagnostics"])
    new_ruff = _expanded(ruff_current - ruff_baseline)
    removed_ruff = _expanded(ruff_baseline - ruff_current)
    new_black = _expanded(black_current - black_baseline)
    removed_black = _expanded(black_baseline - black_current)

    selected_base = base or baseline["source_commit"]
    merge_base, changed_files = _changed_python_files(repo, selected_base)
    strict = _strict_changed_checks(repo, changed_files)
    head = _git(repo, "rev-parse", "HEAD").strip()
    report = {
        "schema_version": SCHEMA_VERSION,
        "baseline_source_commit": baseline["source_commit"],
        "comparison_base": selected_base,
        "merge_base": merge_base,
        "head": head,
        **captured,
        "new_ruff_diagnostics": new_ruff,
        "removed_ruff_diagnostics": removed_ruff,
        "new_black_diagnostics": new_black,
        "removed_black_diagnostics": removed_black,
        "changed_python_files": changed_files,
        "strict_changed_checks": strict,
    }
    if report_path is None:
        report_path = Path(tempfile.mkdtemp(prefix="carbon-quality-")) / "current.json"
    _write_json(report_path, report)

    print(
        "quality inventory: "
        f"Ruff {len(captured['ruff_diagnostics'])}/"
        f"{len(baseline['ruff_diagnostics'])}; "
        f"Black {len(captured['black_diagnostics'])}/"
        f"{len(baseline['black_diagnostics'])}"
    )
    print(
        f"removed debt: Ruff {len(removed_ruff)}, Black {len(removed_black)}; "
        f"changed Python files: {len(changed_files)}"
    )
    print(f"full machine-readable report: {report_path}")

    failures: list[str] = []
    if new_ruff:
        failures.append(f"{len(new_ruff)} new Ruff diagnostic(s)")
        print(json.dumps(new_ruff, indent=2, sort_keys=True))
    if new_black:
        failures.append(f"{len(new_black)} new Black debt entrie(s)")
        print(json.dumps(new_black, indent=2, sort_keys=True))
    if strict["ruff_exit"] != 0:
        failures.append("strict Ruff failed on changed Python files")
        print(strict["ruff_output"])
    if strict["black_exit"] != 0:
        failures.append("strict Black failed on changed Python files")
        print(strict["black_output"])

    if failures:
        print("quality gate failed: " + "; ".join(failures), file=sys.stderr)
        return 1
    print("quality gate passed: no new debt and all changed Python files are clean")
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--baseline",
        type=Path,
        default=Path(".ci/quality-baseline.json"),
    )
    parser.add_argument(
        "--base", help="Git ref/SHA used for strict changed-file checks"
    )
    parser.add_argument(
        "--report", type=Path, help="write the full current inventory here"
    )
    parser.add_argument(
        "--update-baseline",
        action="store_true",
        help="capture a new baseline from a clean checked-out source commit",
    )
    parser.add_argument(
        "--source-commit",
        help="required baseline source identity (must equal checked-out HEAD)",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        repo = _repository_root()
        baseline_path = args.baseline
        if not baseline_path.is_absolute():
            baseline_path = repo / baseline_path
        report_path = args.report
        if report_path is not None and not report_path.is_absolute():
            report_path = repo / report_path
        if args.update_baseline:
            return _update_baseline(
                repo,
                baseline_path,
                args.source_commit,
            )
        return _check(repo, baseline_path, args.base, report_path)
    except QualityGateError as exc:
        print(f"quality gate error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
