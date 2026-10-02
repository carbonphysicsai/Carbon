"""The battery challenge kit: the challenge's own draw and reference, for miners.

The claims tested: the kit's draws are the validator's own rule and not a
look-alike (given the same root and pin they equal `seeds.draw_inputs` byte for
byte); labelling runs the validator's own no-network solve container and keeps
its typed statuses; the dataset has TRAIN v1's shape; and nothing official or
private is named or shipped. Each absence is paired with the same thing present
where it really is.
"""

import json
import os
import stat
from pathlib import Path

import pytest

from carbon.battery import seeds, truth, truth_env
from carbon.battery.challenge import INPUT_BOUNDS, INPUTS, PublicMaterial
from carbon.battery.domain import TrainingData
from carbon.challenge_kit import battery as kit

REPO = Path(__file__).resolve().parents[2]
ROOT = bytes(range(32))


def test_the_pin_is_the_one_a_deployment_of_this_checkout_commits():
    from carbon.battery.daemon import rule_digest
    from carbon.battery.deployment import rule_for

    expected = seeds.seed_pin(
        seeds.generator_digest(REPO), rule_digest(rule_for({"rule": "v1"}))
    )
    assert kit.pin() == expected


def test_draws_are_the_validators_rule_byte_for_byte(tmp_path):
    """Given the same 32 bytes as an operator root, the validator's own
    context and `draw_inputs` give exactly the kit's cases."""
    root_file = tmp_path / "root.bin"
    root_file.write_bytes(ROOT)
    root_file.chmod(0o600)
    operator = seeds._context(seeds.PrivateRoot.load(root_file), kit.pin())
    theirs = [seeds.draw_inputs(operator, "train", i) for i in range(16)]
    ours = [{k: job[k] for k in INPUTS} for job in kit.draw(ROOT, 16)]
    assert json.dumps(ours) == json.dumps(theirs)
    # Specimen: the match is not trivial - another root is another draw.
    other = [{k: job[k] for k in INPUTS} for job in kit.draw(bytes(32), 16)]
    assert other != theirs


def test_draws_stay_in_the_published_box_and_roles_are_separate_streams():
    train = kit.draw(ROOT, 50)
    for job in train:
        for name in INPUTS:
            low, high = INPUT_BOUNDS[name]
            assert low <= job[name] <= high, (name, job)
    assert [j["case_id"] for j in train[:2]] == ["train-00000", "train-00001"]
    test = kit.draw(ROOT, 50, role="test")
    assert {tuple(j[k] for k in INPUTS) for j in train}.isdisjoint(
        {tuple(j[k] for k in INPUTS) for j in test}
    )
    assert kit.draw(ROOT, 50) == train  # deterministic
    for bad in ({"role": "eval"}, {"role": "stress"}):
        with pytest.raises(ValueError, match="role"):
            kit.draw(ROOT, 1, **bad)
    with pytest.raises(ValueError):
        kit.draw(ROOT, 0)


def _record(job, status=truth.OK):
    """A record in the truth service's shape, from TRAIN v1's first case."""
    record = {"case_id": job["case_id"], "refined": False, "status": status}
    record["inputs"] = {k: job[k] for k in INPUTS}
    if status == truth.OK:
        record["outputs"] = _TRAIN_OUTPUTS
        record["diagnostics"] = {"t_max_c": 30.0}
    return record


_TRAIN_OUTPUTS = None


@pytest.fixture(scope="module", autouse=True)
def _train_outputs():
    global _TRAIN_OUTPUTS
    train = PublicMaterial.load(REPO).train
    _TRAIN_OUTPUTS = {
        "voltage_v": train.v[0].tolist(),
        "temperature_c": train.t[0].tolist(),
        "plating_margin_v": float(train.eta[0]),
        "capacity_ah": train.q[0].tolist(),
    }


