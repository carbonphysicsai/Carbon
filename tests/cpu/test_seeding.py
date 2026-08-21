"""CPU acceptance tests for A4's typed, canonical seeding boundary."""

from __future__ import annotations

import inspect
import os
import random
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError

import pytest

from carbon.registry import ChallengeKey
from carbon.registry import digest as registry_digest
from carbon.registry import model as registry_model
from carbon.seeding import (
    HKDF_SALT,
    SEED_SCHEME_ID,
    BeaconConflictError,
    ContextKind,
    DerivedSeed,
    DeterministicFixtureProvider,
    EvaluationBinding,
    FixtureEntropyUnavailable,
    FixtureOfficialContext,
    FixtureOfficialEntropy,
    MockContext,
    MockEntropy,
    OfficialContext,
    OfficialEntropy,
    OfficialEntropyUnavailable,
    QualificationContext,
    QualificationEntropy,
    RoleKey,
    SeedDomain,
    SeedPin,
    SeedValidationError,
    acquire_fixture_official_context,
    acquire_official_context,
    create_fixture_official_exam_projection,
    create_official_exam_projection,
    derive_fixture_official_seed,
    derive_mock_seed,
    derive_official_seed,
    derive_qualification_seed,
)
from carbon.seeding.commitment import _derive_private_exam_root
from carbon.seeding.derive import _hkdf_expand, _hkdf_extract
from carbon.seeding.encoding import (
    EXAM_COMMITMENT_HEADER,
    EXAM_ROOT_INFO_HEADER,
    SEED_INFO_HEADER,
    CanonicalEncodingError,
    _encode_exam_commitment_document,
    _encode_exam_root_info,
    _encode_seed_info,
    _validate_exam_commitment_document,
    _validate_exam_root_info,
    _validate_seed_info,
)
from carbon.seeding.model import _PrivateExamRoot

ENTROPY_BYTES = bytes(range(32))
BINDING_BYTES = bytes(range(32, 64))
OTHER_ENTROPY_BYTES = bytes(reversed(range(32)))
GENERATOR_DIGEST = "sha256:" + "11" * 32
SCORING_DIGEST = "sha256:" + "22" * 32
DRAW_INDEX = 0x0102030405060708

# These vectors were generated independently from the ratified byte contract,
# using only Python's hmac/hashlib and a local tag-length-value builder. They
# are intentionally literals: the expected side never calls A4 production code.
GOLDEN_SEED_INFO = bytes.fromhex("""
    636172626f6e2e736565642e696e666f2e7631
    01000000086f6666696369616c
    020000001a636172626f6e2e736565642e686b64662d7368613235362e7631
    030000000a627572676572735f3164
    0400000003312e32
    050000000867656e2d76312e32
    06000000477368613235363a31313131313131313131313131313131313131313131313131313131313131313131313131313131313131313131313131313131313131313131313131313131
    070000000873636f72655f7633
    08000000477368613235363a32323232323232323232323232323232323232323232323232323232323232323232323232323232323232323232323232323232323232323232323232323232
    0900000020202122232425262728292a2b2c2d2e2f303132333435363738393a3b3c3d3e3f
    0a0000000d6f6666696369616c5f6576616c
    0b0000000b62617463685f6f72646572
    0c000000080102030405060708
    """)
GOLDEN_EXAM_ROOT_INFO = bytes.fromhex("""
    636172626f6e2e6578616d2d726f6f742e696e666f2e7631
    01000000086f6666696369616c
    020000001a636172626f6e2e736565642e686b64662d7368613235362e7631
    030000000a627572676572735f3164
    0400000003312e32
    050000000867656e2d76312e32
    06000000477368613235363a31313131313131313131313131313131313131313131313131313131313131313131313131313131313131313131313131313131313131313131313131313131
    070000000873636f72655f7633
    08000000477368613235363a32323232323232323232323232323232323232323232323232323232323232323232323232323232323232323232323232323232323232323232323232323232
    0900000020202122232425262728292a2b2c2d2e2f303132333435363738393a3b3c3d3e3f
    """)
GOLDEN_PRK = bytes.fromhex(
    "54f2ca52e5d6b5ac686b2c7bfd625932b5e5b05fa18486749555c93142fa547e"
)
GOLDEN_SEED = bytes.fromhex(
    "c1fb826f03611933d2d1c4cc979d6d3c25791da19585663b341e73a4f8904060"
)
GOLDEN_CONTEXT_SEEDS = {
    ContextKind.MOCK: bytes.fromhex(
        "a71f0acc00026e288e93564491e5af0432a7d67f8004b9eda121933e006fbb21"
    ),
    ContextKind.OFFICIAL: GOLDEN_SEED,
    ContextKind.FIXTURE_OFFICIAL: bytes.fromhex(
        "d3ad1f28786a4b1748b4739e76ffb4f28aebec766fcbd90716ede190c55ea2d6"
    ),
    ContextKind.QUALIFICATION: bytes.fromhex(
        "cb8c22eced6aca1303c496c9431df68d449d4fb078c8318c02b1ab2caa41bf7b"
    ),
}
GOLDEN_PRIVATE_EXAM_ROOT = bytes.fromhex(
    "ba8845f0ac7a797c68ae1468b4852e0ffab1e25f7bd655c247c43f1031f8ab70"
)
GOLDEN_COMMITMENT_DOCUMENT = bytes.fromhex("""
    636172626f6e2e6578616d2d636f6d6d69746d656e742e7631
    01000000086f6666696369616c
    020000001a636172626f6e2e736565642e686b64662d7368613235362e7631
    030000000a627572676572735f3164
    0400000003312e32
    050000000867656e2d76312e32
    06000000477368613235363a31313131313131313131313131313131313131313131313131313131313131313131313131313131313131313131313131313131313131313131313131313131
    070000000873636f72655f7633
    08000000477368613235363a32323232323232323232323232323232323232323232323232323232323232323232323232323232323232323232323232323232323232323232323232323232
    0900000020202122232425262728292a2b2c2d2e2f303132333435363738393a3b3c3d3e3f
    0a00000020ba8845f0ac7a797c68ae1468b4852e0ffab1e25f7bd655c247c43f1031f8ab70
    """)
GOLDEN_COMMITMENT = (
    "sha256:8f62a905892a4d974c344c44801aa4e6b58f48260948e1fadd0fde0fca81aa5b"
)


_DEFAULT_OBSERVATION = object()


class _FixedProvider:
    def __init__(self, observation: object = _DEFAULT_OBSERVATION) -> None:
        self.observation = (
            OfficialEntropy(ENTROPY_BYTES)
            if observation is _DEFAULT_OBSERVATION
            else observation
        )
        self.calls = 0

    def observe_entropy(self) -> object:
        self.calls += 1
        return self.observation


