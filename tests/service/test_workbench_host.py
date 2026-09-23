"""Supported private host composition over the real Workbench science service.

Every case here runs through the actual composed routes, the actual registered
draft registry and the actual ``WorkbenchScience`` checks. Nothing stubs the
service under test, and no case claims deployment, delivery or qualification.
"""

import asyncio
import json
import os
import stat
from hashlib import sha256
from pathlib import Path

import httpx2 as httpx
import pytest
from test_workbench_science import configured

from carbon.development_session.julia_research import julia_burgers_scope
from carbon.development_session.profile import canonical
from carbon.scientific_tasks.workbench import TEMPLATE, wire_digest
from carbon.scientific_tasks.workbench_host import (
    _ADVECTION_SCOPE,
    _ENVELOPE_SCOPE,
    _JULIA_SCOPE,
    CONFIGURED_UNAVAILABLE,
    ENABLED,
    FIXTURE_ONLY,
    UNSUPPORTED,
    RegisteredDraftStore,
    StaffPrincipals,
    capability_report,
    create_host_app,
    verify_private_build,
)
from carbon.scientific_tasks.workbench_http import create_workbench_app  # noqa: F401

ORIGIN = "https://workbench.internal.example"
PREFIX = "/api/scientific-studies/"
HOST_PREFIX = "/api/workbench-host/"
TOKEN = "a" * 48
PRIVATE_BUILD = (
    '<!doctype html><html lang="en" data-scientific-service="private"></html>'
)


def private_directory(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    os.chmod(path, 0o700)
    return path


def write_private(path: Path, document) -> Path:
    private_directory(path.parent)
    path.write_bytes(canonical(document))
    os.chmod(path, 0o600)
    return path


def principals_file(tmp_path, principal, *, names=("Ryan Bequette",), token=TOKEN):
    return write_private(
        private_directory(tmp_path / "private") / "staff.json",
        {
            "schema": "carbon.workbench.host-principals.v1",
            "campaign_principal": principal,
            "staff": [
                {
                    "name": name,
                    "token_sha256": sha256(
                        (token if index == 0 else f"{token}{index}").encode()
                    ).hexdigest(),
                }
                for index, name in enumerate(names)
            ],
        },
    )


def static_build(tmp_path, *, body=PRIVATE_BUILD, extra=None):
    directory = tmp_path / "private-build"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "Carbon_Opportunity_Workbench.html").write_text(body)
    (directory / "Carbon_Client_Intake_Preview.html").write_text("<html></html>")
    (directory / "Carbon_Client_Pilot_Designer_Preview.html").write_text(
        "<html></html>"
    )
    if extra is not None:
        (directory / extra).write_text("secret")
    return directory.resolve()


def store_for(tmp_path, principal):
    return RegisteredDraftStore(
        private_directory(tmp_path / "private") / "drafts.json", principal=principal
    )


def install_from(store, request, physical):
    store.install(
        job_id=request["binding"]["job_id"],
        design_id=request["binding"]["design_id"],
        revision=request["binding"]["design_revision"],
        draft_scope=request["draft_scope"],
        physical=physical,
    )


def rebound(service, store, physical):
    from carbon.scientific_tasks.workbench import WorkbenchScience

    return WorkbenchScience(service.adapter, draft_resolver=store.resolver(physical))


class Profile:
    """The exact fields ``capability_report`` reads from a loaded operator profile."""

    def __init__(self, root, runtime, paths):
        self.root = root
        self.manifest = {"runtime": runtime}
        self.document = {"paths": paths}


def profile_for(tmp_path, runtime, *, image=True):
    tmp_path.mkdir(parents=True, exist_ok=True)
    manifest = tmp_path / "image-manifest.json"
    if image:
        manifest.write_text("{}")
    return Profile(tmp_path, runtime, {"image_manifest": str(manifest)})


# -- registered draft registry ----------------------------------------------


