from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import Any

import yaml


NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
SHARED_SANDBOX_VALUES = {"read-only", "workspace-write", "full-access"}
CLAUDE_PERMISSION_VALUES = {
    "default",
    "acceptEdits",
    "dontAsk",
    "bypassPermissions",
    "plan",
}
CLAUDE_EFFORT_VALUES = {"low", "medium", "high", "max"}
CODEX_REASONING_VALUES = {"low", "medium", "high", "xhigh"}
CODEX_SANDBOX_VALUES = {"read-only", "workspace-write", "danger-full-access"}
NICKNAME_RE = re.compile(r"^[A-Za-z0-9 _-]+$")


class SchemaError(ValueError):
    """Raised when an agent definition is invalid."""


@dataclass(frozen=True)
class ClaudeConfig:
    model: str | None = None
    tools: list[str] | None = None
    disallowed_tools: list[str] | None = None
    permission_mode: str | None = None
    max_turns: int | None = None
    effort: str | None = None
    mcp_servers: Any = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CodexConfig:
    model: str | None = None
    model_reasoning_effort: str | None = None
    sandbox_mode: str | None = None
    nickname_candidates: list[str] | None = None
    mcp_servers: dict[str, Any] | None = None
    skills_config: list[dict[str, Any]] = field(default_factory=list)
    config: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AgentDefinition:
    name: str
    description: str
    instructions: str
    source_dir: Path
    sandbox: str
    skills: list[str]
    claude: ClaudeConfig
    codex: CodexConfig

    @property
    def output_name(self) -> str:
        return self.name

    def resolved_codex_sandbox_mode(self) -> str:
        if self.codex.sandbox_mode:
            return self.codex.sandbox_mode
        return {
            "read-only": "read-only",
            "workspace-write": "workspace-write",
            "full-access": "danger-full-access",
        }[self.sandbox]


