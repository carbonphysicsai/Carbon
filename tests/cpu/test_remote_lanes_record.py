"""The remote-lane record generator/checker (scripts/dev/remote_lanes_record.py): lane cpusets are derived from a box's
own ``lscpu -p=CPU,CORE,SOCKET`` capture, every written record reads back through `remote_lane.load_record`, and a
record the door would refuse (or would only refuse at a round) is refused here. Synthetic topologies and example
addresses only."""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import pytest

from carbon.reconstruction import remote_lane

SCRIPT = (
    Path(__file__).resolve().parents[2] / "scripts" / "dev" / "remote_lanes_record.py"
)
_spec = importlib.util.spec_from_file_location("remote_lanes_record", SCRIPT)
gen = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gen)

FSN = "ssh://carbon-grade@box-a.example"
HEL = "ssh://carbon-grade@box-b.example:2222"
STAGE = "/home/carbon-grade/gb/stage"


def _smt2(cores=16):
    """A 16-core SMT-2 capture numbered as Linux numbers a Zen 3 desktop part: CPU n and n+16 are core n's threads."""
    lines = [
        "# The following is the parsable format, which can be fed to other",
        "# CPU,Core,Socket",
    ]
    lines += [f"{cpu},{cpu % cores},0" for cpu in range(2 * cores)]
    return "\n".join(lines) + "\n"


def _adjacent(cores=16):
    """The other common numbering: a core's two threads are adjacent CPUs (2k, 2k+1)."""
    return "".join(f"{cpu},{cpu // 2},0\n" for cpu in range(2 * cores))


def _files(tmp_path, **captures):
    paths = {}
    for name, text in captures.items():
        path = tmp_path / f"{name}.lscpu-p.txt"
        path.write_bytes(text.encode())
        paths[name] = path
    return paths


def test_cpusets_come_from_the_capture_for_both_shapes_and_both_numberings():
    topo = gen.parse_topology(_smt2())
    assert len(topo) == 16 and topo[0] == (0, 0, (0, 16))
    assert gen.lane_cpusets(topo, lanes=4, cores_per_lane=4, shape="physical-only") == [
        "0-3",
        "4-7",
        "8-11",
        "12-15",
    ]
    assert gen.lane_cpusets(
        topo, lanes=4, cores_per_lane=4, shape="physical-with-siblings"
    ) == [
        "0-3,16-19",
        "4-7,20-23",
        "8-11,24-27",
        "12-15,28-31",
    ]
    adjacent = gen.parse_topology(_adjacent())
    assert gen.lane_cpusets(
        adjacent, lanes=2, cores_per_lane=4, shape="physical-only"
    ) == ["0,2,4,6", "8,10,12,14"]
    assert gen.lane_cpusets(
        adjacent, lanes=1, cores_per_lane=4, shape="physical-with-siblings"
    ) == ["0-7"]


def test_a_box_with_too_few_cores_or_a_broken_capture_refuses():
    with pytest.raises(gen.RecordError, match="need 20 physical cores"):
        gen.lane_cpusets(
            gen.parse_topology(_smt2()),
            lanes=5,
            cores_per_lane=4,
            shape="physical-only",
        )
    for bad in ("", "# only comments\n", "0,0\n", "0,0,0\n0,1,0\n", "a,b,c\n"):
        with pytest.raises(gen.RecordError):
            gen.parse_topology(bad)


def test_the_proposed_two_box_records_read_back_as_the_door_reads_them(tmp_path):
    paths = _files(tmp_path, fsn1=_smt2(), hel1=_smt2())
    host, door = tmp_path / "host.json", tmp_path / "door.json"
    argv = ["--box", f"fsn1={FSN}", "--box", f"hel1={HEL}"]
    argv += [
        "--topology",
        f"fsn1={paths['fsn1']}",
        "--topology",
        f"hel1={paths['hel1']}",
    ]
    argv += [
        "--lanes-per-box",
        "4",
        "--cores-per-lane",
        "4",
        "--cpuset-shape",
        "physical-only",
    ]
    argv += [
        "--stage-root",
        STAGE,
        "--worker-cpus",
        "4",
        "--out-host",
        str(host),
        "--out-door",
        str(door),
    ]
    assert gen.main(argv) == 0
    specs, only = gen.load_bytes(host.read_bytes())
    assert only is False and len(specs) == remote_lane.MAX_REMOTE_LANES == 8
    # interleaved: a values row asking for fewer lanes still uses both boxes
    assert [s.docker_host for s in specs[:2]] == [FSN, HEL]
    assert [s.cpuset for s in specs] == [
        "0-3",
        "0-3",
        "4-7",
        "4-7",
        "8-11",
        "8-11",
        "12-15",
        "12-15",
    ]
    assert {s.stage_root for s in specs} == {STAGE}
    door_specs, door_only = gen.load_bytes(door.read_bytes())
    assert door_only is True and door_specs == specs
    for path in (host, door):
        data = path.read_bytes()
        assert b"\r" not in data and data.endswith(b"}\n")
        assert set(json.loads(data)) <= {"schema", "lanes", "only"}
        assert gen.main(["--check", str(path), "--worker-cpus", "4", *argv[:8]]) == 0
    # the generator itself names no address
    assert not re.search(r"\b\d{1,3}(\.\d{1,3}){3}\b", SCRIPT.read_text())


def test_box_order_lists_box_by_box(tmp_path):
    lanes = gen.build_lanes(
        {"fsn1": FSN, "hel1": HEL},
        {"fsn1": _smt2(), "hel1": _smt2()},
        lanes_per_box=2,
        cores_per_lane=4,
        shape="physical-only",
        stage_root=STAGE,
        order="box",
    )
    assert [(lane["docker_host"], lane["cpuset"]) for lane in lanes] == [
        (FSN, "0-3"),
        (FSN, "4-7"),
        (HEL, "0-3"),
        (HEL, "4-7"),
    ]


