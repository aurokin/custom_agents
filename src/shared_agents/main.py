from __future__ import annotations

import argparse
from dataclasses import dataclass
import os
from pathlib import Path
import sys
from typing import Callable

from .discover import DiscoveryError, discover_agents, resolve_source_root
from .generators.claude import write_claude_agent
from .generators.copilot import write_copilot_agent
from .generators.codex import write_codex_agent
from .generators.cursor import write_cursor_agent
from .generators.gemini import write_gemini_agent
from .generators.tprompt import (
    tprompt_executable,
    tprompt_output_path,
    write_tprompt_agent,
)
from .harnesses import HARNESS_KEYWORDS, available_harnesses
from .linker import prune_stale_links, sync_links
from .manifest import (
    Manifest,
    ManifestEntry,
    load_manifest,
    remove_legacy_manifest,
    save_manifest,
)
from .schema import AgentDefinition
from .selection import CLIFilters, resolve_selection


@dataclass(frozen=True)
class HarnessWriter:
    path: Callable[[AgentDefinition], Path]
    write: Callable[..., str]


def _claude_path(agent: AgentDefinition) -> Path:
    return Path.home() / ".claude" / "agents" / f"{agent.output_name}.md"


def _copilot_path(agent: AgentDefinition) -> Path:
    return _resolve_copilot_home() / "agents" / f"{agent.output_name}.agent.md"


def _codex_path(agent: AgentDefinition) -> Path:
    return Path.home() / ".codex" / "agents" / f"{agent.output_name}.toml"


def _cursor_path(agent: AgentDefinition) -> Path:
    return Path.home() / ".cursor" / "agents" / f"{agent.output_name}.md"


def _gemini_path(agent: AgentDefinition) -> Path:
    return Path.home() / ".gemini" / "agents" / f"{agent.output_name}.md"


def _always_on_writers() -> dict[str, HarnessWriter]:
    return {
        "claude": HarnessWriter(path=_claude_path, write=write_claude_agent),
        "copilot": HarnessWriter(path=_copilot_path, write=write_copilot_agent),
        "codex": HarnessWriter(path=_codex_path, write=write_codex_agent),
        "cursor": HarnessWriter(path=_cursor_path, write=write_cursor_agent),
        "gemini": HarnessWriter(path=_gemini_path, write=write_gemini_agent),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="shared-agents")
    subparsers = parser.add_subparsers(dest="command", required=True)

    sync = subparsers.add_parser("sync", help="Generate consumer-native agents")
    sync.add_argument("--dry-run", action="store_true")
    sync.add_argument("--link-canonical", action="store_true")
    sync.add_argument("--source-root", "--agents-home", dest="source_root", type=Path)

    list_cmd = subparsers.add_parser("list", help="List discovered agents")
    list_cmd.add_argument("--source-root", "--agents-home", dest="source_root", type=Path)

    validate = subparsers.add_parser("validate", help="Validate one or all agents")
    validate.add_argument("agent_name", nargs="?")
    validate.add_argument("--source-root", "--agents-home", dest="source_root", type=Path)

    clean = subparsers.add_parser("clean", help="Remove files owned by this tool")
    clean.add_argument("--dry-run", action="store_true")
    clean.add_argument("--source-root", "--agents-home", dest="source_root", type=Path)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    source_root = resolve_source_root(args.source_root)

    try:
        if args.command == "sync":
            return _cmd_sync(
                source_root,
                dry_run=args.dry_run,
                link_canonical=args.link_canonical,
            )
        if args.command == "list":
            return _cmd_list(source_root)
        if args.command == "validate":
            return _cmd_validate(source_root, args.agent_name)
        if args.command == "clean":
            return _cmd_clean(source_root, dry_run=args.dry_run)
    except DiscoveryError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    parser.print_help()
    return 1


def _empty_desired() -> dict[str, list[ManifestEntry]]:
    return {harness: [] for harness in HARNESS_KEYWORDS}


def _empty_counters() -> dict[str, dict[str, int]]:
    return {
        harness: {"written": 0, "unchanged": 0, "skipped": 0}
        for harness in HARNESS_KEYWORDS
    }


def _bucket_for(status: str) -> str:
    return "unchanged" if status == "unchanged" else "written"


