"""The admission-conditions CLI and the designated admission controller.

GRAPHITE-ADMISSION-CONTROLLER-01, under OWNER-GRAPHITE-TEST-WAVE-03 §2 (W2:
an open finding blocks LOCK), approved by the Test Lead:

- `phase3 conditions` records a `carbon.admission-conditions.v1` report's
  conditions as findings on a phase-3 root's own controller, offline (no
  model, no pod, no RunPod key), idempotently, and prints the controller's
  identity; `--identity` prints only the identity.
- `CampaignController.identity()` is the bound grant's digest plus a
  write-once random store id: stable across opens, never a host path.
- `carbon/challenge_pipeline/admission_controllers.json` designates one
  controller per (Challenge, level); `check_lock` refuses any other
  (`admission_controller_not_designated`, `_mismatch`, `_identity_pending`),
  and `conditions` refuses to consume into another unless `--record-also`.

Each guard is switched off once (`MUTATIONS`) and its test shown to fail.
Synthetic grant copies and the retained EV2 report only: no spend, no pod, no
key; nothing here is scientific or security acceptance.
"""

from __future__ import annotations

import builtins
import hashlib
import itertools
import json
import os
import pathlib
from pathlib import Path

import graphite_phase3_fixtures as gp3
import pytest
import test_agent_campaign_controller as tc
import test_challenge_admission as tca

from carbon.agent_campaign import controller as ctl
from carbon.agent_campaign.controller import CampaignController
from carbon.agent_campaign.graphite import phase3
from carbon.agent_campaign.graphite import pods as pods_module
from carbon.agent_campaign.graphite.pods import PodFailure, ScriptedPods
from carbon.challenge_pipeline import admission_controllers as designations
from carbon.challenge_readiness import admission
from carbon.reconstruction.capability_registry import BATTERY_CHALLENGE

REPORT = tc.EV2_CONDITIONS
OTHER = "sha256:" + "d" * 64


# -- helpers ---------------------------------------------------------------------------
def designate(monkeypatch, directory, *entries):
    """Point the designation file at a test copy holding `entries`."""
    path = Path(directory) / "admission_controllers.json"
    path.write_text(
        json.dumps({"schema": designations.SCHEMA, "controllers": list(entries)})
    )
    monkeypatch.setattr(designations, "PATH", path)
    return path


def entry(challenge, identity, level=0, name="test-controller"):
    return {
        "challenge": challenge,
        "level": level,
        "name": name,
        "identity": identity,
        "status": designations.PENDING if identity is None else designations.DESIGNATED,
    }


def designate_controller(monkeypatch, directory, controller, challenge, level=0):
    """Designate `controller` for (challenge, level), as a LOCK test needs."""
    return designate(
        monkeypatch,
        directory,
        entry(challenge, controller.identity()["identity"], level),
    )


def phase3_root(directory):
    """A phase-3 root with its controller store, as a run leaves it, and the
    grant file it was opened under."""
    root = Path(directory) / "root"
    graphite = gp3.provider(root, [], ScriptedPods())
    gp3.controller(root, graphite).close()
    grant = Path(directory) / "grant.json"
    grant.write_text(json.dumps(gp3.grant_document()))
    return root, grant


def cli(capsys, root, grant, *extra, report=REPORT, challenge=BATTERY_CHALLENGE):
    """Run `phase3 conditions`; returns (exit code, stdout JSON, stderr)."""
    argv = ["conditions", "--root", str(root), "--grant", str(grant)]
    argv += ["--challenge", challenge]
    if "--identity" not in extra:
        argv += ["--report", str(report)]
    argv += list(extra)
    try:
        code = phase3.main(argv)
    except SystemExit as stop:
        code = stop.code
    captured = capsys.readouterr()
    return code, json.loads(captured.out), captured.err


def open_root(root):
    return gp3.controller(root, gp3.provider(root, [], ScriptedPods()))


def ledger_of(root):
    control = open_root(root)
    try:
        return control.ledger(), control.open_findings()
    finally:
        control.close()


