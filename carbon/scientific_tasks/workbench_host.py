"""Supported private-host composition for the existing Workbench science routes.

The operator already owns an admitted research campaign, its private stores and
its reviewed static build. This module composes those existing objects instead of
asking the operator to assemble them by hand, and it adds nothing scientific: no
scheduler, evaluator, grant, solver, measurement, qualification or public service.

It creates no authentication scheme beyond reading the operator's own private,
named staff-token file, and it never widens what ``WorkbenchScience`` will accept.
A registered draft remains an operator installation; a browser cannot create one.
"""

from __future__ import annotations

import asyncio
import hmac
import json
import os
import re
import sys
import tempfile
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from carbon.development_session.profile import canonical
from carbon.development_session.research_admission import private_json
from carbon.development_session.research_sequences import SCOPE as _ENVELOPE_SCOPE
from carbon.scientific_tasks.workbench import (
    RegisteredWorkbenchDraft,
    WorkbenchScience,
    granted_physical,
    wire_digest,
)
from carbon.scientific_tasks.workbench_http import (
    check_private_origin,
    create_workbench_app,
)

HOST_PRINCIPALS = "carbon.workbench.host-principals.v1"
DRAFT_REGISTRY = "carbon.workbench.draft-registry.v1"
CAPABILITIES = "carbon.workbench.host-capabilities.v1"
HEALTH = "carbon.workbench.host-health.v1"

#: The exact files ``Business/Carbon_Fit/workbench/tools/build.py`` emits. A host
#: that is pointed at any other directory is refused rather than made to serve a
#: private store, a checkout or a credential by accident.
BUILD_ARTIFACTS = frozenset(
    {
        "Carbon_Opportunity_Workbench.html",
        "Carbon_Client_Intake_Preview.html",
        "Carbon_Client_Pilot_Designer_Preview.html",
    }
)
PRIVATE_BUILD_MARKER = 'data-scientific-service="private"'

ENABLED = "ENABLED"
CONFIGURED_UNAVAILABLE = "CONFIGURED_UNAVAILABLE"
FIXTURE_ONLY = "FIXTURE_ONLY"
UNSUPPORTED = "UNSUPPORTED"

#: Asserted against the scope builders themselves in the host tests, so a
#: renamed registered scope cannot silently downgrade a capability to UNSUPPORTED.
_JULIA_SCOPE = "carbon.public-julia-study.scope.v1"
_ADVECTION_SCOPE = "carbon.public-advection-study.scope.v1"
_IDENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")
_TOKEN = re.compile(r"[A-Za-z0-9._~-]{32,300}\Z")
_SCOPE_FIELDS = frozenset(
    {
        "physics_family",
        "requested_goal",
        "inputs",
        "outputs",
        "units",
        "geometry",
        "conditions",
        "regime",
        "exclusions",
        "query_workload",
        "rights_scope",
        "reference_equation",
        "reference_method",
    }
)
MAX_REGISTRY_BYTES = 65536


def _ident(value, label):
    if type(value) is not str or _IDENT.fullmatch(value) is None:
        raise ValueError(f"bounded {label} required")
    return value


def _revision(value):
    if type(value) is not int or type(value) is bool or not 1 <= value <= 2**53 - 1:
        raise ValueError("positive safe draft revision required")
    return value


def _private_write(path: Path, payload: bytes):
    """Owner-only atomic replace that reaches the disk before it is acknowledged.

    A receipt the operator can see must survive the machine losing power, so the
    replacement file and its directory entry are both flushed before returning.
    """
    directory = path.parent
    handle, temporary = tempfile.mkstemp(
        dir=directory, prefix=".workbench-", suffix=".tmp"
    )
    try:
        with os.fdopen(handle, "wb") as stream:
            os.fchmod(stream.fileno(), 0o600)
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except BaseException:
        os.unlink(temporary)
        raise
    fd = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


