from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from ..schema import AgentDefinition
from .claude import write_atomic_if_changed


def build_cursor_frontmatter(agent: AgentDefinition) -> dict[str, Any]:
    frontmatter: dict[str, Any] = {
        "name": agent.name,
        "description": agent.cursor.description or agent.description,
    }
    if agent.cursor.model:
        frontmatter["model"] = agent.cursor.model
    readonly = agent.resolved_cursor_readonly()
    if readonly is not None:
        frontmatter["readonly"] = readonly
    return frontmatter


def render_cursor_agent(agent: AgentDefinition) -> str:
    frontmatter = build_cursor_frontmatter(agent)
    yaml_block = yaml.safe_dump(
        frontmatter,
        sort_keys=False,
        allow_unicode=False,
        default_flow_style=False,
    ).strip()
    body = agent.instructions.rstrip("\n")
    return f"---\n{yaml_block}\n---\n\n{body}\n"


def write_cursor_agent(
    output_path: Path, agent: AgentDefinition, dry_run: bool = False
) -> str:
    content = render_cursor_agent(agent)
    return write_atomic_if_changed(output_path, content, dry_run=dry_run)
