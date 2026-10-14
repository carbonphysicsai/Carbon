# Carbon exam-design pod bootstrap. Runs as the pod's start command, stdlib only.
#
# Execution class: public/synthetic DEVELOPMENT research, direct execution inside
# the pinned study image plus a hash-locked wheel overlay; not validator_launch;
# containment from the provider's runtime. It is not validator isolation
# acceptance.
#
# 1. Serves GET /status, GET /out.tar.gz, GET /files and GET /file/<path>, and only
#    with the matching X-Probe-Token header; everything else is 404. /out.tar.gz is
#    the results directory, /files lists its regular files with sha256 and
#    /file/<path> serves one of them, so a large result can be fetched file by file.
#    It holds campaign records only - no credential, environment or filesystem path
#    outside it is served. The only writes over HTTP, both with the token, are
#    POST /go (the A40 barrier and CPU operator-start gate) and, for a job that
#    declares inputs, POST
#    /input/<path>: one declared input file, whose size and sha256 are pinned in
#    INPUTS_MANIFEST_GZ_B64, written under INPUT_DIR. Anything else is refused.
# 2. Fetches the Carbon files named in CODE_MANIFEST (or CODE_MANIFEST_GZ_B64, the
#    same JSON gzipped, for a manifest that ships the whole carbon/ package) from the
#    public repository at CODE_REF and refuses any whose sha256 differs.
# 3. Installs the wheel overlay named by OVERLAY_LOCK (a path inside the verified
#    code), refusing any wheel whose sha256 differs from the lock.
# 4. Runs the phase and records its exit.
# 5. At PROBE_DEADLINE asks RunPod to terminate this pod with the pod-scoped key.
import base64
import concurrent.futures
import gzip
import hashlib
import hmac
import http.server
import io
import json
import os
import ssl
import subprocess
import sys
import tarfile
import threading
import time
import urllib.request
import zipfile
from pathlib import Path

TOKEN = os.environ.pop("PROBE_TOKEN", "")
DEADLINE = float(os.environ.pop("PROBE_DEADLINE", "0"))
OPERATOR_START_GATE = os.environ.pop("OPERATOR_START_GATE", "") == "1"
CA = (
    gzip.decompress(base64.b64decode(os.environ.pop("PROBE_CA_GZ_B64", ""))).decode()
    if os.environ.get("PROBE_CA_GZ_B64")
    else ""
)
CODE_REF = os.environ.get("CODE_REF", "")
MANIFEST_TRANSPORT = os.environ.get("CODE_MANIFEST_TRANSPORT", "")
MANIFEST_UPLOAD = "authenticated-upload-v1"
MANIFEST_UPLOAD_LIMIT = 1 << 20
MANIFEST_READY = threading.Event()
MANIFEST = (
    {}
    if MANIFEST_TRANSPORT
    else json.loads(
        gzip.decompress(base64.b64decode(os.environ["CODE_MANIFEST_GZ_B64"])).decode()
        if os.environ.get("CODE_MANIFEST_GZ_B64")
        else os.environ.get("CODE_MANIFEST", "{}")
    )
)
PHASE = os.environ.get("PHASE", "")
# The module run as the phase: the exam-design runner unless a campaign names
# its own (the challenge pools run scripts.dev.challenge_pools.pod_phase).
PHASE_MODULE = os.environ.get("PHASE_MODULE", "scripts.dev.exam_design.runner")
# A CPU pod's shell start command carries this file in CARBON_BOOT; it is not
# passed on to the phase.
os.environ.pop("CARBON_BOOT", None)
ROOT, OVL, OUT = "/tmp/carbon", "/tmp/overlay", "/tmp/out"
# A shared pod job's uploaded inputs (`carbon.agent_campaign.pod_jobs`): {path:
# {"sha256", "bytes"}}. Empty for every other campaign, whose behaviour is unchanged.
INPUTS = json.loads(
    gzip.decompress(base64.b64decode(os.environ.pop("INPUTS_MANIFEST_GZ_B64"))).decode()
    if os.environ.get("INPUTS_MANIFEST_GZ_B64")
    else "{}"
)
INPUT_DIR = os.environ.get("INPUT_DIR", "/tmp/inputs")
MAX_INPUT_BYTES = max([v["bytes"] for v in INPUTS.values()] + [0])
RECEIVED = set()
GO_FILE = os.environ.get("GO_FILE", "/tmp/carbon-go")
CTX = ssl.create_default_context(cadata=CA) if CA else ssl.create_default_context()
STATE = {
    "schema": "carbon.exam-design.pod-status.v1",
    "stage": "starting",
    "code_ref": CODE_REF,
    "phase": PHASE,
    "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "deadline_epoch": DEADLINE,
}
os.makedirs(OUT, exist_ok=True)


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def fetch(url, tries=4):
    for i in range(tries):
        try:
            return urllib.request.urlopen(url, context=CTX, timeout=120).read()
        except Exception as e:  # noqa: BLE001 -- failure is typed
            err = e
            time.sleep(2**i)
    raise RuntimeError(f"fetch failed {url}: {err!r}")


