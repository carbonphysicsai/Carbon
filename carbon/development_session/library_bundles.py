"""Public DEVELOPMENT library catalogue and offline bundle preparation.

Catalogue entries are discovery metadata, not installed packages or construction
admission. A bundle becomes runnable only after an operator supplies and checks
the complete local source/wheel closure and an isolated image is built/probed.
"""

from __future__ import annotations

import gzip
import hashlib
import io
import json
import os
import re
import stat
import struct
import tarfile
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

SCHEMA = "carbon.development.library-catalogue.v1"
BUNDLE_SCHEMA = "carbon.development.library-bundle.v1"
REF_SCHEMA = "carbon.library-bundle-ref.v1"
SHA256 = re.compile(r"sha256:[0-9a-f]{64}\Z")
NAME = re.compile(r"[a-z][a-z0-9-]{0,63}\Z")
LOCK_LINE = re.compile(
    rb"([A-Za-z0-9][A-Za-z0-9._-]*)==([A-Za-z0-9][A-Za-z0-9.!+_-]*) --hash=sha256:([a-f0-9]{64})\Z"
)
MAX_SOURCE_BYTES = 32 * 1024 * 1024
MAX_EXPANDED_BYTES = 128 * 1024 * 1024
MAX_MEMBERS = 4096
MAX_RAW_TAR_BYTES = 144 * 1024 * 1024
MAX_WHEELS = 64
MAX_WHEEL_BYTES = 128 * 1024 * 1024
MAX_WHEEL_TOTAL_BYTES = 512 * 1024 * 1024
MAX_WHEEL_DIRECTORY_BYTES = MAX_MEMBERS * 1024
MAX_LOCK_BYTES = 512 * 1024
MAX_LICENSE_BYTES = 256 * 1024
UV_IMAGE = "ghcr.io/astral-sh/uv:0.12.7@sha256:95f2aa1fe59274951cfe9b0cbc7972e879ff1004bc8945d130a32eb0dbd85945"
_RUNTIME_ACCELERATORS = {
    "jax-cuda13-py311": "cuda13",
    "torch-cu130-py311": "cuda13",
    "python-cpu-py311": "cpu",
}

# These are asset roles, not model-family permissions. Challenge TRAIN is
# staged separately; reconstruction creates fresh state after source install.
# Source/dependency assets may include images, tables and test data, but a
# recognizable pretrained/checkpoint asset must not arrive in either archive.
_STATE_SUFFIXES = (
    ".safetensors",
    ".ckpt",
    ".pth.tar",
    ".pt.tar",
)
_STATE_BINARY_SUFFIXES = (
    ".bin",
    ".gguf",
    ".h5",
    ".hdf5",
    ".index",
    ".joblib",
    ".msgpack",
    ".npy",
    ".npz",
    ".onnx",
    ".pkl",
    ".pickle",
    ".pt",
    ".pth",
    ".tflite",
)
_STATE_NAMES = {
    "pytorch_model.bin",
    "adapter_model.bin",
    "flax_model.msgpack",
    "tf_model.h5",
    "model.safetensors.index.json",
}
_STATE_TOKENS = {
    "checkpoint",
    "checkpoints",
    "ckpt",
    "pretrained",
    "state_dict",
    "model_state",
    "model_weights",
    "adapter_model",
}
_TRAIN_ASSET_DIRECTORIES = {
    "challenge_train",
    "challenge-train",
    "challenge_train_data",
}


def _declared_challenge_train_asset(path):
    # A Challenge's TRAIN bytes have their own staged role. A file explicitly
    # placed under that role cannot be laundered into code/dependency closure.
    parts = [part.casefold() for part in PurePosixPath(path).parts]
    return any(part in _TRAIN_ASSET_DIRECTORIES for part in parts[1:-1])


def _recognizable_pretrained_state(path):
    """High-confidence path inventory check; never a proof about code bytes.

    Arbitrary code can encode arrays or rename files. This check refuses
    recognizable packaged model state without banning ordinary numeric source
    assets or dependency test fixtures merely for using NumPy/pickle formats.
    """
    parts = [part.casefold() for part in PurePosixPath(path).parts]
    leaf = parts[-1]
    if (
        leaf in _STATE_NAMES
        or leaf.endswith(_STATE_SUFFIXES)
        or re.search(r"\.ckpt\.(?:index|data-[0-9]+-of-[0-9]+)\Z", leaf)
    ):
        return True
    if not leaf.endswith(_STATE_BINARY_SUFFIXES):
        return False
    stem = leaf.rsplit(".", 1)[0]
    if re.match(r"(?:pytorch_model|adapter_model|flax_model|tf_model)[-_.]", stem):
        return True
    tokens = {stem, *re.split(r"[-_.]+", stem)}
    parent_tokens = {
        token for part in parts[:-1] for token in (part, *re.split(r"[-_.]+", part))
    }
    return bool(
        tokens & _STATE_TOKENS
        or parent_tokens & _STATE_TOKENS
        or {"model", "weights"} <= tokens
        or ("weights" in tokens and {"model", "models"} & parent_tokens)
    )


