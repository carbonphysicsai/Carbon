"""The F08 2.0 per-job harness: plan job -> five outputs, typed statuses, digests. No solver runs here (a rented pod does that);
the mesher and the solver are replaced by fakes that write the files the real ones write, and the observation is checked against
independent recomputation with the deck's own functions."""

from __future__ import annotations

import json
import math
import queue
import subprocess
import sys
from pathlib import Path

import pytest

CALCULIX = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "dev"
    / "reference_packages"
    / "calculix"
)
sys.path.insert(0, str(CALCULIX))
sys.path.insert(0, str(CALCULIX.parent))

import f08_deck as v1
import f08_deck_v2 as v2
import f08_v2_payload as payload
import f08_v2_runner as runner

HEADER = "stresses (elem, integ.pnt.,sxx,syy,szz,sxy,sxz,syz)"


def _job(**over):
    cell = payload.u_panel(20261101)[0]
    job = {
        "job_id": "f08v2-9000",
        "cell": cell["cell"],
        "kind": cell["kind"],
        "case": cell["case"],
        "h_mm": 3.0,
        "fillet_h_mm": 0.5,
        "axis": "mesh",
    }
    return {**job, **over}


def _fmt(t):
    return " ".join(f"{v:.6e}" for v in t)


def _block(rows):
    lines = [HEADER, ""]
    for element, ip, tensor in rows:
        lines.append(f"{element:10d} {ip:5d} {_fmt(tensor)}")
    lines.append("")
    return "\n".join(lines) + "\n"


# a tiny mesh: two pad triangles, a probe, a tip, the root: just what the deck and the observer read
MESH = {
    "nodes": 12,
    "elements": 5,
    "fillet_elements": 2,
    "mesh_volume_mm3": 1000.0,
    "cad_volume_mm3": 1001.0,
    "tip_node": 3,
    "probe_node": 4,
    "pad_tri6": [[1, 2, 3, 5, 6, 7], [3, 2, 4, 8, 9, 6]],
    "probe_tri6": [[1, 2, 4, 10, 11, 12]],
    "coords": {str(n): [float(n), float(n % 3), 1.0] for n in range(1, 13)},
}


def fake_mesh(directory):
    (Path(directory) / "mesh.json").write_text(json.dumps(MESH))
    (Path(directory) / "mesh.inp").write_text("** fake\n")


def ok_solver(directory, timeout_s, cores):
    (Path(directory) / "case.dat").write_text("synthetic\n")
    return {"stop_reason": "exit", "exit": 0, "wall_s": 1.5}


def test_every_job_of_the_real_plan_passes_the_job_check_and_compiles_its_mesh_script():
    document = payload.plan(20261101)
    jobs = [job for shard in document["shards"] for job in shard]
    assert len(jobs) == document["jobs"] == 120
    for job in jobs:
        case = runner.check_job(job)
        script = v2.gmsh_script_v2(case, job["h_mm"], job["fillet_h_mm"])
        assert v2.script_compiles(script)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda j: {**j, "extra": 1},
        lambda j: {k: v for k, v in j.items() if k != "axis"},
        lambda j: {**j, "job_id": "a/b"},
        lambda j: {**j, "job_id": ""},
        lambda j: {**j, "h_mm": 0},
        lambda j: {**j, "fillet_h_mm": float("nan")},
        lambda j: {**j, "case": {**j["case"], "load_angle_deg": 80.0}},
        lambda j: {**j, "case": 3},
    ],
)
def test_a_malformed_job_or_an_out_of_range_case_is_refused(mutate):
    with pytest.raises((runner.RunnerRefused, v2.Refused)):
        runner.check_job(mutate(_job()))


def test_prepare_writes_the_script_the_deck_and_the_load_weights(tmp_path):
    meta = runner.prepare(_job(), tmp_path / "j", mesh=fake_mesh)
    assert meta["tip_node"] == 3
    directory = tmp_path / "j"
    script = (directory / "make_mesh.py").read_text()
    case = _job()["case"]
    assert script == v2.gmsh_script_v2(case, 3.0, 0.5)
    deck = (directory / "case.inp").read_text()
    assert deck == v2.deck_text(case, MESH, v2.material(case["alloy"]))
    info = json.loads((directory / "deck.json").read_text())
    assert info["modes"] == 48 and info["mesh_image"] == v1.MESH_IMAGE
    assert math.isclose(sum(info["loads"].values()), 1.0, rel_tol=1e-12)
    assert info["deck_sha256"] == runner._sha(deck)


