"""The MCP door onto the shared chain-onboarding service.

The second of two front doors. The browser adapter and this one wrap the same
four functions in `carbon.development_session.chain_onboarding`; neither owns the
logic and neither gets an authority path the other lacks.

Open tier, and that is what makes these tools different in kind from the research
tools beside them. Every other tool on this server routes through
`ResearchToolAdapter`, which requires a bound campaign, a principal and a grant.
Onboarding cannot: it exists for a miner who has none of those, and gating it
behind a campaign would mean the registration flow was only reachable by someone
who no longer needs it.

So these are built like `make_skills_extension` - no adapter, no campaign, no
ledger. Nothing reachable here creates a campaign, consumes compute or touches
the ledger, which is the rule the tier boundary is written as.

**Carbon never holds, transmits, stores, logs or requests a private key, seed
phrase or mnemonic.** No tool here signs, and none accepts key material. The
per-call record is `chain_onboarding.call_record`, which takes a validated
`PublicAddress` rather than a string, so an unvalidated value cannot be recorded
at all - the log cannot capture what it is never given.
"""

from __future__ import annotations

from typing import Annotated

from carbon.development_session import chain_onboarding as service

PREFIX = "carbon_onboarding_"

#: Reported outcomes. Closed, so a record cannot carry a free-text description
#: of what a caller supplied.
OUTCOMES = frozenset({"REGISTERED", "NOT_REGISTERED", "PREPARED", "REFUSED"})


def _outcome(operation: str, value: dict) -> str:
    if operation == "requirements":
        return "PREPARED"
    if operation == "prepare":
        return "PREPARED"
    return "REGISTERED" if value.get("registered") else "NOT_REGISTERED"


def onboarding_records(reader, context, sink=None):
    """Wrap the shared service so every call emits a safe record.

    Calls the async service functions directly rather than reusing the browser
    adapter. That adapter wraps them in `asyncio.run` for a synchronous HTTP
    handler, which cannot be reused inside an already-running loop - so sharing
    the *service* is right and sharing the *adapter* is not. Each door adapts
    the same four functions to its own execution model.

    `sink` receives the record. It is injected rather than assumed so this
    module never decides where records go - a logging surface, a test, or
    nowhere at all if the caller passes nothing.

    The record is built from the *validated* address, never from the caller's
    argument. An unvalidated value is not merely redacted on its way into a
    record, it is structurally unable to reach one, because `call_record`
    requires a `PublicAddress` and only validation produces those.
    """

    def emit(record):
        if sink is not None:
            sink(record)

    async def run(operation: str, address: object = None) -> dict:
        if operation == "requirements":
            value = service.requirements()
            value["chain_reads_available"] = reader is not None and context is not None
            emit(service.call_record(operation, address=None, outcome="PREPARED"))
            return value
        if reader is None or context is None:
            emit(service.call_record(operation, address=None, outcome="REFUSED"))
            raise service.OnboardingFailure(
                "CHAIN_NOT_CONFIGURED",
                next_action=(
                    "This server has no chain endpoint configured. Registration "
                    "is unaffected: check status and register in your own wallet "
                    "tooling."
                ),
            )
        try:
            value = await getattr(service, operation)(reader, context, address)
        except service.OnboardingFailure:
            # A refusal records its reason code and no input at all. There is
            # nothing about the input worth keeping and something about it
            # worth never keeping.
            emit(service.call_record(operation, address=None, outcome="REFUSED"))
            raise
        validated = service.PublicAddress(value["hotkey"])
        emit(
            service.call_record(
                operation, address=validated, outcome=_outcome(operation, value)
            )
        )
        return value

    return run


def make_onboarding_tools(*, reader=None, context=None, guard=None, sink=None):
    """Four tools over the shared service, with no adapter and no campaign."""
    from mcp.server.mcpserver.exceptions import ToolError
    from mcp.server.mcpserver.tools import Tool
    from mcp.server.mcpserver.utilities.func_metadata import ArgModelBase, FuncMetadata
    from pydantic import BaseModel, ConfigDict, Field, JsonValue, create_model

    class StrictArguments(ArgModelBase):
        model_config = ConfigDict(strict=True, extra="forbid")

    class ExactMetadata(FuncMetadata):
        def pre_parse_json(self, data):
            return data

    class OnboardingResult(BaseModel):
        model_config = ConfigDict(strict=True, extra="forbid")
        operation: str
        payload: dict[str, JsonValue]
        official_eligible: bool = False

    # Same default as the browser door, for the same reason: the chain Carbon
    # runs on is settled, and both doors must describe the same one.
    if context is None:
        context = service.carbon_testnet_context()
    if reader is None:
        from carbon.chain.sdk import BittensorReader

        reader = BittensorReader()
    run = onboarding_records(reader, context, sink=sink)

    # Bounded before it reaches anything: an ss58 address is 46-50 characters,
    # so a pasted recovery phrase is refused by length at the wire before the
    # service sees it, and by shape if it somehow fits.
    address_field = Annotated[str, Field(min_length=46, max_length=50)]

    def tool_for(operation: str, description: str, needs_address: bool):
        parameters = {"address": (address_field, ...)} if needs_address else {}
        model = create_model(
            "onboarding_" + operation, __base__=StrictArguments, **parameters
        )

        async def invoke(**arguments):
            if guard is not None:
                guard()
            try:
                payload = await run(operation, arguments.get("address"))
            except service.OnboardingFailure as failure:
                # Actionable and closed: a reason a client can branch on and the
                # next usable step. Never a provider message, never a trace, and
                # never the argument it was given.
                raise ToolError(
                    f"{failure.reason}; next_action={failure.next_action}"
                ) from None
            return OnboardingResult(operation=operation, payload=payload)

        return Tool(
            fn=invoke,
            name=PREFIX + operation,
            description=description,
            parameters=model.model_json_schema(),
            fn_metadata=ExactMetadata(arg_model=model, output_model=OnboardingResult),
            is_async=True,
        )

    return [
        tool_for(
            "requirements",
            "What registering on the Carbon subnet involves. Needs no chain, no "
            "campaign and no registration. Carbon never accepts a key or phrase.",
            False,
        ),
        tool_for(
            "status",
            "Whether an ss58 address is registered on the subnet, and its UID. "
            "Read-only on public chain state.",
            True,
        ),
        tool_for(
            "prepare",
            "A validated, fully described, UNSIGNED registration to execute in "
            "your own wallet tooling. Carbon does not sign and does not submit.",
            True,
        ),
        tool_for(
            "confirm",
            "Re-query after you have executed the registration, and report the "
            "identity that resulted.",
            True,
        ),
    ]
