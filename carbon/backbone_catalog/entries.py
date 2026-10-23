"""The backbone catalog's refusal codes.

Every served catalog setting is checked by its entry's pinned build's own
vocabulary (`settings`), with no size cap of its own (owner, 2026-10-21: no
model-size caps; the rebuild's resource limits bind). The unversioned table of
bounded settings that once lived here (hidden_channels <= 256, n_layers <= 8,
layer_size <= 1024, ...) and the in-process torch loop that read it reached no
served route; both were retired (Validator, 2026-10-21).
"""

from __future__ import annotations

#: Refusal codes (each sent to the Validator for its GAP/REFUSED class).
REFUSAL_CODES = (
    "catalog_entry_unknown",
    "catalog_setting_unknown",
    "catalog_setting_invalid",
    "catalog_settings_inconsistent",
    "catalog_library_not_pinned",
    "catalog_runtime_not_reproducible",
)


class CatalogRefused(ValueError):
    """A catalog selection refused before anything is built or charged."""

    def __init__(self, code, detail):
        if code not in REFUSAL_CODES:
            raise ValueError("unregistered catalog refusal code")
        super().__init__(f"{code}: {detail}")
        self.code, self.detail = code, detail
