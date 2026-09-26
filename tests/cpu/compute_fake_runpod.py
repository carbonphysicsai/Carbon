"""MOCK RunPod transport for carbon.compute tests. No network, no spend.

It models only the request shapes the adapter uses and records every call so
tests can assert ordering and what was (not) sent.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

MOCK_KEY = "rpa_MOCK_ONLY_7f3c9e1a2b4d6f80"  # a fake credential, planted to be found


class Clock:
    def __init__(self, now: float = 1_800_000_000.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def key_file(tmp_path: Path, value: str = MOCK_KEY) -> Path:
    path = tmp_path / "runpod_api_key"
    path.write_text(value + "\n")
    path.chmod(0o600)
    return path


class FakeRunPod:
    """In-memory RunPod account (MOCK)."""

    def __init__(self, *, balance: float = 100.0, rate: float = 0.40) -> None:
        self.pods: dict[str, dict] = {}
        self.calls: list[tuple[str, str]] = []
        self.headers_seen: list[dict[str, str]] = []
        self.balance = balance
        self.rate = rate
        self.lose_next_create_response = False
        self.echo_key_in_next_failure = False
        self.ignore_deletes = False
        self.fail_next_create_with: int | None = None
        self.billing: dict[str, float] = {}
        self.on_request = None  # optional hook(method, url) for ordering checks
        self._next = 0

    def add_pod(self, pod_id: str, name: str | None, **fields) -> None:
        self.pods[pod_id] = {
            "id": pod_id,
            "name": name,
            "desiredStatus": "RUNNING",
            "costPerHr": self.rate,
            **fields,
        }

    def _reply(self, status: int, payload) -> tuple[int, bytes]:
        return status, json.dumps(payload).encode()

    def __call__(self, method, url, *, body, headers, timeout):
        self.calls.append((method, url))
        self.headers_seen.append(dict(headers))
        if self.on_request is not None:
            self.on_request(method, url)
        if "proxy.runpod.net" in url:
            raise AssertionError("MOCK: pod proxy must never be contacted here")
        if self.echo_key_in_next_failure:
            self.echo_key_in_next_failure = False
            # Simulates a client library whose error text echoes the request.
            raise ConnectionError(f"reset while sending {headers['Authorization']}")
        data = json.loads(body) if body else None
        if url == "https://api.runpod.io/graphql":
            query = data["query"]
            if "clientBalance" in query:
                return self._reply(
                    200, {"data": {"myself": {"clientBalance": self.balance}}}
                )
            return self._reply(
                200,
                {
                    "data": {
                        "gpuTypes": [
                            {
                                "lowestPrice": {
                                    "uninterruptablePrice": self.rate,
                                    "stockStatus": "High",
                                }
                            }
                        ]
                    }
                },
            )
        if url == "https://rest.runpod.io/v1/pods" and method == "POST":
            if self.fail_next_create_with is not None:
                status, self.fail_next_create_with = self.fail_next_create_with, None
                return self._reply(status, {"error": "mock refusal"})
            self._next += 1
            pod_id = f"mockpod{self._next:04d}"
            self.add_pod(pod_id, data["name"], env=data["env"])
            if self.lose_next_create_response:
                self.lose_next_create_response = False
                raise TimeoutError("MOCK: response lost after the pod was created")
            return self._reply(200, dict(self.pods[pod_id]))
        if url == "https://rest.runpod.io/v1/pods" and method == "GET":
            return self._reply(200, list(self.pods.values()))
        match = re.fullmatch(r"https://rest\.runpod\.io/v1/pods/(\w+)(/stop)?", url)
        if match:
            pod_id, stop = match.groups()
            if pod_id not in self.pods:
                return self._reply(404, {"error": "not found"})
            if method == "GET":
                return self._reply(200, self.pods[pod_id])
            if method == "POST" and stop:
                self.pods[pod_id]["desiredStatus"] = "EXITED"
                return self._reply(200, self.pods[pod_id])
            if method == "DELETE":
                if not self.ignore_deletes:
                    del self.pods[pod_id]
                return self._reply(200, {})
        match = re.fullmatch(
            r"https://rest\.runpod\.io/v1/billing/pods\?podId=(\w+)", url
        )
        if match:
            pod_id = match.group(1)
            if pod_id not in self.billing:
                return self._reply(200, [])
            return self._reply(200, [{"podId": pod_id, "amount": self.billing[pod_id]}])
        return self._reply(404, {"error": "mock: unmodelled"})

    def creates(self) -> int:
        return sum(
            1
            for call in self.calls
            if call == ("POST", "https://rest.runpod.io/v1/pods")
        )
