from abc import ABC, abstractmethod


class BaseHandler(ABC):
    @abstractmethod
    def process(self, msg: dict, extra: dict) -> dict:
        ...

    @abstractmethod
    def build_hbi_messages(self, facts: dict, msg: dict) -> list[dict]:
        ...
