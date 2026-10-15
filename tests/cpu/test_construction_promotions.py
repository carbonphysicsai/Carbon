"""S4 public fixtures: record references grant no promotion or qualification."""

import copy
import json
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

import pytest

from carbon.reconstruction import capability_registry as cr
from carbon.reconstruction import composition_registry as metadata
from carbon.reconstruction import construction_promotions as promotions
from carbon.reconstruction import development_composition as dc

ROOT = Path(__file__).resolve().parents[2]
BATTERY = cr.BATTERY_CHALLENGE


def proposed():
    source = dc.load(BATTERY)
    return {
        "schema": promotions.RECORD_SCHEMA,
        "challenge": BATTERY,
        "capability": "physical_structure.structure_layers",
        "source": {
            "base_contract_digest": source.base_contract_digest,
            "composition_digest": source.digest,
        },
        "evidence": [
            {"record": "fixture-public-measurement", "digest": "sha256:" + "9" * 64}
        ],
        "decision": {
            "record": "fixture-owner-decision",
            "digest": "sha256:" + "8" * 64,
        },
        "target": promotions.TARGET,
    }


def recipe():
    return {
        "schema_version": "1.0",
        "challenge_id": BATTERY,
        "backbone": "mlp",
        "parameters": {
            "width": 8,
            "depth": 1,
            "steps": 24,
            "batch_size": 32,
            "polish_steps": 4,
            "optimizer_family": "muon",
            "muon_spectral": True,
            "quasi_newton_family": "lbfgs",
            "line_search": "backtracking",
        },
    }


def test_empty_set_keeps_every_base_and_historical_composition_byte_identical():
    assert promotions.promoted() == ()
    for challenge in cr.CONTRACTS:
        original = cr.contract(challenge)
        assert promotions.base_contract(challenge) is original
        assert promotions.base_contract(challenge).digest == original.digest
    for name, digest in metadata.registry()["versions"].items():
        original = metadata.document(name)
        result = promotions.composition_document(digest)
        assert json.dumps(result, sort_keys=True) == json.dumps(
            original, sort_keys=True
        )
        result["composes"].clear()
        assert promotions.composition_document(name) == original


def test_empty_application_keeps_actual_compiled_and_reconstructed_state_identical():
    from carbon.battery.worker import DirectBackend

    original = dc.compile(recipe())
    applied = promotions.compile(recipe())
    before, after_record = asdict(original), asdict(applied)
    before.pop("construction")
    after_record.pop("construction")
    assert after_record == before
    # asdict deep-copies the private compile seal into unequal new objects;
    # compare actual seal identity and canonical recipe semantics instead.
    assert applied.construction.token is original.construction.token
    assert applied.construction.supplied == original.construction.supplied
    assert applied.construction.document() == original.construction.document()
    assert applied.construction.recipe_digest == original.construction.recipe_digest
    backend = DirectBackend(ROOT)
    state, _ = backend.reconstruct(None, original.construction, 7, original.record)
    after, _ = backend.reconstruct(None, applied.construction, 7, applied.record)
    assert state == after


def test_record_is_bound_provenance_but_cannot_approve_its_own_measurement():
    candidate = proposed()
    result = promotions.record(candidate)
    assert result == candidate and result is not candidate
    candidate["evidence"].clear()
    assert result["evidence"]
    with pytest.raises(promotions.PromotionRefused, match="promotion_bar_unset"):
        promotions.promote(result)
    with pytest.raises(TypeError):
        promotions.promote(result, accepted=True)


@pytest.mark.parametrize(
    "change",
    [
        "schema",
        "target",
        "challenge",
        "capability",
        "base",
        "composition",
        "evidence",
        "duplicate",
        "decision",
        "claimed_pass",
    ],
)
def test_invalid_or_unbound_record_cannot_pass_structural_validation(change):
    value = proposed()
    if change in {"schema", "target", "challenge"}:
        value[change] = "unregistered"
    elif change == "capability":
        value[change] = {"claimed": True}
    elif change in {"base", "composition"}:
        value["source"][
            "base_contract_digest" if change == "base" else "composition_digest"
        ] = ("sha256:" + "0" * 64)
    elif change == "evidence":
        value[change] = []
    elif change == "duplicate":
        value["evidence"] *= 2
    elif change == "decision":
        value[change] = None
    else:
        value["measured_and_approved"] = True
    with pytest.raises(promotions.PromotionRefused):
        promotions.record(value)


