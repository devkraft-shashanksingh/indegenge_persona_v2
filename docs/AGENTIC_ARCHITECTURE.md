# Agentification Options for PharmaPersonaSim

You are currently using **Stateless "Engines"**, which are essentially fancy prompt templates. To move to an **Agentic Architecture**, we need to introduce **State**, **Autonomy**, **Tools**, and **Interaction**.

Here are 4 levels of "Agentification" we can implement:

## Option 1: Tool-Enabled Agents (The "Researcher" Pattern)
**Concept**: Give agents the ability to fetch external data instead of relying solely on their training weights.
- **Current**: `PersonaEngine` invents a persona based on GPT-4's frozen training data.
- **Agentic**: `PersonaAgent` has a **Web Search Tool**.
    - "Create a persona for a Type 2 Diabetes patient concerned about Ozempic shortages."
    - *Agent Action*: Searches Google News/Reddit for "Ozempic shortage patient impact 2024".
    - *Agent Action*: Incorporates real-time frustrations into the generated persona.
- **Implementation**:
    - Add `search_web` tool to `persona_engine.py` (or new `agents/researcher.py`).
    - Use OpenAI Function Calling to let the model decide when to search.

## Option 2: Multi-Agent Simulation (The "Focus Group" Pattern)
**Concept**: Personas interact with *each other* or a Moderator, rather than just reacting to a static stimulus.
- **Current**: `CohortEngine` sends the same text to 5 isolated personas. They don't know about each other.
- **Agentic**: Create a **Conversation Loop**.
    - **Moderator Agent**: "What do you all think of this ad?"
    - **Persona A**: "I like the colors, but the side effects scare me."
    - **Persona B**: "I agree with A. My doctor warned me about that too." (Listening to Persona A).
    - **HCP Persona**: "Actually, the side effect profile is manageable."
    - **Persona A**: "Oh, really? That makes me feel better."
- **Value**: Uncover group dynamics and social proof effects which are critical in marketing.
- **Benefits for Pharma**:
    - **Virtual Focus Groups**: Replaces expensive ($50k+) human advisory boards with instant, iterative simulations.
    - **Influence Mapping**: See how a "Skeptical Oncologist" influences a "Hopeful Patient" in a shared conversation. It reveals if your message survives a debate, not just a vacuum.
    - **Consensus Building**: Observe how the group reaches agreement (or doesn't) on a new drug claim.
    - **Adversarial Testing**: One agent attacks the claim, others defend it—simulating real-world peer review conversation.
- **Implementation**:
    - New `SimulationEngine` that manages a message history shared (or partially shared) between agents.

## Option 3: "Living" Personas (The "Sims" Pattern)
**Concept**: Personas persist and evolve over time/sessions.
- **Current**: Personas are static JSON blobs.
- **Agentic**: Personas have **Episodic Memory** (Vector DB).
    - A persona "remembers" previous campaigns they've seen.
    - If you show them a new ad next week, they might say "This contradicts what you showed me last time."
    - Their "Trust Score" becomes a state variable that fluctuates based on interactions.
- **Implementation**:
    - Add `memory` table/vector store linked to `persona_id`.
    - Update `chat_engine` to retrieve relevant past memories before responding.

## Option 4: The Orchestrator (The "Manager" Pattern)
**Concept**: A high-level agent that plans a workflow to achieve a user goal.
- **Current**: User manually clicks "Generate Persona" -> "Run Cohort" -> "Analyze Image".
- **Agentic**: User says "Optimize this campaign for skeptical cardiologists."
- **Orchestrator Agent**:
    1.  *Thinking*: "I need a cohort of skeptical cardiologists." -> Calls `PersonaEngine`.
    2.  *Thinking*: "I need to test the current campaign." -> Calls `CohortEngine`.
    3.  *Thinking*: "Result is bad (Trust 3/10). Reason: 'Lack of data'. I need to add data charts." -> Calls `ImageImprovementEngine`.
    4.  *Thinking*: "Re-testing." -> Calls `CohortEngine`.
    5.  *Result*: "Optimized campaign ready. Trust increased to 8/10."
- **Implementation**:
    - A master `Agent` class using LangGraph or a simple state machine (Needs `Plan`, `Execute`, `Verify` loop).

---

## Recommendation
I recommend starting with **Option 2 (Multi-Agent Simulation)** or **Option 4 (Orchestrator)** as they provide the most immediate "Product" value differentiation from vanilla LLMs.

**Option 2** turns a static "Survey" tool into a "Dynamic Focus Group".
**Option 4** turns a "Toolbox" into an "Employee".
