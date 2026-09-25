"""The operator's battery validator deployment and its commands.

The deployment is the only way a campaign reaches battery evaluation. These
tests check that it fails closed - bad configuration, a changed identity
binding, a required commitment with no chain reader - and that the operator
commands never print a case, seed or key.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tests" / "cpu"))

from test_battery_validator_daemon import (
    PIN_G,
    PIN_S,
    batch,
    refs,  # noqa: F401 - fixture
    submission,
)

from carbon.battery import deployment, operate, seeds, signing
from carbon.battery.pool_store import PoolStore


@pytest.fixture(autouse=True)
def fresh(monkeypatch):
    monkeypatch.setattr(deployment, "_VALIDATORS", {})


def write(path, value, mode=0o600):
    path.write_text(json.dumps(value))
    path.chmod(mode)
    return path


def config(tmp_path, **overrides):
    tmp_path.chmod(0o700)
    root = seeds.PrivateRoot.create(tmp_path / "root.bin")
    journal = seeds.SeedJournal(tmp_path / "journal.jsonl")
    journal.commit_root(root, seeds.seed_pin(PIN_G, PIN_S))
    value = {
        "schema": deployment.SCHEMA,
        "state": str(tmp_path / "state.sqlite3"),
        "private_root": str(tmp_path / "root.bin"),
        "journal": str(tmp_path / "journal.jsonl"),
        "work": str(tmp_path / "work"),
        "backend": "direct",
        "require_commitment": False,
        **overrides,
    }
    return write(tmp_path / "deployment.json", value)


@pytest.mark.parametrize(
    ("change", "code"),
    [
        (
            {"schema": "carbon.battery.evaluation-deployment.v1"},
            "evaluation_config_schema",
        ),
        ({"batches": "x"}, "evaluation_config_fields"),
        ({"backend": "pytorch"}, "evaluation_config_backend"),
        ({"backend": "carrier"}, "evaluation_config_image"),
        ({"require_commitment": "no"}, "evaluation_config_fields"),
    ],
)
def test_a_bad_configuration_is_refused(tmp_path, change, code):
    path = config(tmp_path, **change)
    with pytest.raises(deployment.EvaluationUnavailable) as refused:
        deployment.validator(path, repository=REPOSITORY)
    assert refused.value.code == code


def test_configuration_files_must_be_owner_only(tmp_path):
    path = config(tmp_path)
    path.chmod(0o640)
    with pytest.raises(deployment.EvaluationUnavailable) as refused:
        deployment.validator(path, repository=REPOSITORY)
    assert refused.value.code == "evaluation_input_not_owner_only"


def test_a_changed_identity_binding_stops_the_deployment(tmp_path):
    path = config(tmp_path)
    PoolStore(tmp_path / "state.sqlite3").bind({"schema": "another deployment"})
    with pytest.raises(deployment.EvaluationUnavailable) as refused:
        deployment.validator(path, repository=REPOSITORY)
    assert refused.value.code == "evaluation_identities_changed"


def test_a_required_commitment_is_never_skipped(tmp_path, refs):  # noqa: F811
    path = config(tmp_path, require_commitment=True)
    target = deployment.validator(path, repository=REPOSITORY)
    target.allow_published_cases = True
    for b in range(3):
        fp = target.import_batch(batch(refs, f"pscreen-B0{b}"), kind="screening")
        target.ingest_references(fp, list(refs.values()))
    target.open_pool()
    with pytest.raises(deployment.EvaluationUnavailable) as refused:
        deployment.evaluate(target, submission("hk1"))
    assert refused.value.code == "commitment_reader_unavailable"
    assert target.status()["pool"]["admitted"] == 0


def test_operator_commands_disclose_no_case_seed_or_key(
    tmp_path,
    refs,  # noqa: F811
    capsys,
):
    signing.ServiceKey.create(tmp_path / "service.key")
    path = config(tmp_path, service_key=str(tmp_path / "service.key"))
    target = deployment.validator(path, repository=REPOSITORY)
    target.allow_published_cases = True
    for b in range(3):
        fp = target.import_batch(batch(refs, f"pscreen-B0{b}"), kind="screening")
        records = tmp_path / f"records-{b}.jsonl"
        records.write_text("".join(json.dumps(r) + "\n" for r in refs.values()))
        records.chmod(0o600)
        assert (
            operate.main(
                [
                    "ingest",
                    "--config",
                    str(path),
                    "--batch",
                    fp,
                    "--records",
                    str(records),
                ]
            )
            == 0
        )
    # A fresh batch generated from the private root, committed before use.
    assert (
        operate.main(
            [
                "prepare",
                "--config",
                str(path),
                "--role",
                "pscreen-B03",
                "--kind",
                "screening",
            ]
        )
        == 0
    )
    assert operate.main(["open", "--config", str(path)]) == 0
    deployment.evaluate(target, submission("hk1"))
    assert operate.main(["run", "--config", str(path)]) == 0
    assert operate.main(["batches", "--config", str(path)]) == 0
    assert operate.main(["status", "--config", str(path)]) == 0
    out = tmp_path / "export"
    assert operate.main(["export", "--config", str(path), "--out", str(out)]) == 0
    printed = capsys.readouterr().out
    for case_id in refs:
        assert case_id not in printed
    assert (tmp_path / "root.bin").read_bytes().hex() not in printed
    assert (tmp_path / "service.key").read_bytes().hex() not in printed
    exported = sorted(out.iterdir())
    assert all(p.stat().st_mode & 0o077 == 0 for p in exported)
    intent = json.loads((out / "weight-intent.json").read_text())
    assert signing.verify(intent) and intent["payload"]["mode"] == "ALL_BURN"
    outcomes = [
        json.loads(p.read_text()) for p in exported if p.name.startswith("bsub-")
    ]
    assert len(outcomes) == 1 and all(signing.verify(o) for o in outcomes)
    assert outcomes[0]["payload"]["state"] == "SCORED"
