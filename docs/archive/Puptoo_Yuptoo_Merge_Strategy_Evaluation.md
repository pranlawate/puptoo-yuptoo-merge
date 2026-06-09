# Puptoo-Yuptoo Merge Strategy Evaluation

> Evaluation of three merge strategies based on the [Comparison](Puptoo_Yuptoo_Comparison.md) analysis. Each option is assessed across seven dimensions: effort, risk, architecture quality, operational impact, testing, team familiarity, and long-term maintainability.

---

## Strategy A: Merge Yuptoo into Puptoo

### Concept

Puptoo already routes by service header (`advisor`, `compliance`, `malware-detection`). Add `qpc` as a fourth service type. Port yuptoo's modifier system and QPC-specific processing into puptoo's codebase.

### What Moves

1. **QPC processing pipeline** (`yuptoo/processor/report_processor.py`): tar extraction, metadata validation, slice processing, multi-host iteration
2. **Modifier plugin system** (`yuptoo/modifiers/` directory): 11 modifier classes + the `pkgutil` discovery mechanism
3. **Validators** (`yuptoo/validators/`): `qpc_message_validator.py` (URL expiry check) and `report_metadata_validator.py`
4. **Config additions**: `MAX_HOSTS_PER_REP`, `HOSTS_TRANSFORMATION_ENABLED`, `DISCOVERY_HOST_TTL`, `SATELLITE_HOST_TTL`, `KAFKA_PRODUCER_OVERRIDE_MAX_REQUEST_SIZE`, `BYPASS_PAYLOAD_EXPIRATION`, `KAFKA_CONSUMER_MAXPOLL_INTERVAL`
5. **Helper utilities**: `download_report()`, `has_canonical_facts()`, `print_transformed_info()`, `Modifier` ABC
6. **Yuptoo-specific metrics**: `archive_downloaded_success`, `archive_failed_to_download`, `incoming_hosts_counter`, etc.

### Pros

| Advantage                             | Detail                                                                                                                                                               |
| ------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Natural routing extension**         | Puptoo's main loop already branches on `service` header. Adding `qpc` is a single `elif` clause.                                                                     |
| **Battle-tested infrastructure**      | Puptoo runs 8 replicas in prod, has health probes, Haberdasher logging, Redis retry, and S3 upload. Proven at scale.                                                 |
| **Preserves deployment history**      | Git history, CI/CD pipeline, Konflux configuration, monitoring dashboards, and alerting rules all stay intact. No migration of operational tooling.                   |
| **Lower risk to existing services**   | The advisor/compliance/malware path is untouched. QPC processing is isolated in new modules.                                                                         |
| **Simpler deployment cutover**        | One service to deploy, one to decommission. The new puptoo version can be tested alongside the existing yuptoo before the yuptoo consumer group is retired.          |
| **Single consumer group**             | Both workloads share partition assignments, reducing overall Kafka resource usage.                                                                                    |
| **Fewer operational surfaces**        | One ClowdApp, one set of dashboards, one pager rotation, one deployment pipeline.                                                                                    |

### Cons

| Disadvantage                               | Detail                                                                                                                                        | Mitigation                                                                     |
| ------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------- |
| **`app.py` is already 314 lines**          | Adding QPC routing and processing increases the main loop complexity.                                                                         | Refactor `handle_message()` into per-service handler modules. This is due regardless. |
| **Monolithic architecture**                | Puptoo lacks yuptoo's clean modifier pattern. The `handle_message()` function mixes routing, extraction, post-processing, and output.         | Introduce handler interface as part of the merge. Each service gets a handler class. |
| **Consumer group change for QPC**          | YUptoo currently uses `qpc-group`. After merge, QPC messages are consumed by `insights-puptoo`. Requires coordinated cutover.                 | Deploy merged puptoo first, verify it processes QPC messages, then decommission yuptoo. |
| **No max poll interval config in puptoo**  | QPC processing is slow (multi-host, large tars). Puptoo's consumer lacks `max.poll.interval.ms` override.                                     | Add the config variable. Trivial change.                                        |
| **Different IQE test plugins**             | Puptoo uses `puptoo` IQE plugin; yuptoo uses `foreman-rh-cloud`. Merged service needs both.                                                  | Add both IQE plugins to ClowdApp spec.                                          |

### Effort Estimate

