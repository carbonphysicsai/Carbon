# CI-REGISTRY-MIRROR-01: resolve Docker Hub through a pull-through mirror

## What failed

On 2026-10-09 from about 21:00 UTC, `Canonical environment (0)` failed on
every open pull request it ran on -- #908, #939, #942 and #944 -- on four
different runners, with the same error while building the pinned canonical
image:

```
ERROR: failed to build: failed to solve: failed to copy: httpReadSeeker:
failed open: unexpected status code
https://registry-1.docker.io/v2/library/ubuntu/manifests/sha256:33ceb719...
toomanyrequests
```

`tests/cpu/test_canonical_wrapper.py::test_docker_backed_*` could not build
`carbon-canonical` because the anonymous Docker Hub pull of
`library/ubuntu` was rate limited.

This is an infrastructure limit, not a scientific or test result, and the
typed distinction matters: no candidate failed a test.

## What was ruled out

- Not a stale container or name collision: four runners, four container
  names.
- Not a change on main: nothing merged on 2026-10-09 touched the docker,
  postgres or canonical fixtures.
- Not a stale base: #908 failed again after being reconciled onto current
  main, and #907, #911 and #941 had passed the same shard minutes earlier.

## Decision

Configure the CI runner's Docker daemon to resolve Docker Hub through
`https://mirror.gcr.io`, a read-through cache of Docker Hub.

No image pin, Dockerfile or derived tag changes.

## Why not edit the pinned `FROM` line

Rewriting `.devcontainer/Dockerfile` to name the mirror directly would
change the file, and `scripts/dev/canonical.sh` derives the canonical image
tag from the Dockerfile's hash:

```
image_tag="carbon-canonical:${dockerfile_id:0:16}"
```

`.devcontainer/Dockerfile.julia-science` pins that exact tag *and* the built
image's own digest:

```
FROM carbon-canonical:d9bc9b882f702299@sha256:3dc42abf...
```

so editing the `FROM` line would break a dependent image's pin and require
rebuilding and re-pinning it, with its own release evidence. Configuring the
daemon leaves every pin byte-identical.

## Why the mirror does not weaken the pin

Every Carbon base image is pinned by digest. A digest names its content, and
the daemon verifies the content hash of what it receives, so a mirror cannot
substitute different bytes: it can only serve the same image or fail. The
mirror was verified to serve this exact digest before the change:

```
$ curl -D - https://mirror.gcr.io/v2/library/ubuntu/manifests/sha256:33ceb71981b602c1a7443a53469e4dba065f7503eab3078a2d7a57a2ab987517
HTTP/1.1 200 OK
Docker-Content-Digest: sha256:33ceb71981b602c1a7443a53469e4dba065f7503eab3078a2d7a57a2ab987517
```

This is not a security qualification of the mirror or of the image. It
records that the change cannot alter image content, because content
addressing -- not the host -- is what establishes identity.

## Scope

The step is added to the `Canonical environment` job, which is the job
observed to fail. The other image-building jobs (`Clean dev-container
image`, the isolated service acceptances) were skipped on the affected pull
requests and have not been observed to hit the limit; the same step belongs
in them if they do.

## Authority

The owner approved a CI mirror. The approval was relayed through the Test
Lead; it authorizes an engineering CI change only and carries no security
acceptance, no production authority and no change to any image pin.
