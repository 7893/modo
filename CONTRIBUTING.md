# Contributing to MODO

Thanks for helping improve MODO. Contributions should remain reproducible without
requiring access to the maintainers' infrastructure.

## Development principles

- Never commit credentials, production addresses, tunnel identifiers, or private
  node inventories.
- Keep every first-party source file at or below 400 physical lines. Generated
  output and vendored dependencies are exempt.
- Keep Oracle MySQL HeatWave integration behind environment configuration.
- Unit tests must not connect to real nodes, databases, Supabase projects, or
  Cloudflare accounts.
- Preserve unrelated worktree changes and document behavior changes.

## Local setup

Backend:

```bash
cd data-bridge
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pytest -v tests/
```

The Python test suite uses fixtures and mocks. A local MySQL installation is not
required.

Edge Worker:

```bash
cd edge-app
pnpm install --frozen-lockfile
cp .dev.vars.example .dev.vars
pnpm build:css
pnpm run cf-typegen
pnpm run typecheck
pnpm exec wrangler deploy --dry-run
```

Do not edit `src/tailwind.generated.css` or
`worker-configuration.d.ts`; both are generated and ignored.

## Node configuration

Copy `data-bridge/config/nodes.json.example` to
`data-bridge/config/nodes.json`, then replace the documentation-only addresses
with nodes you control. The local file is ignored by Git.

## Pull requests

Before opening a pull request:

1. Run `python scripts/check_source_file_lines.py`.
2. Run the Python test suite.
3. Run the edge CSS build, type check, and Wrangler dry run.
4. Update documentation and relevant Known Issue records.
5. Confirm `git diff --check` is clean.
6. Review the diff for credentials and environment-specific identifiers.

Keep pull requests focused. Explain operational or schema changes and identify
any validation that must occur later in the contributor's own HeatWave
environment.

## Known Issues

The register at `docs/KNOWN-ISSUES.md` tracks code defects and technical debt.
A real HeatWave deployment check may be recorded as deployment verification
without forcing contributors to install a local database.
