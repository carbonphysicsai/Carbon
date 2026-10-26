"""The first F08 copy was refused at issuance: `verify_copy` compared the manifest's pins
against the kit's `private_roles`, but the grader pack's reference_rows and solver_evidence
are written by `physical.pack_documents`. Validator ruling, option (a): the expected roles
are recomputed from the canonical bank with that same function, never from the pack's own
bytes and never from the kit. Real grader roles for all four Challenges."""

from __future__ import annotations

import json

import pytest
from test_copy_delivery import MASTER, WINDOW, _canonical_pack, _sha
from test_copy_delivery import _grader_roles as _roles
from test_copy_package import FORMATS, HOTKEYS

from carbon.challenge_kit import physical_pack
from carbon.challenge_validator import answer_key as ak
from carbon.challenge_validator import copy_delivery as delivery
from carbon.challenge_validator import sealed_pack_import as spi
from carbon.scoring import copy_package as cp
from carbon.scoring import physical_dual_pack as physical
from carbon.scoring import sealed_batch_source as source

IMAGE = "sha256:" + "0" * 64


@pytest.fixture(scope="module")
def producer(tmp_path_factory):
    return ak.ProducerKey.create(str(tmp_path_factory.mktemp("k") / "producer.key"))


def _canonical_bank(name):
    challenge, version, build, _builder, kit = FORMATS[name]
    document, records = build()
    raw, _src, _fp = cp.canonical_batch(challenge, version, document, records)
    carried = json.loads(raw)
    bank = source._build(
        challenge, kit, carried["document"], carried["records"], version
    )
    return challenge, version, kit, bank


def _grader_roles(name):
    challenge, version, kit, bank = _canonical_bank(name)
    return _roles(challenge, version, kit, bank)


def _rewritten(name, roles):
    """The canonical pack of ``_canonical_pack(name)`` with its COPY_ROLES replaced by
    ``roles`` (manifest pins and files), keeping its shape."""
    challenge, version, manifest_bytes, files, carried = _canonical_pack(name)
    manifest = json.loads(manifest_bytes)
    for role in delivery.COPY_ROLES:
        path = manifest["private"][role]["path"]
        files[path] = roles[role]
        manifest["private"][role]["sha256"] = _sha(roles[role])
    raw = (json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n").encode()
    return challenge, version, raw, files, carried


def _issue(producer, parts, hotkey=HOTKEYS[0]):
    challenge, version, manifest, files, carried = parts
    return delivery.issue_copy(
        producer,
        MASTER,
        challenge=challenge,
        version=version,
        canonical_manifest=manifest,
        canonical_files=files,
        document=carried["document"],
        records=carried["records"],
        hotkey=hotkey,
        window=WINDOW,
    )


@pytest.mark.parametrize("name", sorted(FORMATS))
def test_the_expected_roles_are_the_real_grader_packs(name):
    challenge, version, kit, bank = _canonical_bank(name)
    assert delivery.expected_roles(challenge, version, kit, bank) == _grader_roles(name)


def test_f08_expected_roles_equal_the_bytes_write_sealed_pack_writes(tmp_path):
    """The reported cause: on F08 the kit's reference_rows/solver_evidence differ from the
    pack's; the expected roles are the pack's."""
    from carbon.scoring import f08_sealed_dual_pack as f08

    challenge, version, kit, bank = _canonical_bank("f08")
    f08.write_sealed_pack(
        tmp_path / "pack", bank, version=version, inference_image_id=IMAGE
    )
    written = {
        role: (tmp_path / "pack" / "private" / f"{role}.json").read_bytes()
        for role in ("reference_rows", "solver_evidence")
    }
    expected = delivery.expected_roles(challenge, version, kit, bank)
    kit_roles = kit.private_roles(bank)
    for role, body in written.items():
        assert expected[role] == body
        assert kit_roles[role] != body  # the pre-fix comparison would refuse this
    case_bank = (tmp_path / "pack" / "private" / "case_bank.npz").read_bytes()
    assert expected["case_bank"] == case_bank


@pytest.mark.parametrize("name", sorted(FORMATS))
def test_a_real_grader_pack_issues_and_imports(tmp_path, producer, name):
    parts = _rewritten(name, _grader_roles(name))
    package = _issue(producer, parts)
    store = spi.SealedPackStore(tmp_path / "store")
    digest = delivery.import_copy(
        store, package, producer.public_key, hotkey=HOTKEYS[0]
    )
    assert digest == _sha(parts[2])
    assert store.delivered(digest, parts[0], parts[1])


@pytest.mark.parametrize("name", sorted(FORMATS))
def test_a_tampered_reference_rows_pin_is_refused(tmp_path, producer, name):
    roles = _grader_roles(name)
    roles["reference_rows"] = roles["reference_rows"] + b" "
    package = _issue(producer, _rewritten(name, roles))
    store = spi.SealedPackStore(tmp_path / "store")
    with pytest.raises(ak.AnswerKeyRefused) as refused:
        delivery.import_copy(store, package, producer.public_key, hotkey=HOTKEYS[0])
    assert refused.value.code == "copy_canonical_roles"


@pytest.mark.parametrize("name", sorted(FORMATS))
def test_a_kit_roles_only_manifest_is_refused_on_a_grader_pack(
    tmp_path, producer, name
):
    grader = _grader_roles(name)
    _challenge, _version, _kit, bank = _canonical_bank(name)
    kit_roles = FORMATS[name][4].private_roles(bank)
    if all(kit_roles[r] == grader[r] for r in delivery.COPY_ROLES):
        pytest.skip("this Challenge's kit roles equal its grader pack's")
    package = _issue(producer, _canonical_pack(name, kit_roles=True))
    store = spi.SealedPackStore(tmp_path / "store")
    with pytest.raises(ak.AnswerKeyRefused):
        delivery.import_copy(store, package, producer.public_key, hotkey=HOTKEYS[0])


@pytest.mark.parametrize("name", sorted(FORMATS))
def test_the_bank_roles_do_not_depend_on_the_grading_platform(name):
    challenge, version, _kit, bank = _canonical_bank(name)
    adapter = source._adapter(challenge, bank, version, None)
    public = physical_pack.public_roles(challenge, version)

    def documents(image):
        return physical.pack_documents(
            adapter,
            bank=bank,
            physics=physical_pack.physics_contract(challenge, version),
            interface_raw=public["interface"],
            train_raw=public["train"],
            limits_raw=public["important_limit_definition"],
            objective_raw=public["design_objective"],
            platform=physical.leg_minimum_platform(image, physical.DEVICE_CLASS),
            minimums="calibration",
        )

    one, other = documents(IMAGE), documents("sha256:" + "7" * 64)
    for role in ("reference_rows", "solver_evidence"):
        assert one[role] == other[role]
