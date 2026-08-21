"""A4 public-boundary, leakage, and installed-wheel acceptance tests."""

from __future__ import annotations

import base64
import copy
import dataclasses
import gc
import hashlib
import json
import os
import pickle
import shutil
import subprocess
import sys
import textwrap
import weakref
from pathlib import Path

import pytest

from carbon import seeding
from carbon.registry.model import ChallengeKey
from carbon.schema import dry_validate
from carbon.seeding import (
    BeaconConflictError,
    DerivedSeed,
    DeterministicFixtureProvider,
    EvaluationBinding,
    ExamCommitment,
    FixtureOfficialContext,
    FixtureOfficialEntropy,
    FixtureOfficialExamProjection,
    MockContext,
    MockEntropy,
    OfficialContext,
    OfficialEntropy,
    OfficialEntropyUnavailable,
    OfficialExamProjection,
    QualificationContext,
    QualificationEntropy,
    RoleKey,
    SeedDomain,
    SeedPin,
    acquire_fixture_official_context,
    acquire_official_context,
    create_fixture_official_exam_projection,
    create_official_exam_projection,
    derive_official_seed,
    serialize_exam_projection,
)
from carbon.seeding.commitment import _derive_private_exam_root
from carbon.seeding.model import _PrivateExamRoot

PUBLIC_PROJECTION_FIELDS = (
    "exam_commitment",
    "challenge_id",
    "challenge_version",
    "generator_version",
    "generator_digest",
    "scoring_version",
    "scoring_digest",
    "fixture",
)
OFFICIAL_MATERIAL = b"O" * 32
FIXTURE_MATERIAL = b"F" * 32
MOCK_MATERIAL = b"M" * 32
QUALIFICATION_MATERIAL = b"Q" * 32
BINDING_MATERIAL = b"E" * 32
GENERATOR_DIGEST = "sha256:" + "a" * 64
SCORING_DIGEST = "sha256:" + "b" * 64


class _Provider:
    def __init__(self, entropy: OfficialEntropy) -> None:
        self.entropy = entropy
        self.calls = 0

    def observe_entropy(self) -> OfficialEntropy:
        self.calls += 1
        return self.entropy


def _pin() -> SeedPin:
    return SeedPin(
        ChallengeKey("burgers_1d", "v1"),
        "v1",
        GENERATOR_DIGEST,
        "v1",
        SCORING_DIGEST,
        EvaluationBinding(BINDING_MATERIAL),
    )


def _official_context(pin: SeedPin | None = None) -> OfficialContext:
    provider = _Provider(OfficialEntropy(OFFICIAL_MATERIAL))
    return acquire_official_context(provider, pin or _pin())


def _fixture_context(pin: SeedPin | None = None) -> FixtureOfficialContext:
    provider = DeterministicFixtureProvider(FixtureOfficialEntropy(FIXTURE_MATERIAL))
    return acquire_fixture_official_context(provider, pin or _pin())


def _secret_forms(material: bytes) -> set[str]:
    forms = {
        material.hex(),
        base64.b64encode(material).decode("ascii"),
        base64.urlsafe_b64encode(material).decode("ascii"),
        str(int.from_bytes(material, "big")),
    }
    try:
        forms.add(material.decode("ascii"))
    except UnicodeDecodeError:
        pass
    return forms


def _assert_material_absent(text: str, *materials: bytes) -> None:
    for material in materials:
        for form in _secret_forms(material):
            assert form not in text


@pytest.mark.parametrize(
    "projection",
    (
        pytest.param(
            create_official_exam_projection(_official_context()),
            id="provider-origin",
        ),
        pytest.param(
            create_fixture_official_exam_projection(_fixture_context()),
            id="fixture-official",
        ),
    ),
)
def test_public_projection_and_serializer_have_exact_allow_list(
    projection: object,
) -> None:
    assert tuple(field.name for field in dataclasses.fields(projection)) == (
        PUBLIC_PROJECTION_FIELDS
    )
    assert not hasattr(projection, "__dict__")

    primitive = serialize_exam_projection(projection)

    assert tuple(primitive) == PUBLIC_PROJECTION_FIELDS
    assert all(type(key) is str for key in primitive)
    assert all(type(value) in {str, bool} for value in primitive.values())
    assert json.loads(json.dumps(primitive, sort_keys=True)) == primitive


