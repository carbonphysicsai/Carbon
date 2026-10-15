"""T03: inventory literal refusal references without importing application code.

This is the handoff's static literal-matching measure, not execution coverage.
Git-base comparison prevents a changed allowance file from admitting new gaps.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import io
import json
import os
import re
import subprocess
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOTS = ("scripts/dev/miner_launchpad", "carbon/miner_mcp")
ROOTS = (*SOURCE_ROOTS, "tests")
BASELINE = "docs/development/launchpad/refusal_coverage_baseline.json"
REPORT = "docs/development/launchpad/REFUSAL_COVERAGE.md"
SCHEMA = "carbon.launchpad.refusal-reference-baseline.v1"
CODE = re.compile(r"(?:[a-z][a-z0-9_]{0,63}|[A-Z][A-Z0-9_]{0,63})\Z")
REFUSALS = frozenset(
    {
        "Rejected",
        "SetupRefused",
        "MinerMcpFailure",
        "AccessFailure",
        "AttachRefused",
        "ToolError",
        "AdapterFailure",
        "OperationRefused",
        "ValueError",
        "_rejected",
        "refused",
        "stepped",
        "_operational",
        "_refused_before_dispatch",
    }
)
TABLES = frozenset({"NEXT_ACTIONS", "REFUSAL_FIELDS", "LIBRARY_REFUSALS"})
# environment_setup.SetupRefused(field, code, status=409, next_step=None).
# Code-first calls use argument zero; an explicit code keyword is also recognized.
CODE_ARGUMENTS = {"SetupRefused": 1}


def closed(value):
    return isinstance(value, str) and CODE.fullmatch(value) is not None


def literal(node):
    return node.value if isinstance(node, ast.Constant) else None


def code_argument(call, name):
    index = CODE_ARGUMENTS.get(name, 0)
    if len(call.args) > index:
        return call.args[index]
    return next((item.value for item in call.keywords if item.arg == "code"), None)


def production(path):
    return any(path.startswith(prefix + "/") for prefix in SOURCE_ROOTS) and not (
        Path(path).stem.endswith(("_fixture", "_demo"))
        or Path(path).name == "browser_smoke.py"
    )


def working_files(root):
    """Only Python source in public repository roots; never follow symlinks."""
    result = {}
    for prefix in ROOTS:
        directory = root / prefix
        for path in sorted(directory.rglob("*.py")):
            if any(part.is_symlink() for part in (path, *path.parents)):
                raise ValueError("source_symlink_refused")
            result[path.relative_to(root).as_posix()] = path.read_text(encoding="utf-8")
    return result


def git_files(root, ref):
    """Read public source at a real comparison commit, without extracting it."""
    revision = subprocess.check_output(
        ["git", "rev-parse", "--verify", f"{ref}^{{commit}}"], cwd=root, text=True
    ).strip()
    body = subprocess.check_output(["git", "archive", revision, "--", *ROOTS], cwd=root)
    result = {}
    with tarfile.open(fileobj=io.BytesIO(body)) as archive:
        for member in archive:
            if not member.name.endswith(".py"):
                continue
            if not member.isfile():
                raise ValueError("base_source_not_regular")
            stream = archive.extractfile(member)
            if stream is None:
                raise ValueError("base_source_missing")
            result[member.name] = stream.read().decode("utf-8")
    return revision, result


def inventory(files):
    """Collect existing catalog/typed-site codes and exact Python test strings.

    A code mentioned in a test is a reference, even if that branch never runs.
    Comments/docstrings, non-Python tests, dynamic codes and imported constants
    are not references. Unresolved typed-site expressions are listed separately.
    """
    codes = {}
    tests = {}
    dynamic = []

    def add(code, path, node, kind):
        if closed(code):
            row = codes.setdefault(code, {"sources": [], "tests": []})
            site = {"path": path, "line": node.lineno, "kind": kind}
            if site not in row["sources"]:
                row["sources"].append(site)

    for path, source in sorted(files.items()):
        if not (production(path) or path.startswith("tests/")):
            continue
        tree = ast.parse(source, filename=path)
        docstrings = {
            id(node.body[0].value)
            for node in ast.walk(tree)
            if isinstance(
                node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
            )
            and node.body
            and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
            and isinstance(node.body[0].value.value, str)
        }
        if path.startswith("tests/"):
            for node in ast.walk(tree):
                value = literal(node)
                if closed(value) and id(node) not in docstrings:
                    tests.setdefault(value, []).append(
                        {"path": path, "line": node.lineno}
                    )
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = (
                    node.targets if isinstance(node, ast.Assign) else [node.target]
                )
                names = {
                    target.id for target in targets if isinstance(target, ast.Name)
                }
                if names & TABLES and isinstance(node.value, ast.Dict):
                    for key in node.value.keys:
                        add(
                            literal(key),
                            path,
                            key,
                            "catalog" if "NEXT_ACTIONS" in names else "table",
                        )
                for target in targets:
                    if (
                        isinstance(target, ast.Subscript)
                        and isinstance(target.value, ast.Name)
                        and target.value.id in TABLES
                    ):
                        add(literal(target.slice), path, target, "table")
            if (
                isinstance(node, ast.AugAssign)
                and isinstance(node.target, ast.Name)
                and node.target.id in TABLES
                and isinstance(node.value, ast.Dict)
            ):
                for key in node.value.keys:
                    add(literal(key), path, key, "table")
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id in TABLES
            ):
                if node.func.attr == "update":
                    if node.args and isinstance(node.args[0], ast.Dict):
                        for key in node.args[0].keys:
                            add(literal(key), path, key, "table")
                    for keyword in node.keywords:
                        add(keyword.arg, path, keyword, "table")
                elif node.func.attr == "setdefault" and node.args:
                    add(literal(node.args[0]), path, node.args[0], "table")
            if isinstance(node, ast.Raise) and isinstance(node.exc, ast.Call):
                call = node.exc
                name = ast.unparse(call.func).rsplit(".", 1)[-1]
                if name in REFUSALS or name.endswith(("Refused", "Refusal", "Failure")):
                    argument = code_argument(call, name)
                    code = literal(argument)
                    if closed(code):
                        add(code, path, node, "raise")
                    elif not isinstance(argument, ast.Constant):
                        dynamic.append(
                            {"path": path, "line": node.lineno, "constructor": name}
                        )
            if isinstance(node, ast.Dict):
                for key, value in zip(node.keys, node.values):
                    if literal(key) in ("error", "refused", "code"):
                        add(literal(value), path, value, "response")
    for code, row in codes.items():
        row["sources"].sort(key=lambda site: (site["path"], site["line"], site["kind"]))
        row["tests"] = sorted(
            {
                json.dumps(site, sort_keys=True): site for site in tests.get(code, [])
            }.values(),
            key=lambda site: (site["path"], site["line"]),
        )
    return {"codes": dict(sorted(codes.items())), "dynamic_sites": dynamic}


def unreached(report):
    return {code for code, row in report["codes"].items() if not row["tests"]}


def regressions(current, previous):
    """Compare identities, not just counts: one fixed gap cannot buy another."""
    before = unreached(previous)
    after = unreached(current)
    return {
        "new_unreached": sorted(
            (set(current["codes"]) - set(previous["codes"])) & after
        ),
        "lost_references": sorted((set(previous["codes"]) - before) & after),
        "unreached_increased": len(after) > len(before),
    }


def baseline(report, revision):
    if re.fullmatch(r"[0-9a-f]{40}", revision) is None:
        raise ValueError("full_baseline_revision_required")
    return {
        "schema": SCHEMA,
        "revision": revision,
        "measure": "STATIC_LITERAL_REFERENCE_NOT_EXECUTED_REACHABILITY",
        "codes": sorted(report["codes"]),
        "unreached": sorted(unreached(report)),
    }


def read_baseline(path):
    value = json.loads(path.read_bytes())
    if (
        set(value) != {"schema", "revision", "measure", "codes", "unreached"}
        or value["schema"] != SCHEMA
        or value["measure"] != "STATIC_LITERAL_REFERENCE_NOT_EXECUTED_REACHABILITY"
        or re.fullmatch(r"[0-9a-f]{40}", value["revision"]) is None
        or any(
            type(value[key]) is not list
            or not all(closed(code) for code in value[key])
            or value[key] != sorted(set(value[key]))
            for key in ("codes", "unreached")
        )
        or not set(value["unreached"]) <= set(value["codes"])
    ):
        raise ValueError("invalid_refusal_reference_baseline")
    return value


def render(report, initial):
    missing = unreached(report)
    digest = hashlib.sha256(
        json.dumps(report, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    lines = [
        "# Launchpad refusal literal-reference coverage",
        "",
        "Static snapshot, not executed refusal reachability or door-parity evidence.",
        "REACHED means an exact string literal exists in Python under tests/.",
        "It may occur in fixture data or an unexecuted branch; no test is run by this tool.",
        "Comments/docstrings and non-Python tests are excluded. Dynamic expressions and",
        "imported test constants need independent investigation; this is not a completeness proof.",
        "",
        f"Initial backlog source: `{initial['revision']}`. Inventory SHA256: `{digest}`.",
        f"Codes: **{len(report['codes'])}**; REACHED (literal): **{len(report['codes']) - len(missing)}**;",
        f"UNREACHED (literal): **{len(missing)}**; unresolved typed-site expressions: **{len(report['dynamic_sites'])}**.",
        "",
        "Regenerate: `python -m scripts.dev.launchpad_refusal_coverage --write`.",
        "Compare against actual Git base: `python -m scripts.dev.launchpad_refusal_coverage --check --base-ref origin/main`.",
        "The existing canonical CPU test runs that comparison in CI. The baseline JSON",
        "records initial debt; it is never the check's allowance source. Only the actual",
        "Git base's code and test references determine allowed existing gaps. The report",
        "is a dated source snapshot; current CLI output and CI compute the current counts.",
        "",
        "Every UNREACHED row is an open child ticket under LAUNCHPAD-T03-REFUSAL-COVERAGE-01,",
        "owned by Launchpad for triage. P1 means a direct production raise/response site",
        "exists; P2 means catalog/table-only. This prioritization does not prove a product",
        "path reaches a site. Closing a child requires an actual refusal test and review.",
        "",
        "| Code | Literal coverage | Production source | Python test references | Open child ticket / priority |",
        "|---|---|---|---|---|",
    ]
    for code, row in report["codes"].items():
        sources = ", ".join(
            f"`{s['path']}:{s['line']}` ({s['kind']})" for s in row["sources"]
        )
        refs = ", ".join(f"`{s['path']}:{s['line']}`" for s in row["tests"]) or "—"
        priority = (
            "P1"
            if any(s["kind"] in {"raise", "response"} for s in row["sources"])
            else "P2"
        )
        ticket = f"`T03-REFUSAL-{code}` / {priority}" if code in missing else "—"
        lines.append(
            f"| `{code}` | {'UNREACHED' if code in missing else 'REACHED (literal)'} | {sources} | {refs} | {ticket} |"
        )
    lines += [
        "",
        "## Unresolved typed-site expressions",
        "",
        "These sites were not guessed into new closed codes:",
        "",
    ]
    lines.extend(
        f"- `{s['path']}:{s['line']}` (`{s['constructor']}`)"
        for s in report["dynamic_sites"]
    )
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument(
        "--base-ref", default=os.environ.get("QUALITY_BASE_SHA", "origin/main")
    )
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    current = inventory(working_files(root))
    initial = read_baseline(root / BASELINE)
    if args.write:
        (root / REPORT).write_text(
            render(current, initial), encoding="utf-8", newline="\n"
        )
    result = {
        "codes": len(current["codes"]),
        "unreached": len(unreached(current)),
        "measure": initial["measure"],
    }
    if args.check:
        revision, files = git_files(root, args.base_ref)
        result["base_revision"] = revision
        result.update(regressions(current, inventory(files)))
    print(json.dumps(result, sort_keys=True))
    return int(
        any(
            result.get(key)
            for key in ("new_unreached", "lost_references", "unreached_increased")
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
