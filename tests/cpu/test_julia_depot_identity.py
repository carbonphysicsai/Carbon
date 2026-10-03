"""The precompiled Julia depot's identity depends on Julia inputs only.

The depot is reused across commits only because its identity cannot see the
Carbon source tree. That property is easy to lose - one convenient argument,
one extra file hashed - and invisible when lost: the cache simply never hits
again. These tests pin it three ways: by what the digest reads, by what it
accepts, and by how the recipes start.
"""

from __future__ import annotations

import inspect
import json
import re
import shutil
import sys
import tomllib
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace

import pytest

from carbon.development_session import julia_analysis as julia
from carbon.development_session import julia_depot as depot
from carbon.development_session import julia_depot_build as build
from carbon.development_session.profile import canonical, digest
from carbon.development_session.research_image import ResearchImageIdentity

JULIA_INPUTS = {
    *(
        (depot.ENVIRONMENT_ROOT / name / file).resolve()
        for name in depot.ENVIRONMENTS
        for file in ("Project.toml", "Manifest.toml")
    ),
    *(
        (depot.ENVIRONMENT_ROOT / name / "LocalPreferences.toml").resolve()
        for name in depot.CUDA_ENVIRONMENTS
    ),
    Path(depot.__file__).resolve(),
}
CUDA_RUNTIME_JLL = "76a88914-d11a-5bdc-97e0-2f5a05c973a2"
CUDA_DRIVER_JLL = "4ee394cb-3365-5eb0-8335-949819d2adfc"

_opened = None


def _audit(event, args):
    if _opened is not None and event == "open" and isinstance(args[0], (str, Path)):
        _opened.add(Path(args[0]).resolve())


sys.addaudithook(_audit)


def test_the_depot_digest_reads_only_julia_inputs():
    global _opened
    _opened = set()
    try:
        depot.depot_digest()
        seen = set(_opened)
    finally:
        _opened = None
    # Specimen: the hook does see the reads it is looking for.
    assert (depot.ENVIRONMENT_ROOT / "pde" / "Manifest.toml").resolve() in seen
    assert seen == JULIA_INPUTS


def test_the_depot_document_accepts_nothing_a_caller_holds():
    assert inspect.signature(depot.depot_document).parameters == {}
    assert inspect.signature(depot.depot_digest).parameters == {}
    assert set(depot.depot_document()) == {
        "schema",
        "base_image",
        "julia_version",
        "julia_archive",
        "cpu_target",
        "environments",
        "builder",
        "package_artifacts",
    }
    # The builder named is the depot module, never the composer or the source.
    assert depot.depot_document()["builder"] == digest(
        Path(depot.__file__).read_bytes()
    )


def test_a_julia_input_changes_the_depot_and_an_identical_copy_does_not(
    tmp_path, monkeypatch
):
    before = depot.depot_digest()
    copy = tmp_path / "environments"
    shutil.copytree(depot.ENVIRONMENT_ROOT, copy)
    monkeypatch.setattr(depot, "ENVIRONMENT_ROOT", copy)
    assert depot.depot_digest() == before
    manifest = copy / "current" / "Manifest.toml"
    manifest.write_bytes(manifest.read_bytes() + b"\n")
    assert depot.depot_digest() != before


def test_preferences_are_a_depot_input(tmp_path, monkeypatch):
    """LocalPreferences.toml decides which CUDA toolkit is installed and how
    packages compile, so changing, removing or adding one names another depot."""
    before = depot.depot_digest()
    copy = tmp_path / "environments"
    shutil.copytree(depot.ENVIRONMENT_ROOT, copy)
    monkeypatch.setattr(depot, "ENVIRONMENT_ROOT", copy)
    preferences = copy / "current" / "LocalPreferences.toml"
    preferences.write_bytes(preferences.read_bytes().replace(b'"13.0"', b'"12.9"'))
    changed = depot.depot_digest()
    assert changed != before
    preferences.unlink()
    assert depot.depot_digest() not in (before, changed)
    (copy / "pde" / "LocalPreferences.toml").write_bytes(b"")
    assert depot.environment_preferences("pde") == b""
    assert depot.depot_document()["environments"]["pde"]["preferences"] is not None