@pytest.mark.parametrize(
    "projection",
    (
        pytest.param(
            create_official_exam_projection(_official_context()),
            id="provider-origin",
        ),
        pytest.param(
            create_fixture_official_exam_projection(_fixture_context()),
            id="fixture-official",
        ),
    ),
)
def test_no_private_object_is_reachable_from_public_projection_fields(
    projection: object,
) -> None:
    private_types = (
        OfficialEntropy,
        FixtureOfficialEntropy,
        MockEntropy,
        QualificationEntropy,
        EvaluationBinding,
        DerivedSeed,
        _PrivateExamRoot,
        SeedPin,
        OfficialContext,
        FixtureOfficialContext,
        MockContext,
        QualificationContext,
        DeterministicFixtureProvider,
    )
    public_values = tuple(
        getattr(projection, field.name) for field in dataclasses.fields(projection)
    )

    assert all(not isinstance(value, private_types) for value in public_values)
    assert all(not callable(value) for value in public_values)
    assert {type(value) for value in public_values} <= {str, bool, ExamCommitment}

    seen: set[int] = set()
    pending = [projection]
    while pending:
        value = pending.pop()
        if id(value) in seen:
            continue
        seen.add(id(value))
        if value is not projection:
            assert not isinstance(value, private_types)
        for referent in gc.get_referents(value):
            if isinstance(referent, (str, bytes, int, bool, type)):
                continue
            pending.append(referent)


def test_public_projection_omits_all_private_and_reconstruction_fields() -> None:
    context = _official_context()
    seed = derive_official_seed(
        context,
        SeedDomain.OFFICIAL_EVAL,
        RoleKey("generator"),
        7,
    )
    private_root = _derive_private_exam_root(context)
    primitive = serialize_exam_projection(create_official_exam_projection(context))
    encoded = json.dumps(primitive, sort_keys=True, separators=(",", ":"))

    assert set(primitive) == set(PUBLIC_PROJECTION_FIELDS)
    assert not {
        "entropy",
        "evaluation_binding",
        "private_exam_root",
        "derived_seed",
        "seed",
        "domain_seed",
        "role_key",
        "draw_index",
        "draw_id",
        "sample_id",
        "run_nonce",
        "block_hash",
        "hidden_order",
        "per_role_seed_hashes",
        "payload_hashes",
        "context",
        "provider",
        "emission_capable",
    }.intersection(primitive)
    _assert_material_absent(
        encoded,
        OFFICIAL_MATERIAL,
        BINDING_MATERIAL,
        seed.as_backend_bytes(),
        private_root._copy_bytes(),
    )


def test_secret_bearing_values_redact_and_reject_generic_serialization() -> None:
    pin = _pin()
    official = _official_context(pin)
    fixture = _fixture_context(pin)
    mock = MockContext(MockEntropy(MOCK_MATERIAL), pin)
    qualification = QualificationContext(
        QualificationEntropy(QUALIFICATION_MATERIAL),
        pin,
    )
    derived = derive_official_seed(
        official,
        SeedDomain.OFFICIAL_TRAIN,
        RoleKey("parameter_init"),
        0,
    )
    private_root = _derive_private_exam_root(official)
    fixture_provider = DeterministicFixtureProvider(
        FixtureOfficialEntropy(FIXTURE_MATERIAL)
    )
    secret_values = (
        OfficialEntropy(OFFICIAL_MATERIAL),
        FixtureOfficialEntropy(FIXTURE_MATERIAL),
        MockEntropy(MOCK_MATERIAL),
        QualificationEntropy(QUALIFICATION_MATERIAL),
        EvaluationBinding(BINDING_MATERIAL),
        derived,
        private_root,
        pin,
        official,
        fixture,
        mock,
        qualification,
        fixture_provider,
    )

    for value in secret_values:
        rendered = f"{value!r} {value!s}"
        assert "redacted" in rendered.lower()
        _assert_material_absent(
            rendered,
            OFFICIAL_MATERIAL,
            FIXTURE_MATERIAL,
            MOCK_MATERIAL,
            QUALIFICATION_MATERIAL,
            BINDING_MATERIAL,
            derived.as_backend_bytes(),
            private_root._copy_bytes(),
        )
        with pytest.raises(TypeError):
            value.__getstate__()
        with pytest.raises(TypeError):
            pickle.dumps(value)
        with pytest.raises(TypeError):
            copy.copy(value)
        with pytest.raises(TypeError):
            copy.deepcopy(value)
        with pytest.raises(TypeError):
            json.dumps(value)

    for value in (pin, official, fixture, mock, qualification):
        with pytest.raises(TypeError):
            dataclasses.asdict(value)


