"""A signer failure in a Control Center operation is honest about dispatch.

A signer that is not running, refuses, holds another hotkey or times out
signs nothing, so an operation that fails that way before any of its requests
was signed sent nothing: it is refused and the campaign is READY again. One
that fails after an earlier request of the same operation was signed may have
delivered that request, so it is never reported as a refusal - it goes to
reconciliation like any other ambiguous failure.

Both cases use a real signer over a real socket and a real `SignerFailure`.
"""

from types import SimpleNamespace

import pytest

from carbon.chain.external_signer import SignerCode, SignerFailure
from carbon.development_session import research_campaign
from scripts.dev.miner_launchpad.controller import Rejected
from scripts.dev.miner_launchpad.operations import _signer_reachable
from scripts.dev.miner_launchpad.runner import RunnerAdapter, signer_ready
from tests.cpu._signer_harness import in_thread_signer

RECEIVER = "5FHneW46xGXgs5mUiveU4sbTyGBzmstUspZC92UhjJM694ty"  # //Bob, public


def _key():
    from bittensor.keyfiles import Keypair

    return Keypair.create_from_uri("//Alice")


def _adapter_and_admitted(tmp_path, monkeypatch):
    monkeypatch.setattr(RunnerAdapter, "_cleanup", staticmethod(lambda _: True))
    adapter = RunnerAdapter(tmp_path / "runner.sqlite3", registration=lambda _: None)
    root = tmp_path / "campaign"
    root.mkdir(mode=0o700)
    admitted = SimpleNamespace(
        campaign={"id": "cmp-fixture", "root": str(root), "research_guidance": None},
        profile={"paths": {}, "accepted_revision": "a" * 40, "principal": "alice"},
    )
    return adapter, admitted


def _sign_once(signer):
    import time

    from carbon.chain.auth import BittensorMessageSigner

    BittensorMessageSigner(signer).sign(
        b"{}", receiver=RECEIVER, nonce_ns=time.time_ns()
    )


class _Prepared:
    def close(self):
        pass


def test_a_signer_failure_before_any_signature_is_a_refusal(tmp_path, monkeypatch):
    adapter, admitted = _adapter_and_admitted(tmp_path, monkeypatch)
    with in_thread_signer(_key()) as signer:
        pass  # the miner stopped their signer before this operation

    async def prepare(args, ledger):
        _sign_once(signer)

    monkeypatch.setattr(research_campaign, "prepare", prepare)
    with pytest.raises(Rejected) as refused:
        adapter._operate(admitted, lambda prepared: None)
    assert refused.value.code == SignerCode.NOT_RUNNING.value


def test_a_signer_failure_after_a_signature_is_not_a_refusal(tmp_path, monkeypatch):
    """Specimen for the other direction: the same failure, after this
    operation already obtained a signature, is not reported as nothing sent."""
    adapter, admitted = _adapter_and_admitted(tmp_path, monkeypatch)
    signing = in_thread_signer(_key())
    signer = signing.__enter__()

    async def prepare(args, ledger):
        _sign_once(signer)  # e.g. the bootstrap request, which is sent
        signing.__exit__(None, None, None)  # then the miner stops the signer
        return _Prepared()

    async def work(prepared):
        _sign_once(signer)

    monkeypatch.setattr(research_campaign, "prepare", prepare)
    with pytest.raises(SignerFailure) as failure:
        adapter._operate(admitted, work)
    assert failure.value.code == SignerCode.NOT_RUNNING.value


# --- the early answer at admission ------------------------------------------


def _probe(profile):
    """The admission gate, with the runner's real signer probe."""
    return _signer_reachable(SimpleNamespace(signer=signer_ready), profile)


def _profile(tmp_path, hotkey, socket_path):
    import json

    public = tmp_path / "miner-public.json"
    public.write_text(json.dumps({"netuid": 567, "hotkey": hotkey}))
    return {"paths": {"miner_public": str(public), "signer_socket": str(socket_path)}}


def test_admission_names_each_signer_condition(tmp_path):
    """Not running and a different hotkey are told apart at admission, before
    any work is admitted, and each carries its own code."""
    import socket

    key = _key()
    with in_thread_signer(key) as signer:
        path = signer._path
        _probe(_profile(tmp_path, key.ss58_address, path))  # the right signer
        with pytest.raises(Rejected) as wrong:
            _probe(_profile(tmp_path, RECEIVER, path))
        assert (wrong.value.code, wrong.value.status) == (
            SignerCode.WRONG_HOTKEY.value,
            409,
        )
    with pytest.raises(Rejected) as absent:
        _probe(_profile(tmp_path, key.ss58_address, path))
    assert (absent.value.code, absent.value.status) == (
        SignerCode.NOT_RUNNING.value,
        409,
    )
    # A socket that accepts and never answers: the signer's own timeout.
    silent = tmp_path / "silent.sock"
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    listener.bind(str(silent))
    listener.listen(1)
    try:
        with pytest.raises(Rejected) as late:
            _probe(_profile(tmp_path, key.ss58_address, silent))
    finally:
        listener.close()
    assert (late.value.code, late.value.status) == (SignerCode.TIMEOUT.value, 503)


def test_a_profile_naming_a_password_file_is_refused_by_name(tmp_path):
    """Carbon no longer reads a password for the miner's key. A profile that
    still names one is refused with a code that says to start the signer,
    rather than the file being silently ignored."""
    from scripts.dev.miner_launchpad.runner import PATH_FIELDS, validated_profile

    cfg = {
        "schema": "carbon.launchpad.runner-profile.v2",
        "profile_id": "opaque-profile",
        "principal": "alice",
        "enabled": True,
        "accepted_revision": "a" * 40,
        "campaigns_root": str(tmp_path / "campaigns"),
        "runtime": {},
        "paths": {key: str(tmp_path / key) for key in PATH_FIELDS},
    }
    cfg["paths"]["miner_password_file"] = str(tmp_path / "password")
    with pytest.raises(Rejected) as retired:
        validated_profile(cfg)
    assert (retired.value.code, retired.value.status) == (
        "miner_password_file_retired_start_signer",
        409,
    )
    # Specimen: the same profile without it is not refused for that reason.
    del cfg["paths"]["miner_password_file"]
    try:
        validated_profile(cfg)
    except Rejected as other:
        assert other.code != "miner_password_file_retired_start_signer"
    except ValueError:
        pass
