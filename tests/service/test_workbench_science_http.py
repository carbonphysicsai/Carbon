"""Private HTTP composition with real domain admission and synthetic numerics."""

import asyncio
import json

import httpx2 as httpx
import pytest
from test_workbench_science import configured

from carbon.scientific_tasks.workbench_http import create_workbench_app

ORIGIN = "https://workbench.internal.example"
PREFIX = "/api/scientific-studies/"


def test_http_real_shared_task_results_and_same_origin_auth(tmp_path, monkeypatch):
    service, request, _records, _ledger, executions, _calls, composition = configured(
        tmp_path, monkeypatch
    )
    app = create_workbench_app(
        service, authorize=lambda req: service.adapter.principal, allowed_origin=ORIGIN
    )

    async def run():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url=ORIGIN
        ) as client:
            caps = await client.get(PREFIX + "capabilities")
            assert caps.status_code == 200 and caps.json()["available"] is True
            assert caps.headers["cache-control"] == "no-store"
            first = await client.post(
                PREFIX + "start", json=request, headers={"Origin": ORIGIN}
            )
            assert first.status_code == 200, first.text
            assert first.json()["status"] == "COMPLETE"
            second = await client.post(
                PREFIX + "result", json=request, headers={"Origin": ORIGIN}
            )
            assert second.status_code == 200
            assert second.json()["task_id"] == first.json()["task_id"]
            assert second.json()["result"]["values"] == first.json()["result"]["values"]

    try:
        asyncio.run(run())
        assert len(executions) == 1
    finally:
        composition.tasks.close()


@pytest.mark.parametrize(
    "failure", ["auth", "principal", "origin", "host", "cross-site", "missing-origin"]
)
def test_http_rejects_unbound_identity_and_cross_origin_before_dispatch(
    tmp_path, monkeypatch, failure
):
    service, request, _records, _ledger, executions, calls, composition = configured(
        tmp_path, monkeypatch
    )

    def authorize(req):
        if failure == "auth":
            raise RuntimeError("private-session-cookie")
        return "other-user" if failure == "principal" else service.adapter.principal

    app = create_workbench_app(service, authorize=authorize, allowed_origin=ORIGIN)

    async def run():
        headers = {"Origin": ORIGIN}
        if failure == "origin":
            headers["Origin"] = "https://attacker.invalid"
        elif failure == "host":
            headers["Host"] = "attacker.invalid"
        elif failure == "cross-site":
            headers["Sec-Fetch-Site"] = "cross-site"
        elif failure == "missing-origin":
            headers.clear()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url=ORIGIN
        ) as client:
            result = await client.post(PREFIX + "start", json=request, headers=headers)
            assert result.status_code in {401, 403}
            assert "private-session-cookie" not in result.text

    try:
        asyncio.run(run())
        assert calls == executions == []
    finally:
        composition.tasks.close()


def test_http_closed_routes_duplicate_json_and_byte_limits(tmp_path, monkeypatch):
    service, request, _records, _ledger, executions, calls, composition = configured(
        tmp_path, monkeypatch
    )
    app = create_workbench_app(
        service, authorize=lambda req: service.adapter.principal, allowed_origin=ORIGIN
    )

    async def run():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url=ORIGIN
        ) as client:
            assert (await client.get(PREFIX + "start")).status_code == 405
            assert (await client.head(PREFIX + "capabilities")).status_code == 405
            assert (
                await client.get(PREFIX + "capabilities?authority=public")
            ).status_code == 405
            assert (await client.get(PREFIX + "unknown")).status_code == 404
            assert (
                await client.post(PREFIX + "start/", json=request)
            ).status_code == 404
            headers = {"Origin": ORIGIN, "Content-Type": "application/json"}
            duplicate = '{"schema":"wrong",' + json.dumps(request)[1:]
            result = await client.post(
                PREFIX + "start", content=duplicate, headers=headers
            )
            assert result.status_code == 400
            result = await client.post(
                PREFIX + "start", content=b"x" * 131073, headers=headers
            )
            assert result.status_code == 413
            result = await client.post(
                PREFIX + "start",
                content=json.dumps(request),
                headers={"Origin": ORIGIN},
            )
            assert result.status_code == 415

    try:
        asyncio.run(run())
        assert calls == executions == []
    finally:
        composition.tasks.close()


def test_http_requires_explicit_authentication_and_origin(tmp_path, monkeypatch):
    service, _request, _records, _ledger, _executions, _calls, composition = configured(
        tmp_path, monkeypatch
    )
    try:
        with pytest.raises(ValueError):
            create_workbench_app(service, authorize=None, allowed_origin=ORIGIN)
        for origin in (
            "http://public.example",
            ORIGIN + "/",
            ORIGIN + "?key=value",
            "https://user@private.example",
        ):
            with pytest.raises(ValueError):
                create_workbench_app(
                    service,
                    authorize=lambda req: service.adapter.principal,
                    allowed_origin=origin,
                )
    finally:
        composition.tasks.close()
