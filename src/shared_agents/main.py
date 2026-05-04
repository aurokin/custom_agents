from __future__ import annotations

import argparse
from dataclasses import dataclass
import os
from pathlib import Path
import sys

from .discover import DiscoveryError, discover_agents, resolve_source_root
from .generators.claude import write_claude_agent
from .generators.copilot import write_copilot_agent
from .generators.codex import write_codex_agent
from .generators.gemini import write_gemini_agent
from .generators.tprompt import (
    tprompt_executable,
    tprompt_output_path,
    write_tprompt_agent,
)
from .linker import prune_stale_links, sync_links
from .manifest import Manifest, load_manifest, remove_legacy_manifest, save_manifest
from .schema import AgentDefinition


@dataclass
class SyncSummary:
    claude_written: int = 0
    claude_unchanged: int = 0
    copilot_written: int = 0
    copilot_unchanged: int = 0
    codex_written: int = 0
    codex_unchanged: int = 0
    gemini_written: int = 0
    gemini_unchanged: int = 0
    tprompt_written: int = 0
    tprompt_unchanged: int = 0
    tprompt_skipped: int = 0
    removed: int = 0


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


def _cmd_sync(source_root: Path, dry_run: bool, link_canonical: bool) -> int:
    agents = discover_agents(source_root)
    _check_tprompt_path_collisions(agents)
    manifest = load_manifest(source_root)
    summary = SyncSummary()
    desired = {
        "claude": [],
        "copilot": [],
        "codex": [],
        "gemini": [],
        "tprompt": [],
    }
    copilot_home = _resolve_copilot_home()
    gemini_home = Path.home() / ".gemini"
    tprompt_bin = tprompt_executable()
    tprompt_warning_pending = any(agent.tprompt.enabled for agent in agents) and (
        tprompt_bin is None
    )

    for agent in agents:
        claude_path = Path.home() / ".claude" / "agents" / f"{agent.output_name}.md"
        copilot_path = copilot_home / "agents" / f"{agent.output_name}.agent.md"
        codex_path = Path.home() / ".codex" / "agents" / f"{agent.output_name}.toml"
        gemini_path = gemini_home / "agents" / f"{agent.output_name}.md"
        desired["claude"].append(str(claude_path))
        desired["copilot"].append(str(copilot_path))
        desired["codex"].append(str(codex_path))
        desired["gemini"].append(str(gemini_path))

        claude_status = write_claude_agent(claude_path, agent, dry_run=dry_run)
        if claude_status == "unchanged":
            summary.claude_unchanged += 1
        else:
            summary.claude_written += 1

        copilot_status = write_copilot_agent(copilot_path, agent, dry_run=dry_run)
        if copilot_status == "unchanged":
            summary.copilot_unchanged += 1
        else:
            summary.copilot_written += 1

        codex_status = write_codex_agent(codex_path, agent, dry_run=dry_run)
        if codex_status == "unchanged":
            summary.codex_unchanged += 1
        else:
            summary.codex_written += 1

        gemini_status = write_gemini_agent(gemini_path, agent, dry_run=dry_run)
        if gemini_status == "unchanged":
            summary.gemini_unchanged += 1
        else:
            summary.gemini_written += 1

        if not agent.tprompt.enabled:
            continue
        tprompt_path = tprompt_output_path(agent)
        desired["tprompt"].append(str(tprompt_path))
        if tprompt_bin is None:
            summary.tprompt_skipped += 1
            continue
        tprompt_status = write_tprompt_agent(
            tprompt_path, agent, executable=tprompt_bin, dry_run=dry_run
        )
        if tprompt_status == "unchanged":
            summary.tprompt_unchanged += 1
        else:
            summary.tprompt_written += 1

    if tprompt_warning_pending:
        print(
            "warn: tprompt not on PATH; skipping tprompt export for "
            f"{summary.tprompt_skipped} agent(s)",
            file=sys.stderr,
        )

    removed = _remove_stale_generated_files(manifest, desired, dry_run=dry_run)
    summary.removed = removed

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
                generated_files={
                    "claude": desired["claude"],
                    "copilot": desired["copilot"],
                    "codex": desired["codex"],
                    "gemini": desired["gemini"],
                    "tprompt": desired["tprompt"],
                },
                linked_targets=linked_targets,
            ),
        )
        remove_legacy_manifest(source_root)

    print(
        "sync:"
        f" claude written={summary.claude_written} unchanged={summary.claude_unchanged};"
        f" copilot written={summary.copilot_written} unchanged={summary.copilot_unchanged};"
        f" codex written={summary.codex_written} unchanged={summary.codex_unchanged};"
        f" gemini written={summary.gemini_written} unchanged={summary.gemini_unchanged};"
        f" tprompt written={summary.tprompt_written}"
        f" unchanged={summary.tprompt_unchanged} skipped={summary.tprompt_skipped};"
        f" removed={summary.removed};"
        f" links created={link_summary.created} updated={link_summary.updated}"
        f" skipped={link_summary.skipped} warned={link_summary.warned}"
        f" removed={link_summary.removed}"
    )
    return 0


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
    desired = {
        "claude": [],
        "copilot": [],
        "codex": [],
        "gemini": [],
        "tprompt": [],
    }
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
    desired: dict[str, list[str]],
    *,
    dry_run: bool,
    remove_all: bool = False,
) -> int:
    removed = 0
    for consumer, paths in manifest.generated_files.items():
        desired_paths = set(desired.get(consumer, []))
        for path_str in paths:
            if not remove_all and path_str in desired_paths:
                continue
            path = Path(path_str)
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