def test_the_participation_factor_uses_both_load_components():
    eig = [{"rad": 100.0, "hz": 15.9}]
    shapes = [{1: (0.5, 2.0), 3: (1.0, 4.0)}]
    loads = {1: 0.25, 3: 0.75}
    case = {"load_angle_deg": 30.0}
    (mode,) = runner.modal_data(eig, shapes, loads, case, tip=3)
    fy, fz = math.sin(math.radians(30.0)), math.cos(math.radians(30.0))
    expected = 0.5 * 0.25 * fy + 2.0 * 0.25 * fz + 1.0 * 0.75 * fy + 4.0 * 0.75 * fz
    assert mode["pf"] == pytest.approx(expected, rel=1e-15)
    assert mode["tip"] == 4.0 and mode["omega"] == 100.0 and mode["hz"] == 15.9
    flat = runner.modal_data(eig, shapes, loads, {"load_angle_deg": 0.0}, tip=3)[0]
    assert flat["pf"] == pytest.approx(2.0 * 0.25 + 4.0 * 0.75, rel=1e-15)


def _synthetic_job_directory(tmp_path, monkeypatch, modes=2):
    directory = tmp_path / "obs"
    directory.mkdir()
    case = _job()["case"]
    (directory / "mesh.json").write_text(json.dumps(MESH))
    (directory / "deck.json").write_text(
        json.dumps({"case": case, "modes": modes, "loads": {"1": 0.4, "3": 0.6}})
    )
    modal_rows = [
        (1, 1, (1.0, 0.0, 0.0, 0.0, 0.0, 0.0)),
        (2, 1, (0.0, 2.0, 0.0, 0.0, 0.0, 0.0)),
    ]
    static_rows = [
        (1, 1, (3.0, 0.0, 0.0, 0.0, 0.0, 0.0)),
        (2, 1, (0.0, 1.0, 0.0, 0.0, 0.0, 0.0)),
    ]
    text = "".join(_block(modal_rows) for _ in range(modes)) + _block(static_rows)
    (directory / "case.dat").write_text(text)
    eig = [
        {"mode": i + 1, "eigenvalue": 0.0, "rad": 2 * math.pi * hz, "hz": hz}
        for i, hz in enumerate((200.0, 350.0)[:modes])
    ]
    shapes = [{1: (0.1, 0.2), 3: (0.3, 0.5)}, {1: (0.2, 0.1), 3: (0.1, 0.7)}][:modes]
    steps = [
        {
            "eigen": eig,
            "events": [("disp", {n: (0.0, *v) for n, v in s.items()}) for s in shapes],
        },
        {"eigen": [], "events": []},
        {
            "eigen": [],
            "events": [("disp", {3: (0.0, 0.0, -0.0123), 4: (0.0, 0.0, 0.0)})],
        },
    ]
    monkeypatch.setattr(runner.proof, "parse_dat", lambda _text: steps)
    return directory, case, eig, shapes


def test_the_observation_gives_the_five_outputs_by_the_decks_own_functions(
    tmp_path, monkeypatch
):
    directory, case, eig, shapes = _synthetic_job_directory(tmp_path, monkeypatch)
    out = runner.observe(directory)
    assert set(out) == set(runner.OUTPUTS)
    mat = v2.material(case["alloy"])
    assert out["cad_mass_kg"] == mat["rho_t_per_mm3"] * 1001.0 * 1000.0
    assert out["static_tip_mm_per_n"] == -0.0123
    assert out["static_fillet_stress_mpa_per_n"] == pytest.approx(3.0)
    loads = {1: 0.4, 3: 0.6}
    modal = runner.modal_data(eig, shapes, loads, case, tip=3)
    zeta = case["damping_ratio"]
    grid = v1.dense_grid([m["hz"] for m in modal], zeta)
    expected = v1.resolved_peak(lambda f: v1.response(modal, f, zeta, "tip"), grid)
    assert out["worst_dynamic_mm_per_n"] == expected["mm_per_n"] > 0
    text = (directory / "case.dat").read_text()
    _keys, tensors = v2.modal_stress_tensors(text, 2)
    again = v2.worst_band_dynamic_stress(tensors, modal, zeta)
    assert (
        out["dynamic_fillet_stress_mpa_per_n"]
        == again["dynamic_von_mises_mpa_per_n"]
        > 0
    )
    assert all(type(v) is float and math.isfinite(v) for v in out.values())


