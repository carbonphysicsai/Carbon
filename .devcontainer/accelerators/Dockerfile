# syntax=docker/dockerfile:1
ARG WORKER_IMAGE_REF
FROM ghcr.io/astral-sh/uv:0.12.7@sha256:95f2aa1fe59274951cfe9b0cbc7972e879ff1004bc8945d130a32eb0dbd85945 AS uv
FROM ${WORKER_IMAGE_REF}
ARG WORKER_IMAGE
ARG ACCELERATOR_RECIPE_DIGEST
ARG ACCELERATOR_PROFILE_DIGEST
ARG ACCELERATOR_LOCK_DIGEST
USER root
COPY --from=uv /uv /tmp/uv
COPY .devcontainer/accelerators/cuda13-py311.txt /opt/carbon/accelerator-requirements.txt
RUN test "sha256:$(sha256sum /opt/carbon/accelerator-requirements.txt | cut -d' ' -f1)" = "${ACCELERATOR_LOCK_DIGEST}" \
    && chmod -R u+w /opt/carbon-worker \
    && /tmp/uv pip install --python /opt/carbon-worker/bin/python --require-hashes --only-binary=:all: --no-deps -r /opt/carbon/accelerator-requirements.txt \
    && rm /tmp/uv
RUN WORKER_IMAGE="${WORKER_IMAGE}" ACCELERATOR_RECIPE_DIGEST="${ACCELERATOR_RECIPE_DIGEST}" ACCELERATOR_PROFILE_DIGEST="${ACCELERATOR_PROFILE_DIGEST}" ACCELERATOR_LOCK_DIGEST="${ACCELERATOR_LOCK_DIGEST}" /opt/carbon-worker/bin/python -I - <<'PY'
import json
import os
import pathlib
import re
from carbon.reconstruction.accelerators import GPU_PROFILE

for key in ("WORKER_IMAGE", "ACCELERATOR_RECIPE_DIGEST", "ACCELERATOR_PROFILE_DIGEST", "ACCELERATOR_LOCK_DIGEST"):
    if not re.fullmatch(r"sha256:[a-f0-9]{64}", os.environ[key]):
        raise SystemExit("Exact immutable image identities required")
if os.environ["ACCELERATOR_PROFILE_DIGEST"] != GPU_PROFILE.digest or os.environ["ACCELERATOR_LOCK_DIGEST"] != GPU_PROFILE.environment_lock_digest:
    raise SystemExit("Installed source and accelerator environment differ")
path = pathlib.Path("/opt/carbon/worker-image-build.json")
document = json.loads(path.read_text())
document.update(base_image_digest=os.environ["WORKER_IMAGE"],
                build_recipe_digest=os.environ["ACCELERATOR_RECIPE_DIGEST"],
                lock_digest=os.environ["ACCELERATOR_LOCK_DIGEST"])
path.chmod(0o600)
path.write_text(json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n")
PY
RUN chmod -R a-w /opt/carbon-worker /opt/carbon
LABEL org.opencontainers.image.title="Carbon fixed NVIDIA DEVELOPMENT reconstruction worker" \
      org.opencontainers.image.description="Unqualified GPU worker; private host admission required" \
      org.opencontainers.image.carbon.c03.base-image="${WORKER_IMAGE}" \
      org.opencontainers.image.carbon.c03.build-recipe="${ACCELERATOR_RECIPE_DIGEST}" \
      org.opencontainers.image.carbon.c03.lock="${ACCELERATOR_LOCK_DIGEST}" \
      org.opencontainers.image.carbon.accelerator.profile="${ACCELERATOR_PROFILE_DIGEST}" \
      org.opencontainers.image.carbon.accelerator.environment="${ACCELERATOR_LOCK_DIGEST}"
USER 65532:65532
# The fixed C03 entrypoint waits for admission before numerical initialization.
