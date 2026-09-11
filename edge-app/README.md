# 🌐 MODO Edge Application (Cloudflare Workers)

This directory contains the edge-deployed frontend and proxy gateway for **MODO (墨斗)**, running on the **Cloudflare Workers** global edge network.

- **Live URL**: [https://modo.53.workers.dev](https://modo.53.workers.dev)
- **Framework**: [Hono](https://hono.dev/) on Cloudflare Workers
- **Runtime**: Cloudflare Workerd (V8 isolates)

---

## 🏗️ Architecture & Responsibilities

```text
Browser Client
      │ (HTTPS / TLS 1.3)
      ▼
Cloudflare Workers Edge (modo.53.workers.dev)
      ├─ GET / ───────────────────────────> Serves SPA Dashboard (src/index.html)
      ├─ GET /api/* (Hono Router) ────────> Reverse proxy to https://api-modo.8n8m.cfd
      │                                     (Cloudflare Tunnel -> USA Central Hub)
      └─ Scheduled Cron (0 3 * * *) ──────> Edge keepalive & scheduled health checks
```

1. **Edge Dashboard SPA (`src/index.html`)**:
   - Single Page Application built with **ECharts 5** (Supabase dark neon theme) and vanilla modern JS.
   - **4-Curtain Panorama**:
     - **Curtain 1 (Global Fleet Overview)**: Fleet health index, real-time node count, resource utilization gauges, and latency leaderboard.
     - **Curtain 2 (Dynamic Mesh Radar)**: 11-node multi-cloud topology map with dynamic particle flow lines converging towards the **USA (Ashburn)** central hub. Particle animation speeds and line colors are driven by **HeatWave AutoML** latency predictions.
     - **Curtain 3 (Timeseries Waveforms)**: Live streaming CPU, memory, network I/O, and disk space charts.
     - **Curtain 4 (AI Diagnostics & AutoML)**: Real-time autonomous anomaly heuristics and HeatWave in-database regression forecasts.
   - **Security**: Supabase Auth glassmorphic login modal with session persistence.

2. **Edge Proxy API Router (`src/index.ts`)**:
   - Built on **Hono v4** with global CORS and anti-caching headers (`no-store, no-cache`).
   - Routes requests to the private API gateway (`https://api-modo.8n8m.cfd`) through the Zero-Trust Cloudflare Tunnel:
     - `/api/nodes/latest`: Latest fleet telemetry metrics.
     - `/api/ai/diagnostics`: Fleet health analysis and diagnostic logs.
     - `/api/metrics/history`: Historical metric rollups per node.
     - `/api/predict/latency`: HeatWave AutoML latency forecasting endpoint.

---

## 🛠️ Development & Deployment

### 1. Installation

```bash
npm install
```

### 2. Local Development

Run the local development server using Cloudflare Wrangler:

```bash
npm run dev
# Starts local development worker on http://localhost:8787
```

### 3. Generate Cloudflare Bindings Types

```bash
npm run cf-typegen
```

### 4. Production Deployment

Deploy directly to Cloudflare Workers:

```bash
npm run deploy
# Executes wrangler deploy --minify
```

Automated deployments are also triggered on push to `main` via `.github/workflows/deploy.yml`.

---

## ⚙️ Configuration (`wrangler.jsonc`)

| Variable | Description | Default |
| :--- | :--- | :--- |
| `name` | Cloudflare Worker name | `modo` |
| `compatibility_date` | Worker runtime compatibility date | `2026-08-20` |
| `vars.API_BACKEND_URL` | Upstream private API gateway via Cloudflare Tunnel | `https://api-modo.8n8m.cfd` |
| `vars.SUPABASE_URL` | Supabase Authentication project URL | `https://qkpwuxaylvzycapkojvq.supabase.co` |
| `triggers.crons` | Scheduled trigger interval | `0 3 * * *` |
