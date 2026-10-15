"""Public-test retention: real fixed writer/NPZ round trip; fixture runner only.

No provider/GPU/private material. The subprocess stand-in is NOT isolation
evidence; canonical remote CI exercises this file, not the Product host.
"""

import copy
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from carbon.battery import public_model_retention as retention
from carbon.battery import recipes
from carbon.battery.challenge import INPUTS, TRAIN_V1_SHA256
from carbon.battery.compile import compile_recipe
from carbon.battery.practice import PROGRAM, PracticeSet, staged_files
from carbon.development_session.battery_gpu import GPU_PROGRAM, TORCH_GPU_PROGRAM
from carbon.development_session.profile import canonical, digest

REPOSITORY = Path(__file__).resolve().parents[2]
STRATEGY = {
    "schema_version": "1.0",
    "challenge_id": retention.CHALLENGE,
    "backbone": "knn",
    "parameters": {"neighbours": 4},
}
IMAGE = "sha256:" + "1" * 64


def opt_in(campaign_id="cmp-battery-julia"):
    return {
        "schema": retention.OPT_IN_SCHEMA,
        "campaign_id": campaign_id,
        "scope": "PUBLIC_GRAPHITE_TEST",
        "program_version": retention.PROGRAM_VERSION,
        "source_commit": "a" * 40,
    }


def manifest():
    return {
        "campaign_id": "cmp-battery-julia",
        "owner": "miner-requester",
        "agent": "graphite",
        "provider": {"agent": "graphite"},
        "challenge": {"id": retention.CHALLENGE},
        "public_model_retention": opt_in(),
    }


@pytest.fixture(scope="module")
def public_stage():
    _, recipe = compile_recipe(STRATEGY)
    return staged_files(REPOSITORY, PracticeSet.load(REPOSITORY), recipe, 11)


def test_absent_opt_in_keeps_defaults_and_present_opt_in_is_exact(tmp_path):
    assert retention.launch_opt_in(tmp_path, campaign_id="c", agent="none") == {}
    assert retention.frozen_opt_in({}, owner="miner-requester") is None
    path = tmp_path / retention.OPT_IN_FILE
    path.write_bytes(canonical(opt_in()))
    assert retention.launch_opt_in(
        tmp_path, campaign_id="cmp-battery-julia", agent="graphite"
    ) == {"public_model_retention": opt_in()}
    assert retention.frozen_opt_in(manifest(), owner="miner-requester") == opt_in()
    for field, changed in (
        ("scope", "PRIVATE"),
        ("scope", True),
        ("campaign_id", "another"),
        ("source_commit", "main"),
        ("program_version", "future"),
        ("upload_url", "https://example.invalid"),
    ):
        path.write_bytes(canonical({**opt_in(), field: changed}))
        with pytest.raises(ValueError):
            retention.launch_opt_in(
                tmp_path, campaign_id="cmp-battery-julia", agent="graphite"
            )
    path.write_bytes(canonical(opt_in()))
    with pytest.raises(ValueError):
        retention.launch_opt_in(
            tmp_path, campaign_id="cmp-battery-julia", agent="autonomous"
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("owner", "another"),
        ("agent", "autonomous"),
        ("provider", {"agent": "autonomous"}),
        ("challenge", {"id": "private"}),
    ],
)
def test_frozen_binding_refuses_other_campaign_authority(field, value):
    with pytest.raises(ValueError):
        retention.frozen_opt_in({**manifest(), field: value}, owner="miner-requester")


def test_opt_in_refuses_symlink_and_oversized_file(tmp_path):
    path = tmp_path / retention.OPT_IN_FILE
    target = tmp_path / "target.json"
    target.write_bytes(canonical(opt_in()))
    path.symlink_to(target)
    with pytest.raises(ValueError, match="symlink"):
        retention.launch_opt_in(
            tmp_path, campaign_id="cmp-battery-julia", agent="graphite"
        )
    path.unlink()
    path.write_bytes(b" " * 4097)
    with pytest.raises(ValueError, match="bounded"):
        retention.launch_opt_in(
            tmp_path, campaign_id="cmp-battery-julia", agent="graphite"
        )


