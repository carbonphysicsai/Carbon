"""A miner-edition role's closed toolbox: the `sdk` its research loop calls.

The research loop runs its own local tools (a selection, a stop, the
Planner's `graphite_record_plan`, a reply to the miner) and hands every other
call to `MinerToolbox.call(name, arguments, identity)`, which:

1. **refuses any tool outside the role's manifest** (`REFUSED_NOT_IN_MANIFEST`),
   whatever the model was told - including the internal edition's proposal
   runner and next-level store, which no miner role holds;
2. **refuses a request that names protected material**
   (`REFUSED_PROTECTED_MATERIAL`), with the internal edition's own check
   (`..tools.protected`): official or derived seeds, draw ids, hidden-test
   cases, verification references, private validator state, secrets and
   canaries. It scans every string, including JSON inside `*_json` strings;
3. **holds each stage to its workspace allowlist**: the Planner starts the
   workspace actions its role lists and never a practice; the Constructor
   starts its own list and practises;
4. answers `lit_search` and `lit_card` from the campaign's frozen literature
   (`library.MinerLiterature`) as data, keeping every card's origin and
   UNCHECKED status, and never serves a banned card;
5. hands the remaining research tools to the campaign's own research SDK
   (`research_tools.ResearchMinerTools`), which meters and journals them
   against the miner's ledger;
6. withholds any result that carries protected material
   (`REFUSED_PROTECTED_MATERIAL_IN_RESULT`).

Every refusal dispatches nothing and is noted in the campaign ledger. Results
are data: nothing a result says changes the role, its manifest, the limits or
any authority, which are fixed before the stage starts.
"""

from __future__ import annotations

import json

from carbon.development_session.profile import canonical, digest

from . import edition as editions

REFUSED_MANIFEST = "REFUSED_NOT_IN_MANIFEST"
REFUSED_PROTECTED = "REFUSED_PROTECTED_MATERIAL"
REFUSED_RESULT = "REFUSED_PROTECTED_MATERIAL_IN_RESULT"
REFUSED_STAGE = "REFUSED_NOT_IN_STAGE"
REFUSED_LITERATURE = "REFUSED_LITERATURE_REQUEST"


def protected(value):
    """True when any string in `value` names protected material (the
    internal edition's own check, shared so the two can never differ)."""
    from ..tools import protected as check

    return check(value)


def refusal(status, code, **extra):
    return {
        "status": status,
        "reason_code": code,
        "authority_granted": False,
        "dispatched": False,
        **extra,
    }


def stage_tools(role, schemas, *, guidance=True):
    """The function schemas a stage offers, in the role's manifest order.

    `schemas` are the research SDK's schemas for this campaign
    (`research_tools.tools_for_sdk`, under the campaign's frozen tools rule).
    The research task tool's `kind` and `action` choices are narrowed to what
    the role may start. The reply tool is offered only when the campaign froze
    a miner-guidance rule (`guidance`)."""
    from carbon.development_session.miner_guidance import REPLY_TOOL
    from carbon.development_session.research_agent_policy import STOP_TOOL
    from carbon.development_session.research_loop import SELECTION_TOOL

    local = {
        editions.SELECT: SELECTION_TOOL,
        editions.STOP: STOP_TOOL,
        editions.REPLY: REPLY_TOOL,
        editions.FINISH: editions.FINISH_TOOL,
        **{tool["name"]: tool for tool in editions.LITERATURE_TOOLS},
    }
    research = {tool["name"]: tool for tool in schemas}
    offered = []
    for name in role.tools:
        if name == editions.REPLY and not guidance:
            continue
        if name in research:
            tool = json.loads(canonical(research[name]))
            if name == editions.START_TASK:
                parameters = tool["parameters"]["properties"]
                parameters["kind"]["enum"] = (
                    ["practice", "workspace"] if role.practice else ["workspace"]
                )
                actions = parameters["action"]["enum"]
                parameters["action"]["enum"] = [
                    action
                    for action in actions
                    if action is None or action in role.workspace_actions
                ]
            offered.append(tool)
        elif name in local:
            offered.append(json.loads(canonical(local[name])))
    return offered