def _safe_wheel_assets(body):
    """Inspect a pinned wheel's member names without importing or extracting."""
    # ZipFile parses the complete central directory on open. Bound that input
    # first from the fixed EOCD trailer, before allocating member metadata.
    trailer = body.rfind(b"PK\x05\x06", max(0, len(body) - 65557))
    if trailer < 0 or trailer + 22 > len(body):
        raise ValueError("invalid wheel archive")
    # ZipFile probes the 20 bytes immediately before EOCD for a ZIP64 locator.
    # A locator hidden in an ordinary member comment can make it trust a
    # different, unbounded directory after our EOCD checks, so refuse it first.
    if trailer >= 20 and body[trailer - 20 : trailer - 16] == b"PK\x06\x07":
        raise ValueError("bounded wheel directory required")
    _, disk, start_disk, disk_count, count, size, offset, comment = struct.unpack_from(
        "<4s4H2IH", body, trailer
    )
    if (
        disk != 0
        or start_disk != 0
        or disk_count != count
        or count > MAX_MEMBERS
        or count == 0xFFFF  # ZIP64 needs a separate bounded reader.
        or size > MAX_WHEEL_DIRECTORY_BYTES
        or size == 0xFFFFFFFF
        or offset + size != trailer
        or trailer + 22 + comment != len(body)
    ):
        raise ValueError("bounded wheel directory required")
    cursor = offset
    observed = 0
    while cursor < trailer:
        if cursor + 46 > trailer or body[cursor : cursor + 4] != b"PK\x01\x02":
            raise ValueError("bounded wheel directory required")
        filename, extra, member_comment = struct.unpack_from("<HHH", body, cursor + 28)
        cursor += 46 + filename + extra + member_comment
        observed += 1
        if cursor > trailer or observed > MAX_MEMBERS:
            raise ValueError("bounded wheel directory required")
    if cursor != trailer or observed != count:
        raise ValueError("bounded wheel directory required")
    try:
        with zipfile.ZipFile(io.BytesIO(body)) as archive:
            seen = set()
            for count, member in enumerate(archive.infolist(), start=1):
                if count > MAX_MEMBERS:
                    raise ValueError("bounded wheel members required")
                path = PurePosixPath(member.filename)
                parts = path.parts
                if (
                    not parts
                    or path.is_absolute()
                    or any(part in {"", ".", ".."} for part in parts)
                    or "\\" in member.filename
                    or ":" in member.filename
                    or member.filename.casefold() in seen
                ):
                    raise ValueError("unsafe wheel member")
                seen.add(member.filename.casefold())
                if not member.is_dir() and _declared_challenge_train_asset(
                    member.filename
                ):
                    raise ValueError("Challenge TRAIN asset in wheel")
                if not member.is_dir() and _recognizable_pretrained_state(
                    member.filename
                ):
                    raise ValueError("pretrained state asset in wheel")
    except (zipfile.BadZipFile, EOFError, OSError) as exc:
        raise ValueError("invalid wheel archive") from exc


def uv_stage_tag(bundle_digest):
    return (
        "carbon-library-uv:"
        + bundle_digest[7:]
        + "-"
        + UV_IMAGE.rsplit("sha256:", 1)[1][:16]
    )


def parent_stage_tag(bundle_digest, parent_image):
    return "carbon-library-parent:" + bundle_digest[7:] + "-" + parent_image[7:23]


# Frozen discovery snapshots. They do not claim compatible wheel closure,
# redistribution clearance, runtime import success, or official admission.
_SOURCES = (
    (
        "transolver",
        "THUML/Transolver",
        "75e0f67643806a81cd1d3f6adc88dd8c02416fe7",
        "torch",
        "MIT",
    ),
    (
        "transolver-plus",
        "THUML/Transolver_plus",
        "d5a23bc734a0ebac56384cf72049a26af9673452",
        "torch",
        "MIT",
    ),
    (
        "neural-solver-library",
        "THUML/Neural-Solver-Library",
        "db942b72c6b3972bad217300e3cbdb8004a1a80b",
        "torch",
        "MIT",
    ),
    (
        "geo-fno",
        "neuraloperator/Geo-FNO",
        "d499bde15104f4ac34db6eaf57d3528a101e4ef6",
        "torch",
        "MIT",
    ),
    (
        "latent-spectral-models",
        "THUML/Latent-Spectral-Models",
        "ae99d00e1c214e9a3372c1b2c3da468a30d5fe79",
        "torch",
        "MIT",
    ),
    (
        "jno",
        "FhG-IISB/jNO",
        "c769f46f246a0b9b2761366a1809e016dcf58c19",
        "jax",
        "EPL-2.0",
    ),
    (
        "foundax",
        "FhG-IISB/foundax",
        "72afc6d761aefc04ff2b8ffe8228f2145419143b",
        "jax",
        "LICENSE_CONFLICT",
    ),
    (
        "neuraloperator",
        "neuraloperator/neuraloperator",
        "b098e8f22decf2e46a4282bb912b8bbffcf30da0",
        "torch",
        "MIT",
    ),
    (
        "physicsnemo",
        "NVIDIA/physicsnemo",
        "9303b6580fe852595e235898688a317f9c04c7ba",
        "torch",
        "Apache-2.0",
    ),
)


