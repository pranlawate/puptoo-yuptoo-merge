from .advisor import AdvisorHandler
from .compliance import ComplianceHandler
from .qpc import QPCHandler

_HANDLERS = {
    "advisor": AdvisorHandler(),
    "compliance": ComplianceHandler(),
    "malware-detection": ComplianceHandler(),
    "qpc": QPCHandler(),
}


def get_handler(service: str):
    return _HANDLERS.get(service)
