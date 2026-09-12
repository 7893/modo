#!/usr/bin/env bash
# Render the cloudflared config from the template using values supplied via
# environment variables (sourced from secrets, never committed to the repo).
#
# Usage (on the tunnel host):
#   CF_TUNNEL_ID=... CF_TUNNEL_HOSTNAME=... \
#     deploy/render-cloudflared.sh > /home/ubuntu/.cloudflared/config.yml
#   sudo systemctl restart cloudflared   # apply once, after verifying output
#
# Restarting cloudflared interrupts the tunnel briefly, so run it deliberately.
set -euo pipefail

: "${CF_TUNNEL_ID:?CF_TUNNEL_ID is required}"
: "${CF_TUNNEL_HOSTNAME:?CF_TUNNEL_HOSTNAME is required}"

template_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export CF_TUNNEL_ID CF_TUNNEL_HOSTNAME
envsubst '${CF_TUNNEL_ID} ${CF_TUNNEL_HOSTNAME}' < "${template_dir}/cloudflared.yml.template"
