"""The retained-entry regrade through the receiver (scripts/dev/design_value_parts_regrade_graph.py).

The receiver's serve is replaced by the toy grade of `test_pool_exam` (every number there is a SYNTHETIC test value) that
then writes the bound evaluation a regrade leaves; the tool's own parts are pinned: the entry's files are copied and the
receiver's directories are not changed, the exact A/D self-check, the per-target predicted and true values at the pick,
the A_gen sweep, and that a regrade which binds nothing is refused. The container run and the real graph inference are NOT
exercised here (a box run is the evidence for those).
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tests" / "cpu"))

from test_pool_exam import grade
from test_pool_plugin import U, truth

from carbon.challenge_validator import cpu_pin
from scripts.dev import design_value_parts_regrade_graph as tool

ORIGIN = "rtsk_" + "a" * 64
ENTRY = "sha256:" + "b" * 64


def weak(rows):
    return [[v + 6 * U for v in truth(r)] for r in rows]


def _tree(directory):
    return {
        str(p.relative_to(directory)): (
            hashlib.sha256(p.read_bytes()).hexdigest(),
            p.stat().st_mtime_ns,
        )
        for p in sorted(directory.rglob("*"))
        if p.is_file()
    }


@pytest.fixture
def receiver(tmp_path):
    artifacts, entries = tmp_path / "artifacts", tmp_path / "entries"
    (artifacts / ORIGIN).mkdir(parents=True)
    (entries).mkdir()
    for name, raw in (
        ("recipe.json", b'{"source": {"kind": "graph"}}'),
        ("state.npz", b"state-bytes"),
        ("predictions.json", b"[[1.0]]"),
    ):
        (artifacts / ORIGIN / name).write_bytes(raw)
    (artifacts / (ORIGIN + ".roles.json")).write_bytes(b"{}")
    (artifacts / (ORIGIN + ".custody.json")).write_bytes(b"{}")
    (entries / ("b" * 64 + ".json")).write_bytes(
        json.dumps({"custody_receipt": {"file": ORIGIN + ".custody.json"}}).encode()
    )
    return artifacts, entries


def fake_serve(tmp_path, *, legs=None, state="BOUND_DEVELOPMENT_ONLY", **options):
    """The receiver's regrade: the toy grade (recorded by the tool), then the bound evaluation it leaves."""
    seen = []

    def serve(config, entry_id, artifacts, entries):
        seen.append((entry_id, artifacts, entries))
        measured = grade(weak, **options)
        binding = tmp_path / f"binding{len(seen)}.json"
        binding.write_text(
            json.dumps(
                {"model_p": {"legs": legs or {"A": measured["A"], "D": measured["D"]}}}
            )
        )
        return {
            "private_evaluation_state": state,
            "private_evaluation_path": str(binding),
        }

    serve.seen = seen
    return serve


def _run(tmp_path, receiver, stored, serve, **extra):
    artifacts, entries = receiver
    return tool.regrade(
        tmp_path / "receiver.json",
        ENTRY,
        artifact_directory=artifacts,
        entry_directory=entries,
        work=tmp_path / "work",
        stored=stored,
        serve=serve,
        **extra,
    )


def test_a_regrade_equal_to_the_stored_legs_matches_and_reports_the_pick(
    tmp_path, receiver
):
    base = grade(weak)
    report = _run(tmp_path, receiver, (base["A"], base["D"]), fake_serve(tmp_path))
    assert report["ok"] is True
    assert report["regraded_a"] == base["A"] and report["regraded_d"] == base["D"]
    assert report["regraded_d"] == report["recomputed_d"]
    targets = [t for s in report["sets"] for t in s["targets"]]
    assert targets
    for target in targets:
        for value in target["pick"].values():
            assert set(value) == {"predicted", "true"}
            # the toy model is the truth plus 6 U on every output
            assert value["predicted"] - value["true"] == pytest.approx(6 * U)
    text = tool.render(report)
    assert "pick f: predicted=" in text and text.splitlines()[-1] == "MATCH"


def test_pick_values_can_be_left_out(tmp_path, receiver):
    base = grade(weak)
    report = _run(
        tmp_path,
        receiver,
        (base["A"], base["D"]),
        fake_serve(tmp_path),
        pick_values=False,
    )
    assert report["ok"] and all(
        "pick" not in t for s in report["sets"] for t in s["targets"]
    )


@pytest.mark.parametrize("which", ["A", "D"])
def test_a_stored_leg_off_in_the_last_bit_is_a_mismatch(tmp_path, receiver, which):
    base = grade(weak)
    nudge = lambda x: x + 1e-15 * max(1.0, abs(x))
    stored = (
        (nudge(base["A"]), base["D"]) if which == "A" else (base["A"], nudge(base["D"]))
    )
    assert _run(tmp_path, receiver, stored, fake_serve(tmp_path))["ok"] is False


def test_a_binding_whose_d_differs_from_the_graders_is_not_ok(tmp_path, receiver):
    base = grade(weak)
    serve = fake_serve(tmp_path, legs={"A": base["A"], "D": base["D"] + 0.001})
    assert (
        _run(tmp_path, receiver, (base["A"], base["D"] + 0.001), serve)["ok"] is False
    )


