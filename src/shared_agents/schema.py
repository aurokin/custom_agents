from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import Any

import yaml


NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
SHARED_SANDBOX_VALUES = {"read-only", "workspace-write", "full-access"}
MODEL_STRATEGY_VALUES = {"pinned-defaults", "floating"}
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
COPILOT_TARGET_VALUES = {"vscode", "github-copilot"}
NICKNAME_RE = re.compile(r"^[A-Za-z0-9 _-]+$")
DEFAULT_CLAUDE_MODEL = "opus-4.6"
DEFAULT_CLAUDE_EFFORT = "high"
DEFAULT_CODEX_MODEL = "gpt-5.4"
DEFAULT_CODEX_REASONING_EFFORT = "high"
DEFAULT_COPILOT_MODEL = "gpt-5.4-high"
COPILOT_GITHUB_TARGET = "github-copilot"
COPILOT_VSCODE_TARGET = "vscode"


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
class CopilotConfig:
    target: str | None = None
    tools: list[str] | None = None
    model: str | list[str] | None = None
    agents: str | list[str] | None = None
    disable_model_invocation: bool | None = None
    user_invocable: bool | None = None
    infer: bool | None = None
    mcp_servers: dict[str, Any] | list[Any] | None = None
    metadata: dict[str, str] = field(default_factory=dict)
    argument_hint: str | None = None
    handoffs: list[dict[str, Any]] = field(default_factory=list)
    hooks: dict[str, Any] | None = None


