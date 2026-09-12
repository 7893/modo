# 🌐 MODO (墨斗) // 多云分布式数据底座与智能中枢

[![CI](https://github.com/7893/modo/actions/workflows/ci.yml/badge.svg)](https://github.com/7893/modo/actions/workflows/ci.yml)
[![Deploy to Cloudflare Workers](https://github.com/7893/modo/actions/workflows/deploy.yml/badge.svg)](https://github.com/7893/modo/actions/workflows/deploy.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-purple.svg?style=flat-square)](LICENSE)

> **MODO（墨斗）—— 专为多云分布式业务打造的高可用数据底座与全景遥测中枢。**  
> Powered by **Cloudflare Workers (Hono)**, **MySQL HeatWave Engine (`modo_db`)**, **Network Load Balancer (NLB)**, and **FastAPI**.

---

## ⚡ Production Endpoints

| Service | Access | Architecture Role | Status |
| :--- | :--- | :--- | :---: |
| 🌐 **MODO Command Dashboard** | `Cloudflare Edge (Public)` | Edge Worker UI + ECharts 5 + Supabase Auth | 🟢 **ONLINE** |
| 🚇 **MODO Private API Gateway** | `Encrypted Tunnel (Internal Only)` | Zero-Trust Cloudflare Tunnel ➡️ FastAPI Bridge | 🟢 **ACTIVE** |
| 🗄️ **Managed MySQL Data Store** | `Private VPC Ingress` | OCI MySQL HeatWave Cloud Database System | 🟢 **ACTIVE** |

---

## 🗺️ System Architecture

```text
                               【Operations & Management】
                                             │  (HTTPS / TLS 1.3)
                                             ▼
                        ┌─────────────────────────────────────────┐
                        │      Cloudflare Edge Network (CDN)      │
                        │          Public Edge Endpoint           │
                        │                                         │
                        │  • Hono.js Edge Application             │
                        │  • ECharts 5 Supabase Dark Theme       │
                        │  • 4-Curtain Multi-Screen Dashboard     │
                        │  • Supabase Auth Security Guard         │
                        └────────────────────┬────────────────────┘
                                             │  (Encrypted Edge Proxy)
                                             ▼
                        ┌─────────────────────────────────────────┐
                        │     Cloudflare Tunnel (QUIC Protocol)   │
                        │       (Zero-Trust Private Ingress)      │
                        └────────────────────┬────────────────────┘
                                             │  (Zero-Trust Private Ingress)
                                             ▼
                        ┌─────────────────────────────────────────┐
                        │       usa (US Ashburn Central Hub)      │
                        │                                         │
                        │  • systemd: modo.service (Unified API   │
                        │    8000 + Ingest daemon 15s)            │
                        │  • HeatWave AutoML: MODO_LATENCY_       │
                        │    FORECAST (ExtraTreesRegressor)       │
                        └──────────────┬──────────────────┬───────┘
                                       │                  │
                (Prometheus Scrape)    │                  │ (Private VPC TCP 3306)
                                       ▼                  ▼
             ┌────────────────────────────────────┐   ┌───────────────────────────┐
             │      11 Multi-Cloud VM Fleet       │   │    Cloud MySQL HeatWave   │
             │                                    │   │     Enterprise System     │
             │ • Ashburn (usa, usb, usc)          │   │        (modo_db)          │
             │ • Osaka/Tokyo (jpa, jpb, jpc,      │   │                           │
             │   jpd, jpe)                        │   │ • vm_telemetry (timeseries│
             │ • Singapore (sga), Taiwan (gcp)    │   │ • latency_forecast_train  │
             │ • Beijing (cna)                    │   │ • ML_SCHEMA_admin Catalog │
             └────────────────────────────────────┘   └───────────────────────────┘
```

---

## 🚀 Key Features

* 🌐 **Multi-Cloud Topology Map & Radar (Curtain 2)**: Dynamic geographical visualization rendered with ECharts 5, mapping nodes across Ashburn, Osaka, Tokyo, Singapore, Taiwan, and Beijing. All telemetry lines converge towards the **USA Ashburn Central Hub**, with particle flow speeds dynamically driven by HeatWave AutoML latency forecasting.
* 🧠 **HeatWave AutoML In-Database Intelligence**: Native in-database regression modeling (`sys.ML_TRAIN` on `latency_forecast_train`) using `ExtraTreesRegressor` (`MODO_LATENCY_FORECAST`, model_id 5) loaded in HeatWave memory. Inference via `sys.ML_PREDICT_ROW` blended with real-time EMA (60% ML + 40% EMA) calculates precise per-link latency and particle animation periods.
* 📈 **Time-Series Telemetry Waveforms**: Live streaming CPU, memory utilization, disk space, and network I/O throughput stored in MySQL HeatWave.
* 🤖 **AI Autonomous Diagnostics**: Real-time anomaly detection heuristics, fleet health scoring (`0~100%`), and remediation recommendations.
* 🚇 **Zero-Trust Network Bridge**: Zero public database ports. Cloudflare Tunnel connects Cloudflare Workers directly to private internal subnet instances.
* 🛡️ **Enterprise Process Supervision**: Unified `systemd` daemon supervision (`modo.service`) on USA Central Hub with automatic crash recovery and on-boot restart.
* 🔐 **Supabase Authentication**: Integrated glassmorphic login modal with session persistence.
* 🔄 **Automated CI/CD**: GitHub Actions workflow running `pytest` test suites, instant Wrangler edge deployment on push, and automated code rsync to USA node.

---

## 📂 Monorepo Structure

```text
modo/
├── .github/
│   └── workflows/
│       ├── ci.yml                 # Pytest & TypeScript verification
│       └── deploy.yml             # Cloudflare Workers automated deployment & USA rsync
├── data-bridge/                   # Backend Ingestion & API Gateway (Python)
│   ├── api.py                     # FastAPI REST server & AutoML latency forecast
│   ├── ingest.py                  # Concurrent multi-threaded Prometheus scraper
│   ├── db_setup.py                # MySQL schema initializer
│   ├── run_unified.py             # Single systemd service supervisor
│   ├── train_latency_model.py     # HeatWave AutoML model training script
│   ├── requirements.txt           # Python dependencies
│   └── tests/                     # Automated pytest unit test suite
│       ├── test_parser.py         # Metrics parsing algorithm tests
│       └── test_api.py            # API endpoint integration tests
├── deploy/                        # Deployment configuration
│   └── modo.service               # Unified systemd unit for API + Ingest
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
* Node.js 22+ & pnpm
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
python src/db_setup.py

# Start the unified daemon (API gateway + telemetry ingestion)
python src/run_unified.py
```

### 3. Edge Worker Setup
```bash
cd edge-app
pnpm install

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
