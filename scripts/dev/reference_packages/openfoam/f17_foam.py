"""Minimal independent reader for OpenFOAM v2506 polyMesh and field files.

Reads ascii or binary (label 32, scalar 64) labelList, vectorField,
faceCompactList and vol/surface fields, so the f17 observers integrate raw
solver output on the host without trusting a solver-side post-processor.
numpy only.
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np

_WS = b" \t\r\n"


def _header(buf):
    start = buf.find(b"FoamFile")
    end = buf.find(b"}", start)
    head = buf[start:end].decode()
    fmt = re.search(r"format\s+(\w+)", head)
    cls = re.search(r"class\s+(\w+)", head)
    return end + 1, (fmt[1] if fmt else "ascii"), (cls[1] if cls else "")


def _skip_ws_comments(buf, pos):
    while True:
        while pos < len(buf) and buf[pos] in _WS:
            pos += 1
        if buf.startswith(b"//", pos):
            pos = buf.index(b"\n", pos)
        elif buf.startswith(b"/*", pos):
            pos = buf.index(b"*/", pos) + 2
        else:
            return pos


def _list(buf, pos, binary, width, dtype):
    """Parse 'N ( ... )' at pos; returns (array, new_pos)."""
    pos = _skip_ws_comments(buf, pos)
    m = re.compile(rb"(\d+)\s*\(").match(buf, pos)
    if m is None:
        # 'N{value}' uniform list form
        m2 = re.compile(rb"(\d+)\s*\{([^}]*)\}").match(buf, pos)
        if m2 is None:
            raise ValueError(f"list expected at byte {pos}")
        n, inner = int(m2[1]), m2[2].decode().strip("() ")
        value = np.array([float(x) for x in inner.split()], dtype=float)
        return np.tile(value, (n, 1)).squeeze(), m2.end()
    n, pos = int(m[1]), m.end()
    if binary:
        size = np.dtype(dtype).itemsize * width * n
        arr = np.frombuffer(buf, dtype=dtype, count=width * n, offset=pos).copy()
        pos += size
        pos = _skip_ws_comments(buf, pos)
        if buf[pos : pos + 1] != b")":
            raise ValueError("binary list not terminated")
        return (arr.reshape(n, width) if width > 1 else arr), pos + 1
    depth, end = 1, pos
    while depth:
        c = buf[end : end + 1]
        depth += {b"(": 1, b")": -1}.get(c, 0)
        end += 1
    text = buf[pos : end - 1].decode().replace("(", " ").replace(")", " ")
    arr = np.array(text.split(), dtype=dtype)
    return (arr.reshape(n, width) if width > 1 else arr), end


def read_labels(path):
    buf = Path(path).read_bytes()
    pos, fmt, _ = _header(buf)
    arr, _ = _list(buf, pos, fmt == "binary", 1, np.int32)
    return arr


def read_points(path):
    buf = Path(path).read_bytes()
    pos, fmt, _ = _header(buf)
    arr, _ = _list(buf, pos, fmt == "binary", 3, np.float64)
    return arr


def read_faces(path):
    """faceCompactList (offsets, labels) or faceList; returns (offsets, labels)."""
    buf = Path(path).read_bytes()
    pos, fmt, cls = _header(buf)
    if cls == "faceCompactList":
        offsets, pos = _list(buf, pos, fmt == "binary", 1, np.int32)
        labels, _ = _list(buf, pos, fmt == "binary", 1, np.int32)
        return offsets, labels
    pos = _skip_ws_comments(buf, pos)
    n = int(re.compile(rb"(\d+)").match(buf, pos)[1])
    faces = re.findall(rb"\d+\(([\d ]+)\)", buf[pos:])[:n]
    lists = [np.array(f.split(), dtype=np.int32) for f in faces]
    offsets = np.concatenate([[0], np.cumsum([len(f) for f in lists])])
    return offsets.astype(np.int32), np.concatenate(lists)


def read_boundary(path):
    text = Path(path).read_text()
    text = text[text.index("}", text.index("FoamFile")) + 1 :]
    out = {}
    for name, body in re.findall(r"(\w+)\s*\{([^}]*)\}", text):
        n = re.search(r"nFaces\s+(\d+)", body)
        s = re.search(r"startFace\s+(\d+)", body)
        t = re.search(r"\btype\s+(\w+)", body)
        if n and s:
            out[name] = {"type": t[1], "nFaces": int(n[1]), "startFace": int(s[1])}
    return out


def read_field(path, patches=()):
    """Returns {'internal': array|float, 'patch': {name: array|float|None}}."""
    buf = Path(path).read_bytes()
    pos, fmt, cls = _header(buf)
    binary = fmt == "binary"
    width = 3 if "Vector" in cls else 1

    def value_at(p):
        p = _skip_ws_comments(buf, p)
        if buf.startswith(b"uniform", p):
            p += len(b"uniform")
            p = _skip_ws_comments(buf, p)
            end = buf.index(b";", p)
            raw = buf[p:end].decode().strip("() ")
            vals = [float(x) for x in raw.split()]
            return (vals[0] if width == 1 else np.array(vals)), end + 1
        if buf.startswith(b"nonuniform", p):
            p = buf.index(b">", p) + 1
            return _list(buf, p, binary, width, np.float64)
        raise ValueError("field value expected")

    i = buf.index(b"internalField", pos) + len(b"internalField")
    internal, pos = value_at(i)
    out = {"internal": internal, "patch": {}}
    b = buf.index(b"boundaryField", pos)
    for name in patches:
        m = re.compile(rb"\n\s*" + re.escape(name.encode()) + rb"\s*\n?\s*\{").search(
            buf, b
        )
        if m is None:
            out["patch"][name] = None
            continue
        close = _entry_end(buf, m.end())
        v = re.compile(rb"\bvalue\b").search(buf, m.end(), close)
        out["patch"][name] = value_at(v.end())[0] if v else None
    return out


def _entry_end(buf, pos):
    """Index of the '}' closing a patch entry, skipping binary list payloads."""
    depth = 1
    lst = re.compile(rb"List<\w+>\s*(\d+)\s*\(")
    while depth:
        m = lst.match(buf, pos)
        if m and buf[pos : pos + 4] == b"List":
            n = int(m[1])
            width = 3 if b"vector" in m[0] else 1
            pos = m.end() + 8 * width * n
            continue
        c = buf[pos : pos + 1]
        depth += {b"{": 1, b"}": -1}.get(c, 0)
        pos += 1
    return pos - 1


class Mesh:
    def __init__(self, poly_dir):
        d = Path(poly_dir)
        self.points = read_points(d / "points")
        self.offsets, self.labels = read_faces(d / "faces")
        self.owner = read_labels(d / "owner")
        self.boundary = read_boundary(d / "boundary")

    def patch_slice(self, name):
        p = self.boundary[name]
        return slice(p["startFace"], p["startFace"] + p["nFaces"])

    def face_geometry(self, name):
        """Area vectors (exact polygon vector area) and centroids of a patch."""
        s = self.patch_slice(name)
        areas, centres = [], []
        for f in range(s.start, s.stop):
            pts = self.points[self.labels[self.offsets[f] : self.offsets[f + 1]]]
            c0 = pts.mean(axis=0)
            nxt = np.roll(pts, -1, axis=0)
            tri = 0.5 * np.cross(pts - c0, nxt - c0)
            sf = tri.sum(axis=0)
            mags = np.linalg.norm(tri, axis=1)
            cen = ((pts + nxt + c0) / 3 * mags[:, None]).sum(0) / max(
                mags.sum(), 1e-300
            )
            areas.append(sf)
            centres.append(cen)
        return np.array(areas), np.array(centres)
