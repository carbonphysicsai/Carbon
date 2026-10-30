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
    _stub(
        stubs,
        "systemd-detect-virt",
        '[[ -n "${STUB_VIRT:-}" ]] && { echo "${STUB_VIRT}"; exit 0; }; exit 1',
    )
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


def test_setup_and_one_receiver_are_not_combined(machine):
    done = machine("--setup", "--receiver", "f02", "2.3")
    assert done.returncode == 2
    assert "not both" in done.stderr


@pytest.mark.parametrize(
    "flags",
    [("--domain", "v.example.org"), ("--packs", "/tmp"), ("--challenges", "all")],
)
def test_setup_options_need_setup(machine, flags):
    done = machine(*flags)
    assert done.returncode == 2
    assert "go with --setup" in done.stderr


def test_setup_needs_the_validator_hotkey_before_anything_runs(tmp_path):
    # E2: no hotkey and no terminal to ask on: refused before the machine checks.
    done = subprocess.run(
        ["bash", str(SCRIPT), "--setup"],
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
        env={**os.environ, "CARBON_STATE_DIR": str(tmp_path / "state")},
        check=False,
    )
    assert done.returncode == 2
    assert "--hotkey SS58 is required" in done.stderr
    assert "Checking this machine" not in done.stdout


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
    # VALIDATOR-HOST-CLASS-7950X-01: the dedicated validator box (Ryzen 9 7950X, AVX-512).
    assert document["cpu_model_name"] == "AMD Ryzen 9 7950X 16-Core Processor"
    assert document["isa_flags_present"] == {
        "avx2": True,
        "fma": True,
        "avx512f": True,
        "avx512_bf16": True,
        "amx": False,
    }
    assert document["nproc"] == 32 and document["mem_total_min_gib"] == 124


@pytest.mark.parametrize(
    "knob",
    [
        "CARBON_VALIDATOR_ASSUME_MACHINE",
        "CARBON_VALIDATOR_HOST_CLASS_FILE",
        "CARBON_VALIDATOR_MEMINFO_FILE",
        # Swaps the interpreter that runs the recorded-image check: a real install must not accept it.
        "CARBON_IMAGE_CHECK_PYTHON",
    ],
)
def test_a_test_knob_never_admits_an_install(tmp_path, machine, knob):
    """The knobs make a check result possible, never an install: with any set, a real run refuses."""
    # The fixture already sets the class file and the meminfo file; the other knobs are set here.
    own = ("CARBON_VALIDATOR_HOST_CLASS_FILE", "CARBON_VALIDATOR_MEMINFO_FILE")
    extra = {} if knob in own else {knob: "host"}
    done = machine("--install", **extra)
    assert done.returncode == 2
    assert "V_TEST_OVERRIDE" in done.stderr and knob in done.stderr
    assert not (tmp_path / "state").exists()  # nothing was installed


def test_a_check_only_run_with_the_knobs_still_works(machine):
    done = machine()
    assert done.returncode == 0 and "V_TEST_OVERRIDE" not in done.stderr


def test_a_check_only_run_may_set_the_image_check_interpreter(machine):
    done = machine(CARBON_IMAGE_CHECK_PYTHON="/usr/bin/python3")
    assert done.returncode == 0 and "V_TEST_OVERRIDE" not in done.stderr


# --- the GPUYard VM class (VALIDATOR-HOST-CLASS-EPYC7402P-VM-01, stage 1: identity) ----------------------------

CLASS_DIR = ROOT / "scripts" / "validator_host_classes"
PRIMARY_CLASS = ROOT / "carbon" / "challenge_validator" / "validator-host-class.json"
EPYC_VM = {
    "STUB_MODEL": "AMD EPYC 7402P 24-Core Processor",
    "STUB_FLAGS": "avx2 fma",
    "STUB_NPROC": "8",
    "STUB_VIRT": "vm-other",
}
EPYC_KIB = 65_819_092  # the guest's MemTotal (62.77 GiB, floors to 62)


def _real_classes(tmp_path, mem_kib=EPYC_KIB, directory=CLASS_DIR):
    meminfo = tmp_path / "meminfo-real"
    meminfo.write_text(f"MemTotal:       {mem_kib} kB\nMemFree:        1 kB\n")
    return {
        "CARBON_VALIDATOR_HOST_CLASS_FILE": str(PRIMARY_CLASS),
        "CARBON_VALIDATOR_HOST_CLASS_DIR": str(directory),
        "CARBON_VALIDATOR_MEMINFO_FILE": str(meminfo),
    }


