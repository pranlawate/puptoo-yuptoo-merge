# Puptoo-Yuptoo Merge: Implementation Tasks

> JIRA-sized tasks for executing Strategy A+ (merge yuptoo into puptoo with best-of-both architectural upgrades) as described in [Architecture Recommendation](Puptoo_Yuptoo_Merge_Recommendation.md). Tasks are grouped by sprint/phase, ordered by dependency, and include acceptance criteria.

---

## Epic: [RHINENG-27899](https://redhat.atlassian.net/browse/RHINENG-27899) — Merge Yuptoo into Puptoo

---

## Sprint 1: Refactor Puptoo + A+ Infrastructure

### Task 1.1: Create BaseHandler ABC and handler registry

**Type:** Story
**Points:** 3
**Description:**
Create a `handlers/` package in `src/puptoo/` with a `BaseHandler` abstract base class and a registry that maps service header values to handler instances.

**Acceptance Criteria:**
- [ ] `src/puptoo/handlers/__init__.py` exists with `get_handler(service: str) -> BaseHandler | None`
- [ ] `src/puptoo/handlers/base.py` defines `BaseHandler` ABC with `process(msg, extra)` and `build_hbi_messages(facts, msg)` abstract methods
- [ ] `get_handler()` returns `None` for unknown service types (no crash)
- [ ] No functional change to puptoo behaviour

---

### Task 1.2: Extract AdvisorHandler from app.py

**Type:** Story
**Points:** 5
**Description:**
Move the advisor-specific logic from `handle_message()` in `app.py` into `handlers/advisor.py`. This includes `process_archive()`, insights-core fact extraction, canonical fact validation, MAC cleaning, owner ID extraction, stale timestamp, S3 upload of yum_updates, and display_name/ansible_host override.

**Acceptance Criteria:**
- [ ] `src/puptoo/handlers/advisor.py` contains `AdvisorHandler(BaseHandler)`
- [ ] `handle_message()` in `app.py` dispatches `advisor` to `AdvisorHandler`
- [ ] All existing `test_app.py` tests pass without modification
- [ ] All existing profile extraction tests pass without modification
- [ ] ROS flags (`is_ros`, `is_ros_v2`, `is_pcp_raw_data_collected`, `is_runtimes`) handled correctly

---

### Task 1.3: Extract ComplianceHandler from app.py

**Type:** Story
**Points:** 2
**Description:**
Move the compliance/malware-detection logic from `handle_message()` into `handlers/compliance.py`. This handler simply forwards `msg["metadata"]` as facts.

**Acceptance Criteria:**
- [ ] `src/puptoo/handlers/compliance.py` contains `ComplianceHandler(BaseHandler)`
- [ ] Both `compliance` and `malware-detection` service types route to `ComplianceHandler`
- [ ] Existing tests pass

---

### Task 1.4: Refactor app.py main loop to use handler dispatch

**Type:** Story
**Points:** 3
**Description:**
Replace the `if service in ['advisor', ...]` chain in `app.py` with a call to `get_handler(service)`. Move tracker messages, validation messages, and error handling into common wrapper logic that calls `handler.process()`.

**Acceptance Criteria:**
- [ ] `app.py` main loop uses `get_handler()` for dispatch
- [ ] `handle_message()` is simplified to common pre/post logic + handler dispatch
- [ ] All existing tests pass
- [ ] `app.py` line count reduced by at least 80 lines

---

### Task 1.5: Create mq/auth.py with kafka_auth_config()

