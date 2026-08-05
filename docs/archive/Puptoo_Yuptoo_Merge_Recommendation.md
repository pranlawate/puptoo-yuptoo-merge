# Puptoo-Yuptoo Merge: Architecture Recommendation

> Based on the [Comparison](Puptoo_Yuptoo_Comparison.md) and [Strategy Evaluation](Puptoo_Yuptoo_Merge_Strategy_Evaluation.md), Strategy A+ (merge yuptoo into puptoo with best-of-both architectural upgrades) is the recommended approach. This document describes the proposed architecture, migration plan, testing strategy, deployment cutover, and risk assessment.

> [!note] Historical document (frozen)
> The module layout and core architectural decisions here (handler dispatch, typed exceptions, modifier pre-registration) held up and were implemented in Phase 1/2. The **deployment/cutover sections predate the multi-deployment decision** (see [component_diagram.md](../diagrams/component_diagram.md) correction note) and the Jul 20 repo-strategy reversal — for current cutover planning, see [Implementation Tasks](../Puptoo_Yuptoo_Merge_Tasks.md), not this document. Kept as-is for reference, not updated further.

---

## Recommended Strategy

**Strategy A+: Merge yuptoo into puptoo, adopting the best patterns from both codebases.**

The weighted evaluation scores (A+=107, A=98, B=63, C=55) favour A+ decisively. It costs one extra sprint over vanilla Strategy A but achieves Strategy C's architecture quality (score 5) and long-term maintenance (score 5) without the greenfield risk. The primary reasons:

1. **Lowest risk.** The advisor/compliance/malware path (the vast majority of traffic at 8 replicas) is untouched. QPC processing is additive.
2. **Natural extension.** Puptoo already routes by `service` header. Adding `qpc` is architecturally congruent (fitting).
3. **Operational continuity.** Deployment pipelines, dashboards, alerts, runbooks, and team familiarity remain intact.
4. **Best architecture quality.** By adopting yuptoo's superior patterns (DRY auth, encapsulated produce, typed exceptions, modifier pipeline) and fixing known bugs in both codebases, the result is genuinely better than either predecessor.
5. **Reasonable effort.** ~4 sprints (one more than vanilla A) for a significant quality jump.

---

## Proposed Architecture

### Module Layout (A+ Refined)

```
insights-puptoo/
├── src/puptoo/
│   ├── app.py                          # THINNED: init, poll loop, handler dispatch, signals
│   ├── exceptions.py                   # NEW: typed exception hierarchy (adopted from yuptoo)
│   ├── handlers/                       # NEW: per-service processing handlers
│   │   ├── __init__.py                 # Registry: get_handler(service) -> BaseHandler
│   │   ├── base.py                     # BaseHandler ABC
│   │   ├── advisor.py                  # insights-core extract + postprocess
│   │   ├── compliance.py               # Forward metadata (compliance + malware-detection)
│   │   └── qpc.py                      # QPC report pipeline (ported from yuptoo)
│   ├── modifiers/                      # NEW: pluggable transforms (adopted from yuptoo)
│   │   ├── __init__.py                 # Pre-register at startup, explicit ordering
│   │   ├── base.py                     # Modifier ABC with correct run(host, transformed_obj, **kwargs)
│   │   └── qpc/                        # QPC-specific modifiers (11 classes, ported)
│   │       ├── add_host_facts.py
│   │       ├── remove_display_name.py
│   │       ├── remove_invalid_bios_uuid.py
│   │       ├── transform_cloud_provider.py
│   │       ├── transform_installed_packages.py
│   │       ├── transform_ip_addresses.py
│   │       ├── transform_mac_addresses.py
│   │       ├── transform_network_interfaces.py
│   │       ├── transform_os_kernel_version.py
│   │       ├── transform_os_release.py
│   │       └── transform_tags.py
│   ├── process/                        # insights-core archive extraction (unchanged)
│   │   ├── __init__.py
│   │   └── profile.py
│   ├── qpc/                            # NEW: QPC-specific processing (ported from yuptoo)
│   │   ├── __init__.py
│   │   ├── report_processor.py         # Ported + fixed (pre-registered modifiers, per-report validation)
│   │   └── validators.py               # Merged: qpc_message_validator + report_metadata_validator
│   ├── mq/                             # Kafka infrastructure (REFACTORED)
│   │   ├── __init__.py
│   │   ├── auth.py                     # NEW: kafka_auth_config() (adopted from yuptoo, DRY)
│   │   ├── consume.py                  # Uses auth.py; adds max.poll.interval.ms
│   │   ├── produce.py                  # REFACTORED: send_message() + delivery_report() moved here from app.py
│   │   └── msgs.py                     # Pure message builders (unchanged)
│   ├── upload.py                       # S3 yum_updates (fix bare except, pool MinIO client)
│   └── utils/
│       ├── config.py                   # Merged: puptoo + QPC vars, normalized bool parsing
│       ├── metrics.py                  # Merged: puptoo rich types + yuptoo QPC counters
│       ├── validators.py              # Merged: puptoo provider-pair + yuptoo extended fact list
│       └── puptoo_logging.py          # Unchanged
├── tests/
│   ├── test_app.py                     # Update for handler dispatch
│   ├── test_*.py                       # Existing puptoo tests (unchanged)
│   ├── test_handlers.py               # NEW: handler dispatch tests
│   ├── test_produce.py                # NEW: send_message() + delivery_report() tests
│   └── qpc/                            # NEW: ported yuptoo tests
│       ├── test_report_processor.py
│       ├── test_validators.py
│       └── modifiers/
│           ├── test_add_host_facts.py
│           ├── test_remove_display_name.py
│           └── ... (all 11 modifier tests)
├── deployment.yaml                     # Add QPC config parameters
└── pyproject.toml                      # Migrate from Poetry to uv (PEP 621)
```

