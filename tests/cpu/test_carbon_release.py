"""H5 v1: the deploy tool's prechecks, release identity and log (scripts/dev/release/carbon_release.py)."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "scripts/dev/release/carbon_release.py"
PACK = "a" * 64
RULE = """import re
GRADING_PATHS = (
    "carbon/reconstruction/",
    "carbon/scoring/",
)
_GRADING_MODULE = re.compile(r"carbon/challenge_validator/[a-z0-9_]+_hidden\\.py")
"""
BINDING = """LEGACY_NAME = "receiver-binding.json"
DOOR_NAME = "door-binding.json"
RELEASES_DIR = "bindings"
"""
HEADER = "sha\tlabel\tbase\tgate\tstatus\tpath_class\ttarget\twhere_now\treceipt_ref\tverified\treceipt_by\tnote\n"


@pytest.fixture(scope="module")
def tool():
    spec = importlib.util.spec_from_file_location("carbon_release_tool", TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _git(repo, *args):
    return subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _commit(repo, files, message):
    for rel, text in files.items():
        path = repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode("utf-8"))
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "--allow-empty", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    base = _commit(
        root,
        {
            "carbon/challenge_validator/direct_receiver.py": RULE,
            "carbon/reconstruction/worker/build_inputs.txt": "carbon/reconstruction/worker/run.py\n",
            "carbon/reconstruction/worker/run.py": "RUN = 1\n",
            "carbon/scoring/pool_grader.py": "MARGIN = 1\n",
            "docs/notes.md": "a\n",
        },
        "base, before H1",
    )
    return root, base


def _heads(tmp_path, rows):
    path = tmp_path / "FINAL_HEADS.tsv"
    text = "# comment line\n# status: FINAL ...\n" + HEADER
    for sha, status in rows:
        text += f"{sha}\tlabel\tbase\tgate\t{status}\tclass\tmain\twhere\tref\tverified\tvalidator\tnote\n"
    path.write_text(text, encoding="utf-8")
    return path


def _root(tmp_path, name, *, caches=(), draining=False, release=None):
    root = tmp_path / name
    (root / "receiver/state").mkdir(parents=True)
    for rel, text in caches:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    if draining:
        (root / "receiver/state/draining").write_text("{}", encoding="utf-8")
    if release is not None:
        (root / "release.json").write_text(json.dumps(release), encoding="utf-8")
    return root


LIB = "environment/campaigns/.direct-development/library-cache/"
BUNDLE = LIB + "b" * 64 + "/bundle.tar"
OVERLAY = LIB + "overlays/a1/b2/c3/d4/tree.bin"


def test_manifest_names_the_first_start_files_of_its_own_revision(tool, repo):
    root, base = repo
    pre = tool.manifest(root, base)
    assert pre["revision"] == base and pre["first_start_files"] == [
        "receiver-binding.json"
    ]
    h1 = _commit(root, {"carbon/challenge_validator/state_binding.py": BINDING}, "H1")
    after = tool.manifest(root, h1)
    assert after["first_start_files"] == [
        "receiver-binding.json",
        "door-binding.json",
        "bindings/<64hex>.json",
    ]
    assert (
        after["grading_digest"] == pre["grading_digest"]
    )  # state_binding is no grading path here
    assert after["tree"] != pre["tree"] and after["build_inputs_digest"].startswith(
        "sha256:"
    )


def test_declare_lists_paths_exactly_as_the_receiver_does(tool, repo, tmp_path):
    root, base = repo
    new = _commit(
        root,
        {
            "carbon/scoring/pool_grader.py": "MARGIN = 2\n",
            "carbon/reconstruction/worker/run.py": "RUN = 2\n",
            "docs/notes.md": "b\n",
        },
        "grading + build input",
    )
    evidence = tmp_path / "evidence.json"
    evidence.write_text("{}", encoding="utf-8")
    record = tool.declare(
        root, base, new, " new pool grader, off by default ", evidence
    )
    assert record["paths"] == [
        "build_inputs",
        "carbon/reconstruction/worker/run.py",
        "carbon/scoring/pool_grader.py",
    ]
    assert (record["from_revision"], record["to_revision"]) == (base, new)
    assert record["reason"] == "new pool grader, off by default" and tool._valid_record(
        record
    )
    with pytest.raises(ValueError):
        tool.declare(root, base, base, "nothing", evidence)


def test_final_heads_accepts_final_or_landed_only(tool, tmp_path):
    a, b, c = "1" * 40, "2" * 40, "3" * 40
    tsv = _heads(
        tmp_path,
        [
            (a, "FINAL"),
            (b, "HOLD"),
            (c, "LANDED"),
            (c, "FINAL"),
            ("4" * 40, "CONTENT(conditional)"),
        ],
    )
    assert tool.final_heads_status(tsv, a)["state"] == tool.PASS
    assert tool.final_heads_status(tsv, c)["state"] == tool.PASS
    assert tool.final_heads_status(tsv, b)["code"] == "not_final"
    assert tool.final_heads_status(tsv, "4" * 40)["state"] == tool.REFUSE
    assert tool.final_heads_status(tsv, "5" * 40)["code"] == "not_in_final_heads"
    tsv2 = _heads(tmp_path, [(a, "FINAL"), (a, "HOLD")])
    assert (
        tool.final_heads_status(tsv2, a)["state"] == tool.REFUSE
    )  # rows disagree: refuse


def test_exam_item_same_declared_and_refusals(tool, repo, tmp_path):
    root, base = repo
    docs = _commit(root, {"docs/notes.md": "c\n"}, "docs")
    assert tool.exam_item(root, base, docs, PACK, PACK, None)["state"] == tool.PASS
    graded = _commit(root, {"carbon/scoring/pool_grader.py": "MARGIN = 7\n"}, "grading")
    assert (
        tool.exam_item(root, base, graded, PACK, PACK, None)["code"]
        == "exam_change_undeclared"
    )
    evidence = tmp_path / "e.json"
    evidence.write_text("{}", encoding="utf-8")
    record = tool.declare(root, base, graded, "ruled", evidence)
    assert tool.exam_item(root, base, graded, PACK, PACK, record)["state"] == tool.PASS
    off = {**record, "paths": record["paths"] + ["carbon/scoring/extra.py"]}
    assert (
        tool.exam_item(root, base, graded, PACK, PACK, off)["code"]
        == "declared_paths_differ"
    )
    other = {**record, "from_revision": docs}
    assert (
        tool.exam_item(root, base, graded, PACK, PACK, other)["code"]
        == "declared_revisions_differ"
    )
    assert (
        tool.exam_item(root, base, graded, PACK, PACK, {"x": 1})["code"]
        == "declared_record_invalid"
    )
    # a pack change (re-seal) is said, never silent
    assert (
        tool.exam_item(root, base, docs, PACK, "b" * 64, None)["code"]
        == "pack_change_undeclared"
    )
    said = tool.exam_item(root, base, docs, PACK, "b" * 64, None, "re-seal 1.7 r2")
    assert said["state"] == tool.PASS and said["pack_change"] == "re-seal 1.7 r2"


def test_disk_floor(tool, tmp_path):
    gib = tool.GIB
    ok = tool.disk_item("switch", tmp_path, tmp_path, free=30 * gib, size=6 * gib)
    assert ok["state"] == tool.PASS and ok["floor"] == 29 * gib
    low = tool.disk_item("prepare", tmp_path, tmp_path, free=30 * gib, size=6 * gib)
    assert (
        low["state"] == tool.REFUSE
        and low["code"] == "disk_below_floor"
        and low["floor"] == 32 * gib
    )


def test_caches_must_all_be_carried(tool, tmp_path):
    old = _root(tmp_path, "old", caches=[(BUNDLE, "x"), (OVERLAY, "y")])
    older = _root(tmp_path, "older", caches=[(LIB + "materials/m.bin", "z")])
    full = _root(
        tmp_path,
        "full",
        caches=[(BUNDLE, "x"), (OVERLAY, "y"), (LIB + "materials/m.bin", "z")],
    )
    assert tool.caches_item([old, older], full)["state"] == tool.PASS
    short = _root(tmp_path, "short", caches=[(BUNDLE, "x")])
    out = tool.caches_item([old, older], short)
    assert out["state"] == tool.REFUSE and out["missing"] == 2
    assert "overlay/a1/b2/c3/d4" in out["first"] and "materials/m.bin" in out["first"]
    changed = _root(
        tmp_path,
        "changed",
        caches=[(BUNDLE, "xx"), (OVERLAY, "y"), (LIB + "materials/m.bin", "z")],
    )
    assert tool.caches_item([old, older], changed)["differ"] == 1


def test_drain_and_release_items(tool, tmp_path):
    assert tool.drain_item(_root(tmp_path, "a"))["state"] == tool.PASS
    assert (
        tool.drain_item(_root(tmp_path, "b", draining=True))["code"]
        == "old_door_draining"
    )
    rev = "f" * 40
    assert (
        tool.release_item(_root(tmp_path, "c"), rev)["code"] == "release_json_missing"
    )
    named = _root(tmp_path, "d", release={"schema": tool.SCHEMA, "revision": rev})
    assert tool.release_item(named, rev)["state"] == tool.PASS
    assert (
        tool.release_item(named, "e" * 40)["code"]
        == "release_json_names_another_revision"
    )


def test_precheck_switch_end_to_end(tool, repo, tmp_path, capsys):
    root, base = repo
    new = _commit(root, {"docs/notes.md": "d\n"}, "docs")
    heads = _heads(tmp_path, [(new, "FINAL")])
    old_root = _root(tmp_path, "old", caches=[(BUNDLE, "x")])
    new_root = _root(tmp_path, "new", caches=[(BUNDLE, "x")])
    release = tool.manifest(root, new)
    (new_root / "release.json").write_text(json.dumps(release), encoding="utf-8")
    argv = [
        "precheck", "--mode", "switch", "--repo", str(root),
        "--old-rev", base, "--new-rev", new, "--old-pack", PACK, "--new-pack", PACK,
        "--old-root", str(old_root), "--new-root", str(new_root), "--final-heads", str(heads),
    ]  # fmt: skip
    rc = tool.main(argv)
    out = json.loads(capsys.readouterr().out)
    # the disk floor needs 20 GiB free: the result is either a full PASS or a disk-only REFUSE
    others = {k: v["state"] for k, v in out["items"].items() if k != "disk"}
    assert others == dict.fromkeys(
        ["final_heads", "exam", "caches", "drain", "release"], tool.PASS
    )
    assert (rc, out["state"]) in ((0, tool.PASS), (3, tool.REFUSE))
    (old_root / "receiver/state/draining").write_text("{}", encoding="utf-8")
    assert tool.main(argv) == 3
    assert (
        json.loads(capsys.readouterr().out)["items"]["drain"]["code"]
        == "old_door_draining"
    )


def test_precheck_never_passes_on_a_failing_check(tool, repo, tmp_path, capsys):
    root, base = repo
    argv = [
        "precheck", "--mode", "prepare", "--repo", str(root),
        "--old-rev", base, "--new-rev", base, "--old-pack", PACK, "--new-pack", PACK,
        "--old-root", str(tmp_path), "--new-root", str(tmp_path),
        "--final-heads", str(tmp_path / "missing.tsv"),
    ]  # fmt: skip
    rc = tool.main(argv)
    out = json.loads(capsys.readouterr().out)
    # an unreadable FINAL_HEADS is UNKNOWN (never a pass); the disk item may also refuse on a small test host
    assert (
        out["items"]["final_heads"]["state"] == tool.UNKNOWN
        and out["state"] != tool.PASS
    )
    assert rc == (3 if out["state"] == tool.REFUSE else 4)
    with pytest.raises(SystemExit):
        tool.main([*argv[:-2], "--final-heads"])
    bad_pack = [a if a != PACK else "nothex" for a in argv]
    assert tool.main(bad_pack) == 3


def test_the_deploy_log_is_a_chain(tool, tmp_path):
    log = tmp_path / "deploy.jsonl"
    first = tool.log_append(log, {"step": "precheck", "door": "motor"})
    second = tool.log_append(log, {"step": "switch", "door": "motor"})
    assert (first["seq"], second["seq"]) == (1, 2)
    assert tool.log_verify(log) == {
        "state": tool.PASS,
        "lines": 2,
        "last": second["sha"],
    }
    lines = log.read_bytes().splitlines()
    log.write_bytes(lines[0].replace(b"motor", b"rb") + b"\n" + lines[1] + b"\n")
    assert tool.log_verify(log)["code"] == "line_edited"
    with pytest.raises(ValueError):
        tool.log_append(log, {"step": "x"})  # never extends a broken log
    log.write_bytes(lines[1] + b"\n")
    assert tool.log_verify(log)["code"] == "chain_broken"


def test_no_command_reads_stdin(tmp_path):
    """R22: the tool never waits on a prompt (stdin closed: every command still returns)."""
    log = tmp_path / "l.jsonl"
    done = subprocess.run(
        [
            sys.executable,
            "-I",
            "-B",
            str(TOOL),
            "log",
            "append",
            "--log",
            str(log),
            "--event",
            '{"a":1}',
        ],
        stdin=subprocess.DEVNULL,
        check=False,
        capture_output=True,
        timeout=60,
    )
    assert done.returncode == 0 and json.loads(done.stdout)["seq"] == 1
    assert "input(" not in TOOL.read_text(encoding="utf-8")
    assert "sys.stdin" not in TOOL.read_text(encoding="utf-8")
