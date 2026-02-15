# Developer Guide: API Access & Environment (Codespaces)

## Overview
This document explains how the frontend talks to the backend in a GitHub Codespaces (or any container) environment, and the mechanisms added to make it reliable and observable.

## Key Components Added
1. Vite Dev Proxy (in `frontend/vite.config.ts`)
2. Central API Client (`frontend/src/lib/api.ts`)
3. Health / Status Badge (`frontend/src/components/Layout.tsx`)
4. Retry & Backoff (GET requests, exponential)
5. Startup Config Printer (`scripts/print_config.py` invoked by `run_app.py`)
6. Database & Health Endpoints (`/health/db`, `HEAD /personas/`)

## Why Was Data Invisible Before?
- Backend bound only to `127.0.0.1` inside container → external browser couldn’t reach it.
- Frontend used a root `.env` (ignored by Vite) with wrong port `8001`.
- Multiple duplicated axios calls increased chance of drift.
- Ambiguous DB locations created confusion.

## Vite Dev Proxy
Configured paths: `/personas`, `/cohorts`, `/stats`, `/health`, `/api`
All proxy to `http://127.0.0.1:8000` during `npm run dev`.

Effect: Frontend code can just call relative paths (`/personas/`) with no hardcoded backend base. Reduces env friction and avoids mixed-origin issues in Codespaces.

## API Client Logic (`src/lib/api.ts`)
- Dev Mode: `baseURL=''` (relative) so proxy handles routing.
- Prod Mode: uses `VITE_API_URL` if defined, else `window.location.origin` fallback.
- Retry: Up to 3 automatic retries for GET requests (200ms, 400ms, 800ms delays).
- Health Helper: `checkHealth()` calls `/health/db` to populate badge.

## Status Badge
In `Layout.tsx` footer:
- Shows: Checking API… → API Online / API Down
- Displays base URL (or `relative`) and persona count when available.
- Refreshes every 15s.

## Diagnostic Endpoints
- `GET /health`: Basic service health
- `GET /health/db`: DB status + persona count
- `HEAD /personas/`: Lightweight probe exposing `X-Total-Personas`

## Startup Config Printer
Executed at launch by `run_app.py`:
- Prints effective `BACKEND_HOST`, `BACKEND_PORT`, `DATABASE_URL`, model, key presence
- Assists in confirming env correctness early

## Recommended Workflow
1. Activate venv & run `python run_app.py` (starts backend & frontend).
2. Frontend dev server prints forwarded URL in Codespaces; open it.
3. Personas page loads using relative fetch via proxy.
4. Observe status badge for confirmation.

## Adding New API Routes
1. Implement route in FastAPI.
2. Add relative call in a wrapper inside `lib/api.ts`.
3. (Optional) If new top-level path, add to proxy array in `vite.config.ts`.
4. Consume in pages/components.

## Production Deployment
- Set `VITE_API_URL` to the deployed backend URL (e.g. Railway) for your production build.
- The proxy is dev-only; production will call the absolute base.

## Troubleshooting Matrix
| Symptom | Likely Cause | Fix |
|---------|--------------|-----|
| API badge red | Backend not running / wrong port | Check `run_app.py` logs; ensure port 8000 free |
| Persona count 0 unexpectedly | Empty database | Verify `backend/pharma_personas.db` presence & rows |
| Requests 404 | Missing proxy path | Add path to proxy or use correct endpoint |
| Long initial load | Retry/backoff in action | Inspect network panel; ensure backend is up |
| Works in curl, not browser | Origin mismatch or port forward | Ensure proxy + 0.0.0.0 binding |

## Environment Variables Summary
| Variable | Purpose | Dev Behavior |
|----------|---------|--------------|
| BACKEND_HOST | Bind interface | Default `0.0.0.0` for container accessibility |
| BACKEND_PORT | Backend port | `8000` |
| DATABASE_URL | SQLite / DB connection | Points to `backend/pharma_personas.db` |
| VITE_API_URL | Prod frontend API base | Ignored in dev (proxy) |
| OPENAI_API_KEY | LLM access | Loaded server-side only |

## Extending Retry Logic
Adjust in `api.ts` interceptor:
- Increase attempts: change `>= 3` threshold
- Alter base delay: modify multiplier `200`
- Exclude certain paths: add conditional early returns

## Security Notes
- Do not expose real API keys in client bundle.
- Keep `.env` out of version control (already gitignored).
- For production use a persistent DB (Postgres) instead of ephemeral SQLite.

## Next Potential Enhancements
- Toast component for retries & offline mode
- Service Worker cache for read endpoints
- Structured logging endpoint summary at startup

---
If you modify architecture (e.g., switch to a dedicated API sub-path like `/api`), update: proxy list, API wrappers, and status badge base path logic.