def test_the_cuda_environment_fixes_its_toolkit_and_names_its_jlls():
    """The build host has no GPU and a run has no network, so the toolkit is a
    committed preference. Julia reads a package's preferences only when the
    project names it, so both CUDA JLLs are extras of the project: without
    that the preferences are silently ignored and no toolkit is installed (the
    first rehearsal, 2026-10-03, came out `cuda+none`)."""
    assert depot.CUDA_ENVIRONMENTS == ("current",)
    for name in depot.ENVIRONMENTS:
        project = tomllib.loads(depot.environment_files(name)[0].decode())
        preferences = depot.environment_preferences(name)
        if name not in depot.CUDA_ENVIRONMENTS:
            assert "CUDA" not in project["deps"] and preferences is None
            continue
        assert project["deps"]["CUDA"] == "052768ef-5323-5732-b1bb-66c8b64840ba"
        assert project["extras"] == {
            "CUDA_Driver_jll": CUDA_DRIVER_JLL,
            "CUDA_Runtime_jll": CUDA_RUNTIME_JLL,
        }
        fixed = tomllib.loads(preferences.decode())
        assert fixed == {
            "CUDA_Runtime_jll": {"version": "13.0", "local": False},
            "CUDA_Driver_jll": {"compat": False},
        }
        # The manifest pins the JLLs those preferences address.
        manifest = tomllib.loads(depot.environment_files(name)[1].decode())
        assert manifest["deps"]["CUDA_Runtime_jll"][0]["uuid"] == CUDA_RUNTIME_JLL
        assert manifest["deps"]["CUDA_Driver_jll"][0]["uuid"] == CUDA_DRIVER_JLL


def test_the_recipes_install_one_toolkit_and_keep_the_device_runtime():
    fetch = depot.fetch_recipe("b")
    # The preferences are in place before anything is installed.
    assert fetch.index("current/LocalPreferences.toml") < fetch.index("Pkg.instantiate")
    assert "pde/LocalPreferences.toml" not in fetch
    # The lazy sweep leaves CUDA-tagged JLLs to their own selection hook.
    assert "select_artifacts.jl" in depot.LAZY_ARTIFACTS
    assert 'haskey(entry, "cuda")' in depot.LAZY_ARTIFACTS
    compile_recipe = depot.precompile_recipe("b", "p", "f")
    runtime = f"scratchspaces/{depot.GPUCOMPILER_UUID}"
    assert compile_recipe.index("Pkg.precompile") < compile_recipe.index(
        "CUDA.precompile_runtime()"
    )
    # Only GPUCompiler's compiled runtime survives, and an empty one fails the
    # build rather than shipping a depot that recompiles on every GPU run.
    assert f"! -name {depot.GPUCOMPILER_UUID}" in compile_recipe
    assert f"ls /opt/carbon-julia-analysis/depot/{runtime}/compiled/*/*/runtime_*.bc" in (
        compile_recipe
    )
    assert "rm -rf /opt/carbon-julia-analysis/depot/logs" in compile_recipe


def test_the_parent_names_the_composed_runtime_but_never_the_depot():
    parents = [
        ResearchImageIdentity("sha256:" + c * 64, "sha256:" + "b" * 64, "sha256:" + d)
        for c, d in (("a", "c" * 64), ("e", "f" * 64))
    ]
    built = build.JuliaDepotIdentity(
        "sha256:" + "1" * 64, depot.depot_digest(), "sha256:" + "2" * 64
    )
    composed = [
        digest(canonical(julia.runtime_document_v2(parent, built)))
        for parent in parents
    ]
    # Both identities are recorded: the parent is still a fact about what ran.
    assert composed[0] != composed[1]
    for parent in parents:
        document = julia.runtime_document_v2(parent, built)
        assert document["parent_image"] == parent.image_id
        assert document["depot_digest"] == depot.depot_digest()
    assert depot.depot_digest() == built.depot_digest


def test_depot_recipes_never_start_from_a_carbon_image():
    def sources(recipe):
        return [
            line.split()[1] for line in recipe.splitlines() if line.startswith("FROM ")
        ]

    assert sources(depot.base_recipe()) == [depot.BASE_IMAGE]
    assert sources(depot.fetch_recipe("base-tag")) == ["base-tag"]
    assert sources(depot.precompile_recipe("base-tag", "packages-tag", "sha256:x")) == [
        "packages-tag",
        "base-tag",
    ]
    for recipe in (
        depot.base_recipe(),
        depot.fetch_recipe("b"),
        depot.precompile_recipe("b", "p", "f"),
    ):
        assert "carbon-worker" not in recipe and "carbon-authored" not in recipe
    # Specimen: the composer does start from the Carbon parent.
    assert "carbon-authored-julia-parent" in inspect.getsource(
        julia.build_julia_analysis_image
    )


