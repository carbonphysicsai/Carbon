"""Optional MCP App view over an explicitly authorized existing Workbench service.

The host owns the service, identity and extra Workbench authorization. App inputs
cannot select any of them. This module owns no execution or persistence state.
"""

from __future__ import annotations

import hashlib
import inspect
import json
from importlib.resources import files

APP_EXTENSION = "io.modelcontextprotocol/ui"
APP_URI = "ui://carbon/workbench-study-v1.html"
APP_MIME = "text/html;profile=mcp-app"
TOOL_NAME = "carbon_workbench_study_v1"
APP_META = {
    "ui": {
        "csp": {
            "connectDomains": [],
            "resourceDomains": [],
            "frameDomains": [],
            "baseUriDomains": [],
        },
        "permissions": {},
        "prefersBorder": True,
    }
}


def packaged_app():
    """Read only the installed fixed asset, verifying its build manifest."""
    directory = files("carbon.miner_mcp").joinpath("apps_ui")
    body = directory.joinpath("workbench.html").read_bytes()
    manifest = json.loads(
        directory.joinpath("manifest.json").read_text(encoding="utf-8")
    )
    if (
        not 0 < len(body) <= 1024**2
        or manifest.get("schema") != "carbon.mcp-app.workbench-build.v1"
        or manifest.get("artifact")
        != {
            "name": "workbench.html",
            "sha256": hashlib.sha256(body).hexdigest(),
            "bytes": len(body),
        }
    ):
        raise ValueError("installed Workbench App differs from its build manifest")
    return body.decode("utf-8")


def make_workbench_app_extension(
    *, adapter, workbench, authorize_workbench, guard=None
):
    """Bind an exact service plus independent operator-supplied authorization."""
    from typing import Literal

    from mcp.server.extension import Extension, ResourceBinding, ToolBinding
    from mcp.server.mcpserver.exceptions import ToolError
    from mcp.server.mcpserver.resources import FunctionResource
    from pydantic import BaseModel, ConfigDict, JsonValue, ValidationError

    from carbon.miner_mcp.standard import ResearchToolAdapter
    from carbon.scientific_tasks.workbench import WorkbenchScience

    if (
        type(adapter) is not ResearchToolAdapter
        or type(workbench) is not WorkbenchScience
        or workbench.adapter is not adapter
        or not callable(authorize_workbench)
        or (guard is not None and not callable(guard))
    ):
        raise TypeError("exact Workbench binding and separate authorization required")
    adapter._check_binding()

    class Arguments(BaseModel):
        model_config = ConfigDict(strict=True, extra="forbid")
        action: Literal["capabilities", "start", "status", "result", "cancel"]
        request: dict[str, JsonValue] | None

    async def authorize():
        if workbench.adapter is not adapter:
            raise PermissionError("Workbench binding changed")
        adapter._check_binding()
        for check in (guard, authorize_workbench):
            if check is not None:
                result = check()
                if inspect.isawaitable(result):
                    result = await result
                if result is False:
                    raise PermissionError("Workbench authorization required")

    async def call(action, request):
        await authorize()
        parsed = Arguments.model_validate({"action": action, "request": request})
        if (parsed.action == "capabilities") != (parsed.request is None):
            raise ValueError("capabilities alone requires a null request")
        if len(json.dumps(parsed.model_dump(), allow_nan=False).encode()) > 131072:
            raise ValueError("bounded study request required")
        result = (
            await workbench.capabilities()
            if parsed.action == "capabilities"
            else await workbench.call(parsed.action, parsed.request)
        )
        return {
            "action": parsed.action,
            "request": parsed.request,
            "response": result,
            "official_eligible": False,
        }

    async def study(action: str, request: dict | None):
        # Interception validates the original wire arguments before the SDK's
        # legacy object-looking-string coercion. This callable remains defensive.
        try:
            return await call(action, request)
        except (PermissionError, ValueError, TypeError):
            raise ToolError("Workbench request unavailable") from None

    study.__annotations__ = {
        "action": Arguments.model_fields["action"].annotation,
        "request": Arguments.model_fields["request"].annotation,
        "return": dict,
    }

    async def read():
        await authorize()
        # Resource access itself checks current service/grant scope; no numerical
        # task is started merely to retrieve the fixed presentation resource.
        await workbench._access(cleanup=True)
        return packaged_app()

    class WorkbenchApp(Extension):
        identifier = APP_EXTENSION

        def settings(self):
            return {"mimeTypes": [APP_MIME]}

        def tools(self):
            return (
                ToolBinding(
                    study,
                    meta={
                        "ui": {"resourceUri": APP_URI, "visibility": ["model", "app"]}
                    },
                    kwargs={
                        "name": TOOL_NAME,
                        "description": (
                            "Use the existing authorized Workbench public-source study. "
                            "Preserve exact registered draft/request and operation identity. "
                            "Capabilities requires request=null; other actions require "
                            "the unchanged Workbench v1/v2 request object. No new rights "
                            "or qualification. Results include text and structured data."
                        ),
                    },
                ),
            )

        def resources(self):
            return (
                ResourceBinding(
                    FunctionResource.from_function(
                        read,
                        APP_URI,
                        name="Carbon Workbench public study v1",
                        description="Optional view of existing draft-bound public studies",
                        mime_type=APP_MIME,
                        meta=APP_META,
                    )
                ),
            )

        async def intercept_tool_call(self, params, ctx, call_next):
            if params.name != TOOL_NAME:
                return await call_next(ctx)
            try:
                await authorize()
                parsed = Arguments.model_validate(params.arguments)
                value = await call(**parsed.model_dump())
                return {
                    "resultType": "complete",
                    "content": [
                        {"type": "text", "text": json.dumps(value, allow_nan=False)}
                    ],
                    "structuredContent": value,
                    "isError": False,
                }
            except ValidationError:
                message = (
                    "INVALID_ARGUMENTS: closed object-valued Workbench request required"
                )
            except Exception:  # noqa: BLE001
                # Never disclose service/controller internals to a client.
                message = "OPERATIONAL_STOP: Workbench request unavailable; reconcile before retry"
            return {
                "resultType": "complete",
                "content": [{"type": "text", "text": message}],
                "isError": True,
            }

    return WorkbenchApp()
