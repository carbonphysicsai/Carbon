# Carbon RunPod connectivity probe. Runs as the pod's start command.
# Serves exactly one path, GET /status, and only with the matching X-Probe-Token
# header; every other request gets 404. It exposes no filesystem, environment,
# credential or control interface. It does no training and runs no study code.
# Fallback lifetime bound: at PROBE_DEADLINE (epoch s) it asks RunPod to
# terminate this pod using the pod-scoped RUNPOD_API_KEY that RunPod injects.
import ctypes
import hmac
import http.server
import json
import os
import ssl
import subprocess
import sys
import threading
import time
import urllib.request

TOKEN = os.environ.pop("PROBE_TOKEN", "")
DEADLINE = float(os.environ.pop("PROBE_DEADLINE", "0"))
CA = os.environ.pop("PROBE_CA", "")
STATUS = {
    "schema": "carbon.runpod-connectivity-probe.v1",
    "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
}


def nvml():
    out = {}
    try:
        lib = ctypes.CDLL("libnvidia-ml.so.1")
        if lib.nvmlInit_v2() != 0:
            return {"error": "nvmlInit failed"}
        buf = ctypes.create_string_buffer(96)
        lib.nvmlSystemGetDriverVersion(buf, 96)
        out["driver_version"] = buf.value.decode()
        lib.nvmlSystemGetCudaDriverVersion_v2.argtypes = [ctypes.POINTER(ctypes.c_int)]
        v = ctypes.c_int()
        lib.nvmlSystemGetCudaDriverVersion_v2(ctypes.byref(v))
        out["cuda_driver"] = f"{v.value // 1000}.{(v.value % 1000) // 10}"
        n = ctypes.c_uint()
        lib.nvmlDeviceGetCount_v2(ctypes.byref(n))
        out["device_count"] = n.value
        devs = []
        for i in range(n.value):
            h = ctypes.c_void_p()
            lib.nvmlDeviceGetHandleByIndex_v2(i, ctypes.byref(h))
            lib.nvmlDeviceGetName(h, buf, 96)
            name = buf.value.decode()
            lib.nvmlDeviceGetUUID(h, buf, 96)
            devs.append({"index": i, "name": name, "uuid": buf.value.decode()})
        out["devices"] = devs
    except Exception as e:  # noqa: BLE001 -- failure is typed
        out["error"] = repr(e)
    return out


JAX = r"""
import json, jax, jaxlib
print(json.dumps({"jax": jax.__version__, "jaxlib": jaxlib.__version__, "backend": jax.default_backend(),
  "devices": [{"id": d.id, "platform": d.platform, "kind": d.device_kind} for d in jax.devices()]}))
"""


def jax_probe():
    env = {k: v for k, v in os.environ.items() if k not in ("RUNPOD_API_KEY",)}
    env.update(
        JAX_PLATFORMS="cuda",
        XLA_PYTHON_CLIENT_PREALLOCATE="false",
        JAX_ENABLE_COMPILATION_CACHE="false",
    )
    try:
        r = subprocess.run(
            [sys.executable, "-I", "-c", JAX],
            env=env,
            capture_output=True,
            text=True,
            timeout=240,
            check=False,
        )
        if r.returncode == 0:
            return json.loads(r.stdout.strip().splitlines()[-1])
        return {"error": f"exit {r.returncode}", "stderr_tail": r.stderr[-400:]}
    except Exception as e:  # noqa: BLE001 -- failure is typed
        return {"error": repr(e)}


def self_terminate():
    key, pod = os.environ.get("RUNPOD_API_KEY", ""), os.environ.get("RUNPOD_POD_ID", "")
    if not (key and pod):
        return "unavailable: no pod-scoped key or pod id"
    try:
        ctx = (
            ssl.create_default_context(cadata=CA)
            if CA
            else ssl.create_default_context()
        )
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
            urllib.request.urlopen(req, context=ctx, timeout=30).read()[:200].decode()
        )
    except Exception as e:  # noqa: BLE001 -- failure is typed
        return "failed: " + repr(e)[:200]


def watchdog():
    while DEADLINE and time.time() < DEADLINE:
        time.sleep(5)
    if DEADLINE:
        print("probe deadline reached; self-terminate:", self_terminate(), flush=True)


class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        ok = (
            self.path == "/status"
            and TOKEN
            and hmac.compare_digest(self.headers.get("X-Probe-Token", ""), TOKEN)
        )
        body = json.dumps(STATUS).encode() if ok else b"not found"
        self.send_response(200 if ok else 404)
        self.send_header("Content-Type", "application/json" if ok else "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    do_HEAD = do_POST = do_PUT = do_DELETE = lambda self: (
        self.send_response(404),
        self.end_headers(),
    )

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    threading.Thread(target=watchdog, daemon=True).start()
    STATUS.update(
        state="probing",
        pod_id=os.environ.get("RUNPOD_POD_ID"),
        python=sys.version.split()[0],
        uid=os.getuid(),
    )
    srv = http.server.ThreadingHTTPServer(
        ("0.0.0.0", int(os.environ.get("PROBE_PORT", "8000"))), H
    )
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    STATUS["nvml"] = nvml()
    STATUS["jax"] = jax_probe()
    STATUS["probe_done_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    STATUS["state"] = "done"
    print("PROBE_STATUS " + json.dumps(STATUS), flush=True)
    while True:
        time.sleep(60)