class FakeDocker:
    """Records builds; inspects return what the recorded builds produced."""

    def __init__(self):
        self.builds = []
        self.images = {}

    def run(self, arguments, *, timeout=30, accepted=(0,)):
        if arguments[0] == "build":
            recipe = (Path(arguments[-1]) / "Dockerfile").read_text()
            image = "sha256:" + digest(recipe.encode())[7:]
            labels = {}
            if depot.DEPOT_LABEL in recipe:
                labels = {
                    depot.DEPOT_LABEL: depot.depot_digest(),
                    depot.VERSION_LABEL: depot.VERSION,
                    depot.ARCHIVE_LABEL: depot.ARCHIVE,
                }
            self.images[image] = labels
            self.builds.append(recipe)
            return SimpleNamespace(stdout=image.encode())
        if arguments[0] == "tag":
            self.images[arguments[2]] = self.images[arguments[1]]
            self.images.setdefault("ids", {})[arguments[2]] = arguments[1]
        return SimpleNamespace(stdout=b"")

    def json(self, arguments, *, timeout=30):
        name = arguments[2]
        image = self.images.get("ids", {}).get(name, name)
        if image not in self.images:
            raise ValueError("no such image")
        return {
            "Id": image,
            "Os": "linux",
            "Architecture": "amd64",
            "Config": {"Labels": self.images[image]},
        }


@pytest.fixture
def docker(monkeypatch):
    monkeypatch.setattr(build, "tree_digest", lambda cli, image, path: "sha256:tree")
    return FakeDocker()


def test_a_verified_depot_is_reused_and_nothing_is_compiled(tmp_path, docker):
    root = tmp_path / "depot"
    first, how = build.build_depot(root, docker)
    assert how == "built"
    assert len(docker.builds) == 3
    assert "Pkg.precompile" in docker.builds[-1]
    # The fetch context carries each environment's preferences, byte for byte.
    fetch_context = build.depot_manifest(root).parent / "fetch-context"
    for name in depot.ENVIRONMENTS:
        path = fetch_context / name / "LocalPreferences.toml"
        expected = depot.environment_preferences(name)
        assert (path.read_bytes() if path.exists() else None) == expected
    again, how = build.build_depot(root, docker)
    assert how == "reused" and again == first
    assert len(docker.builds) == 3


def test_a_depot_that_fails_verification_is_rebuilt_never_served(tmp_path, docker):
    root = tmp_path / "depot"
    first, _ = build.build_depot(root, docker)
    # Relabelled after it was recorded: the record no longer verifies.
    docker.images[first.image_id] = {depot.DEPOT_LABEL: "sha256:" + "0" * 64}
    rebuilt, how = build.build_depot(root, docker)
    assert how == "built"
    assert len(docker.builds) == 6
    assert json.loads(build.depot_manifest(root).read_bytes())["image_id"] == (
        rebuilt.image_id
    )
    # And a missing image is the same: a cold rebuild, not a served record.
    del docker.images[rebuilt.image_id]
    _, how = build.build_depot(root, docker)
    assert how == "built"


def test_a_changed_julia_input_names_a_different_depot(tmp_path, docker, monkeypatch):
    root = tmp_path / "depot"
    first, _ = build.build_depot(root, docker)
    copy = tmp_path / "environments"
    shutil.copytree(depot.ENVIRONMENT_ROOT, copy)
    (copy / "pde" / "Project.toml").write_bytes(
        (copy / "pde" / "Project.toml").read_bytes() + b"\n"
    )
    monkeypatch.setattr(depot, "ENVIRONMENT_ROOT", copy)
    second, how = build.build_depot(root, docker)
    assert how == "built"
    assert second.depot_digest != first.depot_digest
    # The old depot is not verified against the new inputs.
    with pytest.raises(ValueError, match="inputs differ"):
        build.verify_depot(first, docker)


