# The electric-motor (#344) reference image: GetDP and Gmsh, pinned.
#
# Every input is pinned: the base by digest (the repository's own Ubuntu
# 24.04), system packages by a dated Ubuntu snapshot, and both solver
# tarballs by SHA-256, checked before they are unpacked. The build needs the
# network; a run never does (it runs with --network none).
#
# GetDP and Gmsh are GPL. Carbon runs them on an operator host and writes
# their input files; it does not redistribute them.

FROM ubuntu:24.04@sha256:33ceb71981b602c1a7443a53469e4dba065f7503eab3078a2d7a57a2ab987517

ARG DEBIAN_FRONTEND=noninteractive
ARG SNAPSHOT=20260930T000000Z
ARG GETDP_URL=https://getdp.info/bin/Linux/getdp-3.5.0-Linux64r.tgz
ARG GETDP_SHA256=bca39450cc6f33feac27bff1c8c3e47bb200f44679b0f03d85820def84ef1444
ARG GMSH_URL=https://gmsh.info/bin/Linux/gmsh-4.15.2-Linux64-sdk.tgz
ARG GMSH_SHA256=2dbd68d033f99b05789554bf4db6d47f4108dd36b0b36d4a50935df0ceb9e772

# The snapshot service is HTTPS-only and the base has no CA bundle, so
# ca-certificates alone comes from the archive current at build time; every
# other package comes from the dated snapshot.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && apt-get update --snapshot "${SNAPSHOT}" \
    && apt-get install -y --no-install-recommends --snapshot "${SNAPSHOT}" \
       curl libgl1 libglu1-mesa libxft2 libgomp1 libxcursor1 libxinerama1 python3 \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /opt/getdp /opt/gmsh /tmp/dl \
    && curl -sSfL -o /tmp/dl/getdp.tgz "${GETDP_URL}" \
    && curl -sSfL -o /tmp/dl/gmsh.tgz "${GMSH_URL}" \
    && echo "${GETDP_SHA256}  /tmp/dl/getdp.tgz" | sha256sum -c - \
    && echo "${GMSH_SHA256}  /tmp/dl/gmsh.tgz" | sha256sum -c - \
    && tar xzf /tmp/dl/getdp.tgz -C /opt/getdp --strip-components 1 \
    && tar xzf /tmp/dl/gmsh.tgz -C /opt/gmsh --strip-components 1 \
    && rm -rf /tmp/dl \
    && apt-get purge -y curl \
    && /opt/getdp/bin/getdp --version \
    && /opt/gmsh/bin/gmsh --version \
    && PYTHONPATH=/opt/gmsh/lib python3 -c "import gmsh; gmsh.initialize(); print('gmsh api', gmsh.option.getString('General.Version')); gmsh.finalize()"

ENV PATH=/opt/getdp/bin:/opt/gmsh/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
    PYTHONPATH=/opt/gmsh/lib \
    HOME=/tmp

LABEL org.opencontainers.image.title="Carbon electric-motor DEVELOPMENT reference" \
      org.opencontainers.image.description="GetDP 3.5.0 and Gmsh 4.15.2, pinned; no scientific qualification"
