# PharmaPersonaSim 🏥

AI-powered pharmaceutical persona simulation platform that transforms patient insights into actionable market intelligence.

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

### Analytics Dashboard
- Individual persona response breakdown
- Summary statistics and AI-generated insights
- Interactive data visualization and export

## Quick Start

### Prerequisites
- Python 3.10+
- Node.js 18+
- OpenAI API key

### Setup

```bash
# Clone and navigate
git clone https://github.com/ishankgp/indegenge_persona.git
cd indegenge_persona/pharmapersonasim

# Backend setup
cd backend
python -m venv venv
venv\Scripts\activate  # Windows | source venv/bin/activate (Mac/Linux)
pip install -r requirements.txt
cd ..

# Frontend setup
cd frontend
npm install
cd ..

# Configure environment
echo "OPENAI_API_KEY=your_key_here" > .env

# Run
python run_app.py
```

**Access:**
- Frontend: http://localhost:5173
- Backend API: http://127.0.0.1:8000
- API Docs: http://127.0.0.1:8000/docs

## Project Structure

```
pharmapersonasim/
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI endpoints
│   │   ├── models.py         # Database models
│   │   ├── persona_engine.py # AI persona generation
│   │   ├── cohort_engine.py  # Cohort analysis
│   │   └── synthetic_testing_engine.py # Synthetic testing logic
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── pages/            # Application pages
│   │   ├── components/       # UI components
│   │   └── lib/api.ts        # API client
│   └── package.json
└── run_app.py                # App launcher
```

## Tech Stack

**Backend:** FastAPI, SQLAlchemy, OpenAI API, Google GenAI  
**Frontend:** React, TypeScript, Vite, Tailwind CSS, shadcn/ui  
**Database:** SQLite (dev) / PostgreSQL (prod)

## Deployment

**Frontend (Vercel):** Deployed at production URL  
**Backend (Railway):** See [DEPLOYMENT.md](DEPLOYMENT.md) for instructions

Set `VITE_API_URL` in Vercel to your backend URL after deployment.

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/personas/` | GET | List all personas |
| `/personas/` | POST | Create persona |
| `/cohorts/analyze` | POST | Run cohort simulation |
| `/api/brands` | GET/POST | Brand management |
| `/health` | GET | Health check |

## Documentation

- [DEPLOYMENT.md](DEPLOYMENT.md) - Deployment guide
- [DEV_GUIDE.md](DEV_GUIDE.md) - Developer setup
- [DATA_NEEDED_FROM_EXPERTS.md](DATA_NEEDED_FROM_EXPERTS.md) - Expert data requirements

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | Yes | OpenAI API key |
| `VITE_API_URL` | Prod | Backend URL for production |
| `DATABASE_URL` | Prod | PostgreSQL connection string |

## Important Notes

⚠️ **Research Tool** - Validate results with actual patient/HCP research before critical decisions  
⚠️ **Compliance** - Content must pass MLR review; this tool doesn't replace regulatory compliance  
⚠️ **Data Privacy** - Don't input actual PHI; use synthetic/anonymized data only  
⚠️ **API Costs** - Monitor OpenAI usage at platform.openai.com/usage

## License

MIT License

## Author

**Ishank GP** - [@ishankgp](https://github.com/ishankgp)  
Built for Indegene's pharmaceutical intelligence platform

---

**Transforming patient insights through AI** 🚀
