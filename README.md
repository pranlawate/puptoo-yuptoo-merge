# puptoo-yuptoo-merge

Merge of [yuptoo](https://github.com/RedHatInsights/yuptoo) (QPC upload processor) into [insights-puptoo](https://github.com/RedHatInsights/insights-puptoo) (advisor/compliance/malware upload processor), producing a single codebase deployed as multiple handler-filtered instances for the Insights platform upload pipeline.

**This README is the current source of truth for this project.** It is kept up to date as work progresses (last updated 2026-08-05). If you're reading this significantly later, cross-check against JIRA epic [RHINENG-27899](https://redhat.atlassian.net/browse/RHINENG-27899).

## Current Status (as of 2026-08-05)

| Phase | Status |
|---|---|
| **Phase 1** — Refactor puptoo, handler dispatch, A+ infrastructure | ✅ Complete. Prod released Jul 20 |
| **Phase 1.5** — Infrastructure investigation | ✅ Closed Jul 23. Most of it turned into **Won't Do** once the repo strategy reversed (see below) |
| **Phase 2** — Port QPC processing into puptoo | 🔄 In progress. 11 tasks, 34 SP, targeting Sprint 4 (Aug 11/12 - Sep 2) |
| **Phase 3** — Stage deploy, cutover, decommission | 📝 Drafted, not yet created in JIRA |

Full task-level detail: [Implementation Tasks](docs/Puptoo_Yuptoo_Merge_Tasks.md) (the other living document in this repo).

### Repo strategy: reversed Jul 20, 2026

The original plan stood up a new repo, `insights-upload-processor`, with its own namespace, CI/CD, and Konflux pipeline (this is what "Phase 1.5" was for). **On 2026-07-20 the team reversed that decision.** The merge now happens in-place in this existing `insights-puptoo` repo, gated by environment variables and Unleash feature flags. `insights-upload-processor` exists on GitHub but is dormant, reserved for a possible final rename once the merge and cutover are complete and stable (see Phase 3, task 3.8, still an open decision).

## Deployment Model

Single container image, deployed as **two independent Deployments** within the existing namespace (confirmed at the Jul 29 sync: no new namespace needed):

- **Puptoo deployment:** 64 pods, `ENABLED_HANDLERS=advisor,compliance,malware-detection`, consumer group `puptoo-upload-processor`
- **Yuptoo deployment:** 8 pods, `ENABLED_HANDLERS=qpc`, consumer group `yuptoo-upload-processor`

Pod topology (64 + 8 = 72 consumers total) and the underlying Kafka partition count are unchanged from today's two-service setup. The merge consolidates the codebase, CI/CD pipeline, and CVE lifecycle without changing operational scaling. Runtime behavior (kill switches, gradual rollout) is additionally controlled by three Unleash flags: `puptoo.qpc-processing-enabled`, `puptoo.qpc-org-migration`, `puptoo.qpc-hosts-transformation`.

**JIRA epic:** [RHINENG-27899](https://redhat.atlassian.net/browse/RHINENG-27899)
**ADR:** [ADR-0009](https://gitlab.cee.redhat.com/insights-platform/architecture/-/blob/master/docs/decisions/common/0009-consolidate-puptoo-yuptoo-upload-processors.md) (accepted and merged 2026-07-09)

## Strategy

**Strategy A+**: merge yuptoo into puptoo in-place, adopting the best architectural patterns from both codebases and fixing known bugs in both during the merge (typed exceptions, DRY Kafka auth, pre-registered modifier pipeline, commit-after-processing semantics).

## Documentation

### Living documents (kept current)

| Document | Description |
|---|---|
| **This README** | Current status, deployment model, repo strategy |
| [Implementation Tasks](docs/Puptoo_Yuptoo_Merge_Tasks.md) | Task-by-task status across all phases, synced with JIRA |
| [Decision Log](docs/Decision_Log.md) | Chronological record of major pivots (repo-strategy reversal, naming, env-var/flag split, etc.) and what each superseded |
| [Architecture Diagrams](docs/diagrams/) | Component, data flow, class, and sequence diagrams (Mermaid). These describe the actual system architecture (built + planned), not a past decision, so they get updated as the real thing changes. Last verified against code: 2026-08-05 (Phase 1 handlers/exceptions confirmed to match; the component diagram's "To-Be" section was corrected the same day, it had drifted to describe an abandoned single-deployment design). **Re-verify once Phase 2 lands `QPCHandler` and the modifier pipeline** |

### Archived documents (`docs/archive/`, frozen — reflect the state at time of writing, not updated further)

These informed decisions that are already closed. Re-reading them changes nothing about current work; they're kept for context on how those decisions were reached. Everything in this folder is frozen, nothing outside it is.

| Document | Description | Served its purpose as of |
|---|---|---|
| [Proposal](docs/archive/Puptoo_Yuptoo_Merge_Proposal.md) | Original engineering proposal used to get stakeholders and the ADR approved | Jun 2026 kickoff |
| [Comparison](docs/archive/Puptoo_Yuptoo_Comparison.md) | 16-section side-by-side codebase study used to pick the merge strategy | Jun 2026 strategy selection |
| [Strategy Evaluation](docs/archive/Puptoo_Yuptoo_Merge_Strategy_Evaluation.md) | Three strategies evaluated with weighted scoring (conclusion: Strategy A+) | Jun 2026 strategy selection |
| [Architecture Recommendation](docs/archive/Puptoo_Yuptoo_Merge_Recommendation.md) | Detailed module layout, migration plan, testing strategy | Jun 2026, module layout still accurate, deployment/cutover sections superseded |
| [HBI Reporter Impact Analysis](docs/archive/HBI_Reporter_Impact_Analysis.md) | Informed the reporter-naming decision (resolved: Scenario A, keep existing names) | Jul 2026 decision |
| [Slides Draft](docs/archive/Google_Slides_Draft.md) | Working draft for the stakeholder presentation deck | Jun 2026 kickoff |
| [Presentation (Google Slides)](https://docs.google.com/presentation/d/1TOqGv-49O1DcKl1hcW0Z_NXtttQ0uk26m0LmIFy0nfU/edit?usp=sharing) | The stakeholder deck itself | Jun 2026 kickoff |

## Naming

The merged service is named **"Insights Upload Processor"** and referred usually as **"Upload Processor"** ([RHINENG-27900](https://redhat.atlassian.net/browse/RHINENG-27900), decided). This repo, the codebase, and the container image keep the `insights-puptoo` name until the Phase 3 final rename to `insights-upload-processor` (still an open scope/ownership decision, see [Implementation Tasks](docs/Puptoo_Yuptoo_Merge_Tasks.md#phase-3-stage-deploy-cutover-decommission--draft-not-yet-created-in-jira)).

## Upstream Repositories

- [RedHatInsights/insights-puptoo](https://github.com/RedHatInsights/insights-puptoo) — the active codebase, where the merge actually happens
- [RedHatInsights/yuptoo](https://github.com/RedHatInsights/yuptoo) — to be archived after Phase 3 decommission
- [RedHatInsights/insights-upload-processor](https://github.com/RedHatInsights/insights-upload-processor) — dormant, reserved for the eventual rename
