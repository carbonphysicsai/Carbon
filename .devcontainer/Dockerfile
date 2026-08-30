# syntax=docker/dockerfile:1

FROM ghcr.io/astral-sh/uv:0.12.7@sha256:95f2aa1fe59274951cfe9b0cbc7972e879ff1004bc8945d130a32eb0dbd85945 AS uv

FROM ubuntu:24.04@sha256:33ceb71981b602c1a7443a53469e4dba065f7503eab3078a2d7a57a2ab987517

ARG DEBIAN_FRONTEND=noninteractive
ARG PYTHON_VERSION=3.11.16
ARG USERNAME=ubuntu
ARG USER_UID=1000
ARG USER_GID=1000

ENV UV_PYTHON_INSTALL_DIR=/opt/uv-python \
    UV_PYTHON_DOWNLOADS=automatic \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/workspaces/Carbon/.venv \
    VIRTUAL_ENV=/workspaces/Carbon/.venv \
    CARBON_CANONICAL_DEV_ENV=ubuntu-24.04-glibc-cpython-3.11.16-uv-0.12.7-amd64 \
    PATH=/workspaces/Carbon/.venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

RUN apt-get update \
    && apt-get install --yes --no-install-recommends \
        bash \
        ca-certificates \
        curl \
        git \
        libc6 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=uv /uv /uvx /usr/local/bin/

RUN uv python install "${PYTHON_VERSION}" \
    && python_path="$(uv python find "${PYTHON_VERSION}")" \
    && ln -s "${python_path}" /usr/local/bin/python3.11 \
    && ln -s "${python_path}" /usr/local/bin/python3 \
    && ln -s "${python_path}" /usr/local/bin/python \
    && [ "$(id -u "${USERNAME}")" = "${USER_UID}" ] \
    && [ "$(id -g "${USERNAME}")" = "${USER_GID}" ] \
    && mkdir -p /workspaces/Carbon \
    && chown -R "${USERNAME}:${USERNAME}" /opt/uv-python /workspaces/Carbon

LABEL org.opencontainers.image.title="Carbon canonical development environment" \
      org.opencontainers.image.description="Ubuntu 24.04, glibc, CPython 3.11.16, uv 0.12.7; B-01E development evidence only" \
      org.opencontainers.image.source="https://github.com/carbonphysicsai/Carbon"

WORKDIR /workspaces/Carbon
USER vscode

CMD ["sleep", "infinity"]
