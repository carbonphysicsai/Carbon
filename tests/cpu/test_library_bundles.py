"""No library archive or wheel can become a controller-side import."""

import ast
import hashlib
import importlib.util
import io
import json
import os
import struct
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

import carbon.development_session.library_bundles as bundles
from carbon.development_session.library_bundles import (
    BUNDLE_SCHEMA,
    UV_IMAGE,
    _environment_digest,
    build_offline_bundle,
    bundle_ref,
    catalogue,
    load_cached_bundle_material,
    load_pinned_bundle_directory,
    load_cached_wheels,
    parent_stage_tag,
    prepare_offline_context,
    prepare_pinned_bundle_directory,
    provision_offline_bundle,
    uv_stage_tag,
    validate_bundle,
)


def sha(body):
    return "sha256:" + hashlib.sha256(body).hexdigest()


def archive(name="source/package.py", *, symlink=False):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz") as tar:
        member = tarfile.TarInfo(name)
        if symlink:
            member.type = tarfile.SYMTYPE
            member.linkname = "../secret"
            tar.addfile(member)
        else:
            body = b"VALUE = 1\n"
            member.size = len(body)
            tar.addfile(member, io.BytesIO(body))
        license_member = tarfile.TarInfo("source/LICENSE")
        license_member.size = 4
        tar.addfile(license_member, io.BytesIO(b"MIT\n"))
    return output.getvalue()


def wheel_archive(members=None):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as wheel:
        payload = members or {"package/__init__.py": b"VALUE = 1\n"}
        for name, body in payload.items():
            wheel.writestr(name, body)
    return output.getvalue()


def fixture():
    source, license_text = archive(), b"MIT\n"
    wheel = wheel_archive()
    lock = (
        b"package==1 --hash=sha256:"
        + hashlib.sha256(wheel).hexdigest().encode()
        + b"\n"
    )
    wheels = {"package-1-py3-none-any.whl": wheel}
    manifest = {
        "schema": BUNDLE_SCHEMA,
        "name": "example-library",
        "language": "python",
        "source_sha256": sha(source),
        "source_bytes": len(source),
        "runtime_profile_id": "torch-cu130-py311",
        "base_environment_digest": "sha256:" + "c" * 64,
        "environment_digest": _environment_digest("sha256:" + "c" * 64, sha(lock)),
        "os": "linux",
        "architecture": "amd64",
        "python_abi": "cp311",
        "accelerator": "cuda13",
        "lock_sha256": sha(lock),
        "wheels": {name: sha(body) for name, body in wheels.items()},
        "license_sha256": sha(license_text),
    }
    return manifest, source, wheels, lock, license_text


def cached_fixture(tmp_path):
    args = fixture()
    cache = tmp_path / "private-bundle"
    cache.mkdir(mode=0o700)
    wheelhouse = cache / "wheels"
    wheelhouse.mkdir(mode=0o700)
    for name, body in (
        ("source.tar.gz", args[1]),
        ("requirements.txt", args[3]),
        ("LICENSE", args[4]),
    ):
        (cache / name).write_bytes(body)
    for name, body in args[2].items():
        (wheelhouse / name).write_bytes(body)
    return cache, args


def user_directory(tmp_path):
    manifest, source, wheels, lock, license_text = fixture()
    manifest["name"] = "user-novel-operator"
    directory = tmp_path / "user-source"
    directory.mkdir()
    (directory / "wheels").mkdir()
    (directory / "bundle.json").write_text(json.dumps(manifest), encoding="utf-8")
    for name, body in (
        ("source.tar.gz", source),
        ("requirements.txt", lock),
        ("LICENSE", license_text),
    ):
        (directory / name).write_bytes(body)
    for name, body in wheels.items():
        (directory / "wheels" / name).write_bytes(body)
    return directory, manifest


def test_catalogue_names_new_and_existing_sources_without_claiming_install():
    document = catalogue()
    assert {row["id"] for row in document["libraries"]} >= {
        "transolver-plus",
        "jno",
        "foundax",
        "neuraloperator",
        "physicsnemo",
    }
    assert all(row["status"] == "DISCOVERY_ONLY" for row in document["libraries"])
    assert document["official_eligible"] is False