class FakeTruthContainer:
    """Stands in for Docker: checks it was asked for the validator's own solve
    run, then writes records as the truth service would."""

    def __init__(self, statuses):
        self.statuses, self.commands = statuses, []

    def __call__(self, command, check=False, **_):
        self.commands.append(command)
        mounts = [command[i + 1] for i, a in enumerate(command) if a == "-v"]
        work = Path(next(m for m in mounts if m.endswith(":/work:rw")).split(":")[0])
        document = json.loads((work / "jobs.json").read_bytes())
        records = work / "records.jsonl"
        if not records.exists():
            records.touch(mode=0o600)
        with records.open("a") as out:
            for job, status in zip(document["jobs"], self.statuses, strict=False):
                out.write(json.dumps(_record(job, status)) + "\n")

        class Done:
            returncode = 0

        return Done()


def test_labelling_runs_the_validators_solve_container(tmp_path):
    jobs = kit.draw(ROOT, 4)
    container = FakeTruthContainer(
        [truth.OK, truth.OK, truth.SOLVER_FAILED, truth.FAILED_INFRA]
    )
    found = kit.label(
        jobs,
        tmp_path / "work",
        overlay=tmp_path / "overlay",
        runner=container,
        prepare=False,
    )
    (command,) = container.commands
    assert command == truth_env.solve_command(
        tmp_path / "overlay", tmp_path / "work", repository=kit.REPOSITORY
    )
    assert command[command.index("--network") + 1] == "none"
    assert "--read-only" in command
    assert truth.TRUTH_IMAGE["base_image"] in command
    assert kit.summary(jobs, found)["counts"] == {
        truth.OK: 2,
        truth.SOLVER_FAILED: 1,
        truth.TIMEOUT: 0,
        truth.FAILED_INFRA: 1,
    }
    work = tmp_path / "work"
    assert stat.S_IMODE(work.stat().st_mode) == 0o700
    assert stat.S_IMODE((work / "jobs.json").stat().st_mode) == 0o600

    out = tmp_path / "data.jsonl.gz"
    assert kit.write_dataset(found, out) == 2
    import gzip

    data = [json.loads(line) for line in gzip.decompress(out.read_bytes()).splitlines()]
    assert {r["status"] for r in data} == {truth.OK}
    train = TrainingData.from_records(data)
    assert train.x.shape == (2, 4) and train.v.shape[1] == 121


def test_a_rerun_keeps_the_latest_record_and_another_draw_is_refused(tmp_path):
    jobs = kit.draw(ROOT, 2)
    kit.label(
        jobs,
        tmp_path / "w",
        runner=FakeTruthContainer([truth.FAILED_INFRA] * 2),
        prepare=False,
    )
    found = kit.label(
        jobs,
        tmp_path / "w",
        runner=FakeTruthContainer([truth.OK] * 2),
        prepare=False,
    )
    assert [r["status"] for r in found] == [truth.OK, truth.OK]
    with pytest.raises(kit.KitRefused, match="another draw"):
        kit.label(
            kit.draw(ROOT, 3),
            tmp_path / "w",
            runner=FakeTruthContainer([]),
            prepare=False,
        )


def test_a_record_that_does_not_match_its_job_is_refused(tmp_path):
    jobs = kit.draw(ROOT, 1)
    work = tmp_path / "w"
    work.mkdir(mode=0o700)
    forged = {**_record(jobs[0]), "inputs": {k: 0.0 for k in INPUTS}}
    (work / "records.jsonl").write_text(json.dumps(forged) + "\n")
    with pytest.raises(kit.KitRefused, match="does not match"):
        kit.records(work, jobs)


def test_a_failed_container_is_a_refusal_not_data(tmp_path):
    class Failed:
        returncode = 125

    with pytest.raises(kit.KitRefused, match="did not finish"):
        kit.label(
            kit.draw(ROOT, 1),
            tmp_path / "w",
            runner=lambda *a, **k: Failed(),
            prepare=False,
        )