class _RaisingProvider:
    def __init__(self, error: Exception) -> None:
        self.error = error
        self.calls = 0

    def observe_entropy(self) -> OfficialEntropy:
        self.calls += 1
        raise self.error


def _pin(**overrides: object) -> SeedPin:
    challenge_key = overrides.pop("challenge_key", ChallengeKey("burgers_1d", "1.2"))
    generator_version = overrides.pop("generator_version", "gen-v1.2")
    generator_digest = overrides.pop("generator_digest", GENERATOR_DIGEST)
    scoring_version = overrides.pop("scoring_version", "score_v3")
    scoring_digest = overrides.pop("scoring_digest", SCORING_DIGEST)
    evaluation_binding = overrides.pop(
        "evaluation_binding", EvaluationBinding(BINDING_BYTES)
    )
    assert not overrides
    return SeedPin(
        challenge_key,  # type: ignore[arg-type]
        generator_version,  # type: ignore[arg-type]
        generator_digest,  # type: ignore[arg-type]
        scoring_version,  # type: ignore[arg-type]
        scoring_digest,  # type: ignore[arg-type]
        evaluation_binding,  # type: ignore[arg-type]
    )


def _official_context(
    *, pin: SeedPin | None = None, entropy: bytes = ENTROPY_BYTES
) -> OfficialContext:
    provider = _FixedProvider(OfficialEntropy(entropy))
    return acquire_official_context(provider, _pin() if pin is None else pin)


def _fixture_context(
    *, pin: SeedPin | None = None, entropy: bytes = ENTROPY_BYTES
) -> FixtureOfficialContext:
    provider = DeterministicFixtureProvider(FixtureOfficialEntropy(entropy))
    return acquire_fixture_official_context(provider, _pin() if pin is None else pin)


def _mock_context(
    *, pin: SeedPin | None = None, entropy: bytes = ENTROPY_BYTES
) -> MockContext:
    return MockContext(MockEntropy(entropy), _pin() if pin is None else pin)


def _qualification_context(
    *, pin: SeedPin | None = None, entropy: bytes = ENTROPY_BYTES
) -> QualificationContext:
    return QualificationContext(
        QualificationEntropy(entropy), _pin() if pin is None else pin
    )


def _fields(document: bytes, header: bytes) -> list[tuple[int, bytes]]:
    """Parse a known-good literal for hostile-test construction only."""
    assert document.startswith(header)
    result: list[tuple[int, bytes]] = []
    offset = len(header)
    while offset < len(document):
        tag = document[offset]
        length = int.from_bytes(document[offset + 1 : offset + 5], "big")
        start = offset + 5
        end = start + length
        assert end <= len(document)
        result.append((tag, document[start:end]))
        offset = end
    assert offset == len(document)
    return result


def _document(header: bytes, fields: list[tuple[int, bytes]]) -> bytes:
    return header + b"".join(
        bytes((tag,)) + len(payload).to_bytes(4, "big") + payload
        for tag, payload in fields
    )


def _with_payload(document: bytes, header: bytes, tag: int, payload: bytes) -> bytes:
    fields = _fields(document, header)
    return _document(
        header,
        [
            (field_tag, payload if field_tag == tag else value)
            for field_tag, value in fields
        ],
    )


def test_exact_scheme_salt_headers_domains_and_context_kinds() -> None:
    assert SEED_SCHEME_ID == "carbon.seed.hkdf-sha256.v1"
    assert HKDF_SALT == b"carbon/a4-seeding/hkdf-sha256/v1"
    assert SEED_INFO_HEADER == b"carbon.seed.info.v1"
    assert EXAM_ROOT_INFO_HEADER == b"carbon.exam-root.info.v1"
    assert EXAM_COMMITMENT_HEADER == b"carbon.exam-commitment.v1"
    assert [domain.value for domain in SeedDomain] == [
        "mock",
        "official_train",
        "official_eval",
        "official_stress",
        "reference",
        "dossier",
    ]
    assert [kind.value for kind in ContextKind] == [
        "mock",
        "official",
        "qualification",
        "fixture_official",
    ]


def test_rfc_5869_sha256_test_case_1() -> None:
    ikm = bytes.fromhex("0b" * 22)
    salt = bytes.fromhex("000102030405060708090a0b0c")
    info = bytes.fromhex("f0f1f2f3f4f5f6f7f8f9")
    expected_prk = bytes.fromhex(
        "077709362c2e32df0ddc3f0dc47bba63" "90b6c73bb50f9c3122ec844ad7c2b3e5"
    )
    expected_okm = bytes.fromhex(
        "3cb25f25faacd57a90434f64d0362f2a"
        "2d2d0a90cf1a5a4c5db02d56ecc4c5bf"
        "34007208d5b887185865"
    )

    assert _hkdf_extract(salt, ikm) == expected_prk
    assert _hkdf_expand(expected_prk, info, 42) == expected_okm


@pytest.mark.parametrize(
    ("salt", "ikm"),
    [
        (bytearray(b"s"), b"i"),
        (b"s", bytearray(b"i")),
        ("salt", b"i"),
        (b"s", "ikm"),
    ],
)
def test_hkdf_extract_rejects_coercion(salt: object, ikm: object) -> None:
    with pytest.raises(SeedValidationError, match="invalid HKDF-SHA-256 input"):
        _hkdf_extract(salt, ikm)


@pytest.mark.parametrize(
    ("prk", "info", "length"),
    [
        (b"p" * 31, b"i", 32),
        (bytearray(b"p" * 32), b"i", 32),
        (b"p" * 32, bytearray(b"i"), 32),
        (b"p" * 32, b"i", True),
        (b"p" * 32, b"i", -1),
        (b"p" * 32, b"i", 255 * 32 + 1),
    ],
)
def test_hkdf_expand_rejects_invalid_bounds(
    prk: object, info: object, length: object
) -> None:
    with pytest.raises(SeedValidationError, match="invalid HKDF-SHA-256 input"):
        _hkdf_expand(prk, info, length)


