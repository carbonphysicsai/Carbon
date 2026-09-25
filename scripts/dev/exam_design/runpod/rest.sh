#!/usr/bin/env bash
# REST helper. usage: rest.sh METHOD /path [json-body]. Key from ~/.runpod/api_key, never echoed or put in argv.
if [ -n "${3:-}" ]; then
  printf '%s' "$3" | curl -sS -m 60 -X "$1" "https://rest.runpod.io/v1$2" -H 'Content-Type: application/json' \
    -H @<(printf 'Authorization: Bearer %s\n' "$(cat ~/.runpod/api_key)") -d @-
else
  curl -sS -m 60 -X "$1" "https://rest.runpod.io/v1$2" -H @<(printf 'Authorization: Bearer %s\n' "$(cat ~/.runpod/api_key)")
fi
