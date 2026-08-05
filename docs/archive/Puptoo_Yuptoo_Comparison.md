# Puptoo vs Yuptoo: Side-by-Side Comparison

> Detailed comparison for evaluating merge strategy. Both services consume from the same Kafka topic, produce to the same downstream topics, and send hosts to HBI. They differ in what they process and how they transform data.

> [!note] Historical document (frozen)
> This was the initial codebase study used to choose a merge strategy (June 2026). It reflects the codebases as they stood at that time and is not updated as the merge progresses. For current status, see [README.md](../../README.md) or JIRA epic [RHINENG-27899](https://redhat.atlassian.net/browse/RHINENG-27899).

---

## 1. Purpose and Service Routing

| Aspect                 | Puptoo                                                  | Yuptoo                                                  |
| ---------------------- | ------------------------------------------------------- | ------------------------------------------------------- |
| Full name              | Platform Upload Processor II                            | Yupana Upload Processor II                              |
| Kafka header filter    | `service` in `[advisor, compliance, malware-detection]` | `service == qpc`                                        |
| Input format           | Insights archive (tar.gz from insights-client)          | QPC tar archive (metadata.json + host slice JSONs)      |
| Processing             | Downloads archive, runs insights-core to extract facts  | Downloads tar, validates metadata, iterates host slices |
| Multi-host per message | No (one host per archive)                               | Yes (up to 10K hosts per slice, multiple slices)        |
| Source systems         | RHEL systems running insights-client                    | Satellite/Discovery via QPC uploads                     |

---

## 2. Entry Point and Main Loop

| Aspect            | Puptoo (`src/puptoo/app.py`, 314 lines)               | Yuptoo (`main.py`, 104 lines)                        |
| ----------------- | ------------------------------------------------------ | ----------------------------------------------------- |
| Entry function    | `main()` via Poetry script `puptoo`                    | `main()` via `python -m main`                         |
| Signal handling   | `SIGTERM` only                                         | `SIGTERM` + `SIGINT`                                  |
| Poll loop         | `consumer.poll(1.0)`, filter by header                 | `consumer.poll(1.0)`, filter by header                |
| Error on poll     | `os._exit(os.EX_SOFTWARE)` (hard restart)              | `LOG.error()` + `continue` (soft continue)            |
| Commit strategy   | In `finally` block after processing                    | Immediately after validation, before processing       |
| Redis retry       | Yes, 3 attempts per `request_id` (TTL 3600s)           | No                                                    |
| Extra context     | `get_extra()` sets `threadctx`                         | `set_extra_log_data()` sets `threadctx`               |

**Key difference:** Puptoo hard-exits on Kafka poll errors to force pod recreation. Yuptoo logs and continues. Yuptoo commits before processing (at-most-once), puptoo commits after (at-least-once with Redis dedup).

---

## 3. Kafka Consumer

| Aspect                 | Puptoo (`src/puptoo/mq/consume.py`, 33 lines)   | Yuptoo (`yuptoo/lib/consume.py`, 29 lines)       |
| ---------------------- | ------------------------------------------------ | ------------------------------------------------- |
| Group ID               | `config.APP_NAME` (`insights-puptoo`)            | `KAFKA_CONSUMER_GROUP_ID` (`qpc-group`)           |
| Max poll interval      | Not configured (default)                         | `KAFKA_CONSUMER_MAXPOLL_INTERVAL` (600000ms)      |
| Queue max KB           | `config.KAFKA_QUEUE_MAX_KBYTES` (1024)           | Not configured                                    |
| Auto create topics     | `config.KAFKA_ALLOW_CREATE_TOPICS`               | Not configured                                    |
| Auth config            | Inline in `init_consumer()`                      | Extracted to `kafka_auth_config()` helper          |
| Subscribe              | `config.ANNOUNCE_TOPIC`                          | `ANNOUNCE_TOPIC`                                   |

**Notable:** Yuptoo extracts Kafka auth into a reusable `kafka_auth_config()` function shared between consumer and producer. Puptoo duplicates the auth logic in both.

---

## 4. Kafka Producer

| Aspect                 | Puptoo (`src/puptoo/mq/produce.py`, 27 lines)   | Yuptoo (`yuptoo/lib/produce.py`, 49 lines)        |
| ---------------------- | ------------------------------------------------ | -------------------------------------------------- |
| Max message size       | Not configured (default)                         | `KAFKA_PRODUCER_OVERRIDE_MAX_REQUEST_SIZE` (2MB)   |
| Send function          | In `app.py` `send_message()` (not in produce.py)| `produce.send_message()` (in produce module)       |
| Delivery callback      | `delivery_report()` in `app.py`                  | Nested `delivery_report()` in `send_message()`     |
| Metrics on delivery    | `msg_produced` / `msg_send_failure` (by topic)   | `host_uploaded` / `host_upload_failures` (HBI only) |
| Key for HBI messages   | `org_id` bytes                                   | `org_id` bytes                                      |
| Global producer        | Yes (module-level in `app.py`)                   | Yes (module-level in `produce.py`)                  |

**Notable:** Puptoo's `send_message()` lives in `app.py` (314-line file), not in the produce module. Yuptoo properly encapsulates it in `produce.py`.

---

## 5. Configuration

| Aspect              | Puptoo (`src/puptoo/utils/config.py`, 97 lines)    | Yuptoo (`yuptoo/lib/config.py`, 53 lines)          |
| -------------------- | --------------------------------------------------- | --------------------------------------------------- |
| Dependency mgmt      | Poetry (`pyproject.toml`)                           | Pipfile                                              | Team prefers `uv` for the merged service |
| Clowder toggle       | `CLOWDER_ENABLED` env var                           | Same                                                 |
| Auth helper          | Inline in consumer/producer                         | `kafka_auth_config()` function                       |
| S3/MinIO config      | Yes (`BUCKET_NAME`, `S3_ENDPOINT`, keys)            | No (no object store)                                 |
| Redis config         | Yes (`REDIS_HOST`, `REDIS_PORT`, `REDIS_PASSWORD`)  | No                                                   |
| HBI topic name       | `INVENTORY_TOPIC` (`host-ingress-p1`)               | `UPLOAD_TOPIC` (`platform.inventory.host-ingress`)   |
| HBI reporter name    | `"puptoo"` (hardcoded in `app.py`)                  | `"discovery"` or `"satellite"` (source-based, in `AddHostFacts`) |
| HBI facts namespace  | N/A (uses insights-core facts)                      | `"yupana"` (historical name, stored in HBI per-host) |
| Metrics port default | 8000 (legacy) / Clowder metricsPort                 | 5005 (legacy) / Clowder metricsPort                  |
| `log_config()`       | Yes, logs all uppercase module vars                  | No equivalent                                        |
| Max hosts per report  | N/A                                                 | `MAX_HOSTS_PER_REP` (10000)                          |
| URL expiry bypass     | N/A                                                 | `BYPASS_PAYLOAD_EXPIRATION`                           |
| Host TTL              | Hardcoded 29 hours in `get_staletime()`             | `DISCOVERY_HOST_TTL` / `SATELLITE_HOST_TTL` (29)     |

---

## 6. Message Builders

| Message type   | Puptoo (`src/puptoo/mq/msgs.py`, 39 lines)                              | Yuptoo (`yuptoo/processor/utils.py`)                                   |
| -------------- | ------------------------------------------------------------------------ | ----------------------------------------------------------------------- |
| HBI (add_host) | `inv_message(operation, data, metadata)`: copies `account`/`org_id`     | Inline in `upload_to_host_inventory_via_kafka()`: `request_id` as key  |
| Tracker        | `tracker_message(extra, status, status_msg)`: `service: "puptoo"`       | `tracker_message(request_obj, status, status_msg)`: `service: "yuptoo"` |
| Validation     | `validation_message(msg, facts, result)`: merges msg+facts              | Inline dict: `{hash, request_id, validation: status}`                   |

**Key difference:** Puptoo sends the full ingress message as `platform_metadata` in the HBI message. Yuptoo sends only `{request_id, b64_identity}`. Puptoo copies `account`/`org_id` into `data`; yuptoo's modifiers add these fields.

---

## 7. Archive Processing

| Aspect                  | Puptoo (`src/puptoo/process/__init__.py`, 85 lines)      | Yuptoo (`yuptoo/processor/report_processor.py`, 181 lines) |
| ----------------------- | --------------------------------------------------------- | ----------------------------------------------------------- |
| Download                | `requests.get(url)` in `get_archive()`                    | `requests.get(url)` in `download_report()`                  |
| Archive format          | insights-core `extract()` context manager                  | `tarfile.open()` on BytesIO                                  |
| Size validation         | `validate_size()` against 1GB/512MB limits                 | Slice-level host count validation (max 10K/slice)            |
| Fact extraction         | `get_system_profile()` via insights-core rules             | Hosts arrive pre-structured in JSON                          |
| insights-core usage     | Heavy: custom `system_profile` rule (1100 lines)           | Light: only `InstalledRpm` parser in one modifier            |
| Post-processing         | `postprocess()`: MAC filter, tag promotion, empty removal  | 11 modifier classes (pluggable via pkgutil)                  |
| Multi-host              | Single host per archive                                    | Multiple hosts per slice, multiple slices per tar            |

---

## 8. Host Transformation

| Aspect              | Puptoo                                                     | Yuptoo                                                           |
| -------------------- | ----------------------------------------------------------- | ----------------------------------------------------------------- |
| Architecture         | Monolithic `handle_message()` in `app.py`                  | Pluggable `Modifier` ABC with 11 concrete classes                |
| Plugin discovery     | N/A                                                         | `pkgutil.walk_packages()` in `modifiers/__init__.py`             |
| MAC cleaning         | `clean_macs()` using `MAC_REGEX` from profile.py           | `TransformMacAddresses` modifier + `_remove_mac_addrs_for_omitted_nics()` |
| Cloud provider       | N/A (extracted by insights-core)                            | `TransformCloudProvider`: `google` to `gcp`                      |
| OS release parsing   | N/A (extracted by insights-core)                            | `TransformOsRelease`: parses release strings                     |
| Installed packages   | Extracted by insights-core system_profile rule              | `TransfromInstalledPackages`: normalizes epochs via `InstalledRpm` |
| Network interfaces   | N/A (extracted by insights-core)                            | `TransformNetworkInterfaces`: omits `cali*`, coerces MTU         |
| IP addresses         | N/A                                                         | `TransformIPAddress`: dedupes, strips blanks                     |
| Tags                 | N/A                                                         | `TransformTags`: coerces bools, truncates >250 chars             |
| Display name         | Override from ingress metadata                              | `RemoveDisplayName`: removes it entirely                         |
| BIOS UUID            | N/A                                                         | `RemoveInvalidBiosUUID`: removes invalid/empty values            |
| Host facts           | Added inline in `handle_message()`                          | `AddHostFacts`: adds `stale_timestamp`, `reporter`, `owner_id`   |
| Owner ID             | `get_owner()` from `b64_identity` CN                       | `AddHostFacts` extracts from cert CN                             |
| Stale timestamp      | `get_staletime()`: now + 29 hours (hardcoded)               | Configurable `DISCOVERY_HOST_TTL`/`SATELLITE_HOST_TTL`           |
| S3 upload            | `yum_updates` uploaded to MinIO, URL in `custom_metadata`  | N/A                                                               |

---

## 9. Canonical Facts Validation

| Aspect                | Puptoo (`src/puptoo/utils/validators.py`, 15 lines)                    | Yuptoo (`yuptoo/processor/utils.py`)                                  |
| --------------------- | ----------------------------------------------------------------------- | ---------------------------------------------------------------------- |
| Function              | `validateCanonicalFacts(facts)`                                        | `has_canonical_facts(host)`                                            |
| Required facts        | At least one ID fact (`provider_id`, `subscription_manager_id`, `insights_id`) AND at least one other fact | At least one of 7 facts (`insights_id`, `bios_uuid`, `ip_addresses`, `mac_addresses`, `vm_uuid`, `etc_machine_id`, `subscription_manager_id`) |
| Provider pair rule    | `provider_id` + `provider_type` must both be present or both absent    | No such rule                                                           |
| On failure            | Raises exception, sends validation failure + tracker error             | Host skipped, counted as `host_upload_failures` metric                 |

---

## 10. Metrics

| Aspect      | Puptoo (`src/puptoo/utils/metrics.py`, 76 lines)                  | Yuptoo (`yuptoo/lib/metrics.py`, 42 lines)                        |
| ----------- | ------------------------------------------------------------------ | ------------------------------------------------------------------ |
| Types used  | Counter, Histogram, Summary                                       | Counter only                                                       |
| Consume     | `kafka_consume_msg_count`, `kafka_consume_msg_failure_count`       | `kafka_failures`                                                    |
| Processing  | `extraction_count`, `extract_failure`, `extract_success`           | `report_processing_exceptions`, `extract_report_slices_failures`   |
| Per-service | `msg_processed_count/success/failure` (labeled by `service`)       | N/A                                                                 |
| Produce     | `msg_produced`, `msg_send_failure` (labeled by `topic`)            | `host_uploaded`, `host_upload_failures`                             |
| Archive     | `unpacking_count/failure/success`, `msg_extraction_size`           | `archive_downloaded_success`, `archive_failed_to_download`          |
| Timing      | `GET_FILE`, `EXTRACT`, `SYSTEM_PROFILE` (Summary), `send_time` (Histogram) | None                                                       |
| Host count  | N/A                                                                | `incoming_hosts_counter` (labeled by `source`)                      |

---

## 11. Logging

| Aspect      | Puptoo (`src/puptoo/utils/puptoo_logging.py`)       | Yuptoo (`yuptoo/lib/logger.py`, 82 lines)           |
| ----------- | ---------------------------------------------------- | ---------------------------------------------------- |
| Format      | LogstashFormatterV1                                  | LogstashFormatterV1                                   |
| CloudWatch  | watchtower via boto3                                 | watchtower via boto3                                  |
| Context     | `ContextualFilter` with `threadctx`                  | `ContextualFilter` with `threadctx`                   |
| Fields      | `request_id`, `account`, `org_id`                    | `request_id`, `account`, `org_id`                     |

**Verdict:** Functionally identical. Can be unified trivially.

---

## 12. Dependencies

| Package              | Puptoo (Poetry)     | Yuptoo (Pipfile)    | Notes                              |
| -------------------- | ------------------- | ------------------- | ---------------------------------- |
| Python               | ~3.11               | 3.11                | Same                               |
| confluent-kafka      | 2.13.2              | 2.13.2              | Same                               |
| insights-core        | 3.7.6               | 3.7.4               | Puptoo slightly newer              |
| app-common-python    | 0.2.9               | 0.2.8               | Puptoo slightly newer              |
| prometheus-client    | ^0.25.0             | *                   | Puptoo pinned                      |
| requests             | ^2.32.4             | 2.33.0              | Yuptoo slightly newer              |
| watchtower           | ^3.4.0              | *                   | Both present                       |
| logstash-formatter   | ^0.5.17             | *                   | Both present                       |
| minio                | ^7.2.15             | N/A                 | Puptoo only (S3 upload)            |
| redis                | 7.2.1 (req.txt)     | N/A                 | Puptoo only (retry tracking)       |
| cachecontrol         | <0.14.4             | <0.14.4             | Same                               |
| wheel                | >=0.46.2            | >=0.46.2            | Same                               |
| flake8               | ^7.1.2              | *                   | Both present (dev)                 |
| pytest               | >=8.3.5             | *                   | Both present (dev)                 |
| freezegun            | ^1.5.1              | N/A                 | Puptoo only                        |
| jsonschema           | ^4.23.0             | N/A                 | Puptoo only (schema validation)    |
| pytest-cov           | N/A                 | *                   | Yuptoo only                        |

---

## 13. Tests

| Aspect             | Puptoo                                        | Yuptoo                                          |
| ------------------- | ---------------------------------------------- | ------------------------------------------------ |
| Framework           | pytest + freezegun                             | pytest + pytest-cov                              |
| Test count          | 67 test functions, 41 files                    | 63 test functions, 15 files                      |
| Coverage tooling    | N/A                                            | `.coveragerc` with branch coverage               |
| What's tested       | system_profile rule extraction (37 files), app helpers, message builders, validators | 11 modifiers (48 tests), validators (8), processor (7) |
| Integration tests   | Schema validation against HBI `system_profile.spec.yaml` | N/A                                              |
| CI                  | GitHub Actions: pytest, Anchore, container     | GitHub Actions: flake8+pytest, container, security |

---

## 14. Deployment (ClowdApp)

| Aspect               | Puptoo (`deployment.yaml`, 149 lines)                     | Yuptoo (`clowdapp.yaml`, 89 lines)                       |
| --------------------- | ---------------------------------------------------------- | ---------------------------------------------------------- |
| App name              | `puptoo`                                                   | `yuptoo`                                                    |
| Deployment name       | `processor`                                                | `service`                                                   |
| Min replicas default  | 8                                                          | 1                                                           |
| Command               | `puptoo` (Poetry script)                                   | `python -m main`                                            |
| Dependencies          | `ingress`, `storage-broker`, `host-inventory` (optional)   | `ingress`, `host-inventory` (required)                      |
| IQE plugin            | `puptoo`                                                   | `foreman-rh-cloud`                                          |
| Object store          | Yes (`insights-upload-puptoo` bucket)                      | No                                                          |
| In-memory DB (Redis)  | Yes                                                        | No                                                          |
| Health probes         | HTTP `/metrics` on port 9000                               | None configured                                             |
| Haberdasher logging   | Yes (5 env vars)                                           | No                                                          |
| Topic partitions      | announce: 64, host-ingress: 20, validation: 24, status: 4 | All topics: 1 partition each                                |
| CPU request           | 100m                                                       | 500m                                                        |
| Memory request        | 256Mi (parameter default)                                  | 1Gi                                                         |

---

## 15. Code Size Summary

| Module                  | Puptoo (lines) | Yuptoo (lines) |
| ----------------------- | -------------- | -------------- |
| Entry point + main loop | 314            | 104            |
| Consumer                | 33             | 29             |
| Producer                | 27             | 49             |
| Config                  | 97             | 53             |
| Metrics                 | 76             | 42             |
| Message builders        | 39             | (inline)       |
| Validators              | 15             | 128 (two files)|
| Processing/extraction   | 85             | 181            |
| Host transformation     | (inline)       | ~600 (11 mods) |
| Logging                 | ~80            | 82             |
| S3 upload               | 40             | N/A            |
| system_profile rule     | ~1100          | N/A            |
| **Total (core)**        | **~1906**      | **~1268**      |

---

## 16. Best-of-Both Analysis

The deep re-review identified which patterns are genuinely superior in each codebase. The merged service should adopt the winning pattern from whichever side has it, not simply port one into the other.

### Yuptoo Wins (Adopt)

| Pattern                         | Why it's better                                                                                      | Puptoo equivalent                         |
| ------------------------------- | ---------------------------------------------------------------------------------------------------- | ------------------------------------------ |
| `kafka_auth_config()` helper    | DRY: single function for SASL/SSL, used by consumer + producer                                      | Auth duplicated in `consume.py` + `produce.py` |
| `send_message()` in produce.py  | Correct module boundary; encapsulates delivery callbacks, key selection, metrics                      | `send_message()` lives in 314-line `app.py` |
| Typed exception hierarchy       | `FailDownloadException`, `QPCKafkaMsgException`, etc. enable granular metrics and error routing       | Bare `Exception` everywhere                |
| Modifier plugin architecture    | Composable, testable, extensible transforms; one class per concern                                   | Inline in `handle_message()` god function  |
| `transformed_obj` audit trail   | Logs `removed`, `modified`, `missing_data` per host for debugging                                    | No equivalent                              |
| URL expiry validation           | Fail fast on stale presigned URLs before downloading                                                 | No equivalent                              |
| `max.poll.interval.ms` config   | Prevents consumer rebalance during long QPC processing                                               | Not configured                             |
| Producer `message.max.bytes`    | Handles large multi-host payloads                                                                    | Not configured                             |
| Configurable host TTL by source | `DISCOVERY_HOST_TTL` / `SATELLITE_HOST_TTL`                                                          | Hardcoded 29 hours                         |
| SIGINT handler                  | Graceful shutdown on Ctrl+C (dev ergonomics)                                                         | SIGTERM only                               |

### Puptoo Wins (Keep)

| Pattern                          | Why it's better                                                                                      | Yuptoo equivalent                          |
| -------------------------------- | ---------------------------------------------------------------------------------------------------- | ------------------------------------------- |
| Commit-after-processing          | At-least-once with Redis dedup; crash-safe                                                           | Commits before processing (at-most-once)    |
| Hard exit on poll errors         | Forces pod recreation on MAXPOLL/session timeout                                                     | Logs and continues (can spin broken)        |
| Rich metrics (Summary/Histogram) | Latency SLOs, capacity planning, per-stage timing                                                    | Counters only                               |
| `msgs.py` message builders       | Pure functions, tested, clear contracts                                                              | Inline dicts scattered across modules       |
| `validateCanonicalFacts()` rules | Provider-pair semantics, stricter ID requirements                                                    | Permissive "any single fact suffices"        |
| Archive size guards              | `validate_size()` with 1GB/512MB limits                                                              | No equivalent                               |
| Redis retry gate                 | 3 attempts per request_id, 1h TTL                                                                    | No retry tracking                           |
| S3 yum_updates offload           | Advisor-specific functionality                                                                       | N/A                                          |
| `log_config()` at startup        | Dumps all config vars for deployment debugging                                                       | No equivalent                               |
| Parser test depth                | 37 profile-specific test files                                                                       | Modifier tests only                          |

### Known Bugs to Fix During Merge

| Bug                                          | Service | Location                         |
| -------------------------------------------- | ------- | --------------------------------- |
| `delivery_report()` swapped format args      | Puptoo  | `app.py:177-181`                  |
| `handle_retries()` exception never formats   | Puptoo  | `app.py:89`                       |
| `clean_macs()` dead code path                | Puptoo  | `app.py:244-245`                  |
| Bare `except:` in upload, config, app        | Puptoo  | Multiple files                    |
| Inconsistent boolean parsing in config       | Puptoo  | `config.py` (3 different patterns)|
| `CONSUMER_ASSIGNMENTS` metric never populated| Puptoo  | `app.py:24-26`                    |
| Early commit before processing               | Yuptoo  | `main.py:78`                      |
| Per-host `importlib`/`inspect` in hot loop   | Yuptoo  | `report_processor.py:46-51`       |
| No modifier ordering guarantee               | Yuptoo  | `modifiers/__init__.py`            |
| `Modifier` ABC signature mismatch            | Yuptoo  | `processor/utils.py:78-80`        |
| Per-host validation message spam             | Yuptoo  | `report_processor.py:55-60`       |
| `download_report()` has no request timeout   | Yuptoo  | `processor/utils.py:50`           |
