"""S3 protected-door metadata identity and executable resolver containment."""

import hashlib
import json
import shutil

import pytest

from carbon.reconstruction import capability_registry as cr
from carbon.reconstruction import composition_registry as metadata
from carbon.reconstruction import development_composition as dc
from carbon.reconstruction import development_variants as dv


def test_composition_is_development_identity_by_name_and_digest_only():
    registry = metadata.registry()
    for name, digest in registry["versions"].items():
        document = metadata.document(name)
        assert metadata.document(digest) == document
        assert cr.is_development_composition(name)
        assert cr.is_development_variant(digest)
        assert cr.is_development_variant(name)
        resolved = dc.registered(digest)
        assert resolved == dc.registered(name)
        assert resolved.digest == digest and resolved.version == name
        assert {v.level for v in resolved.variants} == {
            e["level"] for e in document["composes"]
        }
    for value in (None, [], {}, 4, "sha256:" + "0" * 64, "../escape"):
        assert metadata.document(value) is None
        assert not cr.is_development_composition(value)
        with pytest.raises(dv.VariantRefused):
            dc.registered(value)


def test_parent_document_tampering_fails_closed_in_metadata_and_resolver(
    tmp_path, monkeypatch
):
    shutil.copytree(metadata.DIRECTORY, tmp_path / "compositions")
    directory = tmp_path / "compositions"
    name, digest = next(iter(metadata.registry(directory)["versions"].items()))
    path = directory / (name + ".json")
    document = json.loads(path.read_text(encoding="utf-8"))
    document["participant_code"] = True
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(RuntimeError, match="changed"):
        metadata.document(digest, directory)
    monkeypatch.setattr(dc, "DIRECTORY", directory)
    with pytest.raises(dv.VariantRefused):
        dc.registered(digest)


@pytest.mark.parametrize(
    "mutation",
    ["duplicate_digest", "bad_current", "bad_scope", "bad_base", "duplicate_level"],
)
def test_registered_metadata_cannot_become_permission_from_malformed_records(
    tmp_path, mutation
):
    shutil.copytree(metadata.DIRECTORY, tmp_path / "compositions")
    directory = tmp_path / "compositions"
    registry = metadata.registry(directory)
    name = next(iter(registry["versions"]))
    doc = metadata.document(name, directory)
    if mutation == "duplicate_digest":
        registry["versions"]["duplicate"] = registry["versions"][name]
    elif mutation == "bad_current":
        registry["current"][doc["challenge"]] = "missing"
    else:
        if mutation == "bad_scope":
            doc["scope"] = "LIVE"
        elif mutation == "bad_base":
            doc["base_contract"]["record_sequence"] = True
        else:
            doc["composes"].append(doc["composes"][0])
        raw = json.dumps(doc, sort_keys=True, separators=(",", ":")).encode()
        registry["versions"][name] = "sha256:" + hashlib.sha256(raw).hexdigest()
        (directory / (name + ".json")).write_bytes(raw)
    (directory / "registry.json").write_text(json.dumps(registry), encoding="utf-8")
    with pytest.raises(RuntimeError):
        metadata.document(name, directory)


def test_metadata_recognition_does_not_open_the_base_contract():
    from carbon.reconstruction.capability_registry import DevelopmentVariantNotServed

    for name, digest in metadata.registry()["versions"].items():
        for value in (name, digest):
            with pytest.raises(DevelopmentVariantNotServed):
                cr.contract(value)
    assert (
        cr.contract(cr.BATTERY_CHALLENGE).digest
        == dc.load(cr.BATTERY_CHALLENGE).base_contract_digest
    )