@dataclass(frozen=True)
class LibraryBundleRef:
    """Inert shared identity; the image and constructor belong to a binding."""

    schema: str
    bundle_digest: str
    language: str
    runtime_profile_id: str
    environment_digest: str

    def __post_init__(self):
        if (
            self.schema != REF_SCHEMA
            or type(self.bundle_digest) is not str
            or not SHA256.fullmatch(self.bundle_digest)
            or self.language not in {"python", "julia"}
            or type(self.runtime_profile_id) is not str
            or not NAME.fullmatch(self.runtime_profile_id)
            or type(self.environment_digest) is not str
            or not SHA256.fullmatch(self.environment_digest)
        ):
            raise ValueError("closed inert library bundle reference required")

    def to_dict(self):
        return {
            "schema": self.schema,
            "bundle_digest": self.bundle_digest,
            "language": self.language,
            "runtime_profile_id": self.runtime_profile_id,
            "environment_digest": self.environment_digest,
        }

    @classmethod
    def from_dict(cls, value):
        if type(value) is not dict or set(value) != {
            "schema",
            "bundle_digest",
            "language",
            "runtime_profile_id",
            "environment_digest",
        }:
            raise ValueError("closed inert library bundle reference required")
        return cls(**value)


@dataclass(frozen=True)
class ProvisionedLibraryEnvironment:
    """Private result of one verified local, offline provisioning operation."""

    bundle: LibraryBundleRef
    parent_image: str
    context: Path
    context_digest: str
    image_id: str


def catalogue():
    """Versioned miner-visible discovery, with explicit maturity ceiling."""
    return {
        "schema": SCHEMA,
        "libraries": [
            {
                "id": name,
                "source": f"https://github.com/{repository}",
                "source_commit": commit,
                "framework": framework,
                "license_observation": license_id,
                "status": "DISCOVERY_ONLY",
            }
            for name, repository, commit, framework, license_id in _SOURCES
        ],
        "execution": "requires an installed, verified, owner-selected bundle",
        "official_eligible": False,
    }


def _digest(body):
    return "sha256:" + hashlib.sha256(body).hexdigest()


def _private_cache_directory(path, message):
    base = Path(path)
    if (
        not base.is_dir()
        or base.is_symlink()
        or base.resolve() != base.absolute()
        or (
            os.name == "posix"
            and (
                base.stat().st_uid != os.getuid()
                or stat.S_IMODE(base.stat().st_mode) & 0o077
            )
        )
    ):
        raise ValueError(message)
    return base


def _environment_digest(base, lock):
    return _digest(
        json.dumps(
            {"base_environment_digest": base, "overlay_lock_sha256": lock},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    )


def _locked_wheels(lock):
    """Closed one-hash-per-distribution overlay; no URL or index directives."""
    names = {}
    for line in lock.splitlines():
        if not line:
            continue
        match = LOCK_LINE.fullmatch(line)
        if match is None:
            raise ValueError("closed pinned wheel lock required")
        name, version, hex_digest = (part.decode("ascii") for part in match.groups())
        key = (re.sub(r"[-_.]+", "-", name).lower(), version)
        if key in names:
            raise ValueError("duplicate locked distribution")
        names[key] = "sha256:" + hex_digest
    return names


def _context_digest(context):
    """Exact regular-file tree seal; rejects extra paths and links."""
    manifest = context / "bundle.json"
    if manifest.is_symlink() or manifest.stat().st_size > 65536:
        raise ValueError("bounded bundle context manifest required")
    declared = json.loads(manifest.read_bytes())
    if type(declared) is not dict or type(declared.get("wheels")) is not dict:
        raise ValueError("closed bundle context manifest required")
    expected = {
        "bundle.json",
        "source.tar.gz",
        "requirements.txt",
        "LICENSE",
        "Dockerfile",
        "install-source.py",
    } | {"wheels/" + name for name in declared["wheels"]}
    entries = []
    pending = [(context, "")]
    while pending:
        folder, prefix = pending.pop()
        for item in os.scandir(folder):
            relative = prefix + item.name
            if item.is_symlink():
                raise ValueError("bundle context link refused")
            if item.is_dir(follow_symlinks=False):
                if relative != "wheels":
                    raise ValueError("bundle context directory differs")
                pending.append((Path(item.path), "wheels/"))
            elif item.is_file(follow_symlinks=False):
                if relative not in expected:
                    raise ValueError("bundle context file differs")
                fingerprint = hashlib.sha256()
                size = 0
                with open(item.path, "rb") as stream:
                    for block in iter(lambda: stream.read(1024 * 1024), b""):
                        size += len(block)
                        if size > MAX_WHEEL_TOTAL_BYTES:
                            raise ValueError("bundle context file exceeds bound")
                        fingerprint.update(block)
                entries.append((relative, size, "sha256:" + fingerprint.hexdigest()))
            else:
                raise ValueError("bundle context special file refused")
    if {item[0] for item in entries} != expected:
        raise ValueError("bundle context closure differs")
    return _digest(json.dumps(sorted(entries), separators=(",", ":")).encode())


def _safe_source_archive(body, *, license_text=None):
    """Check a source tar without extracting hostile paths or special files."""
    if type(body) is not bytes or not 0 < len(body) <= MAX_SOURCE_BYTES:
        raise ValueError("bounded source archive required")
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(body)) as compressed:
            raw = compressed.read(MAX_RAW_TAR_BYTES + 1)
        if len(raw) > MAX_RAW_TAR_BYTES:
            raise ValueError("bounded decompressed archive required")
    except (OSError, EOFError) as exc:
        raise ValueError("invalid compressed source archive") from exc
    seen = set()
    roots = set()
    expanded = 0
    licenses = 0
    try:
        count = 0
        with tarfile.open(fileobj=io.BytesIO(raw), mode="r|") as archive:
            for member in archive:
                count += 1
                if count > MAX_MEMBERS:
                    raise ValueError("bounded source members required")
                path = PurePosixPath(member.name)
                parts = path.parts
                if (
                    not parts
                    or path.is_absolute()
                    or any(part in {"", ".", ".."} for part in parts)
                    or "\\" in member.name
                    or ":" in member.name
                    or member.name.casefold() in seen
                    or not (member.isfile() or member.isdir())
                ):
                    raise ValueError("unsafe source archive member")
                seen.add(member.name.casefold())
                roots.add(parts[0])
                if len(roots) != 1 or (member.isfile() and len(parts) < 2):
                    raise ValueError("single-root source archive required")
                if member.isfile() and _declared_challenge_train_asset(member.name):
                    raise ValueError("Challenge TRAIN asset in source archive")
                if member.isfile() and _recognizable_pretrained_state(member.name):
                    raise ValueError("pretrained state asset in source archive")
                expanded += member.size
                if expanded > MAX_EXPANDED_BYTES:
                    raise ValueError("expanded source exceeds bound")
                if (
                    license_text is not None
                    and member.isfile()
                    and len(parts) == 2
                    and path.name.upper() == "LICENSE"
                ):
                    licenses += 1
                    if (
                        archive.extractfile(member).read(MAX_LICENSE_BYTES + 1)
                        != license_text
                    ):
                        raise ValueError("source license bytes differ")
            if count == 0:
                raise ValueError("bounded source members required")
            if license_text is not None and licenses != 1:
                raise ValueError("source license bytes differ")
    except (tarfile.TarError, EOFError, OSError) as exc:
        raise ValueError("invalid source archive") from exc
    return count


