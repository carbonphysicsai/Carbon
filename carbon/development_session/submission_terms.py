"""The Carbon submission terms on the miner's side (owner G-LEAD-50, 23 Nov 2026: terms v0, refuse-without).

From each next Challenge version's open, the validator records with every submission the terms version, the sha256 of
the terms text as published, and the miner's acceptance; a submission without it is refused (`terms_not_accepted`).
This module is the client half:

- The validator names the terms a version requires in its public intake facts (``terms``: version, sha256 and the door
  path that serves the exact text). No ``terms`` = the version requires none (a live version mid-flight is unchanged).
- The client never embeds the text: it reads the bytes from the door, refuses them unless their sha256 is the one the
  facts name, shows them, and records the miner's acceptance only after an explicit accept (the Launchpad's Submission
  terms card, or ``python -m carbon.development_session.submission_terms --door <url>``).
- The accepted version and sha256 go inside the hotkey-signed submission body (`submission_fields`), so the signature
  over them is the acceptance bound to that submission. Acceptance is never inferred from a hotkey alone, and a client
  without a recorded acceptance refuses before it signs anything.

The local record (``~/.carbon/terms/<version>.<sha256>.json``) is the miner's own convenience, not Carbon's evidence:
the validator's evidence is the signed submission. Nothing here reads or grants any score, reward or rights decision.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from carbon.development_session.data import write_once
from carbon.miner_agent import MINER_HEADERS

SCHEMA = "carbon.submission-terms-acceptance.v1"
PATH_PREFIX = "/carbon/v1/terms/"
MAX_TEXT_BYTES = 64 * 1024
MAX_RECORD_BYTES = 4096
FIELDS = ("version", "sha256", "path")
VERSION = re.compile(r"carbon-submission-terms-v[0-9]{1,4}")
SHA256 = re.compile(r"[0-9a-f]{64}")
#: The signed submission fields that carry the acceptance (validator side: door-code's terms head).
SUBMIT_FIELDS = ("terms_version", "terms_sha256")

NOT_ACCEPTED = "terms_not_accepted"
FACTS_INVALID = "terms_facts_invalid"
TEXT_UNAVAILABLE = "terms_text_unavailable"
TEXT_OVERSIZED = "terms_text_oversized"
TEXT_DIGEST_MISMATCH = "terms_text_digest_mismatch"
CODES = (
    NOT_ACCEPTED,
    FACTS_INVALID,
    TEXT_UNAVAILABLE,
    TEXT_OVERSIZED,
    TEXT_DIGEST_MISMATCH,
)


class TermsRefused(ValueError):
    """A closed reason the client cannot show, record or send an acceptance; never a model result."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Terms:
    version: str
    sha256: str
    path: str


def required(facts) -> Terms | None:
    """The terms the validator's intake facts require, or None when they name none. A malformed ``terms`` refuses: a
    client never guesses which text a submission accepts."""
    if type(facts) is not dict:
        raise TermsRefused(FACTS_INVALID)
    value = facts.get("terms")
    if value is None:
        return None
    if (
        type(value) is not dict
        or set(value) != set(FIELDS)
        or not all(type(value[name]) is str for name in FIELDS)
        or VERSION.fullmatch(value["version"]) is None
        or SHA256.fullmatch(value["sha256"]) is None
        or value["path"] != PATH_PREFIX + value["version"]
    ):
        raise TermsRefused(FACTS_INVALID)
    return Terms(value["version"], value["sha256"], value["path"])


def store(home=None) -> Path:
    return Path(home) if home is not None else Path.home() / ".carbon" / "terms"


def record_path(terms: Terms, home=None) -> Path:
    return store(home) / f"{terms.version}.{terms.sha256}.json"


def accepted(terms: Terms, home=None) -> bool:
    """Whether this machine holds the miner's acceptance of exactly this version and text."""
    path = record_path(terms, home)
    try:
        if (
            path.is_symlink()
            or not path.is_file()
            or path.stat().st_size > MAX_RECORD_BYTES
        ):
            return False
        value = json.loads(path.read_bytes())
    except (OSError, ValueError):
        return False
    return (
        type(value) is dict
        and value.get("schema") == SCHEMA
        and value.get("version") == terms.version
        and value.get("sha256") == terms.sha256
        and type(value.get("accepted_utc")) is str
    )


