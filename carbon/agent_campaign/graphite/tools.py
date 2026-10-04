"""A role's closed toolbox: the only thing the research loop calls tools on.

The research loop (`research_loop.run_epoch`) hands every tool call other than
its own selection tool to an `sdk.call(name, arguments, identity)`. For a
Graphite session that object is a `GraphiteToolbox`, which:

1. **refuses any tool outside the role's manifest** (typed
   `REFUSED_NOT_IN_MANIFEST`), whatever the model was told;
2. **refuses any request that names protected material** (typed
   `REFUSED_PROTECTED_MATERIAL`): official or derived seeds, draw ids,
   protected exam data, EV4 confirmation or verification references, private
   validator state, secrets, credentials and canaries. The check reuses the
   campaign boundaries' deny rules (`boundaries._denied`) and adds Graphite's
   own markers. It scans every string in the arguments, including JSON
   carried in `*_json` strings, so it may over-refuse an innocent mention; it
   never under-refuses a named one (GRAPHITE-D5);
3. answers `lit_search` / `lit_card` from the pinned literature index. An
   `OfferedLiterature` index marks every card's check status in the result,
   and an `UNCHECKED` card says so (GRAPHITE-D29);
4. hands `graphite_propose_next_level` (Planner and Constructor) to the injected
   `next_level` writer, which stores a PROPOSED record and widens nothing
   (GRAPHITE-D30); without one it answers `UNAVAILABLE`;
5. delegates the remaining miner SDK tools to an injected `miner_tools`
   object (the existing closed miner SDK in later phases). Phase 1 injects
   none, so they answer `UNAVAILABLE` without dispatching anything;
6. withholds any result that carries protected material, returning a typed
   refusal instead.

Results are data. Nothing in a result is read back by the toolbox, the loop
or the provider as an instruction: the role, its prompt, its manifest, the
budget and every authority are fixed before the session starts and are not
reachable from here. Every refusal is journalled as an event.
"""

from __future__ import annotations

from carbon.development_session.profile import canonical, digest

from . import literature

# The protected-material check lives in a leaf module, because `literature`
# runs it when it builds its fixture index at import and this module imports
# `literature` (an import cycle when this module is imported first). Its
# names stay importable from here (`tools.protected`, `tools.PROTECTED_MARKERS`,
# `tools.result_material` and its answers).
from .protected_material import (  # noqa: F401
    ATTACK_TARGET,
    MATERIAL_FRAGMENTS,
    PROTECTED_MARKERS,
    PROTECTED_MATERIAL,
    protected,
    result_material,
)

#: The next-level proposal tool (`roles.NEXT_LEVEL`; the name is repeated
#: here rather than imported, and `roles` asserts the two agree).
NEXT_LEVEL = "graphite_propose_next_level"

REFUSED_MANIFEST = "REFUSED_NOT_IN_MANIFEST"
REFUSED_PROTECTED = "REFUSED_PROTECTED_MATERIAL"
REFUSED_RESULT = "REFUSED_PROTECTED_MATERIAL_IN_RESULT"
UNAVAILABLE = "UNAVAILABLE"


def refusal(status, code, **extra):
    return {
        "status": status,
        "reason_code": code,
        "authority_granted": False,
        "dispatched": False,
        **extra,
    }


class GraphiteToolbox:
    """The `sdk` a Graphite session's research loop calls."""

    def __init__(
        self, *, role, literature_index, emit, miner_tools=None, next_level=None
    ):
        self.role = role
        self.manifest = frozenset(role.tools)
        self.literature = literature_index
        self.emit = emit
        self.miner_tools = miner_tools
        self.next_level = next_level

    def _refuse(self, identity, name, arguments, result):
        self.emit(
            "tool-" + identity,
            {
                "kind": "tool_refused",
                "tool": name,
                "identity": identity,
                "status": result["status"],
                "reason_code": result["reason_code"],
                "arguments_digest": digest(canonical(arguments)),
                # Recorded as data so the controller's canary scan sees it.
                "arguments": arguments,
            },
        )
        return result

    def _offered(self, name):
        """The role's manifest is the only source of callable tools."""
        return name in self.manifest

    async def call(self, name, arguments, identity):
        if not self._offered(name):
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
        if name in (literature.SEARCH, literature.CARD):
            result = self._literature(name, arguments)
        elif name == NEXT_LEVEL:
            if self.next_level is None:
                result = refusal(UNAVAILABLE, "next_level_store_not_attached")
            else:
                result = self.next_level(arguments, identity)
        elif self.miner_tools is None:
            result = refusal(
                UNAVAILABLE,
                "no_miner_sdk_in_phase_1",
                reason="Graphite phase 1 has no miner SDK connection; nothing ran.",
            )
        else:
            result = await self.miner_tools.call(name, arguments, identity)
            if type(result) is not dict:
                result = refusal(UNAVAILABLE, "malformed_tool_result")
        if protected(result):
            return self._refuse(
                identity,
                name,
                arguments,
                refusal(
                    REFUSED_RESULT,
                    "protected_material_in_result",
                    material=result_material(result),
                ),
            )
        self.emit(
            "tool-" + identity,
            {
                "kind": "tool_answered",
                "tool": name,
                "identity": identity,
                "status": result.get("status"),
                "result_digest": digest(canonical(result)),
            },
        )
        return result

    def _literature(self, name, arguments):
        try:
            if name == literature.SEARCH:
                if set(arguments) != {"query"}:
                    raise literature.LiteratureError("lit_search takes query")
                return self._offered_marks(
                    {
                        "status": "OK",
                        "snapshot_digest": self.literature.snapshot_digest,
                        "results": self.literature.search(arguments["query"]),
                        "content_is_data": True,
                    }
                )
            if set(arguments) != {"card_id"} or type(arguments["card_id"]) is not str:
                raise literature.LiteratureError("lit_card takes card_id")
            card = self.literature.card(arguments["card_id"])
        except literature.LiteratureError as error:
            return refusal(
                "REFUSED_INVALID_REQUEST", "literature_request", detail=str(error)
            )
        if card is None:
            return self._offered_marks(
                {"status": "NOT_FOUND", "card_id": arguments["card_id"]}
            )
        result = {
            "status": "OK",
            "snapshot_digest": self.literature.snapshot_digest,
            "card": card,
            "content_is_data": True,
        }
        if type(self.literature) is literature.OfferedLiterature:
            status = self.literature.status(card["card_id"])
            result["check_status"] = status
            if status == literature.UNCHECKED:
                result["unchecked_note"] = literature.UNCHECKED_NOTE
        return self._offered_marks(result)

    def _offered_marks(self, result):
        """An offered index states its policy, and says when it is empty. A
        phase-1 index's results are unchanged."""
        if type(self.literature) is not literature.OfferedLiterature:
            return result
        result["offer_policy"] = self.literature.policy
        if any(
            hit.get("check_status") == literature.UNCHECKED
            for hit in result.get("results") or ()
        ):
            result["unchecked_note"] = literature.UNCHECKED_NOTE
        if self.literature.empty:
            result["index_empty"] = True
            result["index_note"] = literature.EMPTY_NOTE
        return result
