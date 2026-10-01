"""The miner's local signer for Carbon. THIS PACKAGE OPENS THE MINER'S HOTKEY.

It is the one place in this repository that holds a miner's private key, and
it is deliberately not part of Carbon's product process:

- the miner starts it, in their own terminal, once per session;
- if the hotkey file is encrypted, the Bittensor SDK asks for the password in
  that terminal - the password never passes through Carbon or a file Carbon
  reads;
- it listens on a Unix socket only the miner's own user can reach, and signs
  only Carbon ``btauth/1`` request payloads from its own hotkey, with a fresh
  nonce - never a chain extrinsic, never an arbitrary message;
- it imports nothing from ``carbon``, and nothing in Carbon's product process
  imports it (``tests/invariants/test_product_process_holds_no_key.py``).

Carbon's side is ``carbon.chain.external_signer``: it sends the canonical
payload, receives a signature, and verifies that signature against the public
hotkey before using it.

Start it with ``carbon-miner-signer --wallet NAME --hotkey HOTKEY``.
"""

from .signer import (
    PATH,
    PROTOCOL,
    Refusal,
    SignerServer,
    default_socket,
    load_hotkey,
    main,
    refusal_for,
)

__all__ = [
    "PATH",
    "PROTOCOL",
    "Refusal",
    "SignerServer",
    "default_socket",
    "load_hotkey",
    "main",
    "refusal_for",
]
