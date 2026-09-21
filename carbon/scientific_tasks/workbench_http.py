"""Bounded same-origin routes for an operator's existing private Workbench host.

This factory creates no listener, authorization server, user session or grant.
The host must explicitly supply its authenticated-principal resolver. It must
retain controller ownership and worker reconciliation across HTTP disconnects.
"""

from __future__ import annotations

import inspect
import json
from urllib.parse import urlsplit

from carbon.miner_mcp.standard import AdapterFailure
from carbon.scientific_tasks.workbench import WorkbenchScience

MAX_BYTES = 131072


def _decode(raw):
    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError("duplicate field")
            value[key] = item
        return value

    def finite(_value):
        raise ValueError("nonfinite JSON")

    value = json.loads(raw, object_pairs_hook=unique, parse_constant=finite)
    if type(value) is not dict:
        raise ValueError("object request required")
    return value


def check_private_origin(request, *, allowed_origin, netloc, expected_method):
    """Shared same-origin guard for a private host's own bounded routes.

    Returns a fixed error code, or None when the request may proceed. It grants
    nothing: the caller still owns authentication and every scientific check.
    """
    if request.method != expected_method or request.url.query:
        return "METHOD_OR_PATH_DENIED"
    # Reject duplicate routing/security headers rather than accept whichever
    # a proxy or application happened to choose. No forwarded-host override.
    if request.headers.getlist("host") != [netloc]:
        return "ORIGIN_DENIED"
    incoming = request.headers.getlist("origin")
    if (expected_method == "POST" and incoming != [allowed_origin]) or (
        expected_method == "GET" and incoming not in ([], [allowed_origin])
    ):
        return "ORIGIN_DENIED"
    if request.headers.get("sec-fetch-site") not in (None, "same-origin", "none"):
        return "ORIGIN_DENIED"
    return None


def create_workbench_app(service, *, authorize, allowed_origin):
    """Mount only after operator review; authorize(request) returns one principal.

    The resolver may be async. Caller-supplied principal, headers or rights fields
    are never trusted here; the resolver owns actual session authentication.
    """
    from starlette.applications import Starlette
    from starlette.requests import Request
    from starlette.responses import JSONResponse, Response
    from starlette.routing import Route

    if type(service) is not WorkbenchScience or not callable(authorize):
        raise ValueError("exact service and explicit operator authentication required")
    if type(allowed_origin) is not str:
        raise ValueError("explicit private service origin required")
    origin = urlsplit(allowed_origin)
    if (
        not origin.hostname
        or origin.username is not None
        or origin.password is not None
        or origin.path
        or origin.query
        or origin.fragment
        or origin.scheme not in {"http", "https"}
        or (
            origin.scheme == "http"
            and origin.hostname not in {"localhost", "127.0.0.1", "::1"}
        )
        or allowed_origin != origin.geturl()
    ):
        raise ValueError("exact HTTPS or loopback origin required")
    headers = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}

    def failed(status, code):
        return JSONResponse({"error": code}, status_code=status, headers=headers)

    async def endpoint(request: Request):
        action = request.url.path.rsplit("/", 1)[-1]
        expected_method = "GET" if action == "capabilities" else "POST"
        denied = check_private_origin(
            request,
            allowed_origin=allowed_origin,
            netloc=origin.netloc,
            expected_method=expected_method,
        )
        if denied is not None:
            return failed(405 if denied == "METHOD_OR_PATH_DENIED" else 403, denied)
        try:
            principal = authorize(request)
            if inspect.isawaitable(principal):
                principal = await principal
        except Exception:  # noqa: BLE001
            return failed(401, "AUTHENTICATION_REQUIRED")
        if type(principal) is not str or principal != service.adapter.principal:
            return failed(403, "PRINCIPAL_DENIED")
        try:
            if action == "capabilities":
                result = await service.capabilities()
            else:
                if request.headers.getlist("content-type") != ["application/json"]:
                    return failed(415, "JSON_REQUIRED")
                raw = bytearray()
                async for chunk in request.stream():
                    raw.extend(chunk)
                    if len(raw) > MAX_BYTES:
                        return failed(413, "REQUEST_LIMIT")
                result = await service.call(action, _decode(bytes(raw)))
            body = json.dumps(result, separators=(",", ":"), allow_nan=False).encode()
            if len(body) > MAX_BYTES:
                return failed(500, "RESULT_LIMIT")
            return Response(body, media_type="application/json", headers=headers)
        except PermissionError:
            return failed(403, "DRAFT_BINDING_DENIED")
        except AdapterFailure as error:
            return failed(
                409 if error.dispatch_may_have_occurred else 400,
                "RESEARCH_OPERATION_UNAVAILABLE",
            )
        except (ValueError, TypeError, KeyError, UnicodeError, RecursionError):
            return failed(400, "STUDY_REQUEST_REJECTED")
        except Exception:  # noqa: BLE001
            return failed(500, "STUDY_SERVICE_UNAVAILABLE")

    prefix = "/api/scientific-studies/"
    app = Starlette(
        routes=[
            Route(prefix + "capabilities", endpoint, methods=["GET"]),
            *(
                Route(prefix + action, endpoint, methods=["POST"])
                for action in ("start", "status", "cancel", "result")
            ),
        ]
    )
    app.router.redirect_slashes = False
    return app
