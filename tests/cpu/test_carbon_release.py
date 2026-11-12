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


def test_precheck_switch_end_to_end(tool, repo, tmp_path, capsys, monkeypatch):
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
        "--host-root", str(old_root), "--host-root", str(new_root),
    ]  # fmt: skip
    # this host's process table: OLD's receiver and the weights loop, both on testnet
    run = ["python3", "-m", "carbon.challenge_validator.direct_receiver", "--config"]
    monkeypatch.setattr(
        tool,
        "PROC",
        _proc_env(
            tmp_path / "host",
            {
                21: ([*run, str(old_root / "receiver/receiver.json")], {}),
                22: (["bash", "/home/carbon/weights-loop5.sh"], {}),
            },
        ),
    )
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
            "chain",
            "owners",
            "door_network",
            "receivers",
            "chain_binding",
            "lock_versions",
            "release",
        ],
        tool.PASS,
    )
    assert (rc, out["state"]) in ((0, tool.PASS), (3, tool.REFUSE))
    # a docs-only release: the tool itself reports class 0 (s7.5)
    assert out["release_class"] == {
        "class": 0,
        "basis": "exam_keys_equal_and_no_served_source",
    }
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
    assert said["identity"]["grading_rule_additions_only"] is True
    assert said["identity"]["grading_rule_added"] == [
        "carbon/challenge_validator/exam_cap.py"
    ]


@pytest.mark.parametrize(
    "change",
    [
        ('    "carbon/scoring/",\n', ""),  # a path removed
        ("_hidden", "_secret"),  # the module pattern changed
    ],
)
def test_a_rule_change_that_can_weaken_m2_refuses_even_when_declared(
    tool, repo, change
):
    """Validator-2 13:21: only a pure addition of grading paths may be declared at switch time."""
    root, base = repo
    weaker = RULE.replace(*change)
    assert weaker != RULE
    new = _commit(
        root, {"carbon/challenge_validator/direct_receiver.py": weaker}, "rule edit"
    )
    out = tool.exam_item(root, base, new, PACK, PACK, None, None, "said anyway")
    assert out["state"] == tool.REFUSE
    assert out["code"] == "grading_rule_change_not_additions_only"
    assert out["identity"]["grading_rule_additions_only"] is False


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


def test_never_flip_into_a_chain_outage_unless_said(tool, tmp_path):
    root = _root(tmp_path, "old")
    state = root / "receiver/state/chain-state.json"
    assert tool.chain_item(root) == {"state": tool.PASS, "chain": "not_reported"}
    state.write_text(json.dumps({"state": "OK"}), encoding="utf-8")
    assert tool.chain_item(root)["chain"] == "OK"
    state.write_text(
        json.dumps(
            {"state": "DEGRADED", "code": "PROVIDER_RATE_LIMITED", "since_ns": 1}
        ),
        encoding="utf-8",
    )
    out = tool.chain_item(root)
    assert out["state"] == tool.REFUSE and out["code"] == "chain_degraded"
    allowed = tool.chain_item(root, "fix-forward for the chain reader")
    assert allowed["state"] == tool.PASS and allowed["allowed"].startswith(
        "fix-forward"
    )
    state.write_text("{", encoding="utf-8")
    assert tool.chain_item(root)["state"] == tool.UNKNOWN


def _owner(root, hotkey="5Owner", *, ledger=True, manifest=True, bad_hash=False):
    import hashlib
    import sqlite3

    name = hashlib.sha256(("x" if bad_hash else hotkey).encode()).hexdigest()
    owner = root / "receiver/state/owners" / name
    owner.mkdir(parents=True)
    (owner / "owner.json").write_text(json.dumps({"hotkey": hotkey}), encoding="utf-8")
    if ledger:
        (owner / "ledger").mkdir()
        db = sqlite3.connect(owner / "ledger" / "campaign.sqlite3")
        db.execute("CREATE TABLE campaign (id INTEGER PRIMARY KEY, manifest TEXT)")
        if manifest:
            db.execute("INSERT INTO campaign VALUES (1, '{}')")
        db.commit()
        db.close()
    return owner


def test_a_partly_restored_owner_refuses_the_switch_named(tool, tmp_path):
    root = _root(tmp_path, "old")
    assert tool.owners_item(root) == {"state": tool.PASS, "owners": 0}
    _owner(root, "5Good")
    assert tool.owners_item(root) == {"state": tool.PASS, "owners": 1}
    _owner(root, "5NoLedger", ledger=False)
    _owner(root, "5NoManifest", manifest=False)
    _owner(root, "5Moved", bad_hash=True)
    out = tool.owners_item(root)
    assert out["state"] == tool.REFUSE and out["code"] == "owner_shape_broken"
    assert sorted(b["reason"] for b in out["broken"]) == [
        "campaign_ledger_missing",
        "campaign_manifest_missing",
        "owner_binding_differs",
    ]


def _proc(tmp_path, commands):
    proc = tmp_path / "proc"
    for pid, argv in commands.items():
        (proc / str(pid)).mkdir(parents=True)
        (proc / str(pid) / "cmdline").write_bytes(
            b"\0".join(a.encode() for a in argv) + b"\0"
        )
    (proc / "self").mkdir(exist_ok=True)
    return proc