def test_the_observation_refuses_a_wrong_mode_count_wrong_blocks_or_a_non_finite_output(
    tmp_path, monkeypatch
):
    directory, *_ = _synthetic_job_directory(tmp_path, monkeypatch)
    deck = json.loads((directory / "deck.json").read_text())
    (directory / "deck.json").write_text(json.dumps({**deck, "modes": 3}))
    with pytest.raises(runner.RunnerRefused, match="mode_count"):
        runner.observe(directory)
    (directory / "deck.json").write_text(json.dumps(deck))
    text = (directory / "case.dat").read_text()
    (directory / "case.dat").write_text(text.replace(HEADER, "x", 1))
    with pytest.raises(runner.RunnerRefused, match="stress_blocks"):
        runner.observe(directory)
    (directory / "case.dat").write_text(text)

    steps_nan = [
        {
            "eigen": [
                {"mode": 1, "eigenvalue": 0, "rad": 1000.0, "hz": 200.0},
                {"mode": 2, "eigenvalue": 0, "rad": 2000.0, "hz": 350.0},
            ],
            "events": [
                ("disp", {1: (0, 0.1, 0.2), 3: (0, 0.3, 0.5)}),
                ("disp", {1: (0, 0.2, 0.1), 3: (0, 0.1, 0.7)}),
            ],
        },
        {"eigen": [], "events": []},
        {"eigen": [], "events": [("disp", {3: (0.0, 0.0, float("nan"))})]},
    ]
    monkeypatch.setattr(runner.proof, "parse_dat", lambda _t: steps_nan)
    with pytest.raises(runner.RunnerRefused, match="output_not_finite:static_tip"):
        runner.observe(directory)
    monkeypatch.setattr(runner.proof, "parse_dat", lambda _t: steps_nan[:2])
    with pytest.raises(runner.RunnerRefused, match="dat_steps"):
        runner.observe(directory)


@pytest.mark.parametrize(
    "run,outputs,problem,expected",
    [
        ({"stop_reason": "exit", "exit": 0}, {"x": 1.0}, None, "OK"),
        ({"stop_reason": "infra"}, None, None, "FAILED_INFRA"),
        ({"stop_reason": "cancel", "exit": None}, None, None, "FAILED_INFRA"),
        ({"stop_reason": "memory", "exit": 137}, None, None, "FAILED_INFRA"),
        ({"stop_reason": "exit", "exit": 137}, None, None, "FAILED_INFRA"),
        ({"stop_reason": "exit", "exit": 120}, None, None, "FAILED_INFRA"),
        ({"stop_reason": "timeout", "exit": 143}, None, None, "REFERENCE_INVALID"),
        ({"stop_reason": "exit", "exit": 1}, None, None, "REFERENCE_INVALID"),
        ({"stop_reason": "exit", "exit": 0}, None, "mode_count", "REFERENCE_INVALID"),
    ],
)
def test_the_status_is_typed_infrastructure_failures_are_never_judged(
    run, outputs, problem, expected
):
    status, reasons = runner.classify(run, outputs, problem)
    assert status == expected
    assert (status == "OK") == (reasons == [])


def _cores():
    cores = queue.Queue()
    cores.put(0)
    return cores


def test_a_solved_job_makes_an_ok_record_with_digests_and_leaves_no_directory(
    tmp_path, monkeypatch
):
    outputs = {name: 1.0 for name in runner.OUTPUTS}
    monkeypatch.setattr(runner, "observe", lambda _d: outputs)
    record = runner.run_job(
        _job(), tmp_path, timeout_s=10, cores=_cores(), solvers_id="sha256:" + "a" * 64,
        mesh=fake_mesh, solver=ok_solver,
    )  # fmt: skip
    assert record["status"] == "OK" and record["outputs"] == outputs
    assert record["images"] == {
        "mesh_image": v1.MESH_IMAGE,
        "solvers_id": "sha256:" + "a" * 64,
    }
    assert record["deck_sha256"].startswith("sha256:") and record["dat_sha256"]
    assert record["alloy_table_sha256"] == v2.ALLOY_SHA256
    assert record["mesh"]["nodes"] == 12 and record["job_id"] == "f08v2-9000"
    assert not (tmp_path / "f08v2-9000").exists()
    json.dumps(record)  # a JSON line