def test_registry_resolves_only_the_installed_revision_and_exact_definition(
    tmp_path, monkeypatch
):
    service, request, _records, _ledger, executions, _calls, composition = configured(
        tmp_path, monkeypatch
    )
    try:
        physical = asyncio.run(service.capabilities())["physical"]
        store = store_for(tmp_path, service.adapter.principal)
        resolve = store.resolver(physical)
        binding = request["binding"]
        assert (
            resolve(service.adapter.principal, binding["job_id"], "design-one", 1)
            is None
        )

        install_from(store, request, physical)
        record = resolve(service.adapter.principal, binding["job_id"], "design-one", 1)
        assert record is not None
        assert record.revision == record.current_revision == 1
        assert record.rights_scope == "SYNTHETIC_INTERNAL"
        assert wire_digest(record.physical) == wire_digest(physical)

        # A different campaign principal never resolves another operator's draft.
        assert resolve("other-principal", binding["job_id"], "design-one", 1) is None

        # A registry written against a different granted definition fails closed
        # rather than binding a study to a definition the service will not accept.
        drifted = dict(physical, viscosity=physical["viscosity"] * 2)
        assert (
            store.resolver(drifted)(
                service.adapter.principal, binding["job_id"], "design-one", 1
            )
            is None
        )
        assert executions == []
    finally:
        composition.tasks.close()


def test_registry_stales_earlier_revisions_and_survives_revocation(
    tmp_path, monkeypatch
):
    service, request, _records, _ledger, _executions, _calls, composition = configured(
        tmp_path, monkeypatch
    )
    try:
        physical = asyncio.run(service.capabilities())["physical"]
        store = store_for(tmp_path, service.adapter.principal)
        install_from(store, request, physical)
        store.install(
            job_id="job-one",
            design_id="design-one",
            revision=2,
            draft_scope=request["draft_scope"],
            physical=physical,
        )
        resolve = store.resolver(physical)
        first = resolve(service.adapter.principal, "job-one", "design-one", 1)
        assert first.revision == 1 and first.current_revision == 2
        assert store.summary() == {"designs": 1, "revisions": 2}

        # Revoking the current revision falls back to the highest remaining one.
        store.revoke(job_id="job-one", design_id="design-one", revision=2)
        again = resolve(service.adapter.principal, "job-one", "design-one", 1)
        assert again.current_revision == 1
        store.revoke(job_id="job-one", design_id="design-one")
        assert store.summary() == {"designs": 0, "revisions": 0}
        assert resolve(service.adapter.principal, "job-one", "design-one", 1) is None
        with pytest.raises(ValueError):
            store.revoke(job_id="job-one", design_id="design-one")
    finally:
        composition.tasks.close()


def test_registry_file_is_owner_only_durable_and_closed(tmp_path, monkeypatch):
    service, request, _records, _ledger, _executions, _calls, composition = configured(
        tmp_path, monkeypatch
    )
    try:
        physical = asyncio.run(service.capabilities())["physical"]
        store = store_for(tmp_path, service.adapter.principal)
        install_from(store, request, physical)
        mode = stat.S_IMODE(store.path.stat().st_mode)
        assert mode == 0o600, oct(mode)
        assert store.path.read_bytes() == canonical(store.document())

        # A hand-edited or foreign registry is refused, not silently repaired.
        store.path.chmod(0o600)
        store.path.write_bytes(canonical({"schema": "other", "principal": "x"}))
        with pytest.raises(ValueError):
            store.document()
        assert (
            store.resolver(physical)(
                service.adapter.principal, "job-one", "design-one", 1
            )
            is None
        )
        store.path.write_bytes(
            canonical(
                {
                    "schema": "carbon.workbench.draft-registry.v1",
                    "principal": service.adapter.principal,
                    "designs": [
                        {
                            "job_id": "job-one",
                            "design_id": "design-one",
                            "current_revision": 5,
                            "revisions": [
                                {
                                    "revision": 1,
                                    "draft_scope": request["draft_scope"],
                                    "rights_scope": "SYNTHETIC_INTERNAL",
                                    "physical_sha256": wire_digest(physical),
                                }
                            ],
                        }
                    ],
                }
            )
        )
        with pytest.raises(ValueError):
            store.document()  # current_revision is not installed
    finally:
        composition.tasks.close()