def test_a_stray_receiver_on_the_host_refuses(tool, tmp_path):
    door, other = tmp_path / "rs27" / "CI_motor", tmp_path / "scratch"
    run = ["python3", "-m", "carbon.challenge_validator.direct_receiver", "--config"]
    proc = _proc(
        tmp_path,
        {
            11: [*run, str(door / "receiver/receiver.json")],
            12: ["python3", "-m", "http.server"],
        },
    )
    assert tool.receivers_item([door], proc=proc) == {"state": tool.PASS, "running": 1}
    proc = _proc(
        tmp_path / "b",
        {
            13: [*run, str(door / "receiver/receiver.json")],
            14: [*run, str(other / "receiver/receiver.json")],
        },
    )
    out = tool.receivers_item([door], proc=proc)
    assert out["state"] == tool.REFUSE and out["code"] == "undeclared_receiver_running"
    assert out["stray"] == [str(other)]
    assert tool.receivers_item([door], proc=tmp_path / "none")["state"] == tool.UNKNOWN


def test_mixed_lock_code_on_one_host_refuses_unless_drained(
    tool, repo, tmp_path, monkeypatch
):
    root, base = repo
    rr = _commit(root, {"docs/rr.md": "round robin\n"}, "round robin")
    after = _commit(root, {"docs/after.md": "x\n"}, "after")
    monkeypatch.setattr(tool, "ROUND_ROBIN_COMMIT", rr)
    old_door = _root(tmp_path, "cooling", accepted=base)  # older lock code
    new_door = _root(tmp_path, "motor", accepted=after)
    out = tool.lock_versions_item(root, [old_door, new_door], after)
    assert out["state"] == tool.REFUSE and out["undrained"] == [str(old_door)]
    (old_door / "receiver/state/draining").write_text("{}", encoding="utf-8")
    assert (
        tool.lock_versions_item(root, [old_door, new_door], after)["state"] == tool.PASS
    )
    (old_door / "receiver/state/draining").unlink()
    said = tool.lock_versions_item(
        root, [old_door, new_door], after, "Cooling can't switch: disk floor"
    )
    assert said["state"] == tool.PASS and said["allowed"].startswith("Cooling")
    # NEW without the round-robin: nothing to protect
    assert tool.lock_versions_item(root, [old_door], base)["new_round_robin"] is False


def test_switch_mode_requires_the_host_roots(tool, repo, tmp_path):
    root, base = repo
    argv = [
        "precheck", "--mode", "switch", "--repo", str(root),
        "--old-rev", base, "--new-rev", base, "--old-pack", PACK, "--new-pack", PACK,
        "--old-root", str(tmp_path), "--new-root", str(tmp_path), "--final-heads", str(tmp_path / "h.tsv"),
    ]  # fmt: skip
    with pytest.raises(SystemExit):
        tool.main(argv)


def test_the_release_class_is_reported_from_the_items_never_typed(tool):
    same = {"state": tool.ei.SAME}
    exam = {"state": tool.PASS, "identity": same}
    served = {"state": tool.PASS, "changed": []}
    assert tool.release_class({"exam": exam, "served_source": served})["class"] == 0
    listed = {**served, "changed": ["carbon/level4/graph.py"]}
    one = tool.release_class({"exam": exam, "served_source": listed})
    assert (one["class"], one["changed"]) == (1, ["carbon/level4/graph.py"])
    moved = {
        "state": tool.PASS,
        "identity": {"state": "EXAM_CHANGED"},
        "declared": True,
    }
    assert tool.release_class({"exam": moved, "served_source": served})["class"] == 2
    resealed = {**exam, "pack_change": "re-seal"}
    assert tool.release_class({"exam": resealed, "served_source": listed})["class"] == 2
    refused = {"state": tool.REFUSE, "code": "exam_change_undeclared"}
    for items in (
        {"exam": refused, "served_source": served},
        {"served_source": served},
        {},
    ):
        assert tool.release_class(items) == {
            "class": None,
            "basis": "exam_or_served_source_not_passed",
        }


def _proc_env(tmp_path, processes):
    """A fake /proc: pid -> (argv, environment dict or None for an unreadable environ)."""
    proc = tmp_path / "proc"
    for pid, (argv, env) in processes.items():
        (proc / str(pid)).mkdir(parents=True)
        (proc / str(pid) / "cmdline").write_bytes(
            b"\0".join(a.encode() for a in argv) + b"\0"
        )
        environ = proc / str(pid) / "environ"
        environ.write_bytes(
            b"\0".join(f"{k}={v}".encode() for k, v in (env or {}).items()) + b"\0"
        )
        if env is None:
            environ.chmod(0)
    return proc


