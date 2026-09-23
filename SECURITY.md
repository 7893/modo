# Security Policy

## Supported version

Security fixes target the current `main` branch until versioned releases define
a broader support policy.

## Reporting a vulnerability

Do not open a public issue for suspected vulnerabilities or exposed
credentials. Use the repository's private GitHub Security Advisory reporting
channel and include:

- the affected component and revision;
- reproduction steps or a minimal proof of concept;
- expected impact;
- any suggested mitigation.

Do not include live credentials, private keys, production hostnames, or complete
node inventories in the report. Treat any discovered credential as compromised.

## Secret handling

MODO expects secrets to be injected at runtime:

- backend settings belong in an ignored `.env`;
- Worker development settings belong in an ignored `.dev.vars`;
- production Worker secrets should be managed by Cloudflare or CI secret
  storage;
- node inventories belong in ignored `data-bridge/config/nodes.json`;
- tunnel credentials must remain outside the repository.

Only placeholder values belong in example files. Never commit database
passwords, internal API secrets, Supabase server-side secrets, SSH keys, tunnel
credentials, or production IP inventories.

## Deployment boundary

The FastAPI backend is designed as a private gateway. The Cloudflare Worker
injects `X-Internal-Secret` when proxying requests. Deployments should keep the
backend and MySQL HeatWave endpoints off the public Internet.

Automated tests must use mocks or disposable infrastructure owned by the person
running the test. Project tests must never infer permission to connect to a
configured production environment.

## If a secret is committed

1. Revoke or rotate it immediately.
2. Remove it from the current tree.
3. Rewrite or replace the affected Git history before public distribution.
4. Review forks, CI logs, artifacts, and deployment systems for exposure.
5. Document the incident without copying the secret value.
