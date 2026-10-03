"""Serve the research surface over one synthetic campaign (RSURF-D7).

    python scripts/dev/miner_launchpad/research_demo.py --port 8794 --state-dir DIR

SYNTHETIC FIXTURE. The page is the real Control Center, served by the real
controller, but its runner is `research_fixture.FixtureRunner`: it launches
nothing, controls nothing, opens no ledger and reads no chain. Setup is off.
Paste the printed token (or open the printed link, which carries it, once
the page reads it - `controller.session_link_supported`), then open My
Campaigns.
"""

from __future__ import annotations

import argparse
import secrets
import sys
import tempfile
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


class _NoChain:
    """A device-free chain reader: the demo never reads a chain."""

    async def capture(self, context):
        from carbon.chain.models import MetagraphSnapshot

        return MetagraphSnapshot(
            context=context,
            finalized_block=0,
            block_hash="0x" + "00" * 32,
            timestamp_ms=0,
            participants=(),
        )


def _onboarding():
    from carbon.chain.models import ChainContext
    from carbon.development_session.chain_onboarding import carbon_testnet_context
    from scripts.dev.miner_launchpad.onboarding import BrowserOnboarding

    live = carbon_testnet_context()
    return BrowserOnboarding(
        reader=_NoChain(),
        context=ChainContext(
            network=live.network,
            endpoint=live.endpoint,
            provider=live.provider,
            genesis_hash=live.genesis_hash,
            netuid=live.netuid,
        ),
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8794)
    parser.add_argument("--state-dir", type=Path, default=None)
    args = parser.parse_args(argv)
    if not 1024 <= args.port <= 65535:
        parser.error("Use an unprivileged port between 1024 and 65535")
    sys.path.insert(0, str(ROOT))
    from scripts.dev.miner_launchpad import controller
    from scripts.dev.miner_launchpad.research_fixture import FixtureRunner

    state = args.state_dir or Path(tempfile.mkdtemp(prefix="carbon-research-demo-"))
    with controller.owner_lock(state):
        server = controller.Server(
            controller.Controller(state / "runs.sqlite3"),
            secrets.token_urlsafe(32),
            args.port,
            research_runner=FixtureRunner(),
            onboarding=_onboarding(),
        )
        print("Carbon research surface - SYNTHETIC FIXTURE, nothing runs")
        if controller.session_link_supported():
            print(f"Open: {controller.session_url(server.origin, server.token)}")
        else:
            print(f"Open: {server.origin}")
        print(f"Local session token (paste into the page): {server.token}")
        print("Then: My Campaigns, the fixture campaign; Launchpad shows it too.")
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            thread.join()
        except KeyboardInterrupt:
            pass
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    main()