def test_registered_draft_reaches_the_real_service_and_a_stale_one_does_not(
    tmp_path, monkeypatch
):
    service, request, _records, _ledger, executions, _calls, composition = configured(
        tmp_path, monkeypatch
    )
    try:
        physical = asyncio.run(service.capabilities())["physical"]
        store = store_for(tmp_path, service.adapter.principal)
        install_from(store, request, physical)
        bound = rebound(service, store, physical)
        started = asyncio.run(bound.call("start", request))
        assert started["status"] == "COMPLETE"
        assert started["qualification"] == "NOT_QUALIFIED"
        assert started["official_eligible"] is False
        assert len(executions) == 1

        # A physical edit registers a new revision; the old association is stale.
        store.install(
            job_id="job-one",
            design_id="design-one",
            revision=2,
            draft_scope=request["draft_scope"],
            physical=physical,
        )
        stale = rebound(service, store, physical)
        with pytest.raises(PermissionError):
            asyncio.run(stale.call("status", request))
        # Cancellation of the earlier revision remains reachable for cleanup.
        cancelled = asyncio.run(stale.call("cancel", request))
        assert cancelled["binding"] == request["binding"]
        assert len(executions) == 1
    finally:
        composition.tasks.close()


# -- named staff principals --------------------------------------------------


def test_staff_tokens_authenticate_only_configured_named_credentials(tmp_path):
    path = principals_file(tmp_path, "miner-hotkey", names=("Ryan", "Nick", "Harsh"))
    principals = StaffPrincipals.load(path)
    assert principals.campaign_principal == "miner-hotkey"
    assert principals.names == ("Ryan", "Nick", "Harsh")

    class Request:
        def __init__(self, value):
            from starlette.datastructures import Headers

            self.headers = Headers(
                raw=[(b"authorization", value.encode())] if value else []
            )

    assert principals.resolve(Request("Bearer " + TOKEN)) == "miner-hotkey"
    assert principals.resolve(Request(f"Bearer {TOKEN}1")) == "miner-hotkey"
    for rejected in ("", "Bearer " + "b" * 48, "Basic " + TOKEN, "Bearer short"):
        with pytest.raises(ValueError):
            principals.resolve(Request(rejected))


def test_staff_principal_file_must_be_private_closed_and_distinct(tmp_path):
    good = principals_file(tmp_path, "miner-hotkey")
    StaffPrincipals.load(good)
    good.chmod(0o644)
    with pytest.raises(ValueError):
        StaffPrincipals.load(good)
    good.chmod(0o600)
    for document in (
        {"schema": "other", "campaign_principal": "a", "staff": []},
        {
            "schema": "carbon.workbench.host-principals.v1",
            "campaign_principal": "a",
            "staff": [],
        },
        {
            "schema": "carbon.workbench.host-principals.v1",
            "campaign_principal": "a",
            "staff": [{"name": "R", "token_sha256": "zz"}],
        },
        {
            "schema": "carbon.workbench.host-principals.v1",
            "campaign_principal": "a",
            "staff": [
                {"name": "R", "token_sha256": "0" * 64},
                {"name": "N", "token_sha256": "0" * 64},
            ],
        },
    ):
        write_private(good, document)
        with pytest.raises(ValueError):
            StaffPrincipals.load(good)


# -- private build ------------------------------------------------------------


def test_only_the_reviewed_private_build_directory_is_served(tmp_path):
    good = static_build(tmp_path)
    assert verify_private_build(good).name == "Carbon_Opportunity_Workbench.html"

    offline = static_build(
        tmp_path / "offline",
        body='<html lang="en" data-scientific-service="offline"></html>',
    )
    with pytest.raises(ValueError, match="offline build"):
        verify_private_build(offline)

    polluted = static_build(tmp_path / "polluted", extra="operator-token.json")
    with pytest.raises(ValueError, match="build artifacts"):
        verify_private_build(polluted)

    linked = static_build(tmp_path / "linked")
    (linked / "Carbon_Client_Intake_Preview.html").unlink()
    (linked / "Carbon_Client_Intake_Preview.html").symlink_to(tmp_path / "secret")
    with pytest.raises(ValueError, match="regular files"):
        verify_private_build(linked)

    with pytest.raises(ValueError):
        verify_private_build(tmp_path / "absent")


# -- capability report --------------------------------------------------------


