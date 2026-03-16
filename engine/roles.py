from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)

_DEFAULT_CONFIG = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "role_config.json"
)


class RoleLayer(Enum):
    DISPATCHER = "dispatcher"
    REVIEWER = "reviewer"
    EXECUTOR = "executor"
    DISPATCHER_SUB = "dispatcher_sub"
    EXECUTOR_SUB = "executor_sub"


@dataclass
class RoleDefinition:
    name: str
    display_name: str
    layer: RoleLayer
    capabilities: list[str] = field(default_factory=list)
    review_scope: list[str] = field(default_factory=list)
    wip_limit: int = 1
    allowed_callees: list[str] = field(default_factory=list)
    cron_jobs: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)


class RoleRegistry:
    def __init__(self, config_path: Optional[str] = _DEFAULT_CONFIG) -> None:
        self._roles: dict[str, RoleDefinition] = {}
        self._seen_names: list[str] = []
        if config_path is not None:
            self.load_from_config(config_path)

    def register(self, role: RoleDefinition) -> None:
        self._seen_names.append(role.name)
        self._roles[role.name] = role

    def get_role(self, name: str) -> Optional[RoleDefinition]:
        return self._roles.get(name)

    def get_layer_roles(self, layer: RoleLayer) -> list[RoleDefinition]:
        return [r for r in self._roles.values() if r.layer == layer]

    def get_all_roles(self) -> list[RoleDefinition]:
        return list(self._roles.values())

    def validate(self) -> list[str]:
        errors: list[str] = []

        name_counts: dict[str, int] = {}
        for n in self._seen_names:
            name_counts[n] = name_counts.get(n, 0) + 1
        for n, count in name_counts.items():
            if count > 1:
                errors.append(f"Duplicate role name: {n}")

        for role in self._roles.values():
            for callee in role.allowed_callees:
                if callee not in self._roles:
                    errors.append(
                        f"Role '{role.name}' references unknown callee '{callee}'"
                    )
            for dep in role.dependencies:
                if dep not in self._roles:
                    errors.append(
                        f"Role '{role.name}' references unknown dependency '{dep}'"
                    )

        for layer in RoleLayer:
            if not any(r.layer == layer for r in self._roles.values()):
                errors.append(f"Layer '{layer.value}' has no roles")

        return errors

    def load_from_config(self, config_path: str) -> None:
        with open(config_path, encoding="utf-8") as f:
            data = json.load(f)

        self._roles.clear()
        self._seen_names.clear()
        for entry in data.get("roles", []):
            role = RoleDefinition(
                name=entry["name"],
                display_name=entry["display_name"],
                layer=RoleLayer(entry["layer"]),
                capabilities=entry.get("capabilities", []),
                review_scope=entry.get("review_scope", []),
                wip_limit=entry.get("wip_limit", 1),
                allowed_callees=entry.get("allowed_callees", []),
                cron_jobs=entry.get("cron_jobs", []),
                dependencies=entry.get("dependencies", []),
            )
            self.register(role)
        logger.info("Loaded %d roles from %s", len(self._roles), config_path)

    def to_dict(self) -> dict:
        return {
            "roles": [
                {
                    "name": r.name,
                    "display_name": r.display_name,
                    "layer": r.layer.value,
                    "capabilities": list(r.capabilities),
                    "review_scope": list(r.review_scope),
                    "wip_limit": r.wip_limit,
                    "allowed_callees": list(r.allowed_callees),
                    "cron_jobs": list(r.cron_jobs),
                    "dependencies": list(r.dependencies),
                }
                for r in self._roles.values()
            ]
        }

    # -- convenience helpers --

    def can_call(self, caller: str, callee: str) -> bool:
        role = self._roles.get(caller)
        if role is None:
            return False
        return callee in role.allowed_callees

    def get_reviewers_for_type(self, task_type: str) -> list[RoleDefinition]:
        return [
            r
            for r in self._roles.values()
            if r.layer == RoleLayer.REVIEWER and task_type in r.review_scope
        ]
