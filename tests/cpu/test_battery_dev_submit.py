"""Graphite's signed door to a hidden deployment on another host, and the
service-account guard (VALIDATOR-19 slice 0).

Battery's daemon fixtures (published PyBaMM references, `DirectBackend` in
process); the "host" runs in this process. No network beyond loopback, no
spend. Not a security audit (AGENTS.md §13).
"""

import json
import os
import pwd
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tests" / "cpu"))

from test_battery_validator_daemon import refs  # noqa: F401 - fixture
from test_graphite_hidden_l1 import L1, VARIANT
from test_graphite_hidden_score import TEMPO, deployment, knn

from carbon.agent_campaign.graphite import phase3
from carbon.battery import deployment as battery_deployment
from carbon.battery import dev_submit as ds
from carbon.battery import worker
from carbon.challenge_validator.scoring import scoring_for
from carbon.reconstruction.capability_registry import BATTERY_CHALLENGE as BATTERY

ME = pwd.getpwuid(os.geteuid()).pw_name


@pytest.fixture
def key(tmp_path):
    return ds.SubmitterKey.create(tmp_path / "submitter.key")


@pytest.fixture
def host(tmp_path, refs):  # noqa: F811
    target = deployment(tmp_path / "host", refs, worker.DirectBackend(REPOSITORY))
    target.development_only = True
    return target


def service(tmp_path, target, key, **kw):
    return ds.DevSubmitService(
        target,
        public_key=key.public_key,
        clock=lambda: TEMPO + 5,
        nonce_file=tmp_path / "nonces",
        operator_dir=tmp_path / "operator",
        **kw,
    )


def base_digest():
    return scoring_for(BATTERY).contract().digest


# -- the key and the request ----------------------------------------------------------------


def test_the_key_is_owner_only_and_never_printed(tmp_path, key):
    assert "<redacted>" in repr(key)
    loaded = ds.SubmitterKey.load(tmp_path / "submitter.key")
    assert loaded.public_key == key.public_key
    (tmp_path / "submitter.key").chmod(0o644)
    with pytest.raises(ds.DevSubmitRefused):
        ds.SubmitterKey.load(tmp_path / "submitter.key")


def signed(key, **changes):
    values = {
        "run_id": "run-1",
        "role": "constructor",
        "strategy": knn(),
        "contract_digest": base_digest(),
    }
    values.update(changes)
    return ds.request(key, **values)


def test_a_signed_request_verifies(key):
    body = ds.verify(signed(key), key.public_key)
    assert body["run_id"] == "run-1"


@pytest.mark.parametrize(
    ("mutate", "code"),
    [
        (lambda s: s["body"].update(run_id="run-2"), "dev_submit_signature"),
        (lambda s: s.update(signature="00" * 64), "dev_submit_signature"),
        (lambda s: s["body"].pop("nonce"), "dev_submit_malformed"),
        (lambda s: s.update(extra=1), "dev_submit_malformed"),
    ],
)
def test_a_tampered_request_is_refused(key, mutate, code):
    request = signed(key)
    mutate(request)
    with pytest.raises(ds.DevSubmitRefused) as refused:
        ds.verify(request, key.public_key)
    assert refused.value.code == code


def test_another_key_and_a_stale_request_are_refused(tmp_path, key):
    other = ds.SubmitterKey.create(tmp_path / "other.key")
    with pytest.raises(ds.DevSubmitRefused) as refused:
        ds.verify(signed(other), key.public_key)
    assert refused.value.code == "dev_submit_signature"
    old = ds.request(
        key,
        run_id="r",
        role="baseline",
        strategy=knn(),
        contract_digest=base_digest(),
        now=time.time() - 120,
    )
    with pytest.raises(ds.DevSubmitRefused) as refused:
        ds.verify(old, key.public_key)
    assert refused.value.code == "dev_submit_stale"


# -- the host -------------------------------------------------------------------------------


def test_the_host_serves_only_a_development_deployment(tmp_path, host, key):
    host.development_only = False
    with pytest.raises(ds.DevSubmitRefused) as refused:
        service(tmp_path, host, key)
    assert refused.value.code == "dev_submit_needs_a_development_only_deployment"


def test_a_level_0_submission_returns_only_the_sealed_view(tmp_path, host, key):
    door = service(tmp_path, host, key)
    view = door.handle(signed(key))
    assert view["state"] == "SCORED"
    assert not {"aggregate", "submission_id"} & set(view)
    assert not {"screening", "nominated", "finals"} & set(view["outcome"])
    # The operator record stays on the host, owner-only.
    [record] = list((tmp_path / "operator" / "run-1").glob("*.json"))
    assert record.stat().st_mode & 0o077 == 0
    assert json.loads(record.read_text())["replay"] == "REPRODUCED"
    assert door.report("run-1")["primary"]["by_pool_version"]


def test_a_replayed_request_is_refused(tmp_path, host, key):
    door = service(tmp_path, host, key)
    request = signed(key, role="baseline")
    door.handle(request)
    with pytest.raises(ds.DevSubmitRefused) as refused:
        door.handle(request)
    assert refused.value.code == "dev_submit_replay"


