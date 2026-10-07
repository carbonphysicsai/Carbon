"""`write_once` publishes a file whole or not at all.

The Launchpad supervisor test `test_a_launch_interrupted_again_waits_for_its_miner`
failed once in CI with an empty campaign manifest: a reader checked the path
existed and read it between `write_once` creating it and writing it.
"""

from __future__ import annotations

import os
import stat
import threading

import pytest

from carbon.development_session import data
from carbon.development_session.data import write_once


def test_the_path_does_not_exist_until_its_bytes_are_synced(tmp_path, monkeypatch):
    target = tmp_path / "campaign-manifest.json"
    seen = []
    real = os.fsync

    def fsync(descriptor):
        seen.append(target.exists())
        return real(descriptor)

    monkeypatch.setattr(data.os, "fsync", fsync)
    write_once(target, b'{"challenge": "x"}')
    assert seen == [False]
    assert target.read_bytes() == b'{"challenge": "x"}'
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    assert [p.name for p in tmp_path.iterdir()] == ["campaign-manifest.json"]


def test_an_existing_file_is_never_replaced(tmp_path):
    target = tmp_path / "f.json"
    write_once(target, b"first")
    write_once(target, b"first")
    with pytest.raises(ValueError, match="conflict"):
        write_once(target, b"replacement")
    assert target.read_bytes() == b"first"
    assert [p.name for p in tmp_path.iterdir()] == ["f.json"]


def test_a_symlink_is_refused(tmp_path):
    (tmp_path / "real").write_bytes(b"x")
    (tmp_path / "link").symlink_to(tmp_path / "real")
    with pytest.raises(ValueError, match="symlink"):
        write_once(tmp_path / "link", b"x")


def test_a_concurrent_reader_never_sees_a_partial_file(tmp_path):
    payload = b'{"challenge": "battery"}' + b" " * 1_000_000
    stop, bad = threading.Event(), []

    def reader():
        while not stop.is_set():
            for path in tmp_path.glob("m*.json"):
                body = path.read_bytes()
                if body != payload:
                    bad.append(len(body))

    thread = threading.Thread(target=reader)
    thread.start()
    try:
        for i in range(40):
            write_once(tmp_path / f"m{i}.json", payload)
    finally:
        stop.set()
        thread.join()
    assert bad == []


def test_two_writers_of_the_same_bytes_both_succeed(tmp_path):
    target = tmp_path / "f.json"
    errors = []

    def write():
        try:
            write_once(target, b"same")
        except Exception as error:  # noqa: BLE001
            errors.append(error)

    threads = [threading.Thread(target=write) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == [] and target.read_bytes() == b"same"
