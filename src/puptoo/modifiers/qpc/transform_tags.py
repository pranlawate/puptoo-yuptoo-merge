from puptoo.modifiers.base import Modifier

_BOOL_STRINGS = frozenset({"true", "false"})


class TransformTags(Modifier):
    def run(self, host: dict, transformed_obj: dict, **kwargs) -> None:
        for tag in host.get("tags", []):
            if not isinstance(tag, dict):
                continue
            value = tag.get("value")
            if not isinstance(value, str):
                continue
            if len(value) > 250:
                tag["value"] = value[:250]
            if value.lower() in _BOOL_STRINGS:
                tag["value"] = value.lower() == "true"
