"""CLI boundary toys; no model, physics, solver, provider or hidden material."""

import hashlib
import json
import sys
from types import ModuleType

import pytest

from scripts.dev.score_lab import __main__ as cli


def input_document():
    return {
        "schema": "carbon.scorelab.rich-design-input.v1",
        "scope": "PUBLIC_DEVELOPMENT",
        "policy": {"id": "TOY_ONLY"},
        "reference": {},
        "models": [],
        "original_pack": {},
        "original_benchmark": {},
        "provenance": {},
    }


def invoke(tmp_path, document, *, digest=None):
    raw = document if isinstance(document, bytes) else json.dumps(document).encode()
    path = tmp_path / "input.json"
    path.write_bytes(raw)
    output = tmp_path / "result.json"
    args = [
        "rich-design",
        "--input",
        str(path),
        "--input-sha256",
        digest or hashlib.sha256(raw).hexdigest(),
        "--out",
        str(output),
    ]
    return args, output


def refuse_legacy_import():
    raise AssertionError("public rich-Design must not load historical battery jobs")


def test_cli_reuses_projection_and_binds_exact_input_bytes(tmp_path, monkeypatch):
    calls = []
    module = ModuleType("carbon.scoring.design_benchmark")

    def project(*args, **kwargs):
        calls.append((args, kwargs))
        return {"scope": "PUBLIC_DEVELOPMENT", "reduction": {}, "projections": {}}

    module.score_design_benchmark = project
    monkeypatch.setitem(sys.modules, module.__name__, module)
    monkeypatch.setattr(cli, "_legacy_modules", refuse_legacy_import)
    document = input_document()
    document["original_result"] = {"retained": "TOY_ONLY"}
    document["measurement_basis"] = {"binding": "TOY_CALL_FORWARDING_ONLY"}
    args, output = invoke(tmp_path, document)
    assert cli.main(args) == 0
    assert len(calls) == 1
    assert calls[0][0] == tuple(
        document[name]
        for name in (
            "policy",
            "reference",
            "models",
            "original_pack",
            "original_benchmark",
        )
    )
    assert calls[0][1] == {
        "provenance": document["provenance"],
        "original_result": document["original_result"],
        "measurement_basis": document["measurement_basis"],
    }
    report = json.loads(output.read_text())
    assert (
        report["input_bytes_sha256"]
        == hashlib.sha256((tmp_path / "input.json").read_bytes()).hexdigest()
    )


@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: value.update(scope="LIVE"),
        lambda value: value.update(schema="unknown"),
        lambda value: value.update(hidden_seed=1),
        lambda value: value.pop("reference"),
    ],
)
def test_cli_refuses_nonpublic_or_wrong_input_contract(tmp_path, monkeypatch, mutate):
    monkeypatch.setattr(cli, "_legacy_modules", refuse_legacy_import)
    document = input_document()
    mutate(document)
    args, output = invoke(tmp_path, document)
    with pytest.raises(SystemExit) as error:
        cli.main(args)
    assert error.value.code == 2
    assert not output.exists()


@pytest.mark.parametrize(
    "raw,digest",
    [
        (b'{"schema": 1, "schema": 2}', None),
        (b'{"value": NaN}', None),
        (json.dumps(input_document()).encode(), "0" * 64),
    ],
)
def test_cli_refuses_duplicate_nonfinite_and_changed_input(tmp_path, raw, digest):
    args, output = invoke(tmp_path, raw, digest=digest)
    with pytest.raises(SystemExit) as error:
        cli.main(args)
    assert error.value.code == 2
    assert not output.exists()


def test_cli_preserves_existing_result(tmp_path):
    args, output = invoke(tmp_path, input_document())
    output.write_bytes(b"previous retained result")
    with pytest.raises(SystemExit) as error:
        cli.main(args)
    assert error.value.code == 2
    assert output.read_bytes() == b"previous retained result"
