"""The retained-entry re-grade (scripts/dev/design_value_parts_regrade.py): the recal's grade path, parts recorded.

Run on the synthetic toy Challenge of `test_pool_exam` (every number there is a SYNTHETIC test value) with the container
run replaced by that toy grade: what is pinned is the packaging of a retained model into the recal's artifact form, the
exact A/D self-check, the read-only handling of the receiver's files and that only scalars are printed."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tests" / "cpu"))

from test_pool_exam import grade
from test_pool_plugin import U, truth

from carbon.challenge_validator import calibration_grade as cg
from carbon.challenge_validator import calibration_grade_run as runner
from carbon.challenge_validator import cpu_pin
from scripts.dev import design_value_parts_regrade as tool

TRAIN = "sha256:" + "7" * 64
BUNDLE = "sha256:" + "1" * 64
PARENT = "sha256:" + "2" * 64
TREE = "sha256:" + "3" * 64
IMAGE = "sha256:" + "4" * 64


def weak(rows):
    return [[v + 6 * U for v in truth(r)] for r in rows]


def _recipe(runtime="torch-cu130-py311", kind="bundle"):
    return {
        "schema": "carbon.construction-recipe.v1",
        "challenge": {"id": "f08-ribbed-bracket", "train_digest": TRAIN},
        "source": {
            "kind": kind,
            "bundle_ref": {
                "bundle_digest": BUNDLE,
                "runtime_profile_id": runtime,
                "language": "python",
            },
        },
    }


def _retained(tmp_path, *, overlay=True, **recipe_options):
    directory = tmp_path / "artifacts" / ("rtsk_" + "a" * 64)
    directory.mkdir(parents=True)
    (directory / "recipe.json").write_bytes(
        json.dumps(_recipe(**recipe_options), sort_keys=True).encode()
    )
    (directory / "state.npz").write_bytes(b"retained-state-bytes")
    image = (
        {
            "parent_image_id": PARENT,
            "overlay_tree_digest": TREE,
            "bundle_digest": BUNDLE,
        }
        if overlay
        else {"image_id": IMAGE, "parent_image_id": PARENT, "context_digest": TREE}
    )
    (directory / "image.json").write_bytes(json.dumps(image).encode())
    # a file the tool must never read as an input, and never change
    (directory / "predictions.json").write_bytes(b"[[1.0, 2.0]]")
    return directory


def _tree(directory):
    return {
        str(p.relative_to(directory)): (
            hashlib.sha256(p.read_bytes()).hexdigest(),
            p.stat().st_mtime_ns,
        )
        for p in sorted(directory.rglob("*"))
        if p.is_file()
    }


# --- packaging -------------------------------------------------------------------------------------------


@pytest.mark.parametrize("overlay", [True, False])
def test_the_retained_model_becomes_a_verified_calibration_artifact(tmp_path, overlay):
    retained = _retained(tmp_path, overlay=overlay)
    out = tmp_path / "work" / "artifact"
    out.parent.mkdir()
    manifest = tool.artifact_from_retained(
        retained,
        out,
        challenge_id="f08-ribbed-bracket",
        version="1.7",
        name=retained.name,
    )
    # the recal's own loader verifies it, with the retained bytes unchanged
    artifact = cg.load_artifact(out, challenge_id="f08-ribbed-bracket")
    assert artifact.state_bytes == b"retained-state-bytes"
    assert artifact.recipe_bytes == (retained / "recipe.json").read_bytes()
    assert manifest["train_sha256"] == TRAIN and manifest["bundle_sha256"] == BUNDLE
    assert manifest["worker_image_digest"] == (TREE if overlay else IMAGE)
    assert manifest["parent_image_digest"] == PARENT
    assert manifest["runtime"] == "torch-cu130-py311" and manifest["seed"] == 0


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: (d / "image.json").unlink(),
        lambda d: (d / "state.npz").unlink(),
        lambda d: (d / "recipe.json").write_bytes(b"not json"),
        lambda d: (d / "image.json").write_bytes(b'{"parent_image_id": "x"}'),
        lambda d: (d / "image.json").write_bytes(b"[]"),
    ],
    ids=["no-image", "no-state", "bad-recipe", "bad-digest", "image-not-object"],
)
def test_an_unusable_retained_directory_is_refused(tmp_path, mutate):
    retained = _retained(tmp_path)
    mutate(retained)
    with pytest.raises(tool.RegradeError):
        tool.artifact_from_retained(
            retained, tmp_path / "out", challenge_id="f08-ribbed-bracket", version="1.7"
        )


def test_a_graph_model_is_refused_here(tmp_path):
    retained = _retained(tmp_path, kind="graph")
    with pytest.raises(tool.RegradeError, match="bundle model"):
        tool.artifact_from_retained(
            retained, tmp_path / "out", challenge_id="f08-ribbed-bracket", version="1.7"
        )


# --- the stored legs -------------------------------------------------------------------------------------


def test_the_stored_legs_are_read_from_a_flat_object_or_one_legs_object():
    assert tool.stored_legs({"A": 0.5, "D": 0.25}) == (0.5, 0.25)
    nested = {
        "evidence": {"model_p": {"score_status": "X", "legs": {"A": 0.5, "D": 0.25}}}
    }
    assert tool.stored_legs(nested) == (0.5, 0.25)
    for bad in (
        {},
        {"A": 0.5},
        {"A": True, "D": 0.25},
        {"A": "0.5", "D": 0.25},
        {"a": {"legs": {"A": 0.5, "D": 0.25}}, "b": {"legs": {"A": 0.6, "D": 0.25}}},
    ):
        with pytest.raises(tool.RegradeError):
            tool.stored_legs(bad)
    # the same pair twice is one pair
    twice = {"a": {"legs": {"A": 0.5, "D": 0.25}}, "b": {"legs": {"A": 0.5, "D": 0.25}}}
    assert tool.stored_legs(twice) == (0.5, 0.25)


# --- the re-grade ----------------------------------------------------------------------------------------


def fake_run(serve=weak, **options):
    """Stands in for `calibration_grade_run.run`: the toy grade, whose pool functions the tool records."""

    def run(**_kwargs):
        measured = grade(serve, **options)
        return {"A": measured["A"], "D": measured["D"], "total": 0.5}

    return run


def _call(tmp_path, stored, run, **extra):
    return tool.regrade(
        _retained(tmp_path),
        pack=tmp_path,
        challenge="f08-ribbed-bracket",
        version="1.7",
        work=tmp_path / "work",
        judge_image=None,
        stored=stored,
        grade=run,
        **extra,
    )


def test_a_regrade_whose_a_and_d_equal_the_stored_legs_matches_exactly(tmp_path):
    base = grade(weak)
    report = _call(tmp_path, (base["A"], base["D"]), fake_run())
    assert report["ok"] is True
    assert report["regraded_a"] == report["stored_a"] == base["A"]
    assert (
        report["regraded_d"]
        == report["recomputed_d"]
        == report["stored_d"]
        == base["D"]
    )
    assert [len(s["targets"]) for s in report["sets"]] == [2, 2]


@pytest.mark.parametrize("which", ["A", "D"])
def test_a_stored_leg_that_differs_in_the_last_bit_is_a_mismatch(tmp_path, which):
    base = grade(weak)
    a, d = base["A"], base["D"]
    nudge = lambda x: x + 1e-15 * max(1.0, abs(x))
    stored = (nudge(a), d) if which == "A" else (a, nudge(d))
    report = _call(tmp_path, stored, fake_run())
    assert report["ok"] is False


def test_a_gated_model_matches_only_a_stored_zero_d(tmp_path):
    from test_pool_exam import CEILING

    slow = fake_run(speed=[CEILING * 3] * 20)
    base = grade(weak, speed=[CEILING * 3] * 20)
    report = _call(tmp_path, (base["A"], 0.0), slow)
    assert report["gated"] is True and report["sets"] == [] and report["ok"] is True
    assert _call(tmp_path / "again", (base["A"], 0.25), slow)["ok"] is False


def test_the_receivers_files_are_never_written_and_work_may_not_be_inside_them(
    tmp_path,
):
    retained = _retained(tmp_path)
    before = _tree(retained)
    base = grade(weak)
    tool.regrade(
        retained,
        pack=tmp_path,
        challenge="f08-ribbed-bracket",
        version="1.7",
        work=tmp_path / "scratch",
        judge_image=None,
        stored=(base["A"], base["D"]),
        grade=fake_run(),
    )
    assert _tree(retained) == before  # not a byte, not a modification time
    with pytest.raises(tool.RegradeError, match="inside --retained"):
        tool.regrade(
            retained,
            pack=tmp_path,
            challenge="f08-ribbed-bracket",
            version="1.7",
            work=retained / "work",
            judge_image=None,
            stored=(0.0, 0.0),
            grade=fake_run(),
        )
    assert _tree(retained) == before


def test_the_graders_functions_are_restored_after_a_regrade(tmp_path):
    from carbon.scoring import pool_exam, pool_grader

    real = (pool_grader.grade_set, pool_exam.measure_pool)
    base = grade(weak)
    _call(tmp_path, (base["A"], base["D"]), fake_run())
    assert (pool_grader.grade_set, pool_exam.measure_pool) == real


# --- the command -----------------------------------------------------------------------------------------

ALLOWED = re.compile(
    r"^(set \d+: C=\S+ mean_d=\S+ min\(mean_d,C\)=\S+"
    r"|  target \d+\.\d+ \[[0-9a-f]{16}\]: feasible=(True|False) reason=\w+ d=\S+ q=\S+ e=\S+ s_h=\S+ h=\S+"
    r" reached_reference=(True|False) queries=\d+ regret=\S+ \(derived \(not a grader output\)\)"
    r"|gated: .*|stored D     = \S+|recomputed D = \S+|stored A     = \S+|regraded A   = \S+|regraded D   = \S+"
    r"|MATCH|MISMATCH)$"
)


@pytest.fixture
def command(tmp_path, monkeypatch):
    monkeypatch.setattr(cpu_pin, "require", lambda: None)
    monkeypatch.setattr(runner, "run", lambda **kw: fake_run()(**kw))
    monkeypatch.setattr(runner, "_load_judge_image", lambda path: object())
    retained = _retained(tmp_path)
    base = grade(weak)

    runs = []

    def invoke(stored, *extra):
        runs.append(
            1
        )  # a fresh scratch directory for every run, as the TL gives each entry
        stored_file = tmp_path / "stored.json"
        stored_file.write_text(json.dumps(stored))
        return tool.main(
            [
                "--retained", str(retained),
                "--pack", str(tmp_path),
                "--challenge", "f08-ribbed-bracket",
                "--version", "1.7",
                "--work", str(tmp_path / f"work{len(runs)}"),
                "--judge-image", str(tmp_path / "judge.json"),
                "--stored", str(stored_file),
                *extra,
            ]
        )  # fmt: skip

    return invoke, base


def test_a_match_prints_scalars_only_and_exits_zero(command, capsys):
    invoke, base = command
    assert invoke({"A": base["A"], "D": base["D"]}) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[-1] == "MATCH"
    for line in lines:
        assert ALLOWED.match(line), line
    assert invoke({"legs": {"A": base["A"], "D": base["D"]}}, "--json") == 0
    document = json.loads(capsys.readouterr().out)
    assert document["ok"] is True and "inputs" not in json.dumps(document)


def test_a_mismatch_exits_one_and_an_unusable_input_exits_two(
    command, tmp_path, capsys
):
    invoke, base = command
    assert invoke({"A": base["A"], "D": base["D"] + 1e-6}) == 1
    assert capsys.readouterr().out.splitlines()[-1] == "MISMATCH"
    assert invoke({"A": base["A"]}) == 2
    assert "REFUSED" in capsys.readouterr().err
    assert tool.main(["--retained", str(tmp_path / "absent"), "--pack", "p", "--challenge", "c", "--version", "v",
                      "--work", str(tmp_path / "w"), "--stored", str(tmp_path / "stored.json"), "--fake"]) == 2  # fmt: skip


def test_a_missing_judge_image_is_refused_unless_fake(command, capsys, tmp_path):
    _invoke, base = command
    stored = tmp_path / "s.json"
    stored.write_text(json.dumps({"A": base["A"], "D": base["D"]}))
    args = ["--retained", str(tmp_path / "artifacts" / ("rtsk_" + "a" * 64)), "--pack", str(tmp_path),
            "--challenge", "f08-ribbed-bracket", "--version", "1.7", "--work", str(tmp_path / "w2"),
            "--stored", str(stored)]  # fmt: skip
    assert tool.main(args) == 2
    assert "judge-image is required" in capsys.readouterr().err
    assert tool.main([*args, "--fake"]) == 0


def test_the_tool_does_not_open_the_receiver_or_write_outside_work():
    source = Path(tool.__file__).read_text(encoding="utf-8")
    for forbidden in ("PoolStore", "AttemptLedger", "ReceiptJournal"):
        assert forbidden not in source
    assert (
        "write_text" not in source and "unlink" not in source and "shutil" not in source
    )
