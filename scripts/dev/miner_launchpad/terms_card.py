"""The "Submission terms" card: the Carbon submission terms each of this miner's validators requires, shown in full, and
the miner's own accept (owner G-LEAD-50, 23 Nov 2026: terms v0, refuse-without).

The text is read from the validator (`submission_terms.fetch_text`: the exact bytes, only when their sha256 is the one the
validator's public intake facts name) and shown as it is; nothing here holds or rewrites terms text. Accepting records the
acceptance of exactly that version and text on this machine (`submission_terms.accept`); each submission then carries the
version and sha256 inside its hotkey-signed body. The accept is this page's only: it is not a setup step or an operation,
so no MCP tool or agent door can accept terms for the miner (as the GPU build).
"""

from __future__ import annotations

from carbon.development_session import submission_terms as terms

#: The challenge id in an accept request (the profile's own intake keys).
MAX_CHALLENGE_ID = 64


def _row(challenge, url, *, read, fetch, home):
    from scripts.dev.miner_launchpad.supervisor import NEXT_ACTIONS

    try:
        required = terms.required(read(url))
        if required is None:
            return {"challenge_id": challenge, "required": False}
        text = fetch(url, required)
    except ValueError as refused:  # TermsRefused, or the intake read's own typed refusal
        code = getattr(refused, "code", "construction_intake_unavailable")
        return {"challenge_id": challenge, "code": code, "words": NEXT_ACTIONS.get(code, "")}
    except OSError:
        code = terms.TEXT_UNAVAILABLE
        return {"challenge_id": challenge, "code": code, "words": NEXT_ACTIONS[code]}
    return {
        "challenge_id": challenge,
        "required": True,
        "version": required.version,
        "sha256": required.sha256,
        "text": text.decode("utf-8", errors="replace"),
        "accepted": terms.accepted(required, home),
    }


def _readers(read, fetch):
    if read is None:
        from carbon.development_session.direct_submission import read_intake as read
    return read, fetch or terms.fetch_text


def card(intake_urls, *, read=None, fetch=None, home=None):
    read, fetch = _readers(read, fetch)
    return {
        "challenges": [
            _row(challenge, url, read=read, fetch=fetch, home=home) for challenge, url in sorted(intake_urls.items())
        ]
    }


def accept(intake_urls, value, *, read=None, fetch=None, home=None):
    """Record the miner's accept of the terms one validator requires, re-read from that validator now: the sha256 the page
    showed must still be the one it names, so a miner never accepts a text they were not shown."""
    from scripts.dev.miner_launchpad.controller import Rejected

    if (
        type(value) is not dict
        or set(value) != {"challenge_id", "sha256"}
        or type(value["challenge_id"]) is not str
        or not 0 < len(value["challenge_id"]) <= MAX_CHALLENGE_ID
        or type(value["sha256"]) is not str
        or terms.SHA256.fullmatch(value["sha256"]) is None
    ):
        raise Rejected("closed_terms_accept_required")
    url = intake_urls.get(value["challenge_id"])
    if url is None:
        raise Rejected("terms_challenge_not_in_profile", 404)
    read, fetch = _readers(read, fetch)
    try:
        required = terms.required(read(url))
        if required is None:
            raise Rejected("terms_not_required", 409)
        if required.sha256 != value["sha256"]:
            raise Rejected("terms_changed_since_shown", 409)
        terms.accept(required, fetch(url, required), home=home)
    except terms.TermsRefused as refused:
        raise Rejected(refused.code, 409) from None
    return _row(value["challenge_id"], url, read=read, fetch=fetch, home=home)


def _intakes(configuration):
    if configuration is None:
        return None
    from carbon.development_session.private_records import private_json
    from scripts.dev.miner_launchpad.runner import intakes

    return intakes(private_json(configuration))


def for_profile(configuration):
    urls = _intakes(configuration)
    if urls is None:
        return {"challenges": [], "words": "Finish Setup to see the submission terms your validators require."}
    return card(urls)


def accept_for_profile(configuration, value):
    from scripts.dev.miner_launchpad.controller import Rejected

    urls = _intakes(configuration)
    if urls is None:
        raise Rejected("setup_unavailable", 409)
    return accept(urls, value)
