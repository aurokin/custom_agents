from __future__ import annotations

from pathlib import Path
import tempfile
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib

from ..schema import AgentDefinition


def build_codex_document(
    agent: AgentDefinition, *, emit_defaults: bool = True
) -> dict[str, Any]:
    document: dict[str, Any] = {
        "name": agent.name,
        "description": agent.description,
        "developer_instructions": agent.instructions,
    }
    model = agent.resolved_codex_model() if emit_defaults else agent.codex.model
    if model:
        document["model"] = model
    reasoning_effort = (
        agent.resolved_codex_reasoning_effort()
        if emit_defaults
        else agent.codex.model_reasoning_effort
    )
    if reasoning_effort:
        document["model_reasoning_effort"] = reasoning_effort
    document["sandbox_mode"] = agent.resolved_codex_sandbox_mode()
    if agent.codex.nickname_candidates:
        document["nickname_candidates"] = [item.strip() for item in agent.codex.nickname_candidates]
    if agent.codex.mcp_servers:
        document["mcp_servers"] = agent.codex.mcp_servers

    skills_config = _merge_skills_config(agent)
    if skills_config:
        document["skills"] = {"config": skills_config}

    if agent.codex.config:
        for key, value in agent.codex.config.items():
            if key in document:
                raise ValueError(f"codex.config key collides with reserved field: {key}")
            document[key] = value
    return document


def render_codex_agent(agent: AgentDefinition, *, emit_defaults: bool = True) -> str:
    content = (
        _dump_toml_document(build_codex_document(agent, emit_defaults=emit_defaults)).rstrip()
        + "\n"
    )
    tomllib.loads(content)
    return content


def write_codex_agent(output_path: Path, agent: AgentDefinition, dry_run: bool = False) -> str:
    content = render_codex_agent(agent)
    if output_path.exists() and output_path.read_text(encoding="utf-8") == content:
        return "unchanged"
    if dry_run:
        return "would-write"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=output_path.parent, delete=False
    ) as handle:
        handle.write(content)
        temp_path = Path(handle.name)
    temp_path.replace(output_path)
    return "written"


def _merge_skills_config(agent: AgentDefinition) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for skill_name in agent.skills:
        entry = {"name": skill_name, "enabled": True}
        merged.append(entry)
        seen.add(("name", skill_name))
    for entry in agent.codex.skills_config:
        copied = dict(entry)
        key = ("path", copied["path"]) if "path" in copied else ("name", copied["name"])
        if key in seen:
            for existing in merged:
                existing_key = (
                    ("path", existing["path"])
                    if "path" in existing
                    else ("name", existing["name"])
                )
                if existing_key == key:
                    existing.update(copied)
                    break
            continue
        merged.append(copied)
        seen.add(key)
    return merged


def _dump_toml_document(document: dict[str, Any]) -> str:
    lines: list[str] = []
    _dump_table(lines, document, [])
    return "\n".join(lines) + ("\n" if lines else "")


def _dump_table(lines: list[str], table: dict[str, Any], prefix: list[str]) -> None:
    scalar_items: list[tuple[str, Any]] = []
    nested_tables: list[tuple[str, dict[str, Any]]] = []
    array_tables: list[tuple[str, list[dict[str, Any]]]] = []

    for key, value in table.items():
        if isinstance(value, dict):
            nested_tables.append((key, value))
        elif _is_array_of_tables(value):
            array_tables.append((key, value))
        else:
            scalar_items.append((key, value))

    for key, value in scalar_items:
        lines.append(f"{key} = {_format_value(value)}")

    for key, value in nested_tables:
        if lines and lines[-1] != "":
            lines.append("")
        header = ".".join([*prefix, key])
        lines.append(f"[{header}]")
        _dump_table(lines, value, [*prefix, key])

    for key, values in array_tables:
        for item in values:
            if lines and lines[-1] != "":
                lines.append("")
            header = ".".join([*prefix, key])
            lines.append(f"[[{header}]]")
            _dump_table(lines, item, [*prefix, key])


def _is_array_of_tables(value: Any) -> bool:
    return isinstance(value, list) and value and all(isinstance(item, dict) for item in value)


def _format_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, str):
        if "\n" in value:
            escaped = value.replace("\\", "\\\\").replace('"""', '\\"\\"\\"')
            return f'"""{escaped}"""'
        escaped = (
            value.replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("\n", "\\n")
            .replace("\t", "\\t")
        )
        return f'"{escaped}"'
    if isinstance(value, list):
        return "[" + ", ".join(_format_value(item) for item in value) + "]"
    raise TypeError(f"Unsupported TOML value: {value!r}")