def test_offline_context_is_content_addressed_and_replay_checked(tmp_path):
    args = fixture()
    expected = validate_bundle(*args)
    parent = "sha256:" + "b" * 64
    root, actual, seal = prepare_offline_context(tmp_path, *args, parent)
    assert actual == expected
    assert root.parent.name == expected[7:]
    assert root.name == parent[7:]
    assert (root / "source.tar.gz").read_bytes() == args[1]
    dockerfile = (root / "Dockerfile").read_text()
    assert (
        "--no-index --find-links=/tmp/wheels --require-hashes --no-deps" in dockerfile
    )
    assert "pip check --python /opt/carbon-worker/bin/python" in dockerfile
    assert dockerfile.index("--no-deps") < dockerfile.index("pip check --python")
    assert "FROM " + parent_stage_tag(actual, parent) in dockerfile
    assert "FROM " + uv_stage_tag(actual) + " AS uv" in dockerfile
    assert "FROM ghcr.io/" not in dockerfile
    assert "USER 65532:65532" in dockerfile
    ast.parse((root / "install-source.py").read_text())
    assert prepare_offline_context(tmp_path, *args, parent) == (root, actual, seal)
    (root / "requirements.txt").write_bytes(b"changed")
    with pytest.raises(ValueError, match="cache collision"):
        prepare_offline_context(tmp_path, *args, parent)
    ref = bundle_ref(*args)
    assert ref.bundle_digest == expected
    assert ref.environment_digest == args[0]["environment_digest"]
    assert "image" not in ref.__dict__
    assert type(ref).from_dict(ref.to_dict()) == ref
    with pytest.raises(ValueError):
        type(ref).from_dict({**ref.to_dict(), "image_id": parent})


def test_cached_wheel_loader_selects_only_pinned_bytes_and_refuses_mutation(tmp_path):
    manifest, _, wheels, _, _ = fixture()
    cache = tmp_path / "private-wheels"
    cache.mkdir(mode=0o700)
    for name, body in wheels.items():
        (cache / name).write_bytes(body)
    (cache / "unrelated-2-py3-none-any.whl").write_bytes(b"cache extra")
    assert load_cached_wheels(cache, manifest) == wheels
    (cache / next(iter(wheels))).write_bytes(b"changed")
    with pytest.raises(ValueError, match="cached wheel digest differs"):
        load_cached_wheels(cache, manifest)


def test_cached_wheel_loader_refuses_missing_and_unsafe_paths(tmp_path):
    manifest, _, _, _, _ = fixture()
    cache = tmp_path / "private-wheels"
    cache.mkdir(mode=0o700)
    with pytest.raises(ValueError, match="cached wheel unavailable"):
        load_cached_wheels(cache, manifest)
    manifest["wheels"] = {"../escape.whl": next(iter(manifest["wheels"].values()))}
    with pytest.raises(ValueError, match="wheel identity differs"):
        load_cached_wheels(cache, manifest)


def test_cached_bundle_material_loads_exact_closure(tmp_path):
    cache, args = cached_fixture(tmp_path)
    assert load_cached_bundle_material(cache, args[0]) == args[1:]


