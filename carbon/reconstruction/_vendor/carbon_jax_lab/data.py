"""Immutable public research arrays and explicit trajectory-level separation."""

from __future__ import annotations

import hashlib
import json
import zipfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .config import canonical_json

_MAX_ARCHIVE_BYTES = 1 << 30
_MAX_ARRAY_BYTES = 1 << 29


def _closed_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate JSON member")
            result[key] = value
        return result

    return json.loads(raw, object_pairs_hook=pairs)


def _checked_npz(path, expected):
    path = Path(path)
    if (
        path.is_symlink()
        or not path.is_file()
        or path.stat().st_size > _MAX_ARCHIVE_BYTES
    ):
        raise ValueError("unsafe or oversized array archive")
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        names = [item.filename for item in infos]
        expected_names = {name + ".npy" for name in expected}
        if set(names) != expected_names or len(names) != len(set(names)):
            raise ValueError("array archive members")
        if any(
            item.flag_bits & 1
            or item.is_dir()
            or Path(item.filename).name != item.filename
            for item in infos
        ):
            raise ValueError("unsafe array archive member")
        if sum(item.file_size for item in infos) > _MAX_ARCHIVE_BYTES:
            raise ValueError("uncompressed array archive limit")
    with np.load(path, allow_pickle=False) as loaded:
        arrays = {name: np.array(loaded[name], copy=True) for name in expected}
    if any(
        array.nbytes > _MAX_ARRAY_BYTES or array.ndim > 4 or array.dtype.hasobject
        for array in arrays.values()
    ):
        raise ValueError("array bounds")
    return arrays


def array_digest(arrays):
    h = hashlib.sha256()
    for name, a in sorted(arrays.items()):
        a = np.ascontiguousarray(a)
        h.update(name.encode())
        h.update(a.dtype.str.encode())
        h.update(canonical_json(list(a.shape)).encode())
        h.update(a.tobytes())
    return h.hexdigest()


@dataclass(frozen=True)
class Trajectories:
    initial: np.ndarray  # [cases, points]
    viscosity: np.ndarray  # [cases]
    times: np.ndarray  # [cases, times]
    solution: np.ndarray  # [cases, times, points]
    positions: np.ndarray  # [points], periodic [0,L), uniform for this trainer
    role: str
    provenance: str
    domain_length: float = 1.0

    def __post_init__(self):
        if self.role not in ("train", "validation", "audit"):
            raise ValueError("declared data role required")
        if not isinstance(self.provenance, str) or not self.provenance:
            raise ValueError("provenance required")
        for name in ("initial", "viscosity", "times", "solution", "positions"):
            a = np.array(getattr(self, name), copy=True)
            if a.dtype.kind != "f" or not np.isfinite(a).all():
                raise ValueError(f"{name}: finite float arrays required")
            a.setflags(write=False)
            object.__setattr__(self, name, a)
        s, n = self.initial.shape
        if (
            s < 1
            or n < 8
            or self.solution.ndim != 3
            or self.solution.shape[0] != s
            or self.solution.shape[2] != n
        ):
            raise ValueError("expected initial [S,N], solution [S,T,N], N>=8")
        if (
            self.times.shape != self.solution.shape[:2]
            or self.viscosity.shape != (s,)
            or self.positions.shape != (n,)
        ):
            raise ValueError("inconsistent shapes")
        if (
            (self.viscosity <= 0).any()
            or (self.times < 0).any()
            or (np.diff(self.times, axis=1) <= 0).any()
        ):
            raise ValueError(
                "positive viscosity and increasing nonnegative times required"
            )
        if not np.isfinite(self.domain_length) or self.domain_length <= 0:
            raise ValueError("domain_length")
        expected = np.arange(n, dtype=np.float64) * self.domain_length / n
        if not np.allclose(
            self.positions,
            expected,
            rtol=0,
            atol=20 * np.finfo(self.positions.dtype).eps * self.domain_length,
        ):
            raise ValueError(
                "trainer supports shared endpoint-excluded uniform periodic grids only"
            )
        if self.times.shape[1] < 2:
            raise ValueError("at least two labeled times required")

    @property
    def fingerprint(self):
        return hashlib.sha256(
            (
                array_digest(self.arrays())
                + canonical_json(
                    {
                        "role": self.role,
                        "provenance": self.provenance,
                        "L": self.domain_length,
                    }
                )
            ).encode()
        ).hexdigest()

    def arrays(self):
        return {
            n: getattr(self, n)
            for n in ("initial", "viscosity", "times", "solution", "positions")
        }

    @property
    def case_keys(self):
        return tuple(
            array_digest({"u0": u, "nu": nu.reshape(1)})
            for u, nu in zip(self.initial, self.viscosity)
        )

    def save(self, path):
        path = Path(path)
        if path.exists():
            raise FileExistsError(path)
        meta = {
            "schema": "carbon.public-trajectories.v1",
            "role": self.role,
            "provenance": self.provenance,
            "domain_length": self.domain_length,
            "fingerprint": self.fingerprint,
        }
        with path.open("xb") as f:
            np.savez_compressed(
                f, **self.arrays(), metadata=np.array(canonical_json(meta))
            )

    @classmethod
    def load(cls, path):
        names = ("initial", "viscosity", "times", "solution", "positions", "metadata")
        arrays = _checked_npz(path, names)
        metadata = arrays.pop("metadata")
        if metadata.shape != () or metadata.dtype.kind not in ("U", "S"):
            raise ValueError("metadata scalar")
        meta = _closed_json(str(metadata))
        if (
            type(meta) is not dict
            or set(meta)
            != {"schema", "role", "provenance", "domain_length", "fingerprint"}
            or meta.get("schema") != "carbon.public-trajectories.v1"
        ):
            raise ValueError("data schema")
        obj = cls(
            **arrays,
            role=meta["role"],
            provenance=meta["provenance"],
            domain_length=meta["domain_length"],
        )
        if obj.fingerprint != meta["fingerprint"]:
            raise ValueError("data integrity mismatch")
        return obj

    @classmethod
    def from_workbench_npz(cls, path, *, role, provenance, domain_length):
        """Explicit public-data adapter; never changes the original file or digest.

        Schema matches the supplied workbench description, not the unavailable
        JAX package. A role declaration is research metadata, not access authority.
        """
        arrays = _checked_npz(
            path, ("initial_field", "viscosity", "requested_times", "solution")
        )
        u0 = arrays["initial_field"]
        nu = arrays["viscosity"]
        t = arrays["requested_times"]
        y = arrays["solution"]
        if t.ndim == 1:
            t = np.broadcast_to(t, (len(u0), len(t)))
        x = np.arange(u0.shape[-1], dtype=np.float64) * domain_length / u0.shape[-1]
        return cls(u0, nu, t, y, x, role, provenance, domain_length)


def assert_case_disjoint(*datasets):
    seen = set()
    for data in datasets:
        keys = set(data.case_keys)
        if len(keys) != len(data.case_keys):
            raise ValueError("duplicate physical cases within dataset")
        if seen & keys:
            raise ValueError("physical-case overlap across splits")
        seen |= keys


def subset(data, indices, role):
    i = np.asarray(indices, dtype=int)
    return Trajectories(
        data.initial[i],
        data.viscosity[i],
        data.times[i],
        data.solution[i],
        data.positions,
        role,
        data.provenance,
        data.domain_length,
    )
