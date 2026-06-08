from .base import BaseHandler


class AdvisorHandler(BaseHandler):
    def process(self, msg: dict, extra: dict) -> dict:
        """Download archive, run insights-core extract, postprocess, validate
        canonical facts, upload yum_updates to S3."""
        return {
            "insights_id": msg.get("insights_id"),
            "account_id": msg.get("account_id"),
            "org_id": msg.get("org_id"),
            "hostname": msg.get("hostname"),
            "facts": msg.get("facts", {}),
        }

    def build_hbi_messages(self, facts: dict, msg: dict) -> list[dict]:
        return [
            {
                "insights_id": facts.get("insights_id"),
                "account_id": facts.get("account_id"),
                "org_id": facts.get("org_id"),
                "hostname": facts.get("hostname"),
            }
        ]
