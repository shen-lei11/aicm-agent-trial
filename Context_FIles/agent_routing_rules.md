# Agent Routing Rules

Purpose: Used by Specialist Routing Agent.

## Always run
- Input Structuring Agent
- Missing Info & Coverage Gap Agent after specialist outputs

## Run Base Set Filtering Agent when
- Any AICM scoping is requested
- AI system type, technology, data, lifecycle, or ownership context is available

## Run Production Set Filtering Agent when
- Deployment status is pilot/production/unknown
- Scenario mentions operations, monitoring, logging, guardrails, customer-facing use, business criticality, or live data

## Run Threat & Technique Filtering Agent when
- Scenario mentions threat concerns, LLM/GenAI, agentic AI, APIs, tools/plugins, data exposure, model failure, supply chain, or governance/compliance

## Run Missing Info Agent when
- Any specialist agent outputs Need More Info
- Any required scenario field remains Unknown
- Any control is conditionally included/excluded due to assumptions

## Proceed to Validation only when
- No critical Need More Info remains, OR
- User explicitly chooses to proceed with assumptions/conditional controls.