@dataclass(frozen=True)
class AgentDefinition:
    name: str
    description: str
    instructions: str
    source_dir: Path
    sandbox: str
    model_strategy: str
    skills: list[str]
    claude: ClaudeConfig
    codex: CodexConfig
    copilot: CopilotConfig

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

    def resolved_claude_model(self) -> str:
        return self.claude.model or DEFAULT_CLAUDE_MODEL

    def resolved_claude_effort(self) -> str:
        return self.claude.effort or DEFAULT_CLAUDE_EFFORT

    def resolved_codex_model(self) -> str:
        return self.codex.model or DEFAULT_CODEX_MODEL

    def resolved_codex_reasoning_effort(self) -> str:
        return self.codex.model_reasoning_effort or DEFAULT_CODEX_REASONING_EFFORT

    def resolved_copilot_model(self) -> str | list[str]:
        return self.copilot.model or DEFAULT_COPILOT_MODEL

    def should_emit_model_defaults(self) -> bool:
        return self.model_strategy == "pinned-defaults"


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
    defaults_unknown = set(defaults_raw) - {"sandbox", "skills", "model_strategy"}
    if defaults_unknown:
        unknown_keys = ", ".join(sorted(defaults_unknown))
        raise SchemaError(
            f"Unknown defaults keys in {agent_yaml_path}: {unknown_keys}"
        )
    sandbox = _optional_str(defaults_raw, "sandbox", agent_yaml_path) or "read-only"
    if sandbox not in SHARED_SANDBOX_VALUES:
        raise SchemaError(
            f"Invalid defaults.sandbox in {agent_yaml_path}: {sandbox!r}"
        )
    model_strategy = (
        _optional_str(defaults_raw, "model_strategy", agent_yaml_path)
        or "pinned-defaults"
    )
    if model_strategy not in MODEL_STRATEGY_VALUES:
        raise SchemaError(
            f"Invalid defaults.model_strategy in {agent_yaml_path}: "
            f"{model_strategy!r}"
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

    copilot_raw = _optional_mapping(raw, "copilot", agent_yaml_path)
    copilot_unknown = set(copilot_raw) - {
        "target",
        "tools",
        "model",
        "agents",
        "disable_model_invocation",
        "user_invocable",
        "infer",
        "mcp_servers",
        "metadata",
        "argument_hint",
        "handoffs",
        "hooks",
    }
    if copilot_unknown:
        unknown_keys = ", ".join(sorted(copilot_unknown))
        raise SchemaError(
            f"Unknown copilot keys in {agent_yaml_path}: {unknown_keys}"
        )
    copilot = CopilotConfig(
        target=_optional_str(copilot_raw, "target", agent_yaml_path),
        tools=_optional_str_list(copilot_raw, "tools", agent_yaml_path),
        model=_optional_copilot_model(copilot_raw, agent_yaml_path),
        agents=_optional_copilot_agents(copilot_raw, agent_yaml_path),
        disable_model_invocation=_optional_bool(
            copilot_raw, "disable_model_invocation", agent_yaml_path
        ),
        user_invocable=_optional_bool(
            copilot_raw, "user_invocable", agent_yaml_path
        ),
        infer=_optional_bool(copilot_raw, "infer", agent_yaml_path),
        mcp_servers=_optional_copilot_mcp_servers(copilot_raw, agent_yaml_path),
        metadata=_optional_str_mapping(copilot_raw, "metadata", agent_yaml_path),
        argument_hint=_optional_str(copilot_raw, "argument_hint", agent_yaml_path),
        handoffs=_optional_copilot_handoffs(copilot_raw, agent_yaml_path),
        hooks=_optional_mapping(copilot_raw, "hooks", agent_yaml_path) or None,
    )
    if copilot.target and copilot.target not in COPILOT_TARGET_VALUES:
        raise SchemaError(
            f"Invalid copilot.target in {agent_yaml_path}: {copilot.target!r}"
        )
    _validate_copilot_config(copilot, agent_yaml_path)

    unknown_top_level = set(raw) - {
        "name",
        "description",
        "defaults",
        "claude",
        "codex",
        "copilot",
    }
    if unknown_top_level:
        unknown_keys = ", ".join(sorted(unknown_top_level))
        raise SchemaError(f"Unknown top-level keys in {agent_yaml_path}: {unknown_keys}")

    return AgentDefinition(
        name=name,
        description=description,
        instructions=instructions,
        source_dir=source_dir,
        sandbox=sandbox,
        model_strategy=model_strategy,
        skills=skills,
        claude=claude,
        codex=codex,
        copilot=copilot,
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


def _optional_bool(data: dict[str, Any], key: str, path: Path) -> bool | None:
    if key not in data or data[key] is None:
        return None
    value = data[key]
    if not isinstance(value, bool):
        raise SchemaError(f"Expected {key!r} to be a boolean in {path}")
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


def _optional_str_mapping(
    data: dict[str, Any], key: str, path: Path
) -> dict[str, str]:
    if key not in data or data[key] is None:
        return {}
    value = data[key]
    if not isinstance(value, dict):
        raise SchemaError(f"Expected {key!r} to be a mapping in {path}")
    result: dict[str, str] = {}
    for item_key, item_value in value.items():
        if not isinstance(item_key, str) or not item_key.strip():
            raise SchemaError(f"Expected {key!r} keys to be strings in {path}")
        if not isinstance(item_value, str) or not item_value.strip():
            raise SchemaError(f"Expected {key!r} values to be strings in {path}")
        result[item_key.strip()] = item_value.strip()
    return result


def _optional_copilot_model(
    data: dict[str, Any], path: Path
) -> str | list[str] | None:
    if "model" not in data or data["model"] is None:
        return None
    value = data["model"]
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            raise SchemaError(f"Expected 'model' to be non-empty in {path}")
        return stripped
    if isinstance(value, list):
        models: list[str] = []
        for item in value:
            if not isinstance(item, str) or not item.strip():
                raise SchemaError(f"Expected every item in 'model' to be a string in {path}")
            models.append(item.strip())
        if not models:
            raise SchemaError(f"Expected 'model' list to be non-empty in {path}")
        return models
    raise SchemaError(f"Expected 'model' to be a string or list in {path}")


def _optional_copilot_mcp_servers(
    data: dict[str, Any], path: Path
) -> dict[str, Any] | list[Any] | None:
    if "mcp_servers" not in data or data["mcp_servers"] is None:
        return None
    value = data["mcp_servers"]
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, list):
        servers: list[Any] = []
        for item in value:
            if isinstance(item, str):
                stripped = item.strip()
                if not stripped:
                    raise SchemaError(
                        f"Expected every string item in 'mcp_servers' to be non-empty in {path}"
                    )
                servers.append(stripped)
                continue
            if isinstance(item, dict):
                servers.append(dict(item))
                continue
            raise SchemaError(
                f"Expected every item in 'mcp_servers' to be a string or mapping in {path}"
            )
        return servers
    raise SchemaError(f"Expected 'mcp_servers' to be a mapping or list in {path}")


def _optional_copilot_agents(
    data: dict[str, Any], path: Path
) -> str | list[str] | None:
    if "agents" not in data or data["agents"] is None:
        return None
    value = data["agents"]
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            raise SchemaError(f"Expected 'agents' to be non-empty in {path}")
        return stripped
    if isinstance(value, list):
        agents: list[str] = []
        for item in value:
            if not isinstance(item, str) or not item.strip():
                raise SchemaError(
                    f"Expected every item in 'agents' to be a string in {path}"
                )
            agents.append(item.strip())
        return agents
    raise SchemaError(f"Expected 'agents' to be a string or list in {path}")


def _optional_copilot_handoffs(
    data: dict[str, Any], path: Path
) -> list[dict[str, Any]]:
    if "handoffs" not in data or data["handoffs"] is None:
        return []
    value = data["handoffs"]
    if not isinstance(value, list):
        raise SchemaError(f"Expected 'handoffs' to be a list in {path}")
    handoffs: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            raise SchemaError(
                f"Expected every item in 'handoffs' to be a mapping in {path}"
            )
        copied = dict(item)
        _validate_copilot_handoff(copied, path)
        handoffs.append(copied)
    return handoffs


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


def _validate_copilot_config(config: CopilotConfig, path: Path) -> None:
    if config.target == COPILOT_GITHUB_TARGET:
        if isinstance(config.model, list):
            raise SchemaError(
                f"copilot.model must be a string for target {COPILOT_GITHUB_TARGET!r} in {path}"
            )
        if config.mcp_servers is not None and not isinstance(config.mcp_servers, dict):
            raise SchemaError(
                f"copilot.mcp_servers must be a mapping for target {COPILOT_GITHUB_TARGET!r} in {path}"
            )
        if config.agents is not None:
            raise SchemaError(
                f"copilot.agents is only supported for target {COPILOT_VSCODE_TARGET!r} in {path}"
            )
        if config.argument_hint is not None:
            raise SchemaError(
                f"copilot.argument_hint is only supported for target {COPILOT_VSCODE_TARGET!r} in {path}"
            )
        if config.handoffs:
            raise SchemaError(
                f"copilot.handoffs is only supported for target {COPILOT_VSCODE_TARGET!r} in {path}"
            )
        if config.hooks is not None:
            raise SchemaError(
                f"copilot.hooks is only supported for target {COPILOT_VSCODE_TARGET!r} in {path}"
            )
        return

    if config.target == COPILOT_VSCODE_TARGET:
        if config.metadata:
            raise SchemaError(
                f"copilot.metadata is only supported for target {COPILOT_GITHUB_TARGET!r} in {path}"
            )
        if config.mcp_servers is not None and not isinstance(config.mcp_servers, list):
            raise SchemaError(
                f"copilot.mcp_servers must be a list for target {COPILOT_VSCODE_TARGET!r} in {path}"
            )
        return

    if isinstance(config.model, list):
        raise SchemaError(
            f"Set copilot.target to {COPILOT_VSCODE_TARGET!r} to use a model list in {path}"
        )

    if config.argument_hint is not None or config.handoffs:
        raise SchemaError(
            f"Set copilot.target to {COPILOT_VSCODE_TARGET!r} to use argument_hint or handoffs in {path}"
        )
    if config.agents is not None or config.hooks is not None:
        raise SchemaError(
            f"Set copilot.target to {COPILOT_VSCODE_TARGET!r} to use agents or hooks in {path}"
        )


def _validate_copilot_handoff(handoff: dict[str, Any], path: Path) -> None:
    allowed = {"label", "agent", "prompt", "send", "model"}
    unknown = set(handoff) - allowed
    if unknown:
        unknown_keys = ", ".join(sorted(unknown))
        raise SchemaError(
            f"Unknown keys in copilot.handoffs entry in {path}: {unknown_keys}"
        )
    for key in ("label", "agent"):
        value = handoff.get(key)
        if not isinstance(value, str) or not value.strip():
            raise SchemaError(
                f"copilot.handoffs.{key} must be a non-empty string in {path}"
            )
    if "prompt" in handoff and (
        not isinstance(handoff["prompt"], str) or not handoff["prompt"].strip()
    ):
        raise SchemaError(
            f"copilot.handoffs.prompt must be a non-empty string in {path}"
        )
    if "send" in handoff and not isinstance(handoff["send"], bool):
        raise SchemaError(f"copilot.handoffs.send must be a boolean in {path}")
    if "model" in handoff:
        model = handoff["model"]
        if isinstance(model, str):
            if not model.strip():
                raise SchemaError(
                    f"copilot.handoffs.model must be non-empty in {path}"
                )
            return
        if isinstance(model, list):
            if not model:
                raise SchemaError(
                    f"copilot.handoffs.model list must be non-empty in {path}"
                )
            for item in model:
                if not isinstance(item, str) or not item.strip():
                    raise SchemaError(
                        f"copilot.handoffs.model items must be strings in {path}"
                    )
            return
        raise SchemaError(
            f"copilot.handoffs.model must be a string or list in {path}"
        )


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