def test_no_live_door_or_weights_loop_runs_off_the_live_chain(tool, tmp_path):
    door = tmp_path / "rs27" / "CI_motor"
    (door / "receiver").mkdir(parents=True)
    # a root prepared before doors named their network (N3): it is a testnet door
    (door / "receiver" / "receiver.json").write_text("{}", encoding="utf-8")
    receiver = [
        "python3",
        "-m",
        "carbon.challenge_validator.direct_receiver",
        "--config",
        str(door / "receiver/receiver.json"),
    ]
    loop = ["/home/carbon/venv/bin/python", "/home/carbon/wcycle5.py"]
    good = _proc_env(
        tmp_path / "a",
        {
            11: (receiver, {"PATH": "/usr/bin"}),
            12: (loop, {"CARBON_CHAIN_NETWORK": "testnet"}),
            13: (["bash"], {"CARBON_CHAIN_NETWORK": "localnet"}),
        },
    )
    out = tool.chain_binding_item([door], proc=good, receivers_expected=1)
    assert out == {
        "state": tool.PASS,
        "read": 2,
        "receivers": 1,
        "weights_loops": 1,
        "expect": "testnet",
    }
    local = _proc_env(
        tmp_path / "b",
        {
            11: (receiver, {"CARBON_CHAIN_NETWORK": "localnet"}),
            12: (loop, {"CARBON_LOCALNET_GENESIS": "0x" + "4c" * 32}),
        },
    )
    out = tool.chain_binding_item([door], proc=local)
    assert (
        out["state"] == tool.REFUSE and out["code"] == "process_not_on_the_live_chain"
    )
    assert sorted((p["pid"], p["kind"]) for p in out["processes"]) == [
        (11, "receiver"),
        (12, "weights"),
    ]
    # a finney release expects finney everywhere: a testnet-bound loop refuses
    finney = _proc_env(
        tmp_path / "c", {12: (loop, {"CARBON_CHAIN_NETWORK": "testnet"})}
    )
    assert (
        tool.chain_binding_item([door], "finney", proc=finney)["state"] == tool.REFUSE
    )
    (door / "receiver" / "STAGING").write_text("", encoding="utf-8")
    staged = tool.chain_binding_item([door], proc=good)
    assert (staged["state"], staged["code"]) == (tool.REFUSE, "staging_root_on_host")
    assert tool.chain_binding_item([], proc=tmp_path / "none")["state"] == tool.UNKNOWN


def test_an_unreadable_process_environment_is_unknown_never_a_pass(tool, tmp_path):
    import os

    if os.name != "posix" or os.geteuid() == 0:
        pytest.skip("root reads any file; the permission refusal needs a normal user")
    receiver = ["python3", "-m", "carbon.challenge_validator.direct_receiver"]
    proc = _proc_env(tmp_path, {11: (receiver, None)})
    out = tool.chain_binding_item([], proc=proc)
    assert (out["state"], out["code"]) == (
        tool.UNKNOWN,
        "process_environment_unreadable",
    )


def test_a_binding_check_that_finds_no_door_or_no_weights_loop_is_unknown(
    tool, tmp_path
):
    """Validator-2 10:43: read == 0 is never a pass. Fewer running receivers than declared doors, or no weights-loop
    process (its shell script counts between cycles), is UNKNOWN with the counts."""
    door = tmp_path / "rs27" / "CI_motor"
    receiver = [
        "python3",
        "-m",
        "carbon.challenge_validator.direct_receiver",
        "--config",
        str(door / "r.json"),
    ]
    loop = ["bash", "/home/carbon/weights-loop5.sh"]
    door.mkdir(parents=True)
    (door / "r.json").write_text("{}", encoding="utf-8")
    nothing = _proc_env(tmp_path / "a", {13: (["sshd"], {})})
    out = tool.chain_binding_item([door], proc=nothing, receivers_expected=1)
    assert (out["state"], out["code"]) == (tool.UNKNOWN, "binding_processes_missing")
    assert (out["receivers"], out["receivers_expected"], out["weights_loops"]) == (
        0,
        1,
        0,
    )
    no_loop = _proc_env(tmp_path / "b", {11: (receiver, {})})
    assert (
        tool.chain_binding_item([door], proc=no_loop, receivers_expected=1)["state"]
        == tool.UNKNOWN
    )
    no_door = _proc_env(tmp_path / "c", {12: (loop, {})})
    assert (
        tool.chain_binding_item([door], proc=no_door, receivers_expected=1)["state"]
        == tool.UNKNOWN
    )
    both = _proc_env(tmp_path / "d", {11: (receiver, {}), 12: (loop, {})})
    assert (
        tool.chain_binding_item([door], proc=both, receivers_expected=1)["state"]
        == tool.PASS
    )


def _door(tmp_path, name, network=None):
    """A door root whose receiver.json names ``network`` (None: a root prepared before the record), and the argv of
    the receiver running it."""
    root = tmp_path / name
    (root / "receiver").mkdir(parents=True)
    record = {} if network is None else {"chain_network": {"network": network}}
    config = root / "receiver" / "receiver.json"
    config.write_text(json.dumps(record), encoding="utf-8")
    argv = [
        "python3",
        "-m",
        "carbon.challenge_validator.direct_receiver",
        "--config",
        str(config),
    ]
    return root, argv


