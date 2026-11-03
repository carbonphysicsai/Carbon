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


def _step(n):
    """A ccx .dat step header, as `f08_proof.parse_dat` and `f08_deck_v2.stress_blocks_by_step` read it."""
    return f"\n                        S T E P       {n}\n\n"


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


#: The mesher a record names in these tests (a real run names `runner.mesher_identity()`).
MESHER = {
    "kind": "native_gmsh",
    "gmsh_version": "4.15.2",
    "pinned_gmsh_version": "4.15.2",
    "python": "/usr/bin/python3",
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
    meta = runner.prepare(_job(), tmp_path / "j", mesh=fake_mesh, mesher=MESHER)
    assert meta["tip_node"] == 3
    directory = tmp_path / "j"
    script = (directory / "make_mesh.py").read_text()
    case = _job()["case"]
    assert script == v2.gmsh_script_v2(case, 3.0, 0.5)
    deck = (directory / "case.inp").read_text()
    assert deck == v2.deck_text(case, MESH, v2.material(case["alloy"]))
    info = json.loads((directory / "deck.json").read_text())
    assert info["modes"] == 48 and info["mesher"] == MESHER
    assert math.isclose(sum(info["loads"].values()), 1.0, rel_tol=1e-12)
    assert info["deck_sha256"] == runner._sha(deck)
    assert (
        info["deck_revision"] == v2.DECK_REVISION and "*STATIC,SOLVER=PASTIX\n" in deck
    )


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
    text = (
        _step(1)
        + "".join(_block(modal_rows) for _ in range(modes))
        + _step(2)
        + _step(3)
        + _block(static_rows)
    )
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


def test_stress_blocks_the_steady_state_step_inherits_are_never_read(
    tmp_path, monkeypatch
):
    # 0034 (11-01): the steady-state step names no *EL PRINT, so ccx keeps the frequency step's FILLET S print there and
    # writes blocks between the modes and the static block. The observation reads the frequency step's and the static step's.
    directory, *_ = _synthetic_job_directory(tmp_path, monkeypatch)
    plain = runner.observe(directory)
    text = (directory / "case.dat").read_text()
    noise = [
        (1, 1, (99.0, 0.0, 0.0, 0.0, 0.0, 0.0)),
        (2, 1, (0.0, 99.0, 0.0, 0.0, 0.0, 0.0)),
    ]
    inherited = text.replace(
        _step(2), _step(2) + "".join(_block(noise) for _ in range(7))
    )
    (directory / "case.dat").write_text(inherited)
    assert [len(b) for b in v2.stress_blocks_by_step(inherited)] == [2, 7, 1]
    assert runner.observe(directory) == plain
    # the static step must carry exactly one block, the frequency step exactly one per mode
    (directory / "case.dat").write_text(text + _block(noise))
    with pytest.raises(runner.RunnerRefused, match="stress_blocks:2,0,2"):
        runner.observe(directory)
    # a block before the first step belongs to no step
    with pytest.raises(v2.Refused, match="stress_block_outside_a_step"):
        v2.stress_blocks_by_step(_block(noise) + text)


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
    with pytest.raises(runner.RunnerRefused, match="stress_blocks:1,0,1"):
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
        ({"stop_reason": "timeout", "exit": 143}, None, None, "REFERENCE_TIMEOUT"),
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
    monkeypatch.setattr(runner, "observe", lambda _d, _p=None: outputs)
    record = runner.run_job(
        _job(), tmp_path, timeout_s=10, cores=_cores(), solvers_id="sha256:" + "a" * 64,
        mesh=fake_mesh, solver=ok_solver, mesher=MESHER,
    )  # fmt: skip
    assert record["status"] == "OK" and record["outputs"] == outputs
    assert record["images"] == {"mesher": MESHER, "solvers_id": "sha256:" + "a" * 64}
    assert record["deck_sha256"].startswith("sha256:") and record["dat_sha256"]
    assert record["alloy_table_sha256"] == v2.ALLOY_SHA256
    assert record["schema"] == "carbon.f08.v2-job-record.v3"
    assert record["deck_revision"] == v2.DECK_REVISION
    assert record["mesh"]["nodes"] == 12 and record["job_id"] == "f08v2-9000"
    assert not (tmp_path / "f08v2-9000").exists()
    json.dumps(record)  # a JSON line


def test_keep_all_keeps_the_directory_and_a_second_run_of_a_job_refuses(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(
        runner, "observe", lambda _d, _p=None: {n: 1.0 for n in runner.OUTPUTS}
    )
    args = {
        "timeout_s": 10,
        "cores": _cores(),
        "solvers_id": "s",
        "mesher": MESHER,
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
    args = {
        "timeout_s": 10,
        "cores": _cores(),
        "solvers_id": "s",
        "mesh": fake_mesh,
        "mesher": MESHER,
    }

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

    def unobservable(_d, _p=None):
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
    record = runner.mesh_only(_job(), tmp_path, mesh=fake_mesh, mesher=MESHER)
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


def test_a_timeout_is_its_own_status_until_the_job_is_rerun_alone():
    run = {"stop_reason": "timeout", "exit": 143}
    assert runner.classify(run, None, None) == (
        "REFERENCE_TIMEOUT",
        ["solver_timeout_unconfirmed"],
    )
    # the single rerun alone: a repeat timeout is the case's own
    assert runner.classify(run, None, None, alone=True) == (
        "REFERENCE_INVALID",
        ["solver_timeout"],
    )
    # --alone changes nothing else
    assert runner.classify({"stop_reason": "exit", "exit": 1}, None, None, alone=True)[
        1
    ] == ["solver_failed"]
    assert runner.classify({"stop_reason": "infra"}, None, None, alone=True)[0] == (
        "FAILED_INFRA"
    )


def test_a_timed_out_record_carries_no_outputs_so_the_judge_sees_it_as_missing(
    tmp_path,
):
    def slow(directory, timeout_s, cores):
        return {"stop_reason": "timeout", "exit": 143, "wall_s": 5400.0}

    args = {
        "timeout_s": 10,
        "cores": _cores(),
        "solvers_id": "s",
        "mesh": fake_mesh,
        "mesher": MESHER,
    }
    first = runner.run_job(_job(job_id="t1"), tmp_path, solver=slow, **args)
    assert first["status"] == "REFERENCE_TIMEOUT" and "outputs" not in first
    assert first["reasons"] == ["solver_timeout_unconfirmed"]
    assert first["run"]["wall_s"] == 5400.0
    again = runner.run_job(_job(job_id="t2"), tmp_path, solver=slow, alone=True, **args)
    assert again["status"] == "REFERENCE_INVALID"
    assert again["reasons"] == ["solver_timeout"] and "outputs" not in again
    assert runner.TERMINAL == ("OK", "REFERENCE_INVALID")  # a timeout is not terminal


def test_alone_reruns_exactly_one_job_on_one_core(tmp_path, monkeypatch):
    document = payload.plan(20261101)
    shard = tmp_path / "s.json"
    shard.write_text(json.dumps({"jobs": document["shards"][1]}))
    with pytest.raises(SystemExit, match="exactly one job"):
        runner.main(["run", str(shard), "--out", str(tmp_path / "o"), "--alone"])
    one = document["shards"][1][0]["job_id"]
    with pytest.raises(SystemExit, match="exactly one job"):
        runner.main(
            [
                "run",
                str(shard),
                "--out",
                str(tmp_path / "o2"),
                "--alone",
                "--only",
                one,
                "--parallel",
                "2",
            ]
        )


# --- the mesher is infrastructure (Validator 11-01, Launchpad smoke): a launch fault is FAILED_INFRA, never mesh_failed ----


def _failing_mesh(monkeypatch, error):
    def mesh(directory):
        raise error

    monkeypatch.setattr(v1, "mesh", mesh)


@pytest.mark.parametrize(
    "error, cause",
    [
        (
            subprocess.CalledProcessError(
                1, ["python3", "-c", "import gmsh; print(gmsh.__version__)"]
            ),
            "gmsh_not_importable",
        ),
        (
            subprocess.CalledProcessError(
                1,
                ["python3", "make_mesh.py"],
                stderr=b"ModuleNotFoundError: No module named 'gmsh'\n",
            ),
            "mesher_import_failed",
        ),
        (
            subprocess.CalledProcessError(
                1,
                ["python3", "make_mesh.py"],
                stderr=b"OSError: libgmsh.so.4.15: cannot open shared object file\n",
            ),
            "mesher_import_failed",
        ),
        (
            SystemExit("native Gmsh 4.13.1 differs from pinned 4.15.2"),
            "gmsh_version_not_pinned",
        ),
        (
            subprocess.CalledProcessError(125, ["docker", "run"]),
            "mesh_image_not_launchable",
        ),
        (FileNotFoundError("python3"), "mesher_not_launchable"),
    ],
)
def test_a_mesher_that_cannot_launch_is_failed_infra_with_its_cause(
    tmp_path, monkeypatch, error, cause
):
    _failing_mesh(monkeypatch, error)
    record = runner.run_job(
        _job(),
        tmp_path,
        timeout_s=10,
        cores=_cores(),
        solvers_id="s",
        mesher=MESHER,
        solver=ok_solver,
    )
    assert record["status"] == "FAILED_INFRA"
    assert record["reasons"][-1] == f"mesher_unavailable:{cause}"
    assert "outputs" not in record


def test_a_mesh_the_running_mesher_could_not_make_stays_the_jobs_mesh_failed(
    tmp_path, monkeypatch
):
    _failing_mesh(
        monkeypatch,
        subprocess.CalledProcessError(
            1,
            ["python3", "make_mesh.py"],
            stderr=b"Exception: Invalid boolean operation\n",
        ),
    )
    record = runner.run_job(
        _job(),
        tmp_path,
        timeout_s=10,
        cores=_cores(),
        solvers_id="s",
        mesher=MESHER,
        solver=ok_solver,
    )
    assert record["status"] == "REFERENCE_INVALID" and record["reasons"] == [
        "mesh_failed"
    ]


def _gmsh_says(monkeypatch, returncode, stdout):
    real = subprocess.run

    def run(command, **kwargs):
        if command[:2] == ["python3", "-c"]:
            return subprocess.CompletedProcess(
                command, returncode, stdout=stdout, stderr=""
            )
        return real(command, **kwargs)

    monkeypatch.setattr(runner.subprocess, "run", run)


def test_the_record_names_the_native_gmsh_that_ran_and_its_pin(monkeypatch):
    monkeypatch.setenv("CARBON_F08_NATIVE_GMSH", "1")
    _gmsh_says(monkeypatch, 0, v1.GMSH_VERSION + "\n")
    identity = runner.mesher_identity()
    assert identity["kind"] == "native_gmsh"
    assert (
        identity["gmsh_version"] == identity["pinned_gmsh_version"] == v1.GMSH_VERSION
    )
    assert (
        "image" not in identity
    )  # never the Motor reference image when native Gmsh meshes


@pytest.mark.parametrize(
    "returncode, stdout, cause",
    [(1, "", "gmsh_not_importable"), (0, "4.13.1\n", "gmsh_version_not_pinned")],
)
def test_a_native_gmsh_that_is_missing_or_unpinned_stops_the_run_as_infra(
    monkeypatch, returncode, stdout, cause
):
    monkeypatch.setenv("CARBON_F08_NATIVE_GMSH", "1")
    _gmsh_says(monkeypatch, returncode, stdout)
    with pytest.raises(runner.MesherUnavailable) as lost:
        runner.mesher_identity()
    assert lost.value.cause == cause


def test_without_native_gmsh_the_record_names_the_pinned_mesh_image(monkeypatch):
    monkeypatch.delenv("CARBON_F08_NATIVE_GMSH", raising=False)
    assert runner.mesher_identity() == {
        "kind": "image",
        "image": v1.MESH_IMAGE,
        "pinned_gmsh_version": v1.GMSH_VERSION,
    }


def test_the_pastix_deck_revision_runs_at_the_owners_28_gib_and_1_7_keeps_9_gib():
    assert v2.DECK_REVISION == "f08-2.0-deck-solver-pastix"
    assert runner.memory_bytes() == runner.memory_bytes(v2.DECK_REVISION) == 28 * 2**30
    # any other revision (the SPOOLES-era decks, 1.7's) keeps RR-PACKS-07's 9 GiB
    assert runner.memory_bytes(None) == runner.memory_bytes("f08-1.7") == 9 * 2**30
    status, reasons = runner.classify(
        {"stop_reason": "memory", "exit": 137}, None, None
    )
    assert status == "FAILED_INFRA"
    assert reasons == [f"reference_memory_limit_{28 * 2**30}_bytes"]


def test_solve_hands_the_native_executor_the_revisions_limit(tmp_path, monkeypatch):
    import bulk_run

    seen = {}

    def run_native(*args, rss_limit_bytes, **kwargs):
        seen["rss"] = rss_limit_bytes
        return {"stop_reason": "exit", "exit": 0, "wall_s": 0.0}

    monkeypatch.setattr(bulk_run, "run_native", run_native)
    monkeypatch.setattr(bulk_run, "native_env", lambda env, directory: {})
    runner.solve(tmp_path, 10.0, _cores())
    assert seen["rss"] == 28 * 2**30


def test_the_auxiliary_block_retains_every_mode_the_static_fillet_field_and_the_tip_vector(
    tmp_path, monkeypatch
):
    directory, case, eig, shapes = _synthetic_job_directory(tmp_path, monkeypatch)
    aux = runner.auxiliary(directory)
    modal = runner.modal_data(eig, shapes, {1: 0.4, 3: 0.6}, case, tip=3)
    assert aux["modes_hz"] == [m["hz"] for m in modal] and len(aux["modes_hz"]) == 2
    _keys, tensors = v2.modal_stress_tensors((directory / "case.dat").read_text(), 2)
    assert aux["mode_fillet_von_mises_peak_mpa_per_unit_modal"] == [
        float(v) for v in v2._vm_rows(tensors).max(axis=1)
    ]
    static = aux["static_fillet_von_mises_mpa_per_n"]
    assert max(row[2] for row in static) == pytest.approx(
        runner.observe(directory)["static_fillet_stress_mpa_per_n"]
    )
    assert (
        aux["tip_static_displacement_mm_per_n"][2] == -0.0123
    )  # the graded static tip is its z
    json.dumps(aux)


def test_a_solved_record_carries_the_auxiliary_block_and_its_failure_changes_nothing(
    tmp_path, monkeypatch
):
    outputs = {name: 1.0 for name in runner.OUTPUTS}
    monkeypatch.setattr(runner, "observe", lambda _d, _p=None: outputs)
    monkeypatch.setattr(runner, "auxiliary", lambda _d, _p=None: {"modes_hz": [1.0]})
    record = runner.run_job(
        _job(), tmp_path / "a", timeout_s=10, cores=_cores(), solvers_id="sha256:" + "a" * 64,
        mesh=fake_mesh, solver=ok_solver, mesher=MESHER,
    )  # fmt: skip
    assert record["status"] == "OK" and record["auxiliary"] == {"modes_hz": [1.0]}

    def broken(_d, _p=None):
        raise ValueError("unreadable")

    monkeypatch.setattr(runner, "auxiliary", broken)
    record = runner.run_job(
        _job(), tmp_path / "b", timeout_s=10, cores=_cores(), solvers_id="sha256:" + "a" * 64,
        mesh=fake_mesh, solver=ok_solver, mesher=MESHER,
    )  # fmt: skip
    assert record["status"] == "OK" and record["outputs"] == outputs
    assert "auxiliary" not in record


def test_one_parse_gives_the_same_observation_and_auxiliary_as_parsing_alone(
    tmp_path, monkeypatch
):
    directory, *_ = _synthetic_job_directory(tmp_path, monkeypatch)
    parsed = runner.parse(directory)
    assert runner.observe(directory, parsed) == runner.observe(directory)
    assert runner.auxiliary(directory, parsed) == runner.auxiliary(directory)


def test_a_job_reads_its_dat_once(tmp_path, monkeypatch):
    import builtins

    directory, *_ = _synthetic_job_directory(tmp_path, monkeypatch)
    real_open, real_read = builtins.open, Path.read_text
    reads = []

    def opening(file, *args, **kwargs):
        if Path(file).name == "case.dat":
            reads.append(file)
        return real_open(file, *args, **kwargs)

    def reading(self, *args, **kwargs):
        if self.name == "case.dat":
            reads.append(self)
        return real_read(self, *args, **kwargs)

    # every way the parse could read the .dat: the streaming open and a whole-file read_text
    monkeypatch.setattr(builtins, "open", opening)
    monkeypatch.setattr(Path, "read_text", reading)
    parsed = runner.parse(directory)
    runner.observe(directory, parsed)
    runner.auxiliary(directory, parsed)
    assert len(reads) == 1


def test_the_auxiliary_block_never_reads_the_steady_state_steps_inherited_blocks(
    tmp_path, monkeypatch
):
    directory, *_ = _synthetic_job_directory(tmp_path, monkeypatch)
    plain = runner.auxiliary(directory)
    text = (directory / "case.dat").read_text()
    noise = [
        (1, 1, (99.0, 0.0, 0.0, 0.0, 0.0, 0.0)),
        (2, 1, (0.0, 99.0, 0.0, 0.0, 0.0, 0.0)),
    ]
    (directory / "case.dat").write_text(
        text.replace(_step(2), _step(2) + "".join(_block(noise) for _ in range(7)))
    )
    assert runner.auxiliary(directory) == plain


def _disp(rows):
    """A ccx displacement block as `f08_proof.parse_dat` reads it: the heading, one line, the rows, a blank line."""
    lines = [" displacements (vx,vy,vz) for set NALL and time  0.1000000E+01", ""]
    lines += [f"{n:10d}  {x:.6E}  {y:.6E}  {z:.6E}" for n, x, y, z in rows]
    return "\n".join(lines) + "\n\n"


def test_the_streaming_parse_keeps_every_value_of_the_nodes_read_and_nothing_else_changes(
    tmp_path,
):
    rows = [(n, 0.1 * n, -0.2 * n, 0.3 * n) for n in range(1, 9)]
    stress = [(1, 1, (1.0, 0.0, 0.0, 0.0, 0.0, 0.0))]
    text = (
        _step(1)
        + _disp(rows)
        + _block(stress)
        + _disp(rows[::-1])
        + _step(2)
        + _disp(rows)
        + _step(3)
        + _disp(rows)
        + _block(stress)
    )
    path = tmp_path / "case.dat"
    path.write_text(text)
    kept = "".join(runner._kept_lines(path, {1, 3}))
    assert len(kept) < len(text)
    whole, cut = runner.proof.parse_dat(text), runner.proof.parse_dat(kept)
    assert len(whole) == len(cut) == 3
    for full_step, cut_step in zip(whole, cut, strict=True):
        assert cut_step["eigen"] == full_step["eigen"]
        assert [e[0] for e in cut_step["events"]] == [e[0] for e in full_step["events"]]
        for full_event, cut_event in zip(
            full_step["events"], cut_step["events"], strict=True
        ):
            assert cut_event[1] == {n: full_event[1][n] for n in (1, 3)}
    assert v2.stress_blocks_by_step(kept) == v2.stress_blocks_by_step(text)


JACOBIAN_LOG = (
    " Using up to 1 cpu(s) for the stress calculation.\n"
    " *ERROR in e_c3d: nonpositive jacobian\n"
    "        determinant in element 207959\n"
)
REAL_JACOBIAN_LOG = (
    " *ERROR in e_c3d: nonpositive jacobian determinant in element 207959\n"
)


@pytest.mark.parametrize(
    "log,expected",
    [
        (REAL_JACOBIAN_LOG, ("REFERENCE_INVALID", ["nonpositive_jacobian"])),
        (
            REAL_JACOBIAN_LOG.upper(),
            ("REFERENCE_INVALID", ["nonpositive_jacobian"]),
        ),
        # another ccx error, or no log, keeps the old typing of a code >= 128
        (" *ERROR reading *STEP\n", ("FAILED_INFRA", None)),
        (" *ERROR in e_c3d: positive jacobian\n", ("FAILED_INFRA", None)),
        # e_c3d's own two lines: the message, then "determinant in element N"
        (JACOBIAN_LOG, ("REFERENCE_INVALID", ["nonpositive_jacobian"])),
        (None, ("FAILED_INFRA", None)),
    ],
)
def test_ccx_exit_201_for_an_inverted_element_is_the_meshs_reference_failure(
    tmp_path, log, expected
):
    # Launchpad 22:01: U02 / U03 end with ccx exit 201 and 'nonpositive jacobian determinant' in ccx.log, deterministic on two
    # CPU classes; Validator 22:06 (b): a REFERENCE outcome (invalid mesh), not FAILED_INFRA.
    def inverted(directory, timeout_s, cores):
        if log is not None:
            (Path(directory) / "ccx.log").write_text(log)
        return {"stop_reason": "exit", "exit": 201, "wall_s": 30.0}

    record = runner.run_job(
        _job(job_id="j"),
        tmp_path,
        timeout_s=10,
        cores=_cores(),
        solvers_id="s",
        mesh=fake_mesh,
        mesher=MESHER,
        solver=inverted,
    )
    status, reasons = expected
    assert record["status"] == status and "outputs" not in record
    if reasons is not None:
        assert record["reasons"] == reasons
    assert record["run"]["exit"] == 201


def test_the_jacobian_message_retypes_only_a_failed_exit():
    jac = runner.NONPOSITIVE_JACOBIAN
    assert runner.classify({"stop_reason": "exit", "exit": 1}, None, jac) == (
        "REFERENCE_INVALID",
        [jac],
    )
    # never an outside stop, a memory stop, a timeout or a clean exit
    assert runner.classify({"stop_reason": "infra"}, None, jac)[0] == "FAILED_INFRA"
    assert runner.classify({"stop_reason": "cancel"}, None, jac)[0] == "FAILED_INFRA"
    assert runner.classify({"stop_reason": "memory", "exit": 137}, None, jac)[0] == (
        "FAILED_INFRA"
    )
    assert runner.classify({"stop_reason": "timeout", "exit": 143}, None, jac)[0] == (
        "REFERENCE_TIMEOUT"
    )
    assert runner.classify({"stop_reason": "exit", "exit": 0}, {"x": 1.0}, jac) == (
        "OK",
        [],
    )


def test_a_solved_job_never_reads_ccx_log(tmp_path, monkeypatch):
    monkeypatch.setattr(
        runner, "solver_error", lambda d: pytest.fail("read ccx.log after exit 0")
    )
    monkeypatch.setattr(runner, "observe", lambda d, p=None: {"x": 1.0})
    monkeypatch.setattr(runner, "parse", lambda d: None)
    monkeypatch.setattr(runner, "auxiliary", lambda d, p=None: None)
    record = runner.run_job(
        _job(job_id="k"),
        tmp_path,
        timeout_s=10,
        cores=_cores(),
        solvers_id="s",
        mesh=fake_mesh,
        mesher=MESHER,
        solver=ok_solver,
    )
    assert record["status"] == "OK"


def test_the_a3_mesh_script_is_unchanged_and_hoo2_adds_only_the_optimiser_line():
    case = _job()["case"]
    a3 = v2.gmsh_script_v2(case, 1.7, 0.5)
    assert a3 == v2.gmsh_script_v2(case, 1.7, 0.5, mesh_revision=None)
    assert "HighOrderOptimize" not in a3
    hoo = v2.gmsh_script_v2(case, 1.7, 0.5, mesh_revision="hoo2")
    line = 'gmsh.option.setNumber("Mesh.HighOrderOptimize", 2)\n'
    assert hoo.count(line) == 1
    assert hoo.index(line) < hoo.index("gmsh.model.mesh.generate(3)")
    assert hoo.replace(line, "", 1) == a3
    v2.script_compiles(hoo)


def test_the_mesh_revision_is_named_in_the_record_only_when_set(tmp_path):
    args = {
        "timeout_s": 10,
        "cores": _cores(),
        "solvers_id": "s",
        "mesh": fake_mesh,
        "mesher": MESHER,
        "solver": ok_solver,
        "keep": "all",
    }
    plain = runner.run_job(_job(job_id="p"), tmp_path, **args)
    assert "mesh_revision" not in plain
    hoo = runner.run_job(_job(job_id="q"), tmp_path, mesh_revision="hoo2", **args)
    assert hoo["mesh_revision"] == "hoo2"
    assert "HighOrderOptimize" in (tmp_path / "q" / "make_mesh.py").read_text()
    assert "HighOrderOptimize" not in (tmp_path / "p" / "make_mesh.py").read_text()
    refused = runner.run_job(_job(job_id="r"), tmp_path, mesh_revision="hoo9", **args)
    assert refused["status"] == "REFERENCE_INVALID"
    assert refused["reasons"] == ["deck_refused:mesh_revision_unknown"]


def test_a_failed_solve_keeps_its_ccx_log_tail_in_the_record(tmp_path):
    lines = [f"line {i}" for i in range(100)] + [JACOBIAN_LOG.rstrip("\n")]

    def inverted(directory, timeout_s, cores):
        (Path(directory) / "ccx.log").write_text("\n".join(lines) + "\n")
        return {"stop_reason": "exit", "exit": 201, "wall_s": 3.0}

    args = {
        "timeout_s": 10,
        "cores": _cores(),
        "solvers_id": "s",
        "mesh": fake_mesh,
        "mesher": MESHER,
    }
    record = runner.run_job(_job(job_id="t"), tmp_path, solver=inverted, **args)
    tail = record["solver_log_tail"].splitlines()
    assert len(tail) == runner.SOLVER_LOG_TAIL_LINES
    assert "nonpositive jacobian" in record["solver_log_tail"]
    assert tail[-1].strip().startswith("determinant in element")
    assert record["reasons"] == ["nonpositive_jacobian"]
    assert not (tmp_path / "t").exists()  # kept in the record even with --keep none
    (tmp_path / "big").mkdir()
    (tmp_path / "big" / "ccx.log").write_bytes(b"x" * 50000)
    assert len(runner.solver_log_tail(tmp_path / "big")) <= runner.SOLVER_LOG_TAIL_BYTES
    assert runner.solver_log_tail(tmp_path / "none") is None
    solved = runner.run_job(_job(job_id="u"), tmp_path, solver=ok_solver, **args)
    assert "solver_log_tail" not in solved
