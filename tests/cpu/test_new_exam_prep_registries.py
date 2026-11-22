"""New-exam prep #2 and #11 host side (v2 ruling 22 Nov 2026 00:12:09Z; case-procs design NEW_EXAM_PREP_CASEPROCS_DESIGN).

Claims: (#2) `producer_successor_v2` reads only its OWN registry (never v1's, whose L2 would refuse Motor 1.8's live row),
honours a row for ANY registered version only with a sha-checked kept-grade proof, one row per version, and never
raises; the shipped registry is empty. (#11) `subset_repeat_registry` reads a new version's strata from its overlay
entry's dispatch config, bound to the installed entry digest; a version in both the 1.8 code table and the overlay
refuses; Motor 1.8's definitions come from code unchanged. Golden: Motor 1.8's producer digest is unchanged, and
neither new module is in any live version's producer files. Synthetic fixtures only.
"""

from __future__ import annotations

import hashlib
import importlib
import inspect
import json
from pathlib import Path

import pytest

from carbon.challenge_kit import version_overlay
from carbon.scoring import producer_successor as v1
from carbon.scoring import producer_successor_v2 as v2
from carbon.scoring import subset_repeat_evidence as code
from carbon.scoring import subset_repeat_registry as registry

ROOT = Path(__file__).resolve().parents[2]
OLD = "sha256:" + "a" * 64
NEW = "sha256:" + "b" * 64


# ---------------------------------------------------------------- #2 producer_successor_v2


def _proof(tmp_path, body=b"kept grades: every A, D and total equal, |diff| 0\n"):
    folder = tmp_path / "proofs"
    folder.mkdir(exist_ok=True)
    (folder / "proof.json").write_bytes(body)
    return {
        "path": "proofs/proof.json",
        "sha256": "sha256:" + hashlib.sha256(body).hexdigest(),
    }


def _registry(tmp_path, rows, *, schema=v2.SCHEMA, raw=None):
    path = tmp_path / "producer_successor_v2.json"
    path.write_text(
        raw if raw is not None else json.dumps({"schema": schema, "rows": rows})
    )
    return path


def _row(proof, **change):
    found = {
        "pack_producer_digest": OLD,
        "producer_digest": NEW,
        "v2_receipt": "2026-11-22T00:12:09Z v2",
        "kept_grade_proof": proof,
    }
    found.update(change)
    return found


def test_v2_reads_only_its_own_registry_never_v1s():
    assert v2.REGISTRY.name == "producer_successor_v2.json"
    assert v2.REGISTRY != v1.REGISTRY
    assert v2.SCHEMA != v1.SCHEMA
    source = inspect.getsource(v2)
    assert (
        "import producer_successor\n" not in source
        and "producer_successor import" not in source
    )
    assert '"producer_successor.json"' not in source


def test_the_shipped_v2_registry_is_empty_and_grants_nothing():
    document = json.loads(v2.REGISTRY.read_text(encoding="utf-8"))
    assert document == {"schema": v2.SCHEMA, "rows": {}}
    assert v2.row("electric-motor-magnetics", "1.9") is None
    assert v2.binds("electric-motor-magnetics", "1.9", OLD, NEW) is False


def test_a_row_for_any_registered_version_with_a_matching_proof_binds(tmp_path):
    path = _registry(tmp_path, {"chip-cold-plate 1.9": _row(_proof(tmp_path))})
    assert v2.row("chip-cold-plate", "1.9", path=path, root=tmp_path) == {
        "pack_producer_digest": OLD,
        "producer_digest": NEW,
    }
    assert v2.binds("chip-cold-plate", "1.9", OLD, NEW, path=path, root=tmp_path)
    assert v2.binds(
        "chip-cold-plate", "1.9", NEW, NEW, path=path, root=tmp_path
    )  # equal: as v1
    assert not v2.binds(
        "chip-cold-plate", "1.9", OLD, "sha256:" + "c" * 64, path=path, root=tmp_path
    )
    assert v2.pinned_basis(
        "chip-cold-plate",
        "1.9",
        {"producer_digest": NEW, "x": 1},
        path=path,
        root=tmp_path,
    ) == {"producer_digest": OLD, "x": 1}


