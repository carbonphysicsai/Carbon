# REFERENCE-PACKAGES-01: CalculiX ccx 2.23 with SPOOLES 2.2 (source) and
# Debian ARPACK, on the pinned Debian base with a dated snapshot.
ARG BASE=debian@sha256:a29215f6a35e51e22adffa17f89e9d2ef06214e64a2bad10d765c46aea49f11f
FROM ${BASE} AS build
ARG SNAPSHOT=http://snapshot.debian.org/archive/debian/20261001T000000Z
RUN rm -f /etc/apt/sources.list.d/* \
 && echo "deb [check-valid-until=no] ${SNAPSHOT} trixie main" > /etc/apt/sources.list \
 && apt-get -o Acquire::Check-Valid-Until=false update \
 && apt-get install -y --no-install-recommends build-essential gfortran perl bzip2 libarpack2-dev libopenblas-dev liblapack-dev \
 && dpkg-query -W -f '${Package}=${Version}\n' | sort > /build-packages.txt
COPY ccx_2.23.src.tar.bz2 spooles.2.2.tgz /src/
ENV RELAX="-Wno-error=implicit-function-declaration -Wno-error=incompatible-pointer-types -Wno-error=int-conversion -Wno-error=implicit-int -Wno-error=return-mismatch -std=gnu17"
RUN mkdir -p /src/SPOOLES.2.2 && cd /src/SPOOLES.2.2 && tar xzf ../spooles.2.2.tgz \
 && sed -i "s|^  CC = /usr/lang-4.0/bin/cc|  CC = gcc|; s|^  CC = .*|  CC = gcc|; s|^  OPTLEVEL = .*|  OPTLEVEL = -O2|; s|^  CFLAGS = .*|  CFLAGS = \$(OPTLEVEL) $RELAX|" Make.inc \
 && make lib > /spooles-build.log 2>&1 || (tail -40 /spooles-build.log; exit 1)
RUN cd /src && tar xjf ccx_2.23.src.tar.bz2 && cd CalculiX/ccx_2.23/src \
 && sed -i "s|^CFLAGS = -Wall -O2|CFLAGS = -O2 $RELAX|; s|^FFLAGS = -Wall -O2 -cpp|FFLAGS = -O2 -cpp -fallow-argument-mismatch|; s|^DIR=.*|DIR=/src/SPOOLES.2.2|; s|-I ../../../SPOOLES.2.2|-I /src/SPOOLES.2.2|; s|\.\./\.\./\.\./ARPACK/libarpack_INTEL.a|-larpack -llapack -lopenblas|" Makefile \
 && make -j"$(nproc)" > /ccx-build.log 2>&1 || (tail -60 /ccx-build.log; exit 1) \
 && install -D ccx_2.23 /opt/calculix/bin/ccx

FROM ${BASE}
ARG SNAPSHOT=http://snapshot.debian.org/archive/debian/20261001T000000Z
RUN rm -f /etc/apt/sources.list.d/* \
 && echo "deb [check-valid-until=no] ${SNAPSHOT} trixie main" > /etc/apt/sources.list \
 && apt-get -o Acquire::Check-Valid-Until=false update \
 && apt-get install -y --no-install-recommends libgfortran5 libgomp1 libarpack2t64 libopenblas0 liblapack3 \
 && rm -rf /var/lib/apt/lists/* \
 && dpkg-query -W -f '${Package}=${Version}\n' | sort > /runtime-packages.txt
COPY --from=build /opt/calculix /opt/calculix
COPY --from=build /build-packages.txt /opt/calculix/build-packages.txt
ENV PATH=/opt/calculix/bin:$PATH OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 CCX_NPROC_EQUATION_SOLVER=1
WORKDIR /case
