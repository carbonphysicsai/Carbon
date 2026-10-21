"""Where the keys are made: the Bittensor SDK, and a stand-in for tests."""

from __future__ import annotations

from pathlib import Path


class IdentityRefused(ValueError):
    """The identity cannot be made; the message is plain words and holds no secret."""


class SdkBackend:
    """The Bittensor SDK's own wallet functions.

    The phrase is generated here and handed to ``regenerate_coldkey`` with ``suppress=True`` so the SDK
    never prints it; the password goes to the SDK's own encryption as ``coldkey_password`` /
    ``hotkey_password`` (no prompt, no environment variable, no file of ours). Both keys are encrypted.
    """

    def __init__(self, wallet_path=None):
        self.wallet_path = wallet_path

    def new_phrase(self) -> str:
        from bittensor.keyfiles import Keypair

        return Keypair.generate_mnemonic(12)

    def _wallet(self, name, hotkey):
        from bittensor import Wallet

        return (
            Wallet(name=name, hotkey=hotkey, path=self.wallet_path)
            if self.wallet_path
            else Wallet(name=name, hotkey=hotkey)
        )

    def exists(self, name: str) -> bool:
        wallet = self._wallet(name, "default")
        return Path(wallet.path).expanduser().joinpath(name).exists()

    def save(
        self, name: str, hotkey: str, coldkey_phrase: str, password: str
    ) -> tuple[str, str]:
        """Write both keys; returns the PUBLIC coldkey and hotkey addresses."""
        if self.exists(name):
            raise IdentityRefused(
                "A wallet with that name already exists here. Choose another name."
            )
        from bittensor.keyfiles import Keypair

        wallet = self._wallet(name, hotkey)
        wallet.regenerate_coldkey(
            mnemonic=coldkey_phrase,
            use_password=True,
            coldkey_password=password,
            overwrite=False,
            suppress=True,
        )
        wallet.regenerate_hotkey(
            mnemonic=Keypair.generate_mnemonic(12),
            use_password=True,
            hotkey_password=password,
            overwrite=False,
            suppress=True,
        )
        return wallet.coldkeypub.ss58_address, wallet.hotkeypub.ss58_address


class FakeBackend:
    """For tests: deterministic phrase, nothing written, addresses that are not keys."""

    def __init__(self, phrase=None):
        self.phrase = (
            phrase
            or "alpha bravo charlie delta echo foxtrot golf hotel india juliet kilo lima"
        )
        self.saved = []
        self.names = set()

    def new_phrase(self) -> str:
        return self.phrase

    def exists(self, name: str) -> bool:
        return name in self.names

    def save(self, name, hotkey, coldkey_phrase, password):
        if name in self.names:
            raise IdentityRefused(
                "A wallet with that name already exists here. Choose another name."
            )
        self.names.add(name)
        self.saved.append((name, hotkey, len(password)))
        return "5COLDpublicaddress" + name, "5HOTpublicaddress" + name
