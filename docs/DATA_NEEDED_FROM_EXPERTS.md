# Pharma Persona Simulator - Inputs Needed from Pharma Experts

## What We're Building & Materials Required

**For Pharma Marketing, Medical Affairs & Compliance Teams**: We're building a production-grade tool to test patient marketing materials by simulating how different patient personas react—with built-in compliance guardrails, MLR-approved content grounding, and behavioral realism. To build this with appropriate regulatory safeguards and accuracy, we're requesting structured data inputs, governance frameworks, and expert validation.

---

## 🎯 What We're Building

A compliance-aware persona simulation platform that tests patient marketing campaigns against realistic behavioral models while enforcing regulatory guardrails. The tool will:

- **Simulate patient responses** with quantitative metrics (purchase intent, sentiment, trust, message clarity) and qualitative insights
- **Validate claims and content** against approved brand materials and MLR-vetted assets before generation
- **Ground all outputs** in structured reference data (PI/SmPC, claims database) with full audit trails
- **Calibrate predictions** using historical campaign benchmarks and market research patterns
- **Integrate with existing systems** via agent tools accessing versioned content repositories

**Architecture**: OpenAI agent-based system with retrieval-augmented generation, structured data stores, and compliance validation layer.

**Current Status**: POC Complete - Seeking Structured Inputs for Production Architecture

---

## 📥 REQUIRED: Example Campaign Materials for Testing

To build and validate the tool, we need real examples of the types of materials you want to test:

### Campaign & Branding Materials (Examples Needed):

- **Marketing Campaigns**: Digital ad copy, email campaigns, social media content, display ads
- **Brand Messaging**: Positioning statements, brand narratives, value propositions
- **Clinical Marketing**: Trial results summaries, efficacy/safety claims, RWE presentations
- **Product Communications**: Product launch messaging, patient education materials, DTC content
- **Content Marketing**: Educational content, thought leadership pieces, webinar content
- **Regulatory Communications**: Safety updates, label changes, regulatory messaging

**Requested**: 3-5 real campaign examples (redacted/anonymized) representative of typical testing scenarios.

**Example format**:
"New diabetes medication demonstrates 30% better A1C reduction vs. standard of care in Phase 3 trials. Favorable safety profile with fewer GI side effects. FDA approved for adults with Type 2 Diabetes."

---

## 👥 PATIENT PERSONA APPROACH

**Current Approach**: We generate patient personas from basic attributes: age, gender, medical condition, location, and key concerns.

**Expert Review Request**:
- Review 5-10 sample personas for realism and alignment with actual patient segments
- Feedback on missing attributes or characteristics relevant to campaign targeting
- Confirmation that generated personas match typical target audience profiles

---

## 📋 CRITICAL INPUT: Prioritized Data Requirements

To build production-grade persona simulations with compliance guardrails and behavioral realism, we need specific data inputs ranked by criticality:

---

### 🔴 HIGH PRIORITY - Compliance & Brand Foundations

These inputs establish core guardrails for any persona-driven messaging. Without them, generated content risks compliance violations.

**1. Approved Brand Content**
- **What**: Prescribing Information (PI), Summary of Product Characteristics (SmPC), FAQs, product labels
- **Specific Elements**: Indications, contraindications, clinical endpoints, approved patient populations, dosing/administration
- **Why Critical**: Canonical reference for all messaging; ensures personas operate within regulatory boundaries
- **Technical Use**: Stored as structured reference data (JSON/YAML or CMS) with versioning, expiry metadata, and source document links. Agent retrieves and cites specific sections to ground responses.
- **Requested**: Complete PI/SmPC documents, approved FAQs, current label (with version/approval dates)

**2. MLR-Approved Marketing Materials**
- **What**: All marketing assets that have passed Medical-Legal-Regulatory review
- **Specific Elements**: Asset IDs, approved channels, messaging pillars, allowed claims, tone guidelines
- **Why Critical**: Constrains generated messaging to pre-vetted content; reduces compliance risk
- **Technical Use**: Asset library with retrieval hooks enabling the agent to surface only compliant artifacts per request
- **Requested**: 5-10 MLR-approved campaign materials with asset metadata (approval date, channels, claims used)

