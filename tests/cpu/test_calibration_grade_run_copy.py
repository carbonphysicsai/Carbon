"""calibration_grade_run grades from exactly what the official receiver grades from: the delivered copy
(``--copy-hotkey``) and, for a pool-graded version, the pool material of the sealed bank merged into the
accuracy definition (``physical_dual_pack`` dual-native path)."""

import contextlib
import json
from pathlib import Path

import pytest

from carbon.challenge_validator import calibration_grade as cg
from carbon.challenge_validator import calibration_grade_run as run_module
from carbon.scoring import f08_sealed_dual_pack, physical_adapters, sealed_batch_source


def test_a_pool_graded_adapter_gets_the_banks_pool_material_in_its_definition():
    adapter = f08_sealed_dual_pack.adapter("1.7")
    assert getattr(adapter, "POOL_GRADED", False)
    pool = {"sets": [["a"]], "kind": "f08"}
    definition = {"producer_digest": "sha256:x"}
    graded = run_module.graded_definition(adapter, {"pool": pool}, definition)
    assert graded == {**definition, "pool": pool}
    assert "pool" not in definition  # the pack's public role is not mutated


def test_a_pool_graded_bank_without_pool_material_is_refused_typed():
    adapter = f08_sealed_dual_pack.adapter("1.7")
    with pytest.raises(
        cg.CalibrationRefused, match="calibration_pool_material_missing"
    ):
        run_module.graded_definition(adapter, {}, {"a": 1})


def test_a_version_that_is_not_pool_graded_keeps_its_definition_unchanged():
    adapter = physical_adapters.adapter("f08-ribbed-bracket", "1.5")
    assert not getattr(adapter, "POOL_GRADED", False)
    definition = {"a": 1}
    assert (
        run_module.graded_definition(adapter, {"pool": {"sets": []}}, definition)
        is definition
    )


def test_the_copy_hotkey_reaches_the_banks_resolution(monkeypatch):
    seen = {}

    def resolve(**kwargs):
        seen.update(kwargs)
        return None

    monkeypatch.setattr(sealed_batch_source, "resolve", resolve)
    from carbon.challenge_kit import physical_pack

    monkeypatch.setattr(physical_pack, "development_bank", lambda *a: {"inputs": []})
    with contextlib.suppress(Exception):  # only the resolution call matters here
        run_module.resolve_bank(
            object(), Path("."), "f08-ribbed-bracket", "1.5", copy_hotkey="HOTKEY"
        )
    assert seen["copy_hotkey"] == "HOTKEY"


def test_the_command_line_takes_copy_hotkey_and_passes_it_to_run(monkeypatch, capsys):
    seen = {}

    def fake_run(**kwargs):
        seen.update(kwargs)
        return {"schema": "carbon.calibration-grade.v1", "total": 0.5}

    monkeypatch.setattr(run_module, "run", fake_run)
    from carbon.challenge_validator import cpu_pin

    monkeypatch.setattr(cpu_pin, "require", lambda: None)
    rc = run_module.main(
        [
            "--artifact",
            "a",
            "--pack",
            "p",
            "--challenge",
            "f08-ribbed-bracket",
            "--version",
            "1.7",
            "--work",
            "w",
            "--fake",
            "--copy-hotkey",
            "5Hotkey",
        ]
    )
    assert rc == 0 and seen["copy_hotkey"] == "5Hotkey"
    assert json.loads(capsys.readouterr().out)["total"] == 0.5
    seen.clear()
    run_module.main(
        [
            "--artifact",
            "a",
            "--pack",
            "p",
            "--challenge",
            "c",
            "--version",
            "1",
            "--work",
            "w",
            "--fake",
        ]
    )
    assert seen["copy_hotkey"] is None
