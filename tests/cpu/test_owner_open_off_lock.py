"""mcp_slow (live 116, 21 Nov 2026 02:1xZ and 03:1xZ: /carbon/v1/mcp requests at 30 s, status 0): a brand-new owner's
provider is built under ITS OWN gate, never the receiver's lock, so no other owner's request waits on it; and after
listening ONE background thread opens the recently active lazy owners, so an active miner's first call after a restart
does not pay its owner's whole restore.

Claims:
1. `_open_new` builds outside the receiver lock (another thread takes it meanwhile) and registers once;
2. it does nothing for an owner already open, lazy, set aside, unadmitted, or while stopping;
3. `lazy_warm_order` lists only lazy owners with a task created within a day, newest first, capped;
4. the warmer opens them one at a time through `_restore_lazy` and stops at a stop.
SYNTHETIC owners; no store, chain or container.
"""

from __future__ import annotations

import hashlib
import threading

from carbon.challenge_validator import direct_receiver as receiver

A = "5" + "A" * 47
B = "5" + "B" * 47
C = "5" + "C" * 47


def _name(hotkey):
    return hashlib.sha256(hotkey.encode()).hexdigest()


def _providers(admitted=(A, B, C)):
    owners = receiver.OwnerProviders.__new__(receiver.OwnerProviders)
    owners._lock = threading.RLock()
    owners._providers = {}
    owners._set_aside = {}
    owners._lazy = {}
    owners._lazy_index = {}
    owners._lazy_gates = {}
    owners._open_gates = {}
    owners._closing = False
    owners._warmer = None
    owners._settle_unobserved = lambda: None
    owners._admission = lambda hotkey: {"uid": 1} if hotkey in admitted else None
    registered = []

    def register(hotkey, provider, control, frozen, live, *, restoring):
        registered.append((hotkey, restoring))
        owners._providers[hotkey] = provider

    owners._register = register
    return owners, registered


class _Provider:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


def test_a_new_owner_is_built_off_the_receiver_lock_and_registered_once():
    owners, registered = _providers()
    other_took_lock = []

    def build(hotkey, *, restoring, host):
        # another owner's request takes the receiver lock while this build runs
        def other():
            got = owners._lock.acquire(timeout=2)
            other_took_lock.append(got)
            if got:
                owners._lock.release()

        thread = threading.Thread(target=other)
        thread.start()
        thread.join()
        assert (restoring, host) == (False, False)
        return _Provider(), "control", {"uid": 1}, True

    owners._build = build
    owners._open_new(A)
    assert other_took_lock == [True]
    assert registered == [(A, False)]
    owners._open_new(A)  # already open: nothing built again
    assert registered == [(A, False)]


def test_nothing_is_built_for_an_owner_open_lazy_set_aside_unadmitted_or_while_stopping():
    owners, registered = _providers(admitted=(A, B))
    built = []
    owners._build = lambda hotkey, **kw: built.append(hotkey) or (_Provider(), 0, 0, 1)
    owners._lazy[_name(A)] = A  # lazy: `_restore_lazy` opens it
    owners._set_aside[_name(B)] = "x"  # set aside: `_open` refuses it
    owners._open_new(A)
    owners._open_new(B)
    owners._open_new(C)  # not admitted: `_open` refuses it under the lock, as before
    assert built == [] and registered == []
    owners._closing = True
    owners._lazy.clear()
    owners._open_new(A)
    assert built == []


def test_a_stop_during_the_build_closes_the_new_provider_and_registers_nothing():
    owners, registered = _providers()
    provider = _Provider()

    def build(hotkey, **kw):
        owners._closing = True
        return provider, 0, 0, 1

    owners._build = build
    try:
        owners._open_new(A)
    except Exception as refused:  # noqa: BLE001
        assert getattr(refused, "code", None) == "direct_receiver_stopping"
    else:
        raise AssertionError("a stop during the build must refuse")
    assert provider.closed and registered == []


def test_the_warm_order_is_recent_lazy_owners_newest_first_capped(monkeypatch):
    owners, _registered = _providers()
    now = 1_800_000_000.0
    day = 24 * 3600
    for hotkey, newest in ((A, now - 60), (B, now - 2 * day), (C, now - 3600)):
        owners._lazy[_name(hotkey)] = hotkey
        owners._lazy_index[_name(hotkey)] = {
            "rtsk_" + _name(hotkey)[:64]: ("REFUSED", newest),
            "rtsk_" + "0" * 64: ("FAILED_INFRA", newest - day * 5),
        }
    assert owners.lazy_warm_order(now=now) == [A, C]
    monkeypatch.setattr(receiver.OwnerProviders, "WARM_MAX", 1)
    assert owners.lazy_warm_order(now=now) == [A]


def test_the_warmer_opens_one_at_a_time_and_stops_at_a_stop(monkeypatch):
    owners, _registered = _providers()
    monkeypatch.setattr(owners, "lazy_warm_order", lambda: [A, B, C])
    opened = []

    def restore(hotkey):
        opened.append(hotkey)
        if hotkey == B:
            owners._closing = True  # a stop arrives while warming

    owners._restore_lazy = restore
    thread = owners.start_lazy_warmer(pause=0, sleep=lambda seconds: None)
    thread.join(timeout=5)
    assert opened == [A, B]  # C never: the stop was seen before it
    owners._closing = False
    monkeypatch.setattr(owners, "lazy_warm_order", list)
    assert owners.start_lazy_warmer() is None  # nothing recent: no thread
