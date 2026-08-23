# 🌐 Nexus // Global Fleet Telemetry & AI Command Center

[![CI](https://github.com/7893/nexus/actions/workflows/ci.yml/badge.svg)](https://github.com/7893/nexus/actions/workflows/ci.yml)
[![Deploy to Cloudflare Workers](https://github.com/7893/nexus/actions/workflows/deploy.yml/badge.svg)](https://github.com/7893/nexus/actions/workflows/deploy.yml)
[![Production Dashboard](https://img.shields.io/badge/Live%20Demo-nexus.53.workers.dev-06b6d4?style=flat-square&logo=cloudflare)](https://nexus.53.workers.dev)
[![License: MIT](https://img.shields.io/badge/License-MIT-purple.svg?style=flat-square)](LICENSE)

> **Next-Gen Multi-Cloud Edge Telemetry, Time-Series Ingestion & AI Automated Operations Platform.**  
> Powered by **Cloudflare Workers (Hono)**, **Cloudflare Tunnel (Zero Trust)**, **OCI MySQL HeatWave 26.7 Cloud**, and **FastAPI**.

---

## ⚡ Live Production Endpoints

| Service | Access URL | Architecture Role | Status |
| :--- | :--- | :--- | :---: |
| 🌐 **Nexus Command Dashboard** | [`https://nexus.53.workers.dev`](https://nexus.53.workers.dev) | Global Edge Worker UI + ECharts 5 + Supabase Auth | 🟢 **ONLINE** |
| 🚇 **Nexus Private API Gateway** | `https://api-nexus.8n8m.cfd` | Zero-Trust Cloudflare Tunnel ➡️ FastAPI Bridge | 🟢 **ACTIVE** |
| 🗄️ **Time-Series Telemetry Store** | Private Subnet (`REDACTED_HOST:3306`) | Oracle Cloud MySQL HeatWave DB System | 🟢 **ACTIVE** |

---

## 🗺️ System Architecture

```text
                               【Global Users & Operations】
                                             │  (HTTPS / TLS 1.3)
                                             ▼
                        ┌─────────────────────────────────────────┐
                        │      Cloudflare Edge Network (CDN)      │
                        │       https://nexus.53.workers.dev      │
                        │                                         │
                        │  • Hono.js Edge Application             │
                        │  • ECharts 5 Global Pulse Radar Map     │
                        │  • Real-time Waveform Charts            │
                        │  • Supabase Auth Security Guard         │
                        └────────────────────┬────────────────────┘
                                             │  (Encrypted Edge Proxy)
                                             ▼
                        ┌─────────────────────────────────────────┐
                        │     Cloudflare Tunnel (QUIC Protocol)   │
                        │          api-nexus.8n8m.cfd             │
                        └────────────────────┬────────────────────┘
                                             │  (Zero-Trust Private Ingress)
                                             ▼
                        ┌─────────────────────────────────────────┐
                        │       usa (US Ashburn Ingestion Hub)    │
                        │                                         │
                        │  • systemd: nexus-api.service (FastAPI) │
                        │  • systemd: nexus-ingest.service (60s)  │
                        └──────────────┬──────────────────┬───────┘
                                       │                  │
                (Prometheus Scrape)   │                  │ (Private Subnet TCP 3306)
                                       ▼                  ▼
             ┌────────────────────────────────────┐   ┌───────────────────────────┐
             │     10 Global Cloud VM Fleet       │   │    Oracle Cloud MySQL     │
             │                                    │   │   HeatWave 26.7 Cloud     │
             │ • Tokyo (jpa, jpb, jpc, jpd, jpe)  │   │      (nexus_db)           │
             │ • Ashburn (usa, usb, usc)          │   │                           │
             │ • Singapore (sga)                  │   │ • vm_telemetry (timeseries)
             │ • Beijing (cna)                    │   │ • High-performance index │
             └────────────────────────────────────┘   └───────────────────────────┘
```

---

## 🚀 Key Features

* 🌐 **Global Multi-Cloud Topology Map**: Dynamic geographical visualization rendered with ECharts 5, mapping nodes across Tokyo, Ashburn, Singapore, and Beijing with real-time ping latency and health beacons.
* 📈 **Time-Series Telemetry Waveforms**: Live streaming CPU, memory utilization, disk space, and network I/O throughput stored in MySQL HeatWave.
* 🤖 **AI Autonomous Diagnostics**: Real-time anomaly detection heuristics, fleet health scoring (`0~100%`), and remediation recommendations.
* 🚇 **Zero-Trust Network Bridge**: Zero public database ports. Cloudflare Tunnel connects Cloudflare Workers directly to private internal subnet instances.
* 🛡️ **Enterprise Process Supervision**: `systemd` daemon supervision on Ingestion Hub with automatic crash recovery and on-boot restart.
* 🔐 **Supabase Authentication**: Integrated glassmorphic login modal with session persistence.
* 🔄 **Automated CI/CD**: GitHub Actions workflow running `pytest` test suites and instant Wrangler edge deployment on push.

---

## 📂 Monorepo Structure

```text
nexus/
├── .github/
│   └── workflows/
│       ├── ci.yml                 # Pytest & TypeScript verification
│       └── deploy.yml             # Cloudflare Workers automated deployment
├── data-bridge/                   # Backend Ingestion & API Gateway (Python)
│   ├── api.py                     # FastAPI REST server
│   ├── ingest.py                  # Concurrent multi-threaded Prometheus scraper
│   ├── db_setup.py                # MySQL schema initializer
│   ├── nexus-api.service          # systemd unit for API gateway
│   ├── nexus-ingest.service       # systemd unit for ingestion daemon
│   ├── requirements.txt           # Python dependencies
│   └── tests/                     # Automated pytest unit test suite
│       ├── test_parser.py         # Metrics parsing algorithm tests
│       └── test_api.py            # API endpoint integration tests
└── edge-app/                      # Edge Application (Cloudflare Workers)
    ├── src/
    │   └── index.ts               # Hono app & Glassmorphic Dashboard SPA
    ├── package.json               # Node.js dependencies
    └── wrangler.jsonc             # Cloudflare Worker configuration
```

---

## 🛠️ Quick Start

### 1. Prerequisites
* Python 3.12+
* Node.js 22+ & pnpm / npm
* Cloudflare account with Wrangler CLI configured
* MySQL 8.0+ / OCI HeatWave instance

### 2. Backend Setup
```bash
cd data-bridge
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run Unit Tests
pytest -v tests/

# Initialize database schema
python db_setup.py

# Start ingestion daemon and API
python ingest.py &
uvicorn api:app --host 127.0.0.1 --port 8000
```

### 3. Edge Worker Setup
```bash
cd edge-app
npm install

# Local development
npx wrangler dev

# Deploy to Cloudflare Workers
npx wrangler deploy --minify
```

---

## 📊 Database Schema (`vm_telemetry`)

```sql
CREATE TABLE IF NOT EXISTS vm_telemetry (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    node_name VARCHAR(32) NOT NULL,
    host_ip VARCHAR(64) NOT NULL,
    region VARCHAR(32) DEFAULT '',
    cpu_usage_percent FLOAT DEFAULT 0.0,
    mem_total_bytes BIGINT DEFAULT 0,
    mem_available_bytes BIGINT DEFAULT 0,
    mem_usage_percent FLOAT DEFAULT 0.0,
    disk_usage_percent FLOAT DEFAULT 0.0,
    net_in_bytes_sec BIGINT DEFAULT 0,
    net_out_bytes_sec BIGINT DEFAULT 0,
    scrape_duration_ms INT DEFAULT 0,
    status VARCHAR(16) DEFAULT 'ONLINE',
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_node_time (node_name, recorded_at),
    INDEX idx_recorded_at (recorded_at)
) ENGINE=InnoDB;
```

---

## 📄 License
This project is licensed under the [MIT License](LICENSE).
