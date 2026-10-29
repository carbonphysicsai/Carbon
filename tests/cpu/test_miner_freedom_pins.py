"""Miner-freedom invariant pins (Validator rulings MINER_FREEDOM_RULINGS_20261029, section 3).

A limit stays only if it strictly protects the exam, grading, containment, disclosure or keys.
Freedom values are pinned as FLOORS (raising them passes, lowering them fails); containment and
disclosure values are pinned EXACTLY. A merge that reverts any decision fails here. Nothing in this
file changes a resource value: the 4090 values and the owner's acceptance are separate.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from carbon.challenge_kit import served_versions, version_registry
from carbon.level4 import allowlist as allowlist_module
from carbon.reconstruction.worker import model

ROOT = Path(__file__).resolve().parents[2]
GIB = 1024**3

MOTOR, COOLING = version_registry.MOTOR, version_registry.COOLING
F08, F02 = version_registry.F08, version_registry.F02
#: The launch versions (rulings section 1, question 2): v8 and uncapped, served by the launch
#: receivers. Older versions stay as frozen history.
LAUNCH = [
    (MOTOR, "1.5"),
    (COOLING, "1.5"),
    (COOLING, "1.6"),
    (F08, "1.6"),
    (F08, "1.7"),
    (F02, "2.5"),
]
IDS = [f"{c}-{v}" for c, v in LAUNCH]


def _allowlist(challenge, version):
    return allowlist_module.Allowlist(
        served_versions.material_allowlist_bytes(challenge, version)
    )


# --- T1 -------------------------------------------------------------------------------------


@pytest.mark.parametrize(("challenge", "version"), LAUNCH, ids=IDS)
def test_t1_every_launch_version_is_uncapped_v8_with_the_large_profile(
    challenge, version
):
    entry = version_registry.entry(challenge, version)
    assert served_versions.serves_uncapped(challenge, version)
    assert entry.allowlist == "v8" and entry.step_caps is False
    assert served_versions.step_caps(challenge, version) is False
    # the large profile is applied (its worker-resources version is the allowlist's)
    applied = served_versions.worker_resources(challenge, version)
    assert applied == _allowlist(challenge, version).version
    assert model.worker_resources_for(applied) == model.LARGE_MODEL_RESOURCES


# --- T2 -------------------------------------------------------------------------------------


@pytest.mark.parametrize(("challenge", "version"), LAUNCH, ids=IDS)
def test_t2_an_uncapped_graph_state_has_no_size_ceiling_but_the_containment_bound(
    challenge, version
):
    from carbon.development_session import bundle_graph_state

    limits = bundle_graph_state._limits(_allowlist(challenge, version))
    assert limits == (None, allowlist_module.CONTAINMENT["document_bytes"], None)
    # the fixed v6-and-older bounds exist only for capped versions
    assert bundle_graph_state.MAX_GRAPH_BYTES == 1024**2
    assert bundle_graph_state.MAX_PARAMETERS == 4096


# --- T3 -------------------------------------------------------------------------------------


def test_t3_the_large_profile_is_at_least_todays_values():
    large = model.LARGE_MODEL_RESOURCES
    assert large["memory_bytes"] >= 16 * GIB
    assert large["output_bytes"] >= 2 * GIB
    assert large["scratch_bytes"] >= 4 * GIB
    assert model.LARGE_MODEL_CPU_COUNT >= 4
    assert model.LARGE_MODEL_SHM_BYTES >= 2 * GIB
    # and never below the C-03 profile it replaces
    old = model.worker_resources_for(None)
    for key in ("memory_bytes", "output_bytes", "scratch_bytes"):
        assert large[key] >= old[key]
    assert model.LARGE_MODEL_CPU_COUNT >= model.CPU_COUNT


def test_t3_the_validation_child_keeps_at_least_todays_address_space():
    """Containment: the validation child parses an untrusted artifact on Carbon's host, so its
    RLIMIT_AS stays. Today's floor; the scale-to-lane-memory change waits on the measurement.
    """
    assert model.VALIDATION_MEMORY_BYTES >= 4 * GIB


@pytest.mark.xfail(
    strict=True,
    reason="OPEN (rulings section 1, item 4): validation RLIMIT_AS = the lane memory on "
    "large-profile versions waits for the 2 GiB measurement. Flip this to a plain test when "
    "the scaling lands (strict xfail: it fails the moment it starts passing).",
)
def test_t3_validation_rlimit_is_at_least_the_lane_memory_on_large_versions():
    assert model.VALIDATION_MEMORY_BYTES >= model.LARGE_MODEL_RESOURCES["memory_bytes"]


# --- T4 -------------------------------------------------------------------------------------


def test_t4_miner_container_adds_no_resource_flags_without_a_host_profile():
    from carbon.development_session import miner_container as mc

    assert mc._profile_arguments(None) == []
    flags = mc._profile_arguments(
        mc.ResourceProfile(cpus=4, memory_bytes=16 * GIB, pids_limit=256, nofile=1024)
    )
    assert {"--cpus", "--memory", "--memory-swap", "--pids-limit"} <= set(flags)
    # the flags exist in this module ONLY inside _profile_arguments
    tree = ast.parse(Path(mc.__file__).read_text(encoding="utf-8"))
    holders = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            for child in ast.walk(node):
                if isinstance(child, ast.Constant) and child.value in (
                    "--memory",
                    "--cpus",
                    "--pids-limit",
                ):
                    holders.add(node.name)
    assert holders == {"_profile_arguments"}


# --- T5 -------------------------------------------------------------------------------------


@pytest.mark.parametrize(("challenge", "version"), LAUNCH, ids=IDS)
def test_t5_the_workers_memory_is_the_published_policys_per_version(challenge, version):
    from carbon.challenge_kit import physical_material

    policy = physical_material.bundle_material(challenge, version)[
        "construction_limits_document"
    ]["reconstruction_resource_policy"]
    profile = model.DevelopmentWorkerProfile(
        research_resource_policy_digest="sha256:" + "1" * 64,
        resource_class_digest="sha256:" + "2" * 64,
        worker_resources_version=served_versions.worker_resources(challenge, version),
        rebuild_wall_seconds=policy["build_wall_seconds_max"],
    )
    assert profile.effective_memory_bytes == policy["memory_bytes_max"]
    assert profile.effective_cpu_count == policy["cpu_count_max"]
    assert profile.effective_deadline_seconds == policy["build_wall_seconds_max"]
    source = Path(model.__file__).with_name("docker_runtime.py").read_text()
    # --memory and --memory-swap are both built from effective_memory_bytes
    assert source.count("str(worker_profile.effective_memory_bytes)") >= 2


# --- T6 -------------------------------------------------------------------------------------


def test_t6_only_the_development_approval_path_reaches_effective_controls():
    """A v7/v8 launch never reaches `development_admission.effective_controls`: its only caller
    is the development-host-approval path of the worker controller (the 4 GiB registered
    ceiling there must never bind a launch)."""
    callers = set()
    for path in (ROOT / "carbon").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "effective_controls(" not in text:
            continue
        for node in ast.walk(ast.parse(text)):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "effective_controls"
            ):
                callers.add(str(path.relative_to(ROOT)).replace("\\", "/"))
    assert callers == {"carbon/reconstruction/worker/controller.py"}
    from carbon.reconstruction.worker import development_admission as da

    assert da.REGISTERED_CONTROL_CEILINGS["host_ram_bytes"] == model.MEMORY_BYTES
    for challenge, version in LAUNCH:
        # a launch's profile is the large one, which that ceiling does not describe
        assert served_versions.worker_resources(challenge, version) is not None


# --- T7 -------------------------------------------------------------------------------------


def test_t7_the_graph_route_v2_rebuild_wall_equals_its_registered_value():
    record = ROOT / ".agent" / "decisions" / "2026-10-26-OWNER-REBUILD-WALL-11MIN-01.md"
    assert record.is_file()  # the record id the registry cites
    source = Path(version_registry.__file__).read_text(encoding="utf-8")
    assert "OWNER-REBUILD-WALL-11MIN-01" in source
    assert version_registry.REBUILD_LIMIT_SECONDS == 648
    assert version_registry.REBUILD_TASK_WALL_SECONDS == 947
    routed = [
        key
        for key, entry in version_registry.VERSIONS.items()
        if entry.graph_adapter == "v2"
    ]
    assert routed
    for key in routed:
        assert (
            version_registry.VERSIONS[key].rebuild_wall_seconds
            == version_registry.REBUILD_LIMIT_SECONDS
        ), key
    for key in LAUNCH:
        assert version_registry.VERSIONS[key].rebuild_wall_seconds == 648, key


# --- T8 -------------------------------------------------------------------------------------


def test_t8_the_door_allow_list(receiver_for_t8):
    from carbon.challenge_validator import direct_intake as di

    intake = receiver_for_t8
    info = intake.handle("GET", di.INFO_PATH, {}, b"", "127.0.0.1")
    assert info.status == 200
    assert info.body["tools"] == [
        di.SUBMIT_TOOL,
        di.STATUS_TOOL,
        di.RESEARCH_NAMESPACE,
    ]
    assert info.body["source_staging"]["operation"] == "stage_research_source"
    assert "material_staging" not in info.body
    assert info.body["exam_feedback"]["tool"] == di.FEEDBACK_TOOL
    # nothing but the registered routes
    for method, path in (
        ("GET", "/carbon/v1/other"),
        ("POST", di.INFO_PATH),
        ("GET", di.SUBMIT_PATH),
        ("PUT", di.SUBMIT_PATH),
    ):
        assert intake.handle(method, path, {}, b"", "127.0.0.1").status in (404, 405)
    source = Path(di.__file__).read_text(encoding="utf-8")
    assert 'call.operation != "stage_research_source"' in source


# --- T9 -------------------------------------------------------------------------------------


def _mining_versions(text, marker):
    line = next(row for row in text.splitlines() if marker in row)
    found = set()
    names = {
        "Motor": MOTOR,
        "Cooling": COOLING,
        "Ribbed Bracket": F08,
        "Burst Thermal": F02,
        "Battery": version_registry.BATTERY,
    }
    for name, challenge in names.items():
        for match in re.finditer(
            re.escape(name) + r" ((?:\d+\.\d+)(?: (?:to|and) \d+\.\d+)?)", line
        ):
            numbers = re.findall(r"\d+\.\d+", match.group(1))
            if " to " in match.group(1):
                low, high = numbers
                every = sorted(
                    v
                    for (c, v) in version_registry.VERSIONS
                    if c == challenge
                    and tuple(map(int, low.split(".")))
                    <= tuple(map(int, v.split(".")))
                    <= tuple(map(int, high.split(".")))
                )
                found.update((challenge, v) for v in every)
            else:
                found.update((challenge, v) for v in numbers)
    return found


def test_t9_the_mining_guide_lists_exactly_the_large_resource_versions():
    text = (ROOT / "docs" / "MINING.md").read_text(encoding="utf-8")
    large = {
        key
        for key in version_registry.VERSIONS
        if served_versions.worker_resources(*key) is not None
    }
    assert _mining_versions(text, "**Rebuild resources.**") == large
    line = next(r for r in text.splitlines() if "**Rebuild resources.**" in r)
    resources = model.LARGE_MODEL_RESOURCES
    assert (
        f"{model.LARGE_MODEL_CPU_COUNT} CPUs, {resources['memory_bytes'] // GIB} GiB of memory, "
        f"{resources['scratch_bytes'] // GIB} GiB of scratch space and up to "
        f"{resources['output_bytes'] // GIB} GiB of output"
    ) in line
    walled = {
        key
        for key, entry in version_registry.VERSIONS.items()
        if entry.rebuild_wall_seconds is not None
    }
    assert _mining_versions(text, "**Build time limit.**") == walled


# --- T10 ------------------------------------------------------------------------------------

#: Modules whose strings tell a miner what their machine needs. Requirements come from the
#: version's profile (`supported_setup` derives them), never a literal in the string.
MINER_VISIBLE = (
    "carbon/development_session/supported_setup.py",
    "carbon/development_session/research_campaign.py",
    "carbon/development_session/research_catalog.py",
    "scripts/dev/miner_launchpad/supervisor.py",
)
_REQUIREMENT_LITERAL = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:CPUs?|vCPUs?|cores?)\b"
    r"|\b\d+(?:\.\d+)?[- ]?GiB\b(?=[^.;]{0,40}(?:memory|limit|worker|RAM))"
    r"|(?:memory|limit|worker|RAM)[^.;]{0,40}\b\d+(?:\.\d+)?[- ]?GiB\b",
    re.IGNORECASE,
)
#: What a machine reports when it is too small (an example, not a requirement), and the fixed
#: 1 GiB headroom the Docker doctor adds to the version's limit (`docker_runtime.doctor`).
_ALLOWED = ("15.6 GiB", "plus 1 GiB", "1 GiB more")


def _string_literals(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docstrings = {
        id(body[0].value)
        for node in ast.walk(tree)
        if isinstance(
            node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef
        )
        and (body := node.body)
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
    }
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and id(node) not in docstrings
        ):
            yield node.lineno, node.value


@pytest.mark.parametrize("module", MINER_VISIBLE)
def test_t10_no_miner_visible_string_states_a_cpu_or_memory_requirement_literal(
    module,
):
    offenders = []
    for lineno, value in _string_literals(ROOT / module):
        cleaned = value
        for allowed in _ALLOWED:
            cleaned = cleaned.replace(allowed, "")
        if _REQUIREMENT_LITERAL.search(cleaned):
            offenders.append((lineno, value[:90]))
    assert not offenders, offenders


def test_t10_the_requirements_are_derived_from_the_large_profile():
    from carbon.development_session import supported_setup as ss

    assert ss.MIN_CPUS == model.LARGE_MODEL_CPU_COUNT
    assert ss.WORKER_MEMORY_GIB == model.LARGE_MODEL_RESOURCES["memory_bytes"] // GIB
    assert ss.MIN_DOCKER_MEMORY_GIB == ss.WORKER_MEMORY_GIB + 1
    # the campaign refusal and the supervisor fallback say the same derived numbers
    from scripts.dev.miner_launchpad import supervisor

    text = supervisor.NEXT_ACTIONS["practice_host_too_small"]
    assert f"{ss.MIN_DOCKER_MEMORY_GIB} GiB" in text and f"{ss.MIN_CPUS} CPUs" in text


# --- fixtures -------------------------------------------------------------------------------

from test_direct_intake_source_staging import receiver  # noqa: F401  (a fixture)


@pytest.fixture
def receiver_for_t8(receiver):  # noqa: F811
    return receiver[0]
