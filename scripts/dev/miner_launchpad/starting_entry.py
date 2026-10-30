"""The catalog entry a newcomer's first practice starts on, chosen by the Launchpad (display and install order only).

`listing.preferred` is the registry's ready-example entry (a CNO build) and stays as it is: the example recipe, the
admission tests and the digests depend on it. A newcomer's starting point is a separate choice: the kernel-ridge
baseline (`prior_krr`), which scored best in the agent runs on every Challenge that offers it and is eligible on all
of them, where the CNO example was the weakest and not eligible on Cooling (Launchpad Test Runner and launchpad-ux
runs, 2026-10-29). Nothing here is hidden or blocked: every entry stays in the picker, and the choice is a start,
not a ranking. A Challenge version without a baseline entry keeps the registry's own preference.

Cooling 1.6 differs: its `prior_krr` freezes to 63,026 bytes of operand wiring, over the 32 KiB accounting-v6 budget,
so it is refused at freeze and cannot be graded at launch (owner: "just change the starting model"; the budget fix
for it is after launch). Its start is the entry that freezes under the budget, holds an official GPU receipt and is
eligible in practice with the highest measured practice total: of the two with a receipt, `physicsnemo.MeshGraphNet`
(12,870 bytes; eligible, total 0.371) rather than `physicsnemo.FullyConnected` (1,413 bytes; gate-failed, no total).
Measured on the 12-entry panel of 2026-10-30; its official gradability still needs its receipt on the final
image. The choice lives in `listing.MEASURED_START`, shared with the MCP ready recipe. The other three launch versions keep `prior_krr`, which fits there.
"""

from carbon.backbone_catalog import listing

BASELINE_SUFFIX = ".prior_krr"


def starting_entry(challenge_id, version):
    """The catalog id a first practice on (challenge_id, version) starts on, or None when it offers no entry."""
    chosen = listing.measured_start(challenge_id, version)
    if chosen is not None:
        return chosen
    for item in listing.entries(challenge_id, version):
        catalog_id = item["catalog_id"]
        if catalog_id.startswith(listing.V2_PREFIX) and catalog_id.endswith(
            BASELINE_SUFFIX
        ):
            return catalog_id
    return listing.preferred(challenge_id, version)


def start_first(items):
    """`items` (manifest entries) with each Challenge's newest-version starting entry first, the rest in their order."""
    items = list(items)
    newest = {}
    for item in items:
        for each in item.get("challenges") or []:
            key = each["id"]
            if key not in newest or listing._version_key(
                each["version"]
            ) > listing._version_key(newest[key]):
                newest[key] = each["version"]
    first = []
    for challenge_id in sorted(newest):
        wanted = starting_entry(challenge_id, newest[challenge_id])
        if wanted is not None and wanted not in first:
            first.append(wanted)
    rank = {catalog_id: index for index, catalog_id in enumerate(first)}
    return sorted(items, key=lambda item: rank.get(item["catalog_id"], len(first)))
