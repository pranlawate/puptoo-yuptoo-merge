import time

from puptoo.modifiers.base import Modifier

_STALE_DAYS = 7
_WARNING_DAYS = 3


class AddHostFacts(Modifier):
    def run(self, host: dict, transformed_obj: dict, **kwargs) -> None:
        now = int(time.time())
        host["stale_timestamp"] = now + _STALE_DAYS * 86400
        host["reporter"] = kwargs.get("reporter", "qpc")
        host["stale_warning_timestamp"] = now + _WARNING_DAYS * 86400
