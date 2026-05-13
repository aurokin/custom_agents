from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from ..schema import AgentDefinition, normalize_skill_name
from .claude import write_atomic_if_changed


def resolve_agent_skills_dir() -> Path:
    return Path.home() / ".agents" / "skills"


def resolve_claude_skills_dir() -> Path:
    return Path.home() / ".claude" / "skills"


def skill_name(agent: AgentDefinition) -> str:
    return normalize_skill_name(agent.skill.name or agent.name)


def skill_output_path(agent: AgentDefinition) -> Path:
    name = skill_name(agent)
    return resolve_agent_skills_dir() / name / "SKILL.md"


def claude_skill_output_path(agent: AgentDefinition) -> Path:
    name = skill_name(agent)
    return resolve_claude_skills_dir() / name / "SKILL.md"


def _default_title(name: str) -> str:
    return " ".join(part[:1].upper() + part[1:] for part in name.split("-"))


def build_skill_frontmatter(agent: AgentDefinition) -> dict[str, Any]:
    name = skill_name(agent)
    description = agent.skill.description or agent.description
    frontmatter: dict[str, Any] = {
        "name": name,
        "description": description,
    }
    if agent.skill.license:
        frontmatter["license"] = agent.skill.license
    if agent.skill.compatibility:
        frontmatter["compatibility"] = agent.skill.compatibility
    if agent.skill.tags:
        frontmatter["tags"] = agent.skill.tags
    metadata = {
        "source": "custom_agents",
        "original_name": agent.name,
    }
    metadata.update(agent.skill.metadata)
    frontmatter["metadata"] = metadata
    return frontmatter


def render_skill(agent: AgentDefinition) -> str:
    frontmatter = build_skill_frontmatter(agent)
    yaml_block = yaml.safe_dump(
        frontmatter,
        sort_keys=False,
        allow_unicode=False,
        default_flow_style=False,
    ).strip()
    name = frontmatter["name"]
    title = agent.skill.title or _default_title(name)
    body = agent.instructions.rstrip("\n")
    sandbox_note = (
        f"This skill was generated from the `{agent.name}` shared agent. "
        f"The source agent declares `{agent.sandbox}` sandbox expectations, "
        "but skill consumers must enforce permissions themselves."
    )
    return (
        f"---\n{yaml_block}\n---\n\n"
        f"# {title}\n\n"
        "## Instructions\n\n"
        f"{body}\n\n"
        "## Source Notes\n\n"
        f"{sandbox_note}\n"
    )


def write_agent_skill(
    output_path: Path, agent: AgentDefinition, dry_run: bool = False
) -> str:
    content = render_skill(agent)
    return write_atomic_if_changed(output_path, content, dry_run=dry_run)
