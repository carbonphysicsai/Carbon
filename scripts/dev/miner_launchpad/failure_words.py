"""A short, path-safe, address-safe cause for a failure, for records and the page.

Shared by the owner catalog install (a skipped entry's detail) and the readiness snapshot (a failed run): the failure
type, its stable code and the last line of its private diagnostic, with every word that could name a path, an address,
a host:port or a token replaced. ASCII only; nothing else leaves the host.
"""

import re

#: A word of a daemon line that could name a path, an address, a host:port or a token.
SENSITIVE = re.compile(
    r"[/\\]|\d{1,3}(?:\.\d{1,3}){3}|:\d+[.,;]?$|[A-Za-z0-9+=_-]{24,}"
)


def diagnostic(failure, suffix="") -> str:
    text = f"{type(failure).__name__}: {failure}"
    code = getattr(failure, "code", None)
    if code is not None:
        text += f" [{getattr(code, 'value', code)}]"
    raw = getattr(failure, "private_diagnostic", b"")
    lines = raw.decode("utf-8", "replace").strip().splitlines() if raw else []
    if lines:
        line = lines[-1]  # the daemon's own last word, not the exit-code header
        words = [
            "<redacted>" if SENSITIVE.search(word) else word for word in line.split()
        ]
        text += " (" + " ".join(words)[:120] + ")"
    return re.sub(r"[^ -~]", "?", text)[: 300 - len(suffix)] + suffix
