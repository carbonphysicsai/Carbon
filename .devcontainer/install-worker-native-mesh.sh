#!/bin/sh
# Trusted image build only; package bytes and ABI are fixed by the lock.
set -eu
set --
while read -r package version architecture sha; do
    set -- "$@" "$package=$version"
done < /tmp/carbon-mesh-packages.lock
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get --assume-yes --no-install-recommends --download-only install "$@"
/opt/carbon-worker/bin/python - <<'CARBON_MESH_VERIFY'
import hashlib
import subprocess
from pathlib import Path
rows = [line.split() for line in Path('/tmp/carbon-mesh-packages.lock').read_text().splitlines()]
expected = {(name, version, arch): sha for name, version, arch, sha in rows}
observed = set()
for archive in Path('/var/cache/apt/archives').glob('*.deb'):
    identity = tuple(subprocess.check_output([
        'dpkg-deb', '--show', '--showformat=${Package}\t${Version}\t${Architecture}', str(archive)
    ], text=True).split('\t'))
    if identity in observed or hashlib.sha256(archive.read_bytes()).hexdigest() != expected.get(identity):
        raise RuntimeError('native mesh package identity or bytes differ')
    observed.add(identity)
if observed != set(expected):
    raise RuntimeError('native mesh package closure differs')
CARBON_MESH_VERIFY
DEBIAN_FRONTEND=noninteractive apt-get --assume-yes --no-install-recommends --no-download install "$@"
/opt/carbon-worker/bin/python - <<'CARBON_MESH_ABI'
import ctypes
import subprocess
from pathlib import Path
for line in Path('/tmp/carbon-mesh-packages.lock').read_text().splitlines():
    name, version, arch, sha = line.split()
    actual = subprocess.check_output(['dpkg-query', '-W', '-f=${Version}\t${Architecture}', name], text=True)
    if actual != version + '\t' + arch:
        raise RuntimeError('installed native mesh package differs')
for library in ('libz.so.1', 'libGLU.so.1', 'libGL.so.1', 'libXrender.so.1',
                'libXcursor.so.1', 'libXfixes.so.3', 'libXext.so.6', 'libXft.so.2',
                'libfontconfig.so.1', 'libXinerama.so.1', 'libpthread.so.0', 'libdl.so.2',
                'libX11.so.6', 'libm.so.6', 'libstdc++.so.6', 'libgcc_s.so.1',
                'librt.so.1', 'libgomp.so.1', 'libc.so.6', 'ld-linux-x86-64.so.2'):
    ctypes.CDLL(library)
CARBON_MESH_ABI
install -m 0444 /tmp/carbon-mesh-packages.lock /opt/carbon/native-mesh-packages.lock
rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/*.deb
rm /tmp/carbon-mesh-packages.lock
