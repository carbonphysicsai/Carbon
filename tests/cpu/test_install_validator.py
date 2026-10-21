"""The validator installer refuses a machine that fails the published requirements.

Stub commands stand in for docker, curl, nvidia-smi and nproc; nothing is installed.
"""

from __future__ import annotations

import glob
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "install_validator.sh"

pytestmark = pytest.mark.skipif(
    sys.platform != "linux", reason="the installer runs on Linux hosts"
)


def _stub(directory: Path, name: str, body: str) -> None:
    path = directory / name
    path.write_text("#!/usr/bin/env bash\n" + body + "\n", encoding="utf-8")
    path.chmod(0o755)


#: The registered validator host class (OWNER-VALIDATOR-HOST-CLASS-01), as a fixture.
HOST_CLASS = {
    "schema": "carbon.validator.host-class.v1",
    "scope": "DEVELOPMENT",
    "cpu_model_name": "Fixture EPYC Processor",
    "isa_flags_present": {
        "avx2": True,
        "fma": True,
        "avx512f": False,
        "avx512_bf16": False,
        "amx": False,
    },
    "nproc": 4,
    "mem_total_min_gib": 50,
}


def _host_stubs(directory: Path) -> None:
    """lscpu and nproc answer from STUB_* variables; the default is the registered class."""
    _stub(
        directory,
        "lscpu",
        'echo "Model name:           ${STUB_MODEL:-Fixture EPYC Processor}"\n'
        'echo "Flags:                fpu sse2 ${STUB_FLAGS:-avx2 fma}"',
    )
    _stub(directory, "nproc", 'echo "${STUB_NPROC:-4}"')


def _host_files(directory: Path, registered=None, mem_kib=52428800) -> dict:
    """The class file and a /proc/meminfo stand-in, as test-knob environment."""
    class_file, meminfo = directory / "host-class.json", directory / "meminfo"
    class_file.write_text(json.dumps(HOST_CLASS if registered is None else registered))
    meminfo.write_text(f"MemTotal:       {mem_kib} kB\nMemFree:        1 kB\n")
    return {
        "CARBON_VALIDATOR_HOST_CLASS_FILE": str(class_file),
        "CARBON_VALIDATOR_MEMINFO_FILE": str(meminfo),
    }


@pytest.fixture
def machine(tmp_path):
    stubs = tmp_path / "stubs"
    stubs.mkdir()
    _stub(
        stubs,
        "docker",
        'if [[ "$1" == info ]]; then\n'
        '  [[ "${STUB_DOCKER_DOWN:-0}" == 1 ]] && exit 1\n'
        '  [[ "$*" == *CgroupVersion* ]] && { echo "${STUB_CGROUP:-2}"; exit 0; }\n'
        '  [[ "$*" == *Runtimes* ]] && { echo "${STUB_RUNTIMES:-{\\"runc\\":{}}}"; exit 0; }\n'
        "  exit 0\nfi\nexit 0",
    )
    _stub(stubs, "curl", '[[ "${STUB_CURL_FAIL:-0}" == 1 ]] && exit 6; exit 0')
    _stub(stubs, "nvidia-smi", 'echo "${STUB_DRIVER:-}"')
    _stub(stubs, "systemd-detect-virt", '[[ -n "${STUB_VIRT:-}" ]] && exit 0; exit 1')
    _host_stubs(stubs)
    state = tmp_path / "state"
    host = _host_files(tmp_path)

    def run(*args, **env):
        merged = {
            **os.environ,
            "PATH": f"{stubs}:{os.environ['PATH']}",
            # The canonical container is itself a container: fix the machine type.
            "CARBON_VALIDATOR_ASSUME_MACHINE": "host",
            "CARBON_STATE_DIR": str(state),
            "CARBON_VALIDATOR_MIN_FREE_GIB": "0",
            "CARBON_VALIDATOR_MIN_CPUS": "1",
            "CARBON_VALIDATOR_MIN_RAM_GIB": "0",
            **host,
            **env,
        }
        # "--install" runs the script without --check-only (it must refuse before installing).
        mode = () if "--install" in args else ("--check-only",)
        return subprocess.run(
            ["bash", str(SCRIPT), *mode, *[a for a in args if a != "--install"]],
            capture_output=True,
            text=True,
            env=merged,
            check=False,
        )

    return run