@dataclass(frozen=True)
class StaffPrincipals:
    """Named operator tokens for one campaign principal; no scientific authority.

    Every token resolves to the same campaign principal because the scientific
    routes act as that one admitted identity by construction. The named entry
    records which staff member opened the session; it grants nothing extra.
    """

    path: Path
    campaign_principal: str
    names: tuple[str, ...]
    _digests: tuple[str, ...]

    @classmethod
    def load(cls, path: Path) -> StaffPrincipals:
        document = private_json(path)
        if (
            type(document) is not dict
            or set(document) != {"schema", "campaign_principal", "staff"}
            or document["schema"] != HOST_PRINCIPALS
            or type(document["staff"]) is not list
            or not 1 <= len(document["staff"]) <= 64
        ):
            raise ValueError("closed private staff principal record required")
        principal = _ident(document["campaign_principal"], "campaign principal")
        names, digests = [], []
        for entry in document["staff"]:
            if (
                type(entry) is not dict
                or set(entry) != {"name", "token_sha256"}
                or type(entry["name"]) is not str
                or not 1 <= len(entry["name"]) <= 200
                or type(entry["token_sha256"]) is not str
                or re.fullmatch(r"[0-9a-f]{64}", entry["token_sha256"]) is None
            ):
                raise ValueError("closed named staff token entry required")
            names.append(entry["name"])
            digests.append(entry["token_sha256"])
        if len(set(digests)) != len(digests):
            raise ValueError("distinct staff tokens required")
        return cls(path, principal, tuple(names), tuple(digests))

    def resolve(self, request) -> str:
        """Return the campaign principal for a valid bearer token, else raise.

        Every configured entry is compared so a rejected token cannot be timed
        against its position in the file.
        """
        header = request.headers.getlist("authorization")
        if len(header) != 1:
            raise ValueError("one bearer credential required")
        match = re.fullmatch(r"Bearer ([A-Za-z0-9._~-]{32,300})", header[0])
        if match is None:
            raise ValueError("bearer credential required")
        offered = sha256(match.group(1).encode("ascii")).hexdigest()
        matched = False
        for known in self._digests:
            matched |= hmac.compare_digest(known, offered)
        if not matched:
            raise ValueError("staff credential rejected")
        return self.campaign_principal