def validate_bundle(manifest, source, wheels, lock, license_text):
    """Validate source/dependency bytes and recognizable asset roles.

    Challenge TRAIN is staged outside this closure; any native model state must
    be emitted by fresh reconstruction. Filename inventory cannot prove that
    arbitrary code or renamed numeric files contain no encoded weights.
    Build-time uv must still prove dependency closure.
    """
    if type(source) is not bytes or not 0 < len(source) <= MAX_SOURCE_BYTES:
        raise ValueError("bounded source archive required")
    if type(lock) is not bytes or len(lock) > MAX_LOCK_BYTES:
        raise ValueError("bounded wheel lock required")
    if type(license_text) is not bytes or len(license_text) > MAX_LICENSE_BYTES:
        raise ValueError("bounded license bytes required")
    if type(wheels) is not dict or len(wheels) > MAX_WHEELS:
        raise ValueError("bounded wheel set required")
    total_wheel_bytes = 0
    for name, body in wheels.items():
        if (
            type(name) is not str
            or len(name) > 200
            or type(body) is not bytes
            or len(body) > MAX_WHEEL_BYTES
        ):
            raise ValueError("bounded wheel item required")
        total_wheel_bytes += len(body)
        if total_wheel_bytes > MAX_WHEEL_TOTAL_BYTES:
            raise ValueError("bounded wheel set required")
    required = {
        "schema",
        "name",
        "language",
        "source_sha256",
        "source_bytes",
        "runtime_profile_id",
        "base_environment_digest",
        "environment_digest",
        "os",
        "architecture",
        "python_abi",
        "accelerator",
        "lock_sha256",
        "wheels",
        "license_sha256",
    }
    if type(manifest) is not dict or set(manifest) != required:
        raise ValueError("closed library bundle manifest required")
    if manifest["schema"] != BUNDLE_SCHEMA or not NAME.fullmatch(manifest["name"]):
        raise ValueError("bundle schema or name invalid")
    profile = manifest["runtime_profile_id"]
    if type(profile) is not str or profile not in _RUNTIME_ACCELERATORS:
        raise ValueError("registered isolated profile required")
    if (
        manifest["language"] != "python"
        or manifest["os"] != "linux"
        or manifest["architecture"] != "amd64"
        or manifest["python_abi"] != "cp311"
        or manifest["accelerator"] != _RUNTIME_ACCELERATORS[profile]
        or type(manifest["source_bytes"]) is not int
        or manifest["source_bytes"] != len(source)
        or manifest["environment_digest"]
        != _environment_digest(
            manifest["base_environment_digest"], manifest["lock_sha256"]
        )
    ):
        raise ValueError("runtime ABI or source size differs")
    if any(
        type(manifest[key]) is not str or not SHA256.fullmatch(manifest[key])
        for key in (
            "source_sha256",
            "base_environment_digest",
            "environment_digest",
            "lock_sha256",
            "license_sha256",
        )
    ):
        raise ValueError("exact SHA256 identity required")
    if _digest(source) != manifest["source_sha256"]:
        raise ValueError("source archive digest differs")
    if _digest(lock) != manifest["lock_sha256"]:
        raise ValueError("lock digest differs")
    locked = _locked_wheels(lock)
    if _digest(license_text) != manifest["license_sha256"]:
        raise ValueError("license digest differs")
    _safe_source_archive(source, license_text=license_text)
    expected = manifest["wheels"]
    if (
        type(expected) is not dict
        or type(wheels) is not dict
        or set(expected) != set(wheels)
    ):
        raise ValueError("complete wheel closure required")
    for name, digest in expected.items():
        if (
            type(name) is not str
            or not name.endswith(".whl")
            or Path(name).name != name
            or "/" in name
            or "\\" in name
            or type(digest) is not str
            or not SHA256.fullmatch(digest)
            or type(wheels[name]) is not bytes
            or _digest(wheels[name]) != digest
        ):
            raise ValueError("wheel identity differs")
        parts = name[:-4].split("-")
        if len(parts) < 5:
            raise ValueError("wheel filename invalid")
        key = (re.sub(r"[-_.]+", "-", parts[0]).lower(), parts[1])
        if locked.pop(key, None) != digest:
            raise ValueError("wheel absent from exact requirements lock")
        _safe_wheel_assets(wheels[name])
    if locked:
        raise ValueError("locked wheel bytes unavailable")
    canonical = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    return _digest(canonical)