def _cmd_sync(source_root: Path, dry_run: bool, link_canonical: bool) -> int:
    agents = discover_agents(source_root)
    _check_tprompt_path_collisions(agents)
    manifest = load_manifest(source_root)
    desired = _empty_desired()
    counters = _empty_counters()

    writers = _always_on_writers()
    selections = resolve_selection(
        agents, CLIFilters(), available_harnesses()
    )

    for selection in selections:
        for harness, writer in writers.items():
            if harness not in selection.harnesses:
                continue
            path = writer.path(selection.agent)
            status = writer.write(path, selection.agent, dry_run=dry_run)
            desired[harness].append(
                ManifestEntry(agent=selection.agent.name, path=str(path))
            )
            counters[harness][_bucket_for(status)] += 1

    tprompt_bin = tprompt_executable()
    for selection in selections:
        agent = selection.agent
        if not agent.tprompt.enabled:
            continue
        tprompt_path = tprompt_output_path(agent)
        if "tprompt" in selection.harnesses and tprompt_bin is not None:
            status = write_tprompt_agent(
                tprompt_path, agent, executable=tprompt_bin, dry_run=dry_run
            )
            counters["tprompt"][_bucket_for(status)] += 1
            desired["tprompt"].append(
                ManifestEntry(agent=agent.name, path=str(tprompt_path))
            )
            continue
        counters["tprompt"]["skipped"] += 1
        if tprompt_path.exists():
            desired["tprompt"].append(
                ManifestEntry(agent=agent.name, path=str(tprompt_path))
            )

    if counters["tprompt"]["skipped"] > 0 and tprompt_bin is None:
        print(
            "warn: tprompt not on PATH; skipping tprompt export for "
            f"{counters['tprompt']['skipped']} agent(s)",
            file=sys.stderr,
        )

    removed = _remove_stale_generated_files(manifest, desired, dry_run=dry_run)

    if link_canonical:
        link_summary, link_messages, linked_targets = sync_links(
            source_root,
            managed_links=manifest.linked_targets,
            dry_run=dry_run,
        )
    else:
        link_summary, link_messages = prune_stale_links(
            manifest.linked_targets,
            dry_run=dry_run,
        )
        linked_targets = {}
    for message in link_messages:
        print(message)

    if not dry_run:
        save_manifest(
            source_root,
            Manifest(
                generated_files={harness: list(desired[harness]) for harness in HARNESS_KEYWORDS},
                linked_targets=linked_targets,
            ),
        )
        remove_legacy_manifest(source_root)

    print(_format_sync_summary(counters, removed, link_summary, list(writers.keys())))
    return 0


def _format_sync_summary(
    counters: dict[str, dict[str, int]],
    removed: int,
    link_summary,
    always_on: list[str],
) -> str:
    parts = ["sync:"]
    for harness in always_on:
        c = counters[harness]
        parts.append(f" {harness} written={c['written']} unchanged={c['unchanged']};")
    t = counters["tprompt"]
    parts.append(
        f" tprompt written={t['written']} unchanged={t['unchanged']} skipped={t['skipped']};"
    )
    parts.append(f" removed={removed};")
    parts.append(
        f" links created={link_summary.created} updated={link_summary.updated}"
        f" skipped={link_summary.skipped} warned={link_summary.warned}"
        f" removed={link_summary.removed}"
    )
    return "".join(parts)


def _cmd_list(source_root: Path) -> int:
    agents = discover_agents(source_root)
    for agent in agents:
        print(f"{agent.name}: {agent.description} ({agent.source_dir})")
    return 0


def _cmd_validate(source_root: Path, agent_name: str | None) -> int:
    agents = discover_agents(source_root)
    if agent_name:
        agents = [agent for agent in agents if agent.name == agent_name]
        if not agents:
            print(f"Agent not found: {agent_name}", file=sys.stderr)
            return 1
    for agent in agents:
        print(f"valid {agent.name} ({agent.source_dir})")
    return 0


def _cmd_clean(source_root: Path, dry_run: bool) -> int:
    manifest = load_manifest(source_root)
    desired = _empty_desired()
    removed = _remove_stale_generated_files(manifest, desired, dry_run=dry_run, remove_all=True)
    link_summary, link_messages = prune_stale_links(
        manifest.linked_targets,
        dry_run=dry_run,
    )
    for message in link_messages:
        if message.startswith("remove managed") or message.startswith("warn"):
            print(message)
    if not dry_run:
        save_manifest(source_root, Manifest.empty())
        remove_legacy_manifest(source_root)
    print(
        f"clean: removed={removed} managed-links={link_summary.removed} "
        f"warned={link_summary.warned}"
    )
    return 0


def _remove_stale_generated_files(
    manifest: Manifest,
    desired: dict[str, list[ManifestEntry]],
    *,
    dry_run: bool,
    remove_all: bool = False,
) -> int:
    removed = 0
    for consumer, entries in manifest.generated_files.items():
        desired_paths = {entry.path for entry in desired.get(consumer, [])}
        for entry in entries:
            if not remove_all and entry.path in desired_paths:
                continue
            path = Path(entry.path)
            if path.exists() or path.is_symlink():
                if not dry_run:
                    path.unlink()
                removed += 1
                print(f"remove generated {path}")
    return removed


def _check_tprompt_path_collisions(agents: list[AgentDefinition]) -> None:
    seen: dict[str, str] = {}
    for agent in agents:
        if not agent.tprompt.enabled:
            continue
        path = str(tprompt_output_path(agent))
        if path in seen:
            raise DiscoveryError(
                f"Duplicate tprompt output path {path!r} for agents "
                f"{seen[path]!r} and {agent.name!r}; set a unique tprompt.filename."
            )
        seen[path] = agent.name


def _resolve_copilot_home() -> Path:
    configured = os.environ.get("COPILOT_HOME")
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".copilot"


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