def self_terminate():
    key, pod = os.environ.get("RUNPOD_API_KEY", ""), os.environ.get("RUNPOD_POD_ID", "")
    if not (key and pod):
        return "unavailable"
    try:
        q = json.dumps(
            {"query": 'mutation { podTerminate(input: {podId: "' + pod + '"}) }'}
        ).encode()
        req = urllib.request.Request(
            "https://api.runpod.io/graphql",
            data=q,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer " + key,
                "User-Agent": "carbon-exam-design/1",
            },
        )
        return (
            urllib.request.urlopen(req, context=CTX, timeout=30).read()[:200].decode()
        )
    except Exception as e:  # noqa: BLE001 -- failure is typed
        return "failed: " + repr(e)[:200]


def watchdog():
    while DEADLINE and time.time() < DEADLINE:
        time.sleep(5)
    if DEADLINE:
        STATE["self_terminate"] = self_terminate()


def status_doc():
    doc = dict(STATE)
    try:
        doc["progress"] = json.loads(
            Path(os.path.join(OUT, "progress.json")).read_text()
        )
    except Exception:  # noqa: BLE001, S110 -- failure is typed
        pass
    return doc


def out_files():
    """Every regular file under OUT (no symlink), with size and sha256."""
    rows = []
    for dirpath, dirnames, filenames in os.walk(OUT):
        dirnames.sort()
        for name in sorted(filenames):
            path = os.path.join(dirpath, name)
            if os.path.islink(path) or not os.path.isfile(path):
                continue
            data = Path(path).read_bytes()
            rows.append(
                {
                    "path": os.path.relpath(path, OUT),
                    "size": len(data),
                    "sha256": hashlib.sha256(data).hexdigest(),
                }
            )
    return rows


def out_file(rel):
    """One regular file under OUT, or None: no absolute path, no '..', no link."""
    parts = rel.split("/")
    if not rel or rel.startswith("/") or any(p in ("", ".", "..") for p in parts):
        return None
    path = os.path.join(OUT, *parts)
    real = os.path.realpath(path)
    if os.path.islink(path) or not real.startswith(os.path.realpath(OUT) + os.sep):
        return None
    return Path(real).read_bytes() if os.path.isfile(real) else None


