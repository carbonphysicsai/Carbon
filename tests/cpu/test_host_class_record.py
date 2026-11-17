"""The host-class filler (scripts/dev/host_class_record.py): a v2 class record is filled only from boxes' identity reads,
one class only when the boxes agree, every difference printed otherwise; a template keeps every box-read field an
explicit placeholder and is deliberately not a well-formed class. Synthetic identities only.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "dev" / "host_class_record.py"
_spec = importlib.util.spec_from_file_location("host_class_record", SCRIPT)
filler = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(filler)

DECISION = "OWNER-5950X-GRADING-CLASS-01 (finney)"
FLAGS = ["fpu", "sse2", "avx", "avx2", "fma", "sha_ni"]


def _identity(name, **changes):
    document = {
        "schema": filler.IDENTITY_SCHEMA,
        "box": name,
        "captured_utc": "2026-11-16T00:00:00Z",
        "cpu_model_name": "Fixture Desktop 16-Core Processor",
        "lscpu_flags": FLAGS,
        "cpuinfo_flags": FLAGS,
        "nproc": 32,
        "kernel": "6.8.0-1-fixture",
        "microcode": ["0xfixture"] * 32,
        "os": "Fixture Linux 24.04",
        "docker_server_version": "29.1.3",
        "mem_total_kb": 131_000_000,
        "virtualization": "none",
        "lscpu_p": "0,0,0\n",
    }
    document.update(changes)
    return document


def _write(tmp_path, document):
    path = tmp_path / f"{document['box']}.identity.json"
    path.write_bytes((json.dumps(document, indent=2, sort_keys=True) + "\n").encode())
    return path


def _argv(tmp_path, out, *paths):
    argv = [
        "--id",
        "VALIDATOR-HOST-CLASS-FIXTURE-01",
        "--scope",
        "MAINNET",
        "--owner-decision",
        DECISION,
    ]
    for path in paths:
        argv += ["--identity", f"{path.name.split('.')[0]}={path}"]
    return [*argv, "--read-by", "fixture", "--procedure", "fixture", "--out", str(out)]


def test_two_agreeing_boxes_fill_one_wellformed_class_modelled_on_the_epyc_record(
    tmp_path,
):
    a = _write(tmp_path, _identity("fsn1"))
    b = _write(tmp_path, _identity("hel1", mem_total_kb=130_000_000))
    out = tmp_path / "class.json"
    assert (
        filler.main(
            [
                *_argv(tmp_path, out, a, b),
                "--expect-sha256",
                f"fsn1={hashlib.sha256(a.read_bytes()).hexdigest()}",
            ]
        )
        == 0
    )
    record = json.loads(out.read_bytes())
    assert filler.wellformed(record)
    assert record["isa_flags_present"] == {
        "amx": False,
        "avx2": True,
        "avx512_bf16": False,
        "avx512f": False,
        "fma": True,
    }
    assert (
        record["nproc"] == 32
        and record["virtualization"] == "none"
        and record["scope"] == "MAINNET"
    )
    assert (
        record["mem_total_min_gib"] == 130_000_000 // 1048576
    )  # the lowest box, floored
    assert record["recorded"]["owner_decision"] == DECISION
    assert (
        record["recorded"]["identity_json_sha256"]["hel1"]
        == hashlib.sha256(b.read_bytes()).hexdigest()
    )
    assert record["recorded"]["microcode"] == {
        "fsn1": "0xfixture",
        "hel1": "0xfixture",
    } and record["recorded"]["boxes"] == ["fsn1", "hel1"]
    # the same top-level fields as the registered EPYC class
    epyc = json.loads(
        (
            ROOT / "scripts" / "validator_host_classes" / "EPYC7402P-VM-01.json"
        ).read_bytes()
    )
    assert set(record) == set(epyc)
    assert out.read_bytes().count(b"\r") == 0


@pytest.mark.parametrize(
    "field, value",
    [
        ("cpu_model_name", "Other 16-Core Processor"),
        ("lscpu_flags", FLAGS + ["avx512f"]),
        ("kernel", "6.8.0-2-fixture"),
        ("nproc", 16),
        ("virtualization", "kvm"),
        ("os", "Fixture Linux 22.04"),
        ("docker_server_version", "28.0.0"),
    ],
)
def test_boxes_that_differ_are_not_one_class_and_the_difference_is_printed(
    tmp_path, capsys, field, value
):
    changes = {field: value}
    if field == "lscpu_flags":
        changes["cpuinfo_flags"] = value
    a = _write(tmp_path, _identity("fsn1"))
    b = _write(tmp_path, _identity("hel1", **changes))
    out = tmp_path / "class.json"
    assert filler.main(_argv(tmp_path, out, a, b)) == 2
    err = capsys.readouterr().err
    assert "not one class" in err and "hel1" in err and "fsn1" in err
    assert not out.exists()


@pytest.mark.parametrize(
    "changes, message",
    [
        ({"microcode": ["0xa"] * 31 + ["0xb"]}, "different microcode"),
        ({"cpuinfo_flags": FLAGS + ["amx_tile"]}, "disagree on ISA"),
        ({"box": "other"}, "captured as box"),
        ({"schema": "nope"}, "is not a"),
        ({"nproc": "32"}, "positive integer"),
        ({"cpu_model_name": ""}, "empty"),
    ],
)
def test_a_broken_identity_refuses(tmp_path, capsys, changes, message):
    document = _identity("fsn1", **changes)
    path = tmp_path / "fsn1.identity.json"
    path.write_bytes(json.dumps(document).encode())
    assert filler.main(_argv(tmp_path, tmp_path / "c.json", path)) == 2
    assert message in capsys.readouterr().err


def test_a_wrong_kit_sha_or_crlf_refuses(tmp_path, capsys):
    a = _write(tmp_path, _identity("fsn1"))
    assert (
        filler.main(
            [
                *_argv(tmp_path, tmp_path / "c.json", a),
                "--expect-sha256",
                "fsn1=" + "0" * 64,
            ]
        )
        == 2
    )
    a.write_bytes(a.read_bytes().replace(b"\n", b"\r\n"))
    assert filler.main(_argv(tmp_path, tmp_path / "c.json", a)) == 2
    assert "carriage return" in capsys.readouterr().err


def test_amx_is_any_amx_flag_as_the_installer_reads_it():
    assert filler.isa_flags(["amx_tile"])["amx"] is True
    assert filler.isa_flags(["avx512f", "avx512_bf16"]) == {
        "amx": False,
        "avx2": False,
        "avx512_bf16": True,
        "avx512f": True,
        "fma": False,
    }


def test_the_template_keeps_box_reads_as_placeholders_and_is_not_a_class(tmp_path):
    out = tmp_path / "t.json"
    argv = [
        "--template",
        "--box",
        "fsn1",
        "--box",
        "hel1",
        "--id",
        "VALIDATOR-HOST-CLASS-FIXTURE-01",
    ]
    argv += ["--scope", "MAINNET", "--owner-decision", DECISION, "--out", str(out)]
    assert filler.main(argv) == 0
    record = json.loads(out.read_bytes())
    assert not filler.wellformed(record)
    for key in ("cpu_model_name", "mem_total_min_gib", "nproc", "virtualization"):
        assert record[key] == filler.PLACEHOLDER
    assert set(record["isa_flags_present"].values()) == {filler.PLACEHOLDER}
    for key in ("kernel", "microcode", "os", "docker"):
        assert record["recorded"][key] == filler.PLACEHOLDER
    assert record["recorded"]["identity_json_sha256"] == {
        "fsn1": filler.PLACEHOLDER,
        "hel1": filler.PLACEHOLDER,
    }


def test_the_filler_agrees_with_the_installer_on_wellformed():
    """`wellformed` mirrors install_validator.sh's v2 test: the registered EPYC class passes it."""
    epyc = json.loads(
        (
            ROOT / "scripts" / "validator_host_classes" / "EPYC7402P-VM-01.json"
        ).read_bytes()
    )
    assert filler.wellformed(epyc)
    installer = (ROOT / "scripts" / "install_validator.sh").read_text()
    assert 'FLAGS = ("avx2", "fma", "avx512f", "avx512_bf16", "amx")' in installer
    assert tuple(filler.FLAGS) == ("avx2", "fma", "avx512f", "avx512_bf16", "amx")


