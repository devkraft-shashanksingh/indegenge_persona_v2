# AI Agents & Engines Documentation

This document describes all AI-powered agents and engines in the PharmaPersonaSim platform. Each agent is responsible for a specific domain of AI functionality, using various LLMs and AI services to deliver intelligent capabilities.

---

## Overview

PharmaPersonaSim uses a multi-agent architecture where specialized AI engines handle different aspects of persona simulation, analysis, and content generation. All agents are designed to work together seamlessly through the FastAPI backend.

**Architecture Pattern**: Each agent is a specialized module that encapsulates:
- Model-specific API interactions
- Domain-specific prompt engineering
- Response parsing and validation
- Error handling and fallbacks

---

## Core Agents

### 1. Persona Engine (`persona_engine.py`)

**Purpose**: Generates detailed, realistic AI personas (patients and HCPs) using LLM capabilities.

**Model**: OpenAI GPT-4o (`gpt-4o`)

**Key Capabilities**:
- Generate personas from attributes (age, gender, condition, concerns)
- Extract personas from interview transcripts
- Enrich personas with MBT framework (Motivations, Beliefs, Tensions)
- Generate personas from archetypes
- Extract archetypes from brand insights

**Input**:
- Demographics (age, gender, condition, location)
- Optional: Interview transcripts, brand insights, archetype templates

**Output**:
- Complete persona JSON with:
  - Demographics and medical background
  - Motivations, beliefs, pain points
  - Behavioral patterns and preferences
  - Confidence scores and evidence

**Key Functions**:
- `generate_persona_from_attributes()` - Primary persona generation
- `extract_persona_from_transcript()` - Transcript-based extraction
- `extract_persona_archetypes()` - Archetype discovery
- `generate_persona_from_archetype()` - Archetype-based generation

**Configuration**:
- Model: `OPENAI_MODEL` (default: `gpt-4o`)
- API Key: `OPENAI_API_KEY`

**Thread Safety**: ✅ Thread-safe client initialization with locking

---

### 2. Cohort Engine (`cohort_engine.py`)

**Purpose**: Analyzes how multiple personas respond to marketing stimuli (text, images, or both).

**Model**: OpenAI GPT-4o (`gpt-4o`) with vision capabilities

**Key Capabilities**:
- Text-only cohort analysis
- Multimodal analysis (text + images)
- Parallel processing of multiple personas
- Quantitative metrics extraction (sentiment, trust, clarity, purchase intent)
- Qualitative insights and reasoning
- Custom question answering

**Input**:
- List of persona IDs
- Stimulus text (marketing message, campaign copy)
- Optional: Stimulus images (marketing materials, ads)
- Metrics to analyze
- Optional: Custom questions

**Output**:
- Individual persona responses with:
  - Quantitative scores per metric
  - Reasoning and analysis summary
  - Key insights and behavioral predictions
  - Answers to custom questions
- Summary statistics across cohort
- AI-generated insights and suggestions

**Key Functions**:
- `run_cohort_analysis()` - Text-only analysis
- `run_multimodal_cohort_analysis()` - Multimodal analysis with images
- `_process_persona_multimodal()` - Worker function for parallel processing
- `create_multimodal_analysis_prompt()` - Prompt engineering for vision

**Configuration**:
- Model: `OPENAI_MODEL` (default: `gpt-4o`)
- Max Tokens: `OPENAI_MODEL_MAX_TOKENS` (default: 32768)
- Max Workers: 5 (to avoid API rate limits)
- API Key: `OPENAI_API_KEY`

**Thread Safety**: ✅ Uses ThreadPoolExecutor with serialized data (no ORM objects in workers)

**Important**: Persona data is serialized before passing to worker threads to avoid SQLAlchemy DetachedInstanceError.

---

### 3. Asset Analyzer (`asset_analyzer.py`)

**Purpose**: Provides visual annotation and feedback on marketing assets from persona perspectives using image generation.

**Model**: Google Gemini 3 Pro Image Preview (`gemini-3-pro-image-preview`)

**Key Capabilities**:
- Visual red-lining of marketing images
- Persona-specific feedback annotations
- Circle/arrow annotations with handwritten-style comments
- Color-coded feedback (positive/negative/neutral)
- Returns annotated image with feedback overlay

**Input**:
- Image bytes (PNG, JPEG)
- Persona data (demographics, MBT framework)
- MIME type

