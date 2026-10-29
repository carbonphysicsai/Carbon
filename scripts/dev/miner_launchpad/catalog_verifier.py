"""A display-only, progressive reading of which catalog entries are installed.

A full catalog's readiness (`catalog_state.readiness`) takes tens of seconds, so the capabilities answer cannot wait
for it. One background run, started by a read that finds nothing current, does the same fresh verification as always;
the answer reports what it knows so far (`verifying` with `installed: None`, never counted as ready) and then its
completed result.

It is display only, and "ready" here is never permission. No practice, submission, rebuild or install decision reads
this module (`tests/cpu/test_catalog_verifier.py` checks the import graph): each of those re-verifies the entry's
child, parent, source, material and image itself, at the moment of use. Unknown or failed never reads as ready.

Rules (Validator ruling, 2026-10-29):
- every invalidating event (an install starting or running, a config change, a restart) bumps a generation; a run
  publishes only if the generation it started under is still current, otherwise its result is discarded, never shown;
- a result merely older than `STALE_SECONDS` is kept and shown with `stale: True` and its time while one run, on
  demand from a read, replaces it (no timer: a quiet machine's Docker sees no background load);
- one run at a time; a read during a run starts no second one;
- a change made outside the app (`docker rmi`, an owner CLI install) cannot be seen; it is covered only by the
  stale rule, so a `ready` snapshot may be up to `STALE_SECONDS` old, which is fine because it is display only;
- a failed run carries a stable code and a redacted type/code detail, never raw daemon text, paths or addresses.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time

from scripts.dev.miner_launchpad import catalog_generation

STALE_SECONDS = 60.0
FAILED_CODE = "catalog.readiness.failed"


def _fingerprint(cfg) -> str:
    return hashlib.sha256(
        json.dumps(cfg, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


def _detail(failure) -> str:
    """The failure's type and stable code only: no message, which can hold a path or an address."""
    code = getattr(failure, "code", None)
    value = getattr(code, "value", code)
    return type(failure).__name__ + (f" [{value}]" if value is not None else "")


def _compute(cfg, progress):
    from scripts.dev.miner_launchpad.catalog_state import readiness

    return readiness(cfg, progress=progress) or {}


def _spawn(function):
    threading.Thread(target=function, name="catalog-readiness", daemon=True).start()


class CatalogVerifier:
    def __init__(self, compute=_compute, clock=time.time, spawn=_spawn):
        self._compute, self._clock, self._spawn = compute, clock, spawn
        self._lock = threading.Lock()
        self._generation = 0
        self._seen_external = catalog_generation.current()
        self._fingerprint = None
        self._result = None  # {found, status, code, detail, at}
        self._running = False
        self._checked = self._total = 0

    def invalidate(self) -> None:
        with self._lock:
            self._invalidate()

    def _invalidate(self) -> None:
        self._generation += 1
        self._result = None
        self._checked = self._total = 0

    def read(self, cfg) -> dict:
        """The snapshot to show now; starts a background run when nothing current is held. Never blocks."""
        with self._lock:
            external = catalog_generation.current()
            fingerprint = _fingerprint(cfg)
            if external != self._seen_external or fingerprint != self._fingerprint:
                self._seen_external, self._fingerprint = external, fingerprint
                self._invalidate()
            held = self._result
            stale = held is not None and self._clock() - held["at"] > STALE_SECONDS
            if (held is None or stale) and not self._running:
                self._running = True
                generation = self._generation
                start = True
            else:
                start = False
            view = self._view(held, stale)
        if start:
            self._spawn(lambda: self._run(cfg, generation))
        return view

    def _view(self, held, stale) -> dict:
        if held is None:
            return {
                "status": "verifying",
                "found": None,
                "checked": self._checked,
                "total": self._total,
            }
        view = {
            "status": held["status"],
            "found": held["found"],
            "checked": held["checked"],
            "total": held["total"],
        }
        if held["status"] == "failed":
            view["code"], view["detail"] = held["code"], held["detail"]
        if stale:
            view["stale"], view["checked_at"] = True, held["at"]
        return view

    def _run(self, cfg, generation) -> None:
        def progress(checked, total):
            with self._lock:
                if generation == self._generation:
                    self._checked, self._total = checked, total

        try:
            found, status, code, detail = (
                self._compute(cfg, progress),
                "ready",
                None,
                None,
            )
            found = dict(found)
        except (
            Exception
        ) as failure:  # noqa: BLE001 - any failure reads failed, never ready
            found, status, code, detail = None, "failed", FAILED_CODE, _detail(failure)
        with self._lock:
            self._running = False
            if generation != self._generation:
                return  # began before an invalidating event: discarded, never shown
            total = len(found) if found is not None else self._total
            self._result = {
                "found": found,
                "status": status,
                "code": code,
                "detail": detail,
                "at": self._clock(),
                "checked": total if status == "ready" else self._checked,
                "total": total if status == "ready" else self._total,
            }


#: The Control Center's one verifier (a restart makes a new one, which starts at `verifying`).
VERIFIER = CatalogVerifier()