def write_registry(path, **changes):
    value = {
        "schema": promotions.REGISTRY_SCHEMA,
        "scope": "DEVELOPMENT",
        "promotion_bar": None,
        "promotions": [],
    }
    value.update(changes)
    path.write_text(json.dumps(value), encoding="utf-8", newline="\n")


def test_a_changed_nonempty_registry_never_reuses_a_previous_empty_compile(
    tmp_path, monkeypatch
):
    path = tmp_path / "promotions.json"
    write_registry(path)
    monkeypatch.setattr(promotions, "REGISTRY", path)
    called = []
    monkeypatch.setattr(dc, "compile", lambda *a, **kw: called.append(kw) or "compiled")
    assert promotions.compile(recipe()) == "compiled"
    assert called == [{"check_budget": True}]
    write_registry(path, promotions=[proposed()])
    for action in (
        promotions.promoted,
        lambda: promotions.base_contract(BATTERY),
        lambda: promotions.composition_document(dc.load(BATTERY).digest),
        lambda: promotions.compile(recipe()),
    ):
        with pytest.raises(promotions.PromotionRefused, match="promotion_bar_unset"):
            action()
    assert len(called) == 1


@pytest.mark.parametrize(
    "bar", [True, False, "PASS", {}, {"owner_signed": True}, {"evidence": "MEASURED"}]
)
def test_no_json_claim_can_register_the_owner_bar(tmp_path, monkeypatch, bar):
    path = tmp_path / "promotions.json"
    write_registry(path, promotion_bar=bar)
    monkeypatch.setattr(promotions, "REGISTRY", path)
    with pytest.raises(promotions.PromotionRefused, match="promotion_bar_unregistered"):
        promotions.promoted()


@pytest.mark.parametrize(
    "raw",
    [
        "null",
        "{}",
        '{"schema":"wrong"}',
        '{"schema":"carbon.construction-promotions.v1","scope":"DEVELOPMENT","promotion_bar":null,"promotion_bar":null,"promotions":[]}',
        '{"schema":"carbon.construction-promotions.v1","scope":"DEVELOPMENT","promotion_bar":NaN,"promotions":[]}',
    ],
)
def test_missing_or_malformed_registry_is_not_an_implicit_empty_set(
    tmp_path, monkeypatch, raw
):
    path = tmp_path / "promotions.json"
    monkeypatch.setattr(promotions, "REGISTRY", path)
    with pytest.raises(
        promotions.PromotionRefused, match="promotion_registry_unavailable"
    ):
        promotions.promoted()
    path.write_text(raw, encoding="utf-8", newline="\n")
    with pytest.raises(promotions.PromotionRefused):
        promotions.promoted()


def test_record_source_cannot_rebind_another_base_or_challenge(monkeypatch):
    source = proposed()
    original = metadata.document

    def altered(value):
        doc = copy.deepcopy(original(value))
        doc["base_contract"]["record_sequence"] = 999
        return doc

    monkeypatch.setattr(metadata, "document", altered)
    with pytest.raises(
        promotions.PromotionRefused, match="promotion_source_unregistered"
    ):
        promotions.record(source)


def test_import_does_not_initialize_a_numerical_or_execution_runtime():
    subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; from carbon.reconstruction import construction_promotions; "
                "assert not {'numpy','jax','torch'} & sys.modules.keys()"
            ),
        ],
        cwd=ROOT,
        check=True,
    )


def test_installed_wheel_contains_the_empty_registry_outside_the_checkout(tmp_path):
    import os
    import zipfile

    wheels = tmp_path / "wheels"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "build",
            "--wheel",
            "--no-isolation",
            "--outdir",
            str(wheels),
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    (wheel,) = wheels.glob("*.whl")
    installed = tmp_path / "installed"
    with zipfile.ZipFile(wheel) as archive:
        assert (
            archive.read("carbon/reconstruction/construction_promotions.json")
            == promotions.REGISTRY.read_bytes()
        )
        archive.extractall(installed)
    subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from carbon.reconstruction import construction_promotions as p; "
                "assert p.promoted() == (); assert p.REGISTRY.is_file()"
            ),
        ],
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(installed)},
        check=True,
    )