def bundle_ref(manifest, source, wheels, lock, license_text):
    return LibraryBundleRef(
        REF_SCHEMA,
        validate_bundle(manifest, source, wheels, lock, license_text),
        manifest["language"],
        manifest["runtime_profile_id"],
        manifest["environment_digest"],
    )


def load_cached_wheels(wheelhouse, manifest):
    """Read only a manifest's exact wheels from a private operator cache.

    Cached extras are never copied into a bundle. This does no resolution,
    download, package installation, or catalogue lookup.
    """
    declared = manifest.get("wheels") if type(manifest) is dict else None
    if type(declared) is not dict or len(declared) > MAX_WHEELS:
        raise ValueError("closed wheel manifest required")
    base = _private_cache_directory(wheelhouse, "private operator wheel cache required")
    wheels = {}
    total = 0
    for name, expected in declared.items():
        if (
            type(name) is not str
            or not name.endswith(".whl")
            or Path(name).name != name
            or "/" in name
            or "\\" in name
            or type(expected) is not str
            or SHA256.fullmatch(expected) is None
        ):
            raise ValueError("wheel identity differs")
        path = base / name
        if path.is_symlink() or not path.is_file():
            raise ValueError("cached wheel unavailable")
        size = path.stat().st_size
        total += size
        if size > MAX_WHEEL_BYTES or total > MAX_WHEEL_TOTAL_BYTES:
            raise ValueError("bounded wheel set required")
        body = path.read_bytes()
        if len(body) != size or _digest(body) != expected:
            raise ValueError("cached wheel digest differs")
        wheels[name] = body
    return wheels


def load_cached_bundle_material(cache_root, manifest):
    """Load and validate one complete immutable closure from private local cache.

    This reads only source, lock, license and manifest-named wheel bytes. It
    neither installs packages nor exposes cache paths to the public recipe.
    """
    base = _private_cache_directory(
        cache_root, "private operator bundle cache required"
    )

    def bounded_file(name, limit):
        path = base / name
        if path.is_symlink() or not path.is_file():
            raise ValueError("cached bundle material unavailable")
        size = path.stat().st_size
        if size > limit:
            raise ValueError("cached bundle material exceeds bound")
        body = path.read_bytes()
        if len(body) != size:
            raise ValueError("cached bundle material changed")
        return body

    source = bounded_file("source.tar.gz", MAX_SOURCE_BYTES)
    lock = bounded_file("requirements.txt", MAX_LOCK_BYTES)
    license_text = bounded_file("LICENSE", MAX_LICENSE_BYTES)
    wheels = load_cached_wheels(base / "wheels", manifest)
    validate_bundle(manifest, source, wheels, lock, license_text)
    return source, wheels, lock, license_text


