# Control Applicability Rules

Purpose: Used by Base Filtering, Production Filtering, Missing Info, and Validation agents.

## Decision labels
- Primary Requirement: clearly applicable based on confirmed scenario facts.
- Secondary Recommendation: useful baseline or governance practice not specifically triggered by the scenario.
- Not Applicable: likely non-applicable based on confirmed out-of-scope facts.
- Needs Clarification: cannot classify because a critical dependency is unknown.

## Core rules
1. Do not force applicability. If relevance is unclear, mark Needs Clarification.
2. If a control is AI-Specific and the scenario confirms AI/GenAI/agentic AI, evaluate it before excluding.
3. If a control is Cloud-Specific and the scenario excludes cloud/infrastructure/provider scope, classify as Not Applicable or Needs Clarification.
4. If a control depends on data sensitivity and data sensitivity is unknown, mark Needs Clarification.
5. If a control depends on production operations and production status is unknown, mark Needs Clarification.
6. If lifecycle relevance includes Deployment, Delivery, Operations, Maintenance, or Continuous Monitoring, evaluate under Production Filtering.
7. If service-layer ownership points to AIC/AP/OSP/MP/CSP, compare it against the client's role before deciding applicability.
8. If a threat category is matched by scenario facts, controls tagged to that threat may be considered, but should still require direct rationale.
9. Proposed exclusions must include a reason and confidence.
10. Final validation must check for unsupported broad-filter recommendations.
