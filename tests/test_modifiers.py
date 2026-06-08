import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from puptoo.modifiers import get_modifiers
from puptoo.modifiers.base import Modifier
from puptoo.modifiers.qpc.add_host_facts import AddHostFacts
from puptoo.modifiers.qpc.transform_tags import TransformTags


def test_get_modifiers_non_empty():
    modifiers = get_modifiers()
    assert len(modifiers) > 0


def test_get_modifiers_are_modifier_instances():
    for modifier in get_modifiers():
        assert isinstance(modifier, Modifier)


def test_transform_tags_truncates_long_values():
    host = {"tags": [{"name": "t", "value": "a" * 300}]}
    TransformTags().run(host, {})
    assert len(host["tags"][0]["value"]) == 250


def test_transform_tags_coerces_boolean_strings():
    host = {"tags": [{"name": "a", "value": "true"}, {"name": "b", "value": "false"}]}
    TransformTags().run(host, {})
    assert host["tags"][0]["value"] is True
    assert host["tags"][1]["value"] is False


def test_add_host_facts_adds_required_fields():
    host = {}
    AddHostFacts().run(host, {}, reporter="unit-test")
    assert "stale_timestamp" in host
    assert host["reporter"] == "unit-test"
    assert "stale_warning_timestamp" in host


def test_modifier_ordering_consistent():
    first = [type(m).__name__ for m in get_modifiers()]
    second = [type(m).__name__ for m in get_modifiers()]
    assert first == second
    assert first == ["AddHostFacts", "TransformTags"]
