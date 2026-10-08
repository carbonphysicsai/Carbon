"""Training-budget study sets on the producer (TRAINING-BUDGET-01 slice 2b).

Pins:
- the TRAIN set nests: each ladder size is a prefix of the next;
- a fixed study root reproduces its draws, and another root differs;
- every unset (null or HUMAN_INPUT) value refuses, and N_max above the
  generation ceiling refuses;
- overlap with a published case, a private prior or another study set stops
  the draw before anything is committed, naming only the prior;
- each set is committed to the study journal before any export, and the
  manifest carries public values only;
- the confirmation set stays sealed until the harness journal records
  `limit_frozen` and then `confirmation_opened`, and is released once;
- a failed reference is withdrawn and counted, never dropped;
- every file is owner-only, and the study roles are reserved on the producer
  and `prepare_batch` paths.

Synthetic roots in temporary directories and a scripted truth solve: no
container, network, deployment or real root. The references are not
physics. Not a security audit (AGENTS.md section 13).
"""

import hashlib
import json
import os
import pwd
from pathlib import Path

import pytest
from test_challenge_validator_producer import producer, source  # noqa: F401

from carbon.battery.challenge import INPUT_BOUNDS, INPUTS
from carbon.challenge_validator import interface
from carbon.challenge_validator import producer as pr
from carbon.challenge_validator import study_sets as ss
from carbon.challenge_validator.confirmation_sources import BatterySource
from carbon.challenge_validator.interface import ReservedRole, digest

REPOSITORY = Path(__file__).resolve().parents[2]
ME = pwd.getpwuid(os.geteuid()).pw_name
BATTERY = "battery-fastcharge-ageing-development-v1"
MOTOR = "electric-motor-magnetics"
#: A real decision file stands in for the owner's study-root approval: the
#: check is that a named, pinned record is required, not which one.
DECISION = "2026-10-03-OWNER-EV5-FREEZE-01.md"
APPROVAL = {
    "record": "OWNER-EV5-FREEZE-01",
    "file": DECISION,
    "sha256": hashlib.sha256(
        (REPOSITORY / ".agent/decisions" / DECISION).read_bytes()
    ).hexdigest(),
}
#: Synthetic sizes: TRAIN 4 cases, ladder 1x/2x/3x, so N_max is 12.
SIZES = {
    "train_size": 4,
    "train_size_ladder": [1, 2, 3],
    "generation_ceiling": 12,
    "eval_cases": 5,
    "confirm_cases": 3,
}


def refused(call, code):
    with pytest.raises(ss.StudyRefused) as caught:
        call()
    assert caught.value.code == code, caught.value.code
    return caught.value


def write_private(path, value):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as handle:
        json.dump(value, handle)


def corner():
    """One case at the box's lower corner: never a rounded uniform draw."""
    return {k: float(INPUT_BOUNDS[k][0]) for k in INPUTS}


def write_spec(tmp_path, name="spec.json", study="study", cases=None, **overrides):
    prior = tmp_path / f"{name}.live-pool.json"
    if not prior.exists():
        write_private(prior, {"cases": [{"inputs": x} for x in cases or [corner()]]})
    spec = {
        "schema": ss.SPEC_SCHEMA,
        "service_account": ME,
        "challenge_id": BATTERY,
        "study_dir": str(tmp_path / study),
        "truth_overlay": str(tmp_path / "overlay"),
        "approval": APPROVAL,
        **SIZES,
        "private_priors": {"live-pool": str(prior)},
        **overrides,
    }
    path = tmp_path / name
    if path.exists():
        path.unlink()
    write_private(path, spec)
    return path


def scripted(failed=()):
    """The truth container's contract, scripted: every job in
    `/work/jobs.json` gets a terminal record; a job whose position in its
    set is in `failed` gets REFERENCE_SOLVER_FAILED."""

    def run(command, check):
        mount = next(a for a in command if a.endswith(":/work:rw"))
        work = Path(mount.removesuffix(":/work:rw"))
        jobs = json.loads((work / "jobs.json").read_text())["jobs"]
        with (work / "records.jsonl").open("a") as handle:
            for position, job in enumerate(jobs):
                status = "REFERENCE_SOLVER_FAILED" if position in failed else "OK"
                record = {
                    "case_id": job["case_id"],
                    "inputs": {k: job[k] for k in INPUTS},
                    "status": status,
                }
                handle.write(json.dumps(record) + "\n")

        class Done:
            returncode = 0

        return Done()

    return run


def open_study(path, runner=None):
    return ss.StudySets.from_spec(path, account=ME, runner=runner or scripted())


