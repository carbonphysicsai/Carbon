"""A ``docker`` stand-in for a reference-solvers pod (no Docker inside).

The family tools (freeze scripts, smokes, controls, proofs) call
``docker run [options] IMAGE command...`` with a case directory mounted at
``/case`` or ``/w``. On a pod built natively as the pinned image is
(``pod_control.SOLVER_KINDS``), ``pod_phase.py`` puts this on PATH so those
tools run unchanged: ``run`` executes the command directly, in the host
directory mounted at the container working dir, with container paths in the
arguments mapped to host paths. Standard library only.

Only the images the pod plan step names (``CARBON_DOCKER_SHIM``: JSON
``{"images": [...], "identity": "...", "log": path}``) are accepted, plus the
literal ``native``; any other image, option or subcommand exits 125, so a
tool can never silently get a different environment than its plan names.
Isolation options (``--network``, ``--read-only``, ``--cpus``, ``--memory``,
``--user``, ...) are recorded and ignored: the pod is single-tenant and the
caller's own timeouts still apply. ``image inspect`` answers with the pod's
native identity, never the image's id, so a tool that records an image id
records what really ran.
"""

from __future__ import annotations

import json
import os
import sys
import time

#: Options that take a value and are recorded but have no native effect.
IGNORED_VALUE = {
    "--name",
    "--label",
    "-l",
    "--network",
    "--net",
    "--cpus",
    "--cpu-shares",
    "--cpuset-cpus",
    "--memory",
    "-m",
    "--memory-swap",
    "--pids-limit",
    "--cap-drop",
    "--cap-add",
    "--security-opt",
    "--user",
    "-u",
    "--tmpfs",
    "--ulimit",
    "--shm-size",
    "--platform",
    "--hostname",
    "--stop-timeout",
}
IGNORED_FLAG = {
    "--rm",
    "--read-only",
    "-i",
    "-t",
    "-it",
    "--init",
    "--interactive",
    "--tty",
}
#: The pinned images' working directory when a run names none.
DEFAULT_WORKDIR = "/case"


class Refused(Exception):
    pass


def config():
    return json.loads(os.environ.get("CARBON_DOCKER_SHIM", "{}"))


def accepted(image, cfg):
    return image == "native" or image in cfg.get("images", [])


def parse_run(args):
    """``docker run`` arguments -> (image, command, mounts, workdir, env, ignored)."""
    mounts, env, ignored = {}, {}, []
    workdir = entrypoint = None
    i = 0
    while i < len(args):
        arg = args[i]
        if not arg.startswith("-"):
            break
        name, eq, inline = arg.partition("=")
        if name in IGNORED_FLAG and not eq:
            ignored.append(arg)
            i += 1
            continue
        takes = {"-e", "--env", "-v", "--volume", "-w", "--workdir", "--entrypoint"}
        if name not in IGNORED_VALUE | takes:
            raise Refused(f"unsupported docker run option {arg!r}")
        if eq:
            value, i = inline, i + 1
        elif i + 1 < len(args):
            value, i = args[i + 1], i + 2
        else:
            raise Refused(f"{arg} needs a value")
        if name in IGNORED_VALUE:
            ignored.append(f"{name}={value}")
        elif name in ("-e", "--env"):
            key, has, val = value.partition("=")
            if has:
                env[key] = val
            elif key in os.environ:
                env[key] = os.environ[key]
        elif name in ("-v", "--volume"):
            parts = value.split(":")
            if len(parts) < 2 or not parts[0].startswith("/"):
                raise Refused(f"only host-path mounts are supported: {value!r}")
            mounts[parts[1].rstrip("/") or "/"] = parts[0]
        elif name in ("-w", "--workdir"):
            workdir = value
        else:
            entrypoint = value
    if i >= len(args):
        raise Refused("docker run needs an image")
    image, command = args[i], args[i + 1 :]
    if entrypoint:
        command = [entrypoint, *command]
    if not command:
        raise Refused("a native run needs an explicit command")
    return image, command, mounts, workdir, env, ignored


def host_path(path, mounts):
    """The host path for a container path under a mount, else None."""
    for target in sorted(mounts, key=len, reverse=True):
        if path == target or path.startswith(target.rstrip("/") + "/"):
            return mounts[target] + path[len(target) :]
    return None


def plan_run(args, cfg):
    image, command, mounts, workdir, env, ignored = parse_run(args)
    if not accepted(image, cfg):
        raise Refused(
            f"image {image!r} is not provided natively on this pod "
            f"(accepted: native, {', '.join(cfg.get('images', [])) or 'nothing else'})"
        )
    wd = workdir or DEFAULT_WORKDIR
    cwd = host_path(wd, mounts)
    if cwd is None:
        raise Refused(f"working dir {wd!r} is not inside a mounted host directory")
    mapped = [host_path(a, mounts) or a for a in command]
    return {
        "image": image,
        "argv": mapped,
        "cwd": cwd,
        "env": env,
        "ignored": ignored,
        "mounts": mounts,
    }


def log(cfg, record):
    path = cfg.get("log")
    if path:
        with open(path, "a") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")


def inspect(args, cfg):
    refs = [a for a in args if not a.startswith("-")]
    fmt = ""
    if "--format" in args:
        fmt = args[args.index("--format") + 1]
        refs.remove(fmt)
    fmt = next((a.split("=", 1)[1] for a in args if a.startswith("--format=")), fmt)
    refs = [r for r in refs if r not in ("linux/amd64",)]
    if not refs or not all(accepted(r, cfg) for r in refs):
        print(f"Error: No such image: {' '.join(refs)}", file=sys.stderr)
        return 1
    identity = cfg.get("identity", "native")
    doc = {"Id": identity, "RepoDigests": [], "native_environment": identity}
    for _ in refs:
        print(json.dumps(doc) if "json" in fmt or not fmt else identity)
    return 0


def main(argv):
    cfg = config()
    try:
        if argv[:1] == ["run"]:
            run = plan_run(argv[1:], cfg)
            log(cfg, {"utc": time.time(), "event": "run", **run})
            os.chdir(run["cwd"])
            os.execvpe(run["argv"][0], run["argv"], {**os.environ, **run["env"]})
        if argv[:2] == ["image", "inspect"] or argv[:1] == ["inspect"]:
            rest = argv[2:] if argv[0] == "image" else argv[1:]
            return inspect(rest, cfg)
        raise Refused(f"unsupported docker command {' '.join(argv[:2])!r}")
    except Refused as exc:
        log(
            cfg, {"utc": time.time(), "event": "refused", "argv": argv, "why": str(exc)}
        )
        print(f"docker (native shim): {exc}", file=sys.stderr)
        return 125


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