def test_carbon_golden_documents_seed_root_and_commitment() -> None:
    context = _official_context()
    role_key = RoleKey("batch_order")

    seed_info = _encode_seed_info(
        ContextKind.OFFICIAL,
        context.pin,
        SeedDomain.OFFICIAL_EVAL,
        role_key,
        DRAW_INDEX,
    )
    root_info = _encode_exam_root_info(ContextKind.OFFICIAL, context.pin)
    private_root = _derive_private_exam_root(context)
    commitment_document = _encode_exam_commitment_document(
        ContextKind.OFFICIAL,
        context.pin,
        private_root,
    )
    seed = derive_official_seed(
        context,
        SeedDomain.OFFICIAL_EVAL,
        role_key,
        DRAW_INDEX,
    )
    projection = create_official_exam_projection(context)

    assert seed_info == GOLDEN_SEED_INFO
    assert root_info == GOLDEN_EXAM_ROOT_INFO
    assert _hkdf_extract(HKDF_SALT, ENTROPY_BYTES) == GOLDEN_PRK
    assert seed.as_backend_bytes() == GOLDEN_SEED
    assert private_root._copy_bytes() == GOLDEN_PRIVATE_EXAM_ROOT
    assert commitment_document == GOLDEN_COMMITMENT_DOCUMENT
    assert projection.exam_commitment.value == GOLDEN_COMMITMENT
    assert type(seed) is DerivedSeed
    assert len(seed.as_backend_bytes()) == 32
    _validate_seed_info(seed_info)
    _validate_exam_root_info(root_info)
    _validate_exam_commitment_document(commitment_document)


@pytest.mark.parametrize(
    "wrapper_type",
    [
        OfficialEntropy,
        MockEntropy,
        QualificationEntropy,
        FixtureOfficialEntropy,
        EvaluationBinding,
        DerivedSeed,
        _PrivateExamRoot,
    ],
)
def test_exact_32_byte_values_copy_input_and_are_immutable(wrapper_type: type) -> None:
    source = bytes(bytearray(range(32)))
    wrapped = wrapper_type(source)
    if type(wrapped) is DerivedSeed:
        copied = wrapped.as_backend_bytes()
    else:
        copied = wrapped._copy_bytes()
    assert copied == source
    assert copied is not source
    assert "redacted" in repr(wrapped)
    with pytest.raises(AttributeError, match="immutable"):
        wrapped.replacement = b"x" * 32


class _BytesSubclass(bytes):
    pass


@pytest.mark.parametrize(
    "invalid",
    [
        b"x" * 31,
        b"x" * 33,
        bytearray(b"x" * 32),
        memoryview(b"x" * 32),
        _BytesSubclass(b"x" * 32),
        "x" * 32,
        0,
        [0] * 32,
        None,
    ],
)
@pytest.mark.parametrize(
    "wrapper_type",
    [
        OfficialEntropy,
        MockEntropy,
        QualificationEntropy,
        FixtureOfficialEntropy,
        EvaluationBinding,
        DerivedSeed,
        _PrivateExamRoot,
    ],
)
def test_exact_32_byte_values_reject_wrong_length_or_coercion(
    wrapper_type: type, invalid: object
) -> None:
    with pytest.raises(SeedValidationError, match="exactly 32 bytes"):
        wrapper_type(invalid)


def test_secret_types_are_separate_non_inheriting_and_noncoercible() -> None:
    wrappers = [
        OfficialEntropy(ENTROPY_BYTES),
        MockEntropy(ENTROPY_BYTES),
        QualificationEntropy(ENTROPY_BYTES),
        FixtureOfficialEntropy(ENTROPY_BYTES),
    ]
    assert len({type(value) for value in wrappers}) == 4
    for left in wrappers:
        for right in wrappers:
            assert (left == right) is (type(left) is type(right))
    with pytest.raises(SeedValidationError):
        MockContext(wrappers[0], _pin())  # type: ignore[arg-type]
    with pytest.raises(SeedValidationError):
        QualificationContext(wrappers[1], _pin())  # type: ignore[arg-type]


def test_contexts_copy_entropy_pin_and_binding_and_are_frozen() -> None:
    entropy = MockEntropy(ENTROPY_BYTES)
    pin = _pin()
    context = MockContext(entropy, pin)

    assert context.entropy == entropy
    assert context.entropy is not entropy
    assert context.pin is not pin
    assert context.pin.challenge_key is not pin.challenge_key
    assert context.pin.evaluation_binding is not pin.evaluation_binding
    with pytest.raises(FrozenInstanceError):
        context.entropy = MockEntropy(OTHER_ENTROPY_BYTES)  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        context.pin = _pin(generator_version="different")  # type: ignore[misc]


class _StringSubclass(str):
    pass


@pytest.mark.parametrize(
    "value",
    [
        "a",
        "generator_sampling",
        "batch-order-v2",
        "a" * 64,
    ],
)
def test_role_key_accepts_exact_canonical_ascii_boundary(value: str) -> None:
    role_key = RoleKey(value)
    assert role_key.value == value
    assert str(role_key) == value


@pytest.mark.parametrize(
    "value",
    [
        "",
        "a" * 65,
        "BatchOrder",
        "1batch",
        "batch order",
        "batch__order",
        "batch_",
        "_batch",
        "-a",
        "a-",
        "a--b",
        "a.b",
        "a/b",
        "bátch",
        b"batch_order",
        _StringSubclass("batch_order"),
        True,
        None,
    ],
)
def test_role_key_rejects_noncanonical_or_coercible_values(value: object) -> None:
    with pytest.raises(SeedValidationError):
        RoleKey(value)


def test_role_key_reuses_a3_canonical_identifier_validator(monkeypatch) -> None:
    calls: list[tuple[object, str]] = []
    original = registry_model.validate_canonical_identifier

    def recording_validator(value: object, field_name: str) -> str:
        calls.append((value, field_name))
        return original(value, field_name)

    monkeypatch.setattr(
        registry_model, "validate_canonical_identifier", recording_validator
    )
    assert RoleKey("generator_sampling").value == "generator_sampling"
    assert calls == [("generator_sampling", "role_key")]


def test_seed_pin_reuses_exact_a3_challenge_version_and_digest_validators(
    monkeypatch,
) -> None:
    challenge_key = ChallengeKey("burgers_1d", "1.2")
    challenge_calls: list[tuple[str, str]] = []
    version_calls: list[object] = []
    digest_calls: list[object] = []
    original_post_init = ChallengeKey.__post_init__
    original_version = registry_model.validate_version
    original_digest = registry_digest.is_sha256_digest

    def recording_post_init(self: ChallengeKey) -> None:
        challenge_calls.append((self.challenge_id, self.version))
        original_post_init(self)

    def recording_version(value: object) -> str:
        version_calls.append(value)
        return original_version(value)

    def recording_digest(value: object) -> bool:
        digest_calls.append(value)
        return original_digest(value)

    monkeypatch.setattr(ChallengeKey, "__post_init__", recording_post_init)
    monkeypatch.setattr(registry_model, "validate_version", recording_version)
    monkeypatch.setattr(registry_digest, "is_sha256_digest", recording_digest)

    pin = SeedPin(
        challenge_key,
        "gen-v1.2",
        GENERATOR_DIGEST,
        "score_v3",
        SCORING_DIGEST,
        EvaluationBinding(BINDING_BYTES),
    )
    assert pin.challenge_key == challenge_key
    assert challenge_calls == [("burgers_1d", "1.2")]
    assert "gen-v1.2" in version_calls
    assert "score_v3" in version_calls
    assert GENERATOR_DIGEST in digest_calls
    assert SCORING_DIGEST in digest_calls


