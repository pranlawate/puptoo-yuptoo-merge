from puptoo.modifiers import get_modifiers

from .base import BaseHandler


class QPCHandler(BaseHandler):
    def process(self, msg: dict, extra: dict) -> dict:
        host = dict(msg.get("host", {}))
        if "tags" in msg and "tags" not in host:
            host["tags"] = msg["tags"]
        transformed_obj: dict = {}
        for modifier in get_modifiers():
            modifier.run(host, transformed_obj, **extra)
        return host

    def build_hbi_messages(self, facts: dict, msg: dict) -> list[dict]:
        return [{"host": facts, "org_id": msg.get("org_id")}]
