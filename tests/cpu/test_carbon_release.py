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


def _root(
    tmp_path,
    name,
    *,
    caches=(),
    draining=False,
    release=None,
    state=None,
    accepted=None,
):
    """A prepared door root: its receiver config names its state dir (default <root>/receiver/state)."""
    root = tmp_path / name
    state = root / "receiver/state" if state is None else state
    state.mkdir(parents=True, exist_ok=True)
    cfg = {"root": str(state)}
    if accepted is not None:
        cfg["accepted_revision"] = accepted
    (root / "receiver").mkdir(parents=True, exist_ok=True)
    (root / "receiver/receiver.json").write_text(json.dumps(cfg), encoding="utf-8")
    lib = root / LIB
    lib.mkdir(parents=True, exist_ok=True)
    lib.chmod(0o700)
    for rel, text in caches:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    if (lib / "materials").is_dir():
        (lib / "materials").chmod(0o700)
    if draining:
        (state / "draining").write_text("{}", encoding="utf-8")
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
    root, _ = repo
    base = _commit(
        root,
        {
            "carbon/challenge_validator/lean_recipe.py": SERVED,
            "carbon/development_session/research_tasks.py": "A = 1\n",
        },
        "served list",
    )
    new = _commit(root, {"docs/notes.md": "d\n"}, "docs")
    heads = _heads(tmp_path, [(new, "FINAL")])
    old_root = _root(tmp_path, "old", caches=[(BUNDLE, "x")], accepted=base)
    new_root = _root(tmp_path, "new", caches=[(BUNDLE, "x")], accepted=new)
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
        [
            "final_heads",
            "accepted",
            "ancestry",
            "exam",
            "served_source",
            "caches",
            "drain",
            "release",
        ],
        tool.PASS,
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


POSIX = pytest.mark.skipif(
    __import__("os").name != "posix", reason="posix modes and links"
)


def test_a_wrong_old_root_is_never_an_empty_door(tool, tmp_path):
    new = _root(tmp_path, "new", caches=[(BUNDLE, "x")])
    nowhere = tmp_path / "typo"
    for run in (
        lambda: tool.caches_item([nowhere], new),
        lambda: tool.drain_item(nowhere),
        lambda: tool.disk_item("switch", nowhere, new),
    ):
        with pytest.raises(tool.ei.Unknown):
            run()
    bare = tmp_path / "bare"
    (bare / "receiver").mkdir(parents=True)
    (bare / "receiver/receiver.json").write_text(
        json.dumps({"root": str(bare / "s")}), encoding="utf-8"
    )
    (bare / "s").mkdir()
    with pytest.raises(tool.ei.Unknown):
        tool.caches_item(
            [bare], new
        )  # no library cache on an OLD root: a wrong path, never "nothing to carry"


@POSIX
def test_a_linked_cache_path_on_new_refuses(tool, tmp_path):
    import os

    old = _root(tmp_path, "old", caches=[(BUNDLE, "x"), (OVERLAY, "y")])
    leaf = _root(tmp_path, "leaf", caches=[(BUNDLE, "x")])
    real = tmp_path / "elsewhere/d4"
    real.mkdir(parents=True)
    (real / "tree.bin").write_text("y", encoding="utf-8")
    level = leaf / LIB / "overlays/a1/b2/c3"
    level.mkdir(parents=True)
    os.symlink(real, level / "d4")
    out = tool.caches_item([old], leaf)
    assert out["state"] == tool.REFUSE and out["code"] == "cache_path_is_link"
    whole = tmp_path / "whole"
    (whole / "receiver").mkdir(parents=True)
    (whole / "receiver/receiver.json").write_text(
        json.dumps({"root": str(whole / "s")}), encoding="utf-8"
    )
    (whole / "s").mkdir()
    (whole / LIB).parent.mkdir(parents=True)
    os.symlink(old / LIB, whole / LIB.rstrip("/"))
    assert tool.caches_item([old], whole)["code"] == "cache_path_is_link"