class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        ok = TOKEN and hmac.compare_digest(self.headers.get("X-Probe-Token", ""), TOKEN)
        data = (
            out_file(self.path[len("/file/") :])
            if ok and self.path.startswith("/file/")
            else None
        )
        if ok and self.path == "/status":
            body, ctype = json.dumps(status_doc()).encode(), "application/json"
        elif ok and self.path == "/files":
            body, ctype = json.dumps(out_files()).encode(), "application/json"
        elif data is not None:
            body, ctype = data, "application/octet-stream"
        elif ok and self.path == "/out.tar.gz":
            buf = io.BytesIO()
            with tarfile.open(fileobj=buf, mode="w:gz") as tf:
                tf.add(OUT, arcname="out")
            body, ctype = buf.getvalue(), "application/gzip"
        else:
            body, ctype = b"not found", "text/plain"
            self.send_response(404)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        """POST /go with the matching token drops a marker file outside the
        served results directory (the A40 acceptance barrier). POST
        /input/<path> with the token writes one declared input (`receive`).
        Any other POST is 404 as before."""
        token = TOKEN and hmac.compare_digest(
            self.headers.get("X-Probe-Token", ""), TOKEN
        )
        # The body is read before any answer (at most one declared file's
        # size, else a small limit), so a refused request ends cleanly.
        limit = (
            manifest_upload_size()
            if token
            and self.path == "/code-manifest"
            and MANIFEST_TRANSPORT == MANIFEST_UPLOAD
            else (
                MAX_INPUT_BYTES
                if token and self.path.startswith("/input/")
                else 1 << 20
            )
        )
        body = read_body(self.headers, self.rfile, limit)
        if body is None:
            self.close_connection = True
        if (
            token
            and self.path == "/code-manifest"
            and MANIFEST_TRANSPORT == MANIFEST_UPLOAD
        ):
            if body is None:
                STATE["manifest_refusal"] = "code_manifest_anchor_mismatch"
                code = 409
            else:
                code = receive_manifest(body)
        elif token and body is not None and self.path.startswith("/input/"):
            code = receive(self.path[len("/input/") :], body)
        elif token and self.path == "/go":
            Path(GO_FILE).write_text("go")
            code = 200
        else:
            code = 404
        self.send_response(code)
        self.send_header("Content-Length", "0")
        self.end_headers()

    do_HEAD = do_PUT = do_DELETE = lambda self: (
        self.send_response(404),
        self.end_headers(),
    )

    def log_message(self, *a):
        pass


def read_body(headers, stream, limit):
    """The request body, or None when its length is missing, invalid or over
    `limit` (the connection is then closed rather than read)."""
    try:
        length = int(headers.get("Content-Length", "0"))
    except ValueError:
        return None
    if not 0 <= length <= limit:
        return None
    body = stream.read(length)
    return body if len(body) == length else None


def manifest_upload_size():
    """Malformed declarations cannot turn a body read into an unbounded read."""
    try:
        size = int(os.environ.get("CODE_MANIFEST_BYTES", "0"))
    except ValueError:
        return 0
    return size if 0 < size <= MANIFEST_UPLOAD_LIMIT else 0


def receive_manifest(body):
    """Receive only the create-request-pinned document; never execute its data."""
    global MANIFEST
    if MANIFEST_TRANSPORT != MANIFEST_UPLOAD:
        return 404
    want = os.environ.get("CODE_MANIFEST_SHA256", "")
    if len(body) != manifest_upload_size() or hashlib.sha256(body).hexdigest() != want:
        STATE["manifest_refusal"] = "code_manifest_anchor_mismatch"
        return 409
    try:
        document = json.loads(body)
        if type(document) is not dict or not document:
            raise ValueError
        for path, sha in document.items():
            if (
                type(path) is not str
                or path.startswith("/")
                or "\\" in path
                or {"", ".", ".."} & set(path.split("/"))
                or type(sha) is not str
                or len(sha) != 64
                or any(c not in "0123456789abcdef" for c in sha)
            ):
                raise ValueError
    except (ValueError, TypeError, UnicodeError, RecursionError):
        STATE["manifest_refusal"] = "code_manifest_document_invalid"
        return 409
    MANIFEST = document
    MANIFEST_READY.set()
    return 200


