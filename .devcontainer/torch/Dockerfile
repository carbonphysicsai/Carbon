# syntax=docker/dockerfile:1
# The PyTorch reconstruction worker (OWNER-PYTORCH-BACKEND-01, RECON-TORCH-01).
# Layered on the exact C-03 JAX worker image, so it carries the same Carbon
# wheel, entrypoint, user and JAX stack, plus the exact-hashed `science-torch`
# group exported from uv.lock (CPU wheels). Nothing here is qualified.
ARG WORKER_IMAGE_REF
FROM ghcr.io/astral-sh/uv:0.12.7@sha256:95f2aa1fe59274951cfe9b0cbc7972e879ff1004bc8945d130a32eb0dbd85945 AS uv
FROM ${WORKER_IMAGE_REF}
ARG WORKER_IMAGE
ARG TORCH_RECIPE_DIGEST
ARG TORCH_LOCK_DIGEST
ARG TORCH_DETERMINISM_DIGEST
USER root
COPY --from=uv /uv /tmp/uv
COPY .devcontainer/torch/torch-cpu-py311.txt /opt/carbon/torch-requirements.txt
RUN test "sha256:$(sha256sum /opt/carbon/torch-requirements.txt | cut -d' ' -f1)" = "${TORCH_LOCK_DIGEST}" \
    && chmod -R u+w /opt/carbon-worker \
    && TMPDIR=/tmp /tmp/uv --no-cache pip install --python /opt/carbon-worker/bin/python \
       --require-hashes --only-binary=:all: --no-deps \
       --extra-index-url https://download.pytorch.org/whl/cpu --index-strategy unsafe-best-match \
       -r /opt/carbon/torch-requirements.txt \
    && rm /tmp/uv \
    && chmod -R a-w /opt/carbon-worker \
    && chmod 444 /opt/carbon/torch-requirements.txt
RUN WORKER_IMAGE="${WORKER_IMAGE}" TORCH_RECIPE_DIGEST="${TORCH_RECIPE_DIGEST}" TORCH_LOCK_DIGEST="${TORCH_LOCK_DIGEST}" /opt/carbon-worker/bin/python -I - <<'PY'
import json
import os
import pathlib
import re

for key in ("WORKER_IMAGE", "TORCH_RECIPE_DIGEST", "TORCH_LOCK_DIGEST"):
    if not re.fullmatch(r"sha256:[a-f0-9]{64}", os.environ[key]):
        raise SystemExit("Exact immutable image identities required")
path = pathlib.Path("/opt/carbon/worker-image-build.json")
document = json.loads(path.read_text())
document.update(base_image_digest=os.environ["WORKER_IMAGE"],
                build_recipe_digest=os.environ["TORCH_RECIPE_DIGEST"],
                lock_digest=os.environ["TORCH_LOCK_DIGEST"])
path.chmod(0o600)
path.write_text(json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n")
path.chmod(0o444)
PY
RUN chmod -R a-w /opt/carbon
LABEL org.opencontainers.image.title="Carbon PyTorch DEVELOPMENT reconstruction worker" \
      org.opencontainers.image.description="Pinned CPU-only PyTorch worker on the C-03 image; no scientific or security qualification" \
      org.opencontainers.image.carbon.c03.base-image="${WORKER_IMAGE}" \
      org.opencontainers.image.carbon.c03.build-recipe="${TORCH_RECIPE_DIGEST}" \
      org.opencontainers.image.carbon.c03.lock="${TORCH_LOCK_DIGEST}" \
      org.opencontainers.image.carbon.torch.determinism="${TORCH_DETERMINISM_DIGEST}"
USER 65532:65532
# The determinism configuration is part of the image identity (IMAGE-RELEASE-01):
# the label must be the installed source's own `DETERMINISM_DIGEST`.
RUN TORCH_DETERMINISM_DIGEST="${TORCH_DETERMINISM_DIGEST}" /opt/carbon-worker/bin/python -I - <<'PY'
import importlib.metadata as metadata
import os

from carbon.reconstruction.torch_profile import DETERMINISM_DIGEST, PINS

for name, version, _ in PINS:
    installed = metadata.version(name).split("+")[0]
    if installed != version:
        raise SystemExit(f"{name} {installed} is not the pinned {version}")
if os.environ["TORCH_DETERMINISM_DIGEST"] != DETERMINISM_DIGEST:
    raise SystemExit("the determinism label is not the installed source's configuration")
PY