### Key A+ Architectural Decisions

| Decision                            | Pattern source | Rationale                                                                   |
| ----------------------------------- | -------------- | ---------------------------------------------------------------------------- |
| `mq/auth.py` shared helper         | Yuptoo         | Eliminates duplicated SASL/SSL blocks between consumer and producer          |
| `send_message()` in `mq/produce.py`| Yuptoo         | Correct module boundary; delivery callbacks, key selection, and metrics in one place |
| `exceptions.py` typed hierarchy     | Yuptoo         | Granular error routing, targeted metrics, clearer stack traces               |
| Modifiers pre-registered at startup | Yuptoo (fixed) | Fixes O(hosts x modifiers) import overhead; adds explicit ordering           |
| `Modifier` ABC correct signature   | Yuptoo (fixed) | `run(host, transformed_obj, **kwargs)` for proper static analysis            |
| Commit-after-processing for QPC     | Puptoo         | At-least-once semantics; do NOT adopt yuptoo's at-most-once early commit     |
| Hard exit on poll errors            | Puptoo         | Forces pod recreation on MAXPOLL/session timeout                             |
| Canonical facts validation merged   | Both           | Puptoo's provider-pair rule + yuptoo's extended fact list (`vm_uuid`, `etc_machine_id`) |
| Bool parsing normalized             | Fixed          | Single convention across all config variables                                |
| Request download timeout            | Fixed          | `requests.get(url, timeout=...)` to prevent indefinite hangs                 |

### Architecture Diagram

```
  Kafka: announce
        │
        ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │                    insights-puptoo (A+)                          │
  │                                                                 │
  │  app.py (thin)                                                  │
  │  consumer.poll() → parse service header → get_handler()         │
  │  Redis retry check → handler.process() → commit in finally      │
  │       │                                                         │
  │       ├── advisor ──► AdvisorHandler                            │
  │       │                  ├── process/ (insights-core extract)    │
  │       │                  ├── postprocess()                       │
  │       │                  ├── validateCanonicalFacts()            │
  │       │                  └── upload.py (S3 yum_updates)         │
  │       │                                                         │
  │       ├── compliance ──► ComplianceHandler                      │
  │       │   malware         └── forward msg["metadata"]           │
  │       │                                                         │
  │       └── qpc ──► QPCHandler                                    │
  │                    ├── qpc/validators.py (URL expiry, metadata)  │
  │                    ├── qpc/report_processor.py (tar, slices)     │
  │                    └── modifiers/ (pre-registered pipeline)      │
  │                         ├── TransformTags                        │
  │                         ├── TransformNetworkInterfaces           │
  │                         ├── AddHostFacts                         │
  │                         └── ... (11 total)                       │
  │                                                                 │
  │  mq/produce.py ◄── send_message() + delivery_report()          │
  │  mq/auth.py ◄── kafka_auth_config() (shared)                   │
  │  mq/msgs.py ◄── inv_message / tracker / validation              │
  │  exceptions.py ◄── typed hierarchy                              │
  └─────────────────────┬───────────────────────────────────────────┘
                        │
          ┌─────────────┼─────────────┐
          ▼             ▼             ▼
    host-ingress   payload-status  upload.validation
    (to HBI)       (tracker)       (storage broker)
```

