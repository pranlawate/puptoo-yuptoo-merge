# HBI Reporter Name Impact Analysis

Investigation into how `yupana`, `puptoo`, and `yuptoo` names are embedded across codebases, and the scope of renaming them after the merge.

> **Decision Needed:** Should the merged service adopt a clean new reporter name, or keep existing names for backward compatibility? Review Scenarios A, B, and C before creating JIRA work.

---

## How Reporters Work in HBI

HBI tracks which service last reported a host via the `reporter` field on the Host model. It also maintains `per_reporter_staleness`, a JSON column mapping each reporter name to its last check-in timestamp.

HBI already went through one reporter transition: from `yupana` to `satellite`/`discovery`. The mechanism lives in `app/models/constants.py`:

```python
NEW_TO_OLD_REPORTER_MAP = {"satellite": "yupana", "discovery": "yupana"}
OLD_TO_NEW_REPORTER_MAP = {"yupana": ("satellite", "discovery")}
```

When a new reporter checks in, HBI removes the old reporter entry from `per_reporter_staleness` and writes the new one (`host.py:463-466`).

---

## What Each Service Sends Today

| Service | `reporter` field | Facts namespace | `host_id` key | Kafka topic |
|---------|-----------------|-----------------|---------------|-------------|
| Puptoo | `"puptoo"` | (none, uses insights-core) | N/A | `host-ingress-p1` |
| Yuptoo | `"discovery"` or `"satellite"` | `"yupana"` | `yupana_host_id` | `platform.inventory.host-ingress` |

### Source Evidence

**Puptoo** (`src/puptoo/app.py:243`):

```python
facts["reporter"] = "puptoo"
```

**Yuptoo** (`yuptoo/modifiers/add_host_facts.py:31-42`):

```python
yuptoo_facts = {'namespace': 'yupana',
                'facts': {'yupana_host_id': host['yupana_host_id'], ...}}
host['reporter'] = 'discovery' if request_obj['source'] == "discovery" else 'satellite'
```

> **Key Finding:** The `reporter` field is **not** set to `yupana`. Yuptoo sends `discovery` or `satellite`. The `yupana` name appears only in the **facts namespace** and the **host ID key**. HBI's mapping already handles the `yupana` to `satellite`/`discovery` transition.

---

## HBI Codebase: Where the Names Appear

### Production Source Code

| File | Name | Reference | Impact |
|------|------|-----------|--------|
| `app/models/constants.py:13-14` | `yupana` | `NEW_TO_OLD_REPORTER_MAP` and `OLD_TO_NEW_REPORTER_MAP` | Reporter transition mapping |
| `app/models/host.py:42` | `puptoo` | `DISPLAY_NAME_PRIORITY_REPORTERS = {"puptoo", "API"}` | Display name precedence logic |

### API Specifications

| File | Names | Reference |
|------|-------|-----------|
| `swagger/api.spec.yaml` | `yupana`, `puptoo`, `!yupana`, `!puptoo` | `registered_with` filter enum values |
| `swagger/host_events.spec.yaml` | `puptoo`, `yupana` | Example values for `reporter` field (2 locations) |
| `swagger/openapi.json` | `yupana`, `puptoo` | Generated OpenAPI (mirrors api.spec, 4 refs) |

### Test and IQE Plugin Code

| Area | `puptoo` refs | `yupana` refs | Files touched |
|------|:---:|:---:|:---:|
| Unit/integration tests (`tests/`) | ~100 | ~90 | 12 files |
| IQE plugin (modeling, fixtures, tests) | ~50 | ~50 | 10 files |
| `utils/payloads.py` (test payloads) | 2 | 1 | 1 file |
| **Total** | **~152** | **~141** | **23 files** |

Key IQE constant (`datagen_utils.py:31-33`):

```python
_CORRECT_REGISTERED_WITH_VALUES = [
    "puptoo",
    "yupana",
    "rhsm-conduit",
```

---

## Facts Namespace Considerations

Yuptoo stores host facts under `namespace: 'yupana'`. In HBI, facts are stored per namespace and replaced via `replace_facts_in_namespace()` (`host.py:476-478`). Changing the namespace creates a **data orphaning problem**: existing hosts retain facts under `yupana`, while new uploads write to the new namespace. The old facts are never updated again.

---