**3. Claims Database**
- **What**: Individual marketing claims with substantiating evidence
- **Specific Elements**: Claim text, supporting clinical evidence (trial names, endpoints), approval status, expiry dates
- **Why Critical**: Enables automated claim validation before content generation; prevents off-label or unsubstantiated claims
- **Technical Use**: Separate structured dataset (not embedded in personas) for pre-generation validation
- **Requested**: List of approved claims with linked evidence sources and approval metadata

---

### 🟡 MEDIUM-HIGH PRIORITY - Behavioral Realism & Segmentation

These inputs add depth to persona behavior and improve simulation accuracy, but must be used carefully to avoid bias from outdated or noisy data.

**4. Market Research (Quantitative + Qualitative)**
- **What**: HCP/patient surveys, focus groups, ethnographic studies, behavioral research
- **Specific Elements**: Information preferences by specialty/demographic, decision-making patterns, barriers to adoption
- **Why Important**: Grounds persona responses in real-world behavioral patterns; supports audience segmentation
- **Caution**: Aggregate to anonymized patterns (e.g., "68% of cardiologists prefer peer-reviewed evidence") to avoid PHI/PII
- **Technical Use**: Pattern library feeding persona generation and response calibration (not raw individual responses)
- **Requested**: Aggregated research findings, pattern summaries, segmentation insights (no individual-level data)

**5. Historical Campaign Performance Benchmarks**
- **What**: Past campaign metrics, channel responsiveness, engagement rates, conversion data
- **Specific Elements**: Response rates by channel/demographic, successful vs. failed messaging themes, A/B test results
- **Why Important**: Calibrates simulation outputs to realistic performance ranges; validates model predictions
- **Caution**: Segment learnings by persona cluster to avoid overfitting; tie back to specific audience characteristics
- **Technical Use**: Benchmark dataset for scoring model calibration and scenario simulations (external to personas)
- **Requested**: Anonymized campaign reports with performance metrics segmented by audience type

---

### 🟢 MEDIUM PRIORITY - Advanced Personalization

These inputs enhance persona sophistication and creative routing but should be implemented after core functionality is validated.

**6. Creative Preference Attributes**
- **What**: Patient/HCP preferences for creative format and messaging style
- **Specific Elements**: "Data-forward" vs. "story-driven", visual vs. text-heavy, emotional vs. clinical tone
- **Why Useful**: Enables routing to appropriate creative variants; improves message resonance
- **Caution**: Avoid hard-coding subjective traits until validated via research or feedback loops; start with coarse buckets
- **Technical Use**: Metadata on persona records (once validated) for creative asset matching
- **Requested**: Evidence-based creative preference data (e.g., from message testing or research) mapped to audience segments

---

## 🏗️ Architectural Approach: What Goes Where

### Persona Core (Embedded in Persona Records)
- Demographics and professional data
- Motivations, pain points, barriers
- Preferred information channels
- Creative preferences *(once validated)*

### External Knowledge Bases (Separate from Personas)
- **Brand Content Repository**: PI/SmPC, labels, approved FAQs (versioned, structured)
- **MLR Asset Library**: Approved marketing materials with metadata
- **Claims Database**: Claims + evidence + approval status
- **Research Pattern Library**: Aggregated behavioral insights

### Calibration Datasets (For Model Tuning, Not Persona Fields)
- Historical campaign benchmarks
- Market research aggregations
- Segmentation insights

**Rationale**: Separating brand/claim/MLR assets from personas ensures updates don't require regenerating personas. Calibration data informs scoring models, not individual persona attributes.

---

## 🤖 Technical Implementation: Agent Tools vs. Data Stores

**Data Storage**: All six priority categories require ingestion, normalization, and structured storage:
- Vector store for unstructured documents (PI, research reports)
- Relational database for structured fields (claims, asset metadata, persona attributes)
- Versioning system with provenance tracking (owner, approval date, source)

**Agent Tools**: Build specialized retrieval/validation functions:
- `BrandContentLookup(section, product)` → Retrieves current PI snippet with citation
- `MLRAssetFetcher(asset_id, channel)` → Returns approved materials for specified context
- `ClaimValidator(claim_text)` → Checks approval status and evidence sufficiency
- `PersonaRetrieval(query)` → Fetches personas with creative preference metadata
- `BenchmarkComparator(metric, segment)` → Returns historical performance ranges