### Handler Interface

```python
from abc import ABC, abstractmethod

class BaseHandler(ABC):
    """Base class for service-specific message handlers."""

    @abstractmethod
    def process(self, msg: dict, extra: dict) -> dict:
        """Process message and return facts/host data."""
        ...

    @abstractmethod
    def build_hbi_messages(self, facts: dict, msg: dict) -> list[dict]:
        """Build one or more HBI messages from processed data."""
        ...
```

### Typed Exception Hierarchy (adopted from yuptoo)

```python
# src/puptoo/exceptions.py
class PuptooError(Exception):
    """Base for all puptoo errors."""

class FailDownloadException(PuptooError):
    """Archive download failed (non-retryable)."""

class FailExtractException(PuptooError):
    """Archive extraction failed (non-retryable)."""

class QPCKafkaMsgException(PuptooError):
    """Invalid QPC Kafka message (missing fields, expired URL)."""

class QPCReportException(PuptooError):
    """QPC report has zero valid hosts."""

class RetryExhaustedException(PuptooError):
    """Redis retry limit reached for request_id."""
```

### Modifier Pre-Registration (fixed from yuptoo)

```python
# src/puptoo/modifiers/__init__.py
import importlib
import inspect
from .base import Modifier

_REGISTRY: list[Modifier] = []

def register_modifiers(package_path: str, package_name: str):
    """Import all modifier modules once at startup, register Modifier subclasses."""
    import pkgutil
    for loader, module_name, is_pkg in pkgutil.walk_packages([package_path]):
        module = importlib.import_module(f'{package_name}.{module_name}')
        for _, cls in inspect.getmembers(module, inspect.isclass):
            if issubclass(cls, Modifier) and cls is not Modifier:
                _REGISTRY.append(cls())

def get_modifiers() -> list[Modifier]:
    return _REGISTRY
```

### Refactored Main Loop (Simplified)

```python
# In app.py main loop, replace the current if/elif chain:
from .handlers import get_handler
from .mq.produce import send_message

service = dict(msg.headers() or []).get('service', b'').decode("utf-8")
handler = get_handler(service)
if handler:
    msg_data = json.loads(msg.value().decode("utf-8"))
    extra = get_extra(msg_data.get("account"), msg_data.get("org_id"), msg_data.get("request_id"))
    handle_retries(redis, extra["request_id"])
    handler.process(msg_data, extra)
```

---

## Migration Plan

### Phase 1: Refactor Puptoo Infrastructure (Sprint 1)

| Step | Action                                                                                          |
| ---- | ----------------------------------------------------------------------------------------------- |
| 1.1  | Create `handlers/` directory with `BaseHandler` ABC and registry                                |
| 1.2  | Extract advisor logic from `handle_message()` into `AdvisorHandler`                             |
| 1.3  | Extract compliance logic into `ComplianceHandler`                                               |
| 1.4  | Refactor `app.py` main loop to use handler dispatch                                             |
| 1.5  | Create `mq/auth.py` with `kafka_auth_config()` (adopt yuptoo pattern), use in consumer + producer |
| 1.6  | Move `send_message()` + `delivery_report()` from `app.py` to `mq/produce.py`                   |
| 1.7  | Create `exceptions.py` with typed hierarchy (adopt from yuptoo, extend for puptoo)              |
| 1.8  | Add `max.poll.interval.ms` and `message.max.bytes` config                                       |
| 1.9  | Add SIGINT handler alongside existing SIGTERM                                                    |
| 1.10 | Fix puptoo bugs: `delivery_report` args, `handle_retries` exception, dead `clean_macs`, bare `except:`, bool parsing |
| 1.11 | Verify all existing tests still pass                                                            |
| 1.12 | Deploy to ephemeral (Bonfire) and verify advisor/compliance/malware flows are unaffected         |