def test_noncatalogue_user_directory_import_and_doctor(tmp_path):
    directory, manifest = user_directory(tmp_path)
    assert manifest["name"] not in {row["id"] for row in catalogue()["libraries"]}
    material = load_pinned_bundle_directory(directory)
    assert material[0] == manifest
    parent = "sha256:" + "b" * 64
    cache = tmp_path / "owner-cache"
    cache.mkdir(mode=0o700)
    ref, context, seal = prepare_pinned_bundle_directory(directory, cache, parent)
    assert ref.bundle_digest == validate_bundle(*material)
    assert context.parent.name == ref.bundle_digest[7:]
    assert context.name == parent[7:]
    assert seal == bundles._context_digest(context)
    assert (context / "source.tar.gz").read_bytes() == material[1]
    assert "pip check" in (context / "Dockerfile").read_text()

    cli = Path(__file__).resolve().parents[2] / "scripts/dev/library_bundle.py"
    doctor = subprocess.run(
        [sys.executable, str(cli), "doctor", str(directory)],
        check=True,
        capture_output=True,
        text=True,
    )
    observed = json.loads(doctor.stdout)
    assert observed["status"] == "PINNED_MATERIAL_VALIDATED"
    assert observed["bundle_ref"] == ref.to_dict()
    assert observed["dependency_status"] == "PENDING_OFFLINE_INSTALL_AND_PIP_CHECK"
    imported = subprocess.run(
        [
            sys.executable,
            str(cli),
            "import",
            str(directory),
            "--cache-root",
            str(cache),
            "--parent-image",
            parent,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    result = json.loads(imported.stdout)
    assert result["status"] == "OFFLINE_CONTEXT_PREPARED"
    assert result["bundle_ref"] == ref.to_dict()
    assert result["context"] == str(context)
    assert result["context_digest"] == seal
    assert result["image_status"] == "NOT_VERIFIED"


def test_owner_install_cli_uses_checked_gpu_profile_without_private_path_args(
    tmp_path, monkeypatch, capsys
):
    from scripts.dev import library_bundle as command

    directory, _ = user_directory(tmp_path)
    selected = bundle_ref(*load_pinned_bundle_directory(directory))
    campaigns = tmp_path / "campaigns"
    parent = object()
    adapter = object()
    calls = []
    monkeypatch.setattr(
        command,
        "EnvironmentSetup",
        lambda state_dir, onboarding: SimpleNamespace(
            profile=lambda: {
                "gpu_image": str(tmp_path / "checked-gpu-image.json"),
                "campaigns_root": str(campaigns),
            }
        ),
    )
    monkeypatch.setattr(command, "load_image_identity", lambda _: parent)
    monkeypatch.setattr(command, "gpu_image_backend", lambda _: "pytorch")
    monkeypatch.setattr(command, "_private_dir", lambda path: path)
    monkeypatch.setattr(command, "DockerCLI", lambda: adapter)

    def install(input_directory, cache_root, selected_parent, *, expected_bundle, cli):
        calls.append(
            (input_directory, cache_root, selected_parent, expected_bundle, cli)
        )
        return SimpleNamespace(bundle_ref=expected_bundle.to_dict())

    monkeypatch.setattr(command, "install_pinned_library_worker_image", install)
    assert command.main(["install", str(directory), "--state-dir", str(tmp_path)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result == {
        "status": "INSTALLED_VERIFIED",
        "bundle_ref": selected.to_dict(),
        "qualification": "DEVELOPMENT_ONLY",
    }
    assert calls == [
        (
            directory,
            campaigns / ".direct-development" / "library-cache",
            parent,
            selected,
            adapter,
        )
    ]

    monkeypatch.setattr(command, "gpu_image_backend", lambda _: "jax")
    assert command.main(["install", str(directory), "--state-dir", str(tmp_path)]) == 2
    assert len(calls) == 1

    monkeypatch.setattr(
        command,
        "EnvironmentSetup",
        lambda state_dir, onboarding: SimpleNamespace(
            profile=lambda: {"campaigns_root": str(campaigns)}
        ),
    )
    assert command.main(["install", str(directory), "--state-dir", str(tmp_path)]) == 2
    assert "compatible installed parent missing" in capsys.readouterr().err
    assert len(calls) == 1

    unsupported = type(selected)(
        selected.schema,
        selected.bundle_digest,
        selected.language,
        "python-cpu-py311",
        selected.environment_digest,
    )
    monkeypatch.setattr(command, "bundle_ref", lambda *args: unsupported)
    assert command.main(["install", str(directory), "--state-dir", str(tmp_path)]) == 2
    assert "no registered parent" in capsys.readouterr().err
    assert len(calls) == 1


def test_user_import_refuses_changed_wheel_before_preparing_context(tmp_path):
    directory, manifest = user_directory(tmp_path)
    wheel = directory / "wheels" / next(iter(manifest["wheels"]))
    wheel.write_bytes(wheel.read_bytes() + b"changed")
    cache = tmp_path / "owner-cache"
    cache.mkdir(mode=0o700)
    with pytest.raises(ValueError, match="wheel identity differs"):
        prepare_pinned_bundle_directory(directory, cache, "sha256:" + "b" * 64)
    assert list(cache.iterdir()) == []


def test_user_import_refuses_symlinked_input(tmp_path):
    directory, _ = user_directory(tmp_path)
    source = directory / "source.tar.gz"
    outside = tmp_path / "outside.tar.gz"
    outside.write_bytes(source.read_bytes())
    source.unlink()
    try:
        source.symlink_to(outside)
    except OSError:
        pytest.skip("host cannot create symlinks")
    with pytest.raises(ValueError, match="pinned bundle file unavailable"):
        load_pinned_bundle_directory(directory)


@pytest.mark.parametrize(
    "name",
    [
        "source.tar.gz",
        "requirements.txt",
        "LICENSE",
        "wheels/package-1-py3-none-any.whl",
    ],
)
def test_cached_bundle_material_refuses_each_changed_byte(tmp_path, name):
    cache, args = cached_fixture(tmp_path)
    target = cache / name
    target.write_bytes(target.read_bytes() + b"changed")
    with pytest.raises(ValueError):
        load_cached_bundle_material(cache, args[0])


def test_cached_bundle_material_refuses_missing_and_symlinked_source(tmp_path):
    cache, args = cached_fixture(tmp_path)
    source = cache / "source.tar.gz"
    source.unlink()
    with pytest.raises(ValueError, match="cached bundle material unavailable"):
        load_cached_bundle_material(cache, args[0])
    source.write_bytes(args[1])
    target = tmp_path / "outside-source.tar.gz"
    target.write_bytes(args[1])
    source.unlink()
    try:
        source.symlink_to(target)
    except OSError:
        pytest.skip("host cannot create symlinks")
    with pytest.raises(ValueError, match="cached bundle material unavailable"):
        load_cached_bundle_material(cache, args[0])
    source.unlink()
    source.write_bytes(args[1])
    wheel_name, wheel_body = next(iter(args[2].items()))
    wheel = cache / "wheels" / wheel_name
    wheel.unlink()
    outside_wheel = tmp_path / "outside-wheel.whl"
    outside_wheel.write_bytes(wheel_body)
    wheel.symlink_to(outside_wheel)
    with pytest.raises(ValueError, match="cached wheel unavailable"):
        load_cached_bundle_material(cache, args[0])


@pytest.mark.parametrize("opened", ["root", "wheels", "other-owner"])
def test_cached_bundle_material_refuses_unsafe_posix_cache(
    tmp_path, opened, monkeypatch
):
    if os.name != "posix":
        pytest.skip("owner/mode enforcement is POSIX")
    cache, args = cached_fixture(tmp_path)
    if opened == "other-owner":
        monkeypatch.setattr(bundles.os, "getuid", lambda: cache.stat().st_uid + 1)
    else:
        (cache if opened == "root" else cache / "wheels").chmod(0o755)
    with pytest.raises(ValueError, match="private operator .* cache required"):
        load_cached_bundle_material(cache, args[0])


@pytest.mark.parametrize("transitive_version", [None, "1.0"])
def test_installed_environment_check_refuses_missing_or_incompatible_transitive(
    tmp_path, transitive_version
):
    """A closed no-deps overlay still fails when its parent lacks its requirements."""
    if importlib.util.find_spec("pip") is None:
        pytest.skip("pip check unavailable on this host")
    overlay = tmp_path / "carbon_overlay_closure_probe-1.0.dist-info"
    overlay.mkdir()
    (overlay / "METADATA").write_text(
        "Metadata-Version: 2.1\n"
        "Name: carbon-overlay-closure-probe\n"
        "Version: 1.0\n"
        "Requires-Dist: carbon-parent-closure-probe>=2\n",
        encoding="utf-8",
    )
    if transitive_version is not None:
        parent = (
            tmp_path / f"carbon_parent_closure_probe-{transitive_version}.dist-info"
        )
        parent.mkdir()
        (parent / "METADATA").write_text(
            "Metadata-Version: 2.1\n"
            "Name: carbon-parent-closure-probe\n"
            f"Version: {transitive_version}\n",
            encoding="utf-8",
        )
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(tmp_path)
    result = subprocess.run(
        [sys.executable, "-m", "pip", "check"],
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode != 0
    assert "carbon-overlay-closure-probe" in result.stdout.lower()
    assert "carbon-parent-closure-probe" in result.stdout.lower()


@pytest.mark.parametrize("member", ["../escape", "/absolute", "source/../../escape"])
def test_source_path_escape_refused(member):
    manifest, _, wheels, lock, license_text = fixture()
    source = archive(member)
    manifest["source_sha256"] = sha(source)
    manifest["source_bytes"] = len(source)
    with pytest.raises(ValueError, match="unsafe source"):
        validate_bundle(manifest, source, wheels, lock, license_text)


def test_source_link_and_incomplete_wheel_closure_refused():
    manifest, _, wheels, lock, license_text = fixture()
    source = archive(symlink=True)
    manifest["source_sha256"] = sha(source)
    manifest["source_bytes"] = len(source)
    with pytest.raises(ValueError, match="unsafe source"):
        validate_bundle(manifest, source, wheels, lock, license_text)
    manifest, source, wheels, lock, license_text = fixture()
    with pytest.raises(ValueError, match="complete wheel closure"):
        validate_bundle(manifest, source, {}, lock, license_text)


def test_root_license_allows_bounded_nested_component_license():
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz") as tar:
        for name, body in (
            ("source/LICENSE", b"MIT\n"),
            ("source/component/LICENSE", b"component terms\n"),
            ("source/component/model.py", b"VALUE = 1\n"),
        ):
            member = tarfile.TarInfo(name)
            member.size = len(body)
            tar.addfile(member, io.BytesIO(body))
    assert bundles._safe_source_archive(output.getvalue(), license_text=b"MIT\n") == 3
    with pytest.raises(ValueError, match="source license bytes differ"):
        bundles._safe_source_archive(output.getvalue(), license_text=b"changed\n")


@pytest.mark.parametrize(
    "member",
    [
        "source/checkpoints/model.safetensors",
        "source/model_weights.npz",
        "source/assets/pytorch_model.bin",
        "source/models/weights.npz",
        "source/epoch-4.pth.tar",
        "source/assets/pytorch_model-00001-of-00002.bin",
        "source/checkpoints/model.pth",
    ],
)
def test_recognizable_pretrained_source_asset_refused(member):
    manifest, _, wheels, lock, license_text = fixture()
    source = archive(member)
    manifest["source_sha256"] = sha(source)
    manifest["source_bytes"] = len(source)
    with pytest.raises(ValueError, match="pretrained state asset in source"):
        validate_bundle(manifest, source, wheels, lock, license_text)


def test_declared_challenge_train_asset_is_not_source_material():
    manifest, _, wheels, lock, license_text = fixture()
    source = archive("source/challenge_train/inputs.npz")
    manifest["source_sha256"] = sha(source)
    manifest["source_bytes"] = len(source)
    with pytest.raises(ValueError, match="Challenge TRAIN asset in source"):
        validate_bundle(manifest, source, wheels, lock, license_text)


@pytest.mark.parametrize(
    "member",
    [
        "package/pretrained/epoch-4.ckpt",
        "package/adapter_model.bin",
        "package/model_state.npz",
        "package/challenge_train/inputs.npz",
        "package/pretrained/model.onnx",
    ],
)
def test_recognizable_state_or_train_in_wheel_refused(member):
    manifest, source, _, _, license_text = fixture()
    wheel = wheel_archive({"package/__init__.py": b"", member: b"asset"})
    name = "package-1-py3-none-any.whl"
    wheels = {name: wheel}
    lock = (
        b"package==1 --hash=sha256:"
        + hashlib.sha256(wheel).hexdigest().encode()
        + b"\n"
    )
    manifest["lock_sha256"] = sha(lock)
    manifest["environment_digest"] = _environment_digest(
        manifest["base_environment_digest"], sha(lock)
    )
    manifest["wheels"] = {name: sha(wheel)}
    with pytest.raises(
        ValueError, match="pretrained state asset|Challenge TRAIN asset"
    ):
        validate_bundle(manifest, source, wheels, lock, license_text)


def test_legitimate_source_and_dependency_assets_remain_usable():
    manifest, _, _, _, license_text = fixture()
    source = archive("source/assets/quadrature_weights.npz")
    wheel = wheel_archive(
        {
            "package/__init__.py": b"",
            "package/tests/data/numeric-reference.npz": b"fixture",
            "package/tests/data/legacy.pickle": b"fixture",
            "package/graphs/architecture.tflite": b"graph",
            "package/namespace.pth": b"package\n",
        }
    )
    name = "package-1-py3-none-any.whl"
    wheels = {name: wheel}
    lock = (
        b"package==1 --hash=sha256:"
        + hashlib.sha256(wheel).hexdigest().encode()
        + b"\n"
    )
    manifest["source_sha256"] = sha(source)
    manifest["source_bytes"] = len(source)
    manifest["lock_sha256"] = sha(lock)
    manifest["environment_digest"] = _environment_digest(
        manifest["base_environment_digest"], sha(lock)
    )
    manifest["wheels"] = {name: sha(wheel)}
    assert validate_bundle(manifest, source, wheels, lock, license_text).startswith(
        "sha256:"
    )


@pytest.mark.parametrize(
    "member",
    ["source/architecture.onnx", "source/architecture.pt", "source/architecture.pth"],
)
def test_graph_asset_extension_alone_is_not_pretrained_state(member):
    manifest, _, wheels, lock, license_text = fixture()
    source = archive(member)
    manifest["source_sha256"] = sha(source)
    manifest["source_bytes"] = len(source)
    assert validate_bundle(manifest, source, wheels, lock, license_text).startswith(
        "sha256:"
    )


def test_nonzip_wheel_cannot_skip_asset_inventory():
    manifest, source, _, _, license_text = fixture()
    body = b"not a wheel archive"
    name = "package-1-py3-none-any.whl"
    wheels = {name: body}
    lock = (
        b"package==1 --hash=sha256:" + hashlib.sha256(body).hexdigest().encode() + b"\n"
    )
    manifest["lock_sha256"] = sha(lock)
    manifest["environment_digest"] = _environment_digest(
        manifest["base_environment_digest"], sha(lock)
    )
    manifest["wheels"] = {name: sha(body)}
    with pytest.raises(ValueError, match="invalid wheel archive"):
        validate_bundle(manifest, source, wheels, lock, license_text)


def test_wheel_member_bound_precedes_zip_metadata_parse():
    body = bytearray(wheel_archive())
    trailer = body.rfind(b"PK\x05\x06")
    assert trailer >= 0
    struct.pack_into(
        "<HH", body, trailer + 8, bundles.MAX_MEMBERS + 1, bundles.MAX_MEMBERS + 1
    )
    with pytest.raises(ValueError, match="bounded wheel directory required"):
        bundles._safe_wheel_assets(bytes(body))


def test_source_rejects_multiple_roots_and_nested_only_license():
    for members, error in (
        ((("source/LICENSE", b"MIT\n"), ("other/model.py", b"x")), "single-root"),
        ((("source/component/LICENSE", b"MIT\n"),), "source license bytes differ"),
    ):
        output = io.BytesIO()
        with tarfile.open(fileobj=output, mode="w:gz") as tar:
            for name, body in members:
                member = tarfile.TarInfo(name)
                member.size = len(body)
                tar.addfile(member, io.BytesIO(body))
        with pytest.raises(ValueError, match=error):
            bundles._safe_source_archive(output.getvalue(), license_text=b"MIT\n")


def test_member_limit_refuses_before_unbounded_archive_enumeration():
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz") as tar:
        for index in range(4097):
            tar.addfile(tarfile.TarInfo(f"source/{index}"))
    manifest, _, wheels, lock, license_text = fixture()
    source = output.getvalue()
    manifest["source_sha256"] = sha(source)
    manifest["source_bytes"] = len(source)
    with pytest.raises(ValueError, match="bounded source members"):
        validate_bundle(manifest, source, wheels, lock, license_text)


def test_symlink_cache_root_refused(tmp_path):
    real = tmp_path / "private"
    real.mkdir()
    alias = tmp_path / "alias"
    try:
        alias.symlink_to(real, target_is_directory=True)
    except OSError:
        pytest.skip("host cannot create directory symlinks")
    with pytest.raises(ValueError, match="private operator-owned"):
        prepare_offline_context(alias, *fixture(), "sha256:" + "b" * 64)


@pytest.mark.skipif(os.name != "posix", reason="POSIX cache ownership check")
def test_group_readable_cache_root_refused(tmp_path):
    tmp_path.chmod(0o755)
    with pytest.raises(ValueError, match="private operator-owned"):
        prepare_offline_context(tmp_path, *fixture(), "sha256:" + "b" * 64)


def test_profile_lock_license_and_wheel_identity_refuse():
    manifest, source, wheels, lock, license_text = fixture()
    for changed in (
        {"runtime_profile_id": "unknown"},
        {"source_commit": "main"},
        {"base_environment_digest": "sha256:" + "d" * 64},
    ):
        with pytest.raises(ValueError):
            validate_bundle({**manifest, **changed}, source, wheels, lock, license_text)
    for values in (
        (manifest, source, wheels, b"changed", license_text),
        (manifest, source, wheels, lock, b"changed"),
        (manifest, source, {next(iter(wheels)): b"changed"}, lock, license_text),
    ):
        with pytest.raises(ValueError):
            validate_bundle(*values)


@pytest.mark.parametrize(
    "lock",
    [
        b"package==1 --hash=sha256:" + b"0" * 64 + b" # wheel hash elsewhere\n",
        b"package==1 --hash=sha256:"
        + b"0" * 64
        + b"\nmissing==1 --hash=sha256:"
        + b"1" * 64
        + b"\n",
        b"https://example.com/package.whl\n",
        b"package>=1\n",
    ],
)
def test_lock_cannot_hide_hash_or_omit_locked_wheel(lock):
    manifest, source, wheels, _, license_text = fixture()
    manifest["lock_sha256"] = sha(lock)
    manifest["environment_digest"] = _environment_digest(
        manifest["base_environment_digest"], sha(lock)
    )
    with pytest.raises(ValueError):
        validate_bundle(manifest, source, wheels, lock, license_text)


def test_controller_input_bounds_precede_hashing_and_cache_writes(
    monkeypatch, tmp_path
):
    manifest, source, wheels, lock, license_text = fixture()
    parent = "sha256:" + "b" * 64
    monkeypatch.setattr(bundles, "MAX_LOCK_BYTES", len(lock) - 1)
    with pytest.raises(ValueError, match="bounded wheel lock"):
        prepare_offline_context(
            tmp_path, manifest, source, wheels, lock, license_text, parent
        )
    monkeypatch.setattr(bundles, "MAX_LOCK_BYTES", len(lock))
    monkeypatch.setattr(bundles, "MAX_LICENSE_BYTES", len(license_text) - 1)
    with pytest.raises(ValueError, match="bounded license"):
        validate_bundle(manifest, source, wheels, lock, license_text)
    monkeypatch.setattr(bundles, "MAX_LICENSE_BYTES", len(license_text))
    monkeypatch.setattr(bundles, "MAX_WHEEL_BYTES", 1)
    with pytest.raises(ValueError, match="bounded wheel item"):
        validate_bundle(manifest, source, wheels, lock, license_text)
    monkeypatch.setattr(bundles, "MAX_WHEEL_BYTES", 1024)
    monkeypatch.setattr(
        bundles, "MAX_WHEEL_TOTAL_BYTES", len(next(iter(wheels.values()))) - 1
    )
    with pytest.raises(ValueError, match="bounded wheel set"):
        validate_bundle(manifest, source, wheels, lock, license_text)
    assert not list(tmp_path.iterdir())


def test_compressed_pax_metadata_refused_before_tar_parsing(monkeypatch):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz", format=tarfile.PAX_FORMAT) as tar:
        member = tarfile.TarInfo("source/file")
        member.pax_headers = {"comment": "x" * 10000}
        member.size = 1
        tar.addfile(member, io.BytesIO(b"x"))
    monkeypatch.setattr(bundles, "MAX_RAW_TAR_BYTES", 1024)
    with pytest.raises(ValueError, match="bounded decompressed"):
        bundles._safe_source_archive(output.getvalue())


class FakeLocalDocker:
    def __init__(
        self,
        parent,
        bundle,
        *,
        missing_uv=False,
        missing_parent=False,
        tag_mismatch=False,
        uv_digest_mismatch=False,
    ):
        self.parent, self.bundle = parent, bundle
        self.missing_uv, self.missing_parent, self.tag_mismatch = (
            missing_uv,
            missing_parent,
            tag_mismatch,
        )
        self.uv_digest_mismatch = uv_digest_mismatch
        self.uv_id = "sha256:" + "d" * 64
        self.built_id = "sha256:" + "e" * 64
        self.tags = {}
        self.calls = []

    def json(self, args):
        ref = args[2]
        if ref == self.parent and not self.missing_parent:
            return {"Id": self.parent, "RootFS": {"Layers": ["base-layer"]}}
        if ref == UV_IMAGE and not self.missing_uv:
            repository = UV_IMAGE.partition("@")[0].rsplit(":", 1)[0]
            digest = (
                ("sha256:" + "0" * 64)
                if self.uv_digest_mismatch
                else UV_IMAGE.partition("@")[2]
            )
            return {"Id": self.uv_id, "RepoDigests": [repository + "@" + digest]}
        if ref in self.tags:
            image_id = self.tags[ref]
            return {"Id": "sha256:" + "f" * 64 if self.tag_mismatch else image_id}
        if ref == self.built_id:
            return {
                "Id": self.built_id,
                "Os": "linux",
                "Architecture": "amd64",
                "Config": {
                    "User": "65532:65532",
                    "Labels": {
                        "org.opencontainers.image.carbon.development.library-bundle": self.bundle,
                        "org.opencontainers.image.carbon.development.parent": self.parent,
                    },
                },
                "RootFS": {"Layers": ["base-layer", "new-layer"]},
            }
        raise ValueError("image absent")

    def run(self, args, **kwargs):
        self.calls.append(args)
        if args[0] == "tag":
            self.tags[args[2]] = args[1]
            return SimpleNamespace(stdout=b"")
        if args[0] == "build":
            return SimpleNamespace(stdout=self.built_id.encode())
        raise AssertionError(args)


def test_offline_builder_preflights_both_local_stages_and_final_layers(tmp_path):
    args = fixture()
    parent = "sha256:" + "b" * 64
    context, bundle, seal = prepare_offline_context(tmp_path, *args, parent)
    dockerfile = (context / "Dockerfile").read_text(encoding="utf-8")
    assert "TMPDIR=/tmp /tmp/uv --no-cache pip install" in dockerfile
    assert "TMPDIR=/tmp /tmp/uv pip check" in dockerfile
    assert "chmod -R" not in dockerfile
    assert "ENV TMPDIR" not in dockerfile
    cli = FakeLocalDocker(parent, bundle)
    assert build_offline_bundle(context, bundle, parent, seal, cli=cli) == cli.built_id
    assert [call[0] for call in cli.calls] == ["tag", "tag", "build"]
    assert cli.calls[-1][1:4] == [
        "--network=none",
        "--pull=false",
        "--platform=linux/amd64",
    ]


def test_provisioning_accepts_uncatalogued_closure_and_returns_exact_local_pins(
    tmp_path,
):
    manifest, source, wheels, lock, license_text = fixture()
    manifest["name"] = "uncatalogued-public-library"
    assert manifest["name"] not in {row["id"] for row in catalogue()["libraries"]}
    parent = "sha256:" + "b" * 64
    bundle_digest = validate_bundle(manifest, source, wheels, lock, license_text)
    cli = FakeLocalDocker(parent, bundle_digest)

    result = provision_offline_bundle(
        tmp_path,
        bundle_ref(manifest, source, wheels, lock, license_text).to_dict(),
        manifest,
        source,
        wheels,
        lock,
        license_text,
        parent,
        cli=cli,
    )

    assert result.bundle.bundle_digest == bundle_digest
    assert result.bundle.environment_digest == manifest["environment_digest"]
    assert result.parent_image == parent
    assert result.context == tmp_path / bundle_digest[7:] / parent[7:]
    assert bundles._context_digest(result.context) == result.context_digest
    assert result.image_id == cli.built_id
    assert [call[0] for call in cli.calls] == ["tag", "tag", "build"]


def test_provisioning_refuses_changed_closure_before_local_image_activity(tmp_path):
    manifest, source, wheels, lock, license_text = fixture()
    parent = "sha256:" + "b" * 64
    cli = FakeLocalDocker(parent, validate_bundle(*fixture()))
    with pytest.raises(ValueError, match="lock digest differs"):
        provision_offline_bundle(
            tmp_path,
            bundle_ref(manifest, source, wheels, lock, license_text).to_dict(),
            manifest,
            source,
            wheels,
            lock + b"changed",
            license_text,
            parent,
            cli=cli,
        )
    assert cli.calls == []


def test_provisioning_refuses_a_different_recipe_bundle_before_build(tmp_path):
    manifest, source, wheels, lock, license_text = fixture()
    parent = "sha256:" + "b" * 64
    cli = FakeLocalDocker(parent, validate_bundle(*fixture()))
    wrong_ref = {
        **bundle_ref(manifest, source, wheels, lock, license_text).to_dict(),
        "bundle_digest": sha(b"another recipe"),
    }
    with pytest.raises(ValueError, match="recipe bundle reference differs"):
        provision_offline_bundle(
            tmp_path,
            wrong_ref,
            manifest,
            source,
            wheels,
            lock,
            license_text,
            parent,
            cli=cli,
        )
    assert cli.calls == []


@pytest.mark.parametrize(
    "missing_uv,missing_parent,tag_mismatch",
    [(True, False, False), (False, True, False), (False, False, True)],
)
def test_offline_builder_refuses_missing_or_changed_stage_before_build(
    tmp_path, missing_uv, missing_parent, tag_mismatch
):
    args = fixture()
    parent = "sha256:" + "b" * 64
    context, bundle, seal = prepare_offline_context(tmp_path, *args, parent)
    cli = FakeLocalDocker(
        parent,
        bundle,
        missing_uv=missing_uv,
        missing_parent=missing_parent,
        tag_mismatch=tag_mismatch,
    )
    with pytest.raises(ValueError):
        build_offline_bundle(context, bundle, parent, seal, cli=cli)
    assert not any(call[0] == "build" for call in cli.calls)


def test_offline_builder_refuses_wrong_canonical_uv_digest_before_build(tmp_path):
    args = fixture()
    parent = "sha256:" + "b" * 64
    context, bundle, seal = prepare_offline_context(tmp_path, *args, parent)
    cli = FakeLocalDocker(parent, bundle, uv_digest_mismatch=True)
    with pytest.raises(ValueError, match="pinned local uv image differs"):
        build_offline_bundle(context, bundle, parent, seal, cli=cli)
    assert not any(call[0] == "build" for call in cli.calls)


def test_offline_builder_refuses_registry_from_context(tmp_path):
    args = fixture()
    parent = "sha256:" + "b" * 64
    context, bundle, seal = prepare_offline_context(tmp_path, *args, parent)
    dockerfile = context / "Dockerfile"
    dockerfile.write_text(
        dockerfile.read_text().replace(
            "FROM carbon-library-uv:", "FROM docker.io/unsafe:"
        )
    )
    cli = FakeLocalDocker(parent, bundle)
    with pytest.raises(ValueError, match="sealed bundle context"):
        build_offline_bundle(context, bundle, parent, seal, cli=cli)
    assert cli.calls == []


@pytest.mark.parametrize(
    "path",
    [
        "Dockerfile",
        "install-source.py",
        "source.tar.gz",
        "requirements.txt",
        "LICENSE",
        "wheels/package-1-py3-none-any.whl",
    ],
)
def test_offline_builder_refuses_any_mutated_context_byte_before_build(tmp_path, path):
    args = fixture()
    parent = "sha256:" + "b" * 64
    context, bundle, seal = prepare_offline_context(tmp_path, *args, parent)
    target = context / path
    target.write_bytes(target.read_bytes() + b"tampered")
    cli = FakeLocalDocker(parent, bundle)
    with pytest.raises(ValueError, match="sealed bundle context"):
        build_offline_bundle(context, bundle, parent, seal, cli=cli)
    assert cli.calls == []


def test_offline_builder_refuses_added_or_missing_context_file(tmp_path):
    args = fixture()
    parent = "sha256:" + "b" * 64
    context, bundle, seal = prepare_offline_context(tmp_path, *args, parent)
    extra = context / "extra.py"
    extra.write_bytes(b"print('untrusted')")
    cli = FakeLocalDocker(parent, bundle)
    with pytest.raises(ValueError):
        build_offline_bundle(context, bundle, parent, seal, cli=cli)
    extra.unlink()
    (context / "install-source.py").unlink()
    with pytest.raises(ValueError):
        build_offline_bundle(context, bundle, parent, seal, cli=cli)
    assert cli.calls == []
