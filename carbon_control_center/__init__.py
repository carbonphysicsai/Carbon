"""`carbon-control-center`: the miner's Control Center, as one command (LP-PROD-E).

The installer's environment puts this command beside `carbon-miner-signer`, so a
miner starts the Control Center without naming a script path:

    ~/carbon/.venv/bin/carbon-control-center [--state-dir DIR] [--port PORT]

It runs `scripts/dev/miner_launchpad/controller.py` from the Carbon checkout
this environment was installed from, with the same options, and nothing else:
the controller binds 127.0.0.1 only and prints its session token. The checkout
is put on the import path because its `scripts` package is not installed.

It holds no key and imports nothing that could open one: the miner's hotkey
stays with their own signer.
"""

from __future__ import annotations

import sys
from pathlib import Path

#: The checkout this package was installed from (an editable install).
CHECKOUT = Path(__file__).resolve().parents[1]
CONTROLLER = CHECKOUT / "scripts" / "dev" / "miner_launchpad" / "controller.py"


def main(argv=None) -> None:
    """Run the Control Center from this checkout with `argv` (default: this
    process's own arguments)."""
    if not CONTROLLER.is_file():
        raise SystemExit(
            "carbon-control-center: no Control Center at "
            + str(CONTROLLER)
            + "; run it from the environment scripts/install_miner.sh installed."
        )
    if str(CHECKOUT) not in sys.path:
        sys.path.insert(0, str(CHECKOUT))
    if argv is not None:
        sys.argv = [sys.argv[0], *argv]
    from scripts.dev.miner_launchpad import controller

    controller.main()
