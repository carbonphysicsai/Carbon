"""Config continuity mechanics with public inert config; no worker/chain use."""

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_composition_ladder import MINER, strategy

from carbon.battery import deployment
from carbon.battery.daemon import DevelopmentCompilerUnavailable
from carbon.development_ladder import operate
from carbon.reconstruction import capability_registry as registry
from carbon.reconstruction import development_composition as dc


@pytest.fixture(autouse=True)
def isolated_cache(monkeypatch):
    monkeypatch.setattr(deployment, "_VALIDATORS", {})


def config_file(tmp_path, *, ladder=True):
    value = {
        "schema": deployment.SCHEMA,
        "state": str(tmp_path / "not-created-state.sqlite3"),
        "private_root": str(tmp_path / "never-read-root.bin"),
        "journal": str(tmp_path / "never-read-journal.jsonl"),
        "work": str(tmp_path / "never-created-work"),
        "backend": "direct",
        "require_commitment": False,
    }
    if ladder:
        value.update(
            development_only=True,
            batch_source="answer_key",
            require_commitment=True,
            commitment_reader={
                "network": "testnet",
                "endpoint": "wss://test.finney.opentensor.ai:443",
                "provider": "bittensor-official-test",
                "genesis_hash": "0x8f9cf856bf558a14440e75569c9e58594757048d7b3a84b5d25f6bd978263105",
                "netuid": 567,
            },
            ladder={
                "hotkeys": [MINER],
                "variants": [dc.load(registry.BATTERY_CHALLENGE).version],
            },
        )
    path = tmp_path / "deployment.json"
    path.write_text(json.dumps(value) + "\n", encoding="utf-8")
    path.chmod(0o600)
    return path, value


def factory_target(path, monkeypatch):
    builds = []

    def build(config, *, repository, readonly=False):
        builds.append(config)
        target = SimpleNamespace(
            ladder=deployment.ladder_for(config), readonly=readonly
        )
        if target.ladder is not None:
            operate.setup(target)  # No parts/config: no filesystem/worker construction.
        return target

    monkeypatch.setattr(deployment, "build", build)
    return deployment.validator(path, repository="never-read-repository"), builds


def composition_digest():
    return dc.load(registry.BATTERY_CHALLENGE).digest


def assert_infra(target):
    with pytest.raises(DevelopmentCompilerUnavailable) as failed:
        target.development_compiler(strategy(), composition_digest())
    assert str(failed.value) == "construction_checks_unavailable"
    assert failed.value.candidate is False


def test_snapshot_hashes_the_single_validated_read_and_keeps_dict_api(
    tmp_path, monkeypatch
):
    path, value = config_file(tmp_path)
    original = Path.read_bytes
    reads = []

    def read(file):
        if file == path:
            reads.append(file)
        return original(file)

    monkeypatch.setattr(Path, "read_bytes", read)
    config, digest = deployment._load_config_snapshot(path)
    assert config == value and type(config) is dict
    assert digest == hashlib.sha256(original(path)).hexdigest()
    assert reads == [path]
    assert deployment.load_config(path) == value
    assert reads == [path, path]


def test_existing_loader_errors_and_schema_are_preserved(tmp_path):
    path, _ = config_file(tmp_path)
    path.write_text('{"schema": "wrong"}', encoding="utf-8")
    with pytest.raises(deployment.EvaluationUnavailable) as failed:
        deployment.load_config(path)
    assert failed.value.code == "evaluation_config_schema"
    path.write_text("{", encoding="utf-8")
    with pytest.raises(ValueError):
        deployment.load_config(path)


def test_unchanged_cached_target_rechecks_each_composition_call(tmp_path, monkeypatch):
    path, _ = config_file(tmp_path)
    target, builds = factory_target(path, monkeypatch)
    original = Path.read_bytes
    reads = []
    compiled = []

    def read(file):
        if file == path:
            reads.append(file)
        return original(file)

    def compile_recipe(*args):
        compiled.append(args)
        return "existing-compiler-result"

    monkeypatch.setattr(Path, "read_bytes", read)
    monkeypatch.setattr(operate, "compile_variant", compile_recipe)
    assert deployment.validator(path, repository="never-read-repository") is target
    assert len(builds) == 1 and reads == []
    for _ in range(2):
        assert (
            target.development_compiler(strategy(), composition_digest())
            == "existing-compiler-result"
        )
    assert len(compiled) == 2 and reads == [path, path]