class RegisteredDraftStore:
    """Durable private registry of operator-installed Workbench drafts.

    The record binds an exact job, design and revision to the exact granted
    public physical definition. It carries no customer input, no rights grant and
    no scientific claim: ``WorkbenchScience`` still re-checks every request field.
    The file is re-read on each resolution, so an operator can install or revoke a
    draft while the host serves, and a revocation takes effect immediately.
    """

    def __init__(self, path: Path, *, principal: str):
        self.path = Path(path)
        if not self.path.is_absolute() or self.path.resolve() != self.path:
            raise ValueError("absolute unaliased private registry path required")
        self.principal = _ident(principal, "campaign principal")

    # -- reading ---------------------------------------------------------
    def document(self) -> dict:
        if not self.path.exists():
            return {
                "schema": DRAFT_REGISTRY,
                "principal": self.principal,
                "designs": [],
            }
        document = private_json(self.path)
        if (
            type(document) is not dict
            or set(document) != {"schema", "principal", "designs"}
            or document["schema"] != DRAFT_REGISTRY
            or document["principal"] != self.principal
            or type(document["designs"]) is not list
        ):
            raise ValueError("closed private draft registry required")
        seen = set()
        for design in document["designs"]:
            self._check_design(design)
            key = (design["job_id"], design["design_id"])
            if key in seen:
                raise ValueError("duplicate registered design requires reconciliation")
            seen.add(key)
        return document

    @staticmethod
    def _check_design(design):
        if (
            type(design) is not dict
            or set(design) != {"job_id", "design_id", "current_revision", "revisions"}
            or type(design["revisions"]) is not list
            or not design["revisions"]
        ):
            raise ValueError("closed registered design record required")
        _ident(design["job_id"], "job identity")
        _ident(design["design_id"], "design identity")
        _revision(design["current_revision"])
        revisions = set()
        for record in design["revisions"]:
            if (
                type(record) is not dict
                or set(record)
                != {"revision", "draft_scope", "rights_scope", "physical_sha256"}
                or record["rights_scope"] != "SYNTHETIC_INTERNAL"
                or type(record["physical_sha256"]) is not str
                or re.fullmatch(r"[0-9a-f]{64}", record["physical_sha256"]) is None
                or type(record["draft_scope"]) is not dict
                or set(record["draft_scope"]) != _SCOPE_FIELDS
                or any(
                    type(value) is not str or not 1 <= len(value) <= 8000
                    for value in record["draft_scope"].values()
                )
            ):
                raise ValueError("closed registered draft revision required")
            if _revision(record["revision"]) in revisions:
                raise ValueError("duplicate registered revision")
            revisions.add(record["revision"])
        if design["current_revision"] not in revisions:
            raise ValueError("current revision is not installed")

    def resolver(self, physical: dict):
        """Bind the registry to the exact live granted definition.

        ``physical`` comes from the composed service's own capabilities, never
        from the stored file, so a stored record can only ever agree or fail.
        """
        expected = wire_digest(physical)

        def resolve(principal, job_id, design_id, revision):
            if principal != self.principal:
                return None
            try:
                document = self.document()
            except (ValueError, OSError):
                return None
            for design in document["designs"]:
                if design["job_id"] != job_id or design["design_id"] != design_id:
                    continue
                for record in design["revisions"]:
                    if record["revision"] != revision:
                        continue
                    if record["physical_sha256"] != expected:
                        return None
                    return RegisteredWorkbenchDraft(
                        principal=principal,
                        job_id=job_id,
                        design_id=design_id,
                        revision=revision,
                        current_revision=design["current_revision"],
                        draft_scope=dict(record["draft_scope"]),
                        physical=json.loads(json.dumps(physical)),
                        rights_scope=record["rights_scope"],
                    )
            return None

        return resolve

    # -- operator writes -------------------------------------------------
    def install(self, *, job_id, design_id, revision, draft_scope, physical) -> dict:
        """Install one reviewed revision and make it the design's current one."""
        _ident(job_id, "job identity")
        _ident(design_id, "design identity")
        _revision(revision)
        record = {
            "revision": revision,
            "draft_scope": {str(k): draft_scope[k] for k in sorted(draft_scope)},
            "rights_scope": "SYNTHETIC_INTERNAL",
            "physical_sha256": wire_digest(physical),
        }
        document = self.document()
        designs = [
            design
            for design in document["designs"]
            if (design["job_id"], design["design_id"]) != (job_id, design_id)
        ]
        existing = [
            design
            for design in document["designs"]
            if (design["job_id"], design["design_id"]) == (job_id, design_id)
        ]
        revisions = [
            item
            for design in existing
            for item in design["revisions"]
            if item["revision"] != revision
        ]
        designs.append(
            {
                "job_id": job_id,
                "design_id": design_id,
                "current_revision": revision,
                "revisions": sorted(
                    [*revisions, record], key=lambda item: item["revision"]
                ),
            }
        )
        return self._persist(designs)

    def revoke(self, *, job_id, design_id, revision=None) -> dict:
        """Remove one revision, or the whole design when no revision is named.

        Removing the current revision falls back to the highest one still
        installed; removing the last one removes the design.
        """
        document = self.document()
        designs = []
        found = False
        for design in document["designs"]:
            if (design["job_id"], design["design_id"]) != (job_id, design_id):
                designs.append(design)
                continue
            found = True
            if revision is None:
                continue
            kept = [
                item for item in design["revisions"] if item["revision"] != revision
            ]
            found = len(kept) != len(design["revisions"])
            if not kept:
                continue
            current = design["current_revision"]
            if current == revision:
                current = max(item["revision"] for item in kept)
            designs.append({**design, "current_revision": current, "revisions": kept})
        if not found:
            raise ValueError("no such registered draft")
        return self._persist(designs)

    def _persist(self, designs) -> dict:
        document = {
            "schema": DRAFT_REGISTRY,
            "principal": self.principal,
            "designs": sorted(
                designs, key=lambda design: (design["job_id"], design["design_id"])
            ),
        }
        for design in document["designs"]:
            self._check_design(design)
        payload = canonical(document)
        if len(payload) > MAX_REGISTRY_BYTES:
            raise ValueError("registered draft registry exceeds its bounded size")
        if self.path.is_symlink():
            raise ValueError("private registry must not be a symlink")
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        _private_write(self.path, payload)
        return document

    def summary(self) -> dict:
        document = self.document()
        return {
            "designs": len(document["designs"]),
            "revisions": sum(len(d["revisions"]) for d in document["designs"]),
        }