@pytest.mark.parametrize(
    "overrides",
    [
        {"challenge_key": object()},
        {"generator_version": ""},
        {"generator_version": "gen version"},
        {"generator_version": "x" * 65},
        {"generator_version": True},
        {"scoring_version": "score/β"},
        {"generator_digest": "11" * 32},
        {"generator_digest": "sha256:" + "AA" * 32},
        {"generator_digest": "sha256:" + "1" * 63},
        {"scoring_digest": b"sha256:" + b"2" * 64},
        {"evaluation_binding": OfficialEntropy(BINDING_BYTES)},
    ],
)
def test_seed_pin_rejects_weaker_or_coerced_identity(
    overrides: dict[str, object],
) -> None:
    with pytest.raises(SeedValidationError):
        _pin(**overrides)


def test_official_and_fixture_contexts_require_their_provider_boundaries() -> None:
    with pytest.raises(TypeError, match="BeaconProvider"):
        OfficialContext(OfficialEntropy(ENTROPY_BYTES), _pin())
    with pytest.raises(TypeError, match="fixture provider"):
        FixtureOfficialContext(FixtureOfficialEntropy(ENTROPY_BYTES), _pin())


def test_provider_is_observed_once_then_context_is_an_immutable_snapshot() -> None:
    provider = _FixedProvider()
    context = acquire_official_context(provider, _pin())
    before = derive_official_seed(
        context, SeedDomain.OFFICIAL_EVAL, RoleKey("batch_order"), 7
    )

    provider.observation = OfficialEntropy(OTHER_ENTROPY_BYTES)
    for _ in range(10):
        assert (
            derive_official_seed(
                context, SeedDomain.OFFICIAL_EVAL, RoleKey("batch_order"), 7
            )
            == before
        )
    assert provider.calls == 1
    assert not hasattr(context, "provider")


@pytest.mark.parametrize(
    "provider",
    [
        object(),
        _FixedProvider(None),
        _FixedProvider(ENTROPY_BYTES),
        _FixedProvider(MockEntropy(ENTROPY_BYTES)),
        _FixedProvider(FixtureOfficialEntropy(ENTROPY_BYTES)),
        _RaisingProvider(RuntimeError("unavailable")),
        _RaisingProvider(BeaconConflictError("conflicting observations")),
        _RaisingProvider(SeedValidationError("entropy must be exactly 32 bytes")),
    ],
)
def test_official_provider_failures_are_generic_and_have_no_fallback(
    provider: object,
) -> None:
    with pytest.raises(
        OfficialEntropyUnavailable, match=r"^official entropy is unavailable$"
    ) as captured:
        acquire_official_context(provider, _pin())  # type: ignore[arg-type]
    assert captured.value.__cause__ is None


def test_provider_malformed_observation_fails_closed() -> None:
    class MalformedProvider:
        def observe_entropy(self) -> OfficialEntropy:
            return OfficialEntropy(b"short")

    with pytest.raises(OfficialEntropyUnavailable):
        acquire_official_context(MalformedProvider(), _pin())


def test_provider_forged_exact_type_observations_fail_closed_generically() -> None:
    uninitialized = object.__new__(OfficialEntropy)
    corrupted = OfficialEntropy(ENTROPY_BYTES)
    object.__setattr__(
        corrupted,
        "_OfficialEntropy__material",
        b"short",
    )

    for observation in (uninitialized, corrupted):
        with pytest.raises(
            OfficialEntropyUnavailable,
            match=r"^official entropy is unavailable$",
        ) as captured:
            acquire_official_context(_FixedProvider(observation), _pin())
        assert captured.value.__cause__ is None
        assert captured.value.__context__ is None


def test_invalid_pin_rejects_before_provider_observation() -> None:
    provider = _FixedProvider()
    with pytest.raises(SeedValidationError, match="exact SeedPin"):
        acquire_official_context(provider, object())  # type: ignore[arg-type]
    assert provider.calls == 0


def test_fixture_provider_is_distinct_immutable_and_never_official() -> None:
    fixture_entropy = FixtureOfficialEntropy(ENTROPY_BYTES)
    fixture_provider = DeterministicFixtureProvider(fixture_entropy)
    fixture_context = acquire_fixture_official_context(fixture_provider, _pin())
    fixture_projection = create_fixture_official_exam_projection(fixture_context)

    assert fixture_provider.fixture_entropy() == fixture_entropy
    assert fixture_provider.fixture_entropy() is not fixture_entropy
    assert fixture_context.context_kind is ContextKind.FIXTURE_OFFICIAL
    assert fixture_projection.fixture is True
    assert not hasattr(fixture_provider, "observe_entropy")
    with pytest.raises(AttributeError, match="immutable"):
        fixture_provider.entropy = fixture_entropy  # type: ignore[attr-defined]
    with pytest.raises(OfficialEntropyUnavailable):
        acquire_official_context(fixture_provider, _pin())  # type: ignore[arg-type]
    with pytest.raises(FixtureEntropyUnavailable):
        acquire_fixture_official_context(_FixedProvider(), _pin())  # type: ignore[arg-type]
    with pytest.raises(SeedValidationError):
        DeterministicFixtureProvider(OfficialEntropy(ENTROPY_BYTES))  # type: ignore[arg-type]


def test_fixture_provider_rejects_subclasses_and_wrong_return_types() -> None:
    class FixtureProviderSubclass(DeterministicFixtureProvider):
        pass

    provider = FixtureProviderSubclass(FixtureOfficialEntropy(ENTROPY_BYTES))
    with pytest.raises(FixtureEntropyUnavailable):
        acquire_fixture_official_context(provider, _pin())

    fixture_provider = DeterministicFixtureProvider(
        FixtureOfficialEntropy(ENTROPY_BYTES)
    )
    with pytest.raises(AttributeError, match="immutable"):
        fixture_provider.fixture_entropy = lambda: FixtureOfficialEntropy(  # type: ignore[method-assign]
            OTHER_ENTROPY_BYTES
        )


