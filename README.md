# 🌐 MODO (墨斗) // 多云分布式边缘数据网关与拓扑大屏

[![CI](https://github.com/7893/modo/actions/workflows/ci.yml/badge.svg)](https://github.com/7893/modo/actions/workflows/ci.yml)
[![Deploy to Cloudflare Workers](https://github.com/7893/modo/actions/workflows/deploy.yml/badge.svg)](https://github.com/7893/modo/actions/workflows/deploy.yml)
[![Production Dashboard](https://img.shields.io/badge/Live%20Demo-modo-06b6d4?style=flat-square&logo=cloudflare)](https://modo.53.workers.dev)
[![License: MIT](https://img.shields.io/badge/License-MIT-purple.svg?style=flat-square)](LICENSE)

> **MODO（墨斗）—— 专为多云分布式拓扑打造的轻量边缘网关与全景拓扑大屏。**  
> 采用无状态解耦设计，前置 **Cloudflare Workers (Hono)** 全球边缘代理，结合 **Cloudflare Tunnel** 与 USA **FastAPI** 节点元数据网关。

---

## ⚡ Production Endpoints

| Service | Access URL | Architecture Role | Status |
| :--- | :--- | :--- | :---: |
| 🌐 **MODO Command Dashboard** | [`https://modo.53.workers.dev`](https://modo.53.workers.dev) | Edge Worker UI + ECharts 5 Multi-Curtain Panorama | 🟢 **ONLINE** |
| 🚇 **MODO Private API Gateway** | `https://api-modo.8n8m.cfd` | Zero-Trust Cloudflare Tunnel ➡️ FastAPI Node Gateway | 🟢 **ACTIVE** |

---

## 🗺️ System Architecture

```text
                             【Client / Operations】
                                        │  (HTTPS / TLS 1.3)
                                        ▼
                   ┌─────────────────────────────────────────┐
                   │      Cloudflare Edge Network (CDN)      │
                   │        https://modo.53.workers.dev      │
                   │                                         │
                   │  • Hono.js Edge Application             │
                   │  • ECharts 5 Dark Neon Theme            │
                   │  • 4-Curtain Multi-Screen Dashboard     │
                   │  • Anti-Cache & Rate Limiting Guard     │
                   └────────────────────┬────────────────────┘
                                        │  (Encrypted Edge Proxy)
                                        ▼
                   ┌─────────────────────────────────────────┐
                   │     Cloudflare Tunnel (QUIC Protocol)   │
                   │          api-modo.8n8m.cfd              │
                   └────────────────────┬────────────────────┘
                                        │  (Zero-Trust Private Ingress)
                                        ▼
                   ┌─────────────────────────────────────────┐
                   │       usa (US Ashburn Central Hub)      │
                   │                                         │
                   │  • systemd: modo.service                │
                   │  • Lightweight FastAPI Gateway (8000)   │
                   │  • Multi-Cloud Node Registry            │
                   └────────────────────┬────────────────────┘
                                        │
                                        │ (Target Fleet Definition)
                                        ▼
                   ┌─────────────────────────────────────────┐
                   │        11 Multi-Cloud Fleet Nodes       │
                   │                                         │
                   │ • Ashburn (usa, usb, usc)               │
                   │ • Osaka / Tokyo (jpa, jpb, jpc, jpd,    │
                   │   jpe)                                  │
                   │ • Singapore (sga), Taiwan (gcp)         │
                   │ • Beijing (cna)                         │
                   └─────────────────────────────────────────┘
```

---

## 🚀 Key Features

* 🌐 **多云拓扑雷达大屏 (Curtain 2)**：基于 ECharts 5 渲染的全球 11 节点地理拓扑网格，覆盖阿什本、大阪、东京、新加坡、台湾及北京节点，动态粒子流直观汇聚至 **USA（阿什本中枢）**。
* 🚇 **轻量无状态网关**：全面剥离重型数据库依赖，专注多云节点元数据治理、IP 映射与边缘 API 安全代理。
* 🛡️ **Zero-Trust 隧道防护**：源站零公网开放端口，所有流量通过 Cloudflare Tunnel 穿透至内网 `127.0.0.1:8000`。
* ⚡ **系统级进程守护**：USA 生产中枢使用 `modo.service`（由 `src/run_unified.py` 驱动）实施进程级自愈与崩溃重启。
* 🔄 **自动化 CI/CD 流水线**：代码提交至 `main` 自动触发 GitHub Actions，自动化构建、校验并热部署至 Cloudflare Workers 边缘网络。

---

## 📂 Monorepo Structure

```text
modo/
├── .github/
│   └── workflows/
│       ├── ci.yml                 # Pytest & TypeScript verification
│       └── deploy.yml             # Cloudflare Workers automated deployment & USA rsync
├── data-bridge/                   # Lightweight Backend API Gateway (Python)
│   ├── config/
│   │   └── nodes.json             # Multi-cloud target node metadata
│   ├── src/
│   │   ├── api.py                 # FastAPI REST server (/health, /api/nodes/summary)
│   │   └── run_unified.py         # Supervisor daemon for API Gateway (port 8000)
│   ├── tests/                     # Unit test suite
│   │   └── test_api.py            # API endpoint tests
│   └── requirements.txt           # Minimal Python dependencies
├── deploy/                        # Deployment configuration
│   ├── modo.service               # Unified systemd unit for API Gateway
│   └── cloudflared.yml            # Cloudflare Tunnel ingress configuration
└── edge-app/                      # Edge Application (Cloudflare Workers)
    ├── src/
    │   ├── index.ts               # Hono app & Edge API Router
    │   └── index.html             # Multi-Curtain Dashboard SPA (ECharts 5)
    ├── package.json               # Node.js dependencies
    └── wrangler.jsonc             # Cloudflare Worker configuration
```

---

## 🛠️ Quick Start

### 1. Prerequisites
* Python 3.12+
* Node.js 22+ & pnpm / npm
* Cloudflare account with Wrangler CLI configured

### 2. Backend Gateway Setup
```bash
cd data-bridge
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run Unit Tests
pytest -v tests/test_api.py

# Start Gateway Daemon via Supervisor
python src/run_unified.py
```

### 3. Edge Worker Setup
```bash
cd edge-app
npm install

# Local development
npm run dev

# Deploy to Cloudflare Workers
npm run deploy
```

---

## 📄 License
This project is licensed under the [MIT License](LICENSE).
