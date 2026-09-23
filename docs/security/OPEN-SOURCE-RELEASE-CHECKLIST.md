# Open-source release security checklist

This checklist separates repository preparation from production operations. It
does not authorize secret rotation, Git history rewriting, deployment, or
database changes.

## Repository contents

- [x] Current tracked files contain no live credentials or private keys.
- [x] Production hostnames, public IP inventories, tunnel IDs, and personal
      domains are absent or replaced with documentation placeholders.
- [x] `.env`, `.dev.vars`, node inventories, logs, dependencies, caches, and
      generated assets are ignored.
- [x] Example configuration contains only non-routable or clearly fake values.
- [x] README and diagrams describe a configurable reference architecture.
- [x] License, contribution guidance, and security reporting guidance exist.

## Git history

A clean working tree does not make old Git objects safe. Before publishing,
choose one reviewed strategy:

1. Create a new public repository from the sanitized tree when preserving
   private development history is unnecessary.
2. Rewrite the existing history with a reviewed path/value removal plan when
   history must be preserved.

History rewriting changes commit IDs and requires coordination with every
clone. Do not force-push until affected credentials have been rotated and
collaborators have been notified.

After either strategy, independently scan all reachable refs and release
artifacts. Never include the sensitive values themselves in scan output or
documentation.

## Local quality gates

- [x] `python scripts/check_source_file_lines.py`
- [x] Python compilation and unit tests
- [x] Tailwind CSS generation
- [x] Wrangler type generation
- [x] TypeScript type checking
- [x] Wrangler deployment dry run
- [x] Local Worker root-page smoke test
- [x] `git diff --check`

The local quality gates above were last run on 2026-09-23. They do not cover a
real HeatWave connection, production infrastructure, or publication history.

Oracle MySQL HeatWave deployment checks are documented separately and do not
require contributors to install a local database.

## External actions requiring explicit approval

- [x] Assess historical credential exposure; the project owner confirmed the
      historical internal value is no longer active and needs no further rotation.
- [x] Selectively rewrite the local branch history to remove sensitive paths
      and values while preserving its commit topology.
- [ ] Push rewritten refs or create the public repository.
- [ ] Configure production secrets.
- [ ] Deploy the Worker or backend services.