@pytest.mark.parametrize(
    "source,old_hash",
    [
        (PROGRAM, "13af21c33ca1cde6c7bfb38f80166125fc0a94dd1629069cc7f6c4ec5149aa7a"),
        (
            GPU_PROGRAM,
            "264413438e3456605279d89aa3f066386bbf0dfaa497198a0957bdf912a9746a",
        ),
        (
            TORCH_GPU_PROGRAM,
            "9dc5dd02e557db9b3635af9c57ee65e0d4f0629cbfb74a590b6d1cbb8a36169d",
        ),
    ],
)
def test_retention_versions_program_without_moving_cpu_or_gpu_identity(
    public_stage, source, old_hash
):
    assert digest(source.encode()) == "sha256:" + old_hash
    program, files, provenance = retention.retained_program(
        source, public_stage, opt_in=opt_in(), identity="trial-1", image=IMAGE
    )
    assert digest(program.encode()) != digest(source.encode())
    assert provenance["base_program_sha256"] == digest(source.encode())
    assert provenance["program_sha256"] == digest(program.encode())
    assert files == {**public_stage, retention.STAGED_FILE: canonical(provenance)}
    assert provenance["staged"]["train-v1.jsonl.gz"] == "sha256:" + TRAIN_V1_SHA256
    assert provenance["semantics"]["inputs"] == list(INPUTS)
    assert "cooling" not in provenance["semantics"]["outputs"]
    assert "recipes.state_bytes(model)" in program
    compile(program, "retained-practice", "exec")


def test_retention_never_wraps_arbitrary_code_or_stages_labels(public_stage):
    def wrap(source=PROGRAM, files=None, **kwargs):
        return retention.retained_program(
            source,
            public_stage if files is None else files,
            opt_in=kwargs.get("opt_in", opt_in()),
            identity="trial",
            image=kwargs.get("image", IMAGE),
        )

    with pytest.raises(ValueError, match="fixed public"):
        wrap(source="print('arbitrary')")
    with pytest.raises(ValueError, match="fixed public"):
        wrap(files={**public_stage, "hidden.json": b"{}"})
    with pytest.raises(ValueError, match="pinned public TRAIN"):
        wrap(files={**public_stage, "train-v1.jsonl.gz": b"changed"})
    inputs = json.loads(public_stage["practice-inputs.json"])
    inputs["cases"][0]["outputs"] = {"label": 1}
    with pytest.raises(ValueError, match="without labels"):
        wrap(files={**public_stage, "practice-inputs.json": canonical(inputs)})
    with pytest.raises(ValueError, match="image"):
        wrap(image="mutable:latest")
    with pytest.raises(ValueError, match="opt-in"):
        wrap(opt_in={**opt_in(), "scope": "HIDDEN"})


def practice_fixture(tmp_path):
    from test_battery_research_images import composition

    _service, ledger, practice = composition(tmp_path, None)
    return ledger, practice


def test_default_practice_retains_its_original_outputs_only(tmp_path):
    ledger, practice = practice_fixture(tmp_path)
    result = practice("default-trial", STRATEGY)
    folder = ledger.root / result["worker"]["operation"] / "snapshot"
    assert (folder / "predictions.json").is_file()
    assert (folder / "fit.json").is_file()
    assert not (folder / retention.STATE_FILE).exists()
    assert not (folder / retention.SIDECAR_FILE).exists()
    assert retention.inventory(ledger, owner="miner-requester") == []