def test_deterministic_fixture_provider_reproduces_seed_and_commitment() -> None:
    first = _fixture_context()
    second = _fixture_context()
    role = RoleKey("generator_sampling")
    assert derive_fixture_official_seed(
        first, SeedDomain.OFFICIAL_EVAL, role, 7
    ) == derive_fixture_official_seed(second, SeedDomain.OFFICIAL_EVAL, role, 7)
    assert (
        create_fixture_official_exam_projection(first).exam_commitment
        == create_fixture_official_exam_projection(second).exam_commitment
    )


def test_exam_projection_factories_reject_crossed_contexts() -> None:
    with pytest.raises(SeedValidationError, match="official context"):
        create_official_exam_projection(_fixture_context())  # type: ignore[arg-type]
    with pytest.raises(SeedValidationError, match="fixture-official context"):
        create_fixture_official_exam_projection(  # type: ignore[arg-type]
            _official_context()
        )


def test_all_domain_context_matrices_and_context_namespaces() -> None:
    role = RoleKey("generator_sampling")
    official = _official_context()
    fixture = _fixture_context()
    mock = _mock_context()
    qualification = _qualification_context()

    outputs = {
        SeedDomain.MOCK: derive_mock_seed(mock, role, 7).as_backend_bytes(),
        SeedDomain.OFFICIAL_TRAIN: derive_official_seed(
            official, SeedDomain.OFFICIAL_TRAIN, role, 7
        ).as_backend_bytes(),
        SeedDomain.OFFICIAL_EVAL: derive_official_seed(
            official, SeedDomain.OFFICIAL_EVAL, role, 7
        ).as_backend_bytes(),
        SeedDomain.OFFICIAL_STRESS: derive_official_seed(
            official, SeedDomain.OFFICIAL_STRESS, role, 7
        ).as_backend_bytes(),
        SeedDomain.REFERENCE: derive_qualification_seed(
            qualification, SeedDomain.REFERENCE, role, 7
        ).as_backend_bytes(),
        SeedDomain.DOSSIER: derive_qualification_seed(
            qualification, SeedDomain.DOSSIER, role, 7
        ).as_backend_bytes(),
    }
    fixture_outputs = {
        domain: derive_fixture_official_seed(
            fixture, domain, role, 7
        ).as_backend_bytes()
        for domain in (
            SeedDomain.OFFICIAL_TRAIN,
            SeedDomain.OFFICIAL_EVAL,
            SeedDomain.OFFICIAL_STRESS,
        )
    }

    assert set(outputs) == set(SeedDomain)
    assert len(set(outputs.values())) == 6
    assert len(set(fixture_outputs.values())) == 3
    for domain, fixture_output in fixture_outputs.items():
        assert fixture_output != outputs[domain]
    assert mock.context_kind is ContextKind.MOCK
    assert official.context_kind is ContextKind.OFFICIAL
    assert qualification.context_kind is ContextKind.QUALIFICATION
    assert fixture.context_kind is ContextKind.FIXTURE_OFFICIAL


def test_frozen_representative_vector_for_every_context_kind() -> None:
    role = RoleKey("batch_order")
    outputs = {
        ContextKind.MOCK: derive_mock_seed(
            _mock_context(), role, DRAW_INDEX
        ).as_backend_bytes(),
        ContextKind.OFFICIAL: derive_official_seed(
            _official_context(), SeedDomain.OFFICIAL_EVAL, role, DRAW_INDEX
        ).as_backend_bytes(),
        ContextKind.FIXTURE_OFFICIAL: derive_fixture_official_seed(
            _fixture_context(), SeedDomain.OFFICIAL_EVAL, role, DRAW_INDEX
        ).as_backend_bytes(),
        ContextKind.QUALIFICATION: derive_qualification_seed(
            _qualification_context(), SeedDomain.REFERENCE, role, DRAW_INDEX
        ).as_backend_bytes(),
    }
    assert outputs == GOLDEN_CONTEXT_SEEDS
    assert len(set(outputs.values())) == 4


@pytest.mark.parametrize(
    "domain",
    [
        SeedDomain.MOCK,
        SeedDomain.REFERENCE,
        SeedDomain.DOSSIER,
    ],
)
def test_official_and_fixture_reject_nonofficial_domains(domain: SeedDomain) -> None:
    role = RoleKey("generator_sampling")
    with pytest.raises(SeedValidationError, match="official seed derivation"):
        derive_official_seed(_official_context(), domain, role, 0)
    with pytest.raises(SeedValidationError, match="fixture seed derivation"):
        derive_fixture_official_seed(_fixture_context(), domain, role, 0)


@pytest.mark.parametrize(
    "domain",
    [
        SeedDomain.MOCK,
        SeedDomain.OFFICIAL_TRAIN,
        SeedDomain.OFFICIAL_EVAL,
        SeedDomain.OFFICIAL_STRESS,
    ],
)
def test_qualification_rejects_mock_and_official_domains(domain: SeedDomain) -> None:
    with pytest.raises(SeedValidationError, match="qualification seed derivation"):
        derive_qualification_seed(
            _qualification_context(), domain, RoleKey("generator_sampling"), 0
        )


def test_typed_derivation_entry_points_reject_crossed_contexts_and_raw_values() -> None:
    role = RoleKey("generator_sampling")
    with pytest.raises(SeedValidationError):
        derive_mock_seed(_official_context(), role, 0)  # type: ignore[arg-type]
    with pytest.raises(SeedValidationError):
        derive_mock_seed(_mock_context(), "generator_sampling", 0)  # type: ignore[arg-type]
    with pytest.raises(SeedValidationError):
        derive_official_seed(
            _fixture_context(), SeedDomain.OFFICIAL_EVAL, role, 0  # type: ignore[arg-type]
        )
    with pytest.raises(SeedValidationError):
        derive_fixture_official_seed(
            _official_context(), SeedDomain.OFFICIAL_EVAL, role, 0  # type: ignore[arg-type]
        )
    with pytest.raises(SeedValidationError):
        derive_qualification_seed(
            _mock_context(), SeedDomain.REFERENCE, role, 0  # type: ignore[arg-type]
        )
    with pytest.raises(SeedValidationError):
        derive_official_seed(
            _official_context(), "official_eval", role, 0  # type: ignore[arg-type]
        )


