# Unified Upload Processor: Architecture Proposal

**Author:** Pranav Lawate
**Date:** June 2026
**Audience:** Insights Foundry leadership, team leads, stakeholders

---

## 1. What Is: The Current Architecture

### Two Services, One Job

Today, two separate microservices process upload payloads for Host-Based Inventory (HBI):

| Service | Purpose | Replicas | Maintainers |
| ------- | ------- | -------- | ----------- |
| **insights-puptoo** | Processes advisor, compliance, and malware-detection uploads | 8 | Insights Foundry |
| **yuptoo** | Processes QPC (Quipucords) uploads | 1 | Insights Foundry |

Both services perform the same fundamental job:
1. Consume a message from the `platform.upload.announce` Kafka topic
2. Route by `service` header
3. Transform the payload into HBI-compatible host data
4. Produce the result to `host-ingress` for Host Inventory

They share the same Kafka input topic, the same three output topics, and the same downstream consumer (HBI). The only difference is *which* service header they match and *how* they transform the payload.

### The Cost of Running Two

| Area | Impact |
| ---- | ------ |
| **Infrastructure** | Two ClowdApp manifests, two CI/CD pipelines, two Konflux configs, two consumer groups on the same topic |
| **Monitoring** | Two dashboards, two alert sets, two pager rotation entries |
| **On-call burden** | Engineers must context-switch between two codebases for the same conceptual function |
| **Dependency drift** | Two lockfiles with diverging versions of shared packages (confluent-kafka, insights-core) |
| **Knowledge silos** | Improvements in one codebase are not shared with the other. Yuptoo has superior Kafka auth config that puptoo duplicates inline. Puptoo has safer commit semantics that yuptoo lacks |

### Architecture Diagram: Current State

See [`docs/diagrams/component_diagram.md`](diagrams/component_diagram.md) for the full As-Is Mermaid diagram showing both services, their separate consumer groups, dashboards, and CI/CD pipelines.

---

## 2. What's New: The Unified Architecture

### One Service, All Upload Types

I propose merging yuptoo into insights-puptoo via a **handler dispatch pattern**, where each upload type (advisor, compliance, malware, qpc) is processed by a dedicated handler class, all running within a single service.

```
  platform.upload.announce
            │
            ▼
    ┌─────────────────────────────────┐
    │     Unified Upload Processor     │
    │                                 │
    │   service header → get_handler()│
    │       ├── "advisor"    → AdvisorHandler
    │       ├── "compliance" → ComplianceHandler
    │       ├── "malware"    → ComplianceHandler
    │       └── "qpc"        → QPCHandler
    │                                 │
    │   Shared: auth, produce, retry  │
    └────────────┬────────────────────┘
                 │
       ┌─────────┼──────────┐
       ▼         ▼          ▼
  host-ingress  payload   validation
                status
```

### Key Improvements Beyond the Merge

This is not a naive code port. I am adopting the best patterns from each codebase and fixing 12 known bugs in both:

| Improvement | Source | Impact |
| ----------- | ------ | ------ |
| Handler dispatch pattern | New architecture | Replaces 314-line monolithic function. Each handler is independently testable and deployable |
| DRY Kafka auth config | Adopted from yuptoo | Eliminates duplicated SASL/SSL config between consumer and producer |
| Typed exception hierarchy | New | Replaces bare `Exception` everywhere. Enables granular error metrics and alerting |
| Modifier pre-registration | Fix to yuptoo | Eliminates O(hosts x modifiers) import overhead. Critical for QPC slices with 10K+ hosts |
| At-least-once commit semantics | Kept from puptoo | Fixes yuptoo's commit-before-processing bug that loses messages on crash |
| 7 puptoo bug fixes | Identified during analysis | Swapped format args, dead code, bare except blocks, inconsistent config parsing |
| 5 yuptoo bug fixes | Identified during analysis | Missing timeouts, per-host validation spam, modifier ordering, ABC signature mismatch |
| `uv` migration | Team preference | Replaces Poetry and Pipfile with modern PEP 621 standard tooling |

### Architecture Diagrams

Full visual documentation has been created:

