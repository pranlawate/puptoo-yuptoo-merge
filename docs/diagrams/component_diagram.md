# Component Diagram: As-Is vs To-Be

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

## To-Be: Unified Service

Single merged deployment handles all service types via handler dispatch.

> **Rendering:** If this diagram does not render on GitHub, paste the Mermaid source into [mermaid.live](https://mermaid.live) to view it.

```mermaid
architecture-beta
    group kafka_in(cloud)[Kafka Input]
    group unified(server)[Unified Puptoo 8 pods]
    group kafka_out(cloud)[Kafka Output]

    service announce(disk)[Announce Topic] in kafka_in
    service dispatch(server)[Handler Dispatch] in unified
    service h_adv(server)[AdvisorHandler] in unified
    service h_qpc(server)[QPCHandler] in unified
    service redis_u(database)[Redis] in unified
    service hi(disk)[Host Ingress] in kafka_out
    service ps(disk)[Payload Status] in kafka_out
    service hbi(server)[Host Inventory]

    announce:R --> L:dispatch
    dispatch:R --> L:h_adv
    h_adv:B --> T:h_qpc
    redis_u:T -- B:dispatch
    h_adv:R --> L:hi
    h_qpc:R --> L:hi
    hi:R --> L:hbi
    hi:B -- T:ps
```

| Aspect              | Unified service                         |
| ------------------- | --------------------------------------- |
| Replicas            | 8+                                      |
| Service headers     | advisor, compliance, malware-detection, qpc |
| Redis / MinIO       | Shared by all handlers                  |
| Consumer group      | Single                                  |
| Dashboard / CI/CD   | Single                                  |