| Work Item                         | Size  |
| --------------------------------- | ----- |
| Add `qpc` routing in main loop    | Small |
| Port modifier system              | Medium |
| Port validators                   | Small |
| Port QPC processor                | Medium |
| Add config variables              | Small |
| Add yuptoo metrics                | Small |
| Refactor handler pattern          | Medium |
| Update ClowdApp manifest          | Small |
| Port yuptoo tests                 | Medium |
| IQE test integration              | Small |
| **Total**                         | **~3 sprints** |

---

## Strategy B: Merge Puptoo into Yuptoo

### Concept

Yuptoo has cleaner architecture: pluggable modifiers, separated concerns, well-defined processor pipeline. Make yuptoo the surviving service and port puptoo's insights-core extraction into it.

### What Moves

1. **Insights-core extraction** (`src/puptoo/process/`): archive unpacking, `get_system_profile()`, the 1100-line `profile.py`, `postprocess()`
2. **Canonical fact validation** (`validators.py`): puptoo's stricter validation (provider pair rule)
3. **Redis retry system**: `handle_retries()`, Redis client config
4. **S3 upload**: MinIO client for `yum_updates`
5. **Message builders** (`msgs.py`): puptoo-style `inv_message()`, `tracker_message()`, `validation_message()`
6. **Extensive metrics**: Summaries, Histograms, per-topic/per-service counters
7. **Health probes config**: HTTP `/metrics` endpoint for liveness/readiness
8. **Haberdasher logging**: 5 env vars for logging pipeline

### Pros

| Advantage                            | Detail                                                                                                          |
| ------------------------------------ | ---------------------------------------------------------------------------------------------------------------- |
| **Cleaner architecture**             | Modifier plugin system is extensible. New transformations are added by dropping a class file in `modifiers/`.     |
| **Better separation of concerns**    | Config, logging, metrics, validation, and processing are in separate modules. Producer encapsulates `send_message()`. |
| **Kafka auth is DRY**                | `kafka_auth_config()` helper is used by both consumer and producer. Puptoo duplicates auth logic.                |

### Cons

| Disadvantage                                   | Detail                                                                                                              | Mitigation                                              |
| ---------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------- |
| **Massive porting effort**                     | The `system_profile` rule alone is 1100 lines. The entire insights-core extraction pipeline must be ported.           | Possible but high-effort.                               |
| **Yuptoo is not designed for insights archives**| It processes pre-structured JSON. insights-core extraction is a fundamentally different paradigm.                     | Would need a new processor class, not a modifier.       |
| **Less battle-tested**                         | 1 replica in prod vs 8. No health probes. No Redis. No S3.                                                           | All must be added.                                      |
| **Consumer group disruption**                  | Puptoo's `insights-puptoo` group processes the vast majority of traffic. Retiring it is higher risk than retiring `qpc-group`. | Requires careful rollover.                              |
| **Operational tooling migration**              | Dashboards, alerts, runbooks, and team knowledge all reference `puptoo`. Everything must be migrated to `yuptoo`.     | High effort, error-prone.                               |
| **Naming confusion**                           | The surviving service would be named "yuptoo" but processing advisor/compliance/malware traffic. Team confusion.      | Rename the service, but that's more operational churn.  |
| **Git history disruption**                     | All puptoo git history (the larger, more active codebase) is lost or requires complex git merge.                      | Tolerable but unpleasant.                               |

### Effort Estimate

| Work Item                              | Size   |
| -------------------------------------- | ------ |
| Port insights-core extraction pipeline | Large  |
| Port system_profile rule               | Small (file copy) |
| Port Redis retry system                | Medium |
| Port S3 upload                         | Small  |
| Port puptoo message builders           | Small  |
| Port puptoo metrics (extensive)        | Medium |
| Add health probes                      | Small  |
| Add Haberdasher logging                | Small  |
| Update ClowdApp for 8+ replicas        | Small  |
| Port puptoo tests (67 tests)           | Large  |
| Migrate dashboards/alerts              | Medium |
| **Total**                              | **~5 sprints** |

---

## Strategy C: New Unified Service

### Concept

Create a brand-new service (e.g., `insights-ingress-processor`) cherry-picking the best patterns from both: yuptoo's modifier plugin architecture for extensible host transformation + puptoo's proven infrastructure (Redis, S3, health probes).

### What Moves

Everything. Both codebases are sources, nothing is the destination.

### Pros

