"""The miner's local signer for Carbon. THIS PACKAGE OPENS THE MINER'S HOTKEY.

It is the one place in this repository that holds a miner's private key, and
it is deliberately not part of Carbon's product process:

- the miner starts it, in their own terminal, once per session;
- if the hotkey file is encrypted, the Bittensor SDK asks for the password in
  that terminal - the password never passes through Carbon or a file Carbon
  reads;
- it listens on a Unix socket only the miner's own user can reach, and signs
  only Carbon ``btauth/1`` request payloads from its own hotkey, with a fresh
  nonce, never an arbitrary message;
- its one chain extrinsic is a strategy commitment
  (``Commitments.set_commitment``, OWNER-COMMITMENT-POSTER-01): it rebuilds
  the call and checks every bound itself (``commitment``), never opens a
  network connection, and signs only after the miner types the digest's last
  8 characters in its terminal, or, opt-in and on testnet 567 only, for a
  hotkey in an owner-written allow-list (``autoconfirm``,
  OWNER-SIGNER-TESTNET-AUTOCONFIRM-01);
- it refuses to start on a key file others can read (D8);
- it imports nothing from ``carbon``, and nothing in Carbon's product process
  imports it (``tests/invariants/test_product_process_holds_no_key.py``).

Carbon's side is ``carbon.chain.external_signer``: it sends the canonical
payload, receives a signature, and verifies that signature against the public
hotkey before using it.

Start it with ``carbon-miner-signer --wallet NAME --hotkey HOTKEY``.
"""

from .commitment import CommitRefusal, key_file_problem, load_policy
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
    "CommitRefusal",
    "Refusal",
    "SignerServer",
    "default_socket",
    "key_file_problem",
    "load_hotkey",
    "load_policy",
    "main",
    "refusal_for",
]
