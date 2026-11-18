"""Ops diagnosis (Live ops, 17 Nov 2026): the door registers ``kill -USR1`` to write every thread's stack to stderr."""

import faulthandler
import signal

import pytest

from carbon.challenge_validator import direct_receiver


@pytest.mark.skipif(not hasattr(signal, "SIGUSR1"), reason="no SIGUSR1 here")
def test_the_door_registers_a_stack_dump_on_sigusr1():
    try:
        direct_receiver.register_stack_dump()
        assert faulthandler.unregister(signal.SIGUSR1) is True
    finally:
        faulthandler.unregister(signal.SIGUSR1)


def test_a_stderr_with_no_file_descriptor_never_stops_the_start(monkeypatch):
    """Runner (17 Nov 2026): under a captured or redirected stderr the hook raised io.UnsupportedOperation from main()."""
    import io

    def no_fileno(*args, **kwargs):
        raise io.UnsupportedOperation("fileno")

    monkeypatch.setattr(faulthandler, "register", no_fileno)
    direct_receiver.register_stack_dump()  # never raises
