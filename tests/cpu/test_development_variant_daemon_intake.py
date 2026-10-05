"""The battery daemon and its intake refuse a development-only variant by name.

OWNER-GRAPHITE-TEST-WAVE-03 §1, GRAPHITE-DEV-VARIANTS-01: a submission whose
contract digest names a registered development-only variant is refused
`development_variant_not_served`:
- at the intake, before it is queued (a signed `battery_submit`, real
  `btauth/1` signature, the real gateway);
- at the daemon's admission, before anything compiles;
- and the daemon never binds a variant as the contract it serves.

Each check is switched off once and its test shown to fail: behind it the
contract compiler would still refuse, under the generic `contract_refused`.
Synthetic fixture variants only; nothing here is security acceptance.
"""

from __future__ import annotations

import pytest
import test_battery_intake as tbi
import test_battery_validator_daemon as tbd
from test_battery_validator_daemon import backend, refs  # noqa: F401 - fixtures
from test_development_variants import FIXTURE_DIGESTS, install

from carbon.battery import daemon as daemon_module
from carbon.battery import intake as intake_module
from carbon.battery import intake_client as ic
from carbon.battery.pool_store import StateError

NOT_SERVED = "development_variant_not_served"
VARIANT = FIXTURE_DIGESTS[1]


@pytest.fixture(autouse=True)
def _registry(tmp_path, monkeypatch):
    install(tmp_path / "registry", monkeypatch)


def check_daemon_admission(validator, hotkey):
    before = validator.store.pool()["admitted"]
    outcome = validator.admit(tbd.submission(hotkey, digest=VARIANT))
    assert outcome["failure"]["code"] == NOT_SERVED, outcome
    assert validator.store.pool()["admitted"] == before


def test_daemon_refuses_a_variant(tmp_path, refs, backend):  # noqa: F811
    validator = tbd.make(tmp_path, refs, backend)
    check_daemon_admission(validator, "hk-variant")
    # The same recipe under the served contract is admitted as before.
    admitted = validator.admit(tbd.submission("hk-level0"))
    assert admitted["state"] != "INVALID_CONSTRUCTION"
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(daemon_module, "is_development_variant", lambda *a, **k: False)
        with pytest.raises(AssertionError):
            # The check is what names it; the compiler alone says only
            # contract_refused.
            check_daemon_admission(validator, "hk-mutated")


def test_daemon_binds_no_variant(tmp_path, refs, backend, monkeypatch):  # noqa: F811
    validator = tbd.make(tmp_path, refs, backend)
    live = validator.identities()["contract_digest"]
    monkeypatch.setattr(
        daemon_module,
        "is_development_variant",
        lambda value, directory=None: value == live,
    )
    with pytest.raises(StateError) as refused:
        validator.identities()
    assert refused.value.code == NOT_SERVED


def check_intake(intake):
    body = ic.submission_message(tbi.facts(intake), tbi.STRATEGY, VARIANT, request="v1")
    answer = tbi.post(intake, tbi.MINER, body)
    assert answer.status == 400, answer
    assert answer.body == {"refused": NOT_SERVED}
    assert intake.inbox.received() == []


def test_intake_refuses_a_variant(tmp_path, refs, backend):  # noqa: F811
    intake, _target = tbi.build(tmp_path, refs, backend)
    check_intake(intake)
    assert NOT_SERVED in ic.REFUSALS
    assert ic.describe(400, {"refused": NOT_SERVED})
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(intake_module, "is_development_variant", lambda *a, **k: False)
        with pytest.raises(AssertionError):
            check_intake(intake)  # queued for the daemon instead
