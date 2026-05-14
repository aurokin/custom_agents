from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from ..schema import AgentDefinition
from .claude import write_atomic_if_changed


def build_opencode_frontmatter(agent: AgentDefinition) -> dict[str, Any]:
    frontmatter: dict[str, Any] = {
        "description": agent.opencode.description or agent.description,
        "mode": agent.resolved_opencode_mode(),
    }
    if agent.opencode.model:
        frontmatter["model"] = agent.opencode.model
    if agent.opencode.variant:
        frontmatter["variant"] = agent.opencode.variant
    if agent.opencode.temperature is not None:
        frontmatter["temperature"] = agent.opencode.temperature
    if agent.opencode.top_p is not None:
        frontmatter["top_p"] = agent.opencode.top_p
    if agent.opencode.disable is not None:
        frontmatter["disable"] = agent.opencode.disable
    if agent.opencode.hidden is not None:
        frontmatter["hidden"] = agent.opencode.hidden
    if agent.opencode.color:
        frontmatter["color"] = agent.opencode.color
    if agent.opencode.steps is not None:
        frontmatter["steps"] = agent.opencode.steps
    permission = agent.resolved_opencode_permission()
    if permission is not None:
        frontmatter["permission"] = permission
    if agent.opencode.tools is not None:
        frontmatter["tools"] = agent.opencode.tools
    frontmatter.update(agent.opencode.options)
    return frontmatter


def render_opencode_agent(agent: AgentDefinition) -> str:
    frontmatter = build_opencode_frontmatter(agent)
    yaml_block = yaml.safe_dump(
        frontmatter,
        sort_keys=False,
        allow_unicode=False,
        default_flow_style=False,
    ).strip()
    body = agent.instructions.rstrip("\n")
    return f"---\n{yaml_block}\n---\n\n{body}\n"


def write_opencode_agent(
    output_path: Path, agent: AgentDefinition, dry_run: bool = False
) -> str:
    content = render_opencode_agent(agent)
    return write_atomic_if_changed(output_path, content, dry_run=dry_run)