def test_a_shared_host_holds_each_door_to_its_own_network(tool, tmp_path):
    """N2 (lock-in rev 4): mainnet and testnet doors share GPUYard. With both networks expected, each receiver is held
    to the network its own receiver.json names; a mainnet door bound to testnet (or the reverse) refuses.
    """
    main_door, main_argv = _door(tmp_path, "main-rs1", "finney")
    test_door, test_argv = _door(tmp_path, "test-rs31", "testnet")
    # prepared before the record: a testnet door
    old_door, old_argv = _door(tmp_path, "test-rs30")
    mainnet_loop = ["/home/carbon/venv/bin/python", "/home/carbon/wcycle-finney.py"]
    testnet_loop = ["/home/carbon/venv/bin/python", "/home/carbon/wcycle5.py"]
    both = ["testnet", "finney"]
    doors = [main_door, test_door, old_door]

    good = _proc_env(
        tmp_path / "good",
        {
            11: (main_argv, {"CARBON_CHAIN_NETWORK": "finney"}),
            12: (test_argv, {"CARBON_CHAIN_NETWORK": "testnet"}),
            13: (old_argv, {}),
            14: (mainnet_loop, {"CARBON_CHAIN_NETWORK": "finney"}),
            15: (testnet_loop, {}),
        },
    )
    out = tool.chain_binding_item(doors, both, proc=good, receivers_expected=3)
    assert (out["state"], out["receivers"], out["weights_loops"]) == (tool.PASS, 3, 2)

    # the mainnet door started like a testnet one (the operator's shell, no network in the unit): refused
    crossed = _proc_env(
        tmp_path / "crossed",
        {
            11: (main_argv, {}),
            12: (test_argv, {"CARBON_CHAIN_NETWORK": "finney"}),
            14: (mainnet_loop, {"CARBON_CHAIN_NETWORK": "finney"}),
        },
    )
    out = tool.chain_binding_item(doors, both, proc=crossed)
    assert (out["state"], out["code"]) == (tool.REFUSE, "process_not_on_the_live_chain")
    assert sorted(
        (p["pid"], p["network"], p["door_network"]) for p in out["processes"]
    ) == [
        (11, "", "finney"),
        (12, "finney", "testnet"),
    ]

    # a host declared testnet-only refuses a running mainnet door, even one bound right
    out = tool.chain_binding_item(doors, "testnet", proc=good)
    assert (out["state"], out["code"], out["door_network"]) == (
        tool.REFUSE,
        "receiver_network_not_expected",
        "finney",
    )

    # a host serving two networks runs a weights loop for EACH: one loop alone is not a pass
    one_loop = _proc_env(
        tmp_path / "one_loop",
        {
            11: (main_argv, {"CARBON_CHAIN_NETWORK": "finney"}),
            12: (test_argv, {}),
            13: (old_argv, {}),
            14: (mainnet_loop, {"CARBON_CHAIN_NETWORK": "finney"}),
        },
    )
    out = tool.chain_binding_item(doors, both, proc=one_loop, receivers_expected=3)
    assert (out["state"], out["code"], out["networks_without_a_loop"]) == (
        tool.UNKNOWN,
        "binding_processes_missing",
        ["testnet"],
    )

    # a loop may be bound to any network the host serves, never to another
    stray = _proc_env(
        tmp_path / "stray",
        {12: (test_argv, {}), 14: (mainnet_loop, {"CARBON_CHAIN_NETWORK": "localnet"})},
    )
    assert tool.chain_binding_item(doors, both, proc=stray)["state"] == tool.REFUSE

    # a receiver whose own config cannot be read is UNKNOWN, never a pass
    (old_door / "receiver" / "receiver.json").unlink()
    out = tool.chain_binding_item(doors, both, proc=good)
    assert (out["state"], out["code"], out["pid"]) == (
        tool.UNKNOWN,
        "receiver_config_unreadable",
        13,
    )


def test_the_switch_precheck_takes_one_or_several_expected_networks(tool):
    assert tool._expected_networks(None) == "testnet"
    assert tool._expected_networks(["finney"]) == "finney"
    assert tool._expected_networks(["finney", "finney"]) == "finney"
    assert tool._expected_networks(["testnet", "finney", "testnet"]) == [
        "testnet",
        "finney",
    ]


def test_new_serves_olds_door_on_olds_network(tool, tmp_path):
    """N2/N3: a NEW prepared from a shell bound to another network matches its own record, so its own start would
    pass; the switch precheck compares NEW's record with OLD's before the switch."""
    old_test, _ = _door(tmp_path, "rs31", "testnet")
    legacy, _ = _door(tmp_path, "rs30")  # no record: testnet
    new_test, _ = _door(tmp_path, "rs32", "testnet")
    new_finney, _ = _door(tmp_path, "rs32f", "finney")
    old_main, _ = _door(tmp_path, "m1", "finney")
    new_main, _ = _door(tmp_path, "m2", "finney")
    assert tool.door_network_item(old_test, new_test) == {
        "state": tool.PASS,
        "network": "testnet",
    }
    assert tool.door_network_item(legacy, new_test)["state"] == tool.PASS
    out = tool.door_network_item(old_test, new_finney, ["testnet", "finney"])
    assert (out["state"], out["code"], out["old"], out["new"]) == (
        tool.REFUSE,
        "new_network_differs",
        "testnet",
        "finney",
    )
    assert tool.door_network_item(old_main, new_main, ["testnet", "finney"])[
        "state"
    ] == (tool.PASS)
    out = tool.door_network_item(old_main, new_main, "testnet")
    assert (out["state"], out["code"]) == (tool.REFUSE, "door_network_not_expected")
    out = tool.door_network_item(tmp_path / "nowhere", new_test)
    assert (out["state"], out["code"]) == (tool.UNKNOWN, "receiver_config_unreadable")