def _scientific_kind(runtime) -> str:
    scopes = runtime.get("scientific_tasks")
    if type(scopes) is not list or not scopes:
        return "legacy"
    schemas = [s.get("schema") if type(s) is dict else None for s in scopes]
    if schemas == [_JULIA_SCOPE]:
        return "burgers"
    if schemas == [_JULIA_SCOPE, _ENVELOPE_SCOPE]:
        return "envelope"
    if schemas == [_ADVECTION_SCOPE]:
        return "advection"
    return "unknown"


def capability_report(profile, *, registry: RegisteredDraftStore | None = None) -> dict:
    """Describe exactly what this host can and cannot do, before it serves.

    This reads the operator's already-verified profile and campaign manifest. It
    starts no container, probes no accelerator and reveals no secret, path or
    scientific value; the scientific definition stays on the scientific route.
    """
    runtime = profile.manifest["runtime"]
    kind = _scientific_kind(runtime)
    paths = {name: Path(value) for name, value in profile.document["paths"].items()}

    def present(name):
        path = paths.get(name)
        return path is not None and path.is_file()

    def entry(status, reason):
        return status, reason

    capabilities = {
        "physical_definition_check": entry(
            ENABLED,
            "Browser-local structural check. It is not a solver, a reference"
            " calculation, a measurement or any scientific qualification.",
        ),
        "reference_feasibility": (
            entry(ENABLED, "Registered single-case public Julia study.")
            if kind in {"burgers", "envelope"}
            else entry(
                UNSUPPORTED,
                "This campaign's admitted runtime registers no public Julia"
                " study scope, so no Workbench study can be dispatched.",
            )
        ),
        "operating_envelope": (
            entry(ENABLED, "Registered two-case public Julia envelope study.")
            if kind == "envelope"
            else entry(
                UNSUPPORTED,
                "The admitted runtime does not register the second envelope"
                " scope. Two public cases would not be an operating envelope.",
            )
        ),
        "numerical_worker_image": (
            entry(
                ENABLED,
                "Pinned worker image manifest is present. Host eligibility is"
                " verified when the service starts, not during discovery.",
            )
            if present("image_manifest")
            else entry(
                CONFIGURED_UNAVAILABLE,
                "The configured worker image manifest is missing or is not a"
                " regular file.",
            )
        ),
        "authored_research": entry(
            UNSUPPORTED,
            (
                "Registered for the research MCP surface only."
                if "authored_research" in runtime
                else "Not registered, and the Workbench exposes no authored action."
            ),
        ),
        "gpu_research": entry(
            UNSUPPORTED,
            (
                "Registered for the research MCP surface only; the Workbench adds no"
                " GPU solver and substitutes no backend."
                if "gpu_research" in runtime
                else "Not registered. No Workbench GPU route exists."
            ),
        ),
        "registered_draft_store": (
            entry(ENABLED, "Operator-installed drafts resolve for scientific requests.")
            if registry is not None and registry.path.exists()
            else entry(
                CONFIGURED_UNAVAILABLE,
                "No draft is installed yet, so every scientific request will be"
                " refused until the operator registers one.",
            )
        ),
        "team_intake_receiver": entry(
            FIXTURE_ONLY,
            "The private receiver is a local synthetic store. No public host,"
            " sender, notice, consent, retention or abuse decision is configured.",
        ),
        "public_activation": entry(
            UNSUPPORTED,
            "Live customer collection is not enabled by this host and is not"
            " authorized here.",
        ),
    }
    report = {
        "schema": CAPABILITIES,
        "scientific_scope": kind,
        "capabilities": {
            name: {"status": status, "reason": reason}
            for name, (status, reason) in sorted(capabilities.items())
        },
        "qualification": "NOT_QUALIFIED",
        "authority": "ENGINEERING_COMPOSITION_ONLY_NOT_SCIENTIFIC_OR_DEPLOYMENT",
    }
    if registry is not None:
        try:
            report["registered_drafts"] = registry.summary()
        except (ValueError, OSError):
            report["registered_drafts"] = None
            report["capabilities"]["registered_draft_store"] = {
                "status": CONFIGURED_UNAVAILABLE,
                "reason": "The private draft registry is unreadable or malformed.",
            }
    return report