@POSIX
def test_a_cache_dir_the_receiver_would_refuse_refuses(tool, tmp_path):
    old = _root(tmp_path, "old", caches=[(BUNDLE, "x")])
    new = _root(tmp_path, "new", caches=[(BUNDLE, "x")])
    (new / LIB).chmod(0o755)
    out = tool.caches_item([old], new)
    assert out["state"] == tool.REFUSE and out["code"] == "cache_dir_not_private"


def test_staging_leftovers_are_not_cache_entries(tool, tmp_path):
    old = _root(
        tmp_path, "old", caches=[(BUNDLE, "x"), (LIB + "materials/.pending-abc/f", "t")]
    )
    new = _root(tmp_path, "new", caches=[(BUNDLE, "x")])
    assert tool.caches_item([old], new)["state"] == tool.PASS


def test_the_drain_flag_is_read_where_the_config_puts_state(tool, tmp_path):
    fixed = tmp_path / "doors/motor/state"
    root = _root(tmp_path, "rel", state=fixed, draining=True)
    assert not (root / "receiver/state/draining").exists()
    assert tool.drain_item(root)["code"] == "old_door_draining"


def test_accepted_and_ancestry(tool, repo, tmp_path):
    root, base = repo
    new = _commit(root, {"docs/notes.md": "e\n"}, "docs")
    old_root = _root(tmp_path, "old", accepted=base)
    new_root = _root(tmp_path, "new", accepted=new)
    assert tool.accepted_item(old_root, new_root, base, new)["state"] == tool.PASS
    assert (
        tool.accepted_item(old_root, new_root, new, new)["code"]
        == "old_rev_is_not_the_accepted_revision"
    )
    unnamed = _root(tmp_path, "unnamed")
    out = tool.accepted_item(old_root, unnamed, base, new)
    assert (
        out["state"] == tool.UNKNOWN and out["code"] == "new_accepted_revision_missing"
    )
    assert tool.ancestry_item(root, base, new)["state"] == tool.PASS
    assert tool.ancestry_item(root, new, base)["code"] == "old_not_ancestor_of_new"
    assert tool.ancestry_item(root, base, "0" * 40)["state"] == tool.UNKNOWN


def test_final_heads_reads_short_and_untidy_rows(tool, tmp_path):
    a = "abcdef1" + "0" * 33
    tsv = _heads(tmp_path, [(a, "FINAL"), (a[:8], "HOLD")])
    assert (
        tool.final_heads_status(tsv, a)["code"] == "not_final"
    )  # a short HOLD row still holds
    tsv = _heads(tmp_path, [(a, "FINAL "), (a + " ", " LANDED")])
    assert tool.final_heads_status(tsv, a)["state"] == tool.PASS
    shifted = tmp_path / "shifted.tsv"
    shifted.write_text(
        HEADER + f"{a}\tlabel with\ta tab\tbase\tgate\tFINAL\tc\tm\tw\tr\tv\tb\tn\n",
        encoding="utf-8",
    )
    assert tool.final_heads_status(shifted, a)["code"] == "final_heads_row_shape"


def test_a_rule_only_change_is_said_separately(tool, repo):
    root, base = repo
    widened = RULE.replace(
        '"carbon/scoring/",',
        '"carbon/scoring/",\n    "carbon/challenge_validator/exam_cap.py",',
    )
    new = _commit(
        root, {"carbon/challenge_validator/direct_receiver.py": widened}, "rule only"
    )
    out = tool.exam_item(root, base, new, PACK, PACK, None)
    assert out["code"] == "grading_rule_change_undeclared"
    said = tool.exam_item(root, base, new, PACK, PACK, None, None, "M2 adds exam_cap")
    assert said["state"] == tool.PASS and said["rule_change"] == "M2 adds exam_cap"


@POSIX
def test_an_unreadable_directory_raises_instead_of_counting_low(tool, tmp_path):
    import os

    if os.geteuid() == 0:
        pytest.skip("root reads everything")
    root = tmp_path / "r"
    (root / "locked").mkdir(parents=True)
    (root / "locked/f").write_bytes(b"x" * 10)
    (root / "locked").chmod(0)
    try:
        with pytest.raises(OSError):
            tool.tree_size(root)
    finally:
        (root / "locked").chmod(0o700)