# --- open mode: a FRESH door with no OLD (Fri mainnet day-of, step 2) -------------------------------------------------


def _store(tmp_path, name, network=None, *, raw=None):
    """A sealed-pack store dir with a ``.store-network.json`` naming ``network`` (None: a legacy store, no record)."""
    store = tmp_path / name
    store.mkdir(parents=True)
    if raw is not None:
        (store / ".store-network.json").write_text(raw, encoding="utf-8")
    elif network is not None:
        record = {"network": network, "schema": "carbon.sealed-pack-store-network.v1"}
        (store / ".store-network.json").write_text(json.dumps(record), encoding="utf-8")
    return store


def _fresh(
    tmp_path, name, network="finney", *, store=None, pack_set_store=None, accepted=None
):
    """A prepared, never-started door root as `receiver_setup prepare` writes it (only the fields the checks read)."""
    root = tmp_path / name
    (root / "receiver" / "state").mkdir(parents=True)
    cfg = {"root": str(root / "receiver" / "state")}
    if network is not None:
        cfg["chain_network"] = {"network": network}
    if accepted is not None:
        cfg["accepted_revision"] = accepted
    if store is not None:
        cfg["evaluation_pack"] = {
            "root": "/x", "manifest": "evaluation-pack.json", "public_root": "/x", "private_root": "/x",
            "sealed_delivery": {"store": str(store), "manifest_digest": "d" * 64},
        }  # fmt: skip
    if pack_set_store is not None:
        cfg["evaluation_pack_set"] = {
            "store": str(pack_set_store),
            "set_key": "k",
            "batches": ["d" * 64],
        }
    (root / "receiver" / "receiver.json").write_text(json.dumps(cfg), encoding="utf-8")
    return root


def test_an_open_door_is_held_to_its_own_network_and_its_stores(tool, tmp_path):
    both = ["testnet", "finney"]
    finney = _store(tmp_path, "s-finney", "finney-116")
    legacy = _store(tmp_path, "s-legacy")  # no record: a testnet store
    testnet = _store(tmp_path, "s-testnet", "testnet-567")

    def check(name, network="finney", expect=both, **stores):
        return tool.open_door_item(
            _fresh(tmp_path, name, network, **stores), "finney", expect
        )

    out = check("m1", store=finney, pack_set_store=finney)
    assert out["state"] == tool.PASS
    assert out["stores"] == [{"store": str(finney), "network": "finney-116"}]

    # a mainnet door prepared from a testnet store (legacy or recorded) never opens
    for bad in (legacy, testnet):
        out = check(f"m-{bad.name}", store=bad)
        assert (out["state"], out["code"]) == (
            tool.REFUSE,
            "pack_store_network_mismatch",
        )
    # ... nor when only the pack SET's store is another network's
    out = check("m-set", store=finney, pack_set_store=testnet)
    assert (out["state"], out["code"], out["store"]) == (
        tool.REFUSE,
        "pack_store_network_mismatch",
        str(testnet),
    )
    # a root with no network record is a testnet root, never a mainnet door
    out = check("m-norec", None, store=finney)
    assert (out["state"], out["code"]) == (tool.REFUSE, "new_door_network_unrecorded")
    # prepared in a testnet shell: the record names testnet
    out = check("m-tn", "testnet", store=finney)
    assert (out["state"], out["code"]) == (
        tool.REFUSE,
        "new_door_network_not_the_one_named",
    )
    # a localnet-bound prepare
    assert check("m-local", "localnet", store=finney)["state"] == tool.REFUSE
    # a network this host is not declared to serve
    out = check("m-host", expect="testnet", store=finney)
    assert (out["state"], out["code"]) == (tool.REFUSE, "door_network_not_expected")
    # a mainnet door must serve a sealed delivery
    out = check("m-nostore")
    assert (out["state"], out["code"]) == (
        tool.REFUSE,
        "new_door_pack_not_sealed_delivery",
    )
    # a testnet door without a store is not this check's business
    out = tool.open_door_item(_fresh(tmp_path, "t-nostore", "testnet"), "testnet", both)
    assert out["state"] == tool.PASS
    # an unreadable record or store is UNKNOWN, never a pass
    raws = ("{", json.dumps({"network": "finney-116"}), json.dumps({"network": 1}))
    for i, raw in enumerate(raws):
        out = check(f"m-bad{i}", store=_store(tmp_path, f"s-bad{i}", raw=raw))
        assert (out["state"], out["code"]) == (
            tool.UNKNOWN,
            "pack_store_network_unreadable",
        )
    out = check("m-gone", store=tmp_path / "nowhere")
    assert (out["state"], out["code"]) == (
        tool.UNKNOWN,
        "pack_store_network_unreadable",
    )
    out = tool.open_door_item(tmp_path / "no-root", "finney", both)
    assert (out["state"], out["code"]) == (tool.REFUSE, "new_root_missing")
    (tmp_path / "no-config").mkdir()
    out = tool.open_door_item(tmp_path / "no-config", "finney", both)
    assert (out["state"], out["code"]) == (tool.UNKNOWN, "receiver_config_unreadable")


