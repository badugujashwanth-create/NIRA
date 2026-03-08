from __future__ import annotations

import importlib
import logging
import pkgutil
from types import ModuleType


logger = logging.getLogger(__name__)


class SkillAutoLoader:
    def __init__(self, package: str = "nira_agent.skills") -> None:
        self.package = package
        self.loaded_modules: list[str] = []

    def load(self, registry, executors) -> list[str]:
        try:
            package = importlib.import_module(self.package)
        except Exception as exc:
            logger.error("Failed to import skills package %s: %s", self.package, exc)
            return []

        discovered: list[str] = []
        for module_info in pkgutil.iter_modules(package.__path__, f"{self.package}."):
            module_name = module_info.name
            try:
                mod = importlib.import_module(module_name)
                self._register_from_module(mod, registry, executors)
                discovered.append(module_name)
            except Exception as exc:
                logger.exception("Failed loading skill module %s: %s", module_name, exc)
        self.loaded_modules = discovered
        return discovered

    @staticmethod
    def _register_from_module(module: ModuleType, registry, executors) -> None:
        register_fn = getattr(module, "register", None)
        if callable(register_fn):
            register_fn(registry, executors)

