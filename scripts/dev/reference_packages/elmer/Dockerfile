# REFERENCE-PACKAGES-01: Elmer 26.2.1, serial, from the upstream release
# archive (checksum verified by build.sh before the build) on a pinned
# Debian base with packages from a dated snapshot. No network at solve time.
ARG BASE=debian@sha256:a29215f6a35e51e22adffa17f89e9d2ef06214e64a2bad10d765c46aea49f11f
FROM ${BASE} AS build
ARG SNAPSHOT=http://snapshot.debian.org/archive/debian/20261001T000000Z
RUN rm -f /etc/apt/sources.list.d/* \
 && echo "deb [check-valid-until=no] ${SNAPSHOT} trixie main" > /etc/apt/sources.list \
 && apt-get -o Acquire::Check-Valid-Until=false update \
 && apt-get install -y --no-install-recommends build-essential gfortran cmake libopenblas-dev liblapack-dev \
 && dpkg-query -W -f '${Package}=${Version}\n' | sort > /build-packages.txt
COPY elmerfem-release-26.2.1.tar.gz /src/
RUN cd /src && tar xzf elmerfem-release-26.2.1.tar.gz && mkdir build && cd build \
 && cmake ../elmerfem-release-26.2.1 -DCMAKE_BUILD_TYPE=Release -DWITH_MPI=FALSE -DWITH_OpenMP=FALSE \
    -DWITH_ELMERGUI=FALSE -DWITH_ElmerIce=FALSE -DWITH_LUA=FALSE -DCMAKE_INSTALL_PREFIX=/opt/elmer \
 && make -j"$(nproc)" install > /build.log 2>&1 || (tail -80 /build.log; exit 1)

FROM ${BASE}
ARG SNAPSHOT=http://snapshot.debian.org/archive/debian/20261001T000000Z
RUN rm -f /etc/apt/sources.list.d/* \
 && echo "deb [check-valid-until=no] ${SNAPSHOT} trixie main" > /etc/apt/sources.list \
 && apt-get -o Acquire::Check-Valid-Until=false update \
 && apt-get install -y --no-install-recommends libgfortran5 libopenblas0 liblapack3 libgomp1 \
 && rm -rf /var/lib/apt/lists/* \
 && dpkg-query -W -f '${Package}=${Version}\n' | sort > /runtime-packages.txt
COPY --from=build /opt/elmer /opt/elmer
COPY --from=build /build-packages.txt /opt/elmer/build-packages.txt
ENV PATH=/opt/elmer/bin:$PATH LD_LIBRARY_PATH=/opt/elmer/lib/elmersolver:/opt/elmer/lib \
    ELMER_HOME=/opt/elmer OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
WORKDIR /case
