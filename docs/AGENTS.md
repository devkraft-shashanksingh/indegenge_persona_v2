# AGENTS.md

A guide for AI coding agents working on this project. This file complements the README.md by providing agent-specific instructions, build steps, and conventions.

## Setup Commands

### Backend Setup
- Install dependencies: `cd backend && pip install -r requirements.txt`
- Create virtual environment: `python -m venv venv`
- Activate venv: `venv\Scripts\activate` (Windows) or `source venv/bin/activate` (Mac/Linux)
- Environment variables: Create `backend/.env` with required API keys (see Environment Variables section)

### Frontend Setup
- Install dependencies: `cd frontend && npm install`
- Start dev server: `npm run dev` (runs on http://localhost:5173)

### Full Stack Launch
- Run both servers: `python run_app.py` (from project root)
- Backend API: http://localhost:8000
- Frontend: http://localhost:5173
- API Docs: http://localhost:8000/docs

## Code Style

### Python (Backend)
- Follow PEP 8 style guide
- Use type hints where possible (`from typing import Dict, List, Optional, Any`)
- Use f-strings for string formatting
- Maximum line length: 100 characters (soft limit)
- Use descriptive variable names
- Add docstrings for functions and classes
- Import order: standard library → third-party → local imports

### TypeScript/React (Frontend)
- TypeScript strict mode enabled
- Use functional components with hooks
- Prefer named exports over default exports
- Use interfaces for type definitions
- Follow React best practices (keys for lists, proper dependency arrays)
- ESLint rules configured in `eslint.config.js`
- Current linting is permissive (`@typescript-eslint/no-explicit-any: 'off'`) - incrementally hardening types

### File Naming
- Python: `snake_case.py`
- TypeScript/React: `PascalCase.tsx` for components, `camelCase.ts` for utilities
- Test files: `*.test.ts` or `*.spec.ts` (when added)

## Testing Instructions

### Backend
- No formal test suite yet - add tests when making changes
- Manual testing via FastAPI docs at http://localhost:8000/docs
- Check API endpoints respond correctly
- Verify database operations (SQLite in dev, PostgreSQL in prod)

### Frontend
- No formal test suite yet - add tests when making changes
- Manual testing: Run `npm run dev` and test in browser
- Linting: Run `npm run lint` before committing
- Type checking: Run `npm run build` to check TypeScript compilation

### Before Committing
- Run `npm run lint` in frontend directory
- Run `npm run build` to ensure TypeScript compiles
- Check that `python run_app.py` starts both servers successfully
- Verify no console errors in browser dev tools

## Environment Variables

### Backend (`backend/.env`)
Required:
- `OPENAI_API_KEY` - OpenAI API key for GPT models
- `IMAGE_EDIT_API_KEY` or `GEMINI_API_KEY` - Google Gemini API key for image operations

Optional:
- `DATABASE_URL` - PostgreSQL connection string (defaults to SQLite in dev)
- `OPENAI_MODEL` - Model name (default: `gpt-5.2`)
- `OPENAI_MODEL_MAX_TOKENS` - Max tokens (default: 32768)

### Frontend
- `VITE_API_URL` - Backend API URL (only needed in production)

**Important**: Always use `backend/.env` for API keys, not root `.env`

## Project Structure

```
pharmapersonasim/
├── backend/
│   ├── app/
│   │   ├── main.py               # FastAPI endpoints
│   │   ├── models.py             # SQLAlchemy models
│   │   ├── schemas.py            # Pydantic schemas
│   │   ├── crud.py               # Database operations
│   │   ├── database.py           # DB connection setup
│   │   ├── persona_engine.py     # Persona generation agent
│   │   ├── cohort_engine.py      # Cohort analysis agent
│   │   ├── coverage_engine.py    # Persona coverage gap analysis
│   │   ├── asset_analyzer.py     # Image annotation agent
│   │   ├── image_improvement.py  # Image improvement agent
│   │   ├── avatar_engine.py      # Avatar generation agent
│   │   ├── document_processor.py # Document processing & chunking
│   │   ├── vector_search.py      # RAG/search agent
│   │   ├── knowledge_extractor.py # Knowledge graph extraction
│   │   ├── similarity_service.py # Persona similarity matching
│   │   ├── auto_enrichment.py    # Auto-enrichment pipeline
│   │   ├── disease_packs.py      # Condition-specific MBT packs
│   │   └── archetypes.py         # Persona archetype definitions
│   ├── scripts/                  # Utility & migration scripts
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── pages/               # React pages
│   │   ├── components/          # React components
│   │   ├── lib/                 # Utilities and API client
│   │   └── types/               # TypeScript type definitions
│   └── package.json
├── run_app.py                   # Full-stack launcher
├── README.md                    # Human-readable docs
├── AI_AGENTS.md                 # AI agents documentation
└── AGENTS.md                    # This file
```

## Development Environment Tips

### Database
- Development uses SQLite (`backend/pharma_personas.db`)
- Production uses PostgreSQL (set `DATABASE_URL`)
- Migrations: Run scripts in `backend/scripts/` as needed
- Never commit database files to git

### API Development
- Backend uses FastAPI with automatic OpenAPI docs
- Test endpoints at http://localhost:8000/docs
- Use `Depends(get_db)` for database sessions
- Always serialize ORM objects before passing to worker threads (see `cohort_engine.py`)

### Frontend Development
- Uses Vite for fast HMR
- Proxy configured in `vite.config.ts` for API calls
- Components use shadcn/ui library
- State management: React hooks (useState, useEffect)
- API calls via `src/lib/api.ts`

### Thread Safety
- **Critical**: SQLAlchemy ORM objects cannot be passed to worker threads
- Always serialize persona data before `ThreadPoolExecutor` (see `cohort_engine.py` lines 960-985)
- Use plain dictionaries, not ORM objects, in parallel workers

### OpenAI Client Initialization
- All AI engines use lazy, thread-safe client initialization
- Pattern: Use `threading.Lock()` to protect singleton creation
- Reference implementation in `cohort_engine.py`, `persona_engine.py`, `coverage_engine.py`
- Example:
  ```python
  import threading
  _openai_client: Optional[OpenAI] = None
  _client_lock = threading.Lock()

  def get_openai_client() -> Optional[OpenAI]:
      api_key = os.getenv("OPENAI_API_KEY")
      if not api_key:
          return None
      global _openai_client
      with _client_lock:
          if _openai_client is None:
              _openai_client = OpenAI(api_key=api_key)
      return _openai_client
  ```

## Common Tasks

### Adding a New API Endpoint
1. Add route in `backend/app/main.py`
2. Create schema in `backend/app/schemas.py` if needed
3. Add CRUD operations in `backend/app/crud.py` if needed
4. Test at http://localhost:8000/docs
5. Update frontend API client in `frontend/src/lib/api.ts`

### Adding a New Frontend Page
1. Create component in `frontend/src/pages/`
2. Add route in `frontend/src/App.tsx`
3. Add navigation link in `frontend/src/components/Layout.tsx` if needed
4. Test routing and API integration

### Adding a New AI Agent
1. Create new file in `backend/app/` (e.g., `new_agent.py`)
2. Follow pattern from existing agents:
   - Use thread-safe lazy client initialization (see OpenAI Client Initialization section)
   - Default model: `MODEL_NAME = os.getenv("OPENAI_MODEL", "gpt-5.2")`
   - Proper error handling with consistent response structures
3. Document in `AI_AGENTS.md`
4. Add endpoint in `backend/app/main.py` if needed

## PR Instructions

### Commit Message Format
- Use descriptive commit messages
- Prefix with component if relevant: `[backend]`, `[frontend]`, `[docs]`
- Examples:
  - `[backend] Fix DetachedInstanceError in cohort analysis`
  - `[frontend] Add persona comparison page`
  - `[docs] Update AGENTS.md with thread safety notes`

### Before Submitting PR
- ✅ Run `npm run lint` in frontend (fix any errors)
- ✅ Run `npm run build` to verify TypeScript compiles
- ✅ Test locally with `python run_app.py`
- ✅ Check browser console for errors
- ✅ Verify API endpoints work in FastAPI docs
- ✅ Update documentation if adding features

## Security Considerations

- **Never commit API keys** - Use `.env` files (already in `.gitignore`)
- **Never commit database files** - SQLite DB is in `.gitignore`
- **No PHI/PII** - Use synthetic/anonymized data only
- **API Key Management** - Always load from `backend/.env`, never hardcode

## Known Issues & Workarounds

### SQLAlchemy Threading
- **Issue**: ORM objects detached in worker threads
- **Solution**: Serialize data before passing to `ThreadPoolExecutor`
- **See**: `backend/app/cohort_engine.py` lines 960-985 for reference implementation

### Response Structure Consistency
- **Issue**: Error responses must match success response structure
- **Solution**: Always include all expected keys (e.g., `'answers': []`) in error responses
- **See**: `backend/app/cohort_engine.py` error handlers for examples

### Environment Variables
- **Issue**: `.env` file location confusion
- **Solution**: Always use `backend/.env` for API keys
- **See**: `run_app.py` and `backend/app/database.py` for loading pattern

### Port Conflicts
- **Issue**: Ports 8000 or 5173 already in use
- **Solution**: `run_app.py` automatically kills processes on these ports
- **Manual**: Use `netstat -ano | findstr :8000` (Windows) or `lsof -ti :8000` (Mac/Linux)

## Additional Resources

- [AI_AGENTS.md](AI_AGENTS.md) - Detailed documentation of AI agents/engines
- [README.md](README.md) - Project overview and quick start
- FastAPI Docs: http://localhost:8000/docs (when running)
- [AGENTS.md Specification](https://agents.md/) - Format reference

---

**Last Updated**: 2026-01-12  
**Maintainer**: PharmaPersonaSim Team
