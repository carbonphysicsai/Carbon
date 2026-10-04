"""GRAPHITE-01 phase 2: the runner's refusals, credential handling and dry run.

No live inference: the one live-path test replaces `LiveModel` with a
scripted stand-in that records the credential reference it was given.
"""

from __future__ import annotations

import io
import json
import stat
from pathlib import Path
from typing import ClassVar

import pytest
from graphite_fixtures import grant_document
from graphite_phase2_fixtures import GRANT_FILE, REPOSITORY, entry, replies, seed

from carbon.agent_campaign.graphite import phase2
from carbon.agent_campaign.graphite.model import ScriptedModel

KEY = "fixture-key-0123456789-not-a-real-key"


def _main(capsys, *argv, **kw):
    try:
        code = phase2.main(list(argv)) if not kw else kw["call"]()
    except SystemExit as exit_:
        code = exit_.code
    return code, capsys.readouterr().out


def test_triage_refuses_without_a_grant(tmp_path, capsys):
    seed(tmp_path, entry(1))
    code, out = _main(capsys, "triage", "--root", str(tmp_path))
    assert code == 2
    assert json.loads(out) == {"status": "REFUSED", "reason_code": "grant_required"}


def test_triage_refuses_the_human_input_grant_before_reading_a_key(
    tmp_path, capsys, monkeypatch
):
    seed(tmp_path, entry(1))
    unfinished = json.loads(GRANT_FILE.read_bytes())
    unfinished["account"] = "HUMAN_INPUT"
    grant_file = tmp_path / "grant.json"
    grant_file.write_text(json.dumps(unfinished))
    monkeypatch.setenv("ENGY_API_KEY", KEY)
    code, out = _main(
        capsys,
        "triage",
        "--root",
        str(tmp_path),
        "--grant",
        str(grant_file),
        "--credential-env",
        "ENGY_API_KEY",
    )
    assert code == 2
    assert json.loads(out)["reason_code"] == "grant_refused: grant_value_missing"
    assert KEY not in out


def test_a_root_inside_the_repository_is_refused(capsys):
    code, out = _main(capsys, "cards", "--root", str(REPOSITORY / "docs" / "x"))
    assert code == 2
    assert json.loads(out)["reason_code"] == "root_must_be_outside_the_repository"
    assert not (REPOSITORY / "docs" / "x").exists()


def test_a_key_from_the_environment_becomes_a_private_file_removed_on_exit():
    with phase2.credential_file(
        env="ENGY_API_KEY", environ={"ENGY_API_KEY": KEY}
    ) as path:
        target = Path(path)
        assert target.read_text() == KEY
        assert stat.S_IMODE(target.stat().st_mode) == 0o600
        assert stat.S_IMODE(target.parent.stat().st_mode) == 0o700
    assert not target.exists() and not target.parent.exists()


@pytest.mark.parametrize(
    "kw, code",
    [
        ({}, "one_of_credential_file_or_credential_env_required"),
        (
            {"path": "/x", "env": "ENGY_API_KEY"},
            "one_of_credential_file_or_credential_env_required",
        ),
        ({"env": "ENGY_API_KEY", "environ": {}}, "credential_env_empty"),
        ({"env": "OPENAI_API_KEY", "environ": {}}, "credential_env_not_recognised"),
        (
            {"env": "CHUTES_API_KEY", "environ": {"CHUTES_API_KEY": KEY}},
            "chutes_adapter_not_wired_into_graphite_yet",
        ),
        ({"path": "/nonexistent/graphite/key"}, "credential_file_missing"),
    ],
)
def test_credential_refusals(kw, code, capsys):
    with pytest.raises(SystemExit), phase2.credential_file(**kw):
        pass
    assert json.loads(capsys.readouterr().out)["reason_code"] == code


class _FakeLive(ScriptedModel):
    """Stands in for `LiveModel`: live, bound to the grant, scripted replies."""

    live = True
    seen: ClassVar[list] = []

    def __init__(self, *, grant, credential_file, provider):
        super().__init__(replies(2))
        self.grant = grant
        self.credential_reference = credential_file
        key = Path(credential_file)
        _FakeLive.seen.append(
            (credential_file, key.read_text(), stat.S_IMODE(key.stat().st_mode))
        )


def test_the_live_path_passes_a_file_reference_and_never_prints_the_key(
    tmp_path, capsys, monkeypatch
):
    seed(tmp_path, entry(1), entry(2))
    document = grant_document(worst_case_run_cost="0.50")
    grant_path = tmp_path / "grant.json"
    grant_path.write_text(json.dumps(document))
    monkeypatch.setattr(phase2, "LiveModel", _FakeLive)
    code, out = _main(
        capsys,
        call=lambda: phase2.run_triage(
            phase2.parser().parse_args(
                [
                    "triage",
                    "--root",
                    str(tmp_path),
                    "--grant",
                    str(grant_path),
                    "--credential-env",
                    "ENGY_API_KEY",
                ]
            ),
            environ={"ENGY_API_KEY": KEY},
        ),
    )
    assert code == 0, out
    summary = json.loads(out)
    assert summary["status"] == "COMPLETED" and summary["cards_made"] == 2
    ((reference, content, mode),) = _FakeLive.seen
    assert content == KEY and mode == 0o600
    assert not Path(reference).exists()
    assert KEY not in out
    run = json.loads(
        (tmp_path / "backfill" / "runs" / "backfill-1" / "run.json").read_bytes()
    )
    assert KEY not in json.dumps(run)
    assert run["selection"]["credential"]["kind"] == "file"


def test_a_dry_run_writes_only_under_dry_run_and_sends_nothing(tmp_path, capsys):
    seed(tmp_path, entry(1), entry(2))
    code, out = _main(capsys, "triage", "--root", str(tmp_path), "--dry-run")
    assert code == 0
    summary = json.loads(out)
    assert summary["dry_run"] is True and summary["cards_made"] == 2
    assert (tmp_path / "dry-run" / "cards" / "cards").is_dir()
    assert not (tmp_path / "backfill").exists()
    code, out = _main(capsys, "cards", "--root", str(tmp_path), "--dry-run")
    rows = json.loads(out)
    assert {row["method_name"] for row in rows} == {"DRY RUN: not extracted"}
    first = _main(capsys, "snapshot", "--root", str(tmp_path), "--dry-run")[1]
    second = _main(capsys, "snapshot", "--root", str(tmp_path), "--dry-run")[1]
    assert first == second
    code, out = _main(
        capsys, "triage", "--root", str(tmp_path), "--dry-run", "--grant", "g.json"
    )
    assert json.loads(out)["reason_code"] == "dry_run_takes_no_grant_or_credential"


def test_a_check_needs_an_interactive_terminal(tmp_path, capsys):
    seed(tmp_path, entry(1))
    args = phase2.parser().parse_args(
        [
            "check",
            "--root",
            str(tmp_path),
            "--card",
            "arxiv-2610.00001v1",
            "--checker",
            "Ryan",
            "--verdict",
            "CORRECT",
        ]
    )
    code, out = _main(
        capsys, call=lambda: phase2.check(args, stdin=io.StringIO(""), confirm=input)
    )
    assert code == 2
    assert json.loads(out)["reason_code"] == "human_check_needs_an_interactive_terminal"
