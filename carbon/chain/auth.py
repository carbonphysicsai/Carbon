"""Explicit Bittensor btauth/1 boundary; no import-time SDK or key access."""

from dataclasses import dataclass
from enum import Enum
from importlib.metadata import PackageNotFoundError, version
from typing import Protocol

from .sdk import SDK_VERSION


class AuthCode(str, Enum):
    MALFORMED = "AUTH_MALFORMED"
    SIGNATURE = "AUTH_BAD_SIGNATURE"
    RECEIVER = "AUTH_WRONG_RECEIVER"
    STALE = "AUTH_STALE"
    REPLAY = "AUTH_REPLAY"
    UNAVAILABLE = "AUTH_UNAVAILABLE"


class AuthFailure(Exception):
    def __init__(self, code: AuthCode):
        self.code = code
        super().__init__(code.value)


@dataclass(frozen=True)
class AuthenticatedHotkey:
    hotkey: str
    nonce_ns: int


class NonceStore(Protocol):
    def check_and_store(self, hotkey_ss58: str, nonce_ns: int) -> bool: ...


class HotkeyVerifier(Protocol):
    def verify(
        self,
        headers: dict[str, str],
        body: bytes,
        *,
        method: str,
        path: str,
        receiver: str,
        now_ns: int,
        nonce_store: NonceStore,
    ) -> AuthenticatedHotkey: ...


def _sdk():
    unavailable = False
    try:
        unavailable = version("bittensor") != SDK_VERSION
    except PackageNotFoundError:
        unavailable = True
    if unavailable:
        raise AuthFailure(AuthCode.UNAVAILABLE)
    import bittensor as bt

    return bt


class BittensorHotkeyVerifier:
    def verify(
        self,
        headers: dict[str, str],
        body: bytes,
        *,
        method: str,
        path: str,
        receiver: str,
        now_ns: int,
        nonce_store: NonceStore,
    ) -> AuthenticatedHotkey:
        bt = _sdk()
        failure = None
        try:
            caller = bt.http_auth.verify(
                headers,
                body,
                method=method,
                path=path,
                self_hotkey_ss58=receiver,
                now_ns=now_ns,
                max_age=10.0,
                allowed_skew=2.0,
                require_receiver=True,
                nonce_store=nonce_store,
            )
            return AuthenticatedHotkey(caller.hotkey_ss58, caller.nonce_ns)
        except bt.http_auth.BadSignature:
            failure = AuthCode.SIGNATURE
        except bt.http_auth.WrongReceiver:
            failure = AuthCode.RECEIVER
        except bt.http_auth.StaleRequest:
            failure = AuthCode.STALE
        except bt.http_auth.ReplayedRequest:
            failure = AuthCode.REPLAY
        except bt.http_auth.MalformedAuth:
            failure = AuthCode.MALFORMED
        # Raise outside handlers: no SDK exception/payload retained in context.
        raise AuthFailure(failure)


class BittensorMessageSigner:
    """The trusted composition root supplies a signer; this opens no key file."""

    def __init__(self, signer):
        self._signer = signer

    def sign(self, body: bytes, *, receiver: str, nonce_ns: int) -> dict[str, str]:
        bt = _sdk()
        return bt.http_auth.sign(
            self._signer,
            method="POST",
            path="/carbon/v1/mcp",
            body=body,
            receiver_ss58=receiver,
            nonce_ns=nonce_ns,
        )
