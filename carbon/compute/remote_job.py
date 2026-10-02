# Copyright (c) 2026 Carbon Physics AI, Inc.
# SPDX-License-Identifier: MIT
# Full license text: see LICENSE at the repository root.

"""The controller's side of one rented job (C-MLP-03 slice 4).

`RemoteJob` drives `carbon.compute.job_server` on a rented pod from the
miner's own machine: wait for it, stage the inputs once, run, poll, fetch the
output once. The job token is the only thing it presents; no provider key
leaves the adapter, and no key of the miner's ever reaches the pod.

Every response body is bounded and every archive is flat files only, so a
pod can return nothing but the job's own output files.
"""

from __future__ import annotations

import json
import secrets
import time
import urllib.error
import urllib.request
from collections.abc import Callable

from .job_server import MAX_OUTPUT_BYTES, MAX_STAGE_BYTES, PROGRAM, pack, unpack

#: Polls are short: provider HTTP proxies close long requests, so a run is
#: started asynchronously and its state read until it ends.
POLL_SECONDS = 5.0


class RemoteJobFailure(Exception):
    """The job did not complete; `stage` names where it stopped."""

    def __init__(self, stage, detail):
        super().__init__(f"{stage}: {detail}")
        self.stage, self.detail = stage, detail


def new_token():
    return secrets.token_hex(32)


def _urllib(method, url, *, body, headers, timeout):
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None

    request = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.build_opener(NoRedirect()).open(
            request, timeout=timeout
        ) as response:
            return response.status, response.read(MAX_OUTPUT_BYTES + 1)
    except urllib.error.HTTPError as refused:
        return refused.code, refused.read(65536)


class RemoteJob:
    """One job on one rented pod, addressed by its base URL and token."""

    def __init__(
        self,
        base_url: str,
        token: str,
        *,
        transport: Callable = _urllib,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        cancelled: Callable[[], bool] = lambda: False,
        plain_http: bool = False,
    ):
        # HTTPS unless the provider documents no other route (Lium: the node's
        # IP, plain HTTP), which the caller states and the record carries.
        allowed = ("https://", "http://127.0.0.1:") + (
            ("http://",) if plain_http else ()
        )
        if not base_url.startswith(allowed):
            raise ValueError("a rented job is reached over https")
        self.base, self.token = base_url.rstrip("/"), token
        self.transport, self.clock, self.sleep = transport, clock, sleep
        # The campaign's stop: checked between polls, so a stopped campaign
        # ends the job and its caller tears the pod down.
        self.cancelled = cancelled

    def _call(self, method, path, body=None, *, authorized=True, timeout=60):
        headers = {"User-Agent": "carbon-compute/1"}
        if authorized:
            headers["Authorization"] = "Bearer " + self.token
        if body is not None:
            headers["Content-Type"] = "application/gzip"
        try:
            return self.transport(
                method, self.base + path, body=body, headers=headers, timeout=timeout
            )
        except Exception as failure:  # noqa: BLE001 - only the type survives
            return None, type(failure).__name__.encode()

    def state(self):
        status, body = self._call("GET", "/status", authorized=False, timeout=20)
        if status != 200:
            return None
        try:
            return json.loads(body)["state"]
        except (ValueError, KeyError, TypeError):
            return None

    def wait_for(self, states, deadline):
        while self.clock() < deadline:
            if self.cancelled():
                raise RemoteJobFailure("cancelled", "the campaign was stopped")
            seen = self.state()
            if seen in states:
                return seen
            self.sleep(POLL_SECONDS)
        raise RemoteJobFailure(
            "wait", "deadline passed waiting for " + "/".join(states)
        )

    def stage(self, files):
        if PROGRAM not in files:
            raise ValueError("the program is staged with its inputs")
        body = pack(files)
        if len(body) > MAX_STAGE_BYTES:
            raise ValueError("staged inputs exceed their bound")
        status, _ = self._call("PUT", "/stage", body, timeout=300)
        if status != 200:
            raise RemoteJobFailure("stage", f"http {status}")

    def start(self):
        status, _ = self._call("POST", "/run")
        if status != 202:
            raise RemoteJobFailure("run", f"http {status}")

    def output(self):
        status, body = self._call("GET", "/output", timeout=300)
        if status != 200:
            raise RemoteJobFailure("output", f"http {status}")
        files = unpack(body, MAX_OUTPUT_BYTES)
        result = json.loads(files.pop("carbon-job-result.json"))
        return result, files

    def run(self, files, *, ready_deadline, run_deadline):
        """Stage, run and fetch one job. Returns (result, output files)."""
        self.wait_for(("WAITING",), ready_deadline)
        self.stage(files)
        self.start()
        self.wait_for(("DONE", "FAILED"), run_deadline)
        return self.output()