def expected_ids(path=REPORT):
    body = Path(path).read_bytes()
    head = hashlib.sha256(body).hexdigest()[:12]
    report = json.loads(body)
    return [
        f"{head}-{index}-{c['condition']}"
        for index, c in enumerate(report["conditions"])
    ]


def identity_of(capsys, root, grant):
    code, out, _ = cli(capsys, root, grant, "--identity")
    assert code == 0
    return out["controller"]["identity"]


# -- consume, idempotent repeat ------------------------------------------------------------
def check_consume_and_repeat(tmp_path, monkeypatch, capsys):
    root, grant = phase3_root(tmp_path)
    designate(monkeypatch, tmp_path, entry(BATTERY_CHALLENGE, OTHER))
    identity = identity_of(capsys, root, grant)
    designate(monkeypatch, tmp_path, entry(BATTERY_CHALLENGE, identity))
    code, out, err = cli(capsys, root, grant)
    assert code == 0 and err == ""
    assert out["status"] == "CONSUMED" and out["level"] == 0
    assert out["finding_ids"] == expected_ids() and len(out["finding_ids"]) > 0
    assert {f["result"] for f in out["findings"]} == {"RECORDED"}
    assert out["controller"]["identity"] == identity
    assert out["designation"]["status"] == designations.DESIGNATED
    assert out["designation"]["lock_authority"] is True and out["warnings"] == []
    assert (
        out["report_sha256"]
        == "sha256:" + hashlib.sha256(REPORT.read_bytes()).hexdigest()
    )
    first, open_first = ledger_of(root)
    assert sorted(f["id"] for f in open_first) == sorted(out["finding_ids"])
    # A repeat with the same bytes: the same ids, nothing new, no error.
    code, again, _ = cli(capsys, root, grant)
    assert code == 0 and again["finding_ids"] == out["finding_ids"]
    assert {f["result"] for f in again["findings"]} == {"ALREADY_RECORDED"}
    second, open_second = ledger_of(root)
    assert second == first and open_second == open_first
    return root, grant, out


def test_conditions_consume_and_an_idempotent_repeat(tmp_path, monkeypatch, capsys):
    check_consume_and_repeat(tmp_path, monkeypatch, capsys)


def test_a_repeat_after_a_repair_reopens_the_finding(tmp_path, monkeypatch, capsys):
    """The controller's rule: a repaired finding recorded again is open again.
    A repeat never removes the repair; the CLI reports what happened."""
    root, grant, out = check_consume_and_repeat(tmp_path, monkeypatch, capsys)
    first = out["finding_ids"][0]
    control = open_root(root)
    try:
        control.record_repair(
            first,
            operator=phase3.OPERATOR,
            note="repaired the gate and re-ran the affected attacks",
            evidence=b"rerun report",
            rerun=["rerun-1"],
            code_ref="1" * 40,
        )
    finally:
        control.close()
    code, again, _ = cli(capsys, root, grant)
    results = {f["id"]: f["result"] for f in again["findings"]}
    assert code == 0 and results.pop(first) == "REOPENED_AFTER_REPAIR"
    assert set(results.values()) == {"ALREADY_RECORDED"}


# -- refusals ------------------------------------------------------------------------------
def check_lock_held(tmp_path, monkeypatch, capsys):
    root, grant = phase3_root(tmp_path)
    designate(monkeypatch, tmp_path, entry(BATTERY_CHALLENGE, None))
    holder = open_root(root)
    try:
        code, out, _ = cli(capsys, root, grant)
        assert code == 2 and out["reason_code"] == "controller_already_active"
        assert "Another process holds" in out["message"]
        assert holder.ledger() == []
    finally:
        holder.close()


def test_conditions_refuse_while_another_process_holds_the_lock(
    tmp_path, monkeypatch, capsys
):
    check_lock_held(tmp_path, monkeypatch, capsys)


def _report(tmp_path, name, body):
    path = Path(tmp_path) / name
    path.write_bytes(body if type(body) is bytes else json.dumps(body).encode())
    return path


