#!/usr/bin/env bash
set -euo pipefail

case "${1:-}" in
  package-doctor)
    exec python -m carbon.evidence_archive.alpha_package \
      deploy/evidence_archive/aws_private_alpha
    ;;
  configuration-doctor)
    [[ $# -eq 2 ]]
    exec python -m carbon.evidence_archive.alpha_doctor "$2"
    ;;
  recovery-doctor)
    [[ $# -eq 3 ]]
    exec python -m carbon.evidence_archive.alpha_recovery "$2" "$3"
    ;;
  *)
    echo "usage: $0 {package-doctor|configuration-doctor CONFIG|recovery-doctor WATERMARK OBSERVATION}" >&2
    exit 2
    ;;
esac