# A real v1 record, written by a host build before the depot split, and the
# runtime material written beside it.
HISTORICAL_V1 = {
    "image_id": "sha256:1195576748b1ef934d4794388fba3e892662dbcb302bd6c2dc1b9750f624fb14",
    "parent": {
        "image_id": "sha256:649a5b0bf98d9cc2e412a381a203615156e88093a2944a544d881e863d78a1ad",
        "parent_image": "sha256:0785dadff1d91a04eeb6890fec5e5f3c50c1aa11ad33b008da5b76eb615e0b25",
        "runtime_digest": "sha256:33f7eeefc2b65e0d08ca097cfda15a92d9b412eac047442ec832ca2967108171",
    },
    "runtime_digest": "sha256:5793a12586a8a2a3fd66c85e010fcb96471657923328538b37636d9e7bfab646",
    "schema": "carbon.authored-julia.analysis-image.v1",
}
HISTORICAL_V1_MATERIAL = {
    "builder": "sha256:6adbd8526ffbcbf851a8fff978727aa9fc57f65637127040f0caa6ce8138a0f1",
    "cpu_target": "generic;sandybridge,-xsaveopt,clone_all;haswell,-rdrnd,base(1)",
    "environments": {
        "current": {
            "bootstrap": "sha256:3b5b3c327828aedd2963b78731a3ca8d81aab590d9450bdf73bd2ddf03797e67",
            "manifest": "sha256:d5005f2fdc1d22881a6ecabf0c6a6999856097006366be82adc5e6e134c6f3dc",
            "project": "sha256:1cb4eccb7603dd343537cd184f4c4cd54f0dcccb9d60cd1a845ad6cb0e0dd88c",
        },
        "pde": {
            "bootstrap": "sha256:51538cd12e14486416b50f2aa1673e319d7ec26b3f503b0715c89b114100d1c0",
            "manifest": "sha256:5ad3925263b567931561a3e42dc1fb084a58509c731136ba7e2c0e3cb4526b26",
            "project": "sha256:04dda37d2b3137eda2ab21aaa71c691bd00cfabd41104b51b241ae27119082e5",
        },
    },
    "julia_archive": "sha256:8975da61c128a5e5ded3e719e868da8c8781deb7ad7913d37fb99be02a81904b",
    "julia_version": "1.13.0",
    "package_artifacts": "PINNED_BY_MANIFEST_CONTENT_HASHES",
    "parent_image": "sha256:649a5b0bf98d9cc2e412a381a203615156e88093a2944a544d881e863d78a1ad",
    "parent_runtime": "sha256:33f7eeefc2b65e0d08ca097cfda15a92d9b412eac047442ec832ca2967108171",
    "qualification": False,
    "schema": "carbon.authored-julia.analysis-image.v1",
    "scope": "PUBLIC_MINER_AUTHORED_JULIA_NO_EVALUATOR",
}
#: `authored_julia_scope` of HISTORICAL_V1 as main computed it before the split.
HISTORICAL_V1_SCOPE = (
    "sha256:8c1e56f0ef5dffe70260ff44058528a31384e34801a41e532b3dadf0ff262f72"
)


#: `bootstrap_for` digests on main immediately before the split.
BOOTSTRAPS_BEFORE_SPLIT = {
    "current": "sha256:72bfe5973012ae9e71e9b75f35ba544fe7a6d3b41d4faad7f3c0f73900903d34",
    "pde": "sha256:44fdd5a0ca81aecbbad30ec904abfd6d5659104962d425a6851d5d9d7b8bba6e",
}


def test_historical_v1_records_keep_their_meaning(tmp_path):
    path = tmp_path / "julia-analysis-image.json"
    path.write_bytes(canonical(HISTORICAL_V1))
    image = julia.load_julia_analysis_image(path)
    assert image.depot is None
    # Its runtime digest still means the v1 material recorded beside it.
    assert digest(canonical(HISTORICAL_V1_MATERIAL)) == image.runtime_digest
    assert HISTORICAL_V1_MATERIAL["schema"] == julia.SCHEMA
    # The scope a v1 campaign froze is the same bytes it was.
    assert digest(canonical(julia.authored_julia_scope(image))) == HISTORICAL_V1_SCOPE
    # The bootstraps moved module, not text: the same bytes main had before
    # the split (the historical record above predates a later bootstrap edit).
    assert {
        name: digest(julia.bootstrap_for(name).encode()) for name in julia.ENVIRONMENTS
    } == BOOTSTRAPS_BEFORE_SPLIT
    # And v1 is still checked against the v1 document, never the v2 one.
    assert julia._expected_runtime(image) == digest(
        canonical(julia.runtime_document(image.parent))
    )


