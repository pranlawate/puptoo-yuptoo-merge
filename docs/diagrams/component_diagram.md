# Component Diagram: As-Is vs To-Be

Architecture comparison for merging **yuptoo** and **insights-puptoo** Kafka consumers into a single unified service.

## As-Is: Two Separate Services

Two independent deployments consume the same input topic with different consumer groups, dashboards, and CI/CD pipelines.

```mermaid
flowchart TB
    subgraph input["Kafka Input"]
        announce["platform.upload.announce"]
    end

    subgraph puptoo_svc["insights-puptoo (8 replicas)"]
        cg_puptoo["Consumer Group: insights-puptoo"]
        handlers_p["Handlers: advisor, compliance, malware-detection"]
        redis_p["Redis (retry state)"]
        minio_p["MinIO / S3 (yum_updates)"]
        dash_p["Dashboard (puptoo)"]
        cicd_p["CI/CD Pipeline (puptoo)"]
    end

    subgraph yuptoo_svc["yuptoo (1 replica)"]
        cg_yuptoo["Consumer Group: yuptoo"]
        handlers_y["Handler: qpc"]
        dash_y["Dashboard (yuptoo)"]
        cicd_y["CI/CD Pipeline (yuptoo)"]
    end

    subgraph output["Kafka Output Topics"]
        host_ingress["host-ingress"]
        payload_status["payload-status"]
        upload_validation["upload.validation"]
    end

    subgraph downstream["Downstream"]
        hbi["Host Inventory (HBI)"]
    end

    announce --> cg_puptoo
    announce --> cg_yuptoo

    cg_puptoo --> handlers_p
    handlers_p --> redis_p
    handlers_p --> minio_p
    handlers_p --> host_ingress
    handlers_p --> payload_status
    handlers_p --> upload_validation

    cg_yuptoo --> handlers_y
    handlers_y --> host_ingress
    handlers_y --> payload_status
    handlers_y --> upload_validation

    host_ingress --> hbi

    puptoo_svc --- dash_p
    puptoo_svc --- cicd_p
    yuptoo_svc --- dash_y
    yuptoo_svc --- cicd_y
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

```mermaid
flowchart TB
    subgraph input["Kafka Input"]
        announce["platform.upload.announce"]
    end

    subgraph unified["insights-puptoo unified (8+ replicas)"]
        cg_unified["Consumer Group: insights-puptoo (single)"]
        dispatch["Handler Dispatch"]
        h_advisor["AdvisorHandler"]
        h_compliance["ComplianceHandler"]
        h_malware["MalwareDetectionHandler"]
        h_qpc["QPCHandler"]
        redis_u["Redis (retry state)"]
        minio_u["MinIO / S3 (yum_updates)"]
        dash_u["Dashboard (unified)"]
        cicd_u["CI/CD Pipeline (unified)"]
    end

    subgraph output["Kafka Output Topics"]
        host_ingress["host-ingress"]
        payload_status["payload-status"]
        upload_validation["upload.validation"]
    end

    subgraph downstream["Downstream"]
        hbi["Host Inventory (HBI)"]
    end

    announce --> cg_unified
    cg_unified --> dispatch
    dispatch --> h_advisor
    dispatch --> h_compliance
    dispatch --> h_malware
    dispatch --> h_qpc

    h_advisor --> redis_u
    h_compliance --> redis_u
    h_malware --> redis_u
    h_qpc --> redis_u

    h_advisor --> minio_u
    h_compliance --> minio_u

    h_advisor --> host_ingress
    h_compliance --> host_ingress
    h_malware --> host_ingress
    h_qpc --> host_ingress

    h_advisor --> payload_status
    h_compliance --> payload_status
    h_malware --> payload_status
    h_qpc --> payload_status

    h_advisor --> upload_validation
    h_compliance --> upload_validation
    h_malware --> upload_validation
    h_qpc --> upload_validation

    host_ingress --> hbi

    unified --- dash_u
    unified --- cicd_u
```

| Aspect              | Unified service                         |
| ------------------- | --------------------------------------- |
| Replicas            | 8+                                      |
| Service headers     | advisor, compliance, malware-detection, qpc |
| Redis / MinIO       | Shared by all handlers                  |
| Consumer group      | Single                                  |
| Dashboard / CI/CD   | Single                                  |