**Gate:** All existing puptoo tests pass. Ephemeral test confirms no regression. `app.py` reduced to thin dispatch loop.

### Phase 2: Port QPC Processing (Sprint 2-3)

| Step | Action                                                                                          |
| ---- | ----------------------------------------------------------------------------------------------- |
| 2.1  | Create `modifiers/` with pre-registration pattern, correct `Modifier` ABC, explicit ordering    |
| 2.2  | Port all 11 QPC modifier classes into `modifiers/qpc/`                                          |
| 2.3  | Port both QPC validators into `qpc/validators.py` (URL expiry + metadata validation)            |
| 2.4  | Port `report_processor.py` with fixes: use `mq/produce.send_message()`, per-report validation messages, download timeout |
| 2.5  | Create `QPCHandler` that integrates validators + processor + modifier pipeline                   |
| 2.6  | Register `qpc` in handler dispatch                                                              |
| 2.7  | Add QPC config variables (host TTL, max hosts, bypass expiry, etc.)                             |
| 2.8  | Add QPC metrics to `metrics.py`                                                                 |
| 2.9  | Port all yuptoo tests into `tests/qpc/`                                                         |
| 2.10 | Migrate dependency management from Poetry to `uv` (PEP 621)                                     |
| 2.11 | Run full test suite (puptoo + ported QPC tests)                                                 |
| 2.12 | Deploy to ephemeral and test with QPC payload uploads                                           |

**Gate:** All tests pass (both original and ported). QPC processing verified in ephemeral.

### Phase 3: Deployment and Cutover (Sprint 4)

| Step | Action                                                                                          |
| ---- | ----------------------------------------------------------------------------------------------- |
| 3.1  | Update `deployment.yaml`: add QPC config parameters, IQE plugins, max poll interval             |
| 3.2  | Deploy merged puptoo to stage                                                                   |
| 3.3  | Verify advisor/compliance/malware flows in stage (regression test)                               |
| 3.4  | Send test QPC payloads to stage and verify end-to-end HBI ingestion                             |
| 3.5  | Run IQE tests for both `puptoo` and `foreman-rh-cloud` plugins                                 |
| 3.6  | Deploy merged puptoo to production                                                              |
| 3.7  | Verify production processing for all service types                                               |
| 3.8  | Decommission yuptoo: scale replicas to 0, monitor for residual traffic                          |
| 3.9  | Remove yuptoo ClowdApp after grace period (1-2 weeks)                                           |
| 3.10 | Archive yuptoo repository (mark read-only, update README)                                       |

**Gate:** All IQE tests pass in stage. Production metrics confirm successful processing.

---

## Testing Strategy

### Unit Tests

| Source                                | Destination in Merged Repo                  | Action          |
| ------------------------------------- | ------------------------------------------- | --------------- |
| `insights-puptoo/tests/test_app.py`  | `tests/test_app.py`                         | Update for handler dispatch |
| `insights-puptoo/tests/test_*.py` (37 profile tests) | `tests/test_*.py`            | Unchanged       |
| `insights-puptoo/tests/test_msgs.py` | `tests/test_msgs.py`                        | Unchanged       |
| `insights-puptoo/tests/test_canonical_facts.py` | `tests/test_canonical_facts.py` | Unchanged       |
| `yuptoo/tests/modifiers/test_*.py` (11 files) | `tests/qpc/modifiers/test_*.py` | Update imports  |
| `yuptoo/tests/processor/test_*.py` (2 files) | `tests/qpc/test_report_processor.py` | Update imports  |
| `yuptoo/tests/validators/test_*.py` (2 files) | `tests/qpc/test_validators.py` | Update imports  |

### Integration Tests

| Test Level           | Method                                                    |
| -------------------- | ---------------------------------------------------------- |
| Handler dispatch     | New tests: verify correct handler is selected per service  |
| QPC end-to-end       | Port yuptoo's processor tests, verify HBI message output   |
| Advisor end-to-end   | Existing tests remain unchanged                            |
| Schema validation    | Existing HBI `system_profile.spec.yaml` tests remain       |

### IQE (Ephemeral) Tests

