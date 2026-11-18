"""V2's follow-up (18 Nov 2026): `AutoGrader._crown_held` reads the door's set-aside owners through the grader's
intake (`intake.adapter.provider_for.set_aside`) and answers False when it cannot. This builds that path for real: the
door's own `OwnerProviders` given to a `DirectRecipeIntake` as serve gives it, so a change of that wiring fails here
instead of silently switching the crown hold off."""

from __future__ import annotations

import hashlib

from test_c08_authenticated_miner_mcp import CONTEXT, NOW, _snapshot, _Verifier
from test_direct_v3_durable_tasks import _fixture

from carbon.battery.intake import SnapshotWindow
from carbon.challenge_kit.synthetic_linear_field_2d import bundle_material_v5
from carbon.challenge_validator import AttemptLedger
from carbon.challenge_validator import direct_receiver as receiver
from carbon.challenge_validator.auto_grade import AutoGrader
from carbon.challenge_validator.direct_intake import DirectRecipeIntake
from carbon.transport.store import ReceiptJournal

KING_OWNER = "5" + "3" * 47


def test_the_grader_reads_the_doors_own_set_aside_owners(tmp_path, monkeypatch):
    from carbon.backbone_catalog import gpu_receipt

    monkeypatch.setattr(gpu_receipt, "OFFICIAL_STORE", None)
    _request, _factory, discovery = _fixture(
        tmp_path / "direct", monkeypatch, material=bundle_material_v5()
    )
    providers = receiver.OwnerProviders(tmp_path / "owners", discovery, None, None)
    root = tmp_path / "attempts"
    root.mkdir(mode=0o700)
    root.chmod(0o700)
    window = SnapshotWindow(clock=lambda: NOW / 1_000_000_000)
    window.add(_snapshot())
    intake = DirectRecipeIntake(
        context=CONTEXT,
        receiver="validator",
        journal=ReceiptJournal(tmp_path / "transport.sqlite3", CONTEXT),
        verifier=_Verifier(),
        window=window,
        discovery=discovery,
        provider_for=providers,  # as `direct_receiver.serve` wires it
        attempt_ledger=AttemptLedger(root / "ledger.sqlite3"),
        clock_ns=lambda: NOW,
    )
    grader_root = tmp_path / "grader"
    grader_root.mkdir(mode=0o700)
    grader = AutoGrader(intake, grader_root)
    grader._prelude_owners = lambda: {KING_OWNER}
    assert intake.adapter.provider_for is providers
    assert grader._crown_held() is False
    providers._set_aside[hashlib.sha256(KING_OWNER.encode()).hexdigest()] = "ValueError"
    assert grader._crown_held() is True