def test_every_context_type_crossing_rejects_for_every_entry_point() -> None:
    role = RoleKey("generator_sampling")
    contexts = [
        _mock_context(),
        _official_context(),
        _fixture_context(),
        _qualification_context(),
    ]
    requests = [
        (MockContext, lambda context: derive_mock_seed(context, role, 0)),
        (
            OfficialContext,
            lambda context: derive_official_seed(
                context, SeedDomain.OFFICIAL_EVAL, role, 0
            ),
        ),
        (
            FixtureOfficialContext,
            lambda context: derive_fixture_official_seed(
                context, SeedDomain.OFFICIAL_EVAL, role, 0
            ),
        ),
        (
            QualificationContext,
            lambda context: derive_qualification_seed(
                context, SeedDomain.REFERENCE, role, 0
            ),
        ),
    ]
    for accepted_type, request in requests:
        for context in contexts:
            if type(context) is accepted_type:
                assert type(request(context)) is DerivedSeed
            else:
                with pytest.raises(SeedValidationError):
                    request(context)


class _IntSubclass(int):
    pass


@pytest.mark.parametrize("draw_index", [0, (1 << 64) - 1])
def test_draw_index_accepts_exact_unsigned_64_bit_boundary(draw_index: int) -> None:
    result = derive_official_seed(
        _official_context(),
        SeedDomain.OFFICIAL_EVAL,
        RoleKey("generator_sampling"),
        draw_index,
    )
    assert len(result.as_backend_bytes()) == 32


@pytest.mark.parametrize(
    "draw_index",
    [-1, 1 << 64, True, False, 1.0, "1", _IntSubclass(7), None],
)
def test_draw_index_rejects_negative_overflow_boolean_and_noninteger(
    draw_index: object,
) -> None:
    with pytest.raises(CanonicalEncodingError):
        derive_official_seed(
            _official_context(),
            SeedDomain.OFFICIAL_EVAL,
            RoleKey("generator_sampling"),
            draw_index,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "overrides",
    [
        {"challenge_key": ChallengeKey("darcy_2d", "1.2")},
        {"challenge_key": ChallengeKey("burgers_1d", "1.3")},
        {"generator_version": "gen-v1.3"},
        {"generator_digest": "sha256:" + "33" * 32},
        {"scoring_version": "score_v4"},
        {"scoring_digest": "sha256:" + "44" * 32},
        {"evaluation_binding": EvaluationBinding(bytes(range(31, -1, -1)))},
    ],
)
def test_every_pinned_identity_field_changes_seed_and_commitment(
    overrides: dict[str, object],
) -> None:
    role = RoleKey("generator_sampling")
    baseline = _official_context()
    changed = _official_context(pin=_pin(**overrides))

    baseline_seed = derive_official_seed(baseline, SeedDomain.OFFICIAL_EVAL, role, 7)
    changed_seed = derive_official_seed(changed, SeedDomain.OFFICIAL_EVAL, role, 7)
    baseline_commitment = create_official_exam_projection(baseline).exam_commitment
    changed_commitment = create_official_exam_projection(changed).exam_commitment

    assert changed_seed != baseline_seed
    assert changed_commitment != baseline_commitment


def test_domain_role_and_draw_are_independently_separated() -> None:
    context = _official_context()
    baseline = derive_official_seed(
        context, SeedDomain.OFFICIAL_EVAL, RoleKey("generator_sampling"), 7
    )
    changes = [
        derive_official_seed(
            context, SeedDomain.OFFICIAL_TRAIN, RoleKey("generator_sampling"), 7
        ),
        derive_official_seed(
            context, SeedDomain.OFFICIAL_STRESS, RoleKey("generator_sampling"), 7
        ),
        derive_official_seed(
            context, SeedDomain.OFFICIAL_EVAL, RoleKey("batch_order"), 7
        ),
        derive_official_seed(
            context, SeedDomain.OFFICIAL_EVAL, RoleKey("generator_sampling"), 8
        ),
    ]
    assert all(changed != baseline for changed in changes)
    assert (
        len(
            {
                baseline.as_backend_bytes(),
                *(value.as_backend_bytes() for value in changes),
            }
        )
        == 5
    )


def test_exam_root_and_commitment_are_independent_of_role_domain_and_draw_calls() -> (
    None
):
    context = _official_context()
    before = create_official_exam_projection(context).exam_commitment
    role = RoleKey("generator_sampling")
    for domain in (
        SeedDomain.OFFICIAL_TRAIN,
        SeedDomain.OFFICIAL_EVAL,
        SeedDomain.OFFICIAL_STRESS,
    ):
        for draw_index in (0, 1, (1 << 64) - 1):
            derive_official_seed(context, domain, role, draw_index)
    after = create_official_exam_projection(context).exam_commitment
    assert after == before
    assert _derive_private_exam_root(context)._copy_bytes() not in {
        derive_official_seed(
            context, SeedDomain.OFFICIAL_EVAL, role, 7
        ).as_backend_bytes(),
        derive_official_seed(
            context, SeedDomain.OFFICIAL_TRAIN, role, 7
        ).as_backend_bytes(),
    }


def test_identical_official_inputs_reproduce_across_provider_instances() -> None:
    first = acquire_official_context(_FixedProvider(), _pin())
    second = acquire_official_context(_FixedProvider(), _pin())
    request = (SeedDomain.OFFICIAL_EVAL, RoleKey("generator_sampling"), 7)
    assert derive_official_seed(first, *request) == derive_official_seed(
        second, *request
    )
    assert (
        create_official_exam_projection(first).exam_commitment
        == create_official_exam_projection(second).exam_commitment
    )


def test_entropy_change_changes_seed_and_commitment() -> None:
    baseline = _official_context()
    changed = _official_context(entropy=OTHER_ENTROPY_BYTES)
    role = RoleKey("generator_sampling")
    assert derive_official_seed(
        baseline, SeedDomain.OFFICIAL_EVAL, role, 7
    ) != derive_official_seed(changed, SeedDomain.OFFICIAL_EVAL, role, 7)
    assert (
        create_official_exam_projection(baseline).exam_commitment
        != create_official_exam_projection(changed).exam_commitment
    )


def test_failed_request_and_retry_with_same_context_are_stateless() -> None:
    context = _official_context()
    role = RoleKey("generator_sampling")
    expected = derive_official_seed(context, SeedDomain.OFFICIAL_EVAL, role, DRAW_INDEX)
    with pytest.raises(CanonicalEncodingError):
        derive_official_seed(context, SeedDomain.OFFICIAL_EVAL, role, -1)
    assert (
        derive_official_seed(context, SeedDomain.OFFICIAL_EVAL, role, DRAW_INDEX)
        == expected
    )