def test_a_pending_weights_loop_is_named_never_assumed(tool, tmp_path):
    """Day-of: the finney weights loop starts only after the mainnet doors open, so the open precheck names it pending.
    Pending relaxes the one-loop-per-network count only; every binding rule still holds.
    """
    test_door, test_argv = _door(tmp_path, "test-rs40", "testnet")
    main_door, main_argv = _door(tmp_path, "main-m1", "finney")
    testnet_loop = ["/home/carbon/venv/bin/python", "/home/carbon/wcycle5.py"]
    both = ["testnet", "finney"]
    first = _proc_env(tmp_path / "first", {11: (test_argv, {}), 15: (testnet_loop, {})})
    out = tool.chain_binding_item([test_door], both, proc=first, receivers_expected=1)
    assert (out["state"], out["networks_without_a_loop"]) == (tool.UNKNOWN, ["finney"])
    out = tool.chain_binding_item(
        [test_door], both, proc=first, receivers_expected=1, loops_pending=("finney",)
    )
    assert (out["state"], out["loops_pending"]) == (tool.PASS, ["finney"])
    # the second mainnet door: the first one runs, and must still be bound to finney
    crossed = _proc_env(
        tmp_path / "crossed",
        {11: (test_argv, {}), 12: (main_argv, {}), 15: (testnet_loop, {})},
    )
    out = tool.chain_binding_item(
        [test_door, main_door],
        both,
        proc=crossed,
        receivers_expected=2,
        loops_pending=("finney",),
    )
    assert (out["state"], out["code"]) == (tool.REFUSE, "process_not_on_the_live_chain")
    # pending never excuses a missing TESTNET loop
    no_loop = _proc_env(tmp_path / "no_loop", {11: (test_argv, {})})
    out = tool.chain_binding_item(
        [test_door], both, proc=no_loop, receivers_expected=1, loops_pending=("finney",)
    )
    assert (out["state"], out["networks_without_a_loop"]) == (tool.UNKNOWN, ["testnet"])


def _unit(tmp_path, root, network="finney", *, extra=(), drop_in=None, config=None):
    """A door unit as `receiver_setup service` writes it (and an optional drop-in), for ``root``."""
    unit = tmp_path / "units" / f"{root.name}.service"
    unit.parent.mkdir(parents=True, exist_ok=True)
    config = config or root / "receiver" / "receiver.json"
    lines = [
        "[Unit]", "Description=Carbon validator receiver", "", "[Service]", "Type=simple",
        "Environment=OPENBLAS_CORETYPE=Haswell", f"Environment=CARBON_CHAIN_NETWORK={network}", *extra,
        f"ExecStart=/c/.venv/bin/python -B -m carbon.challenge_validator.direct_receiver --config {config}",
        "", "[Install]", "WantedBy=default.target", "",
    ]  # fmt: skip
    unit.write_text("\n".join(lines), encoding="utf-8")
    if drop_in is not None:
        (unit.parent / (unit.name + ".d")).mkdir()
        (unit.parent / (unit.name + ".d") / "z.conf").write_text(
            drop_in, encoding="utf-8"
        )
    return unit


def _loaded_as_written(tool, monkeypatch, unit_dir):
    """`systemctl --user show` as systemd would answer after a daemon-reload: what the unit file (+ drop-ins) says."""

    def show(name):
        unit = next(Path(unit_dir).rglob(name))
        env, files, exec_start, _ = tool._unit_service(unit)
        return {
            "LoadState": "loaded",
            "NeedDaemonReload": "no",
            "Environment": " ".join(f"{k}={v}" for k, v in env.items()),
            "EnvironmentFiles": " ".join(files),
            "ExecStart": "{ path=/c/.venv/bin/python ; argv[]="
            + (exec_start or "")
            + " ; }",
        }

    monkeypatch.setattr(tool, "UNIT_SHOW", show)