| Diagram | Description | Location |
| ------- | ----------- | -------- |
| Component (As-Is / To-Be) | Side-by-side service architecture | [`component_diagram.md`](diagrams/component_diagram.md) |
| Data Flow | Message lifecycle for advisor and QPC paths | [`data_flow_diagram.md`](diagrams/data_flow_diagram.md) |
| UML Class | Handler and modifier class hierarchies | [`class_diagram.md`](diagrams/class_diagram.md) |
| Sequence | Step-by-step processing for advisor and QPC | [`sequence_diagram.md`](diagrams/sequence_diagram.md) |

### Proof of Concept

A working POC demonstrating the core architectural patterns is available in [`src/puptoo/`](../src/puptoo/). It implements:

- **Handler dispatch**: `get_handler("advisor")` returns the correct handler instance; unknown services return `None`
- **Modifier pre-registration**: modifiers are imported and instantiated once at startup, not per-host
- **Typed exception hierarchy**: `PuptooError` base with specific subclasses for each failure mode
- **DRY Kafka auth**: single `kafka_auth_config()` function for all Kafka connections

**14 passing tests** validate handler routing, modifier behaviour, and exception hierarchy. Run with:

```bash
PYTHONPATH=src pytest tests/ -v
```

---

## 3. Why This Change

### Benefits to the Organization

| Benefit | Description | Impact |
| ------- | ----------- | ------ |
| **Reduced operational overhead** | One deployment, one dashboard, one pager entry instead of two | Directly reduces on-call burden and context-switching |
| **Improved reliability** | 12 bug fixes shipped as part of the merge; at-least-once semantics for all message types | Fewer silent failures, fewer lost messages |
| **Better architecture** | Handler dispatch pattern is extensible: adding a new upload type means adding one handler class | Future services (e.g., new scan types) require no structural changes |
| **Unified dependency management** | One lockfile, one `uv` project, one CI matrix | Eliminates version drift between the two codebases |
| **Knowledge consolidation** | All upload processing knowledge in one repo, one team, one set of docs | Lowers the bus factor; new team members learn one codebase |
| **Resource efficiency** | One service with 8 replicas handles all traffic vs. 8 + 1 replicas across two services | Slight resource savings; eliminates yuptoo's dedicated pod |

### What Does NOT Change

To be explicit about scope:

- The `process/` directory (insights-core extraction, all 37 profile test files) is **untouched**
- The `system_profile` rule (~1100 lines) is **untouched**
- Advisor, compliance, and malware processing logic is **extracted into handlers with identical logic**
- Redis retry mechanism is **unchanged**
- S3 yum_updates upload is **unchanged**

### Risk Assessment Summary

| Risk | Probability | Mitigation |
| ---- | ----------- | ---------- |
| Regression in existing (advisor/compliance/malware) processing | Low | Handler extraction is tested in isolation; 67 existing tests provide coverage; verified in ephemeral before stage |
| QPC processing fails in merged service | Medium | Yuptoo stays deployed during cutover; 63 yuptoo tests ported and passing before merge |
| Consumer group transition drops QPC messages | Low | Both consumer groups run simultaneously during cutover |

### Effort and Timeline

| Sprint | Focus | Story Points |
| ------ | ----- | ------------ |
| 1 | Refactor puptoo infrastructure (handler dispatch, auth, exceptions, bug fixes) | 27 |
| 2-3 | Port QPC processing (modifiers, validators, handler, tests, uv migration) | 30 |
| 4 | Stage/prod deployment, yuptoo decommission | 13 |
| **Total** | | **70 points** |

**Rollback is clean:** revert puptoo, re-deploy yuptoo. Both consumer groups can run simultaneously during any transition.

---

## 4. What I Need

### Personnel

| Role | Who (Proposed) | Why | Duration |
| ---- | -------------- | --- | -------- |
| **Puptoo domain expert** | Sourabh (or designated maintainer) | Code review for Sprint 1 handler extraction. Guidance on insights-core integration points and edge cases. IQE test setup and verification | Sprint 1-2 (review), Sprint 4 (IQE) |
| **QPC/yuptoo expert** | Current yuptoo owner | Validate modifier porting accuracy. Confirm QPC-specific Kafka message structure. Review QPCHandler against production edge cases | Sprint 2-3 |
| **Platform engineer** | App-interface maintainer | ClowdApp manifest updates. Consumer group migration. Konflux pipeline consolidation | Sprint 4 |

