# Changelog

All notable changes to PharmaPersonaSim.

## [Unreleased]

### Added
- **Persona Comparison Engine** (`backend/app/comparison_engine.py`)
  - LLM-powered similarity/difference analysis between personas
  - Attribute differentiation scoring with highlight levels
  - Natural language Q&A for comparative insights
  - Suggested questions for HCP and Patient comparisons

- **Chat Engine** (`backend/app/chat_engine.py`)
  - Multi-turn conversations with personas
  - Persona "stays in character" via rich system prompts
  - Session management with auto-generated conversation titles
  - Message history persistence (20 message context window)

- **Agentic Architecture Roadmap** (`AGENTIC_ARCHITECTURE.md`)
  - 4-level agentification options documented:
    1. Tool-Enabled Agents (Web Search)
    2. Multi-Agent Simulation (Focus Groups)
    3. Living Personas (Episodic Memory)
    4. Orchestrator Pattern (Workflow Planning)

- **Product Vision Document** (`PRODUCT_VISION.md`)
  - 2026 roadmap with quarterly milestones
  - Feature-level timeline visualization
  - Risk management and stakeholder communication plan

- **Frontend: Collapsible UI Component** (`frontend/src/components/ui/collapsible.tsx`)

- **Synthetic Testing Engine** (`backend/app/synthetic_testing_engine.py`)
  - Objective 1-7 scoring of marketing assets
  - Qualitative feedback aggregation
  - Competitive benchmarking against personas

- **Synthetic Testing Workspace** (`frontend/src/components/SyntheticTestingWorkspace.tsx`)
  - UI for uploading assets and viewing analysis results
  - Visual charts for "Unmet Need vs. Performance"

### Changed
- Refactored **Persona Archetypes** to **Segments** (`backend/app/segments.py`) for better domain alignment
- Updated presentation slides with new branded imagery
- Removed old PNG slides in favor of JPG format
