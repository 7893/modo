#!/usr/bin/env bash
# Render the cloudflared config from the template using values supplied via
# environment variables (sourced from secrets, never committed to the repo).
#
# Usage (on the tunnel host):
#   CF_TUNNEL_ID=... CF_TUNNEL_HOSTNAME=... \
#   CF_TUNNEL_CREDENTIALS_FILE=/etc/cloudflared/tunnel.json \
#     deploy/render-cloudflared.sh > /etc/cloudflared/config.yml
#   sudo systemctl restart cloudflared   # apply once, after verifying output
#
# Restarting cloudflared interrupts the tunnel briefly, so run it deliberately.
set -euo pipefail

: "${CF_TUNNEL_ID:?CF_TUNNEL_ID is required}"
: "${CF_TUNNEL_HOSTNAME:?CF_TUNNEL_HOSTNAME is required}"
: "${CF_TUNNEL_CREDENTIALS_FILE:?CF_TUNNEL_CREDENTIALS_FILE is required}"

template_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export CF_TUNNEL_ID CF_TUNNEL_HOSTNAME CF_TUNNEL_CREDENTIALS_FILE
envsubst '${CF_TUNNEL_ID} ${CF_TUNNEL_HOSTNAME} ${CF_TUNNEL_CREDENTIALS_FILE}' < "${template_dir}/cloudflared.yml.template"
