# Intelli-Credit 🏦

**AI-Powered Credit Decisioning Engine for Indian NBFC Corporate Lending**

> Automates end-to-end Credit Appraisal Memo (CAM) preparation using multi-source data, transparent Five Cs scoring, and LLM-powered narration.

---

## Table of Contents

- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Prerequisites](#prerequisites)
- [Getting Started](#getting-started)
  - [Option A — Docker (Recommended)](#option-a--docker-recommended)
  - [Option B — Manual Setup](#option-b--manual-setup)
- [Environment Variables](#environment-variables)
- [API Endpoints](#api-endpoints)
- [Project Structure](#project-structure)
- [Making Changes](#making-changes)
- [Demo Data](#demo-data)
- [Troubleshooting](#troubleshooting)

---

## Architecture

```
Upload Docs → PDF/GST/Bank Ingestor → GSTR Reconciler
                                            ↓
                              Research Agent (MCA/News/e-Courts)
                                            ↓
                              Five Cs Scoring Engine (200-pt scorecard)
                                            ↓
                              LLM CAM Generator (Claude claude-sonnet-4-20250514)
                                            ↓
                              Word Document Download + Audit Trail
```

---

## Tech Stack

| Layer | Technologies |
|-------|-------------|
| **Backend** | Python 3.11, FastAPI, Uvicorn, SQLAlchemy (async), SQLite |
| **PDF / OCR** | PyMuPDF, Tesseract, pdfplumber, OpenCV |
| **Data** | pandas, NumPy, NetworkX |
| **ML** | scikit-learn, XGBoost |
| **LLM** | Anthropic Claude claude-sonnet-4-20250514 |
| **Doc Generation** | python-docx |
| **Frontend** | React 19, Vite 7, Tailwind CSS v4, Recharts, React Query |

---

## Prerequisites

### For Docker setup (Option A)

- [Docker Desktop](https://www.docker.com/products/docker-desktop) (includes Docker Compose)
- An **Anthropic API key** (for LLM-powered CAM generation)

### For manual setup (Option B)

- **Python 3.11+** — [python.org/downloads](https://www.python.org/downloads/)
- **Node.js 18+** and **npm** — [nodejs.org](https://nodejs.org/)
- **Tesseract OCR** — required for PDF OCR processing
  - **Windows:** download installer from [UB Mannheim](https://github.com/UB-Mannheim/tesseract/wiki) and add to PATH
  - **macOS:** `brew install tesseract`
  - **Linux:** `sudo apt install tesseract-ocr tesseract-ocr-eng`
- An **Anthropic API key**

---

## Getting Started

### 1. Clone the repository

```bash
git clone <repo-url> intelli-credit
cd intelli-credit
```

### 2. Configure environment variables

```bash
cp .env.example .env
```

Open `.env` and add your Anthropic API key:

```dotenv
ANTHROPIC_API_KEY=sk-ant-your-real-key-here
```

> **Note:** The `.env` file is git-ignored. Never commit real API keys.

---

### Option A — Docker (Recommended)

This is the fastest way to get the entire stack running.

```bash
# Build and start both backend + frontend
docker-compose up --build
```

That's it! Once the containers are healthy:

| Service | URL |
|---------|-----|
| **Frontend** | [http://localhost:5173](http://localhost:5173) |
| **API Docs (Swagger)** | [http://localhost:8000/api/docs](http://localhost:8000/api/docs) |
| **ReDoc** | [http://localhost:8000/api/redoc](http://localhost:8000/api/redoc) |

To stop the stack:

```bash
docker-compose down
```

To rebuild after dependency changes:

```bash
docker-compose up --build --force-recreate
```

---

### Option B — Manual Setup

#### Backend

```bash
# Navigate to the backend directory
cd backend

# Create and activate a virtual environment
python -m venv venv

# Windows (PowerShell)
.\venv\Scripts\Activate.ps1

# macOS / Linux
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start the dev server (auto-reload enabled)
uvicorn main:app --reload --port 8000
```

The API will be available at **http://localhost:8000**.  
Interactive docs at **http://localhost:8000/api/docs**.

#### Frontend

Open a **new terminal**:

```bash
# Navigate to the frontend directory
cd frontend

# Install dependencies
npm install

# Start the Vite dev server
npm run dev
```

The frontend will be available at **http://localhost:5173**.

> **Tip:** The frontend expects the backend running on port 8000. If you change the backend port, update `VITE_API_BASE_URL` in your environment or in `frontend/vite.config.js`.

---

## Environment Variables

All backend settings use the `INTELLI_` prefix and can be overridden via the `.env` file.

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | — | **(Required)** Your Anthropic Claude API key |
| `INTELLI_DEBUG` | `false` | Enable debug-level logging |
| `INTELLI_DATABASE_URL` | `sqlite+aiosqlite:///...` | Database connection string |
| `INTELLI_USE_CACHED_RESEARCH` | `true` | Use pre-cached research results (recommended for demo) |
| `INTELLI_RBI_REPO_RATE` | `6.50` | RBI repo rate for interest calculations |
| `INTELLI_LLM_MODEL` | `claude-sonnet-4-20250514` | Anthropic model to use |
| `INTELLI_LLM_TEMPERATURE` | `0.3` | LLM temperature (low = consistent banking tone) |

See [`.env.example`](.env.example) for the full list.

---

## API Endpoints

All API routes are prefixed with `/api/v1`. Full interactive docs are at `/api/docs`.

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/health` | Health check / liveness probe |
| `GET` | `/api/v1/config/public` | Public configuration values |
| `POST` | `/api/v1/cases` | Create a new credit case |
| `POST` | `/api/v1/cases/{id}/upload` | Upload documents (PDF, CSV, XLSX) |
| `POST` | `/api/v1/cases/{id}/ingest` | Process uploaded documents |
| `POST` | `/api/v1/cases/{id}/score` | Run Five Cs scoring engine |
| `GET` | `/api/v1/cases/{id}/score` | Retrieve scoring results |
| `POST` | `/api/v1/cases/{id}/research` | Run research agent |
| `POST` | `/api/v1/cases/{id}/cam` | Generate CAM document |

---

## Project Structure

```
intelli-credit/
├── .env.example            # Template for environment variables
├── docker-compose.yml      # One-command full-stack setup
├── backend/
│   ├── Dockerfile          # Python 3.11 + Tesseract + system deps
│   ├── main.py             # FastAPI app entry point
│   ├── config.py           # All settings, weights, thresholds
│   ├── database.py         # SQLAlchemy async models + init
│   ├── requirements.txt    # Python dependencies
│   ├── api/                # API route handlers
│   │   ├── ingest_routes.py    # Document upload & parsing
│   │   ├── score_routes.py     # Five Cs scoring engine
│   │   ├── cam_routes.py       # CAM generation
│   │   └── research_routes.py  # Research agent
│   ├── ingestor/           # PDF, GST, bank statement parsers
│   ├── scoring/            # Scoring logic & feature engineering
│   ├── research/           # MCA/News/e-Courts scraping
│   ├── cam/                # CAM document generator (python-docx)
│   ├── audit/              # Audit trail & hash verification
│   ├── data/               # Demo datasets, benchmarks, lexicons
│   └── outputs/            # Generated CAM documents
├── frontend/
│   ├── package.json        # React 19 + Vite + Tailwind
│   ├── vite.config.js      # Vite dev server config
│   ├── index.html          # HTML entry point
│   └── src/
│       ├── main.jsx        # React entry point
│       ├── App.jsx         # Root component
│       ├── App.css         # Component styles
│       └── index.css       # Global styles (Tailwind)
├── ml/
│   └── models/             # Serialised ML models (joblib)
└── tests/                  # Test suite (empty — contributions welcome!)
```

---

## Making Changes

### Backend development

1. Make sure the backend venv is activated (`.\venv\Scripts\Activate.ps1` or `source venv/bin/activate`)
2. Edit files under `backend/` — Uvicorn auto-reloads on save
3. All configuration lives in `backend/config.py` — thresholds, weights, and feature flags
4. Database models are in `backend/database.py`
5. To add a new API route:
   - Create a new file in `backend/api/` (e.g. `my_routes.py`)
   - Define a FastAPI `APIRouter`
   - Register it in `backend/main.py` via `app.include_router(...)`

### Frontend development

1. Edit files under `frontend/src/` — Vite HMR updates the browser instantly
2. Styling uses **Tailwind CSS v4** — edit classes directly in JSX
3. API calls use **Axios** + **React Query** for server-state management
4. Charts are built with **Recharts**

### Docker development

When using Docker Compose, source code is volume-mounted for live reload:
- `./backend` → `/app` (backend container)
- `./frontend/src` → `/app/src` (frontend container)

Changes to **source files** reflect immediately. For **dependency changes** (new pip/npm packages), rebuild:

```bash
docker-compose up --build
```

### Adding Python dependencies

```bash
cd backend
pip install <package-name>
pip freeze > requirements.txt   # or manually add to requirements.txt
```

### Adding npm dependencies

```bash
cd frontend
npm install <package-name>
```

---

## Demo Data

The project ships with a pre-loaded synthetic dataset:

| Field | Value |
|-------|-------|
| **Company** | Acme Textiles Ltd |
| **CIN** | U17100MH2010PLC201234 |
| **Expected Score** | ~42/100 (Grade C) |
| **Recommendation** | Partial approval ₹12.5 Cr @ 13.5% |

Demo data is located in `backend/data/demo_company/`.

---

## Troubleshooting

### Docker issues

| Problem | Solution |
|---------|----------|
| Port 8000 or 5173 already in use | Stop the conflicting process or change ports in `docker-compose.yml` |
| Backend container unhealthy | Check logs with `docker-compose logs backend` |
| Changes not reflecting | Rebuild with `docker-compose up --build --force-recreate` |

### Backend issues

| Problem | Solution |
|---------|----------|
| `ModuleNotFoundError` | Ensure venv is activated and `pip install -r requirements.txt` was run |
| Tesseract not found | Install Tesseract OCR and ensure it's on your PATH |
| Database errors | Delete `backend/intelli_credit.db` — it will be recreated on next startup |
| LLM errors / rate limits | Check your `ANTHROPIC_API_KEY` is valid and has sufficient credits |

### Frontend issues

| Problem | Solution |
|---------|----------|
| `npm install` fails | Ensure Node.js 18+ is installed (`node --version`) |
| API calls failing | Verify the backend is running on port 8000 |
| CORS errors | Backend allows `localhost:5173` and `localhost:3000` by default |

---

## License

This project was built for a hackathon. See the repository for license details.