def test_validation_errors_do_not_echo_canary_material() -> None:
    canary = b"validation-canary-material-12345"
    assert len(canary) == 32
    operations = (
        lambda: OfficialEntropy(canary[:-1]),
        lambda: EvaluationBinding(canary.decode("ascii")),
        lambda: RoleKey(canary.decode("ascii") + "!"),
        lambda: SeedPin(
            ChallengeKey("burgers_1d", "v1"),
            "v1",
            "invalid:" + canary.decode("ascii"),
            "v1",
            SCORING_DIGEST,
            EvaluationBinding(BINDING_MATERIAL),
        ),
        lambda: OfficialContext(OfficialEntropy(canary), _pin()),
        lambda: serialize_exam_projection({"entropy": canary}),
    )

    for operation in operations:
        with pytest.raises((TypeError, ValueError)) as exc_info:
            operation()
        _assert_material_absent(
            f"{type(exc_info.value).__name__}: {exc_info.value!r}",
            canary,
        )


@pytest.mark.parametrize("error_type", (RuntimeError, BeaconConflictError))
def test_provider_errors_fail_closed_without_leaking_or_chaining_canary(
    error_type: type[Exception],
) -> None:
    canary = b"provider-error-canary-material-1"
    assert len(canary) == 32

    class ExplodingProvider:
        def observe_entropy(self) -> OfficialEntropy:
            raise error_type(" ".join(sorted(_secret_forms(canary))))

    with pytest.raises(OfficialEntropyUnavailable) as exc_info:
        acquire_official_context(ExplodingProvider(), _pin())

    assert exc_info.value.__cause__ is None
    assert exc_info.value.__context__ is None
    _assert_material_absent(
        f"{type(exc_info.value).__name__}: {exc_info.value!r}",
        canary,
    )


def test_official_context_and_projection_retain_no_provider_reference() -> None:
    provider = _Provider(OfficialEntropy(OFFICIAL_MATERIAL))
    provider_reference = weakref.ref(provider)
    context = acquire_official_context(provider, _pin())
    assert provider.calls == 1

    del provider
    gc.collect()
    assert provider_reference() is None

    projection = create_official_exam_projection(context)
    assert not hasattr(projection, "provider")
    assert not hasattr(projection.exam_commitment, "provider")
    assert not hasattr(projection.exam_commitment, "__dict__")


def test_exam_commitment_is_not_a_direct_private_material_encoding() -> None:
    context = _official_context()
    derived = derive_official_seed(
        context,
        SeedDomain.OFFICIAL_STRESS,
        RoleKey("generator_sampling"),
        9,
    )
    private_root = _derive_private_exam_root(context)
    commitment = create_official_exam_projection(context).exam_commitment
    public_value = commitment.to_primitive()
    materials = (
        OFFICIAL_MATERIAL,
        BINDING_MATERIAL,
        derived.as_backend_bytes(),
        private_root._copy_bytes(),
    )

    assert type(commitment) is ExamCommitment
    assert all(public_value not in _secret_forms(material) for material in materials)
    for material in materials:
        assert public_value != "sha256:" + material.hex()
        assert public_value != "sha256:" + hashlib.sha256(material).hexdigest()


