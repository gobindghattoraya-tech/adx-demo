# Market Health Dashboard

> **ADX Platform · GCPAP999-324**
> A 3-tier proof-of-concept web application built with FastAPI, Cloud Run, and Cloud SQL PostgreSQL.

---

## 🌐 URLs

| Endpoint | URL |
|----------|-----|
| **Frontend URL** | `https://market-health-dashboard-<hash>-nw.a.run.app/` |
| **Backend URL** | `https://market-health-dashboard-<hash>-nw.a.run.app/hello` |
| **Health Check** | `https://market-health-dashboard-<hash>-nw.a.run.app/health` |
| **Swagger Docs** | `https://market-health-dashboard-<hash>-nw.a.run.app/docs` |

> URLs are populated after first Cloud Run deployment. Check the Cloud Build logs or run:
> ```bash
> gcloud run services describe market-health-dashboard \
>   --region=europe-west2 --project=sbx-ag-build-adx-7i0q-1 \
>   --format="value(status.url)"
> ```

---

## 🏗 Architecture

```
Browser → Cloud Run (market-health-dashboard, europe-west2)
            ├── GET /          → Jinja2 HTML page (ADX branded)
            ├── GET /health    → {"status": "ok"}
            ├── GET /hello     → {"message": "Hello World"} ← from PostgreSQL
            └── GET /docs      → Swagger UI (auto-generated)
                  │ Direct VPC Egress → adx-vpc (private-ranges-only)
                  ▼
              Cloud SQL ag-adx-postgres → adx_exchange.messages
```

---

## 🛠 Tech Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.13 |
| Framework | FastAPI 0.115.5 (ASGI) |
| Server | uvicorn 0.32.1 |
| Database ORM | SQLAlchemy 2.0 (async) |
| DB Driver | asyncpg 0.30.0 |
| Templating | Jinja2 3.1.4 |
| Container | python:3.13-slim |
| Platform | Google Cloud Run (europe-west2) |
| Database | Cloud SQL PostgreSQL 17 (Private IP) |
| Secrets | GCP Secret Manager |

---

## 🏃 Local Development

### Prerequisites
- Python 3.13
- `psql` or access to Cloud SQL
- Cloud SQL Auth Proxy (for local DB connection)

### Setup

```bash
# Create virtual environment
python3.13 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -r tests/requirements-test.txt

# Set environment variables
export DB_USER=postgres
export DB_PASSWORD=<your-password>
export DB_HOST=127.0.0.1        # Auth Proxy local address
export DB_NAME=adx_exchange
```

### Start Cloud SQL Auth Proxy (separate terminal)

```bash
./cloud-sql-proxy sbx-ag-build-adx-7i0q-1:europe-west2:ag-adx-postgres \
  --private-ip --address 127.0.0.1 --port 5432
```

### Run locally

```bash
uvicorn app.main:app --reload --port 8080
# Open: http://localhost:8080
# Swagger: http://localhost:8080/docs
```

---

## 🧪 Running Tests

```bash
# Unit tests (mock DB — no real Cloud SQL needed)
pytest tests/ -v --tb=short

# All test output
pytest tests/ -v
```

---

## ☁️ Deployment (Cloud Build)

```bash
gcloud builds submit . \
  --config=cloudbuild.yaml \
  --project=sbx-ag-build-adx-7i0q-1 \
  --region=europe-west2
```

---

## 🔐 Environment Variables

| Variable | Source | Description |
|----------|--------|-------------|
| `DB_HOST` | Cloud Run env var | Cloud SQL private IP (`10.104.0.6`) |
| `DB_NAME` | Cloud Run env var | Database name (`adx_exchange`) |
| `DB_USER` | Cloud Run env var | DB user (`postgres`) |
| `DB_PASSWORD` | Secret Manager | `adx-postgres-password:latest` |

---

## 📁 Project Structure

```
market-health-dashboard/
├── app/
│   ├── main.py            # FastAPI app factory + lifespan
│   ├── db.py              # Async SQLAlchemy engine
│   ├── routes.py          # /, /health, /hello
│   ├── schemas.py         # Pydantic response models
│   ├── templates/
│   │   └── index.html     # ADX branded frontend
│   └── static/
│       └── style.css      # ADX design system
├── migrations/
│   └── seed_hello_world.sql
├── tests/
│   ├── conftest.py
│   ├── features/
│   │   └── dashboard.feature
│   └── step_defs/
│       └── test_dashboard_steps.py
├── Dockerfile
├── cloudbuild.yaml
├── requirements.txt
└── README.md
```
