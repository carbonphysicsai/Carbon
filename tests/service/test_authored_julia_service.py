"""Actual authored Julia carrier containment; local engineering fixture grants only."""

from __future__ import annotations

import asyncio
import concurrent.futures
import json
import os
import sys
import time
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPOSITORY), str(REPOSITORY / "tests/cpu")]

from test_authored_julia import prepared

from carbon.development_session.julia_analysis import (
    build_julia_analysis_image,
    load_julia_analysis_image,
    run_julia,
)
from carbon.development_session.research_carrier import reconcile_worker, request_cancel
from carbon.reconstruction.worker.docker_runtime import DockerCLI
from carbon.reconstruction.worker.model import WorkerFailure


def serve(root, image_path):
    from test_standard_mcp_cli import FixtureSigner, fixture_connection

    import carbon.chain.auth
    from carbon.development_session import research_tools
    from carbon.development_session.research_admission import Admission
    from carbon.development_session.research_ledger import CampaignLedger
    from carbon.development_session.research_material import PublicMaterial
    from carbon.development_session.research_service import make_research_service
    from carbon.development_session.research_tools import ResearchMinerTools
    from carbon.miner_mcp.research import AuthenticatedResearchService
    from carbon.miner_mcp.standard import ResearchToolAdapter
    from carbon.miner_mcp.standard_server import create_stdio_server
    from scripts.dev.miner_launchpad.controller import owner_lock

    carbon.chain.auth.BittensorMessageSigner = FixtureSigner
    research_tools.BittensorMessageSigner = FixtureSigner
    image = load_julia_analysis_image(image_path)
    ledger = CampaignLedger(
        root / "campaign",
        clock=lambda: 1000,
        admission=Admission.load(root / "grant.json"),
        generation=1,
    )
    with ledger.db() as db:
        owner = json.loads(
            db.execute("SELECT manifest FROM campaign WHERE id=1").fetchone()[0]
        )["owner"]
    with owner_lock(ledger.root):
        composition = make_research_service(
            root=root / "tasks",
            ledger=ledger,
            owner=owner,
            image=image.parent,
            julia_image=image,
            public_material=PublicMaterial(None),
            practice=None,
        )
        connection = fixture_connection(ledger.root)
        sdk = ResearchMinerTools(
            connection=connection,
            wrapper=AuthenticatedResearchService(
                connection.service.gateway, {owner: composition.service}
            ),
            composition=composition,
            ledger=ledger,
            owner=owner,
        )
        try:
            create_stdio_server(ResearchToolAdapter(sdk, principal=owner)).run()
        finally:
            composition.tasks.close()


@pytest.fixture(scope="module")
def image(tmp_path_factory):
    manifest = Path(os.environ["CARBON_JULIA_WORKER_MANIFEST"])
    root = Path(
        os.environ.get(
            "CARBON_AUTHORED_JULIA_IMAGE_ROOT",
            str(tmp_path_factory.mktemp("julia-image")),
        )
    )
    return build_julia_analysis_image(manifest, root)


def assert_removed(ledger):
    for path in ledger.root.glob("operation-*/intent.json"):
        intent = json.loads(path.read_bytes())
        assert (
            not DockerCLI()
            .run(
                ["ps", "-aq", "--filter", "name=^" + intent["container"] + "$"],
                timeout=10,
            )
            .stdout.strip()
        )