**Output**:
- Annotated image (base64-encoded data URI)
- Text feedback summary
- Analysis of what works/doesn't work from persona perspective

**Key Functions**:
- `analyze_image_with_nano_banana()` - Main analysis function
- `build_annotation_prompt()` - Creates persona-specific annotation prompts

**Configuration**:
- Model: `gemini-3-pro-image-preview`
- API Key: `IMAGE_EDIT_API_KEY` or `GEMINI_API_KEY`
- SDK: `google-genai` (new SDK)

**Visual Style**: 
- Red circles around problematic areas
- Green highlights for effective elements
- Handwritten-style annotations
- Color-coded feedback

**Thread Safety**: ✅ Stateless function calls

---

### 4. Image Improvement Engine (`image_improvement.py`)

**Purpose**: Generates improved versions of marketing images based on persona feedback and reactions.

**Model**: Google Gemini 3 Pro Image Preview (`gemini-3-pro-image-preview`)

**Key Capabilities**:
- Generate improved marketing images
- Incorporate persona feedback into visual design
- Maintain brand consistency while addressing concerns
- Return both improved image and improvement rationale

**Input**:
- Original image bytes
- Persona reactions (from cohort analysis)
- Summary statistics
- Image format (PNG, JPEG)

**Output**:
- Improved image (base64-encoded)
- Improvement rationale text
- List of changes made

**Key Functions**:
- `improve_image_with_persona_feedback()` - Main improvement function
- `extract_persona_insights()` - Extracts key feedback points

**Configuration**:
- Model: `gemini-3-pro-image-preview`
- API Key: `IMAGE_EDIT_API_KEY` or `GEMINI_API_KEY`
- SDK: `google-genai` (new SDK)

**Thread Safety**: ✅ Stateless function calls

---

### 5. Avatar Engine (`avatar_engine.py`)

**Purpose**: Generates unique, professional avatar images for personas using DALL-E 3.

**Model**: OpenAI DALL-E 3

**Key Capabilities**:
- Generate diverse, realistic persona avatars
- Age, gender, and ethnicity representation
- Professional attire based on persona type (HCP vs Patient)
- Consistent style across generations
- Deterministic generation (same inputs = same avatar)

**Input**:
- Persona attributes:
  - Age, gender
  - Persona type (HCP/Patient)
  - Optional: Specialty, condition, ethnicity

**Output**:
- Avatar image URL (DALL-E hosted)
- Generation metadata

**Key Functions**:
- `generate_avatar()` - Main avatar generation
- `build_avatar_prompt()` - Constructs detailed DALL-E prompts

**Configuration**:
- Model: `dall-e-3`
- Size: `1024x1024`
- Quality: `standard`
- Style: `natural`
- API Key: `OPENAI_API_KEY`

**Diversity Features**:
- Random ethnicity assignment if not specified
- Age-appropriate appearance
- Professional attire mapping (lab coats for HCPs, casual for patients)

**Thread Safety**: ✅ Stateless function calls

---

### 6. Document Processor (`document_processor.py`)

**Purpose**: Processes and classifies brand documents, extracts text, and prepares them for vector storage.

**Key Capabilities**:
- Text extraction from PDFs
- Document classification (7 knowledge pillars)
- Text chunking for vector embeddings
- Chunk size optimization
- Overlap handling for context preservation

**Input**:
- File path (PDF)
- Optional: Chunk size, overlap size

**Output**:
- Extracted text
- Document category/classification
- Chunked text segments

**Key Functions**:
- `extract_text()` - PDF text extraction
- `classify_document()` - AI-powered classification
- `chunk_text()` - Text chunking with overlap

**Classification Categories**:
1. Product Information (PI/SmPC)
2. Clinical Studies
3. Market Research
4. Brand Messaging
5. Competitive Intelligence
6. Regulatory Documents
7. Patient Education Materials

**Thread Safety**: ✅ Stateless function calls

---

### 7. Vector Search Engine (`vector_search.py`)

**Purpose**: Provides Retrieval-Augmented Generation (RAG) capabilities for brand document search.

**Model**: OpenAI File Search (Vector Store API)

**Key Capabilities**:
- Semantic search across brand documents
- Context retrieval for persona generation
- Multi-vector-store aggregation
- Segment-specific filtering
- Top-K retrieval with relevance scoring

