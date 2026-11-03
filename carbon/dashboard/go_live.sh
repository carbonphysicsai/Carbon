#!/usr/bin/env bash
# The dashboard go-live: fetch the launch feeds, build the live site, dry-run the deploy.
# With --deploy it also deploys the Worker, sets its feed secrets and checks the public site.
#
#   bash carbon/dashboard/go_live.sh            # fetch + build + wrangler dry run, changes nothing
#   bash carbon/dashboard/go_live.sh --deploy   # the same, then deploy + secrets + verify
#
# Settings live outside the repository, in ~/.config/carbon (or $CARBON_CONFIG_DIR):
#   dashboard-feed-urls  comma-separated https feed URLs, one per launch Challenge
#                        (https://<door>/carbon/v1/feed/<challenge>); a door that answers 404
#                        has nothing published yet and its Challenge shows "Launching soon"
#   dashboard-feed-keys  the pinned feed public key(s), 64 hex, from the validator's configuration
#   cloudflare-dashboard.token / cloudflare-account-id  as DASHBOARD_CLOUDFLARE_SETUP.md section 1
# Roll back with: npx wrangler@4.151.3 rollback --config carbon/dashboard/wrangler.dashboard.toml
set -euo pipefail

cd "$(dirname "$0")/../.."
config="${CARBON_CONFIG_DIR:-$HOME/.config/carbon}"
site="${CARBON_DASHBOARD_SITE:-$HOME/carbon-dashboard-site-$(date +%Y%m%d-%H%M%S)}"
wrangler="${WRANGLER:-npx wrangler@4.151.3}"
public="${DASHBOARD_PUBLIC_URL:-https://dashboard.carbonphysics.ai}"
toml=carbon/dashboard/wrangler.dashboard.toml

python -m carbon.dashboard live \
  --urls-file "$config/dashboard-feed-urls" \
  --keys-file "$config/dashboard-feed-keys" \
  --names carbon/dashboard/names.launch.json \
  --out "$site"

$wrangler deploy --dry-run --config "$toml" --assets "$site"

if [ "${1:-}" != "--deploy" ]; then
  echo "Dry run only. Site built in $site. To go live: bash carbon/dashboard/go_live.sh --deploy"
  exit 0
fi

if [ -z "${CLOUDFLARE_API_TOKEN:-}" ]; then
  CLOUDFLARE_API_TOKEN="$(cat "$config/cloudflare-dashboard.token")"
  export CLOUDFLARE_API_TOKEN
fi
if [ -z "${CLOUDFLARE_ACCOUNT_ID:-}" ]; then
  CLOUDFLARE_ACCOUNT_ID="$(cat "$config/cloudflare-account-id")"
  export CLOUDFLARE_ACCOUNT_ID
fi

$wrangler deploy --config "$toml" --assets "$site"

secrets="$config/dashboard-secrets.json"
python - "$config" "$secrets" <<'PY'
import json, os, pathlib, sys
config, out = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
fd = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
    json.dump({
        "FEED_URLS": (config / "dashboard-feed-urls").read_text(encoding="utf-8").strip(),
        "FEED_KEYS": (config / "dashboard-feed-keys").read_text(encoding="utf-8").strip(),
    }, handle)
PY
$wrangler secret bulk "$secrets" --config "$toml"

echo "Waiting for the Worker to pick up its feeds..."
sleep 70
curl -fsS "$public/data/index.json" | python -c '
import json, sys
index = json.load(sys.stdin)
print("fixture:", index["fixture"])
for board in index["boards"]:
    print(board["state"], board["slug"], board["code"] or "")
if index["fixture"] or not index["boards"] or any(b["state"] != "ACCEPTED" for b in index["boards"]):
    sys.exit("CHECK FAILED: roll back with wrangler rollback")
print("live: every listed board is ACCEPTED")
'
