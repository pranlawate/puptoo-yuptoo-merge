from .base import BaseHandler


class ComplianceHandler(BaseHandler):
    def process(self, msg: dict, extra: dict) -> dict:
        return msg.get("metadata", {})

    def build_hbi_messages(self, facts: dict, msg: dict) -> list[dict]:
        return [{"metadata": facts, "request_id": msg.get("request_id")}]
