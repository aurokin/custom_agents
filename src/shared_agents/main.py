from __future__ import annotations

import argparse
from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import sys
from typing import Any, Callable

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
from .linker import LinkSummary, prune_stale_links, sync_links
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


class CSVAction(argparse.Action):
    """argparse action that splits comma-separated values and accumulates."""

    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: Any,
        option_string: str | None = None,
    ) -> None:
        items = [item.strip() for item in str(values).split(",") if item.strip()]
        if not items:
            raise argparse.ArgumentError(
                self, f"{option_string} requires at least one non-empty value"
            )
        current = list(getattr(namespace, self.dest, None) or [])
        current.extend(items)
        setattr(namespace, self.dest, current)


def _add_selection_flags(subparser: argparse.ArgumentParser) -> None:
    subparser.add_argument(
        "--agents",
        action=CSVAction,
        metavar="A,B,...",
        help="Restrict to these agents (comma-separated; flag may repeat).",
    )
    subparser.add_argument(
        "--exclude-agents",
        action=CSVAction,
        metavar="A,B,...",
        help="Exclude these agents (comma-separated; flag may repeat).",
    )
    subparser.add_argument(
        "--harness",
        action=CSVAction,
        metavar="H,...",
        help="Restrict to these harnesses (comma-separated; flag may repeat).",
    )
    subparser.add_argument(
        "--exclude-harness",
        action=CSVAction,
        metavar="H,...",
        help="Exclude these harnesses (comma-separated; flag may repeat).",
    )
    subparser.add_argument(
        "--no-tprompt",
        action="store_true",
        help=(
            "Exclude tprompt from this run. "
            "On sync: skip writing tprompt outputs. "
            "On clean: leave existing tprompt entries in place."
        ),
    )


def _build_filters(args: argparse.Namespace) -> CLIFilters:
    return CLIFilters(
        include_agents=frozenset(args.agents) if args.agents else None,
        exclude_agents=frozenset(args.exclude_agents or ()),
        include_harness=frozenset(args.harness) if args.harness else None,
        exclude_harness=frozenset(args.exclude_harness or ()),
        no_tprompt=bool(args.no_tprompt),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="shared-agents", allow_abbrev=False)
    subparsers = parser.add_subparsers(dest="command", required=True)

    sync = subparsers.add_parser("sync", help="Generate consumer-native agents", allow_abbrev=False)
    sync.add_argument("--dry-run", action="store_true")
    sync.add_argument("--link-canonical", action="store_true")
    sync.add_argument("--source-root", "--agents-home", dest="source_root", type=Path)
    _add_selection_flags(sync)

    list_cmd = subparsers.add_parser("list", help="List discovered agents", allow_abbrev=False)
    list_cmd.add_argument("--source-root", "--agents-home", dest="source_root", type=Path)
    _add_selection_flags(list_cmd)

    validate = subparsers.add_parser("validate", help="Validate one or all agents", allow_abbrev=False)
    validate.add_argument("agent_name", nargs="?")
    validate.add_argument("--source-root", "--agents-home", dest="source_root", type=Path)

    clean = subparsers.add_parser("clean", help="Remove files owned by this tool", allow_abbrev=False)
    clean.add_argument("--dry-run", action="store_true")
    clean.add_argument("--source-root", "--agents-home", dest="source_root", type=Path)
    _add_selection_flags(clean)

    init = subparsers.add_parser(
        "init",
        help="Bootstrap agent.yaml from agent.yaml.example for every agent",
        allow_abbrev=False,
    )
    init.add_argument("--dry-run", action="store_true")
    init.add_argument("--source-root", "--agents-home", dest="source_root", type=Path)

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
                filters=_build_filters(args),
            )
        if args.command == "list":
            return _cmd_list(source_root, filters=_build_filters(args))
        if args.command == "validate":
            return _cmd_validate(source_root, args.agent_name)
        if args.command == "clean":
            return _cmd_clean(
                source_root,
                dry_run=args.dry_run,
                filters=_build_filters(args),
            )
        if args.command == "init":
            return _cmd_init(source_root, dry_run=args.dry_run)
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