def test_raw_whitespace_change_stops_cached_target_before_compiler_or_parts(
    tmp_path, monkeypatch
):
    path, _ = config_file(tmp_path)
    target, builds = factory_target(path, monkeypatch)
    raw = path.read_bytes()
    path.write_bytes(raw + b" ")
    assert json.loads(path.read_bytes()) == json.loads(raw)
    assert deployment.validator(path, repository="unused") is target
    monkeypatch.setattr(
        operate,
        "compile_variant",
        lambda *args: pytest.fail("compiler or parts touched"),
    )
    assert_infra(target)
    assert len(builds) == 1
    assert str(path) not in str(target.development_compiler)


def test_change_between_admission_and_pre_rebuild_never_reuses_positive(
    tmp_path, monkeypatch
):
    path, _ = config_file(tmp_path)
    target, _ = factory_target(path, monkeypatch)
    calls = []
    monkeypatch.setattr(
        operate, "compile_variant", lambda *args: calls.append(args) or "admitted"
    )
    assert target.development_compiler(strategy(), composition_digest()) == "admitted"
    path.write_bytes(path.read_bytes() + b"\n")
    assert_infra(target)
    assert len(calls) == 1


@pytest.mark.parametrize(
    "failure", ["missing", "permissions", "symlink", "directory", "unreadable"]
)
def test_file_failures_are_typed_infrastructure_before_work(
    tmp_path, monkeypatch, failure
):
    path, _ = config_file(tmp_path)
    target, _ = factory_target(path, monkeypatch)
    if failure == "missing":
        path.unlink()
    elif failure == "permissions":
        path.chmod(0o644)
    elif failure == "symlink":
        raw = path.read_bytes()
        path.unlink()
        replacement = tmp_path / "other.json"
        replacement.write_bytes(raw)
        replacement.chmod(0o600)
        path.symlink_to(replacement)
    elif failure == "directory":
        path.unlink()
        path.mkdir()
    else:
        original = Path.read_bytes

        def unreadable(file):
            if file == path:
                raise PermissionError("private config must not be echoed")
            return original(file)

        monkeypatch.setattr(Path, "read_bytes", unreadable)
    monkeypatch.setattr(
        operate,
        "compile_variant",
        lambda *args: pytest.fail("compiler or parts touched"),
    )
    assert_infra(target)


def test_snapshot_continuity_does_not_override_default_required_checks(
    tmp_path, monkeypatch
):
    path, _ = config_file(tmp_path)
    target, _ = factory_target(path, monkeypatch)
    monkeypatch.setattr(dc, "compile", lambda *args: pytest.fail("compiler touched"))
    assert_infra(target)  # File matches; original provider still says UNAVAILABLE.


def test_direct_setup_and_legacy_variants_gain_no_new_guard(tmp_path, monkeypatch):
    path, _ = config_file(tmp_path)
    target, _ = factory_target(path, monkeypatch)
    path.unlink()
    forwarded = []
    monkeypatch.setattr(
        operate, "compile_variant", lambda *args: forwarded.append(args) or "legacy"
    )
    found = dc.load(registry.BATTERY_CHALLENGE)
    for digest in (found.base_contract_digest, found.variants[-1].digest):
        assert target.development_compiler(strategy(), digest) == "legacy"
    direct = SimpleNamespace(ladder=target.ladder)
    operate.setup(direct)
    assert not hasattr(direct, "_deployment_config_check")
    assert direct.development_compiler(strategy(), composition_digest()) == "legacy"
    assert len(forwarded) == 3


def test_nonladder_factory_has_no_composition_snapshot_authority(tmp_path, monkeypatch):
    path, _ = config_file(tmp_path, ladder=False)
    target, builds = factory_target(path, monkeypatch)
    assert target.ladder is None and len(builds) == 1
    assert not hasattr(target, "_deployment_config_check")


def test_noncallable_private_guard_refuses_before_work(tmp_path, monkeypatch):
    path, _ = config_file(tmp_path)
    target, _ = factory_target(path, monkeypatch)
    target._deployment_config_check = False
    monkeypatch.setattr(
        operate, "compile_variant", lambda *args: pytest.fail("compiler touched")
    )
    assert_infra(target)
