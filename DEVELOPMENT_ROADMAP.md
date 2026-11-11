# Dreamztree Intelligence — Development Roadmap

## Purpose

Evolve the existing Dreamztree Meta Report Streamlit application into a complete marketing intelligence platform while preserving current production behavior.

**Working branch:** `development`  
**Production branch:** `main` (do not modify during development)

## Non-negotiable preservation requirements

The following existing capabilities must remain available unless a later, explicitly approved change says otherwise:

- Meta Ads Excel upload and report processing
- Campaign-to-staff, course, and branch mapping, including manual mapping edits
- Existing lead, spend, cost-per-lead, and currency calculations
- Yesterday-versus-today comparisons and non-result campaign warnings
- USD-to-KWD exchange-rate retrieval and manual fallback
- Existing report exports and downloadable formats
- Existing authentication, account flows, and Supabase integration
- Existing group/private chat and Game Zone functionality
- Existing login experience, branding, and animations

**Explicitly out of scope:** a Smart Excel Cleaning System. Do not add a cleaning module or automatically delete/alter uploaded records.

## Repository findings from the initial review

- `app.py` is the main Streamlit application and currently contains substantial UI, authentication, mapping, reporting, and styling logic.
- `ai_features.py` already provides provider configuration (Groq, Gemini, OpenAI), report metrics, deterministic alerts, forecast helpers, report Q&A, and management summaries.
- `AI_SETUP.md` documents AI configuration, but its stated provider preference should be checked against the actual implementation before changing either.
- `requirements.txt` already includes Streamlit, Pandas, Plotly, Supabase, Excel and document-export dependencies.
- A premium charcoal theme and animated login experience already exist. Refine these rather than replacing them.

## Delivery phases

### Phase 0 — Baseline and safety
- Keep `main` untouched.
- Record the current feature inventory and deployment configuration.
- Inspect the complete application navigation, Supabase schema/RLS assumptions, and secrets usage.
- Capture representative report outputs and calculation baselines.
- Add regression checks around campaign mapping, totals, CPL, currency conversion, and report generation before refactoring.

### Phase 1 — UI and information architecture
- Introduce a clear navigation structure for Overview, Campaign Intelligence, Branch Analytics, Staff Performance, Course Analytics, Reports, AI Analyst, and existing collaboration tools.
- Reuse the existing dark theme tokens and components.
- Keep existing pages reachable during the transition.
- Improve responsive behavior, empty states, loading states, and accessible contrast.

### Phase 2 — Marketing analytics
- Add executive KPI summaries and time-series trends.
- Add campaign, branch, staff, and course comparisons.
- Show attribution coverage and clearly distinguish assigned from unassigned campaigns.
- Preserve the existing definitions and calculations; label any new metric definitions explicitly.

### Phase 3 — AI decision support
- Reuse `ai_features.py` rather than duplicating its calculations.
- Ground generated explanations in verified report aggregates.
- Display the reporting period, data coverage, and limitations with each insight.
- Keep deterministic calculations available when no AI provider is configured.
- Never let AI silently change budgets or campaign settings.

### Phase 4 — Lead and team workflows
- Design optional lead follow-up and status workflows only after reviewing the current data model and privacy requirements.
- Extend existing chat and collaboration features rather than replacing them.
- Apply role-based authorization and Supabase Row Level Security to every new data path.

### Phase 5 — Reporting, QA, and release
- Add scheduled/reporting enhancements only after deployment and delivery constraints are confirmed.
- Test with small and large exports, missing mappings, zero-result campaigns, and currency API failure.
- Run authentication, authorization, regression, and performance checks.
- Deploy the development build for user review; merge to `main` only after explicit approval.

## Engineering rules

1. Do not rewrite the monolithic application in one pass.
2. Prefer small, isolated changes and reversible commits.
3. Do not change existing report inclusion rules or formulas without a documented comparison.
4. Never commit API keys, service-role keys, passwords, or `.streamlit/secrets.toml`.
5. Do not expose Supabase privileged credentials in browser/client code.
6. Do not create or alter database tables/policies until the existing schema and RLS policies have been reviewed.
7. Do not remove existing navigation items or features as part of a redesign.
8. Every new dashboard metric must have a documented definition and test.

## Immediate next actions

1. Complete a full inventory of the current app's pages, tabs, and workflows.
2. Review the remaining `app.py` sections and all AI/report helper call sites.
3. Inspect existing Supabase integration points and deployment assumptions.
4. Build a baseline test set before the first functional code change.