def test_fixture_labels_and_projection_origins_are_immutable() -> None:
    official_projection = create_official_exam_projection(_official_context())
    fixture_projection = create_fixture_official_exam_projection(_fixture_context())

    assert type(official_projection) is OfficialExamProjection
    assert official_projection.fixture is False
    assert type(fixture_projection) is FixtureOfficialExamProjection
    assert fixture_projection.fixture is True
    with pytest.raises((AttributeError, dataclasses.FrozenInstanceError)):
        official_projection.fixture = True  # type: ignore[misc]
    with pytest.raises((AttributeError, dataclasses.FrozenInstanceError)):
        fixture_projection.fixture = False  # type: ignore[misc]
    with pytest.raises((TypeError, ValueError)):
        dataclasses.replace(official_projection, fixture=True)
    with pytest.raises((TypeError, ValueError)):
        dataclasses.replace(fixture_projection, fixture=False)

    values = (
        ExamCommitment("sha256:" + "c" * 64),
        "burgers_1d",
        "v1",
        "v1",
        GENERATOR_DIGEST,
        "v1",
        SCORING_DIGEST,
    )
    with pytest.raises(TypeError):
        OfficialExamProjection(*values)
    with pytest.raises(TypeError):
        FixtureOfficialExamProjection(*values)
    with pytest.raises(TypeError):
        OfficialContext(OfficialEntropy(OFFICIAL_MATERIAL), _pin())
    with pytest.raises(TypeError):
        FixtureOfficialContext(FixtureOfficialEntropy(FIXTURE_MATERIAL), _pin())


def test_fixture_provider_cannot_masquerade_as_official_origin() -> None:
    fixture_provider = DeterministicFixtureProvider(
        FixtureOfficialEntropy(FIXTURE_MATERIAL)
    )

    assert not hasattr(fixture_provider, "observe_entropy")
    with pytest.raises(OfficialEntropyUnavailable):
        acquire_official_context(fixture_provider, _pin())  # type: ignore[arg-type]
    with pytest.raises(AttributeError):
        fixture_provider.fixture = False  # type: ignore[attr-defined]
    with pytest.raises(AttributeError):
        fixture_provider._DeterministicFixtureProvider__entropy = OfficialEntropy(  # type: ignore[attr-defined]
            OFFICIAL_MATERIAL
        )
    with pytest.raises(AttributeError):
        fixture_provider.__init__(FixtureOfficialEntropy(FIXTURE_MATERIAL))


@pytest.mark.parametrize(
    "prospective_consumer",
    (
        "evaluation-card",
        "leaderboard-entry",
        "mcp-challenge-info",
        "mcp-estimate",
        "mcp-result",
    ),
)
def test_representative_consumer_shaped_values_use_only_a4_allow_list(
    prospective_consumer: str,
) -> None:
    context = _official_context()
    seed = derive_official_seed(
        context,
        SeedDomain.OFFICIAL_EVAL,
        RoleKey("generator"),
        7,
    )
    private_root = _derive_private_exam_root(context)
    projection = create_official_exam_projection(context)
    prospective_a4_value = dict(serialize_exam_projection(projection))
    shaped_regression_value = {
        "prospective_consumer": prospective_consumer,
        "a4_exam_projection": prospective_a4_value,
    }
    encoded = json.dumps(shaped_regression_value, sort_keys=True)

    assert prospective_consumer
    assert tuple(prospective_a4_value) == PUBLIC_PROJECTION_FIELDS
    assert all(type(value) in {str, bool} for value in prospective_a4_value.values())
    assert "emission_capable" not in prospective_a4_value
    assert "production" not in prospective_a4_value
    assert "live" not in prospective_a4_value
    _assert_material_absent(
        encoded,
        OFFICIAL_MATERIAL,
        BINDING_MATERIAL,
        seed.as_backend_bytes(),
        private_root._copy_bytes(),
    )


