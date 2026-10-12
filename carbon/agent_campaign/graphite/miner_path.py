"""The real miner path for a Graphite session (GRAPHITE-01 phase 3).

Phase 1 left the Constructor's miner tools unconnected: they answered
`UNAVAILABLE`. Phase 3 connects them to the same door every external research
agent uses: Carbon's standard miner MCP attachment
(`carbon.miner_mcp.standard_cli.attached_profile`). It holds the miner
campaign's ownership lock, checks the registered owner, composes the
Challenge's research service and yields a `ResearchToolAdapter` over the
closed miner SDK (`research_tools.ResearchMinerTools`). Graphite then calls the
adapter's public `call`, exactly as an MCP client does: signing, admission,
accounting, owner binding and typed failures are the miner path's own.

`MinerPathTools` only translates the loop's raw tool calls into the adapter's
request shape:

- the tool name drops the SDK prefix;
- `strategy_json` and `arguments_json` (JSON text) become the `strategy` and
  `arguments` objects the adapter takes back to text;
- each call's operation id is the session's own (`graphite-<run>-<tool>`), so
  two sessions in one miner campaign never share an id.

A request the adapter refuses comes back as a typed result with no authority.
A failure after which the request may have been dispatched sets
`requires_reconciliation`, so the research loop stops rather than resend.

Phase 3 attaches only to a DEVELOPMENT campaign for the session's Challenge
(its `ChallengeScoring`'s id and version): no other Challenge,
and nothing official.
"""

from __future__ import annotations

import contextlib
import json

from carbon.development_session.research_tools import PREFIX

TRANSLATED = {"strategy_json": "strategy", "arguments_json": "arguments"}


class MinerPathRefused(ValueError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _readable(arguments):
    out = {}
    for key, value in arguments.items():
        if key in TRANSLATED:
            if value is None:
                out[TRANSLATED[key]] = None
                continue
            if type(value) is not str:
                raise MinerPathRefused("json_string_required:" + key)
            try:
                out[TRANSLATED[key]] = json.loads(value)
            except ValueError:
                raise MinerPathRefused("json_invalid:" + key) from None
        else:
            out[key] = value
    return out


class MinerPathTools:
    """The Constructor's miner tools over a `ResearchToolAdapter`."""

    def __init__(self, adapter, *, session):
        if type(session) is not str or not session.isascii() or not session:
            raise ValueError("a session label is required")
        self.adapter, self.session = adapter, session

    def operation_id(self, identity):
        return f"graphite-{self.session}-{identity}"[:114]

    async def call(self, name, arguments, identity):
        from carbon.miner_mcp.standard import AdapterFailure, ResearchToolRequest

        if type(name) is not str or not name.startswith(PREFIX):
            return _refused("not_a_miner_tool")
        if type(arguments) is not dict:
            return _refused("arguments_not_an_object")
        try:
            readable = _readable(arguments)
        except MinerPathRefused as refused:
            return _refused(refused.code)
        request = ResearchToolRequest(
            name.removeprefix(PREFIX), self.operation_id(identity), readable
        )
        try:
            result = await self.adapter.call(request)
        except AdapterFailure as failure:
            refused = {
                "status": "MINER_PATH_REFUSED",
                "reason_code": failure.code.value,
                "dispatch_may_have_occurred": failure.dispatch_may_have_occurred,
                # The loop stops on this rather than risk a second dispatch.
                "requires_reconciliation": bool(failure.dispatch_may_have_occurred),
                "authority_granted": False,
            }
            # The door's registered correction, when it gave one: its code,
            # the field and how to fix it (RESEARCH-TOOL-USABILITY-01).
            if failure.correction is not None:
                refused.update(failure.correction)
            return refused
        payload = dict(result.payload)
        if result.requires_reconciliation:
            payload["requires_reconciliation"] = True
        return payload


#: The bytes one `read_file` returns under the v2 research tools rule
#: (`research_tasks.READ_FILE_MAX_BYTES`); a smaller answer ends the file.
READ_CHUNK = 8192


def _read_answer(payload):
    """`(chunk bytes, file bytes)` from a `read_file` answer, wherever the
    door nests its result, or None when the answer carries no content."""
    import base64

    if not isinstance(payload, dict):
        return None
    if "content_base64" in payload or "content_utf8" in payload:
        if payload.get("content_base64") is not None:
            body = base64.b64decode(payload["content_base64"], validate=True)
        elif payload.get("content_utf8") is not None:
            body = payload["content_utf8"].encode()
        else:
            return None
        total = payload.get("bytes")
        return body, total if type(total) is int else None
    for value in payload.values():
        found = _read_answer(value)
        if found is not None:
            return found
    return None


async def read_export(tools, task_id, name, identity, *, max_bytes):
    """The bytes of `name`, exported by the agent's finished workspace run
    `task_id` (`<last 20 characters of the task id>-<name>`), read through the
    miner's own door with `read_file`, exactly as an MCP client reads it
    (GRAPHITE-L4-STAGING-01). Returns bytes, or the door's typed answer (a
    dict) when a read is refused; a file over `max_bytes` is refused here."""
    if type(task_id) is not str or not task_id or len(task_id) < 20:
        return _refused("level4_task_id_required")
    export = task_id[-20:] + "-" + name
    out, offset, k = bytearray(), 0, 0
    while True:
        answer = await tools.call(
            PREFIX + "start_research_task",
            {
                "kind": "workspace",
                "strategy_json": None,
                "action": "read_file",
                "arguments_json": json.dumps(
                    {"name": export, "offset": offset, "count": READ_CHUNK}
                ),
                "hypothesis": "read the Level 4 envelope my lowering run exported",
                "expected_effect": "Carbon stages the submission",
            },
            f"{identity}-l4read-{k}",
        )
        found = _read_answer(answer)
        if found is None:
            return answer if isinstance(answer, dict) else _refused("read_failed")
        chunk, total = found
        out += chunk
        offset += len(chunk)
        k += 1
        if total is not None and total > max_bytes:
            return _refused("level4_envelope_over_bound")
        if len(out) > max_bytes:
            return _refused("level4_envelope_over_bound")
        if (
            not chunk
            or (total is not None and offset >= total)
            or len(chunk) < READ_CHUNK
        ):
            return bytes(out)


def _refused(code):
    return {
        "status": "REJECTED_BEFORE_DISPATCH",
        "reason_code": code,
        "dispatched": False,
        "authority_granted": False,
    }


def check_challenge(manifest, scoring=None):
    """The attached miner campaign must be the session's DEVELOPMENT Challenge
    (its `ChallengeScoring`; the only registered one unless named)."""
    from carbon.challenge_validator import scoring as challenge_scoring

    try:
        scoring = challenge_scoring.resolve(scoring)
    except challenge_scoring.ScoringUnavailable as refused:
        raise MinerPathRefused(refused.code) from None
    challenge = (manifest or {}).get("challenge") or {}
    named = {"id": challenge.get("id"), "version": challenge.get("version")}
    if not scoring.check_challenge(named):
        raise MinerPathRefused("miner_campaign_is_not_the_sessions_challenge")
    return challenge


@contextlib.asynccontextmanager
async def attach(configuration, campaign, *, session, scoring=None):
    """Attach to a miner's campaign for the session's Challenge through the
    standard miner door; yields `MinerPathTools`. The lock is held for the
    whole session."""
    from pathlib import Path

    from carbon.miner_mcp.standard_cli import attached_profile, load_profile

    profile = load_profile(Path(configuration), campaign)
    check_challenge(profile.manifest, scoring)
    async with attached_profile(profile) as (adapter, _profile):
        yield MinerPathTools(adapter, session=session)