def fetch_text(
    url: str, terms: Terms, *, timeout: float = 10.0, opener=urllib.request.urlopen
) -> bytes:
    """The exact terms text the door serves, only when its sha256 is the one the facts name."""
    request = urllib.request.Request(
        url.rstrip("/") + terms.path, headers=MINER_HEADERS, method="GET"
    )
    try:
        with opener(request, timeout=timeout) as response:
            text = response.read(MAX_TEXT_BYTES + 1)
    except (urllib.error.URLError, OSError):
        raise TermsRefused(TEXT_UNAVAILABLE) from None
    if len(text) > MAX_TEXT_BYTES:
        raise TermsRefused(TEXT_OVERSIZED)
    if hashlib.sha256(text).hexdigest() != terms.sha256:
        raise TermsRefused(TEXT_DIGEST_MISMATCH)
    return text


def accept(terms: Terms, text: bytes, *, home=None, clock=time.time) -> Path:
    """Record the miner's acceptance of the text they were shown. Only the text whose sha256 the validator named can be
    accepted; an existing acceptance of the same version and text is kept as it is."""
    if type(text) is not bytes or hashlib.sha256(text).hexdigest() != terms.sha256:
        raise TermsRefused(TEXT_DIGEST_MISMATCH)
    path = record_path(terms, home)
    if accepted(terms, home):
        return path
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    record = {
        "schema": SCHEMA,
        "version": terms.version,
        "sha256": terms.sha256,
        "accepted_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(clock())),
    }
    write_once(
        path,
        json.dumps(record, sort_keys=True, separators=(",", ":")).encode("ascii")
        + b"\n",
    )
    return path


def submission_fields(facts, *, home=None) -> dict:
    """The signed submission fields for the terms the facts require: none when they require none; a typed refusal,
    before anything is signed, when this machine holds no acceptance of exactly that version and text.
    """
    terms = required(facts)
    if terms is None:
        return {}
    if not accepted(terms, home):
        raise TermsRefused(NOT_ACCEPTED)
    return {"terms_version": terms.version, "terms_sha256": terms.sha256}


def main(
    argv=None, *, read=None, fetch=fetch_text, ask=input, out=sys.stdout, home=None
) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m carbon.development_session.submission_terms",
        description="Show the Carbon submission terms a validator requires and record your acceptance.",
    )
    parser.add_argument("--door", required=True, help="the validator's intake URL")
    parser.add_argument(
        "--accept",
        metavar="SHA256",
        help="accept without the prompt; must equal the sha256 printed under the text you read",
    )
    args = parser.parse_args(argv)
    if read is None:
        from carbon.development_session.direct_submission import read_intake as read
    try:
        terms = required(read(args.door))
        if terms is None:
            print("This validator requires no submission terms.", file=out)
            return 0
        text = fetch(args.door, terms)
        print(text.decode("utf-8"), file=out)
        print(f"\nterms version: {terms.version}\nsha256: {terms.sha256}", file=out)
        if accepted(terms, home):
            print("You have already accepted this version on this machine.", file=out)
            return 0
        if args.accept is not None:
            if args.accept != terms.sha256:
                print(
                    "Not accepted: --accept does not match the sha256 of the text shown.",
                    file=out,
                )
                return 2
        elif (
            ask("Type ACCEPT to accept these terms for your submissions: ").strip()
            != "ACCEPT"
        ):
            print(
                "Not accepted. Submissions to this version are refused until you accept.",
                file=out,
            )
            return 1
        path = accept(terms, text, home=home)
    except (
        ValueError
    ) as refused:  # TermsRefused, or the intake read's own typed refusal
        print(f"refused: {getattr(refused, 'code', refused)}", file=out)
        return 2
    print(
        f"Accepted. Recorded at {path}; each submission now carries this version and sha256.",
        file=out,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
