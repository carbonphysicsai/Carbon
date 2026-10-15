# REFERENCE-PACKAGES-01 / f06: Meep 1.32.0 (serial, double precision) built
# from the upstream release asset (checksum verified by build.sh) with its
# Python and MPB (mode-solver) interfaces, against MPB 1.11.1 (from its
# release asset), libctl 4.5.1, Harminv 1.4.2, FFTW 3.3.10, HDF5 1.14.5 (serial) and GSL 2.8 from a dated
# Debian snapshot (main + trixie-security at the same instant: the base image
# already carries security-updated libssl, which libhdf5-dev's libssl-dev pins)
# on the pinned Debian base. No MPI, no OpenMP, no GPU.
# Portable flags (no -march): the image must run unchanged on another x86-64.
ARG BASE=debian@sha256:a29215f6a35e51e22adffa17f89e9d2ef06214e64a2bad10d765c46aea49f11f
FROM ${BASE} AS deps
ARG SNAPSHOT=http://snapshot.debian.org/archive/debian/20261001T000000Z
ARG SECURITY=http://snapshot.debian.org/archive/debian-security/20261001T000000Z
ARG JOBS=2
RUN rm -f /etc/apt/sources.list.d/* \
 && echo "deb [check-valid-until=no] ${SNAPSHOT} trixie main" > /etc/apt/sources.list \
 && echo "deb [check-valid-until=no] ${SECURITY} trixie-security main" >> /etc/apt/sources.list \
 && apt-get -o Acquire::Check-Valid-Until=false update \
 && apt-get install -y --no-install-recommends build-essential gfortran pkg-config libctl-dev \
    libharminv-dev libfftw3-dev libhdf5-dev libgsl-dev libopenblas-dev liblapack-dev \
    python3-dev python3-numpy python3-scipy python3-matplotlib \
 && dpkg-query -W -f '${Package}=${Version}\n' | sort > /build-packages.txt
FROM deps AS build
ARG JOBS=2
COPY meep-1.32.0.tar.gz mpb-1.11.1.tar.gz /src/
ENV CFLAGS="-O3 -mtune=generic" CXXFLAGS="-O3 -mtune=generic" \
    CPPFLAGS="-I/opt/meep/include -I/usr/include/hdf5/serial" \
    LDFLAGS="-L/opt/meep/lib -L/usr/lib/x86_64-linux-gnu/hdf5/serial -Wl,-rpath,/opt/meep/lib"
# Debian's mpb-dev ships headers only (no libmpb), so MPB's library is built
# from its release asset with Hermitian epsilon, as Meep's build guide asks.
RUN cd /src && tar xzf mpb-1.11.1.tar.gz && cd mpb-1.11.1 \
 && ./configure --prefix=/opt/meep --enable-shared --disable-static --with-hermitian-eps \
    --without-libctl --without-mpi > /mpb-configure.log 2>&1 || (tail -60 /mpb-configure.log; exit 1) \
 && make -j"${JOBS}" > /mpb-build.log 2>&1 && make install >> /mpb-build.log 2>&1 \
    || (tail -60 /mpb-build.log; exit 1)
# The release asset's pregenerated python/__init__.py carries a stale
# "__version__ = '1.33.0-beta'" (configure/config.h say 1.32.0, and every
# source file equals tag v1.32.0); rewrite that one line to the configured
# version (the non-maintainer Makefile cannot regenerate the file). No other
# source change.
RUN cd /src && tar xzf meep-1.32.0.tar.gz && cd meep-1.32.0 \
 && grep -qx "__version__ = '1.33.0-beta'" python/__init__.py \
 && sed -i "s/^__version__ = '1.33.0-beta'\$/__version__ = '1.32.0'/" python/__init__.py \
 && grep -qx "__version__ = '1.32.0'" python/__init__.py \
 && ./configure --prefix=/opt/meep --enable-shared --disable-static --without-mpi \
    --without-scheme --with-python --enable-portable-binary PYTHON=python3 > /configure.log 2>&1 \
    || (tail -80 /configure.log; exit 1) \
 && make -j"${JOBS}" > /build.log 2>&1 || (tail -80 /build.log; exit 1)
RUN cd /src/meep-1.32.0 && make install > /install.log 2>&1 || (tail -40 /install.log; exit 1) \
 && grep -E "^ *\\$ \\./configure|^(CC|CXX|CFLAGS|CXXFLAGS|HAVE_[A-Z0-9_]+) *=|checking for (mpb|harminv|ctl|hdf5|fftw|gsl)" \
    /configure.log > /opt/meep/configure-summary.txt || true \
 && cp /src/meep-1.32.0/config.h /opt/meep/config.h \
 && sha256sum /mpb-configure.log /mpb-build.log /configure.log /build.log /install.log > /opt/meep/build-log-sha256.txt \
 && cp /mpb-configure.log /configure.log /opt/meep/ \
 && cp /build-packages.txt /opt/meep/build-packages.txt

FROM ${BASE}
ARG SNAPSHOT=http://snapshot.debian.org/archive/debian/20261001T000000Z
ARG SECURITY=http://snapshot.debian.org/archive/debian-security/20261001T000000Z
RUN rm -f /etc/apt/sources.list.d/* \
 && echo "deb [check-valid-until=no] ${SNAPSHOT} trixie main" > /etc/apt/sources.list \
 && echo "deb [check-valid-until=no] ${SECURITY} trixie-security main" >> /etc/apt/sources.list \
 && apt-get -o Acquire::Check-Valid-Until=false update \
 && apt-get install -y --no-install-recommends libctl7t64 libharminv3 libfftw3-double3 \
    libhdf5-310 libgsl28 libgslcblas0 libopenblas0 liblapack3 python3 python3-numpy python3-scipy python3-matplotlib python3-h5py \
 && rm -rf /var/lib/apt/lists/* \
 && dpkg-query -W -f '${Package}=${Version}\n' | sort > /runtime-packages.txt
COPY --from=build /opt/meep /opt/meep
ENV PYTHONPATH=/opt/meep/lib/python3.13/site-packages LD_LIBRARY_PATH=/opt/meep/lib \
    OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MPLBACKEND=Agg MPLCONFIGDIR=/tmp
WORKDIR /case
RUN ldd /opt/meep/lib/libmeep.so | grep -q "not found" && exit 1 || true \
 && python3 -c "import meep, meep.mpb; assert meep.__version__ == '1.32.0', meep.__version__"