**Type:** Task
**Points:** 2
**Description:**
Create `src/puptoo/mq/auth.py` with a shared `kafka_auth_config(connection_info)` function (adopt yuptoo's `lib/config.py:9-20` pattern). Use it in both `consume.py` and `produce.py` to eliminate duplicated SASL/SSL configuration. Also move cacert writing (`write_cert()` from `app.py`) into this module.

**Acceptance Criteria:**
- [ ] `src/puptoo/mq/auth.py` exists with `kafka_auth_config()` and `write_cert()`
- [ ] Both `consume.init_consumer()` and `produce.init_producer()` use `kafka_auth_config()`
- [ ] Duplicated auth blocks removed from `consume.py` and `produce.py`
- [ ] `write_cert()` removed from `app.py`
- [ ] Kafka auth behaviour unchanged (SASL, cacert handling)

---

### Task 1.6: Move send_message() and delivery_report() to mq/produce.py

**Type:** Story
**Points:** 3
**Description:**
Relocate `send_message()`, `delivery_report()`, and the global `producer` variable from `app.py` to `mq/produce.py` (adopt yuptoo's encapsulation pattern). Fix the swapped format args in `delivery_report()`. Add `message.max.bytes` producer config. Add `send_time` histogram to produce module. Create `tests/test_produce.py`.

**Acceptance Criteria:**
- [ ] `send_message()` and `delivery_report()` live in `mq/produce.py`
- [ ] `delivery_report()` format args corrected: `(topic, request_id, err)`
- [ ] `message.max.bytes` configurable via `KAFKA_PRODUCER_OVERRIDE_MAX_REQUEST_SIZE`
- [ ] `app.py` imports `send_message` from `mq.produce`
- [ ] All existing tests pass
- [ ] New `tests/test_produce.py` covers send + delivery callback

---

### Task 1.7: Create typed exception hierarchy

**Type:** Story
**Points:** 2
**Description:**
Create `src/puptoo/exceptions.py` with a typed exception hierarchy adopted from yuptoo's `lib/exceptions.py`. Add puptoo-specific types. Replace bare `Exception` raises in `app.py` with appropriate typed exceptions. Fix `handle_retries()` exception formatting.

Exception types: `PuptooError` (base), `FailDownloadException`, `FailExtractException`, `QPCKafkaMsgException`, `QPCReportException`, `RetryExhaustedException`.

**Acceptance Criteria:**
- [ ] `src/puptoo/exceptions.py` exists with full hierarchy
- [ ] `handle_retries()` raises `RetryExhaustedException` with f-string formatting
- [ ] Bare `Exception` in `app.py` replaced where appropriate
- [ ] Bare `except:` in `upload.py` and `config.py` replaced with specific types

---

### Task 1.8: Add max.poll.interval.ms and SIGINT config

**Type:** Task
**Points:** 1
**Description:**
Add `KAFKA_CONSUMER_MAXPOLL_INTERVAL` to `config.py` and apply it in `consume.init_consumer()`. Add `SIGINT` handler alongside existing `SIGTERM`. Normalize boolean parsing in `config.py` to use a single convention.

**Acceptance Criteria:**
- [ ] `KAFKA_CONSUMER_MAXPOLL_INTERVAL` in `config.py` with default 600000
- [ ] Applied as `max.poll.interval.ms` in consumer connection info
- [ ] `signal.signal(signal.SIGINT, handle_signal)` added in `app.py`
- [ ] All boolean config vars use `os.getenv(..., "").lower() in ("true", "t", "yes", "y")`
- [ ] Remove unused `CONSUMER_ASSIGNMENTS` Info metric

---

### Task 1.9: Fix puptoo bugs

**Type:** Task
**Points:** 2
**Description:**
Fix remaining known bugs in puptoo as part of the refactoring:
- Remove dead `clean_macs()` code path at `app.py:244-245` (MAC cleaning handled by `postprocess()`)
- Fix bare `except:` in `upload.py` (use `except Exception`)
- Fix bare `except:` in `config.py` Redis password (use `except AttributeError`)
- Pool MinIO client in `upload.py` (module-level instead of per-upload)

**Acceptance Criteria:**
- [ ] Dead `clean_macs()` guard removed
- [ ] No bare `except:` remains in the codebase
- [ ] MinIO client initialized once, not per-upload
- [ ] All existing tests pass

---

### Task 1.10: Write handler dispatch tests

**Type:** Story
**Points:** 2
**Description:**
Add `tests/test_handlers.py` with tests for handler dispatch, ensuring correct handler selection for each service type and graceful handling of unknown services.

**Acceptance Criteria:**
- [ ] Tests verify `advisor` -> `AdvisorHandler`
- [ ] Tests verify `compliance` -> `ComplianceHandler`
- [ ] Tests verify `malware-detection` -> `ComplianceHandler`
- [ ] Tests verify `qpc` -> `None` (not yet registered)
- [ ] Tests verify unknown service -> `None`

---

### Task 1.11: Verify in ephemeral environment

**Type:** Task
**Points:** 2
**Description:**
Deploy the refactored puptoo to a Bonfire ephemeral environment. Run IQE tests and manually verify advisor/compliance/malware uploads process correctly.

**Acceptance Criteria:**
- [ ] IQE `puptoo` plugin tests pass in ephemeral
- [ ] At least one advisor upload processed end-to-end (appears in HBI)
- [ ] No increase in error metrics compared to baseline

---

**Sprint 1 Total:** 27 story points

---

## Sprint 2-3: Port QPC Processing (with A+ Fixes)

### Task 2.1: Create modifier framework with pre-registration

**Type:** Story
**Points:** 5
**Description:**
Create `src/puptoo/modifiers/` as a top-level modifier framework (not nested under `qpc/`, to allow future advisor-path modifiers). Implement pre-registration pattern that imports and instantiates all modifier classes once at startup, fixing yuptoo's per-host `importlib`/`inspect` overhead. Define correct `Modifier` ABC with `run(self, host: dict, transformed_obj: dict, **kwargs)` signature. Port all 11 QPC modifier classes into `modifiers/qpc/`. Define explicit ordering list.

**Files created:**
- `src/puptoo/modifiers/__init__.py` (pre-registration + `get_modifiers()`)
- `src/puptoo/modifiers/base.py` (corrected `Modifier` ABC)
- `src/puptoo/modifiers/qpc/` (11 ported modifier classes)

**Acceptance Criteria:**
- [ ] All 11 modifier classes exist under `src/puptoo/modifiers/qpc/`
- [ ] `Modifier` ABC defines `run(self, host: dict, transformed_obj: dict, **kwargs)`
- [ ] Modifiers pre-registered at startup via `register_modifiers()`, not per-host
- [ ] Ordering is explicit (e.g., `AddHostFacts` runs last after UUID assignment)
- [ ] `get_modifiers()` returns pre-instantiated modifier list
- [ ] All 11 modifier tests pass (ported from yuptoo)

---

### Task 2.2: Port QPC validators

**Type:** Story
**Points:** 3
**Description:**
Port both yuptoo validators into `src/puptoo/qpc/validators.py`. This includes `validate_qpc_message()` (URL expiry check, required field validation) and `validate_metadata_file()` (metadata.json structure, slice validation, host count).

**Acceptance Criteria:**
- [ ] `src/puptoo/qpc/validators.py` contains both `validate_qpc_message()` and `validate_metadata_file()`
- [ ] URL expiry check preserved with `BYPASS_PAYLOAD_EXPIRATION` config
- [ ] All validator tests pass (ported from yuptoo)

---

### Task 2.3: Port QPC report processor (with fixes)

**Type:** Story
**Points:** 5
**Description:**
Port `yuptoo/processor/report_processor.py` into `src/puptoo/qpc/report_processor.py`. Apply the following fixes during port:
1. Use `mq/produce.send_message()` instead of inline produce calls
2. Send validation messages per report/slice, not per host (fix yuptoo's spam)
3. Add `timeout=120` to `download_report()` `requests.get()` call
4. Use pre-registered modifier pipeline from `modifiers/` instead of per-host import
5. Keep commit-after-processing semantics (puptoo pattern), not yuptoo's early commit

**Acceptance Criteria:**
- [ ] `src/puptoo/qpc/report_processor.py` handles: tar download, metadata validation, slice iteration, modifier execution, HBI message production
- [ ] Uses `mq/produce.send_message()` for Kafka production
- [ ] Validation message sent once per report, not per host
- [ ] `download_report()` has `timeout=120` on `requests.get()`
- [ ] Modifier pipeline uses pre-registered instances, not per-host import
- [ ] `download_report()` and `has_canonical_facts()` available as utilities
- [ ] Processor tests pass (ported from yuptoo, updated for new patterns)

---

### Task 2.4: Add QPC configuration variables

**Type:** Task
**Points:** 2
**Description:**
Add yuptoo-specific configuration to `src/puptoo/utils/config.py`:
- `MAX_HOSTS_PER_REP` (default 10000)
- `HOSTS_TRANSFORMATION_ENABLED` (default True)
- `KAFKA_PRODUCER_OVERRIDE_MAX_REQUEST_SIZE` (default 2097152)
- `DISCOVERY_HOST_TTL` (default '29')
- `SATELLITE_HOST_TTL` (default '29')
- `BYPASS_PAYLOAD_EXPIRATION` (default False)

**Acceptance Criteria:**
- [ ] All 6 config variables present with correct defaults
- [ ] Logged by `log_config()` when puptoo starts
- [ ] No impact on existing config variables

---

### Task 2.5: Add QPC metrics

**Type:** Task
**Points:** 2
**Description:**
Add yuptoo's metrics to `src/puptoo/utils/metrics.py`:
- `archive_downloaded_success` (Counter)
- `archive_failed_to_download` (Counter)
- `extract_report_slices_failures` (Counter)
- `report_processing_exceptions` (Counter)
- `host_uploaded` (Counter)
- `host_upload_failures` (Counter)
- `incoming_hosts_counter` (Counter, labeled by `source`)

Prefix all with `puptoo_qpc_` to distinguish from existing puptoo metrics.

**Acceptance Criteria:**
- [ ] All 7 metrics defined with `puptoo_qpc_` prefix
- [ ] Existing puptoo metrics unchanged
- [ ] QPC code references the new metrics correctly

---

### Task 2.6: Create QPCHandler

**Type:** Story
**Points:** 3
**Description:**
Create `src/puptoo/handlers/qpc.py` implementing `QPCHandler(BaseHandler)`. This handler:
1. Calls `validate_qpc_message()` to extract `request_obj`
2. Calls `process_report()` to download, validate, and process the QPC tar archive
3. Handles `QPCKafkaMsgException`, `FailExtractException`, and general exceptions with appropriate metrics and logging

Register `qpc` in the handler dispatch registry.

**Acceptance Criteria:**
- [ ] `QPCHandler` exists and is registered for `service == 'qpc'`
- [ ] Full QPC processing pipeline executes through the handler
- [ ] Error handling matches yuptoo's behaviour (metrics, logging, no crash)
- [ ] Handler dispatch tests updated to verify `qpc` -> `QPCHandler`

---

### Task 2.7: Wire QPC code to unified exception hierarchy

**Type:** Task
**Points:** 1
**Description:**
QPC exception classes were already created in `src/puptoo/exceptions.py` (Task 1.7). Update all ported QPC code (`report_processor.py`, `validators.py`, `QPCHandler`) to import from the unified `exceptions.py` rather than yuptoo's `lib/exceptions.py`. Ensure each exception type triggers the correct metric and tracker/validation message.

**Acceptance Criteria:**
- [ ] All QPC code imports from `src.puptoo.exceptions`
- [ ] No yuptoo exception imports remain
- [ ] Each exception type maps to the correct metric counter
- [ ] `QPCKafkaMsgException` -> `kafka_failures` metric
- [ ] `FailExtractException` -> `extract_report_slices_failures` metric

---

### Task 2.8: Port yuptoo test suite

**Type:** Story
**Points:** 5
**Description:**
Port all yuptoo tests into `tests/qpc/`. Update imports to use puptoo's package structure. Verify all tests pass in the merged codebase.

**Test files to port:**
- 11 modifier tests -> `tests/qpc/modifiers/`
- 2 processor tests -> `tests/qpc/`
- 2 validator tests -> `tests/qpc/`
- Test utilities (`tests/utils.py`) -> merge into existing test utils

**Acceptance Criteria:**
- [ ] All 63 yuptoo tests pass under `tests/qpc/`
- [ ] All 67 existing puptoo tests still pass
- [ ] `pytest` discovers and runs all ~130 tests
- [ ] No import errors or path issues

---

### Task 2.9: Migrate to uv and update dependencies

**Type:** Story
**Points:** 3
**Description:**
Migrate puptoo's dependency management from Poetry to `uv` (team-preferred tooling). Yuptoo has an upstream `pipenv_to_uv` branch in progress; leverage that work where possible. Remove `poetry.lock` and Poetry-specific config from `pyproject.toml`. Add any yuptoo dependencies not already present (`pytest-cov` dev dependency, align `requests` version). Verify `insights-core` 3.7.6 (puptoo's version) is compatible with yuptoo's code. Update the Dockerfile to use `uv` for installs.

**Acceptance Criteria:**
- [ ] `pyproject.toml` uses standard PEP 621 metadata (no `[tool.poetry]` section)
- [ ] `uv lock` succeeds and produces `uv.lock`
- [ ] `poetry.lock` removed
- [ ] All dependencies from both puptoo and yuptoo are present
- [ ] Dockerfile updated to install via `uv pip install` or `uv sync`
- [ ] `uv run pytest` passes all tests
- [ ] No import errors in ported code

---

### Task 2.10: Verify QPC processing in ephemeral

**Type:** Task
**Points:** 3
**Description:**
Deploy the merged puptoo (with QPC handler) to a Bonfire ephemeral environment. Upload a QPC tar payload and verify end-to-end processing: message consumption, tar extraction, metadata validation, modifier execution, HBI host creation.

**Acceptance Criteria:**
- [ ] QPC payload processed without errors
- [ ] Hosts appear in HBI
- [ ] Advisor uploads still process correctly (regression)
- [ ] QPC metrics visible on `/metrics` endpoint

---

**Sprint 2-3 Total:** 30 story points

---

## Sprint 4: Deployment and Cutover

### Task 3.1: Update ClowdApp deployment manifest

**Type:** Story
**Points:** 3
**Description:**
Update `deployment.yaml` to include:
- QPC-specific environment variables (`MAX_HOSTS_PER_REP`, `HOSTS_TRANSFORMATION_ENABLED`, etc.)
- `KAFKA_CONSUMER_MAXPOLL_INTERVAL` parameter
- Both IQE test plugins (`puptoo` + `foreman-rh-cloud`)
- Optional: add `message.max.bytes` for producer if QPC slices can be large

**Acceptance Criteria:**
- [ ] All QPC config parameters present with defaults
- [ ] Both IQE plugins configured
- [ ] Manifest validates without errors
- [ ] Resource limits reviewed for combined workload (may need increase)

---

### Task 3.2: Stage deployment and regression testing

**Type:** Task
**Points:** 3
**Description:**
Deploy merged puptoo to stage. Run IQE tests for both plugins. Verify advisor/compliance/malware processing is unaffected. Test QPC payloads end-to-end.

**Acceptance Criteria:**
- [ ] IQE `puptoo` tests pass in stage
- [ ] IQE `foreman-rh-cloud` tests pass in stage
- [ ] No regression in advisor/compliance/malware metrics
- [ ] QPC test payloads processed successfully

---

### Task 3.3: Production deployment

**Type:** Task
**Points:** 2
**Description:**
Deploy merged puptoo to production. Monitor for errors, metric anomalies, and consumer lag.

**Acceptance Criteria:**
- [ ] Deployment successful
- [ ] Advisor/compliance/malware metrics stable for 24 hours
- [ ] QPC processing metrics confirm host uploads
- [ ] No increase in error rates

---

### Task 3.4: Decommission yuptoo

**Type:** Task
**Points:** 2
**Description:**
Scale yuptoo replicas to 0 in production. Monitor the `qpc-group` consumer group for lag (should show no new messages). After 1-2 weeks grace period, remove the yuptoo ClowdApp entirely.

**Acceptance Criteria:**
- [ ] Yuptoo replicas at 0
- [ ] `qpc-group` consumer group shows zero lag for 1 week
- [ ] No alerts triggered by yuptoo absence
- [ ] Yuptoo ClowdApp removed from app-interface

---

### Task 3.5: Archive yuptoo repository

**Type:** Task
**Points:** 1
**Description:**
Archive the yuptoo repository on GitHub. Update the README to indicate the service has been merged into puptoo with a link to the merged codebase.

**Acceptance Criteria:**
- [ ] Repository marked as archived (read-only)
- [ ] README updated with deprecation notice and redirect
- [ ] Internal documentation updated to reference merged puptoo

---

### Task 3.6: Update monitoring and documentation

**Type:** Task
**Points:** 2
**Description:**
Update Grafana dashboards to include QPC metrics from puptoo. Remove yuptoo-specific dashboards. Update runbooks and on-call documentation to reflect the merged service.

**Acceptance Criteria:**
- [ ] QPC metrics visible on puptoo dashboard
- [ ] Yuptoo dashboard archived or removed
- [ ] Runbooks updated for combined service
- [ ] On-call documentation reflects single service

---

**Sprint 4 Total:** 13 story points

---

## Summary

| Sprint | Focus                                    | Story Points |
| ------ | ---------------------------------------- | ------------ |
| 1      | Refactor puptoo + A+ infrastructure      | 27           |
| 2-3    | Port QPC processing (with fixes)         | 30           |
| 4      | Deployment and cutover                   | 13           |
| **Total** |                                       | **70**       |

> [!NOTE]
> The 8-point increase over vanilla Strategy A (62 -> 70) reflects the typed exceptions, `mq/auth.py`, `send_message()` relocation, bug fixes, and modifier framework improvements. These are one-time costs that yield permanent architectural quality.

### Dependency Graph

```
Sprint 1:
1.1 ──► 1.2 ──► 1.4 ──► 1.10 ──► 1.11
   │         ▲
   └──► 1.3 ─┘
1.5 ──► 1.6            (auth.py before send_message move)
1.7 (independent)       (typed exceptions)
1.8 (independent)       (max.poll + SIGINT + bool normalization)
1.9 (independent)       (puptoo bug fixes)

Sprint 2-3:
2.1 ──► 2.3 ──► 2.6 ──► 2.8 ──► 2.10
2.2 ──► 2.3     ▲
2.4 ────────────┘
2.5 ────────────┘
2.7 ──► 2.6
2.9 (independent, do early)

Sprint 4:
3.1 ──► 3.2 ──► 3.3 ──► 3.4 ──► 3.5
                              └──► 3.6
```

---

## Implementation Notes

### Kafka Topic Routing

The two services write to **different** HBI ingress topics:

| Service | Config variable | Actual topic |
|---------|----------------|--------------|
| Puptoo | `INVENTORY_TOPIC` | `host-ingress-p1` |
| Yuptoo | `UPLOAD_TOPIC` | `platform.inventory.host-ingress` |

The merged service handler dispatch must route produce calls to the correct topic based on handler type (advisor/compliance/malware vs qpc). This should be addressed in the QPCHandler task (2.6) or as a separate sub-task.

### IQE Plugin Co-location

The yuptoo IQE plugin lives at `gitlab.cee.redhat.com/insights-qe/iqe-foreman-rh-cloud-plugin`. Consider migrating IQE plugins into the merged repo (as HBI did) for tighter integration. This is optional but recommended by the project sponsor (Ondrej). If pursued, add as a Sprint 4 task.

### `uv` Migration: Decouple from Merge

Task 2.9 (migrate to `uv`) should be a **separate effort**, done before or after the merge, not during. Getting both repos as similar as possible before porting reduces merge risk. Track as an independent JIRA outside this Epic. (Agreed: Gael + Pranav, Jun 22)

### HBI Reporter Name Change

The merged service's reporter name is part of the `host_events` spec in Host Inventory (HBI). Renaming the service (from "puptoo"/"yuptoo" to the new name) will require corresponding changes in HBI itself. Add as a Sprint 4 subtask under Task 3.1 (deployment manifest) or as a separate cross-team story.