## Scenario A: Keep Existing Names

**Sprint impact: 0**

The merged service continues using `reporter: "puptoo"` for insights-client uploads and `reporter: "discovery"/"satellite"` for QPC uploads. Facts namespace stays `yupana`. HBI requires zero changes.

| Pro | Con |
|-----|-----|
| Zero additional work | Legacy names persist in production |
| No HBI coordination needed | "yupana" confuses future engineers |
| No data migration risk | API consumers still filter by old names |

---

## Scenario B: Full Clean Rename

**Sprint impact: 2-3 additional sprints (~15-22 story points)**

Remove all traces of `yupana`, `puptoo`, and `yuptoo` from all codebases.

| Work area | Changes | Estimate |
|-----------|---------|----------|
| Merged service | Change `reporter`, facts `namespace`, `yupana_host_id` key, tests | 2 pts |
| HBI `constants.py` | Add `{"puptoo": "<new>"}` to reporter map | 1 pt |
| HBI `host.py` | Update `DISPLAY_NAME_PRIORITY_REPORTERS` | 1 pt |
| HBI API spec | Add new reporter to enum, add negation, regenerate openapi.json | 2 pts |
| HBI tests | Update ~190 references across unit/integration tests | 3-5 pts |
| HBI IQE plugin | Update `_CORRECT_REGISTERED_WITH_VALUES`, ~100 refs | 3-5 pts |
| Data migration | `per_reporter_staleness` transition (handled by map). Facts namespace orphaning (needs migration or dual-namespace). | 3-5 pts |
| API backward compat | `?registered_with=puptoo` and `?registered_with=yupana` are public API: must keep as aliases or break consumers | 2-3 pts |

**Risks:**
- Facts namespace change orphans existing host data
- API enum is a public contract: removing old values breaks external consumers
- Touches HBI code owned by a different team: requires buy-in and joint sprint planning

---

## Scenario C: Surgical Rename (Recommended)

**Sprint impact: ~1 additional sprint (~5-7 story points)**

Change the **reporter name** only. Leave the facts namespace as `yupana` (historical artifact, not user-facing). HBI's existing mapping mechanism handles the transition.

| Work area | Changes | Estimate |
|-----------|---------|----------|
| Merged service | Change `reporter` from `"puptoo"` to new name for insights-client path. QPC path already sends `"discovery"`/`"satellite"`, no change. | 1 pt |
| HBI `constants.py` | Add `"puptoo"` to `NEW_TO_OLD_REPORTER_MAP` | 1 pt |
| HBI `host.py` | Add new name to `DISPLAY_NAME_PRIORITY_REPORTERS` | 0.5 pt |
| HBI API spec | Add new reporter to enum. Keep `puptoo`/`yupana` for backward compat. | 1 pt |
| Facts namespace | **Leave as `yupana`**: no data migration, no orphaned facts | 0 |
| HBI tests + IQE | Add new reporter to test matrices. Old tests still valid. | 2-3 pts |

**Why this works:** HBI already has the infrastructure for reporter transitions (the `NEW_TO_OLD_REPORTER_MAP`). We follow the same pattern used when `yupana` was transitioned to `satellite`/`discovery`. Old API consumers keep working. No data migration needed. A full purge (Scenario B) can be done as a follow-up after the merge is stable.

---

## Discussion Points

1. The `reporter` field from yuptoo is already clean: it sends `discovery`/`satellite`, not `yupana`. The `yupana` name is only in the facts namespace and host ID key.
2. Does the facts namespace *need* to change? It is not user-facing. Changing it creates a data orphaning problem for existing hosts.
3. If we go with Scenario C (surgical rename), the merged service just needs to send `reporter: "<new_name>"` and HBI adds one line to the reporter map. This follows HBI's established transition pattern.
4. The `?registered_with=puptoo` and `?registered_with=yupana` API filter values are a public contract. Any rename must maintain backward compatibility.

---

## Related

- [Merge Proposal](Puptoo_Yuptoo_Merge_Proposal.md)
- [Task Breakdown](Puptoo_Yuptoo_Merge_Tasks.md)
- [Codebase Comparison](Puptoo_Yuptoo_Comparison.md)
- JIRA: [RHINENG-27900](https://redhat.atlassian.net/browse/RHINENG-27900) (naming decision)