def test_call_order_mock_query_count_failures_and_global_rng_do_not_influence_official(
    monkeypatch,
) -> None:
    official = _official_context()
    mock = _mock_context()
    role = RoleKey("generator_sampling")
    domains = (
        SeedDomain.OFFICIAL_TRAIN,
        SeedDomain.OFFICIAL_EVAL,
        SeedDomain.OFFICIAL_STRESS,
    )
    expected = {
        domain: derive_official_seed(official, domain, role, 7) for domain in domains
    }

    strategy = {
        "schema_version": "1.0",
        "challenge_id": "burgers_1d",
        "backbone": "fno",
        "parameters": {"width": 16},
    }
    random.seed(999)
    for _ in range(128):
        random.random()
        derive_mock_seed(mock, RoleKey("augmentation"), _)
    for _ in range(16):
        with pytest.raises(SeedValidationError):
            derive_mock_seed(mock, "augmentation", _)  # type: ignore[arg-type]
    strategy["parameters"]["width"] = 128  # type: ignore[index]
    strategy["parameters"]["optimizer"] = "adam"  # type: ignore[index]
    assert not hasattr(official, "strategy")
    assert not hasattr(official.pin, "strategy")
    monkeypatch.setenv("CARBON_VALIDATOR_HOTKEY", "validator-that-must-not-bind")
    monkeypatch.setenv("CARBON_MINER_HOTKEY", "miner-that-must-not-bind")
    monkeypatch.setenv("CARBON_SEED", "ambient-value-that-must-not-bind")
    with pytest.raises(OfficialEntropyUnavailable):
        acquire_official_context(
            _RaisingProvider(BeaconConflictError("retry conflict")), _pin()
        )

    actual = {
        domain: derive_official_seed(official, domain, role, 7)
        for domain in reversed(domains)
    }
    assert actual == expected


def test_derivation_does_not_advance_python_random_state() -> None:
    context = _official_context()
    random.seed(123456789)
    before = random.getstate()
    for draw_index in range(32):
        derive_official_seed(
            context,
            SeedDomain.OFFICIAL_EVAL,
            RoleKey("generator_sampling"),
            draw_index,
        )
    assert random.getstate() == before


def test_thread_scheduling_does_not_influence_derivation() -> None:
    context = _official_context()
    role = RoleKey("batch_order")
    expected = derive_official_seed(context, SeedDomain.OFFICIAL_EVAL, role, DRAW_INDEX)

    def derive(_: int) -> DerivedSeed:
        return derive_official_seed(context, SeedDomain.OFFICIAL_EVAL, role, DRAW_INDEX)

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(derive, range(128)))
    assert results == [expected] * 128


def test_ambient_pid_environment_and_process_randomness_are_not_api_inputs(
    monkeypatch,
) -> None:
    context = _official_context()
    role = RoleKey("generator_sampling")
    before = derive_official_seed(context, SeedDomain.OFFICIAL_EVAL, role, DRAW_INDEX)
    observed_pid = os.getpid()
    monkeypatch.setenv("CARBON_RUN_NONCE", str(observed_pid))
    monkeypatch.setenv("CARBON_BLOCK_HASH", "sha256:" + "ff" * 32)
    monkeypatch.setattr(os, "getpid", lambda: observed_pid + 1000)
    monkeypatch.setattr(time, "time", lambda: 4_102_444_800.0)
    random.seed(os.urandom(32))
    after = derive_official_seed(context, SeedDomain.OFFICIAL_EVAL, role, DRAW_INDEX)
    assert after == before


def test_validator_and_miner_identity_are_absent_from_all_public_inputs() -> None:
    functions = (
        SeedPin,
        acquire_official_context,
        acquire_fixture_official_context,
        derive_mock_seed,
        derive_official_seed,
        derive_fixture_official_seed,
        derive_qualification_seed,
        create_official_exam_projection,
        create_fixture_official_exam_projection,
    )
    forbidden = {
        "validator_hotkey",
        "validator_identity",
        "miner_hotkey",
        "miner_identity",
        "strategy",
        "run_nonce",
        "block_hash",
        "retry_count",
    }
    for function in functions:
        assert forbidden.isdisjoint(inspect.signature(function).parameters)


def test_seed_info_has_exact_tag_order_lengths_and_big_endian_draw() -> None:
    fields = _fields(GOLDEN_SEED_INFO, SEED_INFO_HEADER)
    assert [tag for tag, _ in fields] == list(range(0x01, 0x0D))
    assert fields[0][1] == b"official"
    assert fields[1][1] == b"carbon.seed.hkdf-sha256.v1"
    assert fields[8][1] == BINDING_BYTES
    assert fields[9][1] == b"official_eval"
    assert fields[10][1] == b"batch_order"
    assert fields[11][1] == b"\x01\x02\x03\x04\x05\x06\x07\x08"
    assert int.from_bytes(fields[11][1], "big") == DRAW_INDEX


def test_schema_local_tag_0a_has_two_exact_meanings() -> None:
    seed_fields = _fields(GOLDEN_SEED_INFO, SEED_INFO_HEADER)
    root_fields = _fields(GOLDEN_EXAM_ROOT_INFO, EXAM_ROOT_INFO_HEADER)
    commitment_fields = _fields(GOLDEN_COMMITMENT_DOCUMENT, EXAM_COMMITMENT_HEADER)
    assert seed_fields[-3] == (0x0A, b"official_eval")
    assert root_fields[-1][0] == 0x09
    assert commitment_fields[-1] == (0x0A, GOLDEN_PRIVATE_EXAM_ROOT)
    assert [tag for tag, _ in root_fields] == list(range(0x01, 0x0A))
    assert [tag for tag, _ in commitment_fields] == list(range(0x01, 0x0B))
    _validate_seed_info(GOLDEN_SEED_INFO)
    _validate_exam_root_info(GOLDEN_EXAM_ROOT_INFO)
    _validate_exam_commitment_document(GOLDEN_COMMITMENT_DOCUMENT)


@pytest.mark.parametrize(
    "document",
    [
        bytearray(GOLDEN_SEED_INFO),
        memoryview(GOLDEN_SEED_INFO),
        GOLDEN_SEED_INFO.decode("latin1"),
        None,
    ],
)
def test_seed_info_validator_requires_exact_bytes(document: object) -> None:
    with pytest.raises(CanonicalEncodingError, match="invalid canonical seed-info"):
        _validate_seed_info(document)