def test_every_model_and_failed_trial_is_retained_independently_of_selection(
    tmp_path, monkeypatch
):
    ledger, practice = practice_fixture(tmp_path)
    practice.model_retention = opt_in()
    results = [
        practice("successful-1", STRATEGY),
        practice(
            "successful-2",
            {
                **STRATEGY,
                "parameters": {"neighbours": 8},
            },
        ),
    ]
    with pytest.raises(ValueError):
        practice("refused", {**STRATEGY, "backbone": "no-such-backbone"})

    def failed(*args, **kwargs):
        raise RuntimeError("fixture lost worker; not science failure")

    monkeypatch.setattr(practice, "runner", failed)
    with pytest.raises(RuntimeError):
        practice("worker-failed", STRATEGY)
    roster = {
        r["trial_identity"]: r
        for r in retention.inventory(ledger, owner="miner-requester")
    }
    assert set(roster) == {"successful-1", "successful-2", "refused", "worker-failed"}
    assert roster["refused"]["stage"] == "compile"
    assert roster["worker-failed"]["stage"] == "worker"
    for identity in ("refused", "worker-failed"):
        assert roster[identity]["status"] == "FAILED"
        assert roster[identity]["state"] == {"status": "NOT_RETAINED"}
    for i, result in enumerate(results, 1):
        row = roster[f"successful-{i}"]
        assert row["status"] == "COMPLETED" and row["state"]["status"] == "RETAINED"
        assert row["selected"] is None and row["official_eligible"] is False
        body = (ledger.root / row["state"]["path"]).read_bytes()
        assert digest(body) == row["state"]["sha256"]
        assert len(body) == row["state"]["bytes"]
        artifact = row["artifact_provenance"]
        assert artifact["params_sha256"] == result["fit"]["params_sha256"]
        assert row["state"]["sha256"] != result["recipe_digest"]
        assert (
            row["state"]["sha256"].removeprefix("sha256:") != artifact["params_sha256"]
        )
        assert artifact["fit_cost"]["wall_s"] >= 0
        assert artifact["prediction_cost"]["wall_s"] >= 0
        assert artifact["runtime"]["packages"]["numpy"]
        with np.load(__import__("io").BytesIO(body), allow_pickle=False) as data:
            assert "__header__" in data and all(
                data[k].dtype.kind != "O" for k in data.files
            )
        # Inference is from the original state. Any accidental refit fails.
        monkeypatch.setattr(recipes.KNN, "fit", failed)
        restored = recipes.model_from_bytes(body)
        operation = ledger.root / row["worker"]["operation"]
        inputs = json.loads(
            (operation / "scratch/workspace/practice-inputs.json").read_bytes()
        )["cases"]
        expected = json.loads((operation / "snapshot/predictions.json").read_bytes())
        x = np.asarray([[c["inputs"][k] for k in INPUTS] for c in inputs])
        actual = recipes.to_predictions(
            restored.predict(x), [c["case_id"] for c in inputs]
        )
        assert set(actual) == set(expected)
        for case in actual:
            for quantity in actual[case]:
                np.testing.assert_allclose(
                    actual[case][quantity], expected[case][quantity], rtol=0, atol=0
                )


def test_incomplete_roster_and_replay_never_invent_or_replace_weights(tmp_path):
    ledger, _practice = practice_fixture(tmp_path)
    first = retention.Trial(ledger, "miner-requester", "crashed", STRATEGY, opt_in())
    roster = retention.inventory(ledger, owner="miner-requester")
    assert roster[0]["status"] == "INCOMPLETE"
    assert roster[0]["state"] == {"status": "NOT_RETAINED"}
    retention.Trial(ledger, "miner-requester", "crashed", STRATEGY, opt_in())
    with pytest.raises(ValueError, match="identity reused"):
        retention.Trial(
            ledger,
            "miner-requester",
            "crashed",
            {**STRATEGY, "backbone": "mlp"},
            opt_in(),
        )
    assert retention.inventory(ledger, owner="miner-requester") == roster
    first.dispatch({"image": IMAGE}, {"seed": 11})
    with pytest.raises(ValueError, match="immutable provenance"):
        first.dispatch({"image": "sha256:" + "2" * 64}, {"seed": 11})