def test_registered_scope_schemas_match_their_builders(tmp_path, monkeypatch):
    service, _request, _records, _ledger, _executions, _calls, composition = configured(
        tmp_path, monkeypatch
    )
    try:
        data = service.material.study.data
        assert julia_burgers_scope(data.image, data.role_root)["schema"] == _JULIA_SCOPE
        # The envelope constant is imported from its owner, so it cannot drift.
        # The advection literal is asserted against its builder's own source: a
        # renamed scope must fail here rather than quietly report UNSUPPORTED.
        import inspect

        from carbon.development_session.advection_research import advection_scope

        assert f'"schema": "{_ADVECTION_SCOPE}"' in inspect.getsource(advection_scope)
        assert _ENVELOPE_SCOPE.startswith("carbon.public-julia-envelope.scope.")
    finally:
        composition.tasks.close()


@pytest.mark.parametrize(
    "runtime,feasibility,envelope",
    [
        ({}, UNSUPPORTED, UNSUPPORTED),
        ({"scientific_tasks": [{"schema": _JULIA_SCOPE}]}, ENABLED, UNSUPPORTED),
        (
            {
                "scientific_tasks": [
                    {"schema": _JULIA_SCOPE},
                    {"schema": _ENVELOPE_SCOPE},
                ]
            },
            ENABLED,
            ENABLED,
        ),
        (
            {"scientific_tasks": [{"schema": _ADVECTION_SCOPE}]},
            UNSUPPORTED,
            UNSUPPORTED,
        ),
    ],
)
def test_capability_report_states_what_this_campaign_can_actually_run(
    tmp_path, runtime, feasibility, envelope
):
    report = capability_report(profile_for(tmp_path, runtime))
    capabilities = report["capabilities"]
    assert capabilities["reference_feasibility"]["status"] == feasibility
    assert capabilities["operating_envelope"]["status"] == envelope
    assert capabilities["physical_definition_check"]["status"] == ENABLED
    assert capabilities["numerical_worker_image"]["status"] == ENABLED
    assert capabilities["team_intake_receiver"]["status"] == FIXTURE_ONLY
    assert capabilities["public_activation"]["status"] == UNSUPPORTED
    assert capabilities["gpu_research"]["status"] == UNSUPPORTED
    assert capabilities["authored_research"]["status"] == UNSUPPORTED
    assert report["qualification"] == "NOT_QUALIFIED"
    # Discovery never leaks the scientific definition or any private value.
    body = json.dumps(report)
    assert "viscosity" not in body and "token" not in body


def test_capability_report_separates_missing_inputs_from_unsupported_scope(tmp_path):
    report = capability_report(
        profile_for(
            tmp_path / "missing",
            {"scientific_tasks": [{"schema": _JULIA_SCOPE}], "gpu_research": [{}]},
            image=False,
        )
    )
    capabilities = report["capabilities"]
    assert capabilities["numerical_worker_image"]["status"] == CONFIGURED_UNAVAILABLE
    assert capabilities["registered_draft_store"]["status"] == CONFIGURED_UNAVAILABLE
    assert capabilities["reference_feasibility"]["status"] == ENABLED
    assert "research MCP surface only" in capabilities["gpu_research"]["reason"]


# -- composed host ------------------------------------------------------------


def composed(tmp_path, monkeypatch, **kwargs):
    service, request, _records, _ledger, executions, calls, composition = configured(
        tmp_path, monkeypatch
    )
    physical = asyncio.run(service.capabilities())["physical"]
    store = store_for(tmp_path, service.adapter.principal)
    install_from(store, request, physical)
    bound = rebound(service, store, physical)
    principals = StaffPrincipals.load(
        principals_file(tmp_path, service.adapter.principal)
    )
    app = create_host_app(
        bound,
        principals=principals,
        allowed_origin=ORIGIN,
        static=static_build(tmp_path),
        report=capability_report(
            profile_for(
                tmp_path / "profile", {"scientific_tasks": [{"schema": _JULIA_SCOPE}]}
            ),
            registry=store,
        ),
        **kwargs,
    )
    return app, request, executions, calls, composition, store


