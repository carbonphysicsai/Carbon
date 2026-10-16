"""Input and orchestration refusals; no fabricated CAL/EVAL certificate."""

from __future__ import annotations

import hashlib
import json

import pytest

from carbon.design_search import tasks
from scripts.dev.score_lab import guarded419_eval as evaluation
from scripts.dev.score_lab import guarded419_eval_worker as worker


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def test_registered_subset_is_nonempty_ordered_and_role_closed():
    offered = [
        {
            "case_id": case,
            "reference_role": "PUBLIC_EVALUATION",
            "reference_admission": evaluation.ADMISSION,
        }
        for case in ("a", "b", "c")
    ]
    assert worker._selected({"selected_job_ids": ["a", "c"]}, offered) == [
        offered[0],
        offered[2],
    ]
    for bad in ([], ["c", "a"], ["a", "a"], ["unknown"], [None]):
        with pytest.raises(tasks.TaskError):
            worker._selected({"selected_job_ids": bad}, offered)
    with pytest.raises(tasks.TaskError, match="role"):
        worker._selected(
            {"selected_job_ids": ["a"]},
            [{**offered[0], "reference_role": "PUBLIC_CONSTRUCTION"}],
        )


def test_member_files_match_every_original_byte_pin_without_roster_aliases():
    member = {"id": "member-1"}
    raw_by_name = {}
    entries = {}
    for name, field in worker.MEMBER_FILES.items():
        raw = name.encode()
        member[field] = _sha(raw)
        raw_by_name[name] = raw
        entries[name] = {"path": name, "sha256": _sha(raw)}
    cohort = {"members": [member]}
    spec = {"member_files": {"member-1": entries}}
    worker._member_files(spec, cohort, raw_by_name.__getitem__)
    with pytest.raises(tasks.TaskError, match="all eighteen"):
        worker._member_files({"member_files": {}}, cohort, raw_by_name.__getitem__)
    changed = json.loads(json.dumps(spec))
    changed["member_files"]["member-1"]["fit_receipt"]["sha256"] = "0" * 64
    with pytest.raises(tasks.TaskError, match="content pin"):
        worker._member_files(changed, cohort, raw_by_name.__getitem__)
    changed = json.loads(json.dumps(spec))
    changed["member_files"]["member-1"]["predictions"]["path"] = "fit_receipt"
    with pytest.raises(tasks.TaskError, match="path reused"):
        worker._member_files(changed, cohort, raw_by_name.__getitem__)
    changed = dict(raw_by_name)
    changed["predictions"] = b"different original bytes"
    with pytest.raises(tasks.TaskError, match="independent pin"):
        worker._member_files(spec, cohort, changed.__getitem__)


def test_gitless_execution_source_requires_exact_bootstrap_ref_and_bytes(tmp_path):
    raw = b"bounded runner source"
    path = tmp_path / worker.MODULE
    path.parent.mkdir(parents=True)
    path.write_bytes(raw)
    pins = {"execution_source": "a" * 40, "files": {}}
    with pytest.raises(tasks.TaskError, match="CODE_REF"):
        worker._source(pins, _sha(raw), tmp_path, environ={"CODE_REF": "b" * 40})
    assert (
        worker._source(pins, _sha(raw), tmp_path, environ={"CODE_REF": "a" * 40})
        == "POD_BOOTSTRAP_CODE_REF_AND_LOCAL_FILE_HASHES"
    )
    path.write_bytes(b"changed")
    with pytest.raises(tasks.TaskError, match="source bytes"):
        worker._source(pins, _sha(raw), tmp_path, environ={"CODE_REF": "a" * 40})
    pins["files"] = {"same.py": "0" * 64}
    with pytest.raises(tasks.TaskError, match="CAL and EVAL"):
        worker._source(
            pins,
            _sha(raw),
            tmp_path,
            {"same.py": "1" * 64},
            environ={"CODE_REF": "a" * 40},
        )


def test_file_spec_and_worker_limit_refuse_before_any_truth(monkeypatch, tmp_path):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("must not reach source, CAL, or truth")

    monkeypatch.setattr(worker, "_source", forbidden)
    monkeypatch.setattr(worker, "_provenance", forbidden)
    with pytest.raises(tasks.TaskError, match="one or two workers"):
        worker.run({}, load=forbidden, records_path=tmp_path / "records", workers=3)
    with pytest.raises(tasks.TaskError, match="file specification"):
        worker.run({}, load=forbidden, records_path=tmp_path / "records", workers=2)
    assert not (tmp_path / "records").exists()


def test_cli_rejects_unpinned_spec_bytes_before_run(monkeypatch, tmp_path):
    spec = tmp_path / "spec.json"
    spec.write_text("{}\n", encoding="utf-8")
    public = tmp_path / "public"
    public.mkdir()

    def forbidden(*_args, **_kwargs):
        raise AssertionError("unbound invocation reached runner")

    monkeypatch.setattr(worker, "run", forbidden)
    with pytest.raises(tasks.TaskError, match="Root-pinned"):
        worker.main(
            [
                "--spec",
                str(spec),
                "--spec-sha256",
                "0" * 64,
                "--public-root",
                str(public),
                "--records",
                str(tmp_path / "records"),
            ]
        )
    assert not (tmp_path / "records").exists()