def test_snapshot_digests_and_sidecar_bindings_have_negative_controls(tmp_path):
    ledger, practice = practice_fixture(tmp_path)
    practice.model_retention = opt_in()
    result = practice("bound", STRATEGY)
    row = retention.inventory(ledger, owner="miner-requester")[0]
    folder = ledger.root / row["worker"]["operation"] / "snapshot"
    worker = {
        **result["worker"],
        "files": {p.name: digest(p.read_bytes()) for p in folder.iterdir()},
    }
    trial = retention.Trial(ledger, "miner-requester", "bound", STRATEGY, opt_in())
    # Positive control: the same receipt/bytes collect again without training.
    trial.collect(worker, row["provenance"])
    sidecar = json.loads((folder / retention.SIDECAR_FILE).read_bytes())
    original = (folder / retention.SIDECAR_FILE).read_bytes()
    for field, changed in (
        ("image", "another"),
        ("seed", 12),
        ("params_sha256", "forged"),
        ("recipe_digest", "forged"),
    ):
        (folder / retention.SIDECAR_FILE).write_bytes(
            canonical({**sidecar, field: changed})
        )
        # Even if a worker reports the changed sidecar's hash, its claimed
        # provenance must still match the independent controller request.
        altered = copy.deepcopy(worker)
        altered["files"][retention.SIDECAR_FILE] = digest(
            (folder / retention.SIDECAR_FILE).read_bytes()
        )
        with pytest.raises(ValueError):
            trial.collect(altered, row["provenance"])
    (folder / retention.SIDECAR_FILE).write_bytes(original)
    (folder / retention.STATE_FILE).write_bytes(b"tampered")
    with pytest.raises(ValueError, match="changed after collection"):
        trial.collect(worker, row["provenance"])
    notes = ledger.status(owner="miner-requester")["notes"]
    assert any(
        n["kind"] == "security_incident" and n["body"]["file"] == retention.STATE_FILE
        for n in notes
    )
    escaped = {**worker, "operation": "../outside"}
    with pytest.raises(ValueError, match="operation"):
        trial.collect(escaped, row["provenance"])
    # A failed replay or changed claim must preserve the original success.
    trial.failed(ValueError("tampered replay"))
    assert retention.inventory(ledger, owner="miner-requester")[0] == row


def test_state_file_bound_and_symlink_are_checked_before_reading(tmp_path):
    operation = "operation-" + "1" * 64
    folder = tmp_path / operation / "snapshot"
    folder.mkdir(parents=True)
    target = folder / retention.STATE_FILE
    # Sparse file: exercise the real production bound without allocating it.
    with target.open("wb") as handle:
        handle.truncate(retention.MAX_STATE_BYTES + 1)
    ledger = SimpleNamespace(root=tmp_path)
    worker = {"operation": operation, "files": {retention.STATE_FILE: "forged"}}
    with pytest.raises(ValueError, match="bounded"):
        retention._snapshot_file(
            ledger, worker, retention.STATE_FILE, retention.MAX_STATE_BYTES
        )
    target.unlink()
    other = tmp_path / "outside.npz"
    other.write_bytes(b"not a model")
    target.symlink_to(other)
    with pytest.raises(ValueError, match="symlink"):
        retention._snapshot_file(
            ledger, worker, retention.STATE_FILE, retention.MAX_STATE_BYTES
        )


def test_feedback_failure_keeps_already_collected_original_state(tmp_path, monkeypatch):
    from carbon.battery import research

    ledger, practice = practice_fixture(tmp_path)
    practice.model_retention = opt_in()

    def failed(*args, **kwargs):
        raise RuntimeError("fixture host scorer failure, not model failure")

    monkeypatch.setattr(research, "score_practice", failed)
    with pytest.raises(RuntimeError):
        practice("feedback-failed", STRATEGY)
    row = retention.inventory(ledger, owner="miner-requester")[0]
    assert row["status"] == "FAILED" and row["stage"] == "feedback"
    assert row["state"]["status"] == "RETAINED"
    assert (
        digest((ledger.root / row["state"]["path"]).read_bytes())
        == row["state"]["sha256"]
    )


def test_compose_uses_only_the_frozen_opt_in_not_a_mutable_marker(
    tmp_path, monkeypatch
):
    from carbon.battery import campaign, research

    path = tmp_path / "campaign-manifest.json"
    path.write_bytes(canonical(manifest()))
    (tmp_path / retention.OPT_IN_FILE).write_bytes(b"invalid mutable marker")
    seen = []

    class Captured(Exception):
        pass

    def capture(**kwargs):
        seen.append(kwargs)
        raise Captured

    monkeypatch.setattr(research, "BatteryPractice", capture)
    args = {
        "ledger": SimpleNamespace(root=tmp_path),
        "owner": "miner-requester",
        "image": None,
        "analysis": None,
        "connection": None,
    }
    with pytest.raises(Captured):
        campaign.compose(**args)
    assert seen[-1]["model_retention"] == opt_in()
    frozen = manifest()
    del frozen["public_model_retention"]
    path.write_bytes(canonical(frozen))
    with pytest.raises(Captured):
        campaign.compose(**args)
    assert seen[-1]["model_retention"] is None
