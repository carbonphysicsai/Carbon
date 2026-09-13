# syntax=docker/dockerfile:1

FROM ghcr.io/astral-sh/uv:0.12.7@sha256:95f2aa1fe59274951cfe9b0cbc7972e879ff1004bc8945d130a32eb0dbd85945 AS uv

FROM ubuntu:24.04@sha256:33ceb71981b602c1a7443a53469e4dba065f7503eab3078a2d7a57a2ab987517

ARG DEBIAN_FRONTEND=noninteractive
ARG PYTHON_VERSION=3.11.16
ARG CARBON_SOURCE_REVISION

ENV UV_PYTHON_INSTALL_DIR=/opt/uv-python \
    UV_PYTHON_DOWNLOADS=automatic \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/carbon/.venv \
    VIRTUAL_ENV=/opt/carbon/.venv \
    HOME=/nonexistent \
    PATH=/opt/carbon/.venv/bin:/usr/local/bin:/usr/bin:/bin \
    JAX_PLATFORMS=cpu \
    JAX_ENABLE_X64=0 \
    OMP_NUM_THREADS=1 \
    OPENBLAS_NUM_THREADS=1 \
    MKL_NUM_THREADS=1 \
    TF_CPP_MIN_LOG_LEVEL=3 \
    WANDB_MODE=disabled \
    HF_HUB_OFFLINE=1 \
    CARBON_C03_WORKER=1

RUN test -n "${CARBON_SOURCE_REVISION}" \
    && apt-get update \
    && apt-get install --yes --no-install-recommends ca-certificates libc6 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 carbonworker \
    && useradd --uid 10001 --gid 10001 --no-create-home --home-dir /nonexistent --shell /usr/sbin/nologin carbonworker

COPY --from=uv /uv /uvx /usr/local/bin/
WORKDIR /opt/carbon
COPY --chown=0:0 . /opt/carbon
RUN uv python install "${PYTHON_VERSION}" \
    && uv sync --locked --no-dev --group science-jax --python "${PYTHON_VERSION}" \
    && rm -rf /root/.cache /opt/carbon/.git /opt/carbon/.carbon-artifacts \
    && find /opt/carbon -xdev -type d -exec chmod 0555 {} + \
    && find /opt/carbon -xdev -type f -exec chmod 0444 {} + \
    && find /opt/carbon/.venv/bin -maxdepth 1 -type f -exec chmod 0555 {} +

LABEL org.opencontainers.image.title="Carbon C-03 CPU development reconstruction worker" \
      org.opencontainers.image.source="https://github.com/carbonphysicsai/Carbon" \
      org.opencontainers.image.carbon.worker-profile="carbon_c03_cpu_development_v1" \
      org.opencontainers.image.carbon.source-revision="${CARBON_SOURCE_REVISION}" \
      org.opencontainers.image.carbon.security-state="REVIEWABLE_NOT_SECURITY_ACCEPTED"

USER 10001:10001
WORKDIR /scratch
ENTRYPOINT ["/opt/carbon/.venv/bin/python", "-I", "-m", "carbon.reconstruction.worker_entrypoint"]