def test_native_numerical_script_has_private_state_public_input_and_replay(
    image, tmp_path
):
    ledger, _ = prepared(tmp_path, image=image)
    source = r"""
using LinearAlgebra
using Sockets
@assert VERSION == v"1.13.0"
@assert read("public.txt", String) == "public-only"
@assert !ispath("/var/run/docker.sock")
@assert !ispath("/input/campaign.sqlite3")
@assert !ispath("/opt/carbon-worker/lib/python3.11/site-packages/carbon/development_session")
@assert !any(haskey(ENV,k) for k in ["OPENAI_API_KEY","AWS_SECRET_ACCESS_KEY","GOOGLE_APPLICATION_CREDENTIALS"])
# A writable per-run depot first, then the read-only pinned image depot.
@assert DEPOT_PATH == ["/scratch/julia-depot", "/opt/carbon-julia-analysis/depot"]
# The default environment's pinned project, and nothing a program could add.
@assert LOAD_PATH == ["/opt/carbon-julia-analysis/current", "@stdlib"]
for path in ["/forbidden-root", "/opt/carbon-julia-analysis/Project.toml", "/input/public.txt"]
    failed=false
    try write(path,"forbidden") catch; failed=true end
    @assert failed
end
for address in [ip"192.0.2.1",ip"169.254.169.254"]
    sock=TCPSocket()
    operation=@async try connect(sock,address,80); true catch; false end
    state=timedwait(()->istaskdone(operation),1.0)
    close(sock)
    @assert state == :ok && !fetch(operation)
end
function derivative(n)
    h=2pi/n;x=[h*i for i in 0:n-1];u=sin.(x)
    d=[(u[mod1(i+1,n)]-u[mod1(i-1,n)])/(2h) for i in 1:n]
    return d,norm(d.-cos.(x))/sqrt(n)
end
coarse,e1=derivative(32);fine,e2=derivative(64)
@assert e2 < e1
write("/scratch/output/derivative.f64le",fine)
open("/scratch/output/result.json","w") do io
    print(io,"{\"coarse_rms\":",e1,",\"fine_rms\":",e2,",\"points\":64}")
end
child=run(`/bin/sleep 120`;wait=false)
write("/scratch/output/notes.txt","self-reported synthetic sine derivative refinement")
"""
    kwargs = {
        "owner": "test-miner",
        "identity": "authored-numerical-1",
        "source": source,
        "files": {"public.txt": b"public-only"},
        "image": image,
        "seconds": 120,
    }
    try:
        result = run_julia(ledger, **kwargs)
    except WorkerFailure as exc:
        # Explicitly public synthetic script; diagnostic stays in this test.
        pytest.fail(exc.private_diagnostic.decode("utf-8", errors="replace"))
    assert result["provenance"] == "MINER_SELF_REPORTED"
    assert result["official_eligible"] is result["scientific_qualification"] is False
    snapshot = ledger.root / result["operation"] / "snapshot"
    values = json.loads((snapshot / "result.json").read_bytes())
    assert values["fine_rms"] < values["coarse_rms"]
    assert (snapshot / "derivative.f64le").stat().st_size == 64 * 8
    assert run_julia(ledger, **kwargs) == result
    with pytest.raises(ValueError):
        run_julia(ledger, **dict(kwargs, source="1+2"))
    with pytest.raises(ValueError):
        run_julia(ledger, **dict(kwargs, owner="other-principal"))
    used = ledger.status(owner="test-miner")["used"]
    assert used["research_trials"] == 1
    assert used["provider_attempts"] == used["provider_nanodollars"] == 0
    assert_removed(ledger)
    print(
        json.dumps(
            {"native_julia": str(image.image_id), "result": values, "used": used}
        )
    )


def test_runtime_package_installation_and_user_startup_are_unavailable(image, tmp_path):
    ledger, _ = prepared(tmp_path, image=image)
    source = r"""
using Pkg
@assert !isfile("/scratch/output/startup-ran.txt")
failed=try Pkg.add("CarbonUnregisteredRequestPackage"); false catch; true end
@assert failed
# The depot holds the pinned, precompiled packages and cannot be written.
depot_written=try mkdir("/opt/carbon-julia-analysis/depot/added"); true catch; false end
@assert !depot_written
write("/scratch/output/result.json","{\"installation_denied\":true}")
"""
    result = run_julia(
        ledger,
        owner="test-miner",
        identity="package-denied",
        source=source,
        files={"startup.jl": b'write("/scratch/output/startup-ran.txt","bad")'},
        image=image,
        seconds=120,
    )
    assert result["files"].keys() == {"result.json"}
    assert_removed(ledger)