def load_pinned_bundle_directory(directory):
    """Read a user's complete pinned source closure without importing its code.

    The input may be a normal user directory. Only declared regular files are
    read; an operator-owned cache is created separately by the prepare step.
    """
    base = Path(directory)
    if not base.is_dir() or base.is_symlink() or base.resolve() != base.absolute():
        raise ValueError("regular pinned bundle directory required")

    def bounded(path, limit):
        if path.is_symlink() or not path.is_file():
            raise ValueError("pinned bundle file unavailable")
        size = path.stat().st_size
        if size > limit:
            raise ValueError("pinned bundle file exceeds bound")
        body = path.read_bytes()
        if len(body) != size:
            raise ValueError("pinned bundle file changed")
        return body

    try:
        manifest = json.loads(bounded(base / "bundle.json", 65536))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("pinned bundle manifest invalid") from exc
    if type(manifest) is not dict:
        raise ValueError("pinned bundle manifest invalid")
    declared = manifest.get("wheels")
    if type(declared) is not dict or len(declared) > MAX_WHEELS:
        raise ValueError("closed wheel manifest required")
    wheelhouse = base / "wheels"
    if wheelhouse.is_symlink() or not wheelhouse.is_dir():
        raise ValueError("regular pinned wheel directory required")
    source = bounded(base / "source.tar.gz", MAX_SOURCE_BYTES)
    lock = bounded(base / "requirements.txt", MAX_LOCK_BYTES)
    license_text = bounded(base / "LICENSE", MAX_LICENSE_BYTES)
    wheels = {}
    total = 0
    for name in declared:
        if (
            type(name) is not str
            or not name.endswith(".whl")
            or Path(name).name != name
            or "/" in name
            or "\\" in name
        ):
            raise ValueError("wheel identity differs")
        body = bounded(wheelhouse / name, MAX_WHEEL_BYTES)
        total += len(body)
        if total > MAX_WHEEL_TOTAL_BYTES:
            raise ValueError("bounded wheel set required")
        wheels[name] = body
    validate_bundle(manifest, source, wheels, lock, license_text)
    return manifest, source, wheels, lock, license_text


def prepare_pinned_bundle_directory(directory, cache_root, parent_image):
    """Import one validated user closure into the existing offline build path.

    This prepares a sealed context only. The Product host later verifies local
    images, installs with the pinned wheelhouse, and runs ``pip check``.
    """
    material = load_pinned_bundle_directory(directory)
    ref = bundle_ref(*material)
    context, digest, seal = prepare_offline_context(cache_root, *material, parent_image)
    if digest != ref.bundle_digest:
        raise ValueError("pinned bundle identity changed")
    return ref, context, seal


