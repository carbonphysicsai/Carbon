"""build_path_bench (S6c / P-10 Option 1): its own logic without Docker. A recipe directory's graph must be the one
its recipe names; the graph is staged where the door reads a miner's upload (the door's own envelope read returns it);
N slots run N builds at a time and never two on one slot's cores; the summary counts failures apart.
"""

from __future__ import annotations

import importlib.util
import json
import threading
import time
from pathlib import Path

import pytest

from carbon.battery import public_scaffold
from carbon.development_session.construction_recipe import (
    ConstructionRecipe,
    graph_envelope_from_workspace,
)
from carbon.level4 import staging

ROOT = Path(__file__).resolve().parents[2]


def _bench():
    spec = importlib.util.spec_from_file_location(
        "build_path_bench", ROOT / "scripts" / "dev" / "build_path_bench.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _recipe_dir(root, name, recipe):
    manifest, files = public_scaffold.graph()
    directory = root / name
    staging.write_directory(directory / "graph", manifest, files)
    (directory / "recipe.json").write_text(json.dumps(recipe))
    return directory


def test_a_recipe_loads_only_with_its_own_graph(tmp_path):
    bench = _bench()
    good = _recipe_dir(tmp_path, "scaffold", public_scaffold.recipe())
    ((name, recipe, manifest, files),) = bench.load_recipes([good])
    assert name == "scaffold"
    assert recipe == public_scaffold.recipe()
    assert (manifest, files) == public_scaffold.graph()
    other = public_scaffold.recipe()
    other["source"] = {**other["source"], "submission_digest": "sha256:" + "0" * 64}
    bad = _recipe_dir(tmp_path, "other", other)
    with pytest.raises(SystemExit, match="not the recipe's"):
        bench.load_recipes([bad])
    with pytest.raises(SystemExit, match="must differ"):
        bench.load_recipes([good, good])


def test_the_graph_is_staged_where_the_door_reads_an_upload(tmp_path):
    bench = _bench()
    manifest, files = public_scaffold.graph()
    ledger = bench.scratch_ledger(tmp_path / "ledger")
    bench.stage(ledger, manifest, files)
    envelope = graph_envelope_from_workspace(
        ledger, bench.OWNER, ConstructionRecipe.from_dict(public_scaffold.recipe())
    )
    assert type(envelope) is bytes and envelope
    with pytest.raises(FileExistsError):
        bench.scratch_ledger(tmp_path / "ledger")  # every build gets a fresh ledger


def _args(bench, tmp_path, recipe_dir, **extra):
    argv = [
        "--challenge",
        "c",
        "--version",
        "1",
        "--recipe-dir",
        str(recipe_dir),
        "--cpu-image-identity",
        "cpu.json",
        "--cpu-build",
        "--slot-cpusets",
        "0-3,4-7,8-11",
        "--work",
        str(tmp_path / "work"),
    ]
    for key, value in extra.items():
        argv += ["--" + key.replace("_", "-"), value]
    return argv


def test_n_slots_never_run_two_builds_on_one_slot(tmp_path, monkeypatch, capsys):
    bench = _bench()
    recipe_dir = _recipe_dir(tmp_path, "scaffold", public_scaffold.recipe())
    from carbon.challenge_kit import physical_material
    from carbon.reconstruction.worker import docker_runtime

    monkeypatch.setattr(physical_material, "bundle_material", lambda *a: {})
    monkeypatch.setattr(docker_runtime, "load_image_identity", lambda path: path)
    monkeypatch.setattr(bench, "instrument", lambda: None)
    busy, overlaps, guard = set(), [], threading.Lock()

    def fake(job, args, context):
        n, index, slot, (name, *_rest) = job
        with guard:
            if slot in busy:
                overlaps.append(slot)
            busy.add(slot)
        time.sleep(0.01 * (index % 3))
        with guard:
            busy.discard(slot)
        outcome = "OK" if index != 4 else "candidate_build_refused"
        return {
            "n": n,
            "build": index,
            "recipe": name,
            "outcome": outcome,
            "wall_s": 1.0 + index,
        }

    monkeypatch.setattr(bench, "one_build", fake)
    assert bench.main(_args(bench, tmp_path, recipe_dir, concurrency="1,3")) == 0
    assert overlaps == []
    lines = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    header, *rest = lines
    assert header["schema"] == bench.SCHEMA
    assert header["recipes"] == {
        "scaffold": ConstructionRecipe.from_dict(public_scaffold.recipe()).digest
    }
    summaries = [line for line in rest if line.get("summary")]
    assert [(s["n"], s["builds"], s["failed"]) for s in summaries] == [
        (1, 2, 0),
        (3, 6, 1),
    ]
    builds = [line for line in rest if not line.get("summary")]
    assert sorted(line["build"] for line in builds) == list(range(8))


def test_a_level_above_the_slots_or_a_used_work_dir_is_refused(tmp_path):
    bench = _bench()
    recipe_dir = _recipe_dir(tmp_path, "scaffold", public_scaffold.recipe())
    with pytest.raises(SystemExit):
        bench.parse(_args(bench, tmp_path, recipe_dir, concurrency="4"))
    (tmp_path / "work").mkdir()
    (tmp_path / "work" / "old").write_text("x")
    with pytest.raises(SystemExit, match="must be empty"):
        bench.main(_args(bench, tmp_path, recipe_dir))


def test_the_summary_counts_only_ok_walls():
    bench = _bench()
    records = [
        {"outcome": "OK", "wall_s": 10.0},
        {"outcome": "OK", "wall_s": 30.0},
        {"outcome": "OK", "wall_s": 20.0},
        {"outcome": "FAILED", "wall_s": 999.0},
    ]
    row = bench.summary(2, records, 3600.0)
    assert (
        row["builds"],
        row["failed"],
        row["wall_p50_s"],
        row["builds_per_hour"],
    ) == (
        4,
        1,
        20.0,
        3.0,
    )
    assert row["wall_p90_s"] == 30.0