def test_the_open_door_unit_binds_its_own_network(tool, tmp_path, monkeypatch):
    """R-a (V2C 21:13): the installed, not yet started unit is read: its network, no localnet variable, no unread
    environment file, and it runs this root; then (Deploy-C) what systemd LOADED for it says the same.
    """
    _loaded_as_written(tool, monkeypatch, tmp_path)
    root = _fresh(tmp_path, "m1")
    ok = _unit(tmp_path, root)
    out = tool.new_unit_item(root, "finney", ok)
    assert (out["state"], out["network"], out["loaded"]) == (tool.PASS, "finney", True)

    # what systemd loaded wins: an edit without a daemon-reload, a stale load, a loaded testnet binding, no read
    def loaded(**props):
        base = {
            "LoadState": "loaded",
            "NeedDaemonReload": "no",
            "Environment": "CARBON_CHAIN_NETWORK=finney",
            "EnvironmentFiles": "",
            "ExecStart": f"{{ argv[]=python --config {root}/receiver/receiver.json ; }}",
        }
        monkeypatch.setattr(tool, "UNIT_SHOW", lambda name: {**base, **props})
        out = tool.new_unit_item(root, "finney", ok)
        return out["state"], out.get("code")

    assert loaded() == (tool.PASS, None)
    assert loaded(NeedDaemonReload="yes") == (tool.REFUSE, "unit_not_loaded_as_written")
    assert loaded(LoadState="not-found") == (tool.REFUSE, "unit_not_loaded_as_written")
    assert loaded(Environment="CARBON_CHAIN_NETWORK=testnet") == (
        tool.REFUSE,
        "unit_network_not_the_door_network",
    )
    assert loaded(
        Environment="CARBON_CHAIN_NETWORK=finney CARBON_LOCALNET_GENESIS=0x1"
    ) == (tool.REFUSE, "unit_has_localnet_variable")
    assert loaded(EnvironmentFiles="/etc/carbon.env (ignore_errors=no)") == (
        tool.UNKNOWN,
        "unit_environment_file_unread",
    )
    assert loaded(ExecStart="{ argv[]=python --config /elsewhere ; }") == (
        tool.REFUSE,
        "unit_runs_another_root",
    )
    monkeypatch.setattr(tool, "UNIT_SHOW", lambda name: None)
    out = tool.new_unit_item(root, "finney", ok)
    assert (out["state"], out["code"]) == (tool.UNKNOWN, "unit_loaded_state_unread")
    _loaded_as_written(tool, monkeypatch, tmp_path)

    def code(unit, network="finney"):
        out = tool.new_unit_item(root, network, unit)
        return out["state"], out.get("code")

    def other(name, **kw):
        sub = tmp_path / name
        sub.mkdir()
        return _unit(sub, root, **kw)

    wrong = (tool.REFUSE, "unit_network_not_the_door_network")
    assert code(ok, "testnet") == wrong
    assert code(tmp_path / "none.service") == (tool.REFUSE, "new_unit_missing")
    # a testnet-bound unit, or one naming no network (its shell would decide: never a pass)
    assert code(other("a", network="testnet")) == wrong
    assert code(other("b", network="")) == wrong
    # a drop-in overrides the unit, as systemd applies it
    drop = "[Service]\nEnvironment=CARBON_LOCALNET_ENDPOINT=ws://127.0.0.1:19944\n"
    assert code(other("c", drop_in=drop)) == (
        tool.REFUSE,
        "unit_has_localnet_variable",
    )
    assert (
        code(
            other(
                "d", drop_in='[Service]\nEnvironment="CARBON_CHAIN_NETWORK=testnet"\n'
            )
        )
        == wrong
    )
    unread = other("e", extra=("EnvironmentFile=/etc/carbon.env",))
    assert code(unread) == (tool.UNKNOWN, "unit_environment_file_unread")
    elsewhere = tmp_path / "other" / "receiver" / "receiver.json"
    assert code(other("f", config=elsewhere)) == (tool.REFUSE, "unit_runs_another_root")
    # the default path is the one receiver_setup.unit_name gives this root
    from carbon.challenge_validator import receiver_setup

    assert tool.door_unit_path(root).name == receiver_setup.unit_name(root) + ".service"


def _pin(finney="f" * 64):
    """An exam_producer.json pinning a testnet key and (unless None) a finney key."""
    networks = {"testnet-567": {"decision": "T", "producer_public_key": "e" * 64}}
    networks["finney-116"] = {"decision": "M", "producer_public_key": finney}
    return json.dumps(
        {"networks": networks, "schema": "carbon.validator.exam-producer.v3"}
    )


def test_the_release_pins_a_producer_key_for_the_door_network(tool, repo):
    """(f, Deploy-C): the tree the door runs pins its network's producer key (what `pinned_producer_key` reads)."""
    root, base = repo
    out = tool.producer_key_item(root, base, "finney")
    assert (out["state"], out["code"]) == (
        tool.REFUSE,
        "producer_pin_missing_in_release",
    )
    unset = _commit(root, {tool.PRODUCER_PIN: _pin(None)}, "testnet only")
    out = tool.producer_key_item(root, unset, "finney")
    assert (out["state"], out["code"]) == (tool.REFUSE, "producer_key_not_pinned")
    pinned = _commit(root, {tool.PRODUCER_PIN: _pin()}, "the mainnet pin")
    out = tool.producer_key_item(root, pinned, "finney")
    assert (out["state"], out["network"], out["decision"]) == (
        tool.PASS,
        "finney-116",
        "M",
    )
    assert tool.producer_key_item(root, pinned, "testnet")["network"] == "testnet-567"
    bad = _commit(root, {tool.PRODUCER_PIN: "{"}, "broken")
    assert tool.producer_key_item(root, bad, "finney")["state"] == tool.UNKNOWN