@pytest.mark.parametrize(
    "source",
    [
        'write("/scratch/output/result.json","{\\"x\\":NaN}")',
        'write("/scratch/output/result.json","broken")',
        'write("/scratch/output/value.f64le",[Inf])',
        'symlink("/input/public.txt","/scratch/output/escape.txt")',
        'open("/scratch/output/huge.txt","w") do io; write(io,zeros(UInt8,9*1024^2)); end',
    ],
)
def test_invalid_exports_never_become_results(image, tmp_path, source):
    ledger, _ = prepared(tmp_path, image=image)
    with pytest.raises((ValueError, WorkerFailure)):
        run_julia(
            ledger,
            owner="test-miner",
            identity="invalid-output",
            source=source,
            files={"public.txt": b"public-only"},
            image=image,
            seconds=90,
        )
    assert ledger.status(owner="test-miner")["operations"][0]["state"] == "RESERVED"
    reconciled = reconcile_worker(ledger, owner="test-miner", identity="invalid-output")
    assert reconciled["retry_dispatched"] is False
    assert_removed(ledger)


def test_cancellation_reaps_julia_and_child_and_retains_uncertain_charge(
    image, tmp_path
):
    ledger, _ = prepared(tmp_path, image=image)
    source = 'run(`/bin/sleep 120`;wait=false);write("/scratch/workspace/ready","ready");sleep(120)'
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(
            run_julia,
            ledger,
            owner="test-miner",
            identity="cancel-julia",
            source=source,
            files={},
            image=image,
            seconds=120,
        )
        deadline = time.monotonic() + 35
        while time.monotonic() < deadline:
            intents = list(ledger.root.glob("operation-*/intent.json"))
            if intents:
                intent = json.loads(intents[0].read_bytes())
                try:
                    status = DockerCLI().run(
                        [
                            "exec",
                            intent["container"],
                            "/usr/bin/test",
                            "-f",
                            "/scratch/workspace/ready",
                        ],
                        timeout=2,
                        accepted=(0, 1),
                    )
                    if status.returncode == 0:
                        break
                except WorkerFailure:
                    pass
            if future.done():
                future.result()
            time.sleep(0.1)
        else:
            pytest.fail("native Julia did not become active")
        request_cancel(ledger, owner="test-miner", identity="cancel-julia")
        with pytest.raises((ValueError, WorkerFailure)):
            future.result(timeout=45)
    result = reconcile_worker(ledger, owner="test-miner", identity="cancel-julia")
    assert result["cleanup_observed"] is True
    used = ledger.status(owner="test-miner")["used"]
    assert used["numerical_milliseconds"] == 120000
    assert used["research_trials"] == 1
    assert_removed(ledger)


