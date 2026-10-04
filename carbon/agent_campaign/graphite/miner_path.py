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
(its `ChallengeScoring`'s id and version; battery today): no other Challenge,
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
            return {
                "status": "MINER_PATH_REFUSED",
                "reason_code": failure.code.value,
                "dispatch_may_have_occurred": failure.dispatch_may_have_occurred,
                # The loop stops on this rather than risk a second dispatch.
                "requires_reconciliation": bool(failure.dispatch_may_have_occurred),
                "authority_granted": False,
            }
        payload = dict(result.payload)
        if result.requires_reconciliation:
            payload["requires_reconciliation"] = True
        return payload


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