def test_the_gpuyard_vm_class_is_accepted_exactly(tmp_path, machine):
    done = machine(**_real_classes(tmp_path), **EPYC_VM)
    assert done.returncode == 0, done.stderr
    assert "V_HOST_CLASS" not in done.stderr


def test_the_7950x_class_stays_registered_beside_it(tmp_path, machine):
    done = machine(
        **_real_classes(tmp_path, mem_kib=124 * 1048576),
        STUB_MODEL="AMD Ryzen 9 7950X 16-Core Processor",
        STUB_FLAGS="avx2 fma avx512f avx512_bf16",
        STUB_NPROC="32",
    )
    assert done.returncode == 0, done.stderr


@pytest.mark.parametrize(
    "env, kib, code",
    [
        # EPYC-Milan (the retired ccx33 class) is refused, naming the model
        ({"STUB_MODEL": "AMD EPYC-Milan Processor"}, EPYC_KIB, "V_HOST_CLASS_MODEL"),
        (
            {"STUB_MODEL": "AMD EPYC 7452 32-Core Processor"},
            EPYC_KIB,
            "V_HOST_CLASS_MODEL",
        ),
        ({"STUB_FLAGS": "avx2 fma avx512f"}, EPYC_KIB, "V_HOST_CLASS_ISA"),
        ({"STUB_FLAGS": "avx2 fma avx512_bf16"}, EPYC_KIB, "V_HOST_CLASS_ISA"),
        ({"STUB_FLAGS": "avx2 fma amx_tile"}, EPYC_KIB, "V_HOST_CLASS_ISA"),
        ({"STUB_FLAGS": "avx2"}, EPYC_KIB, "V_HOST_CLASS_ISA"),
        ({"STUB_NPROC": "7"}, EPYC_KIB, "V_HOST_CLASS_VCPU"),
        ({"STUB_NPROC": "16"}, EPYC_KIB, "V_HOST_CLASS_VCPU"),
        ({}, 62 * 1048576 - 1, "V_HOST_CLASS_MEMORY"),
        ({"STUB_VIRT": "kvm"}, EPYC_KIB, "V_HOST_CLASS_VIRT"),
        ({"STUB_VIRT": "none"}, EPYC_KIB, "V_HOST_CLASS_VIRT"),
    ],
)
def test_each_single_drift_from_the_gpuyard_class_is_refused_with_one_code(
    tmp_path, machine, env, kib, code
):
    done = machine(**_real_classes(tmp_path, mem_kib=kib), **{**EPYC_VM, **env})
    if code is None:
        assert done.returncode == 0, done.stderr
        return
    assert done.returncode == 2 and code in done.stderr
    assert done.stderr.count("V_HOST_CLASS") == 1, done.stderr


def test_exactly_62_gib_is_enough_for_the_gpuyard_class(tmp_path, machine):
    done = machine(**_real_classes(tmp_path, mem_kib=62 * 1048576), **EPYC_VM)
    assert done.returncode == 0, done.stderr


def test_a_drift_from_the_7950x_class_still_names_exactly_that_drift(tmp_path, machine):
    done = machine(
        **_real_classes(tmp_path, mem_kib=124 * 1048576),
        STUB_MODEL="AMD Ryzen 9 7950X 16-Core Processor",
        STUB_FLAGS="avx2 fma avx512f avx512_bf16",
        STUB_NPROC="31",
    )
    assert done.returncode == 2 and "V_HOST_CLASS_VCPU" in done.stderr
    assert done.stderr.count("V_HOST_CLASS") == 1


def test_a_machine_of_neither_class_gets_the_closest_classs_refusals(tmp_path, machine):
    done = machine(**_real_classes(tmp_path), STUB_MODEL="Other", STUB_NPROC="2")
    assert done.returncode == 2
    assert "V_HOST_CLASS_MODEL" in done.stderr and "V_HOST_CLASS_VCPU" in done.stderr