def test_seed_info_rejects_hostile_structure() -> None:
    fields = _fields(GOLDEN_SEED_INFO, SEED_INFO_HEADER)
    duplicate = fields.copy()
    duplicate[1] = (0x01, duplicate[1][1])
    reordered = fields.copy()
    reordered[2], reordered[3] = reordered[3], reordered[2]
    unknown = fields.copy()
    unknown[-1] = (0x0D, unknown[-1][1])
    documents = [
        b"x" + GOLDEN_SEED_INFO[1:],
        GOLDEN_SEED_INFO[: len(SEED_INFO_HEADER) - 1],
        GOLDEN_SEED_INFO[: len(SEED_INFO_HEADER) + 3],
        GOLDEN_SEED_INFO[:-1],
        GOLDEN_SEED_INFO + b"\x00",
        _document(SEED_INFO_HEADER, fields[:-1]),
        _document(SEED_INFO_HEADER, fields + [(0x0D, b"unknown")]),
        _document(SEED_INFO_HEADER, duplicate),
        _document(SEED_INFO_HEADER, reordered),
        _document(SEED_INFO_HEADER, unknown),
    ]
    malformed_length = bytearray(GOLDEN_SEED_INFO)
    length_offset = len(SEED_INFO_HEADER) + 1
    malformed_length[length_offset : length_offset + 4] = (0xFFFFFFFF).to_bytes(
        4, "big"
    )
    documents.append(bytes(malformed_length))
    for document in documents:
        with pytest.raises(CanonicalEncodingError, match="invalid canonical seed-info"):
            _validate_seed_info(document)


@pytest.mark.parametrize(
    ("tag", "payload"),
    [
        (0x01, b"Official"),
        (0x01, b"mock"),
        (0x01, b"\xff"),
        (0x02, b"carbon.seed.hkdf-sha256.v2"),
        (0x03, b"Burgers_1d"),
        (0x03, b"burgers\xff"),
        (0x04, b"1/2"),
        (0x05, b"gen version"),
        (0x05, b"gen-\xff"),
        (0x06, b"sha256:" + b"A" * 64),
        (0x06, b"11" * 32),
        (0x07, b"score version"),
        (0x08, b"sha256:" + b"2" * 63),
        (0x09, BINDING_BYTES[:-1]),
        (0x09, BINDING_BYTES + b"x"),
        (0x0A, b"reference"),
        (0x0A, b"official_unknown"),
        (0x0A, b"official_\xff"),
        (0x0B, b"BatchOrder"),
        (0x0B, b"batch__order"),
        (0x0B, b"batch_\xff"),
        (0x0C, b"\x00" * 7),
        (0x0C, b"\x00" * 9),
    ],
)
def test_seed_info_rejects_hostile_field_values(tag: int, payload: bytes) -> None:
    document = _with_payload(GOLDEN_SEED_INFO, SEED_INFO_HEADER, tag, payload)
    with pytest.raises(CanonicalEncodingError, match="invalid canonical seed-info"):
        _validate_seed_info(document)


def test_exam_root_info_rejects_domain_fields_and_hostile_documents() -> None:
    fields = _fields(GOLDEN_EXAM_ROOT_INFO, EXAM_ROOT_INFO_HEADER)
    duplicate = fields.copy()
    duplicate[1] = (0x01, duplicate[1][1])
    reordered = fields.copy()
    reordered[0], reordered[1] = reordered[1], reordered[0]
    documents = [
        GOLDEN_SEED_INFO,
        GOLDEN_EXAM_ROOT_INFO[:-1],
        GOLDEN_EXAM_ROOT_INFO + b"\x00",
        _document(EXAM_ROOT_INFO_HEADER, fields[:-1]),
        _document(EXAM_ROOT_INFO_HEADER, fields + [(0x0A, b"official_eval")]),
        _document(EXAM_ROOT_INFO_HEADER, duplicate),
        _document(EXAM_ROOT_INFO_HEADER, reordered),
        _with_payload(
            GOLDEN_EXAM_ROOT_INFO,
            EXAM_ROOT_INFO_HEADER,
            0x09,
            BINDING_BYTES[:-1],
        ),
        _with_payload(
            GOLDEN_EXAM_ROOT_INFO, EXAM_ROOT_INFO_HEADER, 0x03, b"Burgers_1d"
        ),
    ]
    for document in documents:
        with pytest.raises(
            CanonicalEncodingError, match="invalid canonical exam-root-info"
        ):
            _validate_exam_root_info(document)


def test_commitment_document_rejects_wrong_private_root_tag_or_length() -> None:
    fields = _fields(GOLDEN_COMMITMENT_DOCUMENT, EXAM_COMMITMENT_HEADER)
    duplicate = fields.copy()
    duplicate[-1] = (0x09, duplicate[-1][1])
    reordered = fields.copy()
    reordered[-1], reordered[-2] = reordered[-2], reordered[-1]
    documents = [
        GOLDEN_EXAM_ROOT_INFO,
        GOLDEN_COMMITMENT_DOCUMENT[:-1],
        GOLDEN_COMMITMENT_DOCUMENT + b"\x00",
        _document(EXAM_COMMITMENT_HEADER, fields[:-1]),
        _document(EXAM_COMMITMENT_HEADER, fields + [(0x0B, b"unknown")]),
        _document(EXAM_COMMITMENT_HEADER, duplicate),
        _document(EXAM_COMMITMENT_HEADER, reordered),
        _with_payload(
            GOLDEN_COMMITMENT_DOCUMENT,
            EXAM_COMMITMENT_HEADER,
            0x0A,
            GOLDEN_PRIVATE_EXAM_ROOT[:-1],
        ),
        _with_payload(
            GOLDEN_COMMITMENT_DOCUMENT,
            EXAM_COMMITMENT_HEADER,
            0x0A,
            GOLDEN_PRIVATE_EXAM_ROOT + b"x",
        ),
    ]
    wrong_tag = fields.copy()
    wrong_tag[-1] = (0x0D, wrong_tag[-1][1])
    documents.append(_document(EXAM_COMMITMENT_HEADER, wrong_tag))
    for document in documents:
        with pytest.raises(
            CanonicalEncodingError, match="invalid canonical exam-commitment"
        ):
            _validate_exam_commitment_document(document)


def test_context_domain_matrix_is_enforced_by_canonical_encoder_too() -> None:
    role = RoleKey("generator_sampling")
    cases = [
        (ContextKind.MOCK, SeedDomain.OFFICIAL_EVAL),
        (ContextKind.OFFICIAL, SeedDomain.MOCK),
        (ContextKind.FIXTURE_OFFICIAL, SeedDomain.REFERENCE),
        (ContextKind.QUALIFICATION, SeedDomain.OFFICIAL_STRESS),
    ]
    for context_kind, domain in cases:
        with pytest.raises(CanonicalEncodingError):
            _encode_seed_info(context_kind, _pin(), domain, role, 0)


def test_no_generic_mode_switch_or_master_secret_helper_exists() -> None:
    from carbon import seeding

    assert not hasattr(seeding, "derive_seed")
    assert not hasattr(seeding, "master_secret")
    assert not hasattr(seeding, "local_mode")
    assert not hasattr(seeding, "mode")
