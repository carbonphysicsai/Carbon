"""Battery's sealed tuning set, operator-side (VALIDATOR-17).

The deployment fixtures are battery's daemon fixtures (published PyBaMM
references, `DirectBackend`). The scoring check uses published development
cases as a stand-in batch; the real tuning batch is drawn from an operator
root and never appears in a test.
"""

import json
import sys
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tests" / "cpu"))

from test_battery_validator_daemon import (
    backend,  # noqa: F401 - fixture
    batch,
    make,
    refs,  # noqa: F401 - fixture
)

from carbon.battery.pool_store import StateError
from carbon.battery.value import panel as pn
from carbon.challenge_validator import tuning
from carbon.challenge_validator.confirmation import confirmation_set, load_sets
from carbon.challenge_validator.interface import (
    BATTERY_TUNING_ROLE,
    RESERVED_SEED_ROLES,
    role_reserved,
)


def config_for(directory):
    path = directory / "deployment.json"
    path.write_text(
        json.dumps(
            {
                "schema": "carbon.battery.validator-deployment.v1",
                "state": str(directory / "state.sqlite3"),
                "private_root": str(directory / "root.bin"),
                "journal": str(directory / "journal.jsonl"),
                "work": str(directory / "work"),
                "backend": "direct",
                "require_commitment": False,
            }
        )
    )
    path.chmod(0o600)
    return path


def test_the_tuning_set_is_registered_reserved_and_sized_as_decided():
    item = load_sets()[BATTERY_TUNING_ROLE]
    assert (item.cases, item.hidden_duplicates) == (200, 4)
    assert item.strata == ()
    assert item.sealable is True
    assert set(item.required_prior_roles) == {
        "ev5-confirmation",
        "graphite-confirmation-v1",
    }
    assert set(item.required_private_priors) == {
        "graphite-hidden-battery-v1-pool",
        "practice-decision-set",
    }
    assert BATTERY_TUNING_ROLE in RESERVED_SEED_ROLES
    assert role_reserved("GRAPHITE-TUNING-V1")


def test_no_pool_path_can_prepare_the_tuning_role(
    tmp_path,
    refs,  # noqa: F811
    backend,  # noqa: F811
):
    target = make(tmp_path, refs, backend)
    with pytest.raises(StateError) as refused:
        target.prepare_batch(BATTERY_TUNING_ROLE, kind="screening")
    assert refused.value.code == "seed_role_reserved"


def test_jobs_recall_exactly_the_sealed_batch_and_never_commit(
    tmp_path,
    refs,  # noqa: F811
    backend,  # noqa: F811
):
    deployment_dir = tmp_path / "deployment"
    deployment_dir.mkdir()
    target = make(deployment_dir, refs, backend)
    item = confirmation_set(BATTERY_TUNING_ROLE)
    sealed = target.seal_batch(
        BATTERY_TUNING_ROLE, count=item.batch_size, duplicates=item.hidden_duplicates
    )
    before = (deployment_dir / "journal.jsonl").read_bytes()
    commitment = tmp_path / "commitment.json"
    commitment.write_text(
        json.dumps(
            {"fingerprint": sealed.fingerprint, "journal_sequence": sealed.sequence}
        )
    )
    work = tmp_path / "work"
    result = tuning.jobs(config_for(deployment_dir), commitment, work)
    assert result["fingerprint"] == sealed.fingerprint
    assert result["cases"] == item.batch_size
    assert result["distinct_solves"] == item.batch_size - item.hidden_duplicates
    assert (deployment_dir / "journal.jsonl").read_bytes() == before
    assert (work / "batch.json").stat().st_mode & 0o077 == 0
    # A different commitment is refused.
    commitment.write_text(
        json.dumps({"fingerprint": "f" * 64, "journal_sequence": sealed.sequence})
    )
    with pytest.raises(tuning.TuningRefused):
        tuning.jobs(config_for(deployment_dir), commitment, tmp_path / "other")


def test_work_inside_the_repository_is_refused():
    with pytest.raises(tuning.TuningRefused):
        tuning._owner_only_dir(REPOSITORY / "tmp-tuning-work")


def _stand_in_work(tmp_path, refs):  # noqa: F811
    """A work directory over published development cases (a stand-in batch)."""
    work = tuning._owner_only_dir(tmp_path / "work")
    document = batch(refs, "pscreen-B00").document()
    tuning._write_private(work / "batch.json", document)
    lines = [
        json.dumps(refs[c["case_id"]])
        for c in document["cases"]
        if c["case_id"] in refs
    ]
    (work / "records.jsonl").write_text("\n".join(lines) + "\n")
    (work / "records.jsonl").chmod(0o600)
    return work, document


def test_score_writes_each_members_components_and_case_rows(
    tmp_path,
    refs,  # noqa: F811
):
    work, document = _stand_in_work(tmp_path, refs)
    batch_refs = tuning.references(work)[1]
    predictions = tuning._owner_only_dir(work / "predictions")
    tuning._write_private(
        predictions / "member-a.json",
        {
            "member": "member-a",
            "kind": "RECONSTRUCTED",
            "predictions": pn.control_predictions("conservative", batch_refs),
        },
    )
    result = tuning.score(work)
    scores = tuning._read_private(work / "scores.json")
    assert result["members"] == 1 + len(pn.CONTROLS)
    assert scores["role"] == BATTERY_TUNING_ROLE
    assert scores["members"]["member-a"]["kind"] == "RECONSTRUCTED"
    assert scores["members"]["control-oracle"]["kind"] == "SYNTHETIC_CONTROL"
    assert scores["members"]["control-oracle"]["eligible"] is True
    rows = tuning._read_private(work / "rows" / "member-a.json")
    assert {r["case_id"] for r in rows} <= {c["case_id"] for c in document["cases"]}
    # Re-scoring overwrites cleanly.
    assert tuning.score(work) == result


@pytest.mark.parametrize(
    "panel",
    [
        {"schema": "x", "members": []},
        {"schema": tuning.PANEL_SCHEMA, "members": []},
        {
            "schema": tuning.PANEL_SCHEMA,
            "members": [
                {"member": "../escape", "kind": "K", "strategy": {}, "seed": 1}
            ],
        },
        {
            "schema": tuning.PANEL_SCHEMA,
            "members": [{"member": "a", "kind": "K", "strategy": {}, "seed": "1"}],
        },
    ],
)
def test_a_malformed_panel_is_refused(tmp_path, panel):
    path = tmp_path / "panel.json"
    path.write_text(json.dumps(panel))
    with pytest.raises(tuning.TuningRefused):
        tuning.load_panel(path)


def test_export_pool_writes_the_hidden_pools_inputs_owner_only(
    tmp_path,
    refs,  # noqa: F811
    backend,  # noqa: F811
):
    deployment_dir = tmp_path / "hidden"
    deployment_dir.mkdir()
    target = make(deployment_dir, refs, backend)
    out = tmp_path / "pool.json"
    result = tuning.export_pool(config_for(deployment_dir), out)
    expected = sum(len(b["document"]["cases"]) for b in target.store.batches())
    assert result["cases"] == expected
    assert out.stat().st_mode & 0o077 == 0
    assert len(json.loads(out.read_text())["cases"]) == expected


def test_graphite_withholds_anything_naming_the_tuning_set():
    from carbon.agent_campaign.graphite import protected_material as pm

    for text in ("graphite-tuning-v1", "the tuning_set rows", "TUNING-SET"):
        assert pm.protected(text)
        assert pm.marker_classes(text) == ["exam_material"]
    assert not pm.protected("hyperparameter tuning of the ridge")