def test_the_log_refuses_odd_lines_and_a_cut_tail(tool, tmp_path):
    log = tmp_path / "d.jsonl"
    log.write_bytes(b"[1, 2]\n")
    assert tool.log_verify(log)["code"] == "line_unreadable"
    log2 = tmp_path / "d2.jsonl"
    tool.log_append(log2, {"a": 1})
    second = tool.log_append(log2, {"a": 2})
    assert tool.log_verify(log2, expect_last=second["sha"])["state"] == tool.PASS
    lines = log2.read_bytes().splitlines()
    log2.write_bytes(lines[0] + bytes([10]))  # tail cut (one line + newline)
    assert tool.log_verify(log2)["state"] == tool.PASS  # alone it cannot tell
    assert (
        tool.log_verify(log2, expect_last=second["sha"])["code"] == "last_line_differs"
    )


def test_a_push_line_only_for_a_final_fast_forward(tool, repo, tmp_path):
    root, base = repo
    _git(root, "branch", "main-ref", base)
    ahead = _commit(root, {"docs/notes.md": "f\n"}, "ahead")
    heads = _heads(tmp_path, [(ahead, "FINAL")])
    out = tool.pushline(root, ahead, heads, main="main-ref")
    assert (
        out["state"] == tool.PASS and out["line"] == f"PR Head: push {ahead} to main."
    )
    assert (
        tool.pushline(root, ahead[:12], heads, main="main-ref")["code"]
        == "not_a_full_commit_id"
    )
    _git(root, "checkout", "-q", "-b", "side", base)
    side = _commit(root, {"docs/other.md": "s\n"}, "side")
    _git(root, "branch", "-f", "main-ref", ahead)
    heads2 = _heads(tmp_path, [(side, "FINAL")])
    assert (
        tool.pushline(root, side, heads2, main="main-ref")["code"]
        == "not_a_fast_forward_of_main"
    )
    _git(root, "branch", "-f", "main-ref", base)
    held = _heads(tmp_path, [(side, "HOLD")])
    assert tool.pushline(root, side, held, main="main-ref")["code"] == "not_final"


SERVED = """_SOURCE_PATHS = (
    "carbon/challenge_validator/lean_recipe.py",
    "carbon/development_session/research_tasks.py",
)
"""
WORKER = """STAGED_MODULES = (
    "carbon.level4.graph",
)
"""


def test_served_source_changes_are_listed_never_refused(tool, repo):
    root, base = repo
    with_lists = _commit(
        root,
        {
            "carbon/challenge_validator/lean_recipe.py": SERVED,
            "carbon/development_session/bundle_construction_worker.py": WORKER,
            "carbon/development_session/research_tasks.py": "A = 1\n",
            "carbon/level4/graph.py": "G = 1\n",
        },
        "served lists",
    )
    assert tool.served_files(root, with_lists) == {
        "carbon/challenge_validator/lean_recipe.py",
        "carbon/development_session/research_tasks.py",
        "carbon/level4/graph.py",
    }
    docs = _commit(root, {"docs/notes.md": "g\n"}, "docs")
    assert tool.served_source_item(root, with_lists, docs) == {
        "state": tool.PASS,
        "changed": [],
    }
    plumbing = _commit(
        root,
        {
            "carbon/development_session/research_tasks.py": "A = 1  # comment\n",
            "carbon/level4/graph.py": "G = 2\n",
        },
        "plumbing",
    )
    out = tool.served_source_item(root, docs, plumbing)
    assert out["state"] == tool.PASS
    assert out["changed"] == [
        "carbon/development_session/research_tasks.py",
        "carbon/level4/graph.py",
    ]
    assert "declared record" in out["note"]
    with pytest.raises(tool.ei.Unknown):
        tool.served_files(
            root, base
        )  # a revision with no served list is never "nothing served"
