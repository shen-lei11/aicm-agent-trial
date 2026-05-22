# Scenario Taxonomy for AICM Agentic Workflow

Purpose: Used by the Input Structuring Agent and Specialist Routing Agent to convert messy client input into structured scenario fields.

## Core AICM taxonomy sources extracted
- AICM controls master: `aicm_controls_master.csv`
- LLM taxonomy: `aicm_llm_taxonomy.csv` and `aicm_llm_taxonomy_raw.csv`
- AI-CAIQ question bank: `aicm_caiq_questions.csv`

## Scenario fields to extract
- AI system type: Agentic AI, RAG, GenAI application, AI service, model development/fine-tuning, external SaaS AI, internal productivity AI
- Technologies/vendors: LLM provider, orchestration framework, APIs, plugins/tools, vector database, cloud provider, model provider
- Service layer: GenAI Ops/Processing Infrastructure, Model, Orchestrated Services, Application
- Actor/ownership role: CSP, MP, OSP, AP, AIC, Shared
- AI stack components: Phys, Network, Compute, Storage, App, Data
- Lifecycle: Preparation, Development, Evaluation/Validation, Deployment, Delivery, Service Retirement
- Data sensitivity: personal data, sensitive data, customer data, employee data, confidential data, unknown
- Operational status: concept, prototype, pilot, production, retired, unknown
- Threat themes: model manipulation, data poisoning, sensitive data disclosure, model theft, model/service failure, insecure supply chain, insecure apps/plugins, DoS, loss of governance/compliance

## Rule
Input Structuring Agent must not recommend controls. It should only identify confirmed facts, inferred facts, unknowns, and filter signals.