**Key Principle**: Agents should NOT embed static data in prompts; they should dynamically call these tools with retrieval-augmented generation to stay current and compliant.

---

## ✅ Recommended Implementation Workflow

**Phase 1: Ingestion & Schema Design**
1. Convert each data source to structured schema with provenance (version, owner, approval date)
2. Build data quality checks for completeness and consistency
3. Establish refresh cadence and ownership for each dataset

**Phase 2: Validation Layer**
4. Implement pre-generation validation: all generated content must reference approved brand/claim data
5. Build citation system linking outputs to source documents
6. Create compliance audit trail for all agent-generated content

**Phase 3: Persona Enrichment**
7. Start with essential data (validation rules, basic demographics, metrics)
8. Layer in creative preferences and campaign benchmarks once supporting evidence exists
9. Use market research to adjust persona weights/attributes iteratively

**Phase 4: Feedback Loop**
10. Log agent decisions and overrides for audit and improvement
11. Compare simulation predictions to actual campaign outcomes
12. Refine persona attributes and scoring models based on real-world validation

---

## 📥 What We Need From You (Summary)

| Priority | Data Type | Format Requested |
|----------|-----------|------------------|
| **High** | Approved Brand Content (PI/SmPC/Labels) | Complete documents with version dates |
| **High** | MLR-Approved Marketing Materials | 5-10 assets with metadata (ID, channel, claims, approval date) |
| **High** | Claims Database | List of claims + evidence + approval status |
| **Medium-High** | Market Research (Quant/Qual) | Aggregated patterns, no individual-level data |
| **Medium-High** | Campaign Performance Benchmarks | Anonymized reports segmented by audience |
| **Medium** | Creative Preference Data | Evidence-based preferences mapped to segments |

**Format**: Structured files (JSON/CSV preferred) or documents (PDF) with clear metadata. All materials anonymized (no PHI/PII).

**Governance**: For each dataset, identify owner, refresh cadence, and compliance review requirements.

---

## 📤 What You'll Get Back (Planned Outputs)

Once we have your inputs, the tool will provide:

### For Each Patient Persona:

**Quantitative Metrics:**
- Purchase Intent (1-10)
- Sentiment (-1 to +1)
- Trust in Brand (1-10)
- Message Clarity (1-10)

**Qualitative Insights:**
- Key Concern Flagged
- Reasoning for their response
- Information gaps they perceive

### Campaign-Level Analysis:
- Average scores across all patients
- Demographic-specific patterns
- Common concerns
- Actionable recommendations

**Expert Review**: Confirmation these metrics align with campaign evaluation needs and identification of any additional KPIs.

---

## ❓ KEY QUESTIONS FOR YOU

**1. Use Cases & Workflow**
- What are the top 3 scenarios where you'd use this tool?
- When in your campaign development process would this add most value?
- Who would use this tool? (brand managers, copywriters, compliance, medical affairs?)
- What questions do you need answered about your campaigns?

**2. Metrics & Benchmarks**
- What does "good" vs. "bad" campaign performance look like? (e.g., "purchase intent above 7 is strong")
- What metrics matter most for your team's decision-making?
- How do you currently measure campaign success?
- What performance ranges would trigger message refinement vs. approval?

**3. Personas & Segmentation**
- What patient segments do you typically target?
- What persona attributes are most important for campaign testing?
- How many personas would you typically test against per campaign?
- Do you have existing patient archetypes or segmentation models we should align with?

**4. Data Governance & Compliance**
- Who owns each data type in your organization? (brand content, claims, MLR assets)
- What's the typical review/approval cycle for marketing materials?
- How often do brand content and claims databases need updates?
- What compliance checks are mandatory before campaign deployment?
- Are there specific MLR review requirements for AI-generated content?

**5. Integration & Systems**
- Where is your brand content currently stored? (DAM, CMS, SharePoint, other?)
- Do you have existing APIs or data feeds for approved materials?
- What systems would this tool need to integrate with?
- How do you track asset versioning and approval status today?

---

## 💡 Your Use Cases (Examples Needed)

Please share 2-3 real scenarios where you'd use this tool:

- Pre-launch campaign testing?
- A/B message testing?
- Competitive messaging analysis?
- Patient education material validation?
- Regulatory messaging review?
- Multi-channel campaign optimization?

**Requested**: Specific examples from actual workflows, anonymized as appropriate.

---

## 🤝 HOW TO PROVIDE INPUT

**Phase 1 (High Priority - Required for Compliance)**:
- Approved Brand Content: Complete PI/SmPC documents with version metadata
- MLR-Approved Materials: 5-10 assets with asset IDs, channels, and approval dates
- Claims Database: Approved claims list with supporting evidence and approval status
- 3-5 campaign examples for testing scenarios

**Phase 2 (Medium-High Priority - Enhances Realism)**:
- Market Research: Aggregated behavioral patterns and segmentation insights
- Campaign Benchmarks: Historical performance data segmented by audience
- Persona Review: Feedback on 5-10 generated sample personas

**Phase 3 (Medium Priority - Advanced Features)**:
- Creative Preference Data: Evidence-based preferences by segment
- Competitive Intelligence: Competitor messaging and positioning
- Patient Journey Maps: Detailed pathway documentation

**Preferred Formats**:
- Structured data: JSON, CSV, Excel with clear field definitions
- Documents: PDF with metadata (version, approval date, owner)
- Access: Shared folders, document management systems, or API endpoints

**Governance Setup**:
For each dataset, specify: data owner, refresh cadence, approval workflow, compliance requirements

**Contact**: [Development Team Contact Info]

---

## 📊 How This Strengthens the Tool

**Compliance & Risk Mitigation**
- Approved brand content establishes regulatory guardrails for all generated messaging
- MLR asset library ensures only vetted materials inform persona responses
- Claims validation prevents off-label or unsubstantiated statements
- Audit trails link all outputs to source documents for review

**Behavioral Realism**
- Market research patterns ground persona responses in actual patient/HCP behavior
- Campaign benchmarks calibrate predictions to realistic performance ranges
- Segmentation insights enable audience-specific messaging optimization
- Creative preference data improves message-to-audience matching

**Production Readiness**
- Structured data storage enables scalable, versioned content management
- Agent tooling architecture supports real-time retrieval of current approved materials
- Governance framework ensures data freshness and compliance alignment
- Integration capabilities connect to existing marketing tech stack

**Business Impact**
- Reduces compliance review cycles by pre-validating against approved content
- Improves campaign ROI through behavioral-based message optimization
- Accelerates time-to-market with rapid, compliant testing scenarios
- Provides audit-ready documentation for regulatory requirements

---

## ⏱️ Implementation Timeline

**Phase 1: Foundation (Weeks 1-2)**
- Review prioritized data requirements
- Provide High Priority datasets (brand content, MLR materials, claims)
- Define data governance (owners, refresh cadence, compliance checks)

**Phase 2: Integration & Validation (Weeks 3-4)**
- Ingest and structure Phase 1 data
- Build agent tools for brand content/claim retrieval
- Test compliance validation layer with sample scenarios

**Phase 3: Calibration (Weeks 5-6)**
- Provide Medium-High Priority data (market research, benchmarks)
- Review generated sample personas for realism
- Calibrate scoring models against historical performance

**Phase 4: Enhancement (Weeks 7-8)**
- Layer in Medium Priority data (creative preferences)
- Test campaign simulation scenarios with real examples
- Iterate based on expert feedback and validation results

**Ongoing: Feedback Loop**
- Monitor simulation accuracy vs. real campaign outcomes
- Update datasets per refresh cadence
- Refine persona attributes and scoring based on learnings

---

## 🔒 Data Privacy & Security

**Important Reminders**:
- All data should be anonymized (no PHI/PII)
- No individual patient identifiable information
- Redact proprietary information as needed
- Aggregated or pattern-based data preferred
- We'll comply with your data sharing agreements

---

**Document Purpose**: Requirements Gathering for Production Release  
**Status**: POC Complete - Production Architecture & Compliance Framework Required  
**Target Audience**: Pharma Marketing, Medical Affairs, Compliance, and Data Governance Teams  
**Next Action**: Review prioritized requirements and coordinate phased data sharing

**Document Version**: 3.0  
**Last Updated**: November 20, 2024