def test_script_is_executable_in_the_index():
    listed = subprocess.run(
        ["git", "ls-files", "--stage", "--", "scripts/install_validator.sh"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert listed.split()[0] == "100755"


def test_a_machine_that_meets_the_requirements_passes(machine):
    done = machine()
    assert done.returncode == 0, done.stderr
    assert "meets the requirements" in done.stdout


def test_unreachable_docker_is_refused_with_its_code_and_next_step(machine):
    done = machine(STUB_DOCKER_DOWN="1")
    assert done.returncode == 2
    assert "V_DOCKER" in done.stderr and "Next:" in done.stderr


def test_cgroup_v1_is_refused(machine):
    done = machine(STUB_CGROUP="1")
    assert done.returncode == 2
    assert "V_CGROUP" in done.stderr


def test_unreachable_network_is_refused(machine):
    done = machine(STUB_CURL_FAIL="1")
    assert done.returncode == 2
    assert "V_NETWORK" in done.stderr and "github.com" in done.stderr


def test_too_little_disk_is_refused(machine):
    done = machine(CARBON_VALIDATOR_MIN_FREE_GIB="99999999")
    assert done.returncode == 2
    assert "V_DISK" in done.stderr


def test_gpu_needs_a_recent_driver_and_defers_the_toolkit_to_the_functional_check(
    machine,
):
    old = machine("--gpu", STUB_DRIVER="535.10")
    assert old.returncode == 2
    assert "V_GPU_DRIVER" in old.stderr and "V_GPU_TOOLKIT" not in old.stderr
    # A CDI-mode toolkit registers no runtime: not refused up front, only noted.
    ready = machine("--gpu", STUB_DRIVER="595.45")
    assert ready.returncode == 0, ready.stderr
    if not (glob.glob("/etc/cdi/*nvidia*") or glob.glob("/var/run/cdi/*nvidia*")):
        assert "GPU check after the install decides" in ready.stderr


def test_a_container_without_a_daemon_is_a_machine_type_refusal(machine):
    done = machine(STUB_DOCKER_DOWN="1", CARBON_VALIDATOR_ASSUME_MACHINE="container")
    assert done.returncode == 2
    assert "V_MACHINE_TYPE" in done.stderr and "V_DOCKER" not in done.stderr


def test_a_container_without_a_docker_cli_is_not_told_to_install_docker(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for tool in (
        "bash", "uname", "grep", "awk", "df", "dirname", "sed", "head",
        "cat", "tr", "cut", "env", "git", "sha256sum", "python3",
    ):  # fmt: skip
        found = shutil.which(tool)
        if found:
            (bin_dir / tool).symlink_to(found)
    _stub(bin_dir, "curl", "exit 0")
    _stub(bin_dir, "systemd-detect-virt", "exit 0")
    _host_stubs(bin_dir)
    done = subprocess.run(
        ["bash", str(SCRIPT), "--check-only"],
        capture_output=True,
        text=True,
        env={
            "PATH": str(bin_dir),
            "CARBON_STATE_DIR": str(tmp_path / "state"),
            "CARBON_VALIDATOR_ASSUME_MACHINE": "container",
            "CARBON_VALIDATOR_MIN_FREE_GIB": "0",
            "CARBON_VALIDATOR_MIN_CPUS": "1",
            "CARBON_VALIDATOR_MIN_RAM_GIB": "0",
            **_host_files(tmp_path),
        },
        check=False,
    )
    assert done.returncode == 2
    assert "V_MACHINE_TYPE" in done.stderr
    assert "docker is not installed" not in done.stderr


def test_every_failed_requirement_is_reported_together(machine):
    done = machine(STUB_CGROUP="1", STUB_CURL_FAIL="1")
    assert done.returncode == 2
    assert "V_CGROUP" in done.stderr and "V_NETWORK" in done.stderr


def test_start_receiver_without_a_receiver_is_refused(machine):
    done = machine("--start-receiver")
    assert done.returncode == 2
    assert "--receiver ID VERSION" in done.stderr


def test_the_machine_type_override_is_never_silent(machine):
    done = machine()
    assert "overrides the machine-type check" in done.stderr


# --- one validator host class (OWNER-VALIDATOR-HOST-CLASS-01) -----------------------------


def test_a_machine_of_the_registered_class_passes(machine):
    done = machine()
    assert done.returncode == 0, done.stderr
    assert "V_HOST_CLASS" not in done.stderr


@pytest.mark.parametrize(
    "env,code",
    [
        ({"STUB_MODEL": "Other Processor"}, "V_HOST_CLASS_MODEL"),
        ({"STUB_FLAGS": "avx2 fma avx512f"}, "V_HOST_CLASS_ISA"),
        ({"STUB_FLAGS": "avx2"}, "V_HOST_CLASS_ISA"),
        ({"STUB_FLAGS": "avx2 fma amx_tile"}, "V_HOST_CLASS_ISA"),
        ({"STUB_FLAGS": "avx2 fma avx512_bf16"}, "V_HOST_CLASS_ISA"),
        ({"STUB_NPROC": "3"}, "V_HOST_CLASS_VCPU"),
        ({"STUB_NPROC": "8"}, "V_HOST_CLASS_VCPU"),
    ],
)
def test_any_field_mismatch_is_refused_with_its_typed_code(machine, env, code):
    done = machine(**env)
    assert done.returncode == 2
    assert code in done.stderr and "Next:" in done.stderr
    assert done.stderr.count("V_HOST_CLASS") == 1


def test_memory_must_reach_the_registered_minimum(tmp_path, machine):
    short = machine(**_host_files(tmp_path, mem_kib=50 * 1048576 - 1))
    assert short.returncode == 2 and "V_HOST_CLASS_MEMORY" in short.stderr
    enough = machine(**_host_files(tmp_path, mem_kib=50 * 1048576))
    assert enough.returncode == 0, enough.stderr
    more = machine(**_host_files(tmp_path, mem_kib=64 * 1048576))
    assert more.returncode == 0, more.stderr


def test_all_mismatches_are_reported_together(machine):
    done = machine(STUB_MODEL="Other", STUB_NPROC="2")
    assert done.returncode == 2
    assert "V_HOST_CLASS_MODEL" in done.stderr and "V_HOST_CLASS_VCPU" in done.stderr


@pytest.mark.parametrize(
    "registered",
    [
        {
            **HOST_CLASS,
            "cpu_model_name": None,
            "nproc": None,
            "mem_total_min_gib": None,
        },
        {**HOST_CLASS, "schema": "other"},
        {**HOST_CLASS, "scope": "TEST"},
        {**HOST_CLASS, "nproc": 0},
        {**HOST_CLASS, "mem_total_min_gib": "50"},
        {**HOST_CLASS, "isa_flags_present": {"avx2": True}},
        {
            **HOST_CLASS,
            "isa_flags_present": {**HOST_CLASS["isa_flags_present"], "avx2": 1},
        },
    ],
)
def test_an_unmeasured_or_malformed_class_refuses_everything(
    tmp_path, machine, registered
):
    done = machine(**_host_files(tmp_path, registered=registered))
    assert done.returncode == 2
    assert "V_HOST_CLASS_UNREGISTERED" in done.stderr


def test_a_missing_class_file_refuses(tmp_path, machine):
    done = machine(CARBON_VALIDATOR_HOST_CLASS_FILE=str(tmp_path / "absent.json"))
    assert done.returncode == 2 and "V_HOST_CLASS_UNREGISTERED" in done.stderr


def test_the_committed_class_is_registered_and_well_formed():
    document = json.loads(
        (ROOT / "carbon/challenge_validator/validator-host-class.json").read_bytes()
    )
    assert document["schema"] == "carbon.validator.host-class.v1"
    assert document["scope"] == "DEVELOPMENT"
    assert document["cpu_model_name"] == "AMD EPYC-v4 Processor"
    assert document["isa_flags_present"] == {
        "avx2": True,
        "fma": True,
        "avx512f": False,
        "avx512_bf16": False,
        "amx": False,
    }
    assert document["nproc"] == 4 and document["mem_total_min_gib"] == 50


@pytest.mark.parametrize(
    "knob",
    [
        "CARBON_VALIDATOR_ASSUME_MACHINE",
        "CARBON_VALIDATOR_HOST_CLASS_FILE",
        "CARBON_VALIDATOR_MEMINFO_FILE",
    ],
)
def test_a_test_knob_never_admits_an_install(tmp_path, machine, knob):
    """The knobs make a check result possible, never an install: with any set, a real run refuses."""
    extra = {knob: "host"} if knob == "CARBON_VALIDATOR_ASSUME_MACHINE" else {}
    done = machine("--install", **extra)
    assert done.returncode == 2
    assert "V_TEST_OVERRIDE" in done.stderr and knob in done.stderr
    assert not (tmp_path / "state").exists()  # nothing was installed


def test_a_check_only_run_with_the_knobs_still_works(machine):
    done = machine()
    assert done.returncode == 0 and "V_TEST_OVERRIDE" not in done.stderr
