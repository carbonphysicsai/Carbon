"""The one identity being made: a small state machine holding secrets in memory only."""

from __future__ import annotations

import hmac
import re
import secrets

from .backend import IdentityRefused

NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,31}")
MIN_PASSWORD = 10
MAX_PASSWORD = 256
CONFIRM_WORDS = 3
MAX_WRONG = 5


class Identity:
    """idle -> created (phrase shown once) -> confirmed (three words given back) -> saved (public addresses only).

    The phrase and the password exist in this object only between the calls that need them; `save` and
    `discard` overwrite what they can and drop the references.
    """

    def __init__(self, backend, hotkey_name="default"):
        self.backend = backend
        self.hotkey_name = hotkey_name
        self.stage = "idle"
        self._name = None
        self._phrase = None
        self._ask = ()
        self._wrong = 0

    # -- 1. create: the phrase, once --------------------------------------------------------------
    def create(self, name):
        if self.stage != "idle":
            raise IdentityRefused("An identity is already being made in this window.")
        if not isinstance(name, str) or not NAME.fullmatch(name):
            raise IdentityRefused(
                "Use a short name of letters, digits, - or _ (up to 32)."
            )
        if self.backend.exists(name):
            raise IdentityRefused(
                "A wallet with that name already exists here. Choose another name."
            )
        phrase = self.backend.new_phrase()
        words = phrase.split()
        if len(words) < 12:
            raise IdentityRefused("The key tool did not give a recovery phrase.")
        self._name, self._phrase = name, phrase
        self._ask = tuple(
            sorted(secrets.SystemRandom().sample(range(len(words)), CONFIRM_WORDS))
        )
        self.stage = "created"
        return {"words": words, "ask": [position + 1 for position in self._ask]}

    # -- 2. confirm: three of its words back ------------------------------------------------------
    def confirm(self, answers):
        if self.stage != "created":
            raise IdentityRefused("Create the identity first.")
        words = self._phrase.split()
        given = (
            [str(item).strip().lower() for item in answers]
            if isinstance(answers, list)
            else []
        )
        right = len(given) == CONFIRM_WORDS and all(
            hmac.compare_digest(words[position].encode(), given[i].encode())
            for i, position in enumerate(self._ask)
        )
        if not right:
            self._wrong += 1
            if self._wrong >= MAX_WRONG:
                self.discard()
                raise IdentityRefused(
                    "Too many wrong words. Nothing was saved; start again."
                )
            raise IdentityRefused(
                "Those words do not match. Check what you wrote down."
            )
        self.stage = "confirmed"
        return {"confirmed": True}

    # -- 3. save: the password, then public addresses only ----------------------------------------
    def save(self, password, again):
        if self.stage != "confirmed":
            raise IdentityRefused("Give back the words first.")
        if (
            not isinstance(password, str)
            or not isinstance(again, str)
            or not hmac.compare_digest(password.encode(), again.encode())
        ):
            raise IdentityRefused("The two passwords differ.")
        if not MIN_PASSWORD <= len(password) <= MAX_PASSWORD:
            raise IdentityRefused(
                f"Use a password of at least {MIN_PASSWORD} characters."
            )
        try:
            cold, hot = self.backend.save(
                self._name, self.hotkey_name, self._phrase, password
            )
        finally:
            self._phrase = None
        name = self._name
        self.stage = "saved"
        return {
            "wallet": name,
            "hotkey": self.hotkey_name,
            "coldkey_address": cold,
            "hotkey_address": hot,
        }

    def discard(self):
        self._phrase = None
        self._ask = ()
        self._name = None
        self.stage = "idle"
