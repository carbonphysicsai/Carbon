# Carbon exam-design pod bootstrap. Runs as the pod's start command, stdlib only.
#
# Execution class: public/synthetic DEVELOPMENT research, direct execution inside
# the pinned study image plus a hash-locked wheel overlay; not validator_launch;
# containment from the provider's runtime. It is not validator isolation
# acceptance.
#
# 1. Serves GET /status and GET /out.tar.gz, and only with the matching
#    X-Probe-Token header; everything else is 404. /out.tar.gz is the results
#    directory, which holds campaign records only - no credential, environment or
#    filesystem path outside it is served, and nothing is writable over HTTP.
# 2. Fetches the Carbon files named in CODE_MANIFEST from the public repository at
#    CODE_REF and refuses any whose sha256 differs.
# 3. Installs the wheel overlay named by OVERLAY_LOCK (a path inside the verified
#    code), refusing any wheel whose sha256 differs from the lock.
# 4. Runs the phase and records its exit.
# 5. At PROBE_DEADLINE asks RunPod to terminate this pod with the pod-scoped key.
import base64, gzip, hashlib, hmac, http.server, io, json, os, ssl, subprocess, sys, tarfile, threading, time
import urllib.request, zipfile

TOKEN = os.environ.pop("PROBE_TOKEN", "")
DEADLINE = float(os.environ.pop("PROBE_DEADLINE", "0"))
CA = gzip.decompress(base64.b64decode(os.environ.pop("PROBE_CA_GZ_B64", ""))).decode() if os.environ.get("PROBE_CA_GZ_B64") else ""
CODE_REF = os.environ.get("CODE_REF", "")
MANIFEST = json.loads(os.environ.get("CODE_MANIFEST", "{}"))
PHASE = os.environ.get("PHASE", "")
ROOT, OVL, OUT = "/tmp/carbon", "/tmp/overlay", "/tmp/out"
CTX = ssl.create_default_context(cadata=CA) if CA else ssl.create_default_context()
STATE = {"schema": "carbon.exam-design.pod-status.v1", "stage": "starting", "code_ref": CODE_REF, "phase": PHASE,
         "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "deadline_epoch": DEADLINE}
os.makedirs(OUT, exist_ok=True)


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def fetch(url, tries=4):
    for i in range(tries):
        try:
            return urllib.request.urlopen(url, context=CTX, timeout=120).read()
        except Exception as e:  # noqa: PERF203
            err = e
            time.sleep(2 ** i)
    raise RuntimeError(f"fetch failed {url}: {err!r}")


def self_terminate():
    key, pod = os.environ.get("RUNPOD_API_KEY", ""), os.environ.get("RUNPOD_POD_ID", "")
    if not (key and pod):
        return "unavailable"
    try:
        q = json.dumps({"query": 'mutation { podTerminate(input: {podId: "%s"}) }' % pod}).encode()
        req = urllib.request.Request("https://api.runpod.io/graphql", data=q, method="POST",
                                     headers={"Content-Type": "application/json", "Authorization": "Bearer " + key,
                                              "User-Agent": "carbon-exam-design/1"})
        return urllib.request.urlopen(req, context=CTX, timeout=30).read()[:200].decode()
    except Exception as e:
        return "failed: " + repr(e)[:200]


def watchdog():
    while DEADLINE and time.time() < DEADLINE:
        time.sleep(5)
    if DEADLINE:
        STATE["self_terminate"] = self_terminate()


def status_doc():
    doc = dict(STATE)
    try:
        doc["progress"] = json.load(open(os.path.join(OUT, "progress.json")))
    except Exception:
        pass
    return doc


class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        ok = TOKEN and hmac.compare_digest(self.headers.get("X-Probe-Token", ""), TOKEN)
        if ok and self.path == "/status":
            body, ctype = json.dumps(status_doc()).encode(), "application/json"
        elif ok and self.path == "/out.tar.gz":
            buf = io.BytesIO()
            with tarfile.open(fileobj=buf, mode="w:gz") as tf:
                tf.add(OUT, arcname="out")
            body, ctype = buf.getvalue(), "application/gzip"
        else:
            body, ctype = b"not found", "text/plain"
            self.send_response(404)
            self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
            return
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)

    do_HEAD = do_POST = do_PUT = do_DELETE = lambda self: (self.send_response(404), self.end_headers())

    def log_message(self, *a):
        pass


def install_overlay(lock_path):
    lock = json.load(open(lock_path))
    os.makedirs(OVL, exist_ok=True)
    for w in lock["wheels"]:
        data = fetch(w["url"])
        if hashlib.sha256(data).hexdigest() != w["sha256"]:
            raise RuntimeError(f"wheel hash mismatch: {w['filename']}")
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            for n in z.namelist():
                parts = n.split("/")
                if parts[0].endswith(".data"):
                    if len(parts) > 2 and parts[1] in ("purelib", "platlib"):
                        target = os.path.join(OVL, *parts[2:])
                    else:
                        continue  # scripts/headers are not needed
                else:
                    target = os.path.join(OVL, n)
                if n.endswith("/"):
                    continue
                os.makedirs(os.path.dirname(target), exist_ok=True)
                with open(target, "wb") as f:
                    f.write(z.read(n))
                if target.endswith(".so") or ".so." in target:
                    os.chmod(target, 0o755)
    return {"wheels": len(lock["wheels"]), "lock_sha256": hashlib.sha256(open(lock_path, "rb").read()).hexdigest()}


def main():
    threading.Thread(target=watchdog, daemon=True).start()
    srv = http.server.ThreadingHTTPServer(("0.0.0.0", 8000), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        STATE["stage"] = "fetching_code"
        for path, sha in MANIFEST.items():
            data = fetch(f"https://raw.githubusercontent.com/carbonphysicsai/Carbon/{CODE_REF}/{path}")
            if hashlib.sha256(data).hexdigest() != sha:
                raise RuntimeError(f"code hash mismatch: {path}")
            dst = os.path.join(ROOT, path)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            open(dst, "wb").write(data)
        STATE["code_files"] = len(MANIFEST)
        lock = os.environ.get("OVERLAY_LOCK", "")
        if lock:
            STATE["stage"] = "installing_overlay"
            t = time.time()
            STATE["overlay"] = install_overlay(os.path.join(ROOT, lock)) | {"seconds": round(time.time() - t, 1)}
        STATE["stage"] = "running_phase"
        env = {k: v for k, v in os.environ.items() if k not in ("RUNPOD_API_KEY", "CODE_MANIFEST")}
        env["PYTHONPATH"] = ":".join(p for p in (ROOT, OVL, env.get("PYTHONPATH", "")) if p)
        env["PYBAMM_DISABLE_TELEMETRY"] = "true"
        env["HOME"] = "/tmp"
        env["MPLCONFIGDIR"] = "/tmp/mpl"
        with open(os.path.join(OUT, "phase.log"), "wb") as log:
            rc = subprocess.run([sys.executable, "-m", "scripts.dev.exam_design.runner", PHASE, "--out", OUT],
                                cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT).returncode
        STATE["phase_exit"] = rc
        STATE["stage"] = "done" if rc == 0 else "phase_failed"
    except Exception as e:
        STATE["stage"] = "bootstrap_failed"
        STATE["error"] = repr(e)[:500]
    STATE["finished_utc"] = now()
    while True:
        time.sleep(60)


if __name__ == "__main__":
    main()