@pytest.fixture
def study(tmp_path):
    made = open_study(write_spec(tmp_path))
    made.init()
    return made


def complete(study, names=ss.SETS):
    study.draw()
    for name in names:
        study.jobs(name)
        study.solve(name)
        assert study.ingest(name)["state"] == "COMPLETE"


def harness_journal(path, events, schema=ss.HARNESS_JOURNAL_SCHEMA, challenge=BATTERY):
    lines = [{"schema": schema, "event": "opened", "challenge": challenge}]
    lines += [{"schema": schema, "event": e} for e in events]
    path.write_text("".join(json.dumps(line) + "\n" for line in lines))
    return path


def kinds(study):
    return [e["kind"] for e in study.journal.entries()]


# --- draws ----------------------------------------------------------------------------


def test_every_train_ladder_size_is_a_prefix_of_the_next(study):
    drawn = study.draw()
    assert {name: v["newly_committed"] for name, v in drawn.items()} == {
        "train": True,
        "eval": True,
        "confirm": True,
    }
    root, pin = study._open()
    _entry, document = study._committed("train")
    assert len(document["cases"]) == 12
    rungs = study.manifest("train")["ladder"]
    assert [(r["position"], r["multiple"], r["size"]) for r in rungs] == [
        (0, 1, 4),
        (1, 2, 8),
        (2, 3, 12),
    ]
    for rung in rungs:
        alone = study.source.study_draws(root, pin, "study-train", rung["size"])
        prefix = document["cases"][: rung["size"]]
        assert [(c["case_id"], c["inputs"]) for c in prefix] == alone
        assert rung["fingerprint"] == digest({**document, "cases": prefix})
    assert rungs[-1]["fingerprint"] == study.manifest("train")["fingerprint"]


def test_a_fixed_root_reproduces_its_draws_and_another_root_differs(tmp_path, study):
    first = study.draw()
    again = open_study(write_spec(tmp_path)).draw()
    assert {n: v["fingerprint"] for n, v in again.items()} == {
        n: v["fingerprint"] for n, v in first.items()
    }
    assert not any(v["newly_committed"] for v in again.values())
    assert kinds(study) == ["root", "set", "set", "set"]
    other = open_study(write_spec(tmp_path, name="other.json", study="other"))
    other.init()
    second = other.draw()
    for name in ss.SETS:
        assert second[name]["fingerprint"] != first[name]["fingerprint"]


def test_a_changed_size_after_commit_is_refused(tmp_path, study):
    study.draw()
    changed = open_study(write_spec(tmp_path, eval_cases=6))
    refused(changed.draw, "study_set_changed:eval")


@pytest.mark.parametrize("field", ss.HUMAN_INPUT_FIELDS)
@pytest.mark.parametrize("unset", [None, "HUMAN_INPUT"])
def test_every_unset_value_refuses_the_draw(tmp_path, study, field, unset):
    blocked = open_study(write_spec(tmp_path, **{field: unset}))
    refused(blocked.draw, "study_human_input_missing:" + field)
    assert kinds(study) == ["root"]


def test_init_waits_for_the_owner_approval(tmp_path):
    blocked = open_study(write_spec(tmp_path, approval="HUMAN_INPUT"))
    refused(blocked.init, "study_human_input_missing:approval")
    wrong = open_study(write_spec(tmp_path, approval={**APPROVAL, "sha256": "0" * 64}))
    refused(wrong.init, "study_not_approved")
    assert not (tmp_path / "study").exists()


def test_the_generation_ceiling_and_the_ladder_are_enforced(tmp_path, study):
    for overrides, code in (
        ({"generation_ceiling": 11}, "study_generation_ceiling_exceeded"),
        ({"train_size_ladder": [1, 1.1]}, "study_ladder_size_not_whole"),
        ({"train_size_ladder": [2, 1]}, "study_ladder_not_increasing"),
        ({"train_size": 0}, "study_spec_value_malformed:train_size"),
    ):
        refused(open_study(write_spec(tmp_path, **overrides)).draw, code)
    assert kinds(study) == ["root"]
    # A fractional multiple that makes whole cases is accepted as written.
    rungs = ss.ladder({**SIZES, "train_size_ladder": [0.5, 1, 2.5]})
    assert [size for _p, _m, size in rungs] == [2, 4, 10]


# --- overlap --------------------------------------------------------------------------


def _drawn(study):
    root, pin = study._open()
    sizes, _rungs = study._sizes()
    return study.documents(root, pin, sizes)