def check_report_checked(tmp_path, monkeypatch, capsys):
    root, grant = phase3_root(tmp_path)
    designate(monkeypatch, tmp_path, entry(BATTERY_CHALLENGE, None))
    good = json.loads(REPORT.read_bytes())
    cases = {
        "conditions_report_schema_unsupported": [
            dict(good, schema="carbon.admission-condition.v1"),
            {k: v for k, v in good.items() if k != "schema"},
        ],
        "conditions_report_malformed": [
            b"{not json",
            [good],
            dict(good, conditions={"condition": "GATE_ANOMALY"}),
            dict(good, conditions=[{"member": "m"}]),
            dict(good, conditions=[{"condition": "NOT_A_CONDITION"}]),
            dict(good, level="0"),
            dict(good, level=-1),
            dict(good, level=True),
        ],
        "conditions_report_challenge_mismatch": [
            dict(good, challenge="chip-cold-plate")
        ],
        "conditions_report_unreadable": [None],
    }
    for code_expected, bodies in cases.items():
        for index, body in enumerate(bodies):
            path = (
                Path(tmp_path) / "missing.json"
                if body is None
                else _report(tmp_path, f"{code_expected}-{index}.json", body)
            )
            code, out, _ = cli(capsys, root, grant, report=path)
            assert (code, out["reason_code"]) == (2, code_expected), (index, out)
    assert ledger_of(root) == ([], [])


def test_conditions_refuse_a_wrong_schema_or_malformed_report(
    tmp_path, monkeypatch, capsys
):
    check_report_checked(tmp_path, monkeypatch, capsys)


def test_conditions_refuse_a_root_without_a_controller(tmp_path, monkeypatch, capsys):
    _root, grant = phase3_root(tmp_path)
    empty = tmp_path / "empty"
    code, out, _ = cli(capsys, empty, grant)
    assert (code, out["reason_code"]) == (2, "controller_store_missing")
    assert not (empty / "controller").exists()


def test_the_providers_capabilities_must_match_the_grant(tmp_path, capsys):
    root, _grant = phase3_root(tmp_path)
    other = tmp_path / "other-grant.json"
    other.write_text(json.dumps(gp3.grant_document(provider="fake")))
    code, out, _ = cli(capsys, root, other)
    assert (code, out["reason_code"]) == (2, "grant_provider_mismatch")
    # The grant the store is bound to must be the one given.
    changed = tmp_path / "changed-grant.json"
    changed.write_text(json.dumps(gp3.grant_document(grant_id="another-grant")))
    code, out, _ = cli(capsys, root, changed)
    assert (code, out["reason_code"]) == (2, "grant_changed_under_existing_store")


# -- no RunPod key is needed or read --------------------------------------------------------
class _WatchedEnviron(dict):
    def __init__(self, base, reads):
        super().__init__(base)
        self.reads = reads

    def __getitem__(self, key):
        self.reads.append(key)
        return super().__getitem__(key)

    def get(self, key, default=None):
        self.reads.append(key)
        return super().get(key, default)


def check_no_key_read(tmp_path, monkeypatch, capsys):
    root, grant = phase3_root(tmp_path)
    designate(monkeypatch, tmp_path, entry(BATTERY_CHALLENGE, None))
    home = tmp_path / "home"
    (home / ".runpod").mkdir(parents=True)
    (home / ".runpod" / "api_key").write_text("canary-not-a-key")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("RUNPOD_API_KEY", "canary-not-a-key")
    touched, env_reads = [], []

    def refuse(*_args, **_kwargs):
        raise AssertionError("a RunPod key path was reached")

    for target, name in (
        (phase3, "secret_file"),
        (phase3, "runpod_key_status"),
        (pods_module, "RunPodPods"),
    ):
        monkeypatch.setattr(target, name, refuse)
    real_open, real_read_bytes, real_read_text = (
        builtins.open,
        pathlib.Path.read_bytes,
        pathlib.Path.read_text,
    )

    def watched_open(file, *args, **kwargs):
        touched.append(str(file))
        return real_open(file, *args, **kwargs)

    def watched_bytes(self):
        touched.append(str(self))
        return real_read_bytes(self)

    def watched_text(self, *args, **kwargs):
        touched.append(str(self))
        return real_read_text(self, *args, **kwargs)

    with monkeypatch.context() as watch:
        watch.setattr(builtins, "open", watched_open)
        watch.setattr(pathlib.Path, "read_bytes", watched_bytes)
        watch.setattr(pathlib.Path, "read_text", watched_text)
        watch.setattr(os, "environ", _WatchedEnviron(os.environ, env_reads))
        try:
            code = phase3.main(
                [
                    "conditions",
                    "--root",
                    str(root),
                    "--grant",
                    str(grant),
                    "--challenge",
                    BATTERY_CHALLENGE,
                    "--report",
                    str(REPORT),
                ]
            )
        except SystemExit as stop:
            code = stop.code
    out = json.loads(capsys.readouterr().out)
    assert code == 0 and out["status"] == "CONSUMED"
    assert touched, "the watch saw no reads at all"
    assert not [p for p in touched if ".runpod" in p or "api_key" in p]
    assert not [k for k in env_reads if "RUNPOD" in str(k)]