def test_host_serves_science_status_and_the_private_build_in_one_composition(
    tmp_path, monkeypatch
):
    app, request, executions, _calls, composition, _store = composed(
        tmp_path, monkeypatch
    )
    auth = {"Authorization": "Bearer " + TOKEN}

    async def run():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url=ORIGIN
        ) as client:
            health = await client.get(HOST_PREFIX + "health")
            assert health.status_code == 200
            assert health.json()["status"] == "SERVING"
            assert health.json()["scientific_routes"] == "MOUNTED"

            capabilities = await client.get(HOST_PREFIX + "capabilities", headers=auth)
            assert capabilities.status_code == 200
            assert (
                capabilities.json()["capabilities"]["reference_feasibility"]["status"]
                == ENABLED
            )

            page = await client.get("/")
            assert page.status_code == 200
            assert 'data-scientific-service="private"' in page.text
            # The static mount serves the build's other artifacts and nothing else.
            named = await client.get("/Carbon_Client_Intake_Preview.html")
            assert named.status_code == 200 and "<html>" in named.text
            assert (
                await client.get("/Carbon_Opportunity_Workbench.html")
            ).status_code == 200
            for absent in (
                "/staff.json",
                "/drafts.json",
                "/../drafts.json",
                "/index.html",
            ):
                assert (await client.get(absent)).status_code in {403, 404}, absent

            # The real scientific route, through the real registry-backed service.
            science = await client.get(PREFIX + "capabilities", headers=auth)
            assert science.status_code == 200
            assert science.json()["template_id"] == TEMPLATE
            started = await client.post(
                PREFIX + "start",
                json=request,
                headers={**auth, "Origin": ORIGIN},
            )
            assert started.status_code == 200, started.text
            assert started.json()["status"] == "COMPLETE"

    try:
        asyncio.run(run())
        assert len(executions) == 1
    finally:
        composition.tasks.close()


@pytest.mark.parametrize(
    "headers,expected",
    [
        ({}, 401),
        ({"Authorization": "Bearer " + "z" * 48}, 401),
        ({"Authorization": "Basic " + TOKEN}, 401),
    ],
)
def test_host_routes_refuse_unnamed_credentials_before_any_dispatch(
    tmp_path, monkeypatch, headers, expected
):
    app, request, executions, calls, composition, _store = composed(
        tmp_path, monkeypatch
    )

    async def run():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url=ORIGIN
        ) as client:
            assert (
                await client.get(HOST_PREFIX + "capabilities", headers=headers)
            ).status_code == expected
            started = await client.post(
                PREFIX + "start", json=request, headers={**headers, "Origin": ORIGIN}
            )
            assert started.status_code == expected
            assert TOKEN not in started.text

    try:
        asyncio.run(run())
        assert calls == executions == []
    finally:
        composition.tasks.close()


def test_host_status_routes_keep_the_same_origin_guard(tmp_path, monkeypatch):
    app, _request, _executions, _calls, composition, _store = composed(
        tmp_path, monkeypatch
    )
    auth = {"Authorization": "Bearer " + TOKEN}

    async def run():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url=ORIGIN
        ) as client:
            for headers in (
                {"Origin": "https://attacker.invalid"},
                {"Host": "attacker.invalid"},
                {"Sec-Fetch-Site": "cross-site"},
            ):
                assert (
                    await client.get(HOST_PREFIX + "health", headers=headers)
                ).status_code == 403
                assert (
                    await client.get(
                        HOST_PREFIX + "capabilities", headers={**auth, **headers}
                    )
                ).status_code == 403
            assert (
                await client.post(HOST_PREFIX + "health", headers=auth)
            ).status_code == 405
            assert (await client.get(HOST_PREFIX + "unknown")).status_code == 404

    try:
        asyncio.run(run())
    finally:
        composition.tasks.close()


def test_host_reports_draining_without_touching_the_scientific_routes(
    tmp_path, monkeypatch
):
    state = {"stopping": False}
    app, _request, _executions, _calls, composition, _store = composed(
        tmp_path, monkeypatch, draining=lambda: state["stopping"]
    )

    async def run():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url=ORIGIN
        ) as client:
            assert (await client.get(HOST_PREFIX + "health")).json()[
                "status"
            ] == "SERVING"
            state["stopping"] = True
            assert (await client.get(HOST_PREFIX + "health")).json()[
                "status"
            ] == "DRAINING"

    try:
        asyncio.run(run())
    finally:
        composition.tasks.close()


