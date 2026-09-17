"""Disposable loopback-only browser fixture with real admitted Julia execution.

Not a production host or authentication implementation. The operator test runner
installs the exact synthetic draft before serving; browsers cannot register drafts
or grants. Requires an unused root and immutable existing worker image manifest.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

import pytest
import uvicorn
from starlette.staticfiles import StaticFiles

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPOSITORY), str(REPOSITORY / "tests/cpu")]

from test_julia_research import prepared
from test_standard_mcp_cli import FixtureSigner, fixture_connection

from carbon.development_session.julia_envelope import (
    JuliaEnvelopeMaterial,
    julia_envelope_scope,
)
from carbon.development_session.julia_research import (
    JuliaPublicMaterial,
    PublicJuliaStudy,
)
from carbon.development_session.research_material import PublicMaterial
from carbon.development_session.research_service import make_research_service
from carbon.development_session.research_tools import ResearchMinerTools
from carbon.miner_mcp.research import AuthenticatedResearchService
from carbon.miner_mcp.standard import ResearchToolAdapter
from carbon.miner_mcp.standard_cli import _requester
from carbon.reconstruction.worker.docker_runtime import load_image_identity
from carbon.scientific_tasks.workbench import RegisteredWorkbenchDraft, WorkbenchScience
from carbon.scientific_tasks.workbench_http import create_workbench_app


def main():
    import carbon.chain.auth
    from carbon.development_session import research_tools

    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("root", "manifest", "draft", "static"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--port", required=True, type=int)
    parser.add_argument("--envelope", action="store_true")
    args = parser.parse_args()
    if (
        not args.root.is_absolute()
        or args.root.exists()
        or not 1024 <= args.port <= 65535
    ):
        raise ValueError("new absolute fixture root and unprivileged port required")
    args.root.mkdir(mode=0o700, parents=True)
    (args.root / "campaign").mkdir()
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(carbon.chain.auth, "BittensorMessageSigner", FixtureSigner)
    monkeypatch.setattr(research_tools, "BittensorMessageSigner", FixtureSigner)
    connection = fixture_connection(args.root / "campaign")
    owner = asyncio.run(_requester(connection))
    image = load_image_identity(args.manifest)
    data, ledger, _calls = prepared(
        args.root, monkeypatch, image=image, owner=owner, envelope=args.envelope
    )
    scope = julia_envelope_scope(image, data.role_root) if args.envelope else None
    material = JuliaPublicMaterial(
        PublicMaterial(data), PublicJuliaStudy(data, envelope_scope=scope)
    )
    if args.envelope:
        material = JuliaEnvelopeMaterial(material)
    composition = make_research_service(
        root=args.root / "tasks",
        ledger=ledger,
        owner=owner,
        image=image,
        public_material=material,
        practice=None,
    )
    adapter = ResearchToolAdapter(
        ResearchMinerTools(
            connection=connection,
            wrapper=AuthenticatedResearchService(
                connection.service.gateway, {owner: composition.service}
            ),
            composition=composition,
            ledger=ledger,
            owner=owner,
        ),
        principal=owner,
    )
    records = {}
    service = WorkbenchScience(
        adapter, draft_resolver=lambda p, j, d, r: records.get((p, j, d, r))
    )
    physical = asyncio.run(service.capabilities())["physical"]
    draft = json.loads(args.draft.read_bytes())
    key = (owner, draft["job_id"], draft["design_id"], draft["revision"])
    records[key] = RegisteredWorkbenchDraft(
        *key, draft["current_revision"], draft["scope"], physical, "SYNTHETIC_INTERNAL"
    )
    origin = "http://127.0.0.1:" + str(args.port)
    app = create_workbench_app(
        service,
        authorize=lambda request: (
            owner if request.client.host in {"127.0.0.1", "::1"} else None
        ),
        allowed_origin=origin,
    )
    app.mount("/", StaticFiles(directory=args.static, html=True))
    print(
        json.dumps(
            {
                "fixture": "LOCAL_SYNTHETIC_OPERATOR_AUTH_ONLY",
                "origin": origin,
                "image": image.image_id,
                "root": str(args.root),
            }
        ),
        flush=True,
    )
    try:
        uvicorn.run(app, host="127.0.0.1", port=args.port, access_log=False)
    finally:
        print(
            json.dumps({"fixture_used": ledger.status(owner=owner)["used"]}), flush=True
        )
        composition.tasks.close()
        monkeypatch.undo()


if __name__ == "__main__":
    main()