def test_a_published_case_stops_the_draw(study, monkeypatch):
    case = _drawn(study)["train"]["cases"][7]["inputs"]
    original = BatterySource.published

    def published(self, repository):
        return original(self, repository) | {self.key(case)}

    monkeypatch.setattr(BatterySource, "published", published)
    refused(study.draw, "study_overlaps_prior:published")
    assert kinds(study) == ["root"]


def test_a_private_prior_case_stops_the_draw(tmp_path, study):
    case = _drawn(study)["eval"]["cases"][2]["inputs"]
    blocked = open_study(
        write_spec(tmp_path, name="blocked.json", cases=[corner(), case])
    )
    caught = refused(blocked.draw, "study_overlaps_prior:private:live-pool")
    assert str(case[INPUTS[0]]) not in str(caught)
    assert kinds(study) == ["root"]


def test_the_study_sets_may_not_overlap_each_other(study, monkeypatch):
    original = BatterySource.study_draws

    def study_draws(self, root, pin, role, count):
        drawn = original(self, root, pin, role, count)
        if role == "study-eval":
            [(_c, first)] = original(self, root, pin, "study-train", 1)
            drawn[0] = (drawn[0][0], first)
        return drawn

    monkeypatch.setattr(BatterySource, "study_draws", study_draws)
    caught = refused(study.draw, "study_overlaps_prior:study:eval")
    assert caught.code.startswith("study_overlaps_prior:study:")
    assert kinds(study) == ["root"]


def test_a_missing_or_loose_private_prior_is_refused(tmp_path, study):
    missing = open_study(
        write_spec(tmp_path, private_priors={"live-pool": str(tmp_path / "none")})
    )
    refused(missing.draw, "study_private_prior_missing")
    loose = tmp_path / "loose.json"
    loose.write_text(json.dumps({"cases": [{"inputs": corner()}]}))
    loose.chmod(0o644)
    spec = write_spec(tmp_path, private_priors={"live-pool": str(loose)})
    refused(open_study(spec).draw, "study_private_prior_not_owner_only")
    assert kinds(study) == ["root"]


# --- references, export and the manifest ----------------------------------------------


def test_each_set_is_committed_before_any_export(tmp_path, study):
    out = tmp_path / "pod"
    refused(lambda: study.export(out), "study_set_not_committed:train")
    refused(lambda: study.jobs("eval"), "study_set_not_committed:eval")
    study.draw()
    refused(lambda: study.export(out), "study_references_pending:train")
    assert study.ingest("train") == {"set": "train", "state": "PENDING", "missing": 12}
    for name in ss.SETS:
        assert study.jobs(name)["jobs"] == study.manifest(name)["size"]
        assert study.solve(name) == {"set": name, "returncode": 0}
        assert study.ingest(name)["state"] == "COMPLETE"
    exported = study.export(out)
    assert sorted(p.name for p in out.iterdir()) == ["eval.json", "train.json"]
    entries = study.journal.entries()
    committed = {e["set"]: e["sequence"] for e in entries if e["kind"] == "set"}
    for name in ss.EXPORTED:
        assert committed[name] < exported[name]["journal_sequence"]
        payload = json.loads((out / f"{name}.json").read_text())
        assert payload["manifest"] == study.manifest(name)
        assert len(payload["cases"]) == len(payload["references"])
    assert [e["sequence"] for e in entries] == list(range(len(entries)))
    # A second export writes the same files and journals nothing new.
    assert study.export(out) == exported
    assert len(study.journal.entries()) == len(entries)


def test_the_manifest_holds_public_values_only(tmp_path, study):
    complete(study)
    study.export(tmp_path / "pod")
    exported = [
        json.loads((tmp_path / "pod" / f"{name}.json").read_text())
        for name in ss.EXPORTED
    ]
    case_ids = [c["case_id"] for p in exported for c in p["cases"]]
    case_ids += [c["case_id"] for c in study._committed("confirm")[1]["cases"]]
    values = [
        str(v)
        for p in exported
        for c in p["cases"]
        for v in c["inputs"].values()
        if len(str(v)) >= 6  # long enough not to match by chance
    ]
    public = [json.dumps(study.manifest(name)) for name in ss.SETS]
    public.append((tmp_path / "study" / "journal.jsonl").read_text())
    for text in public:
        assert "inputs" not in text and "case_id" not in text
        assert not any(c in text for c in case_ids)
        assert not any(v in text for v in values)
    manifest = study.manifest("eval")
    assert set(manifest) == {
        "schema",
        "challenge",
        "set",
        "role",
        "size",
        "fingerprint",
        "references_digest",
        "withdrawn",
        "overlap",
        "journal_sequence",
        "evidence",
    }
    assert manifest["schema"] == "carbon.training-budget.study-set.v1"
    assert manifest["overlap"]["verdict"] == "NO_OVERLAP"
    assert manifest["overlap"]["priors"] == [
        "private:live-pool",
        "public_decision",
        "published",
        "study:confirm",
        "study:train",
    ]
    assert set(manifest["overlap"]["private_prior_digests"]) == {"live-pool"}
    assert set(study.manifest("train")) == set(manifest) | {"ladder"}
    assert set(study.manifest("confirm")) == set(manifest) | {"released_sequence"}