def test_the_two_schemas_never_read_as_each_other(tmp_path):
    path = tmp_path / "julia-analysis-image.json"
    built = build.JuliaDepotIdentity(
        "sha256:" + "1" * 64, depot.depot_digest(), "sha256:" + "2" * 64
    )
    v2 = {
        **{k: v for k, v in HISTORICAL_V1.items() if k != "schema"},
        "schema": julia.SCHEMA_V2,
        "depot": asdict(built),
    }
    path.write_bytes(canonical(v2))
    image = julia.load_julia_analysis_image(path)
    assert image.depot == built
    scope = julia.authored_julia_scope(image)
    assert scope["schema"] == "carbon.authored-julia.scope.v3"
    assert scope["depot"] == built.depot_digest
    for record in (
        {**HISTORICAL_V1, "depot": asdict(built)},
        {k: v for k, v in v2.items() if k != "depot"},
        {**v2, "depot": {**asdict(built), "extra": 1}},
    ):
        path.write_bytes(canonical(record))
        with pytest.raises(ValueError, match="closed"):
            julia.load_julia_analysis_image(path)


def test_the_committed_lock_is_closed_and_pinned_by_digest(tmp_path):
    """The lock names a published depot by immutable digest. A lock for other
    Julia inputs is not an error - it reads as absent, and CI builds cold -
    but a malformed or tag-pinned lock is refused."""
    lock = build.read_lock()
    if lock is not None:
        assert lock["depot_digest"] == depot.depot_digest()
        assert lock["image"].startswith(build.REGISTRY + "@sha256:")
    base = {
        "schema": build.LOCK_SCHEMA,
        "depot_digest": depot.depot_digest(),
        "image": build.REGISTRY + "@sha256:" + "a" * 64,
    }
    path = tmp_path / "lock.json"
    path.write_text(json.dumps(base))
    assert build.read_lock(path) == base  # specimen: a good lock reads
    path.write_text(json.dumps({**base, "depot_digest": "sha256:" + "b" * 64}))
    assert build.read_lock(path) is None
    for bad in (
        {**base, "image": build.REGISTRY + ":latest"},
        {**base, "extra": 1},
    ):
        path.write_text(json.dumps(bad))
        with pytest.raises(ValueError):
            build.read_lock(path)


def test_every_image_is_recorded_under_its_own_schema(tmp_path):
    """image_record is the one way to write a Julia image record, and each
    schema round-trips; a v2 record never carries the v1 label, nor the
    reverse. (A service test that hand-wrote v1's label over a v2 image's
    fields is what this replaced; the closed loader refused it.)"""
    parent = ResearchImageIdentity(
        "sha256:" + "a" * 64, "sha256:" + "b" * 64, "sha256:" + "c" * 64
    )
    built = build.JuliaDepotIdentity(
        "sha256:" + "1" * 64, depot.depot_digest(), "sha256:" + "2" * 64
    )
    v1 = julia.JuliaResearchImageIdentity("sha256:" + "d" * 64, parent, "sha256:x")
    v2 = julia.JuliaResearchImageIdentity(
        "sha256:" + "e" * 64, parent, "sha256:y", built
    )
    path = tmp_path / "julia-analysis-image.json"
    for image, schema in ((v1, julia.SCHEMA), (v2, julia.SCHEMA_V2)):
        record = julia.image_record(image)
        assert record["schema"] == schema
        assert ("depot" in record) is (image.depot is not None)
        path.write_bytes(canonical(record))
        assert julia.load_julia_analysis_image(path) == image


#: A Julia image record written by hand: a schema label spread over asdict().
HAND_WRITTEN_RECORD = re.compile(
    r"schema\W{1,6}(?:julia\.)?(?:IMAGE_)?SCHEMA(?:_V2)?\W{1,6}\*\*asdict\("
)


def test_no_julia_image_record_is_written_by_hand():
    """image_record is the only writer. A hand-written record pairs one
    schema's label with the other's fields as soon as the identity grows a
    field - twice already, in code from two branches."""
    specimens = (
        'canonical({"schema": SCHEMA, **asdict(image)})',
        "canonical(dict(schema=julia.SCHEMA, **asdict(image)))",
        '{"schema": IMAGE_SCHEMA, **asdict(worker)}',
    )
    assert all(HAND_WRITTEN_RECORD.search(line) for line in specimens)
    root = Path(__file__).resolve().parents[2]
    offenders = [
        f"{path.relative_to(root)}:{number}"
        for folder in ("carbon", "scripts", "tests")
        for path in sorted((root / folder).rglob("*.py"))
        if path.name != "test_julia_depot_identity.py"
        for number, line in enumerate(path.read_text("utf-8").splitlines(), 1)
        if HAND_WRITTEN_RECORD.search(line)
    ]
    assert offenders == []