def test_keep_all_keeps_the_directory_and_a_second_run_of_a_job_refuses(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(runner, "observe", lambda _d: {n: 1.0 for n in runner.OUTPUTS})
    args = {
        "timeout_s": 10,
        "cores": _cores(),
        "solvers_id": "s",
        "mesh": fake_mesh,
        "solver": ok_solver,
    }
    runner.run_job(_job(), tmp_path, keep="all", **args)
    assert (tmp_path / "f08v2-9000" / "case.inp").is_file()
    with pytest.raises(runner.RunnerRefused, match="job_directory_exists"):
        runner.run_job(_job(), tmp_path, **args)


def test_failed_solves_and_refused_decks_are_typed_records_not_exceptions(
    tmp_path, monkeypatch
):
    args = {"timeout_s": 10, "cores": _cores(), "solvers_id": "s", "mesh": fake_mesh}

    def failing(directory, timeout_s, cores):
        return {"stop_reason": "exit", "exit": 1}

    bad = runner.run_job(_job(job_id="a"), tmp_path, solver=failing, **args)
    assert bad["status"] == "REFERENCE_INVALID" and bad["reasons"] == ["solver_failed"]
    assert "outputs" not in bad

    def infra(directory, timeout_s, cores):
        return {"stop_reason": "infra", "exit": None}

    lost = runner.run_job(_job(job_id="b"), tmp_path, solver=infra, **args)
    assert lost["status"] == "FAILED_INFRA"

    def silent(directory, timeout_s, cores):
        return {"stop_reason": "exit", "exit": 0}  # exit 0 and no case.dat

    none = runner.run_job(_job(job_id="c"), tmp_path, solver=silent, **args)
    assert none["status"] == "REFERENCE_INVALID" and none["reasons"] == [
        "no_observable_output"
    ]

    def unobservable(_d):
        raise runner.RunnerRefused("mode_count")

    monkeypatch.setattr(runner, "observe", unobservable)
    refused = runner.run_job(_job(job_id="d"), tmp_path, solver=ok_solver, **args)
    assert refused["status"] == "REFERENCE_INVALID"
    assert refused["reasons"] == ["observation_refused:mode_count"]

    broken = _job(job_id="e", case={**_job()["case"], "load_angle_deg": 80.0})
    deck = runner.run_job(broken, tmp_path, solver=ok_solver, **args)
    assert deck["status"] == "REFERENCE_INVALID"
    assert deck["reasons"][0].startswith("deck_refused:")

    def no_mesh(directory):
        raise OSError("gmsh not found")

    lost_mesher = runner.run_job(
        _job(job_id="f"), tmp_path, solver=ok_solver, **{**args, "mesh": no_mesh}
    )
    assert lost_mesher["status"] == "FAILED_INFRA"

    def bad_mesh(directory):
        raise subprocess.CalledProcessError(1, "gmsh")

    meshed = runner.run_job(
        _job(job_id="g"), tmp_path, solver=ok_solver, **{**args, "mesh": bad_mesh}
    )
    assert meshed["status"] == "REFERENCE_INVALID"
    assert meshed["reasons"] == ["mesh_failed"]


def test_the_mesh_only_dry_run_reports_sizes_and_solves_nothing(tmp_path):
    record = runner.mesh_only(_job(), tmp_path, mesh=fake_mesh)
    assert record["status"] == "MESH_ONLY"
    assert record["mesh"]["nodes"] == 12 and record["mesh"]["cad_volume_mm3"] == 1001.0
    assert not (tmp_path / "f08v2-9000" / "case.dat").exists()
    assert record["deck_sha256"].startswith("sha256:")


def test_load_jobs_reads_a_real_shard_and_selects_by_id(tmp_path):
    document = payload.plan(20261101)
    shard = tmp_path / "shard-01.json"
    shard.write_text(
        json.dumps({"schema": payload.SCHEMA, "jobs": document["shards"][1]})
    )
    jobs = runner.load_jobs(shard)
    assert len(jobs) == len(document["shards"][1])
    only = runner.load_jobs(shard, [jobs[2]["job_id"]])
    assert [j["job_id"] for j in only] == [jobs[2]["job_id"]]
    with pytest.raises(runner.RunnerRefused, match="only_job_unknown"):
        runner.load_jobs(shard, ["nope"])
    shard.write_text(json.dumps({"jobs": [jobs[0], jobs[0]]}))
    with pytest.raises(runner.RunnerRefused, match="repeat"):
        runner.load_jobs(shard)


def test_the_command_line_refuses_without_the_verified_build(tmp_path, monkeypatch):
    document = payload.plan(20261101)
    shard = tmp_path / "s.json"
    shard.write_text(json.dumps({"jobs": document["shards"][0]}))
    monkeypatch.delenv("CARBON_F08_NATIVE_GMSH", raising=False)
    with pytest.raises(SystemExit, match="CARBON_F08_NATIVE_GMSH"):
        runner.main(["mesh-only", str(shard), "--out", str(tmp_path / "o")])
