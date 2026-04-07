from __future__ import annotations

from pathlib import Path
from typing import Any
import tempfile

import yaml

from ..schema import AgentDefinition


def build_claude_frontmatter(
    agent: AgentDefinition, *, emit_defaults: bool = True
) -> dict[str, Any]:
    frontmatter: dict[str, Any] = {
        "name": agent.name,
        "description": agent.description,
    }
    if agent.claude.tools:
        frontmatter["tools"] = agent.claude.tools
    if agent.claude.disallowed_tools:
        frontmatter["disallowedTools"] = agent.claude.disallowed_tools
    model = agent.resolved_claude_model() if emit_defaults else agent.claude.model
    if model:
        frontmatter["model"] = model
    if agent.claude.permission_mode:
        frontmatter["permissionMode"] = agent.claude.permission_mode
    if agent.claude.max_turns is not None:
        frontmatter["maxTurns"] = agent.claude.max_turns
    effort = agent.resolved_claude_effort() if emit_defaults else agent.claude.effort
    if effort:
        frontmatter["effort"] = effort
    if agent.skills:
        frontmatter["skills"] = agent.skills
    if agent.claude.mcp_servers:
        frontmatter["mcpServers"] = agent.claude.mcp_servers
    frontmatter.update(agent.claude.extra)
    return frontmatter


def render_claude_agent(agent: AgentDefinition, *, emit_defaults: bool = True) -> str:
    frontmatter = build_claude_frontmatter(agent, emit_defaults=emit_defaults)
    yaml_block = yaml.safe_dump(
        frontmatter,
        sort_keys=False,
        allow_unicode=False,
        default_flow_style=False,
    ).strip()
    body = agent.instructions.rstrip("\n")
    return f"---\n{yaml_block}\n---\n\n{body}\n"


def write_claude_agent(output_path: Path, agent: AgentDefinition, dry_run: bool = False) -> str:
    content = render_claude_agent(agent)
    return write_atomic_if_changed(output_path, content, dry_run=dry_run)


def write_atomic_if_changed(output_path: Path, content: str, dry_run: bool = False) -> str:
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