def test_conditions_need_and_read_no_runpod_key(tmp_path, monkeypatch, capsys):
    check_no_key_read(tmp_path, monkeypatch, capsys)


def check_no_pods_refuse(_tmp_path, _monkeypatch, _capsys):
    nopods = phase3.NoPods()
    for name in ("launch", "wait", "fetch", "terminate", "charge", "recover"):
        with pytest.raises(PodFailure) as refused:
            getattr(nopods, name)(object(), object())
        assert refused.value.executed is False


def test_the_conditions_provider_refuses_every_pod(tmp_path, monkeypatch, capsys):
    check_no_pods_refuse(tmp_path, monkeypatch, capsys)


# -- identity -------------------------------------------------------------------------------
def check_identity_stable(tmp_path, _monkeypatch, _capsys):
    root, _grant = phase3_root(tmp_path)
    first = open_root(root)
    try:
        identity = first.identity()
    finally:
        first.close()
    store_id = (root / "controller" / ctl.STORE_ID_FILE).read_text().strip()
    assert identity["store_id"] == store_id and len(store_id) == 32
    assert (root / "controller" / ctl.STORE_ID_FILE).stat().st_mode & 0o777 == 0o600
    again = open_root(root)
    try:
        assert again.identity() == identity
    finally:
        again.close()
    # Never a host path.
    text = json.dumps(identity)
    assert str(tmp_path) not in text and "/" not in text.replace("sha256:", "")
    assert set(identity) == {"schema", "grant_digest", "store_id", "identity"}
    # Another store under the same grant is another controller.
    other, _ = phase3_root(tmp_path / "other")
    control = open_root(other)
    try:
        assert control.identity()["identity"] != identity["identity"]
        assert control.identity()["grant_digest"] == identity["grant_digest"]
    finally:
        control.close()


def test_the_identity_is_stable_across_opens(tmp_path, monkeypatch, capsys):
    check_identity_stable(tmp_path, monkeypatch, capsys)


def test_an_existing_store_gets_a_store_id_and_nothing_else_changes(tmp_path):
    root, _grant = phase3_root(tmp_path)
    control = open_root(root)
    control.record_finding("f-old", "OTHER_SIGNAL", b"old evidence")
    ledger = control.ledger()
    control.close()
    store = root / "controller"
    (store / ctl.STORE_ID_FILE).unlink()  # a store from before store ids
    database = (store / "campaign.sqlite3").read_bytes()
    names = sorted(p.name for p in store.rglob("*"))
    control = open_root(root)
    try:
        assert (store / ctl.STORE_ID_FILE).is_file()
        assert control.ledger() == ledger and control.verify_ledger()["consistent"]
        identity = control.identity()
    finally:
        control.close()
    assert (store / "campaign.sqlite3").read_bytes() == database
    assert sorted(p.name for p in store.rglob("*")) == sorted(
        [*names, ctl.STORE_ID_FILE]
    )
    control = open_root(root)
    assert control.identity() == identity
    control.close()