def test_a_level_1_submission_goes_through_its_registered_variant(tmp_path, host, key):
    door = service(tmp_path, host, key)
    view = door.handle(signed(key, strategy=L1, contract_digest=VARIANT.digest))
    assert view["state"] == "SCORED", view
    [record] = list((tmp_path / "operator" / "run-1").glob("*.json"))
    assert json.loads(record.read_text())["level"] == 1


# -- Graphite's side, across the wire -------------------------------------------------------


def test_graphite_reaches_the_host_and_holds_nothing_hidden(tmp_path, host, key):
    door = service(tmp_path, host, key)
    config = {"host": "127.0.0.1", "port": 0}
    server = ds.make_server(door, config, repository=REPOSITORY)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_address[1]}"
        remote = ds.RemoteHiddenPool(
            url,
            key,
            run_id="run-9",
            challenge_id=BATTERY,
            contract_digest=base_digest(),
        )
        view, operator = remote.submit("proposal", knn(7))
        assert view["state"] == "SCORED"
        assert operator is None
        # A forged request is refused at the door, by code.
        forged = ds.RemoteHiddenPool(
            url,
            ds.SubmitterKey.create(tmp_path / "forged.key"),
            run_id="run-9",
            challenge_id=BATTERY,
            contract_digest=base_digest(),
        )
        view, _ = forged.submit("proposal", knn(8))
        assert (view["state"], view["code"]) == ("UNAVAILABLE", "dev_submit_signature")
    finally:
        server.shutdown()


def self_signed(directory, ip):
    """HIDDEN_HOST_SETUP.md §5's certificate command, verbatim but for paths."""
    if shutil.which("openssl") is None:
        pytest.skip("openssl is not installed")
    subprocess.run(
        [
            "openssl", "req", "-x509", "-newkey", "ec",
            "-pkeyopt", "ec_paramgen_curve:prime256v1", "-nodes", "-days", "825",
            "-subj", "/CN=carbon-hidden", "-addext", f"subjectAltName=IP:{ip}",
            "-keyout", str(directory / "tls.key"), "-out", str(directory / "tls.crt"),
        ],
        check=True,
        capture_output=True,
    )  # fmt: skip
    return directory / "tls.crt", directory / "tls.key"


def test_graphite_trusts_only_the_pinned_certificate(tmp_path, host, key):
    door = service(tmp_path, host, key)
    cert, private = self_signed(tmp_path, "127.0.0.1")
    other = tmp_path / "other"
    other.mkdir()
    other_cert, _ = self_signed(other, "127.0.0.1")
    config = {
        "host": "127.0.0.1",
        "port": 0,
        "tls_cert": str(cert),
        "tls_key": str(private),
    }
    server = ds.make_server(door, config, repository=REPOSITORY)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"https://127.0.0.1:{server.server_address[1]}"

        def remote(ca):
            return ds.RemoteHiddenPool(
                url,
                key,
                run_id="run-tls",
                challenge_id=BATTERY,
                contract_digest=base_digest(),
                ca=ca,
            )

        view, _ = remote(cert).submit("proposal", knn(7))
        assert view["state"] == "SCORED"
        # Another certificate, or the system trust store, is refused.
        for ca in (other_cert, None):
            view, _ = remote(ca).submit("proposal", knn(9))
            assert (view["state"], view["code"]) == (
                "UNAVAILABLE",
                "dev_submit_unreachable",
            )
    finally:
        server.shutdown()


def test_a_remote_pool_needs_tls_beyond_loopback(key):
    with pytest.raises(ds.DevSubmitRefused) as refused:
        ds.RemoteHiddenPool(
            "http://203.0.113.5:8468",
            key,
            run_id="r",
            challenge_id=BATTERY,
            contract_digest=base_digest(),
        )
    assert refused.value.code == "dev_submit_needs_tls"


def test_phase3_builds_a_remote_factory_from_the_key(tmp_path, key):
    factory = phase3.hidden_remote_factory(
        "https://hidden.example", tmp_path / "submitter.key", scoring_for(BATTERY), None
    )
    pool = factory("run-3")
    assert (pool.run_id, pool.challenge_id) == ("run-3", BATTERY)


# -- the service-account guard (S0a) --------------------------------------------------------


def test_the_service_account_guard(tmp_path):
    with pytest.raises(ds.DevSubmitRefused) as refused:
        ds.require_service_account({})
    assert refused.value.code == "dev_submit_needs_a_service_account"
    with pytest.raises(ds.DevSubmitRefused) as refused:
        ds.require_service_account({"service_account": "carbon-producer"}, account=ME)
    assert refused.value.code == "dev_submit_wrong_account"
    ds.require_service_account({"service_account": ME}, account=ME)


@pytest.mark.parametrize(
    ("account", "accepted"), [(ME, True), ("carbon-producer", False)]
)
def test_a_deployment_loads_only_under_its_service_account(tmp_path, account, accepted):
    path = tmp_path / "deployment.json"
    path.write_text(
        json.dumps(
            {
                "schema": "carbon.battery.validator-deployment.v1",
                "state": "s",
                "private_root": "r",
                "journal": "j",
                "work": "w",
                "backend": "direct",
                "service_account": account,
            }
        )
    )
    path.chmod(0o600)
    if accepted:
        assert battery_deployment.load_config(path)["service_account"] == ME
        return
    with pytest.raises(battery_deployment.EvaluationUnavailable) as refused:
        battery_deployment.load_config(path)
    assert refused.value.code == "evaluation_wrong_account"