def _cmd_sync(
    source_root: Path,
    dry_run: bool,
    link_canonical: bool,
    filters: CLIFilters | None = None,
) -> int:
    filters = filters or CLIFilters()
    agents = discover_agents(source_root)
    _check_tprompt_path_collisions(agents)
    manifest = load_manifest(source_root)
    desired = _empty_desired()
    counters = _empty_counters()

    writers = _always_on_writers()
    selections = resolve_selection(
        agents, filters, available_harnesses()
    )

    scope = (
        _build_scope(filters, {agent.name for agent in agents})
        if filters.is_active()
        else None
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

    removed = _remove_stale_generated_files(
        manifest, desired, scope=scope, dry_run=dry_run
    )

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
                generated_files=_merge_out_of_scope_entries(manifest, desired, scope),
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


def _cmd_list(source_root: Path, filters: CLIFilters | None = None) -> int:
    agents = discover_agents(source_root)
    filters = filters or CLIFilters()
    selections = resolve_selection(agents, filters, available_harnesses())
    for selection in selections:
        line = f"{selection.agent.name}: {selection.agent.description} ({selection.agent.source_dir})"
        if filters.is_active():
            harnesses = ", ".join(sorted(selection.harnesses)) or "<none>"
            line += f" [{harnesses}]"
        print(line)
    return 0


def _cmd_init(source_root: Path, dry_run: bool) -> int:
    agents_dir = source_root / "agents"
    verb = "would copy" if dry_run else "copy"
    summary_verb = "would copy" if dry_run else "copied"
    if not agents_dir.exists():
        print(f"init: {summary_verb} 0, skipped 0")
        return 0
    copied = 0
    skipped = 0
    for example_path in sorted(agents_dir.rglob("agent.yaml.example")):
        target = example_path.with_name("agent.yaml")
        if target.exists():
            skipped += 1
            continue
        if not dry_run:
            shutil.copy2(example_path, target)
        copied += 1
        print(f"init: {verb} {example_path} -> {target}")
    print(f"init: {summary_verb} {copied}, skipped {skipped}")
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


def _cmd_clean(
    source_root: Path,
    dry_run: bool,
    filters: CLIFilters | None = None,
) -> int:
    filters = filters or CLIFilters()
    manifest = load_manifest(source_root)
    desired = _empty_desired()

    if filters.is_active():
        _validate_clean_filters(filters, manifest, source_root)
        agent_universe = _manifest_agents(manifest)
        try:
            discovered = discover_agents(source_root)
        except DiscoveryError as exc:
            print(
                f"warn: agent discovery failed during clean: {exc}; "
                "using manifest-only universe",
                file=sys.stderr,
            )
            discovered = []
        agent_universe.update(agent.name for agent in discovered)
        scope: _Scope | None = _build_scope(filters, agent_universe)
        _warn_about_ghost_entries(manifest, scope)
    else:
        scope = None

    removed = _remove_stale_generated_files(
        manifest, desired, scope=scope, dry_run=dry_run, remove_all=True
    )

    if filters.is_active():
        link_summary = LinkSummary()
        link_messages: list[str] = []
    else:
        link_summary, link_messages = prune_stale_links(
            manifest.linked_targets,
            dry_run=dry_run,
        )
    for message in link_messages:
        if message.startswith("remove managed") or message.startswith("warn"):
            print(message)

    if not dry_run:
        if scope is None:
            save_manifest(source_root, Manifest.empty())
        else:
            preserved = _merge_out_of_scope_entries(manifest, desired, scope)
            save_manifest(
                source_root,
                Manifest(
                    generated_files=preserved,
                    linked_targets=manifest.linked_targets,
                ),
            )
        remove_legacy_manifest(source_root)
    print(
        f"clean: removed={removed} managed-links={link_summary.removed} "
        f"warned={link_summary.warned}"
    )
    return 0


def _manifest_agents(manifest: Manifest) -> set[str]:
    agents: set[str] = set()
    for entries in manifest.generated_files.values():
        for entry in entries:
            if entry.agent:
                agents.add(entry.agent)
    return agents


def _validate_clean_filters(
    filters: CLIFilters, manifest: Manifest, source_root: Path
) -> None:
    for keywords, label in (
        (filters.include_harness, "harness filter include"),
        (filters.exclude_harness, "harness filter exclude"),
    ):
        if not keywords:
            continue
        unknown = sorted(set(keywords) - set(HARNESS_KEYWORDS))
        if unknown:
            allowed = ", ".join(HARNESS_KEYWORDS)
            raise ValueError(
                f"Unknown harness keyword(s) in {label}: {', '.join(unknown)} "
                f"(allowed: {allowed})"
            )
    requested_agents = (filters.include_agents or frozenset()) | filters.exclude_agents
    if not requested_agents:
        return
    universe = _manifest_agents(manifest)
    try:
        universe.update(agent.name for agent in discover_agents(source_root))
    except DiscoveryError:
        pass
    unknown_agents = sorted(requested_agents - universe)
    if unknown_agents:
        raise ValueError(
            f"Unknown agent name(s): {', '.join(unknown_agents)}"
        )


def _warn_about_ghost_entries(manifest: Manifest, scope: _Scope) -> None:
    if not scope.agent_filter_active:
        return
    ghost_count = sum(
        1
        for entries in manifest.generated_files.values()
        for entry in entries
        if not entry.agent
    )
    if ghost_count:
        print(
            f"note: {ghost_count} manifest entries lack agent attribution and "
            "were skipped; run an unscoped sync to re-attribute or unscoped "
            "clean to remove them.",
            file=sys.stderr,
        )




@dataclass(frozen=True)
class _Scope:
    agents: frozenset[str]
    harnesses: frozenset[str]
    agent_filter_active: bool

    def covers(self, entry: ManifestEntry, harness: str) -> bool:
        if harness not in self.harnesses:
            return False
        if not entry.agent:
            return not self.agent_filter_active
        return entry.agent in self.agents


def _build_scope(filters: CLIFilters, agent_universe: set[str]) -> _Scope:
    if filters.include_agents is not None:
        selected_agents = set(filters.include_agents)
    else:
        selected_agents = set(agent_universe)
    selected_agents -= filters.exclude_agents

    selected_harnesses = set(HARNESS_KEYWORDS)
    if filters.include_harness is not None:
        selected_harnesses &= filters.include_harness
    selected_harnesses -= filters.exclude_harness
    if filters.no_tprompt:
        selected_harnesses.discard("tprompt")

    return _Scope(
        agents=frozenset(selected_agents),
        harnesses=frozenset(selected_harnesses),
        agent_filter_active=(
            filters.include_agents is not None or bool(filters.exclude_agents)
        ),
    )


def _merge_out_of_scope_entries(
    manifest: Manifest,
    desired: dict[str, list[ManifestEntry]],
    scope: _Scope | None,
) -> dict[str, list[ManifestEntry]]:
    if scope is None:
        return {harness: list(desired[harness]) for harness in HARNESS_KEYWORDS}
    merged: dict[str, list[ManifestEntry]] = {
        harness: list(desired[harness]) for harness in HARNESS_KEYWORDS
    }
    for harness, entries in manifest.generated_files.items():
        existing_paths = {entry.path for entry in merged.get(harness, [])}
        for entry in entries:
            if scope.covers(entry, harness):
                continue
            # Dedupe by path: freshly written entries with proper agent
            # attribution win over migrated (agent="") ghosts at the same path.
            if entry.path in existing_paths:
                continue
            merged.setdefault(harness, []).append(entry)
            existing_paths.add(entry.path)
    return merged


def _remove_stale_generated_files(
    manifest: Manifest,
    desired: dict[str, list[ManifestEntry]],
    *,
    scope: _Scope | None = None,
    dry_run: bool,
    remove_all: bool = False,
) -> int:
    removed = 0
    for consumer, entries in manifest.generated_files.items():
        desired_paths = {entry.path for entry in desired.get(consumer, [])}
        for entry in entries:
            if scope is not None and not scope.covers(entry, consumer):
                continue
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
