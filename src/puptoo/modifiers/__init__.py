import importlib
import inspect
import pkgutil

from .base import Modifier

_REGISTRY: list[Modifier] = []
_initialized = False


def register_modifiers(package_path: str, package_name: str):
    global _initialized
    if _initialized:
        return
    for _, module_name, _ in pkgutil.walk_packages([package_path]):
        module = importlib.import_module(f"{package_name}.{module_name}")
        for _, cls in inspect.getmembers(module, inspect.isclass):
            if issubclass(cls, Modifier) and cls is not Modifier:
                _REGISTRY.append(cls())
    _initialized = True


def get_modifiers() -> list[Modifier]:
    if not _initialized:
        import os

        qpc_path = os.path.join(os.path.dirname(__file__), "qpc")
        register_modifiers(qpc_path, "puptoo.modifiers.qpc")
    return _REGISTRY
