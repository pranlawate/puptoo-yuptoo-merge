# puptoo-yuptoo-merge

Merge of [yuptoo](https://github.com/RedHatInsights/yuptoo) (QPC upload processor) into [insights-puptoo](https://github.com/RedHatInsights/insights-puptoo) (advisor/compliance/malware upload processor), producing a single unified Kafka consumer for the Insights platform upload pipeline.

## Status

**Phase:** Planning (approved)

## Strategy

**Strategy A+**: Merge yuptoo into puptoo, adopting the best architectural patterns from both codebases and fixing known bugs in both during the merge.

- Puptoo's battle-tested infrastructure (Redis retry, S3 upload, rich metrics, at-least-once commit semantics) is retained
- Yuptoo's superior patterns (DRY Kafka auth, encapsulated producer, typed exceptions, pluggable modifier pipeline) are adopted
- 12 known bugs across both codebases are fixed as part of the merge

See [docs/Puptoo_Yuptoo_Merge_Proposal.md](docs/Puptoo_Yuptoo_Merge_Proposal.md) for the full proposal.

## Documentation

| Document | Description |
| -------- | ----------- |
| [Proposal](docs/Puptoo_Yuptoo_Merge_Proposal.md) | Executive summary, architecture, timeline, risk assessment |
| [Comparison](docs/Puptoo_Yuptoo_Comparison.md) | 16-section side-by-side comparison of both codebases |
| [Strategy Evaluation](docs/Puptoo_Yuptoo_Merge_Strategy_Evaluation.md) | Three strategies evaluated with weighted scoring |
| [Architecture Recommendation](docs/Puptoo_Yuptoo_Merge_Recommendation.md) | Module layout, migration plan, testing strategy |
| [Implementation Tasks](docs/Puptoo_Yuptoo_Merge_Tasks.md) | 24 JIRA-sized tasks across 4 sprints (70 story points) |

## Timeline

| Sprint | Focus | Story Points |
| ------ | ----- | ------------ |
| 1 | Refactor puptoo: handler dispatch, DRY auth, typed exceptions, bug fixes | 27 |
| 2-3 | Port QPC processing: modifiers, validators, report processor, tests, uv migration | 30 |
| 4 | Deploy to stage/prod, decommission yuptoo, archive repo | 13 |

## Naming (TBD)

The merged service needs a final name. Working name for this repo is `puptoo-yuptoo-merge`. Candidates under consideration:

| Option | Full form | Style | Notes |
| ------ | --------- | ----- | ----- |
| **`uiup`** | **U**nified **I**nsights **U**pload **P**rocessor | Acronym | **Preferred.** Covers all four concepts, pronounceable ("we-up") |
| `insights-puptoo` | (keep current name) | Continuity | No rename, no operational churn. Merge is an internal change |
| `insights-upload-processor` | Insights Upload Processor | Descriptive | Future-proof for additional service types |
| `pupthree` | Platform Upload Processor III | Generational | Continues puptoo's numbering lineage (PUP II -> PUP III) |
| `puptoo-ng` | PUP II, Next Generation | Generational | Common open-source convention for rearchitected successors |

Final decision deferred until implementation phase. Current preference: **uiup**.

## Upstream Repositories

- [RedHatInsights/insights-puptoo](https://github.com/RedHatInsights/insights-puptoo)
- [RedHatInsights/yuptoo](https://github.com/RedHatInsights/yuptoo)
