"""A miner's signer served on a thread, for tests that play the miner.

Carbon signs only through `carbon.chain.external_signer`, so a test that needs
a real signed request runs a real `carbon_miner_signer.SignerServer` holding a
public development key, and reaches it over a real socket.
"""

import io
import tempfile
import threading
from contextlib import contextmanager
from pathlib import Path

from carbon.chain.external_signer import connect_signer
from carbon_miner_signer import SignerServer


@contextmanager
def in_thread_signer(keypair, *, clock=None, **options):
    """Yield an `ExternalSigner` for `keypair`, served until the block exits.
    Other `options` (`receivers`, `requests`) go to the `SignerServer`."""
    with tempfile.TemporaryDirectory(prefix="cs-", dir="/tmp") as directory:
        if clock is not None:
            options["clock"] = clock
        server = SignerServer(
            keypair, Path(directory) / "s.sock", log=io.StringIO(), **options
        ).bind()
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield connect_signer(keypair.ss58_address, socket_path=server.socket_path)
        finally:
            server.close()
            thread.join(timeout=5)
