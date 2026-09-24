#!/usr/bin/env bash
# GraphQL helper. usage: rp.sh '<graphql>'. Key from ~/.runpod/api_key (mode 600), never echoed or put in argv.
python3 -c 'import json,sys; print(json.dumps({"query":sys.argv[1]}))' "$1" \
 | curl -sS -m 40 https://api.runpod.io/graphql -H 'Content-Type: application/json' \
     -H @<(printf 'Authorization: Bearer %s\n' "$(cat ~/.runpod/api_key)") -d @-
