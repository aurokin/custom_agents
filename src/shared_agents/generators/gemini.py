from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from ..schema import AgentDefinition
from .claude import write_atomic_if_changed


def build_gemini_frontmatter(agent: AgentDefinition) -> dict[str, Any]:
    frontmatter: dict[str, Any] = {
        "name": agent.name,
        "description": agent.description,
    }
    if agent.gemini.tools is not None:
        frontmatter["tools"] = agent.gemini.tools
    if agent.gemini.model:
        frontmatter["model"] = agent.gemini.model
    if agent.gemini.temperature is not None:
        frontmatter["temperature"] = agent.gemini.temperature
    if agent.gemini.max_turns is not None:
        frontmatter["max_turns"] = agent.gemini.max_turns
    if agent.gemini.timeout_mins is not None:
        frontmatter["timeout_mins"] = agent.gemini.timeout_mins
    if agent.gemini.mcp_servers is not None:
        frontmatter["mcpServers"] = agent.gemini.mcp_servers
    return frontmatter


def render_gemini_agent(agent: AgentDefinition) -> str:
    frontmatter = build_gemini_frontmatter(agent)
    yaml_block = yaml.safe_dump(
        frontmatter,
        sort_keys=False,
        allow_unicode=False,
        default_flow_style=False,
    ).strip()
    body = agent.instructions.rstrip("\n")
    return f"---\n{yaml_block}\n---\n\n{body}\n"


def write_gemini_agent(
    output_path: Path, agent: AgentDefinition, dry_run: bool = False
) -> str:
    content = render_gemini_agent(agent)
    return write_atomic_if_changed(output_path, content, dry_run=dry_run)