def test_precheck_open_end_to_end(tool, repo, tmp_path, capsys, monkeypatch):
    root, base = repo
    new = _commit(
        root, {"docs/notes.md": "open\n", tool.PRODUCER_PIN: _pin()}, "the release"
    )
    heads = _heads(tmp_path, [(new, "FINAL")])
    store = _store(tmp_path, "store-finney", "finney-116")
    fresh = _fresh(tmp_path, "m1", store=store, accepted=new)
    release = json.dumps(tool.manifest(root, new))
    (fresh / "release.json").write_text(release, encoding="utf-8")
    unit = _unit(tmp_path, fresh)
    _loaded_as_written(tool, monkeypatch, tmp_path)
    # the testnet door already serving on this host
    test_door, test_argv = _door(tmp_path, "rs40", "testnet")
    (test_door / "receiver" / "state").mkdir()
    config = test_door / "receiver" / "receiver.json"
    cfg = json.loads(config.read_text(encoding="utf-8"))
    cfg.update(root=str(test_door / "receiver" / "state"), accepted_revision=base)
    config.write_text(json.dumps(cfg), encoding="utf-8")
    monkeypatch.setattr(
        tool,
        "PROC",
        _proc_env(
            tmp_path / "host",
            {21: (test_argv, {}), 22: (["bash", "/home/carbon/weights-loop5.sh"], {})},
        ),
    )
    argv = [
        "precheck", "--mode", "open", "--repo", str(root), "--new-rev", new,
        "--new-root", str(fresh), "--final-heads", str(heads), "--new-network", "finney",
        "--expect-network", "testnet", "--expect-network", "finney", "--weights-loop-pending", "finney",
        "--new-unit", str(unit), "--host-root", str(test_door), "--host-root", str(fresh),
    ]  # fmt: skip
    items = ["final_heads", "accepted", "release", "open_door", "unit", "producer_key"]
    items += ["receivers", "chain_binding", "lock_versions"]
    for mode in ("open", "release"):  # release: the lock-in's day-of name for open
        rc = tool.main([a if a != "open" else mode for a in argv])
        out = json.loads(capsys.readouterr().out)
        others = {k: v["state"] for k, v in out["items"].items() if k != "disk"}
        assert others == dict.fromkeys(items, tool.PASS)
        # the disk floor needs 20 GiB free: a full PASS or a disk-only REFUSE
        assert (rc, out["state"]) in ((0, tool.PASS), (3, tool.REFUSE))
        assert out["release_class"] == {"class": None, "basis": "open_has_no_old_door"}
        assert "old" not in out and (out["new"], out["mode"]) == (new, "open")
        assert out.get("mode_given") == (None if mode == "open" else "release")

    # the staging marker on the fresh root refuses
    (fresh / "receiver" / "STAGING").write_text("", encoding="utf-8")
    assert tool.main(argv) == 3
    out = json.loads(capsys.readouterr().out)
    assert out["items"]["open_door"]["code"] == "new_root_is_staging"
    assert out["items"]["chain_binding"]["code"] == "staging_root_on_host"
    (fresh / "receiver" / "STAGING").unlink()
    # the same fresh root prepared from a legacy (testnet-567) store refuses before it opens
    (store / ".store-network.json").unlink()
    assert tool.main(argv) == 3
    out = json.loads(capsys.readouterr().out)
    assert out["items"]["open_door"]["code"] == "pack_store_network_mismatch"
    # a missing new root refuses
    assert (
        tool.main([a if a != str(fresh) else str(tmp_path / "gone") for a in argv]) == 3
    )
    out = json.loads(capsys.readouterr().out)
    assert out["items"]["open_door"]["code"] == "new_root_missing"

    # usage (exit 2): no network, an OLD, an option open mode does not read (R-b), a network not expected, a pending
    # loop on a network not expected
    i = argv.index("--new-network")
    head = argv[:i]  # mode, repo, rev, root, heads

    def line(*extra):
        return [*head, *extra, "--host-root", str(test_door)]

    for bad in (
        argv[:i] + argv[i + 2 :],
        [*argv, "--old-root", str(test_door)],
        [*argv, "--old-rev", base],
        [*argv, "--new-pack", PACK],
        [*argv, "--declared", str(heads)],
        [*argv, "--allow-chain-degraded", "why"],
        [*argv, "--older-root", str(test_door)],
        line("--new-network", "finney", "--expect-network", "testnet"),
        line("--new-network", "testnet", "--weights-loop-pending", "finney"),
    ):
        with pytest.raises(SystemExit):
            tool.main(bad)


def test_prepare_and_switch_keep_their_old_door_and_refuse_unused_options(
    tool, repo, tmp_path
):
    root, base = repo
    full = [
        "precheck", "--mode", "prepare", "--repo", str(root),
        "--old-rev", base, "--new-rev", base, "--old-pack", PACK, "--new-pack", PACK,
        "--old-root", str(tmp_path), "--new-root", str(tmp_path), "--final-heads", str(tmp_path / "h.tsv"),
    ]  # fmt: skip
    for flag in ("--old-rev", "--old-pack", "--new-pack", "--old-root"):
        i = full.index(flag)
        with pytest.raises(SystemExit):
            tool.main(full[:i] + full[i + 2 :])
    # (R-b) prepare reads no host, chain or open-mode option: each refuses, never silently ignored
    for extra in (
        ["--new-network", "finney"],
        ["--weights-loop-pending", "finney"],
        ["--new-unit", str(tmp_path)],
        ["--expect-network", "finney"],
        ["--host-root", str(tmp_path)],
        ["--allow-mixed-lock", "why"],
        ["--allow-chain-degraded", "why"],
        ["--older-root", str(tmp_path)],
    ):
        with pytest.raises(SystemExit):
            tool.main([*full, *extra])
    switch = [a if a != "prepare" else "switch" for a in full]
    for extra in (["--new-network", "finney"], ["--new-unit", str(tmp_path)]):
        with pytest.raises(SystemExit):
            tool.main([*switch, "--host-root", str(tmp_path), *extra])
