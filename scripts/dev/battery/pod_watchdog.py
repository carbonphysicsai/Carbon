"""SCORE-PROOF-CONFIRM-02 pod watchdog (OWNER-STARTUP-HOST-CUSTODY-03-EXT-02 §2).

Runs as root on each confirmation pod, started by the pod's start command
only after this file's sha256 matches the value pinned in that command.

    python -I watchdog.py DEADLINE_EPOCH

It waits for either:
- the AX42's teardown marker (written over the pinned SSH after the AX42
  has pulled and verified the pod's records and wiped the pod), or
- the registered maximum lifetime (DEADLINE_EPOCH, fixed by the start
  command at container start).

Then, in this order: it stops every carbon-producer process, shreds every
file of that account outside `~/.ssh`, prints the remaining count, and only
then terminates the pod with RunPod's injected key: podTerminate, never stop.
The termination call is the pod's only outbound connection, and it happens
after the shred, when the pod holds no question.

The key is read once from the environment, removed from it, sent only in the
termination request's Authorization header, and never printed or written.
Nothing else here talks to the network.

`--dry --base DIR [--endpoint URL --cafile PEM]` is the sheet's dry run: every
path is under DIR, no process is killed, and the request goes to the given
test endpoint instead of RunPod.
"""

import argparse
import json
import os
import ssl
import subprocess
import sys
import time
import urllib.request

ENDPOINT = "https://api.runpod.io/graphql"
ACCOUNT = "carbon-producer"
HOME = "/var/lib/carbon-producer/startup"
WATCH = "/var/lib/carbon-producer/watchdog"
SCRATCH = ("/tmp", "/var/tmp", "/dev/shm")
POLL_S = 15
TRIES = 10
RETRY_S = 30


def say(*parts):
    print("WATCHDOG", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), *parts)
    sys.stdout.flush()


def files_of(home, scratch, uid):
    """Every regular file to shred: the account's home outside `.ssh`, and
    its files in the scratch directories."""
    found = []
    for top, owned_only in [(home, False)] + [(s, True) for s in scratch]:
        for d, dirs, names in os.walk(top):
            if d == top and not owned_only:
                dirs[:] = [x for x in dirs if x != ".ssh"]
            for name in names:
                path = os.path.join(d, name)
                try:
                    info = os.lstat(path)
                except OSError:
                    continue
                if not os.path.isfile(path) or os.path.islink(path):
                    continue
                if owned_only and info.st_uid != uid:
                    continue
                found.append(path)
    return found


def kill_account(uid):
    """SIGKILL every process of `uid` (stock Ubuntu has no pkill)."""
    import signal

    for pid in os.listdir("/proc"):
        if not pid.isdigit():
            continue
        try:
            with open(f"/proc/{pid}/status") as status:
                uids = next(x for x in status if x.startswith("Uid:")).split()
            if int(uids[1]) == uid:
                os.kill(int(pid), signal.SIGKILL)
        except (OSError, StopIteration, ValueError):
            continue


def shred(paths):
    for path in paths:
        if subprocess.run(
            ["shred", "-u", path], capture_output=True, check=False
        ).returncode:
            try:
                os.unlink(path)
            except OSError:
                pass


def terminate(key, pod, endpoint, cafile):
    if not (key and pod):
        return "unavailable: no injected key or pod id"
    body = json.dumps(
        {"query": 'mutation { podTerminate(input: {podId: "' + pod + '"}) }'}
    ).encode()
    request = urllib.request.Request(
        endpoint,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + key,
            "User-Agent": "carbon-confirm02-watchdog/1",
        },
    )
    context = (
        ssl.create_default_context(cafile=cafile)
        if cafile and os.path.exists(cafile)
        else ssl.create_default_context()
    )
    try:
        with urllib.request.urlopen(request, context=context, timeout=30) as reply:
            text = reply.read(400).decode(errors="replace")
        return "ok " + text
    except Exception as error:  # noqa: BLE001 -- reported, then retried
        return "failed " + type(error).__name__ + ": " + str(error)


def clean(text, key):
    text = " ".join(str(text).split())
    return (text.replace(key, "<key>") if key else text)[:240]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("deadline", type=int)
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--base", default="")
    ap.add_argument("--endpoint", default=ENDPOINT)
    ap.add_argument("--cafile")
    args = ap.parse_args(argv)
    if not args.dry and (args.base or args.endpoint != ENDPOINT):
        raise SystemExit("refused: --base and --endpoint are for --dry only")
    base = args.base
    home, watch = base + HOME, base + WATCH
    scratch = tuple(base + s for s in SCRATCH) if not args.dry else (base + "/tmp",)
    cafile = args.cafile or watch + "/ca.pem"
    key = os.environ.pop("RUNPOD_API_KEY", "")
    pod = os.environ.get("RUNPOD_POD_ID", "")
    if args.dry:
        uid = os.getuid()
    else:
        import pwd

        uid = pwd.getpwnam(ACCOUNT).pw_uid
    deadline = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(args.deadline))
    with open(watch + "/armed", "w") as status:
        status.write(
            f"ARMED deadline {deadline} key {'present' if key else 'ABSENT'}\n"
        )
    say("ARMED deadline", deadline, "key", "present" if key else "ABSENT")

    marker = watch + "/teardown"
    while True:
        if os.path.exists(marker):
            reason = "teardown"
            break
        if time.time() >= args.deadline:
            reason = "max_lifetime"
            break
        time.sleep(POLL_S if not args.dry else 0.2)
    say("TEARDOWN", reason)

    if not args.dry:
        kill_account(uid)
        time.sleep(2)
    shred(files_of(home, scratch, uid))
    left = len(files_of(home, scratch, uid))
    say("WIPED remaining", left)
    with open(watch + "/armed", "a") as status:
        status.write(f"TEARDOWN {reason} remaining {left}\n")

    for attempt in range(1, TRIES + 1):
        result = terminate(key, pod, args.endpoint, cafile)
        say("TERMINATE attempt", attempt, clean(result, key))
        if result.startswith("ok") and '"errors"' not in result:
            say("TERMINATE_REQUESTED: the owner confirms Terminated in the console")
            return 0
        if result.startswith("unavailable"):
            break
        time.sleep(RETRY_S if not args.dry else 0.1)
    say("TERMINATE_FAILED: the owner terminates this pod in the console now")
    return 1


if __name__ == "__main__":
    sys.exit(main())