def test_authored_julia_through_real_external_stdio_reconnect_and_owned_ledger(
    image, tmp_path, monkeypatch
):
    from dataclasses import asdict

    from mcp import Client
    from mcp.client.stdio import StdioServerParameters
    from test_standard_mcp_cli import FixtureSigner, fixture_connection

    import carbon.chain.auth
    from carbon.development_session.julia_analysis import SCHEMA
    from carbon.development_session.profile import canonical
    from carbon.miner_mcp.standard_cli import _requester

    monkeypatch.setattr(carbon.chain.auth, "BittensorMessageSigner", FixtureSigner)
    (tmp_path / "campaign").mkdir()
    owner = asyncio.run(_requester(fixture_connection(tmp_path / "campaign")))
    ledger, _ = prepared(tmp_path, image=image, owner=owner)
    image_path = tmp_path / "image.json"
    image_path.write_bytes(canonical({"schema": SCHEMA, **asdict(image)}))
    parameters = StdioServerParameters(
        command=sys.executable,
        args=[str(Path(__file__).resolve()), "--serve", str(tmp_path), str(image_path)],
        cwd=REPOSITORY,
    )
    request = {
        "operation_id": "authored-julia-external-0001",
        "kind": "workspace",
        "strategy": None,
        "action": "run_julia",
        "arguments": {
            "source": 'write("/scratch/output/squares.f64le",Float64[i^2 for i in 1:8])',
            "files": [],
            "seconds": 90,
            "hypothesis": "exercise public Julia analysis",
            "expected_effect": "retain eight finite squares",
        },
        "hypothesis": "exercise public Julia analysis",
        "expected_effect": "retain eight finite squares",
    }
    results = []

    async def exercise():
        for _ in range(2):
            async with Client(parameters, read_timeout_seconds=180) as client:
                tools = await client.list_tools()
                assert "run_julia" in str(tools)
                response = await client.call_tool(
                    "carbon_research_v2__start_research_task", request
                )
                assert not response.is_error, response
                body = response.structured_content["payload"]
                assert body["terminal_task"]["state"] == "SUCCEEDED", body
                assert (
                    body["terminal_task"]["immutable_bindings"]["task_kind"]
                    == "DEVELOPMENT_WORKSPACE_V2"
                )
                results.append(body["public_result"]["result"])

    asyncio.run(exercise())
    assert results[0] == results[1]
    status = ledger.status(owner=owner)
    assert status["used"]["research_trials"] == 1
    assert (
        status["used"]["provider_nanodollars"]
        == status["used"]["provider_attempts"]
        == 0
    )
    assert all(op["state"] == "SUCCEEDED" for op in status["operations"])
    assert_removed(ledger)
    print(
        json.dumps(
            {
                "external_stdio_replay": True,
                "used": status["used"],
                "image": image.image_id,
            }
        )
    )


def test_deadline_stops_running_julia_and_child_without_refund(image, tmp_path):
    ledger, _ = prepared(tmp_path, image=image)
    source = 'run(`/bin/sleep 120`;wait=false);write("/scratch/workspace/ready","ready");sleep(120)'
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(
            run_julia,
            ledger,
            owner="test-miner",
            identity="deadline-julia",
            source=source,
            files={},
            image=image,
            seconds=60,
        )
        deadline = time.monotonic() + 12
        while time.monotonic() < deadline:
            intents = list(ledger.root.glob("operation-*/intent.json"))
            if intents:
                name = json.loads(intents[0].read_bytes())["container"]
                try:
                    if (
                        DockerCLI()
                        .run(
                            [
                                "exec",
                                name,
                                "/usr/bin/test",
                                "-f",
                                "/scratch/workspace/ready",
                            ],
                            timeout=2,
                            accepted=(0, 1),
                        )
                        .returncode
                        == 0
                    ):
                        break
                except WorkerFailure:
                    pass
            if future.done():
                future.result()
            time.sleep(0.1)
        else:
            pytest.fail("deadline test did not observe active Julia and child")
        # The miner lane times the allowance from program start, not container
        # creation, so the wait must outlast the whole 60 s allowance.
        with pytest.raises(WorkerFailure) as caught:
            future.result(timeout=90)
        # Either deadline stops it: the watchdog kills the container at the
        # allowance (SIGKILL, exit 137), or the stream's own timeout fires first.
        diagnostic = caught.value.private_diagnostic
        assert diagnostic == b"stream command timed out" or diagnostic.startswith(
            b"exit=137\n"
        ), diagnostic
    result = reconcile_worker(ledger, owner="test-miner", identity="deadline-julia")
    assert result["cleanup_observed"] is True
    assert ledger.status(owner="test-miner")["used"]["numerical_milliseconds"] == 60000
    assert_removed(ledger)


if __name__ == "__main__":
    assert sys.argv[1] == "--serve"
    serve(Path(sys.argv[2]), Path(sys.argv[3]))
