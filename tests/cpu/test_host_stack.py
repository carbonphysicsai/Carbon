"""The validator host's tested software stack (carbon.reconstruction.host_stack): the GPU lane reports
READY only on the registered Docker engine, image store and NVIDIA driver/toolkit, and the Docker facts
are read in ways that do not depend on one engine release's field set."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from test_receiver_setup import (
    TESTED_STACK,
    _accept,
    _Device,
    _gpu_files,
    _TestnetChecks,
)

from carbon.challenge_validator import receiver_setup
from carbon.reconstruction import host_stack

GOOD = dict(TESTED_STACK)


def _checks(facts):
    return {row["check"] for row in host_stack.problems(facts)}


def test_the_tested_stack_has_no_problems():
    assert host_stack.problems(GOOD) == []


@pytest.mark.parametrize(
    "change, check",
    [
        ({"docker_engine": "29.6.1"}, "docker_engine"),  # refused, with its reason
        ({"docker_engine": "29.9.2"}, "docker_engine"),  # newer is not tested
        ({"docker_engine": "28.0.4"}, "docker_engine"),
        ({"docker_engine": "27.3.1"}, "docker_engine"),
        ({"docker_engine": None}, "docker_engine"),
        ({"image_store": "classic"}, "image_store"),
        ({"image_store": "unknown"}, "image_store"),
        ({"nvidia_driver": "575.51.03"}, "nvidia_driver"),
        ({"nvidia_driver": "580.65.05"}, "nvidia_driver"),
        ({"nvidia_driver": "590.10"}, "nvidia_driver_series"),
        ({"nvidia_driver": None}, "nvidia_driver"),
        ({"nvidia_driver": "garbage"}, "nvidia_driver"),
        ({"nvidia_toolkit": None}, "nvidia_toolkit"),
        ({"nvidia_toolkit": "none"}, "nvidia_toolkit"),
    ],
)
def test_anything_else_is_a_named_problem(change, check):
    assert check in _checks({**GOOD, **change})


def test_a_refused_engine_says_why():
    (row,) = [r for r in host_stack.problems({**GOOD, "docker_engine": "29.6.1"})]
    assert "STAGING" in row["required"] and row["found"] == "29.6.1"


def test_a_missing_fact_is_never_a_pass():
    assert len(host_stack.problems({})) >= 4


def test_a_registered_toolkit_list_is_exact_when_filled():
    stack = {**host_stack.HOST_STACK, "nvidia_toolkit_tested": ("1.17.8",)}
    assert host_stack.problems(GOOD, stack) == []
    assert (
        _checks({**GOOD, "nvidia_toolkit": "1.18.0"}) == set()
    )  # none registered here
    assert [
        r["check"]
        for r in host_stack.problems({**GOOD, "nvidia_toolkit": "1.18.0"}, stack)
    ] == ["nvidia_toolkit"]


# ---- reading the facts without trusting one release's fields ------------------------


@pytest.mark.parametrize(
    "info, store",
    [
        (
            {
                "Driver": "overlayfs",
                "DriverStatus": [["driver-type", "io.containerd.snapshotter.v1"]],
            },
            "containerd",
        ),
        # a future engine that words it differently still announces a containerd snapshotter
        (
            {
                "Driver": "overlayfs",
                "DriverStatus": [["Snapshotter", "containerd.io/overlayfs"]],
            },
            "containerd",
        ),
        (
            {"Driver": "overlay2", "DriverStatus": [["Backing Filesystem", "extfs"]]},
            "classic",
        ),
        ({"Driver": "zfs", "DriverStatus": []}, "unknown"),
        ({}, "unknown"),
        (None, "unknown"),
        ({"DriverStatus": "not a list"}, "unknown"),
    ],
)
def test_the_image_store_is_read_from_what_the_engine_announces(info, store):
    assert host_stack.image_store(info) == store


def test_read_facts_uses_plain_commands_and_tolerates_what_is_absent():
    answers = {
        ("docker", "version", "--format", "{{.Server.Version}}"): "29.1.3\n",
        ("docker", "info", "--format", "{{json .}}"): json.dumps(
            {
                "Driver": "overlayfs",
                "DriverStatus": [["driver-type", "io.containerd.snapshotter.v1"]],
            }
        ),
        (
            "nvidia-smi",
            "--query-gpu=driver_version",
            "--format=csv,noheader",
        ): "580.159.03\n",
        (
            "nvidia-ctk",
            "--version",
        ): "NVIDIA Container Toolkit CLI version 1.17.8\ncommit: abc\n",
    }

    def run(command, **_):
        text = answers.get(tuple(command))
        return SimpleNamespace(
            returncode=0 if text is not None else 1, stdout=text or ""
        )

    facts = host_stack.read_facts(run=run, which=lambda name: name)
    assert facts == {
        "docker_engine": "29.1.3",
        "image_store": "containerd",
        "nvidia_driver": "580.159.03",
        "nvidia_toolkit": "1.17.8",
    }
    assert host_stack.problems(facts) == []
    nothing = host_stack.read_facts(
        run=lambda command, **_: (_ for _ in ()).throw(OSError("no docker")),
        which=lambda name: None,
    )
    assert nothing == {
        "docker_engine": None,
        "image_store": "unknown",
        "nvidia_driver": None,
        "nvidia_toolkit": None,
    }


# ---- the GPU lane refuses to be READY on anything else -----------------------------


@pytest.mark.parametrize(
    "change",
    [
        {"docker_engine": "29.6.1"},
        {"docker_engine": "29.9.2"},
        {"image_store": "classic"},
        {"nvidia_driver": "570.1"},
        {"nvidia_toolkit": None},
    ],
)
def test_gpu_check_is_not_ready_on_an_untested_stack(tmp_path, monkeypatch, change):
    image, ops = _gpu_files(tmp_path, "jax-gpu.json", "ops.json")
    _accept(monkeypatch)
    with pytest.raises(receiver_setup.SetupRefused, match="host_stack_not_tested"):
        receiver_setup.gpu_check(
            graph_gpu_image_manifest=image,
            graph_gpu_ops=ops,
            checks=_TestnetChecks(),
            device=_Device(),
            stack_facts={**GOOD, **change},
        )