def verify_private_build(directory: Path) -> Path:
    """Accept only the reviewed private-science build output.

    The offline artifact cannot reach the service and a checkout, private store or
    credential directory must never be published by a host that merely serves HTML.
    """
    directory = Path(directory)
    if (
        not directory.is_absolute()
        or directory.resolve() != directory
        or not directory.is_dir()
        or directory.is_symlink()
    ):
        raise ValueError("absolute unaliased private build directory required")
    entries = sorted(item.name for item in directory.iterdir())
    if not entries or set(entries) - BUILD_ARTIFACTS:
        raise ValueError(
            "the static directory must contain only the Workbench build artifacts"
        )
    for name in entries:
        item = directory / name
        if item.is_symlink() or not item.is_file():
            raise ValueError("the static directory must contain only regular files")
    page = directory / "Carbon_Opportunity_Workbench.html"
    if not page.is_file():
        raise ValueError("the private build's Workbench page is missing")
    if PRIVATE_BUILD_MARKER not in page.read_text(encoding="utf-8"):
        raise ValueError(
            "an offline build cannot reach the private service; rebuild with "
            "--private-science"
        )
    return page


def create_host_app(
    service: WorkbenchScience,
    *,
    principals: StaffPrincipals,
    allowed_origin: str,
    static: Path,
    report: dict,
    draining=None,
):
    """Compose the fixed scientific routes, host status and the static build.

    Route order is deliberate: the reviewed scientific routes resolve first, then
    this host's own status routes, then the static build as the catch-all. No
    handler here reads, repeats or bypasses any scientific logic.
    """
    from urllib.parse import urlsplit

    from starlette.responses import JSONResponse, Response
    from starlette.routing import Route
    from starlette.staticfiles import StaticFiles

    if type(service) is not WorkbenchScience:
        raise ValueError("composed Workbench science service required")
    if type(principals) is not StaffPrincipals:
        raise ValueError("named private staff principals required")
    if principals.campaign_principal != service.adapter.principal:
        raise ValueError("staff principal file names a different campaign principal")
    page = verify_private_build(static)
    app = create_workbench_app(
        service,
        authorize=principals.resolve,
        allowed_origin=allowed_origin,
    )
    netloc = urlsplit(allowed_origin).netloc
    headers = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}
    if draining is not None and not callable(draining):
        raise ValueError("draining must be a predicate")

    def failed(status, code):
        return JSONResponse({"error": code}, status_code=status, headers=headers)

    async def health(request):
        denied = check_private_origin(
            request, allowed_origin=allowed_origin, netloc=netloc, expected_method="GET"
        )
        if denied is not None:
            return failed(405 if denied == "METHOD_OR_PATH_DENIED" else 403, denied)
        return JSONResponse(
            {
                "schema": HEALTH,
                "status": "DRAINING" if draining and draining() else "SERVING",
                "scientific_routes": "MOUNTED",
            },
            headers=headers,
        )

    async def capabilities(request):
        denied = check_private_origin(
            request, allowed_origin=allowed_origin, netloc=netloc, expected_method="GET"
        )
        if denied is not None:
            return failed(405 if denied == "METHOD_OR_PATH_DENIED" else 403, denied)
        try:
            principal = principals.resolve(request)
        except Exception:  # noqa: BLE001
            return failed(401, "AUTHENTICATION_REQUIRED")
        if principal != service.adapter.principal:
            return failed(403, "PRINCIPAL_DENIED")
        return JSONResponse(report, headers=headers)

    app.router.routes.append(
        Route("/api/workbench-host/health", health, methods=["GET"])
    )
    app.router.routes.append(
        Route("/api/workbench-host/capabilities", capabilities, methods=["GET"])
    )

    async def index(request):
        denied = check_private_origin(
            request, allowed_origin=allowed_origin, netloc=netloc, expected_method="GET"
        )
        if denied is not None:
            return failed(405 if denied == "METHOD_OR_PATH_DENIED" else 403, denied)
        # Read per request, exactly as the static mount serves the other
        # artifacts, so "/" cannot quietly disagree with its own file name.
        return Response(
            page.read_bytes(), media_type="text/html; charset=utf-8", headers=headers
        )

    app.router.routes.append(Route("/", index, methods=["GET"]))
    app.mount("/", StaticFiles(directory=str(static), html=True))
    return app


