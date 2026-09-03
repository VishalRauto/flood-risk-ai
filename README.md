# 🌊 India Flood Intelligence System

An AI-powered flood intelligence and disaster response system built for **India**, monitoring all major river basins in real-time using Open-Meteo Flood API (GloFAS), NVIDIA NIM AI models, and multi-agent coordination.

![India Flood Intelligence](https://img.shields.io/badge/India-Flood%20Intelligence-blue)
![Python](https://img.shields.io/badge/Python-3.11-green)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green)
![React](https://img.shields.io/badge/React-19-blue)
![Docker](https://img.shields.io/badge/Docker-Ready-blue)
![License](https://img.shields.io/badge/License-Apache%202.0-yellow)

---

## What This System Does

A real-time flood intelligence platform covering **8 major India river basins** with **45+ river monitoring sites**:

- **Live river discharge monitoring** from Open-Meteo Flood API (GloFAS — free, no key needed)
- **AI-powered flood risk assessment** using `nvidia/llama-3.1-nemotron-ultra-253b-v1`
- **IMD rainfall alert integration** — Heavy (≥64.5mm), Very Heavy (≥115.5mm/day) thresholds
- **Multi-agent AI system** with 4 specialised India flood agents
- **Interactive dashboard** with India map, real-time alerts, and chatbot
- **NDMA/NDRF emergency guidance** for flood response coordination

---

## India River Basins Covered

| Basin | Key Sites | States |
|---|---|---|
| 🔵 Ganga | Haridwar, Prayagraj, Varanasi, Patna, Yamuna Delhi | UK, UP, Bihar, WB |
| 🔵 Brahmaputra | Guwahati, Dibrugarh, Manas, Barak | Assam, AR |
| 🔵 Mahanadi | Hirakud Dam, Cuttack, Tel | Odisha, CG |
| 🔵 Godavari | Nashik, Rajahmundry, Pranhita | MH, TG, AP |
| 🔵 Krishna | Vijayawada, Tungabhadra, Bhima | KA, MH, AP |
| 🔵 Narmada | Jabalpur, Sardar Sarovar, Tawa | MP, GJ |
| 🔵 Kaveri | KRS Dam, Tiruchirappalli, Hemavathi | KA, TN |
| 🔵 Indus (India) | Sutlej, Beas, Ravi, Chenab, Jhelum | PB, HP, J&K |

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                  React Frontend (Vite)               │
│  India Map · Risk Dashboard · AI Chatbot · Alerts   │
└──────────────────────┬──────────────────────────────┘
                       │ REST + SSE
┌──────────────────────▼──────────────────────────────┐
│              FastAPI Backend (Python 3.11)           │
│                                                      │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────┐  │
│  │Data Collector│  │Risk Analyzer │  │ Predictor │  │
│  │Open-Meteo   │  │0-10 Score    │  │24-72h     │  │
│  │IMD Rainfall │  │CWC Thresholds│  │Forecast   │  │
│  └─────────────┘  └──────────────┘  └───────────┘  │
│  ┌─────────────────────────────────────────────────┐ │
│  │       Emergency Responder (NDMA/NDRF)           │ │
│  │  SACHET · IMD · Doordarshan · AIR · State DMA  │ │
│  └─────────────────────────────────────────────────┘ │
│                                                      │
│  NVIDIA NIM: llama-3.1-nemotron-ultra-253b-v1       │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│                  Redis (Task Queue)                  │
└─────────────────────────────────────────────────────┘
```

---

## AI Models Used

| Component | Model | Purpose |
|---|---|---|
| AI Chat & Agents | `nvidia/llama-3.1-nemotron-ultra-253b-v1` | Flood Q&A, risk analysis, emergency guidance |
| Risk Analyzer Agent | `nvidia/llama-3.1-nemotron-ultra-253b-v1` | Multi-factor India flood risk scoring |
| Predictor Agent | `nvidia/llama-3.1-nemotron-ultra-253b-v1` | 24–72h river discharge forecasting |
| Data Collector Agent | `nvidia/llama-3.1-nemotron-ultra-253b-v1` | India data collection orchestration |
| Flood Data | Open-Meteo GloFAS API | River discharge (free, no key needed) |

---

## Risk Scoring

```
flow_ratio  = current_discharge (m³/s) / CWC_flood_stage
risk_score  = min(10, flow_ratio × 8)

LOW      < 4.0   — Normal conditions
MODERATE 4.0–6.0 — Monitor closely
HIGH     6.0–8.0 — Prepare response
CRITICAL > 8.0   — Immediate action
```

IMD Rainfall thresholds applied:
- Light Rain: < 2.5 mm/day
- Moderate: 2.5 – 64.5 mm/day
- **Heavy Rain (Yellow): ≥ 64.5 mm/day**
- **Very Heavy Rain (Orange): ≥ 115.5 mm/day**
- **Extremely Heavy Rain (Red): ≥ 204.5 mm/day**

---

## Quick Start

### Prerequisites

- Docker Desktop installed and running
- NVIDIA API key from [build.nvidia.com](https://build.nvidia.com) (free)

### 1. Clone the repository

```bash
git clone https://github.com/VishalRauto/flood-risk-ai.git
cd flood-risk-ai
```

### 2. Set up environment

```bash
cp core/.env.example core/.env
```

Edit `core/.env` and add your NVIDIA API key:

```env
APP_NVIDIA_API_KEY=nvapi-your-key-here
APP_AI_PROVIDER=nvidia
APP_ENABLE_AUTH=false
```

### 3. Run with Docker

```bash
docker compose -f docker-compose.local.yml up --build
```

First run takes 3–5 minutes (downloads images, installs dependencies).

### 4. Open the dashboard

```
http://localhost:8000
```

---

## Project Structure

```
flood-risk-ai/
├── core/                          # Python backend
│   ├── src/flood_prediction/
│   │   ├── server.py              # FastAPI routes
│   │   ├── data_sources.py        # Open-Meteo + India river sites
│   │   ├── db.py                  # SQLite database
│   │   ├── settings.py            # App configuration
│   │   └── agents/
│   │       ├── data_collector.py  # Open-Meteo data collection
│   │       ├── risk_analyzer.py   # CWC-based risk scoring
│   │       ├── predictor.py       # 24-72h flood forecasting
│   │       ├── emergency_responder.py  # NDMA/NDRF coordination
│   │       ├── nat_base.py        # NVIDIA NAT agent orchestration
│   │       └── nat/               # NAT agent config YMLs
│   ├── requirements.txt           # Python dependencies
│   └── .env.example               # Environment template
├── ui/                            # React frontend (Vite + TypeScript)
│   └── src/
│       ├── components/
│       │   ├── UnifiedDashboard.tsx   # Main dashboard
│       │   ├── GlobalWatershedMap.tsx # India map (Leaflet)
│       │   └── DataSourceBadge.tsx    # CWC/IMD/Open-Meteo badges
│       ├── dashboard/page.tsx         # Dashboard page
│       └── lib/api.ts                 # API client
├── docker-compose.local.yml       # Local Docker setup
├── Dockerfile                     # Multi-stage build
├── test.py                        # India river data fetcher demo
└── india_watershed_config.json    # All India basin configurations
```

---

## API Keys

| Key | Required | Where to Get | Cost |
|---|---|---|---|
| `APP_NVIDIA_API_KEY` | ✅ Yes | [build.nvidia.com](https://build.nvidia.com) | Free tier available |
| `APP_H2OGPTE_API_KEY` | ❌ No | [h2o.ai](https://h2o.ai) | Optional AutoML |
| Open-Meteo Flood API | ✅ Free | No key needed | Free forever |
| IMD / CWC | ✅ Free | No key needed (via Open-Meteo) | Free forever |

---

## AI Agents

### 1. Data Collector
Fetches real-time river discharge from **Open-Meteo Flood API** (GloFAS) for 45+ India river monitoring sites. Also collects IMD rainfall warnings and Open-Meteo weather forecasts for flood-prone cities.

### 2. Risk Analyzer
Calculates flood risk scores (0–10) using CWC danger level thresholds. Tracks risk trends, detects rapid escalations, and monitors critical watershed count across all 8 India basins.

### 3. AI Predictor
Generates 24–72 hour flood forecasts using trend decay models and GloFAS ensemble data. Tracks model accuracy, detects prediction conflicts, and estimates critical period windows.

### 4. Emergency Responder
Coordinates with India's emergency systems — NDMA (helpline 1078), NDRF battalion tracking, SACHET alert platform, IMD district warnings, Doordarshan/AIR broadcasts, and State DMA systems.

---

## Data Sources

| Source | Data | Cost |
|---|---|---|
| [Open-Meteo Flood API](https://open-meteo.com/en/docs/flood-api) | River discharge (GloFAS), 7-day forecast | Free |
| [Open-Meteo Weather API](https://api.open-meteo.com) | Rainfall, temperature, humidity | Free |
| [NVIDIA NIM](https://build.nvidia.com) | AI inference — llama-3.1-nemotron-ultra-253b-v1 | Free tier |

---

## Management Commands

```bash
# Start
docker compose -f docker-compose.local.yml up

# Stop
docker compose -f docker-compose.local.yml down

# View logs
docker logs flood-web

# Check status
docker ps

# Health check
curl http://localhost:8000/health
```

---

## Emergency Contacts (India)

| Agency | Contact |
|---|---|
| NDMA National Helpline | **1078** |
| NDRF | **011-24363260** |
| IMD Weather | [mausam.imd.gov.in](https://mausam.imd.gov.in) |
| CWC Flood Forecast | [cwc.gov.in](https://cwc.gov.in/flood-forecast) |
| India WRIS | [indiawris.gov.in](https://indiawris.gov.in) |
| NDMA SACHET Alerts | [sachet.ndma.gov.in](https://sachet.ndma.gov.in) |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11, FastAPI, SQLite, RQ |
| Frontend | React 19, TypeScript, Vite, Tailwind CSS, Leaflet |
| AI | NVIDIA NIM (llama-3.1-nemotron-ultra-253b-v1), NVIDIA NAT |
| Data | Open-Meteo Flood API (GloFAS), Open-Meteo Weather API |
| Infrastructure | Docker, Redis |

---

## License

Apache 2.0 — see [LICENSE](LICENSE)

---

*Built for India flood disaster management using Open-Meteo GloFAS data and NVIDIA AI* 🇮🇳
