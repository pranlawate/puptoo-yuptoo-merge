class PuptooError(Exception):
    """Base for all puptoo errors."""


class FailDownloadException(PuptooError):
    """Archive download failed."""


class FailExtractException(PuptooError):
    """Archive extraction failed."""


class QPCKafkaMsgException(PuptooError):
    """Invalid QPC Kafka message."""


class QPCReportException(PuptooError):
    """QPC report has zero valid hosts."""


class RetryExhaustedException(PuptooError):
    """Redis retry limit reached."""