def test_a_malformed_extra_class_file_is_not_a_class(tmp_path, machine):
    bad = tmp_path / "classes"
    bad.mkdir()
    (bad / "broken.json").write_text("{not json")
    (bad / "wrong-schema.json").write_text(
        json.dumps({"schema": "carbon.validator.host-class.v1"})
    )
    done = machine(**_real_classes(tmp_path, directory=bad), **EPYC_VM)
    assert done.returncode == 2 and "V_HOST_CLASS_MODEL" in done.stderr


def test_an_unregistered_primary_class_still_refuses_everything_even_with_extras(
    tmp_path, machine
):
    env = _real_classes(tmp_path)
    env["CARBON_VALIDATOR_HOST_CLASS_FILE"] = str(tmp_path / "absent.json")
    done = machine(**env, **EPYC_VM)
    assert done.returncode == 2 and "V_HOST_CLASS_UNREGISTERED" in done.stderr


def test_the_class_dir_is_a_test_knob_never_allowed_for_an_install(tmp_path, machine):
    done = machine("--install", **_real_classes(tmp_path), **EPYC_VM)
    assert done.returncode == 2 and "V_TEST_OVERRIDE" in done.stderr
    assert "CARBON_VALIDATOR_HOST_CLASS_DIR" in done.stderr


def test_the_committed_gpuyard_record_is_stage_1_identity_only_and_outside_the_build_inputs():
    from carbon.reconstruction.worker import build_inputs

    record = json.loads((CLASS_DIR / "EPYC7402P-VM-01.json").read_bytes())
    assert record["schema"] == "carbon.validator.host-class.v2"
    assert record["id"] == "VALIDATOR-HOST-CLASS-EPYC7402P-VM-01"
    assert record["scope"] == "DEVELOPMENT" and record["stage"] == 1
    assert record["cpu_model_name"] == "AMD EPYC 7402P 24-Core Processor"
    assert record["isa_flags_present"] == {
        "amx": False,
        "avx2": True,
        "avx512_bf16": False,
        "avx512f": False,
        "fma": True,
    }
    assert (record["nproc"], record["mem_total_min_gib"]) == (8, 62)
    assert record["virtualization"] == "vm-other"
    assert 65_819_092 // 1048576 == record["mem_total_min_gib"]
    # stage 2 (image ids, thread pins, lane cpusets, CPU pin values) is explicitly not registered here
    assert record["recorded"]["stage_2"].startswith("UNREGISTERED")
    assert not any(
        key in record for key in ("image_ids", "thread_pins", "lane_cpusets")
    )
    relative = "scripts/validator_host_classes/EPYC7402P-VM-01.json"
    inputs = build_inputs.paths()
    assert not any(relative == p or relative.startswith(p + "/") for p in inputs)
    # the 7950X class file is untouched: still v1, still the only primary class
    primary = json.loads(PRIMARY_CLASS.read_bytes())
    assert primary["schema"] == "carbon.validator.host-class.v1"
    assert primary["cpu_model_name"] == "AMD Ryzen 9 7950X 16-Core Processor"


# --- a class file counts only if it is tracked at HEAD and unmodified (Validator condition) --------------------------


def _checkout(tmp_path):
    """A scratch git checkout holding the installer, the primary class and the committed v2 classes, as a box has them."""
    repo = tmp_path / "box"
    (repo / "scripts").mkdir(parents=True)
    (repo / "carbon" / "challenge_validator").mkdir(parents=True)
    shutil.copy(SCRIPT, repo / "scripts" / "install_validator.sh")
    shutil.copy(
        PRIMARY_CLASS,
        repo / "carbon" / "challenge_validator" / "validator-host-class.json",
    )
    shutil.copytree(CLASS_DIR, repo / "scripts" / "validator_host_classes")

    def git(*args):
        return subprocess.run(
            [
                "git",
                "-c",
                "user.name=t",
                "-c",
                "user.email=t@t",
                "-C",
                str(repo),
                *args,
            ],
            check=True,
            capture_output=True,
            text=True,
        )

    git("init", "-q")
    git("add", "-A")
    git("commit", "-q", "-m", "box")
    return repo, git


