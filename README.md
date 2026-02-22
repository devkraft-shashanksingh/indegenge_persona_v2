# PharmaPersonaSim Backend 🏥

AI-powered pharmaceutical persona simulation platform that transforms patient insights into actionable market intelligence. This repository contains the backend service and API.

## What It Does

PharmaPersonaSim uses Large Language Models to create dynamic AI personas (patients and HCPs) that simulate realistic responses to marketing campaigns, treatment options, and clinical scenarios—delivering insights in minutes instead of months.

**Key Benefits:**
- ⚡ **90% faster** than traditional market research
- 💰 **70% cost savings** on patient insights
- 📈 **Unlimited scalability** for testing scenarios
- 🎯 **Quantitative metrics** from qualitative data

## Features

### Persona Generation
- Generate detailed HCP and patient personas using GPT-4
- Rich profiles with demographics, medical background, motivations, and preferences
- MBT Framework (Motivation, Belief, Tension) for behavioral realism

### Brand Library
- Upload documents across 7 knowledge pillars
- AI-powered document classification
- Context-aware insights extraction

### Cohort Simulation
- Test responses to marketing messages with multiple personas
- Configure metrics: sentiment, purchase intent, trust, clarity
- Real-time LLM-powered analysis with reasoning

### Synthetic Testing
- Objective scoring of marketing assets against key metrics (1-7 scale)
- Qualitative feedback generation (What works, Challenges, Considerations)
- Aggregated insights across multiple personas

## Quick Start (Docker - Recommended)

### Prerequisites
- Docker and Docker Compose
- OpenAI API key and Azure OpenAI configuration (if applicable)

### Setup

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd indegenge_persona_v2
   ```

2. **Configure Environment:**
   Create a `.env` file in the `backend/` directory by copying the example:
   ```bash
   cp backend/.env.example backend/.env
   # Edit backend/.env and add your required API keys
   ```

3. **Start the containers:**
   From the repository root (where `docker-compose.yml` is located):
   ```bash
   docker-compose up --build
   ```

This will run:
- A PostgreSQL database on port `5435`
- The FastAPI backend on port `8000`

**Access:**
- Backend API Base (Health check): `http://localhost:8000/persona-apis/`
- API Docs (Swagger UI): `http://localhost:8000/persona-apis/docs`
- ReDoc: `http://localhost:8000/persona-apis/redoc`

## Local Development (Without Docker)

### Prerequisites
- Python 3.11+
- PostgreSQL database

### Setup

```bash
# Backend setup
cd backend
python -m venv venv
source venv/bin/activate  # Mac/Linux | venv\Scripts\activate (Windows)
pip install -r requirements.txt

# Run migrations (ensure your local DB is running and configured via DATABASE_URL)
alembic upgrade head

# Run server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## Project Structure

```text
indegenge_persona_v2/
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI entry point & core routing
│   │   ├── models.py         # SQLAlchemy database models
│   │   ├── routers/          # API route definitions
│   │   ├── core/             # Configuration and utilities
│   │   └── ...               # Various engine components
│   ├── alembic/              # Database migration scripts
│   ├── Dockerfile            # Container definition
│   └── requirements.txt      # Python dependencies
└── docker-compose.yml        # Multi-container orchestration
```

## Tech Stack

**Backend:** FastAPI, SQLAlchemy, Alembic  
**Database:** PostgreSQL  
**AI Services:** OpenAI API, Azure OpenAI  
**Containerization:** Docker, Docker Compose

## API Endpoints

All endpoints are prefixed with `/persona-apis`. For comprehensive details, check the interactive Swagger UI at `/persona-apis/docs`.

| Endpoint Prefix | Description |
|-----------------|-------------|
| `/personas/` | Persona generation and management |
| `/cohorts/` | Cohort simulation and analysis |
| `/brands/` | Brand document management and indexing |
| `/synthetic/` | Synthetic testing logic |
| `/simulations/` | Simulation management |
| `/panel-feedback/` | Panel feedback analysis |
| `/analysis/` | Analytics and deep search |

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | Yes | OpenAI API key |
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `DB_SCHEMA` | No | Schema name (default: persona) |

*See `backend/.env.example` for a full list of required variables, supporting logic for Azure OpenAI, logging, and other settings.*

## Important Notes

⚠️ **Research Tool** - Validate results with actual patient/HCP research before critical decisions  
⚠️ **Compliance** - Content must pass MLR review; this tool doesn't replace regulatory compliance  
⚠️ **Data Privacy** - Don't input actual PHI; use synthetic/anonymized data only  
⚠️ **API Costs** - Monitor OpenAI usage costs at platform.openai.com/usage or your Azure portal.

## License

MIT License

## Author

**Ishank GP** - [@ishankgp](https://github.com/ishankgp)  
Built for Indegene's pharmaceutical intelligence platform

---

**Transforming patient insights through AI** 🚀