# -- one class across CPU revisions: microcode and stepping RECORDED per box, never required equal (owner, 16 Nov) ----


def test_microcode_and_stepping_are_recorded_per_box_not_required_equal(tmp_path):
    a = _write(
        tmp_path, _identity("fsn1", microcode=["0xa201211"] * 32, stepping=["2"] * 32)
    )
    b = _write(
        tmp_path, _identity("hel1", microcode=["0xa20102e"] * 32, stepping=["0"] * 32)
    )
    out = tmp_path / "class.json"
    assert filler.main(_argv(tmp_path, out, a, b)) == 0
    record = json.loads(out.read_bytes())
    assert filler.wellformed(record)
    assert record["recorded"]["microcode"] == {"fsn1": "0xa201211", "hel1": "0xa20102e"}
    assert record["recorded"]["stepping"] == {"fsn1": "2", "hel1": "0"}


def test_identities_without_stepping_record_no_stepping(tmp_path):
    a = _write(tmp_path, _identity("fsn1", microcode=["0xa201211"] * 32))
    b = _write(tmp_path, _identity("hel1", microcode=["0xa20102e"] * 32))
    out = tmp_path / "class.json"
    assert filler.main(_argv(tmp_path, out, a, b)) == 0
    assert "stepping" not in json.loads(out.read_bytes())["recorded"]


@pytest.mark.parametrize(
    "stepping, message",
    [(["0"] * 31 + ["2"], "different steppings"), (["x"] * 32, "decimal")],
)
def test_one_box_must_report_one_stepping(tmp_path, capsys, stepping, message):
    path = _write(tmp_path, _identity("fsn1", stepping=stepping))
    assert filler.main(_argv(tmp_path, tmp_path / "c.json", path)) == 2
    assert message in capsys.readouterr().err