def test_private_seed_remains_inert_a2_strategy_json() -> None:
    strategy = {
        "schema_version": "1.0",
        "challenge_id": "burgers_1d",
        "backbone": "fno",
        "parameters": {
            "private_seed": {
                "description": "miner-authored inert metadata",
                "value": [None, True, 7, 2.5, "not an official seed"],
            }
        },
    }

    result = dry_validate(strategy)

    assert result.ok is True
    assert result.errors == ()


def test_public_api_excludes_private_helpers_and_later_consumer_claims() -> None:
    public_names = set(seeding.__all__)

    assert all(not name.startswith("_") for name in public_names)
    assert not {
        "CanonicalEncodingError",
        "PrivateExamRoot",
        "_PrivateExamRoot",
        "_derive_private_exam_root",
        "_encode_seed_info",
        "_hkdf_expand",
        "derive_seed",
        "to_dict",
        "EvaluationCard",
        "EvaluationReceipt",
        "LeaderboardEntry",
        "MCPResult",
        "emission_capable",
        "write_weights",
    }.intersection(public_names)
    assert not hasattr(seeding, "_PrivateExamRoot")
    assert not hasattr(seeding, "_derive_private_exam_root")
    assert not hasattr(seeding, "derive_seed")


def _copy_fresh_wheel_source(
    repository_root: Path,
    destination: Path,
) -> None:
    shutil.copy2(repository_root / "pyproject.toml", destination)
    shutil.copy2(repository_root / "README.md", destination)
    shutil.copytree(
        repository_root / "carbon",
        destination / "carbon",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.egg-info"),
    )


def _offline_wheel_builder() -> str | None:
    candidates = (
        sys.executable,
        getattr(sys, "_base_executable", None),
    )
    checked: set[str] = set()
    for candidate in candidates:
        if type(candidate) is not str or candidate in checked:
            continue
        checked.add(candidate)
        probe = subprocess.run(
            [candidate, "-I", "-c", "import setuptools, wheel"],
            check=False,
            capture_output=True,
            text=True,
        )
        if probe.returncode == 0:
            return candidate
    return None


