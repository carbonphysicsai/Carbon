"""A local signer holding one miner hotkey, reachable only by that miner's user.

Wire protocol, one request per connection, one JSON object per line:

    -> {"protocol": PROTOCOL, "op": "identity"}
    <- {"ok": true, "hotkey": "<ss58>", "crypto_type": 1}

    -> {"protocol": PROTOCOL, "op": "sign", "payload": "<btauth/1 payload>"}
    <- {"ok": true, "signature": "0x<hex>"}
    <- {"ok": false, "refusal": "<Refusal>"}

The payload is the exact ``btauth/1`` byte string the verifier rebuilds
(``bittensor.http_auth.build_payload``). The signer parses it only to decide
whether to sign; it never signs anything but these bytes.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import socket
import stat
import struct
import sys
import time
from enum import Enum
from pathlib import Path

PROTOCOL = "carbon.miner-signer.v1"
#: The one request target Carbon's miner session signs for.
PATH = "/carbon/v1/mcp"
MAX_REQUEST_BYTES = 4096
#: How old, and how far in the future, a request nonce may be. The verifier's
#: own window is 10 s back and 2 s ahead; this is wider only so clock
#: granularity between the two processes never refuses an honest request.
PAST_WINDOW_NS = 30 * 10**9
FUTURE_WINDOW_NS = 5 * 10**9
CONNECTION_TIMEOUT_S = 5.0
SCHEMES = {0: "ed25519", 1: "sr25519"}
_SS58 = re.compile(r"[1-9A-HJ-NP-Za-km-z]{46,48}")
_HEX64 = re.compile(r"[0-9a-f]{64}")
_NONCE = re.compile(r"[0-9]{1,20}")


class Refusal(str, Enum):
    """Why the signer declined. Closed: nothing else crosses the socket."""

    MALFORMED_REQUEST = "MALFORMED_REQUEST"
    NOT_A_CARBON_REQUEST = "NOT_A_CARBON_REQUEST"
    WRONG_SENDER = "WRONG_SENDER"
    STALE_NONCE = "STALE_NONCE"
    RECEIVER_NOT_ALLOWED = "RECEIVER_NOT_ALLOWED"


def default_socket(hotkey: str) -> Path:
    """Where the signer for ``hotkey`` listens unless told otherwise.

    Carbon derives the same path from the same public hotkey, so neither side
    needs configuring. Kept short: a Unix socket path is limited to ~104 bytes.
    """
    if not _SS58.fullmatch(hotkey):
        raise ValueError("a hotkey ss58 address is required")
    return Path.home() / ".carbon" / "signer" / (hotkey + ".sock")


def refusal_for(
    payload: bytes,
    *,
    hotkey: str,
    scheme: str,
    receivers: frozenset[str] | None,
    now_ns: int,
) -> Refusal | None:
    """None when ``payload`` is a Carbon request this signer may sign."""
    try:
        lines = payload.decode("ascii").split("\n")
    except UnicodeDecodeError:
        return Refusal.NOT_A_CARBON_REQUEST
    if len(lines) != 8:
        return Refusal.NOT_A_CARBON_REQUEST
    protocol, signed_scheme, method, path, body_hash, nonce, sender, receiver = lines
    if (
        protocol != "btauth/1"
        or signed_scheme != scheme
        or method != "POST"
        or path != PATH
        or not _HEX64.fullmatch(body_hash)
        or not _NONCE.fullmatch(nonce)
    ):
        return Refusal.NOT_A_CARBON_REQUEST
    if sender != hotkey:
        return Refusal.WRONG_SENDER
    age = now_ns - int(nonce)
    if age > PAST_WINDOW_NS or -age > FUTURE_WINDOW_NS:
        return Refusal.STALE_NONCE
    # An unbound request ("-") could be replayed to any receiver.
    if not _SS58.fullmatch(receiver) or (
        receivers is not None and receiver not in receivers
    ):
        return Refusal.RECEIVER_NOT_ALLOWED
    return None


def _peer_is_this_user(connection: socket.socket) -> bool:
    """Linux reports the connecting process's uid; elsewhere the 0700
    directory is the boundary."""
    option = getattr(socket, "SO_PEERCRED", None)
    if option is None:
        return True
    _pid, uid, _gid = struct.unpack(
        "3i", connection.getsockopt(socket.SOL_SOCKET, option, struct.calcsize("3i"))
    )
    return uid == os.getuid()


class SignerServer:
    """Holds one keypair and signs Carbon request payloads for its owner."""

    def __init__(
        self, keypair, socket_path: Path, *, receivers=None, log=None, clock=time.time_ns
    ):
        if keypair.crypto_type not in SCHEMES:
            raise ValueError("unsupported key type")
        self._keypair = keypair
        self.hotkey = keypair.ss58_address
        self.scheme = SCHEMES[keypair.crypto_type]
        self.socket_path = Path(socket_path)
        self.receivers = None if receivers is None else frozenset(receivers)
        self._log = log if log is not None else sys.stderr
        self._clock = clock
        self._listener = None

    def __repr__(self):
        # Never the keypair.
        return f"SignerServer(hotkey={self.hotkey!r}, socket={str(self.socket_path)!r})"

    def bind(self):
        directory = self.socket_path.parent
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        info = directory.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid():
            raise ValueError(f"{directory} must be a directory you own")
        os.chmod(directory, 0o700)
        if self.socket_path.exists() or self.socket_path.is_symlink():
            if not stat.S_ISSOCK(self.socket_path.lstat().st_mode):
                raise ValueError(f"{self.socket_path} exists and is not a socket")
            probe = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            try:
                probe.connect(str(self.socket_path))
            except OSError:
                self.socket_path.unlink()  # a previous signer's, no longer live
            else:
                raise ValueError("a signer is already running on " + str(self.socket_path))
            finally:
                probe.close()
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        previous = os.umask(0o177)
        try:
            listener.bind(str(self.socket_path))
        finally:
            os.umask(previous)
        listener.listen(8)
        self._listener = listener
        return self

    def serve_forever(self):
        while self._listener is not None:
            try:
                connection, _ = self._listener.accept()
            except OSError:
                if self._listener is None:
                    return
                raise
            with connection:
                self.serve_one(connection)

    def serve_one(self, connection):
        connection.settimeout(CONNECTION_TIMEOUT_S)
        try:
            if not _peer_is_this_user(connection):
                self._note("refused a connection from another user")
                return
            request = self._read(connection)
            response = self.answer(request)
            connection.sendall(json.dumps(response).encode() + b"\n")
        except (OSError, ValueError):
            return

    def answer(self, request) -> dict:
        if type(request) is not dict or request.get("protocol") != PROTOCOL:
            return self._refuse(Refusal.MALFORMED_REQUEST)
        if request.get("op") == "identity" and set(request) == {"protocol", "op"}:
            return {
                "ok": True,
                "hotkey": self.hotkey,
                "crypto_type": self._keypair.crypto_type,
            }
        if (
            request.get("op") != "sign"
            or set(request) != {"protocol", "op", "payload"}
            or type(request["payload"]) is not str
        ):
            return self._refuse(Refusal.MALFORMED_REQUEST)
        payload = request["payload"].encode("utf-8")
        refusal = refusal_for(
            payload,
            hotkey=self.hotkey,
            scheme=self.scheme,
            receivers=self.receivers,
            now_ns=self._clock(),
        )
        if refusal is not None:
            return self._refuse(refusal)
        signature = bytes(self._keypair.sign(payload))
        lines = payload.decode("ascii").split("\n")
        self._note(f"signed a Carbon request for receiver {lines[7]}, body sha256 {lines[4][:16]}")
        return {"ok": True, "signature": "0x" + signature.hex()}

    def close(self):
        listener, self._listener = self._listener, None
        if listener is not None:
            listener.close()
            try:
                self.socket_path.unlink()
            except FileNotFoundError:
                pass

    def _read(self, connection):
        data = b""
        while b"\n" not in data:
            chunk = connection.recv(1024)
            if not chunk:
                break
            data += chunk
            if len(data) > MAX_REQUEST_BYTES:
                raise ValueError("request too large")
        try:
            return json.loads(data.split(b"\n", 1)[0])
        except ValueError:
            return None

    def _refuse(self, refusal: Refusal) -> dict:
        self._note("refused a request: " + refusal.value)
        return {"ok": False, "refusal": refusal.value}

    def _note(self, text):
        stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M:%SZ")
        print(f"{stamp} {text}", file=self._log, flush=True)


def load_hotkey(*, wallet=None, hotkey=None, wallet_path=None, key_file=None):
    """Unlock the miner's hotkey with the Bittensor SDK.

    If the file is encrypted the SDK asks for the password on this terminal
    (or reads the SDK's own ``BT_PW_*`` environment variable if the miner set
    one). Errors are reduced to a fixed message so no key material or password
    can surface in a traceback.
    """
    try:
        from bittensor.keyfiles import Keyfile
        from bittensor.wallet import DEFAULT_WALLET_PATH

        if key_file is None:
            root = Path(wallet_path or DEFAULT_WALLET_PATH).expanduser()
            key_file = root / wallet / "hotkeys" / hotkey
        keypair = Keyfile(Path(key_file).expanduser()).get_keypair()
    except KeyboardInterrupt:
        raise
    except Exception:  # noqa: BLE001 - never show the SDK's error text
        keypair = None
    if keypair is None:
        raise SystemExit("could not unlock the hotkey (wrong password, or no such key file)")
    return keypair


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="carbon-miner-signer",
        description=(
            "Hold your hotkey and sign Carbon's requests with it, so Carbon never "
            "has your key or its password. Leave it running while you mine."
        ),
    )
    parser.add_argument("--wallet", help="Bittensor wallet name")
    parser.add_argument("--hotkey", help="hotkey name within the wallet")
    parser.add_argument("--wallet-path", help="wallets directory (the SDK default if omitted)")
    parser.add_argument("--key-file", type=Path, help="a hotkey file, instead of --wallet/--hotkey")
    parser.add_argument("--expect", help="refuse to start unless the hotkey has this ss58 address")
    parser.add_argument(
        "--receiver",
        action="append",
        help="only sign requests addressed to this validator hotkey (repeatable)",
    )
    parser.add_argument("--socket", type=Path, help="socket path (derived from the hotkey if omitted)")
    args = parser.parse_args(argv)
    if (args.key_file is None) == (args.wallet is None or args.hotkey is None):
        parser.error("give either --wallet and --hotkey, or --key-file")
    keypair = load_hotkey(
        wallet=args.wallet,
        hotkey=args.hotkey,
        wallet_path=args.wallet_path,
        key_file=args.key_file,
    )
    if args.expect is not None and keypair.ss58_address != args.expect:
        raise SystemExit("this key file holds a different hotkey than --expect")
    server = SignerServer(
        keypair,
        args.socket or default_socket(keypair.ss58_address),
        receivers=args.receiver,
    )
    del keypair
    server.bind()
    print(
        f"Carbon miner signer for hotkey {server.hotkey}\n"
        f"listening on {server.socket_path}\n"
        "Carbon's requests are signed here and each one is shown below. "
        "Ctrl-C stops signing.",
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.close()
    return 0