def test_the_command_line_draws_and_refuses_a_bad_root(tmp_path, capsys):
    out = tmp_path / "cases.json"
    assert (
        kit.main(["draw", "--root-hex", ROOT.hex(), "--count", "3", "--out", str(out)])
        == 0
    )
    document = json.loads(out.read_text())
    assert document["jobs"] == kit.draw(ROOT, 3)
    assert (
        document["fingerprint"] == kit.jobs_document(kit.draw(ROOT, 3))["fingerprint"]
    )
    assert (
        kit.main(["draw", "--root-hex", "00" * 31, "--count", "3", "--out", str(out)])
        == 2
    )
    assert "32 bytes" in capsys.readouterr().err


_OFFICIAL_NAMES = frozenset(
    {
        "OfficialContext",
        "OfficialEntropy",
        "OfficialExamProjection",
        "QualificationContext",
        "QualificationEntropy",
        "FixtureOfficialContext",
        "FixtureOfficialEntropy",
        "FixtureOfficialExamProjection",
        "acquire_official_context",
        "acquire_fixture_official_context",
        "frozen_seeds",
        "ROLE_ROOTS",
        # The validator's private-root and evaluation-batch surface.
        "PrivateRoot",
        "make_batch",
        "reconstruction_seed",
        "SeedJournal",
        "CommittedBatch",
        "PrivateBatch",
    }
)


def _official_names_used(path):
    import ast

    names = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.ImportFrom):
            names |= {a.name for a in node.names}
        elif isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
    return names & _OFFICIAL_NAMES


def test_no_official_seed_material_is_named_or_reachable():
    """Structural separation only: the kit names no official or qualification
    seeding, no private root, batch or journal, and its only context is a mock
    one over the miner's own 32-byte root. This does NOT establish semantic
    decontamination (constitution section 7.2), which stays open and owned by
    the MQ-008 holder."""
    from carbon.seeding.model import MockContext

    source = Path(kit.__file__)
    assert _official_names_used(source) == set()
    # Specimens: the same scan finds official seeding and the private root
    # where they really live.
    assert "OfficialContext" in _official_names_used(
        REPO / "carbon" / "seeding" / "provider.py"
    )
    assert {"PrivateRoot", "SeedJournal"} <= _official_names_used(
        REPO / "carbon" / "battery" / "operate.py"
    )
    assert type(kit.context(ROOT)) is MockContext
    for bad in (b"", bytes(31), bytes(33), "00" * 32):
        with pytest.raises(ValueError):
            kit.context(bad)


def test_the_kit_runs_on_the_miners_machine_not_in_the_sandbox():
    """OWNER-MINER-OWN-MACHINE-01 item 4: the battery kit is a host command;
    adding it to the research sandbox is a later, separately reviewed step."""
    from carbon.development_session.research_image import (
        challenge_kit_files,
        permitted_files,
    )

    assert "carbon/challenge_kit/battery.py" not in challenge_kit_files(REPO)
    assert "carbon/challenge_kit/battery.py" not in permitted_files()
    # Specimen: the Burgers kit really is shipped.
    assert "carbon/challenge_kit/burgers.py" in permitted_files()


def test_a_jobs_document_is_what_the_truth_service_reads(tmp_path):
    """`truth_env.solve` reads `fingerprint` and `jobs`; each job carries the
    case id and the four inputs the reference solver reads."""
    document = kit.jobs_document(kit.draw(ROOT, 2))
    assert set(document) >= {"fingerprint", "jobs"}
    for job in document["jobs"]:
        assert set(job) == {"case_id", *INPUTS}
    # The owner-only work directory is enforced.
    loose = tmp_path / "loose"
    loose.mkdir()
    os.chmod(loose, 0o755)
    with pytest.raises(kit.KitRefused, match="owner-only"):
        kit.label(
            kit.draw(ROOT, 1), loose, runner=FakeTruthContainer([]), prepare=False
        )
