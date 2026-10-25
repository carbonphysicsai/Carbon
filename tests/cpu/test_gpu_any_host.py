"""Any NVIDIA GPU, any host: one test per recorded or described host shape
(GPU_ANY_HOST_20261025.md, step 1).

`tests/fixtures/gpu_hosts/<host>/` holds what a machine said about its GPU and
Docker (`scripts/dev/record_gpu_host.sh` records it; `meta.json` says whether the
folder is `recorded`, `described` or `synthetic`) and `expected.json`, the
behaviour the design requires of `prepare` on that host. A host the current code
cannot meet yet carries `currently_fails`: it is a strict xfail, so the change
that makes it pass must remove the mark (step 2 of the design).

Every refusal must print the fields it concerns, a reason and a next step, and
must not echo anything the host reported (a multi-GPU choice list excepted: it
goes to the operator's own screen)."""

import json
import os
import stat
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "dev"))

import carbon_accelerator

from carbon.reconstruction import onboarding
from carbon.reconstruction.host_inventory import PLATFORMS

FIXTURES = ROOT / "tests" / "fixtures" / "gpu_hosts"
posix = pytest.mark.skipif(os.name == "nt", reason="a fake vendor tool needs POSIX")


def _read(host, name):
    return json.loads((FIXTURES / host / name).read_text(encoding="utf-8"))


def _params():
    params = []
    for folder in sorted(p for p in FIXTURES.iterdir() if p.is_dir()):
        expected = _read(folder.name, "expected.json")
        marks = []
        if expected.get("currently_fails"):
            marks.append(
                pytest.mark.xfail(strict=True, reason=expected["currently_fails"])
            )
        params.append(pytest.param(folder.name, marks=marks, id=folder.name))
    return params


HOSTS = [p.values[0] for p in _params()]


def _smi(tmp_path, host):
    """A fake nvidia-smi that prints the host's recorded query output (or no tool)."""
    recorded = FIXTURES / host / "nvidia-smi-query.csv"
    if not recorded.exists():
        return tmp_path / "no-nvidia-smi"
    tool = tmp_path / "nvidia-smi"
    tool.write_text("#!/bin/sh\ncat <<'EOF'\n" + recorded.read_text() + "EOF\n")
    tool.chmod(tool.stat().st_mode | stat.S_IXUSR)
    return tool


def _prepare(tmp_path, capsys, host, monkeypatch):
    meta = _read(host, "meta.json")
    # The vendor probe seam step 2 must provide: what `lspci`/`rocm-smi`/`uname`
    # said, in vendor-probe.json's shape (absent today: the patch is inert).
    probe = _read(host, "vendor-probe.json")
    monkeypatch.setattr(onboarding, "probe_vendors", lambda: probe, raising=False)
    platform = meta.get("platform")
    code = carbon_accelerator.main(
        [
            "--host-root",
            str(tmp_path / "root"),
            "prepare",
            "--record-id",
            "this-machine",
            "--provider",
            "own-machine",
            *(["--platform", platform] if platform in PLATFORMS else []),
            "--container-runtime",
            "DOCKER_ENGINE",
            "--dry-run",
            "--miner-lane",
            "--smi",
            str(_smi(tmp_path, host)),
        ]
    )
    return code, json.loads(capsys.readouterr().out)


def test_the_corpus_is_labelled_and_complete():
    assert len(HOSTS) >= 9
    for host in HOSTS:
        meta = _read(host, "meta.json")
        assert meta["provenance"] in ("recorded", "described", "synthetic"), host
        assert meta["source"], host
        assert (FIXTURES / host / "expected.json").exists()
    # The corpus must grow by recording: at least one host is a real recording.
    assert any(_read(h, "meta.json")["provenance"] == "recorded" for h in HOSTS)


@posix
@pytest.mark.parametrize("host", _params())
def test_prepare_on_this_host_does_what_the_design_requires(
    host, tmp_path, capsys, monkeypatch
):
    expected = _read(host, "expected.json")["prepare"]
    code, out = _prepare(tmp_path, capsys, host, monkeypatch)
    if expected["status"] == "NOT_WRITTEN":
        assert code == 0 and out["status"] == "NOT_WRITTEN", out
        rows = (FIXTURES / host / "nvidia-smi-query.csv").read_text().splitlines()
        assert (
            out["document"]["device_uuid"]
            == rows[expected["chosen_index"]].split(",")[0].strip()
        )
        if expected["gpus"] > 1:
            # Several GPUs: the first is used and the choice is printed.
            assert out["chosen"]["index"] == expected["chosen_index"]
        return
    assert code == 2 and out["status"] == "REFUSED", out
    assert out["fields"] and out["reasons"] and out["next"], out
    if "fields" in expected:
        assert out["fields"] == expected["fields"]
    if "reason_contains" in expected:
        assert expected["reason_contains"] in json.dumps(out["reasons"])
    if "next_contains" in expected:
        assert expected["next_contains"] in out["next"]


class _Docker:
    """The recorded `docker info`, served the way the CLI wrapper serves it."""

    def __init__(self, info):
        self.info = info

    def json(self, arguments, **_):
        if arguments[0] == "version":
            return {"Version": self.info["ServerVersion"], "ApiVersion": "1.52"}
        if arguments[0] == "info":
            return self.info
        raise AssertionError(arguments)


@pytest.mark.parametrize(
    "host",
    [h for h in HOSTS if (FIXTURES / h / "docker-info.json").exists()],
)
def test_the_recorded_docker_shape_is_read_without_a_hardware_rule(host, tmp_path):
    info = _read(host, "docker-info.json")
    expected = _read(host, "expected.json")
    report = onboarding.doctor_report(root=tmp_path / "root", cli=_Docker(info))
    findings = {f["check"]: f for f in report["findings"]}
    assert findings["container_runtime"]["value"] == "DOCKER_ENGINE"
    runtime = findings["container_device_runtime"]
    assert (runtime["state"] == "READY") == expected["docker_nvidia_runtime"]
    if runtime["state"] != "READY":
        assert "NVIDIA Container Toolkit" in runtime["next"]
    # Docker 27, 28 and 29 are all read the same way (the version is just data).
    assert info["ServerVersion"].split(".")[0] in ("27", "28", "29")
