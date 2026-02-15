# Refactor Monolithic `main.py` and Implement Alembic Migrations

**Type:** Refactor / Technical Debt
**Priority:** High
**Effort:** Large (3-5 days)
**Status:** Open

## TL;DR
The `backend/app/main.py` file has grown excessively large (>3300 lines) and handles mixed concerns including API routing, database models, business logic, and schema migrations. This creates a brittle architecture that is hard to maintain and test. Additionally, schema changes are applied via raw SQL on startup, which is risky for production environments.

## Current vs Expected Behavior

| Feature | Current Behavior | Expected Behavior |
| :--- | :--- | :--- |
| **Routing** | All API routes (Personas, Synthetic Testing, etc.) are defined in `main.py`. | Routes are split into modular routers (e.g., `app/routers/personas.py`) and included via `app.include_router()`. |
| **Migrations** | `run_startup_migration()` executes raw SQL DDL statements on app startup. | Database schema changes are managed via `alembic` migrations with properly versioned scripts. |
| **Configuration** | Environment variables are accessed directly or hardcoded in `verify_apis.py`. | Configuration is centralized in a `Settings` class (using Pydantic) with proper validation. |
| **Exception Handling** | Global exception handlers are defined in `main.py`. | Exception handlers are moved to `app/core/exceptions.py`. |

## Relevant Files
- `backend/app/main.py` (3397 lines)
- `backend/verify_apis.py` (Contains hardcoded model names and direct env access)
- `backend/app/database.py` (Needs update for Alembic integration)

## Technical Implementation Plan
1.  **Modularize Routes**: Create a standard `app/routers` directory and move endpoint logic from `main.py` to dedicated files (e.g., `personas.py`, `synthetic.py`, `health.py`).
2.  **Setup Alembic**: Initialize Alembic in `backend/` and generate an initial migration `alembic revision --autogenerate` to capture the current schema state.
3.  **Refactor Config**: Create `app/core/config.py` using `pydantic-settings` to manage environment variables and constants.
4.  **Clean up `main.py`**: Reduce `main.py` to < 100 lines, focused solely on initializing the `FastAPI` app, including routers, and setting up middleware.

## Risks & Notes
- **Database Consistency**: Ensure the initial Alembic migration accurately reflects the existing schema to avoid conflicts during the first run.
- **Testing**: Existing tests that import from `main` might need updates to point to the new module locations.