def test_a_shape_whose_size_is_not_the_worker_cpu_count_refuses(tmp_path, capsys):
    paths = _files(tmp_path, fsn1=_smt2(), hel1=_smt2())
    argv = [
        "--box",
        f"fsn1={FSN}",
        "--box",
        f"hel1={HEL}",
        "--topology",
        f"fsn1={paths['fsn1']}",
    ]
    argv += [
        "--topology",
        f"hel1={paths['hel1']}",
        "--lanes-per-box",
        "4",
        "--cores-per-lane",
        "4",
    ]
    argv += [
        "--cpuset-shape",
        "physical-with-siblings",
        "--stage-root",
        STAGE,
        "--worker-cpus",
        "4",
    ]
    argv += ["--out-host", str(tmp_path / "h.json")]
    assert gen.main(argv) == 2
    assert "8 CPUs" in capsys.readouterr().err
    assert not (tmp_path / "h.json").exists()


def test_the_script_sets_no_lane_value_of_its_own(tmp_path, capsys):
    paths = _files(tmp_path, fsn1=_smt2())
    argv = [
        "--box",
        f"fsn1={FSN}",
        "--topology",
        f"fsn1={paths['fsn1']}",
        "--out-host",
        str(tmp_path / "h.json"),
    ]
    assert gen.main(argv) == 2
    err = capsys.readouterr().err
    assert (
        "--lanes-per-box" in err and "--cpuset-shape" in err and "--stage-root" in err
    )


@pytest.mark.parametrize(
    "lanes, only, message",
    [
        (
            [{"cpuset": "0-3", "docker_host": FSN, "stage_root": STAGE}],
            True,
            "at least two lanes",
        ),
        (
            [
                {"cpuset": "0-3", "docker_host": FSN, "stage_root": STAGE},
                {"cpuset": "3-6", "docker_host": FSN, "stage_root": STAGE},
            ],
            False,
            "share CPUs",
        ),
        (
            [
                {"cpuset": "0-3", "docker_host": FSN, "stage_root": STAGE},
                {"cpuset": "4-9", "docker_host": HEL, "stage_root": STAGE},
            ],
            False,
            "unequal size",
        ),
        (
            [
                {"cpuset": "0-3", "docker_host": FSN, "stage_root": STAGE},
                {"cpuset": "16-19", "docker_host": FSN, "stage_root": STAGE},
            ],
            False,
            "share a physical core",
        ),
        (
            [
                {"cpuset": "0-3", "docker_host": FSN, "stage_root": STAGE},
                {"cpuset": "40-43", "docker_host": FSN, "stage_root": STAGE},
            ],
            False,
            "not on the box",
        ),
        (
            [
                {
                    "cpuset": "0-3",
                    "docker_host": "ssh://root@x -oProxy",
                    "stage_root": STAGE,
                }
            ],
            False,
            "load_record",
        ),
        (
            [{"cpuset": "0-3", "docker_host": FSN, "stage_root": "/a/../b"}],
            False,
            "load_record",
        ),
        (
            [{"cpuset": "0-3", "docker_host": FSN, "stage_root": STAGE}] * 9,
            False,
            "load_record",
        ),
    ],
)
def test_check_refuses_what_the_door_would(lanes, only, message):
    with pytest.raises(gen.RecordError, match=message):
        gen.check(
            gen.render(lanes, only=only),
            topologies={"fsn1": _smt2()},
            boxes={"fsn1": FSN},
        )


def test_check_refuses_crlf_and_non_canonical_bytes():
    lanes = [{"cpuset": "0-3", "docker_host": FSN, "stage_root": STAGE}]
    data = gen.render(lanes, only=False)
    assert gen.check(data)[1] is False
    with pytest.raises(gen.RecordError, match="carriage return"):
        gen.check(data.replace(b"\n", b"\r\n"))
    with pytest.raises(gen.RecordError, match="canonical"):
        gen.check(json.dumps(json.loads(data)).encode())


def test_a_door_state_root_outside_stage_root_refuses(tmp_path, capsys):
    paths = _files(tmp_path, fsn1=_smt2(), hel1=_smt2())
    argv = [
        "--box",
        f"fsn1={FSN}",
        "--box",
        f"hel1={HEL}",
        "--topology",
        f"fsn1={paths['fsn1']}",
    ]
    argv += [
        "--topology",
        f"hel1={paths['hel1']}",
        "--lanes-per-box",
        "1",
        "--cores-per-lane",
        "4",
    ]
    argv += [
        "--cpuset-shape",
        "physical-only",
        "--stage-root",
        STAGE,
        "--out-door",
        str(tmp_path / "d.json"),
    ]
    assert gen.main([*argv, "--door-state-root", "/var/lib/carbon/doors/x"]) == 2
    assert "_remote_path" in capsys.readouterr().err
    assert gen.main([*argv, "--door-state-root", STAGE + "/door-a"]) == 0


def test_topology_may_be_the_box_identity_json(tmp_path):
    path = tmp_path / "fsn1.identity.json"
    path.write_text(
        json.dumps({"schema": "carbon.gradebox.identity.v1", "lscpu_p": _smt2()}),
        newline="\n",
    )
    assert gen.read_topology_text(path) == _smt2()
    path.write_bytes(_smt2().replace("\n", "\r\n").encode())
    with pytest.raises(gen.RecordError, match="carriage return"):
        gen.read_topology_text(path)
