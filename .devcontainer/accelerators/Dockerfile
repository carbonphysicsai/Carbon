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
    && TMPDIR=/tmp /tmp/uv --no-cache pip install --python /opt/carbon-worker/bin/python --require-hashes --only-binary=:all: --no-deps -r /opt/carbon/accelerator-requirements.txt \
    && rm /tmp/uv \
    && chmod -R a-w /opt/carbon-worker \
    && chmod 444 /opt/carbon/accelerator-requirements.txt
# The build identity is written by a program file, never a RUN heredoc:
# Docker's legacy builder drops a heredoc's body silently (S20).
COPY .devcontainer/accelerators/build_identity.py /tmp/carbon-build-identity.py
RUN WORKER_IMAGE="${WORKER_IMAGE}" ACCELERATOR_RECIPE_DIGEST="${ACCELERATOR_RECIPE_DIGEST}" ACCELERATOR_PROFILE_DIGEST="${ACCELERATOR_PROFILE_DIGEST}" ACCELERATOR_LOCK_DIGEST="${ACCELERATOR_LOCK_DIGEST}" /opt/carbon-worker/bin/python -I /tmp/carbon-build-identity.py \
    && rm /tmp/carbon-build-identity.py
RUN chmod -R a-w /opt/carbon
LABEL org.opencontainers.image.title="Carbon fixed NVIDIA DEVELOPMENT reconstruction worker" \
      org.opencontainers.image.description="Unqualified GPU worker; private host admission required" \
      org.opencontainers.image.carbon.c03.base-image="${WORKER_IMAGE}" \
      org.opencontainers.image.carbon.c03.build-recipe="${ACCELERATOR_RECIPE_DIGEST}" \
      org.opencontainers.image.carbon.c03.lock="${ACCELERATOR_LOCK_DIGEST}" \
      org.opencontainers.image.carbon.accelerator.profile="${ACCELERATOR_PROFILE_DIGEST}" \
      org.opencontainers.image.carbon.accelerator.environment="${ACCELERATOR_LOCK_DIGEST}"
USER 65532:65532
# Checked as the worker's own user: one line, so no builder can drop it.
RUN /opt/carbon-worker/bin/python -I -c "import hashlib, json, pathlib; from carbon.reconstruction.accelerators import GPU_PROFILE; build = json.loads(pathlib.Path('/opt/carbon/worker-image-build.json').read_bytes()); lock = pathlib.Path('/opt/carbon/accelerator-requirements.txt').read_bytes(); assert build['lock_digest'] == GPU_PROFILE.environment_lock_digest, 'GPU worker lock differs'; assert 'sha256:' + hashlib.sha256(lock).hexdigest() == build['lock_digest'], 'GPU worker lock file differs'"
# The fixed C03 entrypoint waits for admission before numerical initialization.
