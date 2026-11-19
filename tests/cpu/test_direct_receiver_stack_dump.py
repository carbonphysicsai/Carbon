"""Ops diagnosis (Live ops, 17 Nov 2026): the door registers ``kill -USR1`` to write every thread's stack to stderr.
19 Nov 2026: a Python handler over `sys._current_frames` (GIL held), never faulthandler's all-thread walk, which
crashed the live receiver mid-dump (SEGV)."""

import io
import signal
import threading

import pytest

from carbon.challenge_validator import direct_receiver


@pytest.mark.skipif(not hasattr(signal, "SIGUSR1"), reason="no SIGUSR1 here")
def test_the_door_registers_the_python_stack_dump_on_sigusr1():
    before = signal.getsignal(signal.SIGUSR1)
    try:
        direct_receiver.register_stack_dump()
        assert signal.getsignal(signal.SIGUSR1) is direct_receiver._dump_stacks
    finally:
        signal.signal(signal.SIGUSR1, before)


def test_the_dump_names_every_thread():
    """Every thread and its code locations, never a value."""
    secret = "value-7f3e-never-shown"  # a local the dump must not print
    parked = threading.Event()
    done = threading.Event()

    def worker_waits_here():
        parked.set()
        done.wait(10)

    thread = threading.Thread(target=worker_waits_here, name="grade-lane-x")
    thread.start()
    parked.wait(10)
    try:
        out = io.StringIO()
        direct_receiver._dump_stacks(stream=out)
    finally:
        done.set()
        thread.join()
    text = out.getvalue()
    assert "grade-lane-x (most recent call first):" in text
    assert "in worker_waits_here" in text
    assert "in " + test_the_dump_names_every_thread.__name__ in text
    assert secret not in text


def test_registering_off_the_main_thread_never_raises():
    failures = []

    def register():
        try:
            direct_receiver.register_stack_dump()
        except Exception as failure:  # noqa: BLE001
            failures.append(failure)

    thread = threading.Thread(target=register)
    thread.start()
    thread.join()
    assert failures == []


def test_a_broken_stream_never_raises():
    class Broken:
        def write(self, _text):
            raise OSError("closed")

    direct_receiver._dump_stacks(stream=Broken())