Both `puptoo` and `foreman-rh-cloud` IQE plugins are added to the ClowdApp:

```yaml
testing:
  iqePlugin: puptoo
  # second plugin added for QPC coverage
```

> [!NOTE]
> The exact mechanism for specifying multiple IQE plugins in a ClowdApp should be confirmed with the team. It may require listing both plugins or creating a combined test config.

---

## Deployment Cutover Plan

```
Timeline (approximate)

Week 1: Merged puptoo deployed to stage
         ├─ Advisor/compliance/malware verified (regression)
         └─ QPC payloads tested
         
Week 2: Merged puptoo deployed to production
         ├─ All service types monitored
         └─ Yuptoo replicas reduced to 0
         
Week 3: Grace period
         ├─ Monitor for any residual yuptoo consumer lag
         └─ Confirm zero messages consumed by qpc-group
         
Week 4: Yuptoo ClowdApp removed
         └─ Repository archived
```

### Rollback Plan

If issues arise after production deployment:

1. **Revert puptoo** to the pre-merge version (the `qpc` handler simply won't match, QPC messages are ignored)
2. **Re-deploy yuptoo** from the archived deployment config
3. Both services return to their independent state within minutes

The rollback is clean because puptoo's handling of `qpc` messages is purely additive. Reverting to the old puptoo version means QPC messages pass through unconsumed until yuptoo is restored.

---

## Appendix: Bug Fixes Included in A+

These bugs exist in the current codebases and are fixed as part of the merge to avoid carrying forward known defects.

### Puptoo Fixes

| Bug | Fix |
| --- | --- |
| `delivery_report()` swapped format args (`app.py:177-181`) | Correct to `(topic, request_id, err)` |
| `handle_retries()` exception never interpolates (`app.py:89`) | Use f-string: `raise RetryExhaustedException(f"...{request_id}")` |
| `clean_macs()` dead code path (`app.py:244-245`) | Remove; MAC cleaning is handled by `postprocess()` |
| Bare `except:` in upload, config, app | Replace with specific exception types |
| Inconsistent boolean parsing in config | Standardize on `os.getenv(..., "").lower() in ("true", "t", "yes", "y")` |
| `CONSUMER_ASSIGNMENTS` metric never populated | Remove unused metric |
| Global mutable `producer` in app.py | Encapsulate in `mq/produce.py` module |

### Yuptoo Fixes (applied during port)

| Bug | Fix |
| --- | --- |
| Early commit before processing (`main.py:78`) | Commit in `finally` block after processing (adopt puptoo pattern) |
| Per-host `importlib`/`inspect` in modifier loop | Pre-register modifiers at startup; iterate pre-built list in hot loop |
| No modifier ordering guarantee | Explicit ordered list in `modifiers/__init__.py` |
| `Modifier` ABC signature mismatch | Define as `run(self, host: dict, transformed_obj: dict, **kwargs)` |
| Per-host validation message spam | Send one validation message per report/slice, not per host |
| `download_report()` has no request timeout | Add `requests.get(url, timeout=120)` |
| Shadows builtin `bytes` variable in `produce.py` | Rename to `msg_bytes` |

---

## Risk Assessment

| Risk                                             | Probability | Impact | Mitigation                                                                 |
| ------------------------------------------------ | ----------- | ------ | --------------------------------------------------------------------------- |
| Regression in advisor/compliance/malware flow     | Low         | High   | Handler refactor is tested in isolation. Existing tests provide coverage.    |
| QPC processing fails in merged service            | Medium      | Medium | Tested in ephemeral before stage. Yuptoo remains available for rollback.    |
| Consumer group transition drops QPC messages      | Low         | Medium | Both consumer groups can run simultaneously during transition.               |
| Performance impact from QPC's large tars          | Low         | Medium | `max.poll.interval.ms` config prevents consumer timeout. Separate replicas possible. |
| Modifier behaviour differs after porting          | Low         | Low    | All 11 modifier tests are ported with original test data.                    |
| insights-core version conflict                    | Very Low    | Low    | Both use ~3.7.x. Merged service uses puptoo's 3.7.6 (newer).               |
| Team unfamiliarity with QPC codebase              | Medium      | Low    | QPC code is isolated in `qpc/` directory. Clear separation.                 |
