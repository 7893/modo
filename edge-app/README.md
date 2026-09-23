# MODO Edge Application

Cloudflare Worker entrypoint and dashboard shell for MODO.

## Structure

- `src/index.ts`: Hono routes, authenticated backend proxy, and HTML composition.
- `src/index.html`: document shell only.
- `src/fragments/`: six dashboard curtains and the authentication modal.
- `src/client/`: browser behavior split into core loading, insights, charts, and authentication.
- `src/tailwind.css`: Tailwind CLI input.
- `src/tailwind.generated.css`: generated output; do not edit by hand.

The Worker imports HTML, CSS, and `*.client.js` files as text modules and assembles
one response document. First-party source files must remain at or below 400 lines.

## Commands

```bash
pnpm install
pnpm dev
pnpm run cf-typegen
pnpm deploy
```

The development and deployment scripts regenerate the static Tailwind stylesheet
before invoking Wrangler.