def wait_for_manifest():
    """No code fetch/import until the uploaded manifest matches the request."""
    if not MANIFEST_TRANSPORT:
        return
    if (
        MANIFEST_TRANSPORT != MANIFEST_UPLOAD
        or not manifest_upload_size()
        or len(os.environ.get("CODE_MANIFEST_SHA256", "")) != 64
        or any(c not in "0123456789abcdef" for c in os.environ["CODE_MANIFEST_SHA256"])
        or os.environ.get("CODE_MANIFEST")
        or os.environ.get("CODE_MANIFEST_GZ_B64")
    ):
        raise RuntimeError("code_manifest_anchor_invalid")
    STATE["stage"] = "waiting_code_manifest"
    while True:
        if DEADLINE and time.time() >= DEADLINE:
            raise RuntimeError("code_manifest_deadline_expired")
        if MANIFEST_READY.wait(timeout=2):
            if DEADLINE and time.time() >= DEADLINE:
                raise RuntimeError("code_manifest_deadline_expired")
            return


def receive(rel, body):
    """One declared input: its size and sha256 checked, then written under
    INPUT_DIR. 404 for an undeclared path, 409 for a size or digest that
    differs (nothing written). A file already received is accepted again only
    with the same bytes."""
    want = INPUTS.get(rel)
    parts = rel.split("/")
    if (
        want is None
        or rel.startswith("/")
        or "\\" in rel
        or {"", ".", ".."} & set(parts)
    ):
        return 404
    if len(body) != want["bytes"] or hashlib.sha256(body).hexdigest() != want["sha256"]:
        return 409
    path = os.path.join(INPUT_DIR, *rel.split("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    partial = path + ".partial"
    Path(partial).write_bytes(body)
    os.replace(partial, path)
    RECEIVED.add(rel)
    return 200


def wait_for_inputs():
    """Until every declared input has arrived, or the deadline."""
    STATE["stage"] = "waiting_inputs"
    STATE["inputs"] = {"declared": len(INPUTS), "received": 0}
    while len(RECEIVED) < len(INPUTS):
        if DEADLINE and time.time() > DEADLINE:
            raise RuntimeError("inputs incomplete at the deadline")
        STATE["inputs"]["received"] = len(RECEIVED)
        time.sleep(2)
    STATE["inputs"]["received"] = len(RECEIVED)


def wait_for_operator_start():
    """Hold the job phase until the operator explicitly releases its gate."""
    if not OPERATOR_START_GATE:
        return
    STATE["stage"] = "waiting_for_operator"
    STATE["operator_start_gate"] = "waiting"
    while not os.path.isfile(GO_FILE):
        if DEADLINE and time.time() >= DEADLINE:
            raise RuntimeError("operator start gate was not released before deadline")
        time.sleep(2)
    STATE["operator_start_gate"] = "released"


def install_overlay(lock_path, target):
    lock = json.loads(Path(lock_path).read_text())
    os.makedirs(target, exist_ok=True)
    for w in lock["wheels"]:
        data = fetch(w["url"])
        if hashlib.sha256(data).hexdigest() != w["sha256"]:
            raise RuntimeError(f"wheel hash mismatch: {w['filename']}")
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            for n in z.namelist():
                parts = n.split("/")
                if parts[0].endswith(".data"):
                    if len(parts) > 2 and parts[1] in ("purelib", "platlib"):
                        dst = os.path.join(target, *parts[2:])
                    else:
                        continue  # scripts/headers are not needed
                else:
                    dst = os.path.join(target, n)
                if n.endswith("/"):
                    continue
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                with open(dst, "wb") as f:
                    f.write(z.read(n))
                # Keep the wheel's recorded mode: bundled executables (imageio-ffmpeg's ffmpeg)
                # must stay executable, not only shared libraries.
                mode = (z.getinfo(n).external_attr >> 16) & 0o777
                if mode & 0o111 or dst.endswith(".so") or ".so." in dst:
                    os.chmod(dst, 0o755)
    return {
        "wheels": len(lock["wheels"]),
        "lock_sha256": hashlib.sha256(Path(lock_path).read_bytes()).hexdigest(),
    }


def main():
    threading.Thread(target=watchdog, daemon=True).start()
    srv = http.server.ThreadingHTTPServer(("0.0.0.0", 8000), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        wait_for_manifest()
        STATE["stage"] = "fetching_code"

        def fetch_verified(item):
            path, sha = item
            data = fetch(
                f"https://raw.githubusercontent.com/carbonphysicsai/Carbon/{CODE_REF}/{path}"
            )
            if hashlib.sha256(data).hexdigest() != sha:
                raise RuntimeError(f"code hash mismatch: {path}")
            return path, data

        # Every file is verified before any is written, and nothing is imported
        # until all are written.
        with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
            fetched = list(pool.map(fetch_verified, sorted(MANIFEST.items())))
        for path, data in fetched:
            dst = os.path.join(ROOT, path)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            Path(dst).write_bytes(data)
        STATE["code_files"] = len(MANIFEST)
        # OVERLAYS: {"name": "path/to/lock.json"}; each lock installs into its own directory, because
        # two locks may pin one package differently (xarray differs between battery and photonic).
        overlays = json.loads(os.environ.get("OVERLAYS", "{}"))
        STATE["overlay"] = {}
        for name, lock in overlays.items():
            STATE["stage"] = f"installing_overlay:{name}"
            t = time.time()
            STATE["overlay"][name] = install_overlay(
                os.path.join(ROOT, lock), os.path.join(OVL, name)
            ) | {"seconds": round(time.time() - t, 1)}
        if INPUTS:
            wait_for_inputs()
        wait_for_operator_start()
        STATE["stage"] = "running_phase"
        env = {
            k: v
            for k, v in os.environ.items()
            if k != "RUNPOD_API_KEY" and not k.startswith("CODE_MANIFEST")
        }
        # A single overlay goes on the path directly; a multi-phase run gives each child its own.
        single = [os.path.join(OVL, n) for n in overlays] if len(overlays) == 1 else []
        env["PYTHONPATH"] = ":".join(
            p for p in (ROOT, *single, env.get("PYTHONPATH", "")) if p
        )
        env["OVERLAY_ROOT"] = OVL
        if INPUTS:
            env["INPUTS_DIR"] = INPUT_DIR
        env["PYBAMM_DISABLE_TELEMETRY"] = "true"
        env["HOME"] = "/tmp"
        env.setdefault("XLA_PYTHON_CLIENT_PREALLOCATE", "false")
        env.setdefault(
            "JAX_ENABLE_COMPILATION_CACHE", "false"
        )  # the image points the cache at an unwritable /scratch
        # Numerical libraries size thread pools to every visible core (96 on some hosts) regardless of
        # the pod's CPU share; the pilot found 6 workers thrashing to ~1/10 speed without this.
        env.setdefault("OMP_NUM_THREADS", "1")
        env.setdefault("OPENBLAS_NUM_THREADS", "1")
        env["MPLCONFIGDIR"] = "/tmp/mpl"
        # The image points TMPDIR at /scratch/tmp, which is not writable; JAX's GPU compiler (ptxas) writes its
        # temporaries there and every GPU compile failed on the first GPU pod. Only /tmp is writable.
        os.makedirs("/tmp/tmpdir", exist_ok=True)
        for var in ("TMPDIR", "TMP", "TEMP"):
            env[var] = "/tmp/tmpdir"
        with open(os.path.join(OUT, "phase.log"), "wb") as log:
            rc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    PHASE_MODULE,
                    PHASE,
                    "--out",
                    OUT,
                ],
                cwd=ROOT,
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
                check=False,
            ).returncode
        STATE["phase_exit"] = rc
        STATE["stage"] = "done" if rc == 0 else "phase_failed"
    except Exception as e:  # noqa: BLE001 -- failure is typed
        STATE["stage"] = "bootstrap_failed"
        STATE["error"] = repr(e)[:500]
    STATE["finished_utc"] = now()
    while True:
        time.sleep(60)


if __name__ == "__main__":
    main()
