"""The canary's reports (CANARY-01 S1, plan §7): pings and the journal.

- A completed cycle within every set deadline sends one success ping to the
  owner's healthchecks.io check; a stage miss or a closed failure sends a
  `/fail` ping whose body names the stage and its closed code. The ping is
  `curl -fsS -m 10 --retry 3` in Python: a 10 s timeout per try, up to three
  retries on a timeout, a connection failure or a 408, 429, 500, 502, 503 or
  504, with 1, 2 and 4 s between tries, and success only on a 2xx.
- The ping URL is read from the owner-only env file by path (`HC_CANARY=`) and
  is never logged, printed or journalled.
- Every run appends one JSONL line to the journal: stage timings, closed
  codes, the submission id and the variant index. Public values only: no
  hidden material, no key, no ping URL.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

from scripts.dev.canary.config import ConfigRefused, owner_only_bytes

JOURNAL_SCHEMA = "carbon.canary.journal.v1"
ENV_KEY = "HC_CANARY"
RETRY_STATUSES = frozenset({408, 429, 500, 502, 503, 504})
TIMEOUT_S = 10.0
RETRIES = 3


def ping_url(env_file):
    """The ping URL from the owner-only env file: its one `HC_CANARY=` line,
    an https URL. Refused `healthcheck_env_unusable` otherwise; the refusal
    never carries the file's content."""
    raw = owner_only_bytes(env_file, limit=4096, code="healthcheck_env_unusable")
    found = []
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise ConfigRefused("healthcheck_env_unusable") from None
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, sep, value = line.partition("=")
        if sep and key.strip() == ENV_KEY:
            found.append(value.strip())
    if (
        len(found) != 1
        or not found[0].startswith("https://")
        or any(c.isspace() for c in found[0])
        or len(found[0]) > 512
    ):
        raise ConfigRefused("healthcheck_env_unusable")
    return found[0]


def ping(url, body, *, fail, opener=urllib.request.urlopen, sleep=time.sleep):
    """Send one ping; whether it was delivered (a 2xx). Never raises, and
    never says which URL."""
    target = url.rstrip("/") + "/fail" if fail else url
    delay = 1.0
    for attempt in range(RETRIES + 1):
        retryable = False
        try:
            request = urllib.request.Request(
                target,
                data=body.encode("utf-8"),
                method="POST",
                headers={
                    "Content-Type": "text/plain; charset=utf-8",
                    "User-Agent": "carbon-canary/1",
                },
            )
            with opener(request, timeout=TIMEOUT_S) as answer:
                status = getattr(answer, "status", None)
            if type(status) is int and 200 <= status < 300:
                return True
            retryable = status in RETRY_STATUSES
        except urllib.error.HTTPError as refused:
            retryable = refused.code in RETRY_STATUSES
        except (urllib.error.URLError, TimeoutError, OSError):
            retryable = True
        except Exception:  # noqa: BLE001 - a ping never stops the runner
            retryable = False
        if not retryable or attempt == RETRIES:
            return False
        sleep(delay)
        delay *= 2
    return False


def success_body(line):
    """A success ping's body: the cycle, variant and submission, all public."""
    return (
        f"canary cycle {line['cycle_id']} completed: variant {line['variant_index']}, "
        f"submission {line['submission_id']}"
    )


def fail_body(line):
    """A failure ping's body: the stage, its closed code and the cycle."""
    failure = line["failure"]
    return (
        f"stage={failure['stage']} code={failure['code']} "
        f"cycle={line['cycle_id']} variant={line['variant_index']}"
    )


def append(path, line):
    """Append one journal line (owner-only file, created 0600)."""
    data = (json.dumps(line, sort_keys=True, separators=(",", ":")) + "\n").encode()
    fd = os.open(
        path,
        os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW,
        0o600,
    )
    try:
        os.write(fd, data)
    finally:
        os.close(fd)