def test_host_refuses_a_principal_file_for_a_different_campaign(tmp_path, monkeypatch):
    service, request, _records, _ledger, _executions, _calls, composition = configured(
        tmp_path, monkeypatch
    )
    try:
        physical = asyncio.run(service.capabilities())["physical"]
        store = store_for(tmp_path, service.adapter.principal)
        install_from(store, request, physical)
        principals = StaffPrincipals.load(principals_file(tmp_path, "someone-else"))
        with pytest.raises(ValueError, match="different campaign principal"):
            create_host_app(
                rebound(service, store, physical),
                principals=principals,
                allowed_origin=ORIGIN,
                static=static_build(tmp_path),
                report={"capabilities": {}},
            )
    finally:
        composition.tasks.close()


# -- operator command line ----------------------------------------------------


def operator_profile(service, tmp_path):
    """Stand in for ``load_profile`` with the exact fields the commands read.

    The campaign's real private role directory is placed where the commands
    derive it, so the installed record binds the definition the service checks.
    """
    import shutil

    data = service.material.study.data
    profile = profile_for(
        tmp_path / "profile", {"scientific_tasks": [{"schema": _JULIA_SCOPE}]}
    )
    profile.document["principal"] = service.adapter.principal
    profile.root = tmp_path / "campaign-root"
    if not (profile.root / "private-roles").exists():
        shutil.copytree(data.role_root, profile.root / "private-roles")
    return profile


def test_operator_commands_install_list_and_revoke_the_real_registry(
    tmp_path, monkeypatch, capsys
):
    from carbon.scientific_tasks import workbench_host

    service, request, _records, _ledger, _executions, _calls, composition = configured(
        tmp_path, monkeypatch
    )
    try:
        profile = operator_profile(service, tmp_path)
        monkeypatch.setattr(
            workbench_host, "load_development_profile", lambda *a, **k: profile
        )
        registry = private_directory(tmp_path / "private") / "cli-drafts.json"
        draft = tmp_path / "draft.json"
        draft.write_text(
            json.dumps(
                {
                    "job_id": "job-one",
                    "design_id": "design-one",
                    "revision": 1,
                    "draft_scope": request["draft_scope"],
                }
            )
        )
        common = [
            "--configuration",
            str(tmp_path / "cfg"),
            "--draft-registry",
            str(registry),
        ]
        assert (
            workbench_host.main(["register-draft", *common, "--draft", str(draft)]) == 0
        )
        assert json.loads(capsys.readouterr().out)["registered_drafts"] == {
            "designs": 1,
            "revisions": 1,
        }

        # The installed record must bind the definition the service will check.
        physical = asyncio.run(service.capabilities())["physical"]
        store = RegisteredDraftStore(registry, principal=service.adapter.principal)
        assert (
            store.resolver(physical)(
                service.adapter.principal, "job-one", "design-one", 1
            )
            is not None
        )
        started = asyncio.run(rebound(service, store, physical).call("start", request))
        assert started["status"] == "COMPLETE"

        assert workbench_host.main(["list-drafts", *common]) == 0
        capsys.readouterr()
        assert (
            workbench_host.main(
                [
                    "revoke-draft",
                    *common,
                    "--job-id",
                    "job-one",
                    "--design-id",
                    "design-one",
                ]
            )
            == 0
        )
        assert json.loads(capsys.readouterr().out)["registered_drafts"]["designs"] == 0
    finally:
        composition.tasks.close()


def test_operator_commands_reject_an_open_draft_and_report_without_secrets(
    tmp_path, monkeypatch, capsys
):
    from carbon.scientific_tasks import workbench_host

    service, request, _records, _ledger, _executions, _calls, composition = configured(
        tmp_path, monkeypatch
    )
    try:
        profile = operator_profile(service, tmp_path)
        monkeypatch.setattr(
            workbench_host, "load_development_profile", lambda *a, **k: profile
        )
        registry = private_directory(tmp_path / "private") / "cli-drafts.json"
        common = [
            "--configuration",
            str(tmp_path / "cfg"),
            "--draft-registry",
            str(registry),
        ]
        draft = tmp_path / "open.json"
        draft.write_text(
            json.dumps(
                {
                    "job_id": "job-one",
                    "design_id": "design-one",
                    "revision": 1,
                    "draft_scope": request["draft_scope"],
                    "rights_scope": "CUSTOMER_CONFIDENTIAL",
                }
            )
        )
        assert (
            workbench_host.main(["register-draft", *common, "--draft", str(draft)]) == 2
        )
        assert "closed" in capsys.readouterr().err
        assert not registry.exists()

        assert (
            workbench_host.main(["check", "--configuration", str(tmp_path / "cfg")])
            == 0
        )
        printed = capsys.readouterr().out
        assert "NOT_QUALIFIED" not in printed  # the banner says it in words instead
        assert "ENABLED" in printed and "UNSUPPORTED" in printed
        assert "qualifies no physics" in printed
        assert service.adapter.principal not in printed
    finally:
        composition.tasks.close()


