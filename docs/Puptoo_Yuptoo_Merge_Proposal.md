# Proposal: Merge Yuptoo into Puptoo

**Author:** Pranav Lawate
**Date:** June 2026
**Status:** Kickoff (Jun 22, 2026)
**Epic:** [RHINENG-27899](https://redhat.atlassian.net/browse/RHINENG-27899)
**ADR:** [GitLab MR #13](https://gitlab.cee.redhat.com/insights-platform/architecture/-/merge_requests/13)
**Audience:** insights-puptoo and yuptoo maintainers, Insights-Framework team

---

## Executive Summary

I propose merging `yuptoo` (QPC upload processor) into `insights-puptoo` (advisor/compliance/malware upload processor). Both services consume from the same Kafka topic (`platform.upload.announce`), produce to the same downstream topics, and send hosts to HBI. They differ only in which `service` header they match and how they transform host data.

Rather than a naive code port, the merge adopts the best architectural patterns from each codebase and fixes 12 known bugs in both. The result is a single service that is more maintainable, more correct, and operationally simpler than running two separate services.

**Effort:** ~4 sprints (70 story points)
**Risk to existing traffic:** Low (advisor/compliance/malware path untouched)
**Rollback:** Clean (revert puptoo, re-deploy yuptoo)

---

## Why Merge?

### Operational Cost of Two Services

| Concern      | Current state (two services)                                                                                                                               |
| ------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Deployment   | Two ClowdApp manifests, two CI/CD pipelines, two Konflux configs                                                                                           |
| Monitoring   | Two sets of dashboards, two sets of alerts, two pager rotation entries                                                                                     |
| On-call      | Engineers must understand two codebases for the same conceptual function                                                                                   |
| Kafka        | Two consumer groups competing for the same topic partitions                                                                                                |
| Dependencies | Two lockfiles with slightly different versions of the same packages                                                                                        |
| Code quality | No cross-pollination of improvements (e.g., yuptoo has DRY Kafka auth that puptoo duplicates; puptoo has at-least-once commit semantics that yuptoo lacks) |

### Natural Fit

Puptoo already routes by `service` header:

```python
if service in ["advisor"]:
    # insights-core extraction
elif service in ["compliance", "malware-detection"]:
    # forward metadata
```

Adding `qpc` is architecturally identical to adding `compliance` was. The routing, retry, and output infrastructure already exists.

---

## Strategy Evaluated

I evaluated three strategies with weighted scoring across six dimensions:

| Strategy | Description | Effort | Weighted Score |
| -------- | ----------- | ------ | -------------- |
| **A: yuptoo into puptoo** | Add QPC as a fourth service type in puptoo | ~3 sprints | 98 |
| B: puptoo into yuptoo | Port insights-core extraction into yuptoo | ~5 sprints | 63 |
| C: New unified service | Clean-room design cherry-picking from both | ~8 sprints | 55 |
| **A+: Best-of-both** | Strategy A + adopt yuptoo's superior patterns + fix bugs | ~4 sprints | **107** |

**My recommendation: Strategy A+.** It costs one extra sprint over vanilla A but achieves clean-room architecture quality (score 5/5) and long-term maintenance (score 5/5) without the greenfield risk.

### Scoring Breakdown

| Criterion | Weight | A | A+ | B | C |
| --------- | ------ | - | -- | - | - |
| Low effort | 3 | 5 | 4 | 3 | 1 |
| Low risk | 5 | 5 | 5 | 2 | 2 |
| Architecture quality | 3 | 3 | 5 | 4 | 5 |
| Operational continuity | 4 | 5 | 5 | 2 | 1 |
| Test confidence | 4 | 5 | 5 | 3 | 2 |
| Long-term maintenance | 3 | 3 | 5 | 4 | 5 |

---

## What the Merged Service Looks Like

### Data Flow

```
  Kafka: platform.upload.announce
        │
        ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │                    insights-puptoo (merged)                      │
  │                                                                 │
  │  app.py (thin dispatch loop)                                    │
  │  consumer.poll() → service header → get_handler() → commit     │
  │       │                                                         │
  │       ├── "advisor"    ──► AdvisorHandler                       │
  │       │                     └── insights-core extract           │
  │       │                                                         │
  │       ├── "compliance" ──► ComplianceHandler                    │
  │       │   "malware"         └── forward metadata                │
  │       │                                                         │
  │       └── "qpc"        ──► QPCHandler                           │
  │                              ├── validate QPC message + URL     │
  │                              ├── download & extract tar         │
  │                              ├── iterate slices + hosts         │
  │                              └── modifier pipeline (11 classes) │
  │                                                                 │
  │  Shared infrastructure:                                         │
  │    mq/auth.py      Kafka SASL/SSL config (one place)            │
  │    mq/produce.py   send_message + delivery callback             │
  │    mq/msgs.py      Message builders                             │
  │    exceptions.py   Typed error hierarchy                        │
  └─────────────────────┬───────────────────────────────────────────┘
                        │
          ┌─────────────┼─────────────┐
          ▼             ▼             ▼
    host-ingress   payload-status  upload.validation
```

### Key Architectural Decisions

| Decision | What | Why |
| -------- | ---- | --- |
| **Handler dispatch pattern** | Each service type gets a handler class | Replaces 314-line monolithic `handle_message()`. Isolates QPC from advisor path. Extensible for future services |
| **Adopt yuptoo's `kafka_auth_config()`** | Shared Kafka SASL/SSL helper in `mq/auth.py` | Puptoo currently duplicates auth config between consumer and producer |
| **Move `send_message()` to `mq/produce.py`** | Encapsulate Kafka production in the produce module | Currently embedded in `app.py` alongside unrelated logic |
| **Typed exception hierarchy** | `FailDownloadException`, `QPCKafkaMsgException`, etc. | Replaces bare `Exception` everywhere. Enables granular metrics and error routing |
| **Pre-register modifiers at startup** | Import and instantiate modifier classes once, not per-host | Yuptoo's current pattern causes O(hosts x modifiers) import overhead. Catastrophic for 10K-host QPC slices |
| **Keep puptoo's commit-after-processing** | Commit Kafka offset in `finally` block, after processing | Yuptoo commits before processing (at-most-once). Crash during `process_report()` loses the message |
| **Keep puptoo's hard exit on poll errors** | `os._exit()` on MAXPOLL/session timeout | Forces pod recreation. Yuptoo's `continue` can spin a broken consumer indefinitely |
| **Migrate to `uv`** | Replace Poetry (puptoo) and Pipfile (yuptoo) with `uv` | Team-preferred tooling. PEP 621 standard metadata. Yuptoo has an upstream `pipenv_to_uv` branch in progress; the merged service will inherit that work where possible |

---

## What Improves (Beyond the Merge Itself)

The merge is an opportunity to fix 12 known bugs I identified across both codebases rather than carrying them forward.

### Puptoo Bugs Fixed

| Bug | Impact | Fix |
| --- | ------ | --- |
| `delivery_report()` has swapped format args | Misleading error logs in production | Correct arg order |
| `handle_retries()` exception never interpolates `request_id` | Exception message is a tuple, not a string | Use f-string |
| `clean_macs()` dead code path | Unreachable code, confusing to readers | Remove |
| Bare `except:` in three files | Silently swallows all errors including `KeyboardInterrupt` | Replace with specific types |
| Three different boolean parsing patterns in `config.py` | Inconsistent behavior across config vars | Standardize |
| `CONSUMER_ASSIGNMENTS` metric defined but never populated | Dead metric | Remove |

### Yuptoo Bugs Fixed (During Port)

| Bug | Impact | Fix |
| --- | ------ | --- |
| Commits before processing | At-most-once: crash loses message | Commit after processing |
| Per-host `importlib`/`inspect` in modifier loop | O(hosts x modifiers) import overhead | Pre-register at startup |
| No modifier ordering guarantee | `AddHostFacts` can run before UUID assignment | Explicit ordered list |
| `Modifier` ABC signature mismatch | Abstract `run(self)` vs actual `run(self, host, obj, **kwargs)` | Correct the ABC |
| Per-host validation message to storage broker | 10K validation messages for a 10K-host slice | One per report |
| `download_report()` has no timeout | Request can hang indefinitely | Add `timeout=120` |

---

## Implementation Plan

### Sprint Overview

| Sprint | Focus | Story Points | Gate |
| ------ | ----- | ------------ | ---- |
| 1 | Refactor puptoo: handler dispatch, move send_message, add auth.py, typed exceptions, bug fixes | 27 | All existing tests pass. Ephemeral verification |
| 2-3 | Port QPC processing: modifiers (with pre-registration), validators, report processor, QPCHandler, tests, uv migration | 30 | All ~130 tests pass. QPC verified in ephemeral |
| 4 | Deploy to stage/prod, decommission yuptoo, archive repo | 13 | IQE tests pass in stage. Production metrics stable |

### PR Strategy: Bottom-Up by Dependency Layer

Each PR is independently deployable. No PR breaks production if merged in isolation.

**Layer 1: Foundation (no behavior change)**

| PR | Contents | Risk |
| -- | -------- | ---- |
| PR 1 | `exceptions.py`: typed hierarchy (new file, unused) | Zero |
| PR 2 | Config normalization: bool parsing, add `max.poll.interval.ms`, SIGINT, remove dead metric | Minimal |
| PR 3 | Bug fixes: dead code, bare `except:`, MinIO pooling | Low |

**Layer 2: Internal Relocation (same behavior, better structure)**

| PR | Contents | Risk |
| -- | -------- | ---- |
| PR 4 | `mq/auth.py` + wire into consumer/producer. Move `send_message()` to `mq/produce.py` | Low |

**Layer 3: Structural Reshape**

| PR | Contents | Risk |
| -- | -------- | ---- |
| PR 5 | `handlers/` with BaseHandler, AdvisorHandler, ComplianceHandler | Medium |
| PR 6 | Swap main loop to handler dispatch + dispatch tests | Medium |
| PR 7 | Ephemeral verification | N/A |

**Layer 4: QPC Port (Sprint 2-3)**

| PR | Contents | Risk |
| -- | -------- | ---- |
| PR 8 | `uv` migration (do first, independent) | Low |
| PR 9 | QPC config + metrics (additive) | Zero |
| PR 10 | Modifier framework + 11 ported modifier classes | Low |
| PR 11 | QPC validators + report processor (with fixes) | Medium |
| PR 12 | QPCHandler + exception wiring + dispatch registration | Medium |
| PR 13 | Port yuptoo test suite (~63 tests) | Low |
| PR 14 | Ephemeral QPC verification | N/A |

### What Stays Untouched

| Component | Status |
| --------- | ------ |
| `process/` directory (insights-core extraction, `profile.py`) | Unchanged |
| `system_profile` rule (~1100 lines) | Unchanged |
| All 37 profile extraction test files | Unchanged |
| Advisor processing logic | Extracted into handler, logic identical |
| Compliance/malware forwarding logic | Extracted into handler, logic identical |
| Redis retry mechanism | Unchanged |
| S3 yum_updates upload | Unchanged (bare `except:` fixed) |

---

## Deployment and Rollback

### Cutover Timeline

All code is merged and tested in ephemeral before this phase begins. The cutover itself is a sequence of deployment gates, not development work.

| Step | Action | Timeline | Gate to proceed |
| ---- | ------ | -------- | --------------- |
| 1 | Deploy merged puptoo to **stage** | Stage deployment day | Deployment succeeds |
| 2 | Run IQE tests (both `puptoo` and `foreman-rh-cloud` plugins) | Stage +1-2 days | Both IQE suites pass |
| 3 | Verify advisor/compliance/malware metrics match baseline | Stage +1-2 days | No regression in error rates or processing latency |
| 4 | Send QPC test payloads, verify hosts appear in HBI | Same validation window | QPC end-to-end confirmed |
| 5 | Deploy merged puptoo to **production** | After stage validation (approx. week 2) | Deployment succeeds |
| 6 | Monitor production metrics for all service types | Prod +1-2 days | Error rates stable, QPC hosts ingested |
| 7 | Scale yuptoo replicas to **0** | After prod stability confirmed | No increase in errors after yuptoo stops |
| 8 | Monitor `qpc-group` consumer lag | Grace period: 1-2 weeks | Lag remains at zero (confirms no traffic routed to old group) |
| 9 | Remove yuptoo ClowdApp from app-interface | After grace period | Sign-off from team |
| 10 | Archive yuptoo repository | Same milestone | README updated with redirect |

**Total cutover window:** approximately 3-4 weeks from stage deployment to repository archival. Steps 1-4 (stage validation) take roughly one week. Steps 5-7 (production) take 2-3 days. Steps 8-10 (grace period) take 1-2 weeks. All timelines are milestone-driven: we do not advance until the gate criteria are met.

### Rollback

Rollback is clean because QPC support is purely additive:

1. Revert puptoo to the pre-merge version. The `qpc` handler simply won't match. QPC messages pass through unconsumed.
2. Re-deploy yuptoo from the archived config.
3. Both services return to independent operation within minutes.

Both consumer groups (`insights-puptoo` and `qpc-group`) can run simultaneously during any transition period.

---

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
| ---- | ----------- | ------ | ---------- |
| Regression in advisor/compliance/malware | Low | High | Handler extraction tested in isolation. 67 existing puptoo tests provide coverage. Verified in ephemeral before stage |
| QPC processing fails in merged service | Medium | Medium | Yuptoo remains deployed during testing. Full yuptoo test suite (63 tests) ported and passing before merge |
| Consumer group transition drops QPC messages | Low | Medium | Both consumer groups run simultaneously during cutover. No messages are lost |
| Performance impact from QPC's large tars | Low | Medium | `max.poll.interval.ms` (600s) prevents consumer timeout. QPC uses same pod resources |
| Modifier behavior differs after porting | Low | Low | All 11 modifier tests ported with original test data. Per-host output verified |
| `insights-core` version conflict | Very Low | Low | Both use ~3.7.x. Merged service uses puptoo's 3.7.6 (newer and compatible) |

---

## Open Questions for Discussion

1. **IQE plugin configuration:** Can a single ClowdApp specify both `puptoo` and `foreman-rh-cloud` IQE plugins? If not, what is the preferred approach?

2. **QPC metric naming:** Should ported QPC metrics keep yuptoo's original names (e.g., `archive_downloaded_success`) or be prefixed with `puptoo_qpc_` to avoid dashboard confusion during transition?

3. **Consumer group migration:** When merged puptoo starts consuming `qpc` messages, the `qpc-group` will see lag increase (yuptoo is still running). Preferred approach: stop yuptoo first, or let both consume simultaneously until confidence is established?

4. **Resource limits:** Puptoo runs at 100m CPU / 256Mi memory; yuptoo runs at 500m / 1Gi. Combined workload may need a resource bump, especially for QPC's tar processing. Suggested starting point?

5. **Modifier ordering:** Yuptoo's `pkgutil.walk_packages` returns filesystem order, which is not deterministic. I propose an explicit ordered list. Does the team have a preferred ordering, or is the current implicit order acceptable as the baseline?

6. **Repository ownership:** After merge, does the `yuptoo` repository stay under `RedHatInsights` as archived, or is there a different archival process?

---

## Supporting Documentation

Detailed analysis backing this proposal:

- **[Puptoo vs Yuptoo Comparison](Puptoo_Yuptoo_Comparison.md)**: 16-section side-by-side comparison of both codebases
- **[Merge Strategy Evaluation](Puptoo_Yuptoo_Merge_Strategy_Evaluation.md)**: Three strategies evaluated with weighted scoring
- **[Architecture Recommendation](Puptoo_Yuptoo_Merge_Recommendation.md)**: Full architecture recommendation with module layout, migration plan, and testing strategy
- **[Implementation Tasks](Puptoo_Yuptoo_Merge_Tasks.md)**: 24 JIRA-sized tasks across 4 sprints with acceptance criteria and dependency graph
