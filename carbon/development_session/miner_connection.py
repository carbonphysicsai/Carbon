"""A product campaign's connection to the in-process research service.

One place for what every Challenge's campaign did in its own copy: read the
miner's network binding and public hotkey, check the hotkey is the one the
campaign was admitted with, reach the miner's signer, and connect. A
practice-only campaign (LP practice-only) connects with the install's
practice identity instead: no network binding, no public hotkey, no signer,
no chain read (`service.PracticeMinerConnection`).
"""

from __future__ import annotations

import json
from pathlib import Path

from carbon.chain.models import CARBON_NETUID

#: The refusal for a practice-only campaign continued under a registered
#: profile: it stays readable, and its practice identity is not the hotkey.
PRACTICE_CAMPAIGN_READ_ONLY = "practice_campaign_read_only"


class PracticeCampaignReadOnly(ValueError):
    code = PRACTICE_CAMPAIGN_READ_ONLY

    def __init__(self):
        super().__init__("a practice-only campaign takes no registered work")


def campaign_connection(args, root: Path, *, frozen, product):
    """(connection, signing key, network binding) for the campaign at `root`.

    `frozen` is its manifest once frozen, else None and `product` is the
    launch admitting it. The binding is None for a practice-only campaign,
    which has no network."""
    from carbon.development_session.practice_identity import (
        PRACTICE_ONLY,
        is_practice_admission,
        load,
    )

    session = Path(root) / "research-auth"
    session.mkdir(mode=0o700, exist_ok=True)
    admitted = frozen["admission"] if frozen is not None else product.miner.record()
    practice_key = getattr(args, "practice_identity", None)
    if practice_key is not None:
        from carbon.development_session.service import practice_connection

        signer = load(Path(practice_key))
        if (
            admitted.get("admission") != PRACTICE_ONLY
            or admitted.get("identity") != signer.public_key.hex()
        ):
            raise ValueError("the practice identity differs from this campaign's")
        return practice_connection(session, args.image_manifest, signer), signer, None
    if is_practice_admission(frozen):
        # Registered since: the practice campaign stays readable, but its
        # practice identity is not this hotkey (launch a new campaign).
        raise PracticeCampaignReadOnly()
    from carbon.chain.external_signer import miner_signer
    from carbon.development_session.miner_network import binding_for
    from carbon.development_session.research_campaign import private_file
    from carbon.development_session.service import LocalMinerConnection

    config = binding_for(args)
    public = json.loads(private_file(args.miner_public).read_bytes())
    if public["netuid"] != CARBON_NETUID or config.netuid != CARBON_NETUID:
        raise ValueError(f"existing subnet {CARBON_NETUID} context required")
    if public["hotkey"] != admitted["hotkey"]:
        raise ValueError("the registered miner differs from this hotkey")
    # The miner's own signer holds the hotkey; Carbon only reaches it.
    key = miner_signer(public, getattr(args, "signer_socket", None))
    connection = LocalMinerConnection(
        session, args.image_manifest, config.context, config.publisher_hotkey, key
    )
    return connection, key, config
