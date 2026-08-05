# Data Flow Diagrams

> **Living diagram, last spot-checked against code: 2026-08-05.** The Advisor/Compliance path's major steps (archive download, extraction, postprocessing, yum_updates handling) were confirmed present in the current `insights-puptoo` codebase (Phase 1 complete); this was a structural spot-check, not a full line-by-line trace. The QPC path below describes planned behavior, Phase 2 hasn't built it yet, re-verify once it lands.

Message lifecycle from `platform.upload.announce` through processing to Kafka output topics. Error paths route to `upload.validation`.

## Advisor / Compliance Path

Advisor downloads and extracts archives; compliance forwards metadata without download/extract.

```mermaid
flowchart TB
    subgraph input["Input"]
        announce["platform.upload.announce"]
    end

    poll["consumer.poll()"]
    parse["parse service header"]
    redis_check["Redis retry check"]
    retry_exhausted{"Retry exhausted?"}

    subgraph advisor_path["Advisor Path"]
        advisor_handler["AdvisorHandler"]
        download["download archive"]
        extract["insights-core extract()"]
        postprocess["postprocess()"]
        validate["validateCanonicalFacts()"]
        s3_upload["S3 yum_updates upload"]
    end

    subgraph compliance_path["Compliance Path"]
        compliance_handler["ComplianceHandler"]
        forward_meta["forward msg metadata as facts"]
    end

    build_inv["build inv_message()"]
    send_hbi["send_message() to host-ingress"]
    tracker["tracker_message() to payload-status"]
    commit["commit offset"]

    subgraph errors["Error Path"]
        upload_val["upload.validation"]
    end

    announce --> poll
    poll --> parse
    parse --> redis_check
    redis_check --> retry_exhausted
    retry_exhausted -->|yes| upload_val
    retry_exhausted -->|no| advisor_handler
    retry_exhausted -->|no| compliance_handler

    advisor_handler --> download
    download -->|fail| upload_val
    download --> extract
    extract -->|fail| upload_val
    extract --> postprocess
    postprocess --> validate
    validate -->|invalid| upload_val
    validate --> s3_upload
    s3_upload --> build_inv

    compliance_handler --> forward_meta
    forward_meta --> build_inv

    build_inv --> send_hbi
    send_hbi --> tracker
    tracker --> commit
```

## QPC Path

QPC validates message and report, runs an 11-modifier pipeline per host, then emits inventory messages.

```mermaid
flowchart TB
    subgraph input["Input"]
        announce["platform.upload.announce"]
    end

    poll["consumer.poll()"]
    parse["parse service header"]
    redis_check["Redis retry check"]
    retry_exhausted{"Retry exhausted?"}

    subgraph qpc_path["QPC Path"]
        qpc_handler["QPCHandler"]
        validate_msg["validate_qpc_message() URL expiry"]
        download_tar["download_report() tar"]
        validate_meta["validate_metadata_file()"]
        iterate_slices["iterate slices"]
        iterate_hosts["for each host"]
        modifiers["modifier pipeline 11 modifiers"]
        canonical["has_canonical_facts()"]
    end

    build_inv["build inv_message()"]
    send_hbi["send_message() to host-ingress"]
    tracker["tracker_message() to payload-status"]
    commit["commit offset"]

    subgraph errors["Error Path"]
        upload_val["upload.validation"]
    end

    announce --> poll
    poll --> parse
    parse --> redis_check
    redis_check --> retry_exhausted
    retry_exhausted -->|yes| upload_val
    retry_exhausted -->|no| qpc_handler

    qpc_handler --> validate_msg
    validate_msg -->|invalid| upload_val
    validate_msg --> download_tar
    download_tar -->|fail| upload_val
    download_tar --> validate_meta
    validate_meta -->|invalid| upload_val
    validate_meta --> iterate_slices
    iterate_slices --> iterate_hosts
    iterate_hosts --> modifiers
    modifiers --> canonical
    canonical -->|no facts| upload_val
    canonical --> build_inv
    build_inv --> send_hbi
    send_hbi --> tracker
    tracker --> commit

    iterate_hosts -->|next host| iterate_hosts
    iterate_slices -->|next slice| iterate_slices
```

### Modifier Pipeline (QPC)

Applied per host in order: `TransformTags`, `TransformNetworkInterfaces`, `TransformMacAddresses`, `TransformCloudProvider`, `TransformOsRelease`, `TransformOsKernelVersion`, `TransformInstalledPackages`, `TransformIpAddresses`, `RemoveDisplayName`, `RemoveInvalidBiosUUID`, `AddHostFacts`.
