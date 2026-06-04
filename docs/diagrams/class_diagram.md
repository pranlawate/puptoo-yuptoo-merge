# UML Class Diagram: Handlers and Modifiers

Handler hierarchy for service-type dispatch and QPC report transformation via the modifier pipeline.

```mermaid
classDiagram
    direction TB

    class BaseHandler {
        <<abstract>>
        +process(msg, extra) dict*
        +build_hbi_messages(facts, msg) list~dict~*
    }

    class AdvisorHandler {
        +process() downloads archive, insights-core, postprocess, validate facts
        +build_hbi_messages() inv_message with platform_metadata
    }

    class ComplianceHandler {
        +process() forwards msg metadata as facts
        +build_hbi_messages() inv_message
    }

    class QPCHandler {
        +process() validates QPC, downloads tar, ReportProcessor + modifiers
        +build_hbi_messages() one inv_message per valid host
    }

    class Modifier {
        <<abstract>>
        +run(host, transformed_obj, **kwargs)*
    }

    class TransformTags
    class TransformNetworkInterfaces
    class TransformMacAddresses
    class TransformCloudProvider
    class TransformOsRelease
    class TransformOsKernelVersion
    class TransformInstalledPackages
    class TransformIpAddresses
    class RemoveDisplayName
    class RemoveInvalidBiosUUID
    class AddHostFacts

    class PuptooError {
        <<exception>>
    }

    class FailDownloadException
    class FailExtractException
    class QPCKafkaMsgException
    class QPCReportException
    class RetryExhaustedException

    BaseHandler <|-- AdvisorHandler
    BaseHandler <|-- ComplianceHandler
    BaseHandler <|-- QPCHandler

    Modifier <|-- TransformTags
    Modifier <|-- TransformNetworkInterfaces
    Modifier <|-- TransformMacAddresses
    Modifier <|-- TransformCloudProvider
    Modifier <|-- TransformOsRelease
    Modifier <|-- TransformOsKernelVersion
    Modifier <|-- TransformInstalledPackages
    Modifier <|-- TransformIpAddresses
    Modifier <|-- RemoveDisplayName
    Modifier <|-- RemoveInvalidBiosUUID
    Modifier <|-- AddHostFacts

    QPCHandler ..> Modifier : uses pipeline

    PuptooError <|-- FailDownloadException
    PuptooError <|-- FailExtractException
    PuptooError <|-- QPCKafkaMsgException
    PuptooError <|-- QPCReportException
    PuptooError <|-- RetryExhaustedException

    AdvisorHandler ..> FailDownloadException : raises
    AdvisorHandler ..> FailExtractException : raises
    QPCHandler ..> QPCKafkaMsgException : raises
    QPCHandler ..> QPCReportException : raises
    BaseHandler ..> RetryExhaustedException : raises
```

## Summary

| Layer       | Role                                                                 |
| ----------- | -------------------------------------------------------------------- |
| BaseHandler | Abstract `process()` and `build_hbi_messages()` contract             |
| Handlers    | Service-specific ingestion and HBI message construction              |
| Modifier    | Per-host QPC fact normalization before canonical-facts check         |
| PuptooError | Typed failures for download, extract, QPC validation, retry exhaustion |
