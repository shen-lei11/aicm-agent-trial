# Control Applicability Rules

Purpose: Used by Base Filtering, Production Filtering, Missing Info, and Validation agents.

## Decision labels
- Keep: clearly applicable based on confirmed scenario facts.
- Proposed Remove: likely non-applicable based on confirmed out-of-scope facts.
- Need More Info: cannot classify because a critical dependency is unknown.
- Conditional: relevant only if an assumption or user-provided condition is true.
- Baseline Only: generally useful baseline but not specifically triggered by the scenario.
- Manual Review Required: ambiguous, high-impact, or requires human judgement.

## Core rules
1. Do not force applicability. If relevance is unclear, mark Need More Info or Manual Review Required.
2. If a control is AI-Specific and the scenario confirms AI/GenAI/agentic AI, evaluate it before excluding.
3. If a control is Cloud-Specific and the scenario excludes cloud/infrastructure/provider scope, classify as Proposed Remove or Need More Info.
4. If a control depends on data sensitivity and data sensitivity is unknown, mark Need More Info.
5. If a control depends on production operations and production status is unknown, mark Need More Info or Conditional.
6. If lifecycle relevance includes Deployment, Delivery, Operations, Maintenance, or Continuous Monitoring, evaluate under Production Filtering.
7. If service-layer ownership points to AIC/AP/OSP/MP/CSP, compare it against the client's role before deciding applicability.
8. If a threat category is matched by scenario facts, controls tagged to that threat may be considered, but should still require direct rationale.
9. Proposed exclusions must include a reason and confidence.
10. Final validation must check for unsupported broad-filter recommendations.