class MinerToolbox:
    """The `sdk` one miner-edition stage's research loop calls."""

    def __init__(self, *, role, sdk, literature, ledger, owner, stage, bans=()):
        self.role = role
        self.manifest = frozenset(role.tools)
        self.sdk = sdk
        self.literature = literature
        self.ledger = ledger
        self.owner = owner
        self.stage = stage
        self.bans = frozenset(bans)

    # The research SDK's own attributes, which the loop's tool discovery
    # reads (`research_tools.tools_for_sdk`), pass through unchanged.
    @property
    def composition(self):
        return getattr(self.sdk, "composition", None)

    def _refuse(self, identity, name, arguments, result):
        self.ledger.note(
            owner=self.owner,
            kind="refusal",
            body={
                "graphite_stage": self.stage,
                "tool": name if type(name) is str else None,
                "identity": identity,
                "status": result["status"],
                "reason_code": result["reason_code"],
                "arguments_digest": digest(canonical(arguments)),
            },
        )
        return result

    def _stage_refusal(self, name, arguments):
        """A research task outside this stage's allowlist, or None."""
        if name != editions.START_TASK or type(arguments) is not dict:
            return None
        kind = arguments.get("kind")
        if kind == "practice" and not self.role.practice:
            return refusal(
                REFUSED_STAGE,
                "practice_not_in_stage",
                reason=(
                    f"the {self.role.name} does not practise; the Constructor "
                    "practises in the build stage"
                ),
            )
        action = arguments.get("action")
        if (
            kind == "workspace"
            and type(action) is str
            and action not in self.role.workspace_actions
        ):
            return refusal(
                REFUSED_STAGE,
                "workspace_action_not_in_stage",
                reason=f"the {self.role.name} does not start {action[:64]}",
                offered=list(self.role.workspace_actions),
            )
        return None

    async def call(self, name, arguments, identity):
        if name not in self.manifest:
            return self._refuse(
                identity,
                name,
                arguments,
                refusal(REFUSED_MANIFEST, "tool_not_in_role_manifest"),
            )
        if protected(arguments):
            return self._refuse(
                identity,
                name,
                arguments,
                refusal(REFUSED_PROTECTED, "protected_material_requested"),
            )
        refused = self._stage_refusal(name, arguments)
        if refused is not None:
            return self._refuse(identity, name, arguments, refused)
        if name in (editions.LIT_SEARCH, editions.LIT_CARD):
            result = self._literature(name, arguments)
        else:
            result = await self.sdk.call(name, arguments, identity)
            if type(result) is not dict:
                result = refusal("UNAVAILABLE", "malformed_tool_result")
        if protected(result):
            return self._refuse(
                identity,
                name,
                arguments,
                refusal(REFUSED_RESULT, "protected_material_in_result"),
            )
        return result

    def _literature(self, name, arguments):
        if name == editions.LIT_CARD:
            if set(arguments) != {"card_id"} or type(arguments["card_id"]) is not str:
                return refusal(REFUSED_LITERATURE, "lit_card_takes_card_id")
            if arguments["card_id"] in self.bans:
                return refusal(
                    REFUSED_LITERATURE,
                    "card_banned",
                    card_id=arguments["card_id"],
                    reason="the miner banned this card; it is never served",
                )
        elif set(arguments) != {"query"} or type(arguments["query"]) is not str:
            return refusal(REFUSED_LITERATURE, "lit_search_takes_query")
        try:
            if name == editions.LIT_SEARCH:
                result = self.literature.lit_search(arguments)
            else:
                result = self.literature.lit_card(arguments)
        except (ValueError, KeyError, LookupError, TypeError):
            return refusal(REFUSED_LITERATURE, "literature_request_refused")
        if type(result) is not dict:
            return refusal("UNAVAILABLE", "malformed_literature_result")
        return self._without_bans(result)

    def _without_bans(self, result):
        """Defence in depth over the literature's own ban filter: a banned
        card is dropped from a search and never returned by id."""
        result = json.loads(canonical(result))
        hits = result.get("results")
        if type(hits) is list:
            result["results"] = [
                hit
                for hit in hits
                if not (type(hit) is dict and hit.get("card_id") in self.bans)
            ]
        card = result.get("card")
        if type(card) is dict and card.get("card_id") in self.bans:
            return refusal(
                REFUSED_LITERATURE,
                "card_banned",
                card_id=card.get("card_id"),
                reason="the miner banned this card; it is never served",
            )
        result.setdefault("content_is_data", True)
        return result