def test_a_failed_reference_is_withdrawn_and_counted_never_dropped(tmp_path):
    made = open_study(write_spec(tmp_path), runner=scripted(failed={1, 6}))
    made.init()
    complete(made)
    train = made.manifest("train")
    assert train["withdrawn"] == 2
    # Sizes 4, 8 and 12: position 1 is in every rung, position 6 from 8 up.
    assert [r["withdrawn"] for r in train["ladder"]] == [1, 2, 2]
    assert made.manifest("eval")["withdrawn"] == 1
    made.export(tmp_path / "pod")
    payload = json.loads((tmp_path / "pod" / "train.json").read_text())
    ids = [c["case_id"] for c in payload["cases"]]
    assert payload["withdrawn"] == sorted([ids[1], ids[6]])
    assert payload["references"][ids[1]]["status"] == "REFERENCE_SOLVER_FAILED"
    assert len(payload["references"]) == 12


def test_failed_infra_leaves_a_set_pending(tmp_path, study):
    study.draw()
    study.jobs("confirm")
    _entry, document = study._committed("confirm")
    work = tmp_path / "study" / "work" / "confirm"
    with (work / "records.jsonl").open("w") as handle:
        for case in document["cases"]:
            record = {"case_id": case["case_id"], "status": "FAILED_INFRA"}
            handle.write(json.dumps(record) + "\n")
    (work / "records.jsonl").chmod(0o600)
    assert study.ingest("confirm")["state"] == "PENDING"
    assert "references" not in kinds(study)


def test_a_record_for_other_inputs_refuses_the_file(tmp_path, study):
    study.draw()
    study.jobs("eval")
    _entry, document = study._committed("eval")
    work = tmp_path / "study" / "work" / "eval"
    case = document["cases"][0]
    record = {"case_id": case["case_id"], "inputs": corner(), "status": "OK"}
    write_private(work / "records.jsonl", record)
    refused(lambda: study.ingest("eval"), "study_records_inputs_mismatch")


# --- the sealed confirmation set ------------------------------------------------------


def test_the_confirmation_set_is_released_once_after_the_limit(tmp_path, study):
    complete(study)
    out = tmp_path / "pod"
    study.export(out)
    assert not (out / "confirm.json").exists()
    journal = tmp_path / "harness.jsonl"
    release = lambda: study.release_confirmation(journal, out)
    harness_journal(journal, [])
    refused(release, "study_limit_not_frozen")
    harness_journal(journal, ["limit_frozen"])
    refused(release, "study_confirmation_not_opened")
    harness_journal(journal, ["confirmation_opened", "limit_frozen"])
    refused(release, "study_confirmation_opened_before_limit")
    harness_journal(journal, ["limit_frozen", "confirmation_opened"], schema="x")
    refused(release, "study_harness_journal_malformed")
    harness_journal(journal, ["limit_frozen", "confirmation_opened"], challenge=MOTOR)
    refused(release, "study_harness_journal_names_another_challenge")
    assert not (out / "confirm.json").exists()
    assert "confirmation_released" not in kinds(study)
    assert study.manifest("confirm")["released_sequence"] is None

    harness_journal(journal, ["limit_frozen", "planned", "confirmation_opened"])
    released = release()
    payload = json.loads((out / "confirm.json").read_text())
    assert len(payload["cases"]) == 3
    assert (
        payload["manifest"]["fingerprint"] == study.manifest("confirm")["fingerprint"]
    )
    entry = study.journal.entries()[-1]
    assert entry["kind"] == "confirmation_released"
    assert entry["sequence"] == released["journal_sequence"]
    assert entry["harness_journal_digest"].startswith("sha256:")
    assert study.manifest("confirm")["released_sequence"] == entry["sequence"]
    refused(release, "study_confirmation_already_released")
    refused(
        lambda: study.release_confirmation(journal, tmp_path / "again"),
        "study_confirmation_already_released",
    )
    assert kinds(study).count("confirmation_released") == 1