| Advantage                            | Detail                                                                                          |
| ------------------------------------ | ------------------------------------------------------------------------------------------------ |
| **Clean architecture from scratch**  | No legacy cruft. Design the ideal module layout, naming, and patterns.                           |
| **Best of both worlds**              | Yuptoo's modifier system + puptoo's operational maturity + modern Python practices.              |
| **Fresh dependency management**      | Unified on `uv` (team-preferred tooling), consistent pinning, no legacy lockfile conflicts.      |
| **No naming baggage**                | A neutral name avoids confusion about which service was the "winner."                            |

### Cons

| Disadvantage                                    | Detail                                                                                                      | Mitigation                                |
| ----------------------------------------------- | ------------------------------------------------------------------------------------------------------------ | ------------------------------------------ |
| **Maximum effort**                              | Every line of code is a rewrite or deliberate port. Both test suites must be adapted.                         | Unavoidable.                               |
| **Maximum risk**                                | No existing deployment, no operational history, no proven CI/CD pipeline. All greenfield risk.                | Mitigated by thorough testing, but still highest risk. |
| **All operational tooling from scratch**         | Dashboards, alerts, runbooks, Konflux pipeline, app-interface manifests, namespace config, RBAC.              | Significant ops work.                      |
| **Double the cutover complexity**               | Must decommission both puptoo and yuptoo simultaneously, routing all traffic to the new service.             | Phased rollout possible but complex.       |
| **Git history loss for both**                   | Neither codebase's git history is preserved.                                                                  | Tolerable but loses debugging context.     |
| **Team learning curve**                         | Everyone must learn the new codebase structure, even for functionality they previously maintained.             | Documentation helps but doesn't eliminate. |

### Effort Estimate

| Work Item                                | Size   |
| ---------------------------------------- | ------ |
| Design and scaffold new service          | Medium |
| Implement unified main loop              | Medium |
| Port insights-core extraction            | Large  |
| Port QPC processing                      | Medium |
| Implement modifier plugin system         | Medium |
| Port and unify configuration             | Medium |
| Port and unify metrics                   | Medium |
| Port and unify logging                   | Small  |
| Implement Redis, S3, health probes       | Medium |
| Port and unify all tests (~130)          | Large  |
| Create CI/CD pipeline                    | Medium |
| Create ClowdApp and deployment config    | Medium |
| Dashboards, alerts, runbooks from scratch| Large  |
| **Total**                                | **~8 sprints** |

---

## Comparative Summary

| Dimension                  | A: yuptoo into puptoo      | B: puptoo into yuptoo       | C: New service               |
| -------------------------- | -------------------------- | ---------------------------- | ----------------------------- |
| **Effort**                 | ~3 sprints                 | ~5 sprints                   | ~8 sprints                    |
| **Risk to existing users** | Low (advisor path untouched)| High (majority traffic moves)| High (both paths rewritten)   |
| **Architecture quality**   | Medium (needs refactoring) | High (modifier system native)| Highest (clean-room design)   |
| **Operational continuity** | High (puptoo infra intact) | Low (all ops migrate)        | None (all new)                |
| **Testing confidence**     | High (puptoo tests stay)   | Medium (tests must be ported)| Low (all tests rewritten)     |
| **Naming / identity**      | Natural (puptoo gains QPC) | Confusing (yuptoo runs advisor)| Clean (new neutral name)    |
| **Git history**            | Preserved for puptoo       | Preserved for yuptoo only    | Lost for both                 |
| **Deployment cutover**     | Simple (one decommission)  | Complex (majority traffic)   | Most complex (two decommissions)|
| **Long-term maintenance**  | Good (with refactoring)    | Good (modifier system)       | Best (ideal design)           |
| **Kafka consumer groups**  | One group (merge traffic)  | One group (merge traffic)    | One group (new)               |

---

## Scoring Matrix (1-5, higher is better)

| Criterion              | Weight | A: into puptoo | B: into yuptoo | C: new service |
| ---------------------- | ------ | -------------- | -------------- | -------------- |
| Low effort             | 3      | 5              | 3              | 1              |
| Low risk               | 5      | 5              | 2              | 2              |
| Architecture quality   | 3      | 3              | 4              | 5              |
| Operational continuity | 4      | 5              | 2              | 1              |
| Test confidence        | 4      | 5              | 3              | 2              |
| Long-term maintenance  | 3      | 3              | 4              | 5              |
| **Weighted total**     |        | **97**         | **62**         | **51**         |

