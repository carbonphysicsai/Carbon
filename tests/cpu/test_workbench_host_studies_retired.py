"""A retired Burgers Challenge leaves the Workbench host nothing to serve.

Owner decision, 2026-09-27: when Burgers is retired from the research path,
Workbench scientific studies go dark with a named refusal. Every study runs on
the fixed public Burgers definition, so the host refuses every command, by
name, before it loads a profile or attaches a campaign.

The registry decides whether Burgers is retired. Both states are forced here,
so the test means the same thing before and after the retirement lands.
"""

from __future__ import annotations

import asyncio
import dataclasses

import pytest

from carbon.challenge_registry import registry
from carbon.reconstruction.capability_registry import BURGERS_CHALLENGE
from carbon.scientific_tasks import workbench_host


def _burgers_status(monkeypatch, status):
    real = registry.entries()
    forced = tuple(
        (
            dataclasses.replace(entry, status=status)
            if entry.challenge_id == BURGERS_CHALLENGE
            else entry
        )
        for entry in real
    )
    assert any(entry.challenge_id == BURGERS_CHALLENGE for entry in forced)
    monkeypatch.setattr(registry, "entries", lambda: forced)


COMMANDS = [
    ["check", "--configuration", "/nonexistent/profile.json"],
    [
        "list-drafts",
        "--configuration",
        "/nonexistent/profile.json",
        "--draft-registry",
        "/nonexistent/drafts",
    ],
    [
        "register-draft",
        "--configuration",
        "/nonexistent/profile.json",
        "--draft-registry",
        "/nonexistent/drafts",
        "--draft",
        "/nonexistent/draft.json",
    ],
    [
        "serve",
        "--configuration",
        "/nonexistent/profile.json",
        "--draft-registry",
        "/nonexistent/drafts",
        "--static",
        "/nonexistent/static",
        "--principals",
        "/nonexistent/principals.json",
        "--origin",
        "http://127.0.0.1:1",
        "--port",
        "1",
    ],
]


@pytest.mark.parametrize("argv", COMMANDS, ids=[c[0] for c in COMMANDS])
def test_every_command_refuses_by_name_when_burgers_is_retired(
    monkeypatch, capsys, argv
):
    _burgers_status(monkeypatch, "RETIRED")
    assert workbench_host.main(argv) == workbench_host.STUDIES_RETIRED_EXIT
    err = capsys.readouterr().err
    assert (
        "Burgers Challenge" in err and "retired" in err and "Nothing was started" in err
    )
    # Refused before any configuration is read: the generic branch never ran.
    assert "Verify the private profile" not in err


@pytest.mark.parametrize("argv", COMMANDS, ids=[c[0] for c in COMMANDS])
def test_specimen_an_implemented_burgers_reaches_the_configuration(
    monkeypatch, capsys, argv
):
    # The same commands, with Burgers implemented, get past the refusal and
    # fail only on the missing configuration: the refusal is conditional.
    _burgers_status(monkeypatch, "IMPLEMENTED")
    assert workbench_host.main(argv) == 2
    err = capsys.readouterr().err
    assert "Verify the private profile" in err
    assert "retired" not in err


def test_serve_called_directly_refuses_too(monkeypatch):
    _burgers_status(monkeypatch, "RETIRED")
    with pytest.raises(workbench_host.StudiesRetired, match="Nothing was started"):
        asyncio.run(workbench_host.serve(object()))


def test_the_registry_decides_nothing_else():
    # Whatever the live registry says right now is what the host acts on.
    live = any(
        e.challenge_id == BURGERS_CHALLENGE and e.status == "RETIRED"
        for e in registry.entries()
    )
    assert workbench_host.studies_retired() is live