def load_agent_definition(source_dir: Path) -> AgentDefinition:
    agent_yaml_path = source_dir / "agent.yaml"
    instructions_path = source_dir / "instructions.md"

    if not agent_yaml_path.exists():
        raise SchemaError(f"Missing agent.yaml: {agent_yaml_path}")
    if not instructions_path.exists():
        raise SchemaError(f"Missing instructions.md: {instructions_path}")

    raw = _load_yaml_mapping(agent_yaml_path)
    name = _required_str(raw, "name", agent_yaml_path)
    _validate_name(name, agent_yaml_path)
    description = _required_str(raw, "description", agent_yaml_path)
    instructions = instructions_path.read_text(encoding="utf-8")
    if not instructions.strip():
        raise SchemaError(f"instructions.md is empty: {instructions_path}")

    defaults_raw = _optional_mapping(raw, "defaults", agent_yaml_path)
    sandbox = _optional_str(defaults_raw, "sandbox", agent_yaml_path) or "read-only"
    if sandbox not in SHARED_SANDBOX_VALUES:
        raise SchemaError(
            f"Invalid defaults.sandbox in {agent_yaml_path}: {sandbox!r}"
        )
    skills = _optional_str_list(defaults_raw, "skills", agent_yaml_path, default=[])

    claude_raw = _optional_mapping(raw, "claude", agent_yaml_path)
    claude_known_keys = {
        "model",
        "tools",
        "disallowed_tools",
        "permission_mode",
        "max_turns",
        "effort",
        "mcp_servers",
    }
    claude = ClaudeConfig(
        model=_optional_str(claude_raw, "model", agent_yaml_path),
        tools=_optional_str_list(claude_raw, "tools", agent_yaml_path),
        disallowed_tools=_optional_str_list(
            claude_raw, "disallowed_tools", agent_yaml_path
        ),
        permission_mode=_optional_str(
            claude_raw, "permission_mode", agent_yaml_path
        ),
        max_turns=_optional_int(claude_raw, "max_turns", agent_yaml_path),
        effort=_optional_str(claude_raw, "effort", agent_yaml_path),
        mcp_servers=claude_raw.get("mcp_servers"),
        extra={k: v for k, v in claude_raw.items() if k not in claude_known_keys},
    )
    if claude.permission_mode and claude.permission_mode not in CLAUDE_PERMISSION_VALUES:
        raise SchemaError(
            f"Invalid claude.permission_mode in {agent_yaml_path}: "
            f"{claude.permission_mode!r}"
        )
    if claude.effort and claude.effort not in CLAUDE_EFFORT_VALUES:
        raise SchemaError(
            f"Invalid claude.effort in {agent_yaml_path}: {claude.effort!r}"
        )

    codex_raw = _optional_mapping(raw, "codex", agent_yaml_path)
    codex_unknown = set(codex_raw) - {
        "model",
        "model_reasoning_effort",
        "sandbox_mode",
        "nickname_candidates",
        "mcp_servers",
        "skills_config",
        "config",
    }
    if codex_unknown:
        unknown_keys = ", ".join(sorted(codex_unknown))
        raise SchemaError(
            f"Unknown codex keys in {agent_yaml_path}: {unknown_keys}. "
            "Use codex.config for additional valid Codex config fields."
        )
    codex = CodexConfig(
        model=_optional_str(codex_raw, "model", agent_yaml_path),
        model_reasoning_effort=_optional_str(
            codex_raw, "model_reasoning_effort", agent_yaml_path
        ),
        sandbox_mode=_optional_str(codex_raw, "sandbox_mode", agent_yaml_path),
        nickname_candidates=_optional_str_list(
            codex_raw, "nickname_candidates", agent_yaml_path
        ),
        mcp_servers=_optional_mapping(codex_raw, "mcp_servers", agent_yaml_path)
        or None,
        skills_config=_optional_dict_list(
            codex_raw, "skills_config", agent_yaml_path
        ),
        config=_optional_mapping(codex_raw, "config", agent_yaml_path),
    )
    if (
        codex.model_reasoning_effort
        and codex.model_reasoning_effort not in CODEX_REASONING_VALUES
    ):
        raise SchemaError(
            f"Invalid codex.model_reasoning_effort in {agent_yaml_path}: "
            f"{codex.model_reasoning_effort!r}"
        )
    if codex.sandbox_mode and codex.sandbox_mode not in CODEX_SANDBOX_VALUES:
        raise SchemaError(
            f"Invalid codex.sandbox_mode in {agent_yaml_path}: "
            f"{codex.sandbox_mode!r}"
        )
    if codex.nickname_candidates:
        _validate_nickname_candidates(codex.nickname_candidates, agent_yaml_path)
    for entry in codex.skills_config:
        _validate_skills_config_entry(entry, agent_yaml_path)
    if codex.mcp_servers is not None and not isinstance(codex.mcp_servers, dict):
        raise SchemaError(
            f"codex.mcp_servers must be a mapping in {agent_yaml_path}"
        )
    _validate_codex_config(codex.config, agent_yaml_path)

    unknown_top_level = set(raw) - {"name", "description", "defaults", "claude", "codex"}
    if unknown_top_level:
        unknown_keys = ", ".join(sorted(unknown_top_level))
        raise SchemaError(f"Unknown top-level keys in {agent_yaml_path}: {unknown_keys}")

    return AgentDefinition(
        name=name,
        description=description,
        instructions=instructions,
        source_dir=source_dir,
        sandbox=sandbox,
        skills=skills,
        claude=claude,
        codex=codex,
    )


