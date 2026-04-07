from __future__ import annotations

from pathlib import Path
from typing import Iterable
import os

from .schema import AgentDefinition, SchemaError, load_agent_definition


class DiscoveryError(ValueError):
    """Raised when agent discovery fails."""


def resolve_source_root(source_root: Path | None = None) -> Path:
    if source_root is not None:
        return source_root.expanduser().resolve()
    cwd = Path.cwd().resolve()
    if (cwd / "agents").exists():
        return cwd
    env_value = os.environ.get("AGENTS_HOME")
    if env_value:
        return Path(env_value).expanduser().resolve()
    return (Path.home() / ".agents").resolve()


def resolve_agents_home(agents_home: Path | None = None) -> Path:
    return resolve_source_root(agents_home)


def iter_agent_directories(source_root: Path) -> Iterable[Path]:
    agents_dir = source_root / "agents"
    if not agents_dir.exists():
        return []
    return sorted(path.parent for path in agents_dir.rglob("agent.yaml"))


def discover_agents(source_root: Path | None = None) -> list[AgentDefinition]:
    resolved_home = resolve_source_root(source_root)
    discovered: list[AgentDefinition] = []
    seen_names: dict[str, Path] = {}
    for source_dir in iter_agent_directories(resolved_home):
        try:
            agent = load_agent_definition(source_dir)
        except SchemaError as exc:
            raise DiscoveryError(str(exc)) from exc
        if agent.name in seen_names:
            first = seen_names[agent.name]
            raise DiscoveryError(
                f"Duplicate agent name {agent.name!r}: {first} and {source_dir}"
            )
        seen_names[agent.name] = source_dir
        discovered.append(agent)
    return sorted(discovered, key=lambda agent: agent.name)