def test_a_damaged_store_id_is_refused(tmp_path):
    root, _grant = phase3_root(tmp_path)
    (root / "controller" / ctl.STORE_ID_FILE).write_text("not-an-id\n")
    with pytest.raises(ctl.ControllerError) as refused:
        open_root(root)
    assert refused.value.code == "controller_store_id_invalid"
    # The lease was released with the refusal.
    (root / "controller" / ctl.STORE_ID_FILE).unlink()
    open_root(root).close()


def test_identity_mode_consumes_nothing(tmp_path, monkeypatch, capsys):
    root, grant = phase3_root(tmp_path)
    designate(monkeypatch, tmp_path, entry(BATTERY_CHALLENGE, None, name="r2"))
    code, out, _ = cli(capsys, root, grant, "--identity")
    assert code == 0 and set(out) == {"controller", "designation"}
    assert out["designation"]["status"] == designations.IDENTITY_PENDING
    assert ledger_of(root) == ([], [])


# -- check_lock binding -------------------------------------------------------------------
def _lock_code(controller, block, challenge, **kw):
    with pytest.raises(admission.AdmissionError) as refused:
        controller.check_lock(block, challenge, repository=kw.pop("repo"), **kw)
    return refused.value.args[0]


def check_lock_not_designated(tmp_path, monkeypatch, _capsys):
    controller = tc.make(tmp_path)
    try:
        block = tca.accepted(tmp_path, "fixture")
        designate(
            monkeypatch, tmp_path, entry("another", controller.identity()["identity"])
        )
        assert _lock_code(controller, block, "fixture", repo=tmp_path) == (
            designations.NOT_DESIGNATED
        )
        # Designated at level 0 only: level 1 is not designated.
        designate_controller(monkeypatch, tmp_path, controller, "fixture")
        assert controller.check_lock(block, "fixture", repository=tmp_path) is block
        assert _lock_code(controller, block, "fixture", repo=tmp_path, level=1) == (
            designations.NOT_DESIGNATED
        )
    finally:
        controller.close()


def check_lock_mismatch(tmp_path, monkeypatch, _capsys):
    controller = tc.make(tmp_path)
    try:
        block = tca.accepted(tmp_path, "fixture")
        designate(monkeypatch, tmp_path, entry("fixture", OTHER))
        assert _lock_code(controller, block, "fixture", repo=tmp_path) == (
            designations.MISMATCH
        )
    finally:
        controller.close()


def check_lock_pending(tmp_path, monkeypatch, _capsys):
    controller = tc.make(tmp_path)
    try:
        block = tca.accepted(tmp_path, "fixture")
        designate(monkeypatch, tmp_path, entry("fixture", None))
        assert _lock_code(controller, block, "fixture", repo=tmp_path) == (
            designations.IDENTITY_PENDING
        )
    finally:
        controller.close()


def test_check_lock_refuses_an_undesignated_controller(tmp_path, monkeypatch, capsys):
    check_lock_not_designated(tmp_path, monkeypatch, capsys)


def test_check_lock_refuses_another_controller(tmp_path, monkeypatch, capsys):
    check_lock_mismatch(tmp_path, monkeypatch, capsys)


def test_check_lock_refuses_while_the_identity_is_pending(
    tmp_path, monkeypatch, capsys
):
    check_lock_pending(tmp_path, monkeypatch, capsys)


def test_the_committed_battery_level0_designation_is_pending(tmp_path):
    document = designations.load()
    (battery,) = [
        e
        for e in document["controllers"]
        if (e["challenge"], e["level"]) == (BATTERY_CHALLENGE, 0)
    ]
    assert battery["identity"] is None and battery["status"] == designations.PENDING
    controller = tc.make(tmp_path)
    try:
        # The designation is checked before anything in the block is read.
        assert _lock_code(controller, {}, BATTERY_CHALLENGE, repo=tmp_path) == (
            designations.IDENTITY_PENDING
        )
    finally:
        controller.close()


