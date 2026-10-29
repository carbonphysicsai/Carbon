"""The scripted pre-mainnet attacks (scripts/dev/mainnet_attack_tests.py): none succeeds against this build, and
the live-run sentinel scanner finds a planted sentinel in every encoding it claims to handle.
"""

from __future__ import annotations

import base64

from scripts.dev import mainnet_attack_tests as attacks

SENTINEL = attacks.SENTINEL


def test_no_attack_succeeds_in_the_fast_run():
    results = attacks.run(seed=7, fast=True)
    assert {r.id for r in results} >= {"G1a", "G1f", "G4a", "G5c", "G6a"}
    failed = [(r.id, r.observed) for r in results if r.verdict == "FAIL"]
    assert failed == []


def test_the_scanner_finds_the_sentinel_in_each_encoding_and_passes_a_clean_directory(
    tmp_path,
):
    clean = tmp_path / "clean"
    clean.mkdir()
    (clean / "ladder.json").write_text('{"status": "IMPROVED", "total": 0.62}')
    assert attacks.scan_directory(clean, [SENTINEL]) == []
    raw = SENTINEL.encode()
    planted = {
        "raw.json": SENTINEL,
        "lower.json": SENTINEL.lower(),
        "hex.json": raw.hex(),
        "b64.json": base64.b64encode(raw).decode(),
        "b64url_shifted.json": base64.urlsafe_b64encode(b"\0" + raw).decode(),
    }
    for name, text in planted.items():
        directory = tmp_path / name.split(".")[0]
        directory.mkdir()
        (directory / name).write_text('{"x": "' + text + '"}')
        assert attacks.scan_directory(directory, [SENTINEL]), name