@pytest.mark.parametrize(
    "change",
    [
        {"producer_digest": OLD},  # pinned == producer
        {"pack_producer_digest": "sha256:short"},
        {"v2_receipt": "yesterday"},
        {"v2_receipt": "2026-11-22T00:12:09Z V2!"},
        {"kept_grade_proof": {"path": "proofs/proof.json"}},
        {
            "kept_grade_proof": {
                "path": "../proofs/proof.json",
                "sha256": "sha256:" + "0" * 64,
            }
        },
        {"kept_grade_proof": {"path": "/etc/passwd", "sha256": "sha256:" + "0" * 64}},
        {
            "kept_grade_proof": {
                "path": "proofs/missing.json",
                "sha256": "sha256:" + "0" * 64,
            }
        },
        {"extra": True},
    ],
)
def test_a_malformed_row_or_proof_is_no_row(tmp_path, change):
    path = _registry(
        tmp_path, {"chip-cold-plate 1.9": _row(_proof(tmp_path), **change)}
    )
    assert v2.row("chip-cold-plate", "1.9", path=path, root=tmp_path) is None
    assert not v2.binds("chip-cold-plate", "1.9", OLD, NEW, path=path, root=tmp_path)


def test_a_proof_whose_bytes_changed_is_no_row(tmp_path):
    proof = _proof(tmp_path)
    path = _registry(tmp_path, {"chip-cold-plate 1.9": _row(proof)})
    (tmp_path / "proofs" / "proof.json").write_bytes(b"edited after the receipt\n")
    assert v2.row("chip-cold-plate", "1.9", path=path, root=tmp_path) is None


def test_one_row_per_version_a_duplicate_key_refuses_the_registry(tmp_path):
    good = json.dumps(_row(_proof(tmp_path)))
    rows = f'{{"chip-cold-plate 1.9": {good}, "chip-cold-plate 1.9": {good}}}'
    raw = f'{{"schema": "{v2.SCHEMA}", "rows": {rows}}}'
    path = _registry(tmp_path, None, raw=raw)
    assert v2.row("chip-cold-plate", "1.9", path=path, root=tmp_path) is None


@pytest.mark.parametrize(
    "raw",
    [
        "not json",
        "[]",
        '{"schema": "carbon.exam.producer-successor.v1", "rows": {}}',
        '{"schema": 1}',
    ],
)
def test_a_missing_malformed_or_v1_registry_never_raises(tmp_path, raw):
    path = _registry(tmp_path, None, raw=raw)
    assert v2.row("chip-cold-plate", "1.9", path=path, root=tmp_path) is None
    assert v2.row("chip-cold-plate", "1.9", path=tmp_path / "absent.json") is None
    assert v2.binds(None, None, OLD, NEW, path=path) is False


# ---------------------------------------------------------------- #11 subset_repeat_registry


def _overlay(tmp_path, subset_repeat, *, key=("chip-cold-plate", "1.9")):
    entry = {
        "challenge_id": key[0],
        "version": key[1],
        "dispatch": {
            "module": "carbon.x",
            "sha256": "0" * 64,
            "config": {"subset_repeat": subset_repeat},
        },
    }
    path = tmp_path / "version_overlay.json"
    path.write_text(
        json.dumps(
            {
                "schema": version_overlay.SCHEMA,
                "versions": {f"{key[0]} {key[1]}": entry},
            }
        )
    )
    return path, version_overlay.canonical_digest(entry)


def _declared():
    return {
        "producer": "carbon.scoring.cooling19_dual_pack",
        "strata": {
            "probe_response": {"source": "cohort", "selector": "probe_response"},
            "gate_t": {
                "source": "in_range_outputs",
                "selector": ["t_max"],
                "every": True,
                "n": 12,
            },
        },
    }