def test_a_gated_model_matches_only_a_stored_zero_d(tmp_path, receiver):
    from test_pool_exam import CEILING

    slow = {"speed": [CEILING * 3] * 20}
    base = grade(weak, **slow)
    report = _run(tmp_path, receiver, (base["A"], 0.0), fake_serve(tmp_path, **slow))
    assert report["gated"] is True and report["sets"] == [] and report["ok"] is True


def test_a_regrade_that_binds_nothing_is_refused(tmp_path, receiver):
    serve = fake_serve(tmp_path, state="UNAVAILABLE")
    with pytest.raises(tool.RegradeError, match="bound no evaluation"):
        _run(tmp_path, receiver, (0.0, 0.0), serve)


def test_the_receivers_directories_are_copied_not_written(tmp_path, receiver):
    artifacts, entries = receiver
    before = (_tree(artifacts), _tree(entries))
    base = grade(weak)
    serve = fake_serve(tmp_path)
    _run(tmp_path, receiver, (base["A"], base["D"]), serve)
    assert (_tree(artifacts), _tree(entries)) == before
    ((entry_id, used_artifacts, used_entries),) = serve.seen
    assert entry_id == ENTRY
    assert used_artifacts == tmp_path / "work" / "artifacts"
    assert (used_artifacts / ORIGIN / "state.npz").read_bytes() == b"state-bytes"
    assert (used_artifacts / (ORIGIN + ".custody.json")).is_file()
    assert [p.name for p in used_entries.iterdir()] == ["b" * 64 + ".json"]


def test_in_place_runs_on_the_receivers_directories(tmp_path, receiver):
    base = grade(weak)
    serve = fake_serve(tmp_path)
    _run(tmp_path, receiver, (base["A"], base["D"]), serve, in_place=True)
    assert serve.seen[0][1:] == receiver


def test_a_work_inside_the_receiver_or_already_used_is_refused(tmp_path, receiver):
    artifacts, entries = receiver
    with pytest.raises(tool.RegradeError, match="inside"):
        tool.isolate(artifacts, entries, ENTRY, artifacts / "work")
    tool.isolate(artifacts, entries, ENTRY, tmp_path / "fresh")
    with pytest.raises(tool.RegradeError, match="fresh"):
        tool.isolate(artifacts, entries, ENTRY, tmp_path / "fresh")


@pytest.mark.parametrize(
    "entry_id", ["sha256:short", "b" * 64, ENTRY.replace("b", "c")]
)
def test_an_unusable_entry_is_refused(tmp_path, receiver, entry_id):
    artifacts, entries = receiver
    with pytest.raises(tool.RegradeError):
        tool.isolate(artifacts, entries, entry_id, tmp_path / "w")


def test_the_graders_functions_are_restored(tmp_path, receiver):
    from carbon.scoring import pool_exam, pool_grader

    real = (pool_grader.grade_set, pool_exam.measure_pool)
    base = grade(weak)
    _run(tmp_path, receiver, (base["A"], base["D"]), fake_serve(tmp_path))
    assert (pool_grader.grade_set, pool_exam.measure_pool) == real


def test_the_command_exits_zero_one_and_two(tmp_path, receiver, monkeypatch, capsys):
    monkeypatch.setattr(cpu_pin, "require", lambda: None)
    monkeypatch.setattr(tool, "_run_receiver", lambda *a: fake_serve(tmp_path)(*a))
    base = grade(weak)
    artifacts, entries = receiver
    runs = []

    def invoke(stored, *extra):
        runs.append(1)
        stored_file = tmp_path / "stored.json"
        stored_file.write_text(json.dumps(stored))
        return tool.main(
            [
                "--config",
                str(tmp_path / "receiver.json"),
                "--entry",
                ENTRY,
                "--artifact-directory",
                str(artifacts),
                "--entry-directory",
                str(entries),
                "--work",
                str(tmp_path / f"w{len(runs)}"),
                "--stored",
                str(stored_file),
                *extra,
            ]
        )

    assert invoke({"A": base["A"], "D": base["D"]}) == 0
    out = capsys.readouterr().out
    assert out.splitlines()[-1] == "MATCH" and "regraded A" in out
    assert invoke({"A": base["A"], "D": base["D"] + 0.5}) == 1
    capsys.readouterr()
    assert invoke({"A": base["A"]}) == 2  # no D
    assert invoke({"A": base["A"], "D": base["D"]}, "--agen-scale-sets", "x.json") == 2
    assert "--challenge and --version" in capsys.readouterr().err


def test_a_receiver_root_held_by_a_running_serve_is_refused_clearly(
    tmp_path, receiver, monkeypatch, capsys
):
    from scripts.dev.miner_launchpad.controller import LockHeld

    def held(*_args):
        raise LockHeld("held")

    monkeypatch.setattr(cpu_pin, "require", lambda: None)
    monkeypatch.setattr(tool, "_run_receiver", held)
    artifacts, entries = receiver
    stored = tmp_path / "stored.json"
    stored.write_text(json.dumps({"A": 0.5, "D": 0.5}))
    code = tool.main(
        [
            "--config",
            str(tmp_path / "receiver.json"),
            "--entry",
            ENTRY,
            "--artifact-directory",
            str(artifacts),
            "--entry-directory",
            str(entries),
            "--work",
            str(tmp_path / "w"),
            "--stored",
            str(stored),
        ]
    )
    assert code == 2
    assert "running serve unit" in capsys.readouterr().err