def prepare_offline_context(
    root, manifest, source, wheels, lock, license_text, parent_image
):
    """Write immutable build inputs; image build/adoption is a separate step.

    The exact parent must be verified by the Product host before building.
    No source or wheel is installed on the controller by this function.
    """
    bundle_digest = validate_bundle(manifest, source, wheels, lock, license_text)
    if manifest["runtime_profile_id"] == "python-cpu-py311":
        repository = Path(__file__).resolve().parents[2]
        if manifest["base_environment_digest"] != _digest(
            (repository / "uv.lock").read_bytes()
        ):
            raise ValueError("CPU base environment lock differs")
    if type(parent_image) is not str or not SHA256.fullmatch(parent_image):
        raise ValueError("exact verified parent image required")
    base = _private_cache_directory(
        root, "private operator-owned bundle cache required"
    )
    root = base / bundle_digest[7:] / parent_image[7:]
    if root.is_symlink() or root.parent.is_symlink():
        raise ValueError("bundle cache symlink")
    root.mkdir(parents=True, exist_ok=True, mode=0o700)

    def once(path, body):
        if path.is_symlink():
            raise ValueError("bundle cache symlink")
        if path.exists():
            if path.read_bytes() != body:
                raise ValueError("bundle cache collision")
        else:
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
            with os.fdopen(os.open(path, flags, 0o600), "wb") as output:
                output.write(body)

    once(
        root / "bundle.json",
        json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode(),
    )
    once(root / "source.tar.gz", source)
    once(root / "requirements.txt", lock)
    once(root / "LICENSE", license_text)
    wheelhouse = root / "wheels"
    if wheelhouse.is_symlink():
        raise ValueError("bundle cache symlink")
    wheelhouse.mkdir(exist_ok=True, mode=0o700)
    for name, body in wheels.items():
        once(wheelhouse / name, body)
    # Product verifies/tags BOTH exact local images. Missing local tags fail;
    # neither FROM line can name a registry or cause daemon resolution.
    parent_tag = parent_stage_tag(bundle_digest, parent_image)
    dockerfile = f"""FROM {uv_stage_tag(bundle_digest)} AS uv
FROM {parent_tag}
USER 0:0
COPY --from=uv /uv /tmp/uv
COPY source.tar.gz /tmp/source.tar.gz
COPY bundle.json /tmp/bundle.json
COPY wheels /tmp/wheels
COPY requirements.txt /tmp/requirements.txt
COPY install-source.py /tmp/install-source.py
RUN /opt/carbon-worker/bin/python -I /tmp/install-source.py --check && /opt/carbon-worker/bin/python -I /tmp/install-source.py --snapshot && TMPDIR=/tmp /tmp/uv --no-cache pip install --python /opt/carbon-worker/bin/python --no-index --find-links=/tmp/wheels --require-hashes --no-deps --only-binary=:all: -r /tmp/requirements.txt && TMPDIR=/tmp /tmp/uv pip check --python /opt/carbon-worker/bin/python && /opt/carbon-worker/bin/python -I /tmp/install-source.py --verify && /opt/carbon-worker/bin/python -I /tmp/install-source.py --install && rm -rf /tmp/uv /tmp/wheels /tmp/source.tar.gz /tmp/requirements.txt /tmp/install-source.py /tmp/bundle.json /tmp/before.json
LABEL org.opencontainers.image.carbon.development.library-bundle="{bundle_digest}" org.opencontainers.image.carbon.development.parent="{parent_image}"
USER 65532:65532
"""
    install = """import gzip, hashlib, importlib.metadata, io, json, pathlib, sys, sysconfig, tarfile
manifest = json.loads(pathlib.Path('/tmp/bundle.json').read_bytes())
source = pathlib.Path('/tmp/source.tar.gz').read_bytes()
if len(source) > 32 * 1024 * 1024:
    raise SystemExit('source archive exceeds bound')
with gzip.GzipFile(fileobj=io.BytesIO(source)) as compressed:
    raw = compressed.read(144 * 1024 * 1024 + 1)
if len(raw) > 144 * 1024 * 1024:
    raise SystemExit('decompressed source exceeds bound')
digest = lambda body: 'sha256:' + hashlib.sha256(body).hexdigest()
if digest(source) != manifest['source_sha256'] or digest(pathlib.Path('/tmp/requirements.txt').read_bytes()) != manifest['lock_sha256']:
    raise SystemExit('library source or lock digest differs')
base_lock = {'jax-cuda13-py311': '/opt/carbon/accelerator-requirements.txt', 'torch-cu130-py311': '/opt/carbon/torch-gpu-requirements.txt'}[manifest['runtime_profile_id']]
if digest(pathlib.Path(base_lock).read_bytes()) != manifest['base_environment_digest']:
    raise SystemExit('base environment digest differs')
for name, expected in manifest['wheels'].items():
    if pathlib.Path(name).name != name or digest((pathlib.Path('/tmp/wheels') / name).read_bytes()) != expected:
        raise SystemExit('library wheel digest differs')
seen, roots, count, expanded = set(), set(), 0, 0
with tarfile.open(fileobj=io.BytesIO(raw), mode='r|') as archive:
    for member in archive:
        count += 1
        expanded += member.size
        if count > 4096 or expanded > 128 * 1024 * 1024:
            raise SystemExit('source archive bounds differ')
        parts = pathlib.PurePosixPath(member.name).parts
        if not parts or member.name.startswith('/') or '..' in parts or '\\\\' in member.name or ':' in member.name or member.name.casefold() in seen or not (member.isfile() or member.isdir()):
            raise SystemExit('unsafe source archive member')
        seen.add(member.name.casefold())
        roots.add(parts[0])
if not count:
    raise SystemExit('source archive empty')
if sys.argv[1] == '--check':
    raise SystemExit(0)
installed = lambda: {d.metadata['Name'].lower().replace('_', '-'): d.version for d in importlib.metadata.distributions()}
if sys.argv[1] == '--snapshot':
    pathlib.Path('/tmp/before.json').write_text(json.dumps(installed(), sort_keys=True))
    raise SystemExit(0)
if sys.argv[1] == '--verify':
    before = json.loads(pathlib.Path('/tmp/before.json').read_text())
    after = installed()
    changed = sorted(name for name, version in before.items() if after.get(name) != version)
    if changed:
        raise SystemExit('base worker distribution changed: ' + ', '.join(changed))
    raise SystemExit(0)
if sys.argv[1] != '--install':
    raise SystemExit('unsupported install action')
target = pathlib.Path('/opt/carbon-library-source')
target.mkdir(mode=0o555)
with tarfile.open(fileobj=io.BytesIO(raw), mode='r|') as archive:
    for member in archive:
        path = target.joinpath(*pathlib.PurePosixPath(member.name).parts)
        if member.isdir():
            path.mkdir(parents=True, exist_ok=True)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            with archive.extractfile(member) as source_file, path.open('wb') as output:
                output.write(source_file.read())
site = pathlib.Path(sysconfig.get_paths()['purelib'])
import_root = target / next(iter(roots)) if len(roots) == 1 else target
(site / 'carbon-library-source.pth').write_text(str(import_root) + '\\n')
"""
    if manifest["runtime_profile_id"] == "python-cpu-py311":
        repository = Path(__file__).resolve().parents[2]
        recipe_digest = _digest(
            (repository / ".devcontainer/Dockerfile.reconstruction-worker").read_bytes()
        )
        entrypoint_digest = _digest(
            (repository / "carbon/reconstruction/worker/entrypoint.py").read_bytes()
        )
        cuda_check = """base_lock = {'jax-cuda13-py311': '/opt/carbon/accelerator-requirements.txt', 'torch-cu130-py311': '/opt/carbon/torch-gpu-requirements.txt'}[manifest['runtime_profile_id']]
if digest(pathlib.Path(base_lock).read_bytes()) != manifest['base_environment_digest']:
    raise SystemExit('base environment digest differs')
"""
        cpu_check = f"""build = json.loads(pathlib.Path('/opt/carbon/worker-image-build.json').read_bytes())
if build.get('schema') != 'carbon.c03.worker-image-build.v1' or build.get('lock_digest') != manifest['base_environment_digest'] or build.get('build_recipe_digest') != '{recipe_digest}' or build.get('entrypoint_digest') != '{entrypoint_digest}':
    raise SystemExit('base environment digest differs')
"""
        if install.count(cuda_check) != 1:
            raise ValueError("library installer base-lock check differs")
        install = install.replace(cuda_check, cpu_check)
    once(root / "Dockerfile", dockerfile.encode())
    once(root / "install-source.py", install.encode())
    return root, bundle_digest, _context_digest(root)


