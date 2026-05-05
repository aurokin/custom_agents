from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import yaml

from ..schema import AgentDefinition
from .claude import write_atomic_if_changed


TPROMPT_SUFFIX = "-ca"
SUBAGENT_FOOTER = "Do not use subagents for this specific request."
_WORD_SPLIT_RE = re.compile(r"[-_]+")


def tprompt_executable() -> str | None:
    return shutil.which("tprompt")


def resolve_tprompt_prompts_dir() -> Path:
    config_home = os.environ.get("XDG_CONFIG_HOME")
    root = Path(config_home).expanduser() if config_home else Path.home() / ".config"
    return root / "tprompt" / "prompts"


def tprompt_prompt_id(agent: AgentDefinition) -> str:
    base = agent.tprompt.filename or agent.name
    return f"{base}{TPROMPT_SUFFIX}"


def tprompt_output_path(agent: AgentDefinition) -> Path:
    return resolve_tprompt_prompts_dir() / f"{tprompt_prompt_id(agent)}.md"


def _default_title(name: str) -> str:
    parts = [part for part in _WORD_SPLIT_RE.split(name) if part]
    return " ".join(part[:1].upper() + part[1:] for part in parts)


def build_tprompt_frontmatter(agent: AgentDefinition) -> dict[str, Any]:
    frontmatter: dict[str, Any] = {
        "title": agent.tprompt.title or _default_title(agent.name),
        "description": agent.tprompt.description or agent.description,
        "tags": list(agent.tprompt.tags) if agent.tprompt.tags is not None else [],
    }
    if agent.tprompt.key is not None:
        frontmatter["key"] = agent.tprompt.key
    if agent.tprompt.mode is not None:
        frontmatter["mode"] = agent.tprompt.mode
    if agent.tprompt.enter is not None:
        frontmatter["enter"] = agent.tprompt.enter
    return frontmatter


def render_tprompt_agent(agent: AgentDefinition) -> str:
    frontmatter = build_tprompt_frontmatter(agent)
    yaml_block = yaml.safe_dump(
        frontmatter,
        sort_keys=False,
        allow_unicode=False,
        default_flow_style=False,
    ).strip()
    body = agent.instructions.rstrip("\n")
    return f"---\n{yaml_block}\n---\n\n{body}\n\n{SUBAGENT_FOOTER}\n"


def scaffold_with_tprompt(
    output_path: Path, prompt_id: str, executable: str
) -> None:
    if output_path.exists():
        return
    subprocess.run(
        [executable, "new", prompt_id],
        check=True,
        capture_output=True,
        text=True,
    )


def write_tprompt_agent(
    output_path: Path,
    agent: AgentDefinition,
    *,
    executable: str,
    dry_run: bool = False,
) -> str:
    content = render_tprompt_agent(agent)
    if not dry_run:
        scaffold_with_tprompt(output_path, tprompt_prompt_id(agent), executable)
    return write_atomic_if_changed(output_path, content, dry_run=dry_run)