def role_root(profile) -> Path:
    """The campaign's existing private role directory; no case is ever drawn."""
    return profile.root / "private-roles"


def compose(adapter, registry: RegisteredDraftStore) -> WorkbenchScience:
    """Bind the registry to the live grant, or say plainly that there is no route."""
    try:
        probe = WorkbenchScience(adapter, draft_resolver=lambda *_: None)
    except ValueError as error:
        raise ValueError(
            "this campaign's registered scientific scope exposes no Workbench "
            "study route; run the host check for the exact capability status"
        ) from error
    physical = granted_physical(probe.material.study.data.role_root)
    return WorkbenchScience(adapter, draft_resolver=registry.resolver(physical))


def _origin(value: str, port: int) -> str:
    from urllib.parse import urlsplit

    parsed = urlsplit(value)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.path
        or parsed.query
        or parsed.fragment
        or parsed.username is not None
        or parsed.password is not None
        or value != parsed.geturl()
    ):
        raise ValueError("exact scheme://host[:port] service origin required")
    if parsed.scheme == "http":
        if parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
            raise ValueError("plain HTTP is available only for a loopback fixture")
        if parsed.port != port:
            raise ValueError("loopback origin port must match the served port")
    return value


async def serve(args) -> int:
    """Serve the composed private host for as long as the campaign is attached."""
    import uvicorn

    from carbon.miner_mcp.standard_cli import attached

    origin = _origin(args.origin, args.port)
    principals = StaffPrincipals.load(args.principals)
    verify_private_build(args.static)
    async with attached(args.configuration) as (adapter, profile):
        registry = RegisteredDraftStore(
            args.draft_registry, principal=adapter.principal
        )
        service = compose(adapter, registry)
        report = capability_report(profile, registry=registry)
        holder = {}
        app = create_host_app(
            service,
            principals=principals,
            allowed_origin=origin,
            static=args.static,
            report=report,
            draining=lambda: bool(
                holder.get("server") and holder["server"].should_exit
            ),
        )
        server = uvicorn.Server(
            uvicorn.Config(
                app,
                host=args.bind_host,
                port=args.port,
                access_log=False,
                log_level="warning",
                date_header=False,
                server_header=False,
            )
        )
        holder["server"] = server
        _print_report(report, origin=origin, staff=principals.names)
        await server.serve()
    return 0


