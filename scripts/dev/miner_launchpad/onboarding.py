"""The browser's door onto the shared chain-onboarding service.

One service, two front doors: this adapts
`carbon.development_session.chain_onboarding` for the loopback HTTP surface, and
the MCP extension adapts the same four functions. Neither owns the logic, and
neither gets an authority path the other lacks.

Open tier. Registration gates Carbon's research environment, so onboarding has
to work for someone who is not registered yet - that is the whole audience.
Nothing reachable here creates a campaign, consumes compute or touches the
ledger, which is the rule the tier boundary is written as rather than a list of
endpoints that would drift.

The browser never supplies a chain endpoint. `requirements` needs no chain at
all; the others read public state through the operator-configured context, so a
browser request cannot point Carbon at a network the operator did not choose.
"""

from __future__ import annotations

import asyncio

from carbon.development_session import chain_onboarding as service


class BrowserOnboarding:
    """Adapts the shared service. Holds no key and signs nothing.

    `reader` and `context` are supplied by the operator at startup, or left
    absent. Absent is a supported state rather than an error: `requirements`
    still answers, which is what an unregistered visitor needs first, and the
    reads report plainly that the operator has not configured a chain endpoint.
    """

    def __init__(self, *, reader=None, context=None):
        self.reader = reader
        self.context = context

    @property
    def chain_configured(self) -> bool:
        return self.reader is not None and self.context is not None

    def requirements(self) -> dict:
        value = service.requirements()
        value["chain_reads_available"] = self.chain_configured
        if not self.chain_configured:
            value["next_action"] = (
                "This launcher has no chain endpoint configured, so registration "
                "status cannot be read here. The requirements above still apply, "
                "and your own wallet tooling can check and register without it."
            )
        return value

    def _read(self, name: str, address: object) -> dict:
        if not self.chain_configured:
            raise service.OnboardingFailure(
                "CHAIN_NOT_CONFIGURED",
                next_action=(
                    "The operator has not configured a chain endpoint for this "
                    "launcher. Registration is unaffected: check status and "
                    "register in your own wallet tooling."
                ),
            )
        call = getattr(service, name)
        return asyncio.run(call(self.reader, self.context, address))

    def status(self, address: object) -> dict:
        return self._read("status", address)

    def prepare(self, address: object) -> dict:
        return self._read("prepare", address)

    def confirm(self, address: object) -> dict:
        return self._read("confirm", address)