def test_a_malformed_draft_scope_never_reaches_the_registry(tmp_path, monkeypatch):
    service, request, _records, _ledger, _executions, _calls, composition = configured(
        tmp_path, monkeypatch
    )
    try:
        physical = asyncio.run(service.capabilities())["physical"]
        store = store_for(tmp_path, service.adapter.principal)
        install_from(store, request, physical)
        before = store.path.read_bytes()
        rejected = [
            {**request["draft_scope"], "extra_field": "x"},
            {k: v for k, v in request["draft_scope"].items() if k != "units"},
            {**request["draft_scope"], "units": ""},
            {**request["draft_scope"], "units": "u" * 8001},
            {**request["draft_scope"], "units": 3},
        ]
        for scope in rejected:
            with pytest.raises((ValueError, TypeError)):
                store.install(
                    job_id="job-two",
                    design_id="design-two",
                    revision=1,
                    draft_scope=scope,
                    physical=physical,
                )
        for revision in (0, -1, 1.5, True, "1"):
            with pytest.raises(ValueError):
                store.install(
                    job_id="job-two",
                    design_id="design-two",
                    revision=revision,
                    draft_scope=request["draft_scope"],
                    physical=physical,
                )
        for job in ("", "job two", "../escape", "x" * 200):
            with pytest.raises(ValueError):
                store.install(
                    job_id=job,
                    design_id="design-two",
                    revision=1,
                    draft_scope=request["draft_scope"],
                    physical=physical,
                )
        # Nothing was written: the earlier registry is byte-identical.
        assert store.path.read_bytes() == before
        assert store.summary() == {"designs": 1, "revisions": 1}
    finally:
        composition.tasks.close()


def test_capability_states_are_not_readable_from_the_co_served_client_surface(
    tmp_path, monkeypatch
):
    """The client intake preview shares this origin, so the four capability
    states must cost a staff credential to read.

    The preview deliberately collapses "unreachable" and "misconfigured" into one
    unavailable state: the customer's next action is the same either way, and
    distinguishing them would disclose operator configuration to an external
    party. That withholding only means something if the distinction is not
    available from the same origin without authentication -- and the preview is
    co-served, because verify_private_build requires it to be present.
    """
    app, _request, _executions, _calls, composition, _store = composed(
        tmp_path, monkeypatch
    )

    async def run():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url=ORIGIN
        ) as client:
            # The preview really is served from this origin.
            preview = await client.get("/Carbon_Client_Intake_Preview.html")
            assert preview.status_code == 200, "the client preview is not co-served"

            # Reading it must not also hand over the capability states.
            refused = await client.get(HOST_PREFIX + "capabilities")
            assert refused.status_code == 401, (
                "the four capability states are readable from the co-served "
                "client origin without a credential, so the preview's collapsed "
                "unavailable state is cosmetic rather than a boundary"
            )
            body = refused.text
            for state in ("ENABLED", "CONFIGURED_UNAVAILABLE", "FIXTURE_ONLY"):
                assert state not in body, f"refusal leaked the {state} vocabulary"

            # Health is unauthenticated on purpose and must stay uninformative
            # about configuration.
            health = await client.get(HOST_PREFIX + "health")
            assert health.status_code == 200
            text = json.dumps(health.json())
            for leaked in (
                "CONFIGURED_UNAVAILABLE",
                "FIXTURE_ONLY",
                "UNSUPPORTED",
                "provider",
                "token",
            ):
                assert leaked not in text, f"health disclosed {leaked}"

    try:
        asyncio.run(run())
    finally:
        composition.tasks.close()