def _print_report(report, *, origin=None, staff=()):
    """Print capability status only. No secret, token, path or scientific value."""
    print(
        json.dumps(
            {"schema": CAPABILITIES, "scientific_scope": report["scientific_scope"]}
        )
    )
    if origin is not None:
        print(f"origin: {origin}")
    if staff:
        print("named staff credentials configured: " + ", ".join(staff))
    for name, entry in report["capabilities"].items():
        print(f"  {entry['status']:<24} {name}: {entry['reason']}")
    drafts = report.get("registered_drafts")
    if drafts is not None:
        print(
            f"  registered drafts: {drafts['designs']} design(s), "
            f"{drafts['revisions']} revision(s)"
        )
    print(
        "This host composes existing objects. It qualifies no physics, grants no "
        "rights and activates no public collection."
    )


def _registry_for(args):
    from carbon.miner_mcp.standard_cli import load_profile

    profile = load_profile(args.configuration)
    registry = RegisteredDraftStore(
        args.draft_registry, principal=profile.document["principal"]
    )
    return profile, registry


def main(argv=None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    def common(sub):
        sub.add_argument("--configuration", required=True, type=Path)
        sub.add_argument("--draft-registry", required=True, type=Path)

    check = commands.add_parser(
        "check", help="Report capability status without starting any container"
    )
    check.add_argument("--configuration", required=True, type=Path)
    check.add_argument("--draft-registry", type=Path)

    run = commands.add_parser("serve", help="Serve the composed private host")
    common(run)
    run.add_argument("--static", required=True, type=Path)
    run.add_argument("--principals", required=True, type=Path)
    run.add_argument("--origin", required=True)
    run.add_argument("--port", required=True, type=int)
    run.add_argument("--bind-host", default="127.0.0.1")

    install = commands.add_parser(
        "register-draft", help="Install one reviewed design revision"
    )
    common(install)
    install.add_argument("--draft", required=True, type=Path)

    remove = commands.add_parser("revoke-draft", help="Remove a registered revision")
    common(remove)
    remove.add_argument("--job-id", required=True)
    remove.add_argument("--design-id", required=True)
    remove.add_argument("--revision", type=int)

    listing = commands.add_parser("list-drafts", help="Summarize installed drafts")
    common(listing)

    args = parser.parse_args(argv)
    try:
        if args.command == "check":
            from carbon.miner_mcp.standard_cli import load_profile

            profile = load_profile(args.configuration)
            registry = (
                RegisteredDraftStore(
                    args.draft_registry, principal=profile.document["principal"]
                )
                if args.draft_registry is not None
                else None
            )
            _print_report(capability_report(profile, registry=registry))
            return 0
        if args.command == "serve":
            return asyncio.run(serve(args))
        profile, registry = _registry_for(args)
        if args.command == "register-draft":
            draft = json.loads(Path(args.draft).read_bytes())
            if type(draft) is not dict or set(draft) != {
                "job_id",
                "design_id",
                "revision",
                "draft_scope",
            }:
                raise ValueError(
                    "closed {job_id, design_id, revision, draft_scope} draft required"
                )
            registry.install(
                job_id=draft["job_id"],
                design_id=draft["design_id"],
                revision=draft["revision"],
                draft_scope=draft["draft_scope"],
                physical=granted_physical(role_root(profile)),
            )
        elif args.command == "revoke-draft":
            registry.revoke(
                job_id=args.job_id,
                design_id=args.design_id,
                revision=args.revision,
            )
        print(json.dumps({"registered_drafts": registry.summary()}))
        return 0
    except (Exception, KeyboardInterrupt) as error:  # noqa: BLE001
        print(
            "Carbon Workbench host unavailable: "
            + str(error)
            + "\nVerify the private profile, grant, prepared campaign, staff "
            "principals, draft registry and private-science build.",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
