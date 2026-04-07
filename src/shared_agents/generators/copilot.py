from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from ..schema import (
    AgentDefinition,
    COPILOT_VSCODE_TARGET,
)
from .claude import write_atomic_if_changed


def build_copilot_frontmatter(
    agent: AgentDefinition, *, emit_defaults: bool = True
) -> dict[str, Any]:
    frontmatter: dict[str, Any] = {
        "name": agent.name,
        "description": agent.description,
    }
    if agent.copilot.target:
        frontmatter["target"] = agent.copilot.target
    if agent.copilot.tools is not None:
        frontmatter["tools"] = agent.copilot.tools
    if agent.copilot.agents is not None:
        frontmatter["agents"] = agent.copilot.agents
    model = agent.resolved_copilot_model() if emit_defaults else agent.copilot.model
    if model is not None:
        frontmatter["model"] = model
    if agent.copilot.disable_model_invocation is not None:
        frontmatter["disable-model-invocation"] = (
            agent.copilot.disable_model_invocation
        )
    if agent.copilot.user_invocable is not None:
        frontmatter["user-invocable"] = agent.copilot.user_invocable
    if agent.copilot.infer is not None:
        frontmatter["infer"] = agent.copilot.infer
    if agent.copilot.mcp_servers is not None:
        frontmatter["mcp-servers"] = agent.copilot.mcp_servers
    if (
        agent.copilot.target != COPILOT_VSCODE_TARGET
        and agent.copilot.metadata
    ):
        frontmatter["metadata"] = agent.copilot.metadata
    if (
        agent.copilot.target == COPILOT_VSCODE_TARGET
        and agent.copilot.argument_hint
    ):
        frontmatter["argument-hint"] = agent.copilot.argument_hint
    if (
        agent.copilot.target == COPILOT_VSCODE_TARGET
        and agent.copilot.handoffs
    ):
        frontmatter["handoffs"] = agent.copilot.handoffs
    if agent.copilot.target == COPILOT_VSCODE_TARGET and agent.copilot.hooks:
        frontmatter["hooks"] = agent.copilot.hooks
    return frontmatter


def render_copilot_agent(agent: AgentDefinition, *, emit_defaults: bool = True) -> str:
    frontmatter = build_copilot_frontmatter(agent, emit_defaults=emit_defaults)
    yaml_block = yaml.safe_dump(
        frontmatter,
        sort_keys=False,
        allow_unicode=False,
        default_flow_style=False,
    ).strip()
    body = agent.instructions.rstrip("\n")
    return f"---\n{yaml_block}\n---\n\n{body}\n"


def write_copilot_agent(
    output_path: Path, agent: AgentDefinition, dry_run: bool = False
) -> str:
    content = render_copilot_agent(agent)
    return write_atomic_if_changed(output_path, content, dry_run=dry_run)