def test_the_designation_file_is_checked(tmp_path, monkeypatch):
    good = entry("fixture", OTHER)
    bad = [
        dict(good, name="/srv/runs/phase3-root"),
        dict(good, name="~/root"),
        dict(good, identity=None),
        dict(good, status=designations.PENDING),
        dict(good, status="LOCKED"),
        dict(good, level="0"),
        dict(good, level=True),
        dict(good, extra="x"),
        {k: v for k, v in good.items() if k != "status"},
    ]
    for index, body in enumerate(bad):
        designate(monkeypatch, tmp_path, body)
        with pytest.raises(designations.DesignationRefused) as refused:
            designations.load()
        assert refused.value.code == designations.MALFORMED, index
    designate(monkeypatch, tmp_path, good, good)
    with pytest.raises(designations.DesignationRefused):
        designations.load()
    (tmp_path / "admission_controllers.json").write_text("{")
    with pytest.raises(designations.DesignationRefused):
        designations.load()
    # A malformed file refuses every LOCK.
    controller = tc.make(tmp_path)
    try:
        assert _lock_code(controller, {}, "fixture", repo=tmp_path) == (
            designations.MALFORMED
        )
    finally:
        controller.close()


# -- the CLI and the designation ------------------------------------------------------------
def check_record_also(tmp_path, monkeypatch, capsys):
    root, grant = phase3_root(tmp_path)
    for designated in ((), (entry(BATTERY_CHALLENGE, OTHER),)):
        designate(monkeypatch, tmp_path, *designated)
        code_expected = (
            designations.MISMATCH if designated else designations.NOT_DESIGNATED
        )
        code, out, _ = cli(capsys, root, grant)
        assert (code, out.get("reason_code")) == (2, code_expected)
        assert "--record-also" in out["message"]
        assert ledger_of(root) == ([], [])
    code, out, err = cli(capsys, root, grant, "--record-also")
    assert code == 0 and out["finding_ids"] == expected_ids()
    assert out["designation"]["lock_authority"] is False
    assert out["designation"]["status"] == designations.MISMATCH
    assert "not the LOCK authority" in out["warnings"][0]
    assert "WARNING: --record-also" in err
    assert sorted(f["id"] for f in ledger_of(root)[1]) == sorted(expected_ids())


def test_record_also_records_into_a_root_that_is_not_the_authority(
    tmp_path, monkeypatch, capsys
):
    check_record_also(tmp_path, monkeypatch, capsys)


def check_pending_consumes_with_a_warning(tmp_path, monkeypatch, capsys):
    root, grant = phase3_root(tmp_path)
    designate(monkeypatch, tmp_path, entry(BATTERY_CHALLENGE, None, name="r2"))
    code, out, err = cli(capsys, root, grant)
    assert code == 0 and out["finding_ids"] == expected_ids()
    assert out["designation"]["status"] == designations.IDENTITY_PENDING
    assert out["designation"]["lock_authority"] is None
    assert "pending its operator-reported identity" in out["warnings"][0]
    assert "WARNING:" in err


def test_a_pending_designation_consumes_with_a_warning(tmp_path, monkeypatch, capsys):
    check_pending_consumes_with_a_warning(tmp_path, monkeypatch, capsys)


def test_the_committed_pending_designation_lets_the_r2_root_consume(tmp_path, capsys):
    root, grant = phase3_root(tmp_path)
    code, out, _ = cli(capsys, root, grant)
    assert code == 0 and out["designation"]["status"] == designations.IDENTITY_PENDING


def test_a_report_naming_a_level_is_checked_at_that_level(
    tmp_path, monkeypatch, capsys
):
    root, grant = phase3_root(tmp_path)
    identity = identity_of(capsys, root, grant)
    designate(monkeypatch, tmp_path, entry(BATTERY_CHALLENGE, identity))
    leveled = _report(
        tmp_path, "level1.json", dict(json.loads(REPORT.read_bytes()), level=1)
    )
    code, out, _ = cli(capsys, root, grant, report=leveled)
    assert (code, out["reason_code"]) == (2, designations.NOT_DESIGNATED)
    designate(
        monkeypatch,
        tmp_path,
        entry(BATTERY_CHALLENGE, identity),
        entry(BATTERY_CHALLENGE, identity, level=1),
    )
    code, out, _ = cli(capsys, root, grant, report=leveled)
    assert code == 0 and out["level"] == 1 and out["designation"]["lock_authority"]


