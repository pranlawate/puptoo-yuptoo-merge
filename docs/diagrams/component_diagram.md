# Component Diagram: As-Is vs To-Be

> **Living diagram, last verified against code: 2026-08-05.** Describes the actual system architecture, not a past decision, so it's updated as the real thing changes (unlike the frozen historical docs elsewhere in this repo). Re-verify once Phase 2 lands `QPCHandler`.

Architecture comparison for merging **yuptoo** and **insights-puptoo** Kafka consumers into a single unified service.

## As-Is: Two Separate Services

Two independent deployments consume the same input topic with different consumer groups, dashboards, and CI/CD pipelines.

> **Rendering:** If this diagram does not render on GitHub, paste the Mermaid source into [mermaid.live](https://mermaid.live) to view it.

```mermaid
architecture-beta
    group kafka_in(cloud)[Kafka Input]
    group puptoo_svc(server)[Puptoo 8 pods]
    group yuptoo_svc(server)[Yuptoo 1 pod]
    group kafka_out(cloud)[Kafka Output]

    service announce(disk)[Announce Topic] in kafka_in
    service handlers_p(server)[Advisor Compliance Malware] in puptoo_svc
    service redis_p(database)[Redis] in puptoo_svc
    service handlers_y(server)[QPC Handler] in yuptoo_svc
    service hi(disk)[Host Ingress] in kafka_out
    service ps(disk)[Payload Status] in kafka_out
    service hbi(server)[Host Inventory]

    announce:R --> L:handlers_y
    announce:B --> T:handlers_p
    handlers_p:B -- T:redis_p
    handlers_p:R --> L:hi
    handlers_y:B --> T:hi
    hi:R --> L:hbi
    hi:B -- T:ps
```

| Aspect              | insights-puptoo              | yuptoo        |
| ------------------- | ---------------------------- | ------------- |
| Replicas            | 8                            | 1             |
| Service headers     | advisor, compliance, malware-detection | qpc |
| Redis               | Yes (retry)                  | No            |
| MinIO / S3          | Yes (yum_updates)            | No            |
| Consumer group      | Separate                     | Separate      |
| Dashboard / CI/CD   | Separate                     | Separate      |

## To-Be: Unified Codebase, Multi-Deployment

> [!note] Corrected 2026-08-05
> The version of this diagram below (single deployment, single consumer group) was superseded before implementation began. The team settled on a **multi-deployment** model instead: one codebase and container image, but two independent Kubernetes Deployments, each with its own consumer group, replica count, and `ENABLED_HANDLERS` filter. This preserves the current 72-consumer topology (64 + 8) instead of collapsing it into one 64-consumer group, which would have reduced effective throughput. See [README.md](../../README.md) for the current architecture.

One codebase and container image, deployed as two independent instances filtered by `ENABLED_HANDLERS`.

> **Rendering:** If this diagram does not render on GitHub, paste the Mermaid source into [mermaid.live](https://mermaid.live) to view it.

```mermaid
architecture-beta
    group kafka_in(cloud)[Kafka Input]
    group puptoo_dep(server)[Puptoo Deployment 64 pods]
    group yuptoo_dep(server)[Yuptoo Deployment 8 pods]
    group kafka_out(cloud)[Kafka Output]

    service announce(disk)[Announce Topic] in kafka_in
    service h_adv(server)[AdvisorHandler ComplianceHandler] in puptoo_dep
    service redis_p(database)[Redis] in puptoo_dep
    service h_qpc(server)[QPCHandler] in yuptoo_dep
    service hi(disk)[Host Ingress] in kafka_out
    service ps(disk)[Payload Status] in kafka_out
    service hbi(server)[Host Inventory]

    announce:R --> L:h_adv
    announce:B --> T:h_qpc
    h_adv:B -- T:redis_p
    h_adv:R --> L:hi
    h_qpc:R --> L:hi
    hi:R --> L:hbi
    hi:B -- T:ps
```

| Aspect              | Puptoo deployment                       | Yuptoo deployment |
| ------------------- | ---------------------------------------- | ------------------ |
| Replicas            | 64                                       | 8                   |
| Service headers     | advisor, compliance, malware-detection   | qpc                 |
| Consumer group      | `puptoo-upload-processor`                | `yuptoo-upload-processor` |
| Redis / MinIO       | Yes (advisor path only)                  | No                  |
| Container image     | Same image, same repo                    | Same image, same repo |
| Dashboard / CI/CD   | Single (shared codebase, one pipeline)   | Single (shared codebase, one pipeline) |
