from __future__ import annotations

from pathlib import Path
from typing import Iterable
import os
import shutil
import sys

from .schema import AgentDefinition, SchemaError, load_agent_definition


class DiscoveryError(ValueError):
    """Raised when agent discovery fails."""


STALE_AGENT_DIRECTORY_RENAMES: dict[Path, Path] = {
    Path("retrorabbit_code_reviewer"): Path("retrorabbit-code-reviewer"),
}


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
    return sorted(
        path.parent
        for path in agents_dir.rglob("agent.yaml")
        if not _is_stale_materialized_rename(path.parent, agents_dir)
    )


def _is_stale_materialized_rename(source_dir: Path, agents_dir: Path) -> bool:
    """Identify ignored ``agent.yaml`` files stranded by known agent renames."""
    try:
        relative_source = source_dir.relative_to(agents_dir)
    except ValueError:
        return False
    replacement = STALE_AGENT_DIRECTORY_RENAMES.get(relative_source)
    if replacement is None:
        return False
    return (
        not (source_dir / "agent.yaml.example").exists()
        and not (source_dir / "instructions.md").exists()
        and (agents_dir / replacement).exists()
    )


def iter_example_only_directories(source_root: Path) -> list[Path]:
    agents_dir = source_root / "agents"
    if not agents_dir.exists():
        return []
    example_dirs = {path.parent for path in agents_dir.rglob("agent.yaml.example")}
    yaml_dirs = {path.parent for path in agents_dir.rglob("agent.yaml")}
    return sorted(example_dirs - yaml_dirs)


def _discoverable_directories(source_root: Path, *, materialize: bool) -> list[Path]:
    directories = set(iter_agent_directories(source_root))
    if not materialize:
        directories.update(iter_example_only_directories(source_root))
    return sorted(directories)


def materialize_example_configs(source_root: Path) -> list[Path]:
    """Copy each ``agent.yaml.example`` lacking a sibling ``agent.yaml`` into place.

    Returns the list of created ``agent.yaml`` paths (empty when nothing was
    missing). Raises :class:`DiscoveryError` if a copy fails (e.g. a read-only
    checkout) so the caller can point the user at ``shared-agents init``.
    """
    created: list[Path] = []
    for source_dir in iter_example_only_directories(source_root):
        example_path = source_dir / "agent.yaml.example"
        target_path = source_dir / "agent.yaml"
        try:
            shutil.copy2(example_path, target_path)
        except OSError as exc:
            raise DiscoveryError(
                f"could not create {target_path} from {example_path}: {exc} — "
                "run `shared-agents init` to bootstrap"
            ) from exc
        created.append(target_path)
    return created


def discover_agents(
    source_root: Path | None = None, *, materialize: bool = True
) -> list[AgentDefinition]:
    resolved_home = resolve_source_root(source_root)
    created = materialize_example_configs(resolved_home) if materialize else []
    if created:
        listing = ", ".join(str(path.parent) for path in created)
        print(
            f"note: created agent.yaml from agent.yaml.example for: {listing}",
            file=sys.stderr,
        )
    discovered: list[AgentDefinition] = []
    seen_names: dict[str, Path] = {}
    for source_dir in _discoverable_directories(resolved_home, materialize=materialize):
        try:
            config_filename = (
                "agent.yaml"
                if (source_dir / "agent.yaml").exists()
                else "agent.yaml.example"
            )
            agent = load_agent_definition(source_dir, config_filename=config_filename)
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
