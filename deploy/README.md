# Deployment templates

Files in this directory are reference templates. They are not installed or
activated by the repository's local development workflow.

## systemd units

The sample units assume:

- a dedicated `modo` service account;
- a checkout at `/opt/modo`;
- a Python environment at `/opt/modo/data-bridge/venv`;
- runtime configuration at `/etc/modo/modo.env`;
- logs collected by the systemd journal.

Review and adapt these paths before copying a unit into `/etc/systemd/system`.
Use either the unified `modo.service` or the two separate API and ingestion
units, not both layouts at once.

## Cloudflare Tunnel

`render-cloudflared.sh` renders `cloudflared.yml.template` from three required
environment variables:

- `CF_TUNNEL_ID`;
- `CF_TUNNEL_HOSTNAME`;
- `CF_TUNNEL_CREDENTIALS_FILE`.

Inspect the rendered file before restarting a tunnel. Tunnel creation,
credential provisioning, and service restarts are operator-controlled actions.

## GitHub deployment workflow

The deployment workflow is manual and each target must be selected explicitly.
The backend job expects these production-environment secrets:

- `DEPLOY_HOST`, `DEPLOY_SSH_KEY`, and `DEPLOY_KNOWN_HOSTS`;
- optional `DEPLOY_USER` (defaults to `modo`);
- optional `DEPLOY_PATH` (defaults to `/opt/modo`).

The Worker job expects the Cloudflare, backend, Supabase, and internal-secret
values named in `.github/workflows/deploy.yml`. Its optional
`TOPOLOGY_HUB_NODE` GitHub environment variable selects the map hub. Configure
environment approval rules before enabling either job.