def build_offline_bundle(
    context, bundle_digest, parent_image, context_digest, *, cli=None
):
    """Product-only local-image preflight, offline build and image verification.

    `docker image inspect` and `docker tag` use only local daemon state; neither
    can pull. A failed/missing stage refuses before `docker build`. The caller
    must not use a raw Docker build as an adopted Carbon bundle receipt.
    """
    from carbon.reconstruction.worker.docker_runtime import DockerCLI

    if any(
        type(value) is not str or not SHA256.fullmatch(value)
        for value in (bundle_digest, parent_image, context_digest)
    ):
        raise ValueError("exact bundle and parent identities required")
    context = Path(context)
    if context.is_symlink() or not context.is_dir():
        raise ValueError("private bundle context required")
    if _context_digest(context) != context_digest:
        raise ValueError("sealed bundle context differs")
    manifest = context / "bundle.json"
    if manifest.is_symlink() or _digest(manifest.read_bytes()) != bundle_digest:
        raise ValueError("bundle context identity differs")
    dockerfile = context / "Dockerfile"
    first_lines = (
        f"FROM {uv_stage_tag(bundle_digest)} AS uv",
        f"FROM {parent_stage_tag(bundle_digest, parent_image)}",
    )
    if (
        dockerfile.is_symlink()
        or tuple(dockerfile.read_text().splitlines()[:2]) != first_lines
    ):
        raise ValueError("local-only library build stages required")
    cli = cli or DockerCLI()

    def local_image(reference):
        try:
            image = cli.json(["image", "inspect", reference, "--format", "{{json .}}"])
        except Exception as exc:
            raise ValueError("required local image absent") from exc
        if (
            type(image) is not dict
            or type(image.get("Id")) is not str
            or not SHA256.fullmatch(image["Id"])
        ):
            raise ValueError("required local image identity invalid")
        return image

    parent = local_image(parent_image)
    if parent["Id"] != parent_image:
        raise ValueError("local parent image differs")
    uv = local_image(UV_IMAGE)
    uv_name, _, uv_digest = UV_IMAGE.partition("@")
    uv_repo_digest = uv_name.rsplit(":", 1)[0] + "@" + uv_digest
    if uv_repo_digest not in uv.get("RepoDigests", []):
        raise ValueError("pinned local uv image differs")
    parent_tag = parent_stage_tag(bundle_digest, parent_image)
    uv_tag = uv_stage_tag(bundle_digest)
    cli.run(["tag", parent_image, parent_tag])
    cli.run(["tag", uv["Id"], uv_tag])
    if (
        local_image(parent_tag)["Id"] != parent_image
        or local_image(uv_tag)["Id"] != uv["Id"]
    ):
        raise ValueError("local build stage tag differs")
    built = cli.run(
        [
            "build",
            "--network=none",
            "--pull=false",
            "--platform=linux/amd64",
            "-q",
            str(context),
        ],
        timeout=600,
    )
    image_id = built.stdout.decode().strip()
    if not SHA256.fullmatch(image_id):
        raise ValueError("built image identity unavailable")
    result = local_image(image_id)
    labels = result.get("Config", {}).get("Labels", {})
    layers = parent.get("RootFS", {}).get("Layers", [])
    if (
        result["Id"] != image_id
        or result.get("Os") != "linux"
        or result.get("Architecture") != "amd64"
        or result.get("Config", {}).get("User") != "65532:65532"
        or labels.get("org.opencontainers.image.carbon.development.library-bundle")
        != bundle_digest
        or labels.get("org.opencontainers.image.carbon.development.parent")
        != parent_image
        or not layers
        or result.get("RootFS", {}).get("Layers", [])[: len(layers)] != layers
    ):
        raise ValueError("built library image binding differs")
    return image_id


def provision_offline_bundle(
    root,
    expected_bundle_ref,
    manifest,
    source,
    wheels,
    lock,
    license_text,
    parent_image,
    *,
    cli=None,
):
    """Resolve a complete closure into one sealed context and local child image.

    This operator-side composition retains both independent checks. It never
    consults the discovery catalogue, fetches dependencies, or grants a recipe
    evaluation authority. The caller still verifies the child at dispatch.
    """
    expected = LibraryBundleRef.from_dict(expected_bundle_ref)
    context, bundle_digest, context_digest = prepare_offline_context(
        root, manifest, source, wheels, lock, license_text, parent_image
    )
    actual = LibraryBundleRef(
        REF_SCHEMA,
        bundle_digest,
        manifest["language"],
        manifest["runtime_profile_id"],
        manifest["environment_digest"],
    )
    if actual != expected:
        raise ValueError("recipe bundle reference differs from resolved closure")
    image_id = build_offline_bundle(
        context, bundle_digest, parent_image, context_digest, cli=cli
    )
    return ProvisionedLibraryEnvironment(
        actual,
        parent_image,
        context,
        context_digest,
        image_id,
    )
