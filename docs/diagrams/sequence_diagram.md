# Sequence Diagrams

> **Living diagram, last verified against code: 2026-08-05.** Advisor sequence's participants confirmed present in `insights-puptoo` (Phase 1 complete). The QPC sequence describes planned behavior, Phase 2 hasn't built it yet, re-verify once it lands.

End-to-end message processing for **advisor** and **qpc** service headers through the unified consumer application.

## Advisor Message Processing

```mermaid
sequenceDiagram
    participant Kafka
    participant app as app.py
    participant Registry as HandlerRegistry
    participant Handler as AdvisorHandler
    participant Core as insights-core
    participant Validators
    participant MQ as mq/produce
    participant Redis
    participant S3

    Kafka->>app: poll()
    app->>Registry: get_handler("advisor")
    Registry-->>app: AdvisorHandler

    app->>Redis: retry check
    alt retry exhausted
        Redis-->>app: RetryExhaustedException
        app->>MQ: send_message(upload.validation)
    else proceed
        Redis-->>app: ok

        app->>Handler: process(msg, extra)
        Handler->>Handler: download archive
        Handler->>Core: extract()
        Core-->>Handler: facts
        Handler->>Core: postprocess()
        Handler->>Validators: validateCanonicalFacts()
        Validators-->>Handler: validated facts

        Handler->>S3: upload yum_updates
        S3-->>Handler: ok

        Handler-->>app: facts dict
        app->>Handler: build_hbi_messages(facts, msg)
        Handler-->>app: inv_messages

        app->>MQ: send_message(host-ingress)
        app->>MQ: send_message(payload-status)
        app->>Kafka: commit offset
    end
```

## QPC Message Processing

```mermaid
sequenceDiagram
    participant Kafka
    participant app as app.py
    participant Registry as HandlerRegistry
    participant Handler as QPCHandler
    participant QPCVal as QPC Validators
    participant Report as ReportProcessor
    participant Pipeline as ModifierPipeline
    participant MQ as mq/produce
    participant Redis

    Kafka->>app: poll()
    app->>Registry: get_handler("qpc")
    Registry-->>app: QPCHandler

    app->>Redis: retry check
    alt retry exhausted
        Redis-->>app: RetryExhaustedException
        app->>MQ: send_message(upload.validation)
    else proceed
        Redis-->>app: ok

        app->>Handler: process(msg, extra)
        Handler->>QPCVal: validate_qpc_message() URL expiry
        QPCVal-->>Handler: ok

        Handler->>Handler: download_report() tar
        Handler->>QPCVal: validate_metadata_file()
        QPCVal-->>Handler: metadata ok

        Handler->>Report: process report
        loop each slice
            loop each host
                Report->>Pipeline: run 11 modifiers
                Pipeline-->>Report: transformed host
                Report->>Report: has_canonical_facts()
            end
        end
        Report-->>Handler: per-host facts

        Handler-->>app: facts per host
        app->>Handler: build_hbi_messages(facts, msg)
        Handler-->>app: inv_messages (one per valid host)

        loop each inv_message
            app->>MQ: send_message(host-ingress)
            app->>MQ: send_message(payload-status)
        end
        app->>Kafka: commit offset
    end
```
