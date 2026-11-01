"""The host-side version overlay: add-only, digest-bound, image registry changed only by the hook (Validator, 2026-11-01)."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from carbon.challenge_kit import served_versions, version_overlay, version_registry

ROOT = Path(__file__).resolve().parents[2]
COOLING = "chip-cold-plate"
#: sha256 of version_registry.py on origin/main (ae260371c2) before the overlay hook.
IMAGE_REGISTRY_SHA256 = (
    "6eae4ac66da6aa925700e27762e26b68370866b5f0ffb0153a3963f2fb20bfd5"
)
HOOK_MARKER = b"\n\n\n# Host-side additions"


def _document():
    return json.loads(version_overlay.OVERLAY_PATH.read_bytes())


def _write(tmp_path, document):
    path = tmp_path / "overlay.json"
    path.write_text(json.dumps(document))
    return path


def test_the_image_registry_file_is_origin_main_plus_only_the_overlay_hook():
    data = (ROOT / "carbon/challenge_kit/version_registry.py").read_bytes()
    data = data.replace(b"\r\n", b"\n")
    head, marker, hook = data.partition(HOOK_MARKER)
    assert marker, "the overlay hook is missing"
    assert hook.rstrip().endswith(b"_overlay.install()")
    assert hook.count(b"\n") <= 8  # a comment, one import and one call: nothing else
    assert hashlib.sha256(head + b"\n").hexdigest() == IMAGE_REGISTRY_SHA256


def test_cooling_1_7_is_an_overlay_version_and_not_in_the_image_registry_text():
    text = (ROOT / "carbon/challenge_kit/version_registry.py").read_text("utf-8")
    assert "cooling-pool-sealed-v3" not in text
    assert version_overlay.is_overlay(COOLING, "1.7")
    entry = version_registry.entry(COOLING, "1.7")
    assert (entry.train, entry.allowlist, entry.catalog, entry.graph_adapter) == (
        version_registry.COOLING_TRAIN_ENCODED,
        "v8",
        True,
        "v2",
    )
    assert entry.output_encoding == version_registry.COOLING_LAW_SAFE
    assert entry.rebuild_wall_seconds == version_registry.REBUILD_LIMIT_SECONDS
    assert entry.development_evaluation == (
        "cooling-dual-development-grid-v3",
        "cooling-development-grid-8x6",
    )
    assert entry.catalog_entries_from == ("1.4", "1.3")


def test_install_is_idempotent_and_the_derived_sets_include_the_overlay_version():
    before = dict(version_registry.VERSIONS)
    assert version_overlay.install() == version_overlay.install()
    assert version_registry.VERSIONS == before
    key = (COOLING, "1.7")
    assert key in served_versions.V8 and key in served_versions.CATALOG
    assert served_versions.is_step2(*key) and served_versions.serves_catalog(*key)
    from carbon.challenge_kit import physical_public_train

    assert key in physical_public_train.ENCODED_VERSIONS  # 1.7 is law-safe encoded


def test_the_overlay_refuses_to_redefine_an_image_registered_version(tmp_path):
    document = _document()
    image = copy.deepcopy(document["versions"]["chip-cold-plate 1.7"])
    image["version"] = "1.6"
    document["versions"] = {"chip-cold-plate 1.6": image}
    with pytest.raises(version_overlay.OverlayRefused, match="image"):
        version_overlay.install(_write(tmp_path, document))
    assert (
        version_registry.entry(COOLING, "1.6").sealed_evaluation
        == "cooling-pool-sealed-v2"
    )


def test_the_overlay_refuses_a_changed_entry_for_an_installed_version(tmp_path):
    document = _document()
    document["versions"]["chip-cold-plate 1.7"]["step_caps"] = True
    with pytest.raises(version_overlay.OverlayRefused, match="different entry"):
        version_overlay.install(_write(tmp_path, document))
    assert version_registry.entry(COOLING, "1.7").step_caps is False


def _wrong_schema(d):
    d["schema"] = "other"


def _unknown_field(d):
    d["versions"]["chip-cold-plate 1.7"]["unknown_field"] = 1


def _misnamed(d):
    d["versions"]["chip-cold-plate 9.9"] = d["versions"]["chip-cold-plate 1.7"]


def _missing_field(d):
    del d["versions"]["chip-cold-plate 1.7"]["train"]


@pytest.mark.parametrize(
    "mutate", [_wrong_schema, _unknown_field, _misnamed, _missing_field]
)
def test_a_malformed_overlay_is_refused(tmp_path, mutate):
    document = _document()
    mutate(document)
    with pytest.raises(version_overlay.OverlayRefused):
        version_overlay.load(_write(tmp_path, document))


def test_a_missing_overlay_registers_nothing(tmp_path):
    assert version_overlay.load(tmp_path / "absent.json") == {}


def test_a_changed_field_is_a_different_registration_digest():
    document = _document()
    entry = document["versions"]["chip-cold-plate 1.7"]
    digest = version_overlay.entry_digest(COOLING, "1.7")
    assert digest == version_overlay.canonical_digest(entry)
    entry["rebuild_wall_seconds"] = 649
    assert version_overlay.canonical_digest(entry) != digest
    with pytest.raises(version_overlay.OverlayRefused):
        version_overlay.entry_digest(COOLING, "1.6")  # an image version has none


def test_the_overlay_module_is_a_worker_build_input_and_the_overlay_file_is_not():
    for listing in (
        "carbon/reconstruction/worker/build_inputs.txt",
        "carbon/reconstruction/worker/worker_image_files.txt",
    ):
        lines = (ROOT / listing).read_text("utf-8").splitlines()
        assert "carbon/challenge_kit/version_overlay.py" in lines, listing
        assert not any("version_overlay.json" in line for line in lines), listing
    ignore = (
        ROOT / ".devcontainer/Dockerfile.reconstruction-worker.dockerignore"
    ).read_text("utf-8")
    assert "!carbon/challenge_kit/version_overlay.py" in ignore


def _run(code, *args):
    env = {**os.environ, "PYTHONPATH": str(ROOT), "PYTHONDONTWRITEBYTECODE": "1"}
    return subprocess.run(
        [sys.executable, "-c", code, *args],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )


ORDER_CODE = "\n".join(  # noqa: FLY002
    [
        "import sys",
        "__import__('carbon.challenge_kit.' + sys.argv[1])",
        "from carbon.challenge_kit import version_registry, version_overlay",
        "assert version_registry.find('chip-cold-plate', '1.7') is not None",
        "assert version_overlay.is_overlay('chip-cold-plate', '1.7')",
        "print(len(version_registry.VERSIONS))",
    ]
)


def test_importing_the_overlay_or_the_registry_first_gives_the_same_registry():
    counts = {
        first: _run(ORDER_CODE, first).stdout.strip()
        for first in ("version_overlay", "version_registry", "served_versions")
    }
    assert len(set(counts.values())) == 1 and "" not in counts.values(), counts


PROBE = "\n".join(  # noqa: FLY002
    [
        "import importlib, importlib.util, os, sys",
        "target = sys.argv[1]",
        "if target.endswith('.py'):",
        "    sys.path.insert(0, os.path.dirname(target))",
        "    spec = importlib.util.spec_from_file_location('probe_target', target)",
        "    module = importlib.util.module_from_spec(spec)",
        "    sys.modules['probe_target'] = module",
        "    spec.loader.exec_module(module)",
        "else:",
        "    importlib.import_module(target)",
        "from carbon.challenge_kit import served_versions, version_registry",
        "key = ('chip-cold-plate', '1.7')",
        "assert version_registry.find(*key) is not None, 'unregistered'",
        "assert key in served_versions.V8, 'derived set stale'",
        "print('ok')",
    ]
)

#: The modules that derive a set from the registry AT IMPORT, plus every producer file that reads it: each must see the
#: overlay version, and the derived sets must include it, in a clean interpreter.
CONSUMERS = (
    "carbon.challenge_kit.served_versions",
    "carbon.challenge_kit.physical_public_train",
    "carbon.challenge_kit.f02_train",
    "carbon.challenge_kit.f08_train",
    "carbon.challenge_kit.physical_material",
    "carbon.cold_plate.campaign",
    "carbon.motor.campaign",
    "carbon.scoring.dev_grid",
    "carbon.scoring.cooling_encoded_dual_pack",
    "carbon.scoring.f02_dual_pack",
    "carbon.scoring.f08_dual_pack",
    "carbon.scoring.motor_dual_pack",
    "carbon.scoring.pool_adapters",
    "carbon.challenge_registry.registry",
)

RECEIVER_ENTRY_POINTS = (
    "carbon.challenge_validator.direct_receiver",
    "carbon.challenge_validator.receiver_setup",
    "carbon.challenge_validator.crown_pause_sweep",
    "carbon.validator_setup.weights",
    "scripts/dev/sealed_exam/pool_pack.py",
)


@pytest.mark.parametrize("module", CONSUMERS + RECEIVER_ENTRY_POINTS)
def test_every_consumer_and_receiver_entry_sees_the_overlay_version_in_a_clean_interpreter(
    module,
):
    target = str(ROOT / module) if module.endswith(".py") else module
    result = _run(PROBE, target)
    assert result.returncode == 0 and result.stdout.strip() == "ok", (
        module,
        result.stderr[-600:],
    )


DERIVED = "\n".join(  # noqa: FLY002
    [
        "from carbon.challenge_kit import physical_public_train as p, served_versions as s",
        "from carbon.challenge_kit import f02_train, f08_train, version_registry as r",
        "from carbon.cold_plate import campaign as c",
        "key = ('chip-cold-plate', '1.7')",
        "assert key in p.ENCODED_VERSIONS and key in s.V8 and key in s.CATALOG",
        "assert '1.7' in c.CATALOG_VERSIONS",
        "assert f02_train.CHALLENGE_VERSIONS == r.versions(f02_train.CHALLENGE_ID)",
        "assert f08_train.CHALLENGE_VERSIONS == r.versions(f08_train.CHALLENGE_ID)",
        "print('ok')",
    ]
)


def test_the_import_time_derived_sets_agree_with_the_registry_in_a_clean_interpreter():
    result = _run(DERIVED)
    assert result.stdout.strip() == "ok", result.stderr[-600:]