### Access and Permissions

| Resource | Purpose |
| -------- | ------- |
| Ephemeral environment (Bonfire) | Deploy and test merged service in isolation |
| Stage environment deployment rights | Deploy for IQE testing (Sprint 4) |
| Prometheus/Grafana for puptoo and yuptoo | Baseline current metrics for comparison |
| yuptoo repository write access | Port tests, reference during implementation |

### Time Allocation

I estimate this requires approximately 60-70% of my sprint capacity for Sprints 1-3, dropping to 30-40% for Sprint 4 (deployment is largely gate-based waiting). Reviewer time needed is approximately 4-6 hours per sprint.

---

## 5. Delegation and Enablement Plan

### Philosophy

This merge is an opportunity to **enable others** on the team and **improve the product** simultaneously. Rather than executing everything in isolation, I plan to delegate specific work streams that build team capability.

### Delegation Matrix

| Work Stream | Owner | Delegated To | What They Gain |
| ----------- | ----- | ------------ | -------------- |
| **Architecture documentation** | Pranav | (Self) | Drives the design and owns the narrative |
| **Handler extraction (Sprint 1)** | Pranav | Peer reviewer (Sourabh) | Reviewer gains deep understanding of puptoo internals and the handler pattern |
| **Modifier porting (Sprint 2)** | Pranav | Junior team member (pair programming) | Learn modifier pattern, gain confidence with QPC codebase, contribute directly to a production merge |
| **Test suite porting (Sprint 2-3)** | Delegated | Team member familiar with pytest | Straightforward porting work that builds familiarity with both codebases. Good first contribution |
| **Dashboard consolidation (Sprint 4)** | Delegated | SRE/platform team member | Gains ownership of unified monitoring. Learn the metrics landscape |
| **IQE test configuration (Sprint 4)** | Pranav + Sourabh | (Collaborative) | Knowledge transfer on IQE patterns |
| **Yuptoo archival process** | Delegated | Team member | Learn app-interface and repository lifecycle |

### How This Enables Others

1. **Pair programming on modifier porting** gives a junior engineer hands-on experience with both codebases, the ABC pattern, and the modifier pipeline. This is well-scoped, testable work with clear acceptance criteria.

2. **Delegating test porting** is a low-risk task that builds familiarity with the codebase. The ported tests must pass identically, so the success criteria are unambiguous.

3. **Dashboard consolidation** gives an SRE-oriented team member ownership of the unified monitoring story. They decide how metrics are presented and alerted on.

4. **Code reviews on every PR** ensure at least two people understand each layer of the merged service. No single point of failure in knowledge.

### Checkpoints

| Checkpoint | When | Purpose |
| ---------- | ---- | ------- |
| Architecture review | Before Sprint 1 | Validate approach with team. This presentation |
| Sprint 1 demo | End of Sprint 1 | Show handler dispatch working with existing tests passing. Invite feedback |
| QPC integration review | Mid Sprint 2 | Walk through modifier porting with yuptoo expert. Validate accuracy |
| Pre-deploy review | End of Sprint 3 | Full test suite green. Ephemeral verified. Team sign-off before stage |
| Post-deploy retrospective | Sprint 4 + 1 week | Lessons learned. Update runbooks. Close out |

---

## Supporting Materials

| Document | Description |
| -------- | ----------- |
| [Merge Proposal (Engineering)](Puptoo_Yuptoo_Merge_Proposal.md) | Detailed engineering proposal with cutover timeline |
| [Codebase Comparison](Puptoo_Yuptoo_Comparison.md) | 16-section side-by-side analysis |
| [Strategy Evaluation](Puptoo_Yuptoo_Merge_Strategy_Evaluation.md) | Weighted scoring of three strategies + A+ |
| [Architecture Recommendation](Puptoo_Yuptoo_Merge_Recommendation.md) | Full module layout and migration plan |
| [Implementation Tasks](Puptoo_Yuptoo_Merge_Tasks.md) | 24 JIRA-sized tasks with acceptance criteria |
| [Architecture Diagrams](diagrams/) | Component, data flow, class, and sequence diagrams |
| [POC Code](../src/puptoo/) | Working skeleton: handler dispatch, modifiers, exceptions, auth |