**Input**:
- Brand ID
- Query text
- Optional: Target segment, top_k results

**Output**:
- List of relevant document chunks
- Relevance scores
- Source metadata

**Key Functions**:
- `search_brand_chunks()` - Main search function
- Uses OpenAI Threads API with file_search tool

**Configuration**:
- API Key: `OPENAI_API_KEY`
- Default top_k: 5

**Thread Safety**: ✅ Stateless function calls

---

## Agent Interaction Patterns

### Sequential Flow
```
User Input → Persona Engine → Cohort Engine → Asset Analyzer → Results
```

### Parallel Processing
```
Cohort Engine → ThreadPoolExecutor → Multiple Persona Workers → Aggregate Results
```

### RAG Integration
```
Persona Engine → Vector Search → Brand Documents → Enhanced Persona Generation
```

---

## Model Configuration

### OpenAI Models
- **GPT-4o**: Persona generation, cohort analysis, document classification
- **DALL-E 3**: Avatar generation
- **File Search API**: Vector search and RAG

### Google Gemini Models
- **Gemini 3 Pro Image Preview**: Image annotation and improvement

### Model Selection Rationale
- **GPT-4o**: Best for complex reasoning, persona generation, and multimodal analysis
- **DALL-E 3**: High-quality avatar generation with consistency
- **Gemini 3 Pro**: Superior image understanding and annotation capabilities

---

## Error Handling & Fallbacks

All agents implement robust error handling:

1. **API Key Validation**: Checks for API keys before initialization
2. **Model Availability**: Graceful degradation if models unavailable
3. **Rate Limiting**: Built-in retry logic and worker limits
4. **Response Validation**: JSON parsing with fallback to text extraction
5. **Thread Safety**: Proper serialization for multi-threaded operations

---

## Performance Considerations

### Optimization Strategies
- **Lazy Client Initialization**: Clients created only when needed
- **Thread Pooling**: Parallel processing with worker limits
- **Caching**: Client instances cached per process
- **Token Estimation**: Pre-flight checks for model limits

### Rate Limits
- **OpenAI**: 5 parallel workers max in cohort analysis
- **Gemini**: Sequential processing for image operations
- **DALL-E**: 1 request per persona (deterministic caching)

---

## Environment Variables

| Variable | Required | Used By | Description |
|----------|----------|---------|-------------|
| `OPENAI_API_KEY` | Yes | Persona, Cohort, Avatar, Vector Search | OpenAI API key |
| `IMAGE_EDIT_API_KEY` | Yes* | Asset Analyzer, Image Improvement | Gemini API key (fallback: GEMINI_API_KEY) |
| `GEMINI_API_KEY` | Yes* | Asset Analyzer, Image Improvement | Gemini API key (alternative) |
| `OPENAI_MODEL` | No | Persona, Cohort | Model name (default: `gpt-4o`) |
| `OPENAI_MODEL_MAX_TOKENS` | No | Cohort | Max tokens (default: 32768) |

*At least one Gemini key required for image operations

---

## Future Enhancements

### Planned Agents
1. **Compliance Agent**: MLR validation and claim verification
2. **Benchmark Agent**: Historical performance comparison
3. **Insight Agent**: Advanced pattern recognition across cohorts
4. **Translation Agent**: Multi-language persona generation

### Model Upgrades
- GPT-5 integration when available
- Gemini 3 Pro full release (beyond preview)
- Enhanced vision models for better image understanding

---

## Testing & Validation

Each agent should be tested with:
- ✅ Valid inputs (happy path)
- ✅ Invalid inputs (error handling)
- ✅ Missing API keys (graceful degradation)
- ✅ Rate limit scenarios
- ✅ Thread safety (for parallel agents)

---

## Contributing

When adding new agents:
1. Follow the existing pattern (separate file, lazy initialization)
2. Document model, capabilities, inputs, outputs
3. Implement error handling and logging
4. Add thread safety considerations
5. Update this document

---

## References

- [OpenAI API Documentation](https://platform.openai.com/docs)
- [Google Gemini API Documentation](https://ai.google.dev/gemini-api/docs)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy Threading Guide](https://docs.sqlalchemy.org/en/20/core/pooling.html#thread-local-pooling)

---

**Last Updated**: 2025-01-27  
**Maintainer**: PharmaPersonaSim Team
