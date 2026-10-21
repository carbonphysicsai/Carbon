"""Create a mining identity (coldkey and hotkey) on the miner's own machine.
THIS PACKAGE HANDLES SECRETS, and is deliberately not part of Carbon's product process.

Design: `codex-queue/reports/MINING_IDENTITY_HELPER_DESIGN_20261021.md`; accepted by the owner
(2026-10-21): the password is typed in this helper's own page only, never in the Control Center.

- the miner starts it, once, in their own terminal (`carbon-miner-identity`); it is its own process on its
  own loopback port with its own one-time token, which travels in the URL *fragment* and is then sent as a
  header, never as a query parameter;
- the Control Center and its page never import it, talk to it, or receive anything from it: the miner
  carries the public hotkey address across themselves;
- it uses the Bittensor SDK's own wallet functions in the SDK's own wallet directory, with files the SDK
  makes owner-only, exactly as the SDK's own wallet tool would;
- the coldkey recovery phrase is shown once, in this page only, with no copy button, and the miner must give
  back three of its words before a password can be set; the phrase and the password live in this process's
  memory only, are never written by this package, logged, put in a URL, or sent anywhere but to the SDK;
- it opens no connection except its own loopback listener, and exits when closed or after an idle period;
- it imports nothing from ``carbon``, and nothing in Carbon's product process imports it.

Ship gate: ``tests/cpu/test_miner_identity_helper.py`` searches every log line, every response, the process's
output and the files written for a sentinel password and phrase.
"""

__all__ = ["main"]


def main(argv=None):
    from .server import main as run

    return run(argv)