def test_the_confirmation_set_waits_for_its_references(tmp_path, study):
    complete(study, names=ss.EXPORTED)
    journal = harness_journal(
        tmp_path / "harness.jsonl", ["limit_frozen", "confirmation_opened"]
    )
    refused(
        lambda: study.release_confirmation(journal, tmp_path / "pod"),
        "study_references_pending:confirm",
    )
    assert "confirmation_released" not in kinds(study)


# --- custody --------------------------------------------------------------------------


def test_every_file_is_owner_only(tmp_path, study):
    complete(study)
    study.export(tmp_path / "pod")
    journal = harness_journal(
        tmp_path / "harness.jsonl", ["limit_frozen", "confirmation_opened"]
    )
    study.release_confirmation(journal, tmp_path / "pod")
    paths = [tmp_path / "study", tmp_path / "pod"]
    paths += [*(tmp_path / "study").rglob("*"), *(tmp_path / "pod").rglob("*")]
    assert len(paths) > 15
    for path in paths:
        assert os.lstat(path).st_mode & 0o077 == 0, path


def test_the_spec_is_loaded_only_owner_only_under_its_account(tmp_path):
    path = write_spec(tmp_path)
    refused(lambda: ss.load_spec(path, account="someone-else"), "study_wrong_account")
    path.chmod(0o640)
    refused(lambda: ss.load_spec(path, account=ME), "study_file_not_owner_only")
    path.chmod(0o600)
    document = json.loads(path.read_text())
    path.unlink()
    write_private(path, {**document, "extra": 1})
    refused(lambda: ss.load_spec(path, account=ME), "study_spec_malformed")
    inside = write_spec(tmp_path, name="inside.json", study=str(REPOSITORY / "x"))
    refused(lambda: ss.load_spec(inside, account=ME), "study_dir_inside_repository")


def test_init_never_overwrites_and_a_swapped_root_is_refused(tmp_path, study):
    refused(study.init, "study_dir_exists")
    root = tmp_path / "study" / "root.bin"
    root.chmod(0o600)
    root.write_bytes(os.urandom(32))
    refused(study.draw, "study_root_not_committed")


def test_a_challenge_without_study_draws_is_refused(tmp_path):
    path = write_spec(tmp_path, challenge_id=MOTOR)
    refused(lambda: open_study(path), "study_challenge_not_served")
    path = write_spec(tmp_path, name="unknown.json", challenge_id="no-such-challenge")
    refused(lambda: open_study(path), "study_challenge_not_served")


def test_the_command_line_answers_in_public_values(tmp_path, capsys):
    path = write_spec(tmp_path)
    assert ss.main(["manifest", "--spec", str(path), "--set", "eval"]) == 2
    assert json.loads(capsys.readouterr().out) == {"refused": "study_file_missing"}
    assert ss.main(["init", "--spec", str(path)]) == 0
    assert json.loads(capsys.readouterr().out)["journal_sequence"] == 0
    assert ss.main(["draw", "--spec", str(path)]) == 0
    capsys.readouterr()
    assert ss.main(["manifest", "--spec", str(path), "--set", "eval"]) == 0
    manifest = json.loads(capsys.readouterr().out)
    assert manifest["size"] == 5 and manifest["references_digest"] is None


# --- the reserved roles ---------------------------------------------------------------


def test_the_study_roles_are_reserved_in_every_spelling():
    assert interface.STUDY_ROLES == {"study-train", "study-eval", "study-confirm"}
    assert interface.STUDY_ROLES <= interface.RESERVED_SEED_ROLES
    assert set(ss.ROLES.values()) == interface.STUDY_ROLES
    for role in interface.STUDY_ROLES:
        assert interface.role_reserved(role.upper())


@pytest.mark.parametrize("role", ["study-train", "Study-Eval", "STUDY-CONFIRM"])
def test_the_producer_refuses_a_study_role(producer, source, role):  # noqa: F811
    with pytest.raises(pr.ProducerRefused) as caught:
        producer.draw(source.challenge_id, role, kind="screening")
    assert caught.value.code == "seed_role_reserved"
    assert producer.journal.entries() == []


@pytest.mark.parametrize("role", ["study-train", "STUDY-eval", "study-Confirm"])
def test_prepare_batch_refuses_a_study_role(source, role):  # noqa: F811
    with pytest.raises(ReservedRole) as caught:
        source.adapter.prepare_batch(role, kind="screening", count=4, duplicates=1)
    assert caught.value.code == "seed_role_reserved"