> Calculation: each score multiplied by weight, summed.
> A = (5x3)+(5x5)+(3x3)+(5x4)+(5x4)+(3x3) = 15+25+9+20+20+9 = **98**
> B = (3x3)+(2x5)+(4x3)+(2x4)+(3x4)+(4x3) = 9+10+12+8+12+12 = **63**
> C = (1x3)+(2x5)+(5x3)+(1x4)+(2x4)+(5x3) = 3+10+15+4+8+15 = **55**

---

## Strategy A+: Best-of-Both Refinement

### Concept

Strategy A remains the base (merge yuptoo into puptoo), but rather than a naive port, the merge actively adopts yuptoo's superior architectural patterns and fixes known bugs in both codebases. The result is a unified service that is genuinely better than either predecessor.

### What A+ Adds Over Plain A

| Enhancement                        | Source | What changes                                                                   |
| ---------------------------------- | ------ | ------------------------------------------------------------------------------- |
| `mq/auth.py` shared helper        | Yuptoo | Eliminate duplicated SASL/SSL blocks in consumer + producer                     |
| `send_message()` in `mq/produce.py`| Yuptoo | Move out of 314-line `app.py`; encapsulate delivery callbacks + key selection   |
| Typed exception hierarchy          | Yuptoo | Replace bare `Exception` with `FailDownloadException`, `FailExtractException`, etc. |
| Pre-registered modifier pipeline   | Yuptoo (fixed) | Fix per-host `importlib`/`inspect` overhead; add explicit ordering         |
| Correct `Modifier` ABC signature   | Yuptoo (fixed) | `run(host, transformed_obj, **kwargs)` instead of bare `run(self)`         |
| Per-report validation messages     | Yuptoo (fixed) | One validation message per report, not per host                            |
| Request download timeout           | Yuptoo (fixed) | Add `requests.get(url, timeout=...)` to prevent hangs                      |
| Commit-after-processing for QPC    | Puptoo | Do not adopt yuptoo's at-most-once commit pattern                               |
| Bug fixes in both codebases        | Both   | 12 known bugs fixed as part of the merge (see [Comparison](Puptoo_Yuptoo_Comparison.md))     |
| `uv` dependency management         | Team   | Migrate from Poetry/Pipfile to `uv` with PEP 621 metadata                      |

### Revised Effort Estimate

| Work Item                         | Size  | Change from A |
| --------------------------------- | ----- | ------------- |
| Add `qpc` routing in main loop    | Small | Same          |
| Port modifier system **(with fixes)** | Medium | +1 point (pre-registration, ordering, ABC fix) |
| Port validators                   | Small | Same          |
| Port QPC processor **(with fixes)** | Medium | +1 point (commit semantics, per-report validation) |
| Add config variables              | Small | Same          |
| Add yuptoo metrics                | Small | Same          |
| Refactor handler pattern          | Medium | Same          |
| **NEW: Typed exceptions**         | Small | +2 points     |
| **NEW: Move send_message + auth** | Small | +2 points     |
| **NEW: Bug fixes (both services)**| Medium | +3 points     |
| **NEW: uv migration**             | Small | +2 points (already in plan) |
| Update ClowdApp manifest          | Small | Same          |
| Port yuptoo tests                 | Medium | Same          |
| IQE test integration              | Small | Same          |
| **Total**                         | **~4 sprints** | +1 sprint over vanilla A |

### Revised Scoring

| Criterion              | Weight | A (vanilla) | A+ (refined) | B: into yuptoo | C: new service |
| ---------------------- | ------ | ----------- | ------------ | -------------- | -------------- |
| Low effort             | 3      | 5           | 4            | 3              | 1              |
| Low risk               | 5      | 5           | 5            | 2              | 2              |
| Architecture quality   | 3      | 3           | 5            | 4              | 5              |
| Operational continuity | 4      | 5           | 5            | 2              | 1              |
| Test confidence        | 4      | 5           | 5            | 3              | 2              |
| Long-term maintenance  | 3      | 3           | 5            | 4              | 5              |
| **Weighted total**     |        | **98**      | **106**      | **63**         | **55**         |

> A+ = (4x3)+(5x5)+(5x3)+(5x4)+(5x4)+(5x3) = 12+25+15+20+20+15 = **107**

The extra sprint pays for a significant jump in architecture quality (3 to 5) and long-term maintenance (3 to 5), while preserving the risk and operational advantages of Strategy A.