def test_a_new_version_s_strata_come_from_its_bound_overlay_entry(tmp_path):
    path, digest = _overlay(tmp_path, _declared())

    def bound(challenge, version):  # the installed entry digest
        return digest

    key = ("chip-cold-plate", "1.9")
    assert registry.versions(
        path, installed_digest=bound
    ) == code.SUBSET_REPEAT_VERSIONS | {key}
    assert registry.is_subset_version(*key, path, installed_digest=bound)
    assert (
        registry.producer_module(*key, path, installed_digest=bound)
        == "carbon.scoring.cooling19_dual_pack"
    )
    strata = registry.definitions(*key, path, installed_digest=bound)
    assert strata["probe_response"] == code.Stratum("cohort", "probe_response")
    assert strata["gate_t"] == code.Stratum("in_range_outputs", ("t_max",), True, 12)


def test_an_entry_not_bound_to_the_installed_digest_refuses(tmp_path):
    path, _digest = _overlay(tmp_path, _declared())
    with pytest.raises(registry.SubsetRegistryRefused) as refused:
        registry.versions(path, installed_digest=lambda c, v: "sha256:" + "f" * 64)
    assert refused.value.code == "subset_repeat_overlay_unbound"

    def not_installed(c, v):
        raise version_overlay.OverlayRefused("not an overlay version")

    with pytest.raises(registry.SubsetRegistryRefused):
        registry.versions(path, installed_digest=not_installed)


def test_a_version_in_both_the_1_8_code_table_and_the_overlay_refuses(tmp_path):
    path, digest = _overlay(
        tmp_path, _declared(), key=("electric-motor-magnetics", "1.8")
    )
    with pytest.raises(registry.SubsetRegistryRefused) as refused:
        registry.versions(path, installed_digest=lambda c, v: digest)
    assert refused.value.code == "subset_repeat_version_in_both"


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d.update(producer="os.system"),
        lambda d: d.update(strata={}),
        lambda d: d["strata"].update(bad={"source": "cohort"}),
        lambda d: d["strata"].update(bad={"source": "nowhere", "selector": "x"}),
        lambda d: d["strata"].update(
            bad={"source": "in_range_outputs", "selector": "t_max"}
        ),
        lambda d: d["strata"].update(
            bad={"source": "cohort", "selector": "x", "every": True}
        ),
        lambda d: d["strata"].update(
            {code.SEALED_COHORT: {"source": "cohort", "selector": "x"}}
        ),
        lambda d: d.update(extra=1),
    ],
)
def test_a_malformed_declaration_refuses_typed(tmp_path, mutate):
    declared = _declared()
    mutate(declared)
    path, digest = _overlay(tmp_path, declared)
    with pytest.raises(registry.SubsetRegistryRefused):
        registry.versions(path, installed_digest=lambda c, v: digest)


def test_motor_1_8_comes_from_code_unchanged_and_no_overlay_declares_nothing(tmp_path):
    key = ("electric-motor-magnetics", "1.8")
    assert registry.definitions(*key, tmp_path / "absent.json") is code.STRATA[key]
    assert (
        registry.producer_module(*key, tmp_path / "absent.json") == code.PRODUCERS[key]
    )
    assert registry.versions(tmp_path / "absent.json") == code.SUBSET_REPEAT_VERSIONS
    with pytest.raises(code.SubsetRepeatRefused):
        registry.definitions("chip-cold-plate", "1.9", tmp_path / "absent.json")


# ---------------------------------------------------------------- golden: no live byte moved


def test_no_live_producer_byte_moves_and_neither_module_is_a_live_producer_file():
    importlib.import_module("carbon.challenge_kit.version_registry")
    importlib.import_module("carbon.scoring.motor_sealed_dual_pack")
    from carbon.scoring import motor18_dual_pack
    from carbon.scoring import physical_dual_pack as physical

    pins = json.loads(
        (
            ROOT / "scripts" / "validator_host_classes" / "producer_successor.json"
        ).read_text(encoding="utf-8")
    )["rows"]["electric-motor-magnetics 1.8"]
    assert motor18_dual_pack.producer_digest() == pins["producer_digest"]
    for name in (*v2.NEW_VERSION_PRODUCER_FILES, *registry.NEW_VERSION_PRODUCER_FILES):
        assert name not in motor18_dual_pack.FILES
        assert name not in physical._SHARED_FILES