def _check_on_box(repo, tmp_path, machine_env):
    """Run the box's own installer copy with NO class knobs, so the default class directory and the git rule apply."""
    stubs = tmp_path / "stubs-box"
    stubs.mkdir(exist_ok=True)
    _host_stubs(stubs)
    _stub(
        stubs,
        "docker",
        'if [[ "$1" == info ]]; then [[ "$*" == *CgroupVersion* ]] && echo 2; [[ "$*" == *Runtimes* ]] && echo "{\\"runc\\":{}}"; fi; exit 0',
    )
    _stub(stubs, "curl", "exit 0")
    _stub(stubs, "nvidia-smi", 'echo ""')
    _stub(stubs, "systemd-detect-virt", 'echo "${STUB_VIRT:-}"')
    meminfo = tmp_path / "meminfo-box"
    meminfo.write_text(f"MemTotal:       {EPYC_KIB} kB\nMemFree:        1 kB\n")
    env = {
        **os.environ,
        "PATH": f"{stubs}:{os.environ['PATH']}",
        "CARBON_VALIDATOR_ASSUME_MACHINE": "host",
        "CARBON_STATE_DIR": str(tmp_path / "state-box"),
        "CARBON_VALIDATOR_MIN_FREE_GIB": "0",
        "CARBON_VALIDATOR_MIN_CPUS": "1",
        "CARBON_VALIDATOR_MIN_RAM_GIB": "0",
        "CARBON_VALIDATOR_MEMINFO_FILE": str(meminfo),
        **machine_env,
    }
    return subprocess.run(
        ["bash", str(repo / "scripts" / "install_validator.sh"), "--check-only"],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


def test_a_committed_unmodified_class_file_admits_the_machine(tmp_path):
    repo, _ = _checkout(tmp_path)
    done = _check_on_box(repo, tmp_path, EPYC_VM)
    assert done.returncode == 0, done.stderr


def test_an_edited_class_file_never_admits_a_machine_even_in_check_only(tmp_path):
    repo, _ = _checkout(tmp_path)
    record = repo / "scripts" / "validator_host_classes" / "EPYC7402P-VM-01.json"
    edited = json.loads(record.read_text())
    edited["cpu_model_name"] = "Some Other Processor"
    record.write_text(json.dumps(edited))  # edited in place, not committed
    done = _check_on_box(
        repo, tmp_path, {**EPYC_VM, "STUB_MODEL": "Some Other Processor"}
    )
    assert done.returncode == 2 and "V_HOST_CLASS_MODEL" in done.stderr


def test_a_staged_but_uncommitted_edit_does_not_count_either(tmp_path):
    repo, git = _checkout(tmp_path)
    record = repo / "scripts" / "validator_host_classes" / "EPYC7402P-VM-01.json"
    edited = json.loads(record.read_text())
    edited["nproc"] = 3
    record.write_text(json.dumps(edited))
    git("add", "--", str(record))
    done = _check_on_box(repo, tmp_path, {**EPYC_VM, "STUB_NPROC": "3"})
    assert done.returncode == 2 and "V_HOST_CLASS" in done.stderr


def test_an_untracked_class_file_dropped_on_the_box_never_admits_a_machine(tmp_path):
    repo, _ = _checkout(tmp_path)
    dropped = json.loads(
        (
            repo / "scripts" / "validator_host_classes" / "EPYC7402P-VM-01.json"
        ).read_text()
    )
    dropped["id"] = "DROPPED"
    dropped["cpu_model_name"] = "Some Other Processor"
    (repo / "scripts" / "validator_host_classes" / "dropped.json").write_text(
        json.dumps(dropped)
    )
    done = _check_on_box(
        repo, tmp_path, {**EPYC_VM, "STUB_MODEL": "Some Other Processor"}
    )
    assert done.returncode == 2 and "V_HOST_CLASS_MODEL" in done.stderr
    # the committed class still admits its own machine beside the stray file
    assert _check_on_box(repo, tmp_path, EPYC_VM).returncode == 0


def test_a_checkout_without_git_admits_no_extra_class(tmp_path):
    repo, _ = _checkout(tmp_path)
    shutil.rmtree(repo / ".git")
    done = _check_on_box(repo, tmp_path, EPYC_VM)
    assert (
        done.returncode == 2 and "V_HOST_CLASS_MODEL" in done.stderr
    )  # only the primary class is left


def test_a_deleted_committed_class_file_is_simply_not_a_class(tmp_path):
    repo, _ = _checkout(tmp_path)
    (repo / "scripts" / "validator_host_classes" / "EPYC7402P-VM-01.json").unlink()
    done = _check_on_box(repo, tmp_path, EPYC_VM)
    assert done.returncode == 2 and "V_HOST_CLASS_MODEL" in done.stderr
