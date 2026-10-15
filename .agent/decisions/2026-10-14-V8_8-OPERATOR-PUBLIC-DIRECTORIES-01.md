# V8_8-OPERATOR-PUBLIC-DIRECTORIES-01: explicit public traversal modes

Domain: public operator packaging; IMPLEMENTATION_LAG. Root's actual R3
nonroot mirror failed because private builder umask077 left nested public
directories0700 in the image. Existing file chmod does not fix traversal.

REPAIR prospective materialize only: collect directory paths from the already
validated public manifest rows plus the new release root; seal those0755 after
writing immutable files. Never walk/chmod the builder's parent/private tree or
change process umask. Keep manifest format/file hashes and historical verify.

The regression uses actual Git materialization under077, finally restores its
caller mask, and checks all nested public directories, executable/nonexecutable
file modes and unchanged private ancestor/cache/secret permissions. Root owns
real default-nonroot image verify and host mirror; a fixture is not that proof.
R3 artifact/receipts remain held historical evidence. No host chmod/root-user
workaround, private-mount expansion, new framework or authority change.