def test_fresh_wheel_outside_tree_a4_execution_is_import_isolated(
    tmp_path: Path,
) -> None:
    repository_root = Path(__file__).resolve().parents[2]
    build_source = tmp_path / "fresh-source"
    wheelhouse = tmp_path / "wheelhouse"
    build_source.mkdir()
    wheelhouse.mkdir()
    _copy_fresh_wheel_source(repository_root, build_source)
    builder = _offline_wheel_builder()
    wheel_command = [
        builder or sys.executable,
        "-m",
        "pip",
        "wheel",
        "--no-deps",
        "--wheel-dir",
        str(wheelhouse),
        str(build_source),
    ]
    if builder is not None:
        wheel_command.insert(4, "--no-build-isolation")
    wheel_result = subprocess.run(
        wheel_command,
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
    )
    assert wheel_result.returncode == 0, wheel_result.stderr
    wheels = tuple(wheelhouse.glob("carbon-*.whl"))
    assert len(wheels) == 1
    wheel = wheels[0]
    environment = tmp_path / "fresh-environment"
    outside_tree = tmp_path / "outside-checkout"
    outside_tree.mkdir()

    create_result = subprocess.run(
        [sys.executable, "-m", "venv", str(environment)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert create_result.returncode == 0, create_result.stderr
    environment_python = environment / (
        "Scripts/python.exe" if os.name == "nt" else "bin/python"
    )
    pip_environment = os.environ.copy()
    pip_environment.update(
        {
            "PIP_DISABLE_PIP_VERSION_CHECK": "1",
            "PIP_NO_INDEX": "1",
        }
    )
    install_result = subprocess.run(
        [
            str(environment_python),
            "-m",
            "pip",
            "install",
            "--no-deps",
            "--no-index",
            str(wheel),
        ],
        cwd=outside_tree,
        env=pip_environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert install_result.returncode == 0, install_result.stderr

    script = textwrap.dedent("""
        import importlib.abc
        import importlib.metadata
        import json
        import pathlib
        import sys

        blocked_roots = {
            "bittensor",
            "jax",
            "mcp",
            "neuralop",
            "neuraloperator",
            "numpy",
            "physicsnemo",
            "scipy",
            "torch",
            "yaml",
        }
        blocked_carbon_modules = {
            "carbon.audit",
            "carbon.backbones",
            "carbon.cards",
            "carbon.chain",
            "carbon.common",
            "carbon.emission",
            "carbon.evaluation",
            "carbon.execution",
            "carbon.fees",
            "carbon.leaderboard",
            "carbon.logging",
            "carbon.logging_utils",
            "carbon.mcp",
            "carbon.miner",
            "carbon.physics",
            "carbon.protocol",
            "carbon.qualification",
            "carbon.sciml",
            "carbon.scoring",
            "carbon.specialist",
            "carbon.symbolic",
            "carbon.training",
            "carbon.traineval",
            "carbon.validator",
        }

        def is_blocked(fullname):
            root = fullname.partition(".")[0]
            return root in blocked_roots or any(
                fullname == name or fullname.startswith(name + ".")
                for name in blocked_carbon_modules
            )

        class BoundaryBlocker(importlib.abc.MetaPathFinder):
            def __init__(self):
                self.attempted = []

            def find_spec(self, fullname, path=None, target=None):
                del path, target
                if is_blocked(fullname):
                    self.attempted.append(fullname)
                    raise ModuleNotFoundError(
                        "blocked A4 dependency or consumer import",
                        name=fullname,
                    )
                return None

        blocker = BoundaryBlocker()
        sys.meta_path.insert(0, blocker)

        import carbon.seeding as seeding
        from carbon.registry.model import ChallengeKey

        public_api = {name: getattr(seeding, name) for name in seeding.__all__}
        pin = public_api["SeedPin"](
            ChallengeKey("burgers_1d", "v1"),
            "v1",
            "sha256:" + "a" * 64,
            "v1",
            "sha256:" + "b" * 64,
            public_api["EvaluationBinding"](b"E" * 32),
        )

        class Provider:
            def observe_entropy(self):
                return public_api["OfficialEntropy"](b"O" * 32)

        official = public_api["acquire_official_context"](Provider(), pin)
        fixture = public_api["acquire_fixture_official_context"](
            public_api["DeterministicFixtureProvider"](
                public_api["FixtureOfficialEntropy"](b"F" * 32)
            ),
            pin,
        )
        mock = public_api["MockContext"](
            public_api["MockEntropy"](b"M" * 32),
            pin,
        )
        qualification = public_api["QualificationContext"](
            public_api["QualificationEntropy"](b"Q" * 32),
            pin,
        )
        role = public_api["RoleKey"]("generator")
        seeds = {
            "fixture": public_api["derive_fixture_official_seed"](
                fixture,
                public_api["SeedDomain"].OFFICIAL_EVAL,
                role,
                7,
            ).as_backend_bytes().hex(),
            "mock": public_api["derive_mock_seed"](
                mock,
                role,
                7,
            ).as_backend_bytes().hex(),
            "official": public_api["derive_official_seed"](
                official,
                public_api["SeedDomain"].OFFICIAL_EVAL,
                role,
                7,
            ).as_backend_bytes().hex(),
            "qualification": public_api["derive_qualification_seed"](
                qualification,
                public_api["SeedDomain"].REFERENCE,
                role,
                7,
            ).as_backend_bytes().hex(),
        }
        official_projection = public_api["serialize_exam_projection"](
            public_api["create_official_exam_projection"](official)
        )
        fixture_projection = public_api["serialize_exam_projection"](
            public_api["create_fixture_official_exam_projection"](fixture)
        )
        distribution = importlib.metadata.distribution("carbon")
        loaded = sorted(name for name in sys.modules if is_blocked(name))
        print(json.dumps({
            "attempted": blocker.attempted,
            "context_kinds": [item.value for item in public_api["ContextKind"]],
            "distribution": [
                distribution.metadata["Name"],
                distribution.version,
            ],
            "error_types": sorted(
                public_api[name].__name__
                for name in (
                    "BeaconConflictError",
                    "FixtureEntropyUnavailable",
                    "OfficialEntropyUnavailable",
                    "SeedValidationError",
                )
            ),
            "fixture_projection": fixture_projection,
            "hkdf_salt": public_api["HKDF_SALT"].decode("ascii"),
            "loaded": loaded,
            "module_file": str(pathlib.Path(seeding.__file__).resolve()),
            "official_projection": official_projection,
            "public_api": sorted(public_api),
            "scheme": public_api["SEED_SCHEME_ID"],
            "seed_domains": [item.value for item in public_api["SeedDomain"]],
            "seeds": seeds,
            "types": [
                type(official).__name__,
                type(fixture).__name__,
                type(mock).__name__,
                type(qualification).__name__,
            ],
        }, sort_keys=True))
        """)
    execution_result = subprocess.run(
        [str(environment_python), "-I", "-c", script],
        cwd=outside_tree,
        check=False,
        capture_output=True,
        text=True,
    )

    assert execution_result.returncode == 0, execution_result.stderr
    payload = json.loads(execution_result.stdout)
    module_file = Path(payload.pop("module_file"))
    assert repository_root not in module_file.parents
    assert outside_tree not in module_file.parents
    assert payload == {
        "attempted": [],
        "context_kinds": [
            "mock",
            "official",
            "qualification",
            "fixture_official",
        ],
        "distribution": ["carbon", "0.9.0"],
        "error_types": [
            "BeaconConflictError",
            "FixtureEntropyUnavailable",
            "OfficialEntropyUnavailable",
            "SeedValidationError",
        ],
        "fixture_projection": {
            "challenge_id": "burgers_1d",
            "challenge_version": "v1",
            "exam_commitment": (
                "sha256:753a8fd634f8c9f8a32f4a6eb7387e1b36251b9b866056de71dc61f5cbbf7372"
            ),
            "fixture": True,
            "generator_digest": GENERATOR_DIGEST,
            "generator_version": "v1",
            "scoring_digest": SCORING_DIGEST,
            "scoring_version": "v1",
        },
        "hkdf_salt": "carbon/a4-seeding/hkdf-sha256/v1",
        "loaded": [],
        "official_projection": {
            "challenge_id": "burgers_1d",
            "challenge_version": "v1",
            "exam_commitment": (
                "sha256:f57095155310e4608f7982d23598ac6035d2aa2449f20fa8c126b47bb0c5c466"
            ),
            "fixture": False,
            "generator_digest": GENERATOR_DIGEST,
            "generator_version": "v1",
            "scoring_digest": SCORING_DIGEST,
            "scoring_version": "v1",
        },
        "public_api": sorted(seeding.__all__),
        "scheme": "carbon.seed.hkdf-sha256.v1",
        "seed_domains": [
            "mock",
            "official_train",
            "official_eval",
            "official_stress",
            "reference",
            "dossier",
        ],
        "seeds": {
            "fixture": (
                "d417415235375349886f1505a72d25757788568b9293ca774c6d81967f804c2e"
            ),
            "mock": (
                "93eaa357f51ed1d5c2c92c03de379bc1de87976fea18496f1caac8af3c201b12"
            ),
            "official": (
                "5a454eb7784d75cde1411c0d8d02e1e93076128a472233548186c983a69950a9"
            ),
            "qualification": (
                "c987df0129e5ff8fcb7436236ef75f68cf4c31902170c1ce8df12cd8d3c461b4"
            ),
        },
        "types": [
            "OfficialContext",
            "FixtureOfficialContext",
            "MockContext",
            "QualificationContext",
        ],
    }