# -- switching each guard off fails its test -------------------------------------------------
def _unchecked_report(path, challenge):
    body = Path(path).read_bytes()
    return body, json.loads(body), 0


def _reads_the_key(monkeypatch):
    original = phase3.conditions_controller

    def reads(root, grant, scoring):
        (Path.home() / ".runpod" / "api_key").read_bytes()
        return original(root, grant, scoring)

    monkeypatch.setattr(phase3, "conditions_controller", reads)


def _always_authority(monkeypatch):
    def authority(challenge, level, identity, record_also):
        return {"status": designations.DESIGNATED, "lock_authority": True}, []

    monkeypatch.setattr(phase3, "_designation", authority)


def _ignore_record_also(monkeypatch):
    original = phase3._designation
    monkeypatch.setattr(
        phase3,
        "_designation",
        lambda challenge, level, identity, record_also: original(
            challenge, level, identity, False
        ),
    )


def _duplicating_findings(monkeypatch):
    original = CampaignController._finding
    counter = itertools.count()

    def duplicate(self, db, finding_id, *args):
        return original(self, db, f"{finding_id}-{next(counter)}", *args)

    monkeypatch.setattr(CampaignController, "_finding", duplicate)


def _regenerated_store_id(monkeypatch):
    original = CampaignController._load_store_id

    def regenerate(self):
        (self.root / ctl.STORE_ID_FILE).unlink(missing_ok=True)
        return original(self)

    monkeypatch.setattr(CampaignController, "_load_store_id", regenerate)


MUTATIONS = {
    "cli_checks_the_report": (
        lambda m: m.setattr(phase3, "conditions_report", _unchecked_report),
        check_report_checked,
    ),
    "cli_refuses_a_held_lock": (
        lambda m: m.setattr(ctl.fcntl, "flock", lambda *a: None),
        check_lock_held,
    ),
    "cli_reads_no_key": (_reads_the_key, check_no_key_read),
    "no_pods_refuses_launch": (
        lambda m: m.setattr(phase3.NoPods, "launch", lambda self, *a: "handle"),
        check_no_pods_refuse,
    ),
    "cli_repeat_is_idempotent": (_duplicating_findings, check_consume_and_repeat),
    "identity_is_write_once": (_regenerated_store_id, check_identity_stable),
    "cli_refuses_an_undesignated_controller": (_always_authority, check_record_also),
    "cli_record_also_records": (_ignore_record_also, check_record_also),
    "cli_pending_consumes_with_a_warning": (
        lambda m: m.setattr(designations, "pending", lambda e: False),
        check_pending_consumes_with_a_warning,
    ),
    "lock_designation_checked": (
        lambda m: m.setattr(
            CampaignController, "_lock_designation_check", lambda *a: None
        ),
        check_lock_not_designated,
    ),
    "lock_not_designated": (
        lambda m: m.setattr(
            designations,
            "designation",
            lambda challenge, level, path=None: entry(challenge, OTHER, level),
        ),
        check_lock_not_designated,
    ),
    "lock_mismatch": (
        lambda m: m.setattr(designations, "_same_identity", lambda e, i: True),
        check_lock_mismatch,
    ),
    "lock_identity_pending": (
        lambda m: m.setattr(designations, "pending", lambda e: False),
        check_lock_pending,
    ),
}


@pytest.mark.parametrize("name", sorted(MUTATIONS))
def test_switching_a_guard_off_fails_its_test(name, tmp_path, monkeypatch, capsys):
    disable, guard = MUTATIONS[name]
    intact, mutated = tmp_path / "intact", tmp_path / "mutated"
    intact.mkdir()
    mutated.mkdir()
    guard(intact, monkeypatch, capsys)  # holds with the guard in place
    disable(monkeypatch)
    # Any failure of the guard's test: an assertion, a typed refusal it did not
    # expect, or a `pytest.raises` that saw nothing raised.
    with pytest.raises((Exception, pytest.fail.Exception)):
        guard(mutated, monkeypatch, capsys)
