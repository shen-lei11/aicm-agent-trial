# Dashboard Filter Mapping

Purpose: Maps structured scenario facts to dashboard filter signals.

## Stack filters
- Scenario involves application, interface, user interaction, API, plugin, or agent orchestration -> App
- Scenario involves data lifecycle, data storage, personal/sensitive data, RAG, documents, logs -> Data
- Scenario involves hosting, model serving, runtime, GPUs, infrastructure, capacity -> Compute
- Scenario involves network exposure, APIs, connectivity, segmentation -> Network
- Scenario involves storage, retention, backup, model artifacts, logs -> Storage
- Scenario involves physical/data centre/provider infrastructure -> Phys

## Lifecycle filters
- Data collection/curation/storage -> Preparation
- Design, training, guardrails, secure development -> Development
- Evaluation, validation, red teaming, re-evaluation -> Evaluation/Validation
- AI applications, orchestration, service supply chain rollout -> Deployment
- Operations, maintenance, continuous monitoring/improvement -> Delivery
- Archiving, deletion, model disposal -> Service Retirement

## Threat filters
Map scenario concerns to AICM threat flags:
- Data exposure/privacy -> Sensitive data disclosure
- Prompt/tool/plugin/API abuse -> Insecure apps/plugins
- Vendor/model/provider dependency -> Insecure supply chain
- AI governance/compliance concern -> Loss of governance/compliance
- Model performance/failure/drift -> Model/Service Failure/Malfunctioning
- Training data tampering -> Data poisoning
- Model extraction/IP risk -> Model theft
- Availability attack -> Denial of Service (DoS)
- Model behaviour manipulation -> Model manipulation