def _load_yaml_mapping(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise SchemaError(f"Expected a mapping in {path}")
    return data


def _required_str(data: dict[str, Any], key: str, path: Path) -> str:
    value = _optional_str(data, key, path)
    if value is None:
        raise SchemaError(f"Missing required field {key!r} in {path}")
    return value


def _optional_mapping(
    data: dict[str, Any], key: str, path: Path
) -> dict[str, Any]:
    value = data.get(key, {})
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise SchemaError(f"Expected {key!r} to be a mapping in {path}")
    return dict(value)


def _optional_str(data: dict[str, Any], key: str, path: Path) -> str | None:
    if key not in data or data[key] is None:
        return None
    value = data[key]
    if not isinstance(value, str):
        raise SchemaError(f"Expected {key!r} to be a string in {path}")
    stripped = value.strip()
    if not stripped:
        raise SchemaError(f"Expected {key!r} to be non-empty in {path}")
    return stripped


def _optional_int(data: dict[str, Any], key: str, path: Path) -> int | None:
    if key not in data or data[key] is None:
        return None
    value = data[key]
    if not isinstance(value, int) or isinstance(value, bool):
        raise SchemaError(f"Expected {key!r} to be an integer in {path}")
    return value


def _optional_str_list(
    data: dict[str, Any],
    key: str,
    path: Path,
    default: list[str] | None = None,
) -> list[str] | None:
    if key not in data or data[key] is None:
        return default
    value = data[key]
    if not isinstance(value, list):
        raise SchemaError(f"Expected {key!r} to be a list in {path}")
    items: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise SchemaError(f"Expected every item in {key!r} to be a string in {path}")
        items.append(item.strip())
    return items


def _optional_dict_list(
    data: dict[str, Any], key: str, path: Path
) -> list[dict[str, Any]]:
    if key not in data or data[key] is None:
        return []
    value = data[key]
    if not isinstance(value, list):
        raise SchemaError(f"Expected {key!r} to be a list in {path}")
    entries: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            raise SchemaError(f"Expected every item in {key!r} to be a mapping in {path}")
        entries.append(dict(item))
    return entries


def _validate_name(name: str, path: Path) -> None:
    if not NAME_RE.fullmatch(name):
        raise SchemaError(
            f"Invalid name in {path}: {name!r}. Use lowercase letters, digits, hyphens, and underscores."
        )


def _validate_nickname_candidates(values: list[str], path: Path) -> None:
    seen: set[str] = set()
    for value in values:
        trimmed = value.strip()
        if not trimmed:
            raise SchemaError(f"Nickname candidates must be non-empty in {path}")
        if not NICKNAME_RE.fullmatch(trimmed):
            raise SchemaError(
                f"Invalid codex.nickname_candidates entry in {path}: {value!r}"
            )
        lowered = trimmed.lower()
        if lowered in seen:
            raise SchemaError(
                f"Duplicate codex.nickname_candidates entry in {path}: {value!r}"
            )
        seen.add(lowered)


def _validate_skills_config_entry(entry: dict[str, Any], path: Path) -> None:
    if "name" not in entry and "path" not in entry:
        raise SchemaError(
            f"Each codex.skills_config entry must include name or path in {path}"
        )
    allowed = {"name", "path", "enabled"}
    unknown = set(entry) - allowed
    if unknown:
        unknown_keys = ", ".join(sorted(unknown))
        raise SchemaError(
            f"Unknown keys in codex.skills_config entry in {path}: {unknown_keys}"
        )
    if "name" in entry and (
        not isinstance(entry["name"], str) or not entry["name"].strip()
    ):
        raise SchemaError(
            f"codex.skills_config.name must be a non-empty string in {path}"
        )
    if "path" in entry and (
        not isinstance(entry["path"], str) or not entry["path"].strip()
    ):
        raise SchemaError(
            f"codex.skills_config.path must be a non-empty string in {path}"
        )
    if "enabled" in entry and not isinstance(entry["enabled"], bool):
        raise SchemaError(f"codex.skills_config.enabled must be a boolean in {path}")


def _validate_codex_config(config: dict[str, Any], path: Path) -> None:
    forbidden = {
        "name",
        "description",
        "nickname_candidates",
        "developer_instructions",
        "model",
        "model_reasoning_effort",
        "sandbox_mode",
        "mcp_servers",
        "skills",
    }
    conflict = forbidden & set(config)
    if conflict:
        keys = ", ".join(sorted(conflict))
        raise SchemaError(
            f"codex.config in {path} contains fields handled elsewhere: {keys}"
        )
