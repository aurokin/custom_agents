from __future__ import annotations

import argparse
from dataclasses import dataclass
import os
from pathlib import Path
import sys
from typing import Any, Callable

from .discover import (
    DiscoveryError,
    discover_agents,
    iter_example_only_directories,
    materialize_example_configs,
    resolve_source_root,
)
from .generators.claude import write_claude_agent
from .generators.copilot import write_copilot_agent
from .generators.codex import write_codex_agent
from .generators.cursor import write_cursor_agent
from .generators.gemini import write_gemini_agent
from .generators.opencode import write_opencode_agent
from .generators.skills import (
    claude_skill_output_path,
    hermes_skill_output_path,
    resolve_agent_skills_dir,
    resolve_claude_skills_dir,
    resolve_hermes_skills_dir,
    skill_output_path,
    write_agent_skill,
    write_hermes_skill,
)
from .generators.tprompt import (
    tprompt_executable,
    tprompt_output_path,
    write_tprompt_agent,
)
from .harnesses import HARNESS_KEYWORDS, SKILL_HARNESS_KEYWORDS, available_harnesses
from .linker import LinkSummary, prune_stale_links, sync_links
from .manifest import (
    Manifest,
    ManifestEntry,
    load_manifest,
    remove_legacy_manifest,
    save_manifest,
)
from .schema import AgentDefinition
from .selection import AgentSelection, CLIFilters, cli_harness_set, resolve_selection


@dataclass(frozen=True)
class HarnessWriter:
    path: Callable[[AgentDefinition], Path]
    write: Callable[..., str]


@dataclass(frozen=True)
class SyncPreview:
    write_paths: tuple[Path, ...]
    remove_paths: tuple[Path, ...]
    link_messages: tuple[str, ...]


def _claude_path(agent: AgentDefinition) -> Path:
    return Path.home() / ".claude" / "agents" / f"{agent.output_name}.md"


def _copilot_path(agent: AgentDefinition) -> Path:
    return _resolve_copilot_home() / "agents" / f"{agent.output_name}.agent.md"


def _codex_path(agent: AgentDefinition) -> Path:
    return Path.home() / ".codex" / "agents" / f"{agent.output_name}.toml"


def _cursor_path(agent: AgentDefinition) -> Path:
    return Path.home() / ".cursor" / "agents" / f"{agent.output_name}.md"


def _opencode_path(agent: AgentDefinition) -> Path:
    return Path.home() / ".config" / "opencode" / "agents" / f"{agent.output_name}.md"


def _gemini_path(agent: AgentDefinition) -> Path:
    return Path.home() / ".gemini" / "agents" / f"{agent.output_name}.md"


def _agent_skill_path(agent: AgentDefinition) -> Path:
    return skill_output_path(agent)


def _claude_skill_path(agent: AgentDefinition) -> Path:
    return claude_skill_output_path(agent)


def _hermes_skill_path(agent: AgentDefinition) -> Path:
    return hermes_skill_output_path(agent)


def _always_on_writers() -> dict[str, HarnessWriter]:
    return {
        "claude": HarnessWriter(path=_claude_path, write=write_claude_agent),
        "claude-skills": HarnessWriter(path=_claude_skill_path, write=write_agent_skill),
        "copilot": HarnessWriter(path=_copilot_path, write=write_copilot_agent),
        "codex": HarnessWriter(path=_codex_path, write=write_codex_agent),
        "cursor": HarnessWriter(path=_cursor_path, write=write_cursor_agent),
        "opencode": HarnessWriter(path=_opencode_path, write=write_opencode_agent),
        "gemini": HarnessWriter(path=_gemini_path, write=write_gemini_agent),
        "agent-skills": HarnessWriter(path=_agent_skill_path, write=write_agent_skill),
        "hermes-skills": HarnessWriter(
            path=_hermes_skill_path, write=write_hermes_skill
        ),
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

    tui = subparsers.add_parser(
        "tui",
        help="Interactively select agents and harnesses",
        allow_abbrev=False,
    )
    tui.add_argument("--source-root", "--agents-home", dest="source_root", type=Path)

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
        if args.command == "tui":
            from .tui import _cmd_tui

            return _cmd_tui(source_root)
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
        harness: {"written": 0, "unchanged": 0, "skipped": 0, "excluded": 0}
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
    agents = discover_agents(source_root, materialize=not dry_run)
    _check_tprompt_path_collisions(agents)
    manifest = load_manifest(source_root)
    desired = _empty_desired()
    counters = _empty_counters()

    writers = _always_on_writers()
    selections = resolve_selection(
        agents, filters, available_harnesses()
    )
    _check_skill_path_collisions(agents, filters)

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
    tprompt_selections = resolve_selection(agents, filters, HARNESS_KEYWORDS)
    for selection in tprompt_selections:
        agent = selection.agent
        if not agent.tprompt.enabled:
            continue
        tprompt_path = tprompt_output_path(agent)
        if "tprompt" not in selection.harnesses:
            counters["tprompt"]["excluded"] += 1
            if agent.export != "agent":
                continue
        elif tprompt_bin is None:
            # tprompt selected for this agent but its binary isn't on PATH.
            counters["tprompt"]["skipped"] += 1
        else:
            status = write_tprompt_agent(
                tprompt_path, agent, executable=tprompt_bin, dry_run=dry_run
            )
            counters["tprompt"][_bucket_for(status)] += 1
            desired["tprompt"].append(
                ManifestEntry(agent=agent.name, path=str(tprompt_path))
            )
            continue
        # Not produced this run; leave any existing output (and manifest entry) be.
        if tprompt_path.exists():
            desired["tprompt"].append(
                ManifestEntry(agent=agent.name, path=str(tprompt_path))
            )

    if counters["tprompt"]["skipped"]:
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


def build_sync_preview(
    source_root: Path,
    filters: CLIFilters | None = None,
) -> SyncPreview:
    filters = filters or CLIFilters()
    agents = discover_agents(source_root, materialize=False)
    _check_tprompt_path_collisions(agents)
    _check_skill_path_collisions(agents, filters)
    manifest = load_manifest(source_root)
    desired = _empty_desired()
    write_paths: list[Path] = []

    writers = _always_on_writers()
    selections = resolve_selection(agents, filters, available_harnesses())
    for selection in selections:
        for harness, writer in writers.items():
            if harness not in selection.harnesses:
                continue
            path = writer.path(selection.agent)
            status = writer.write(path, selection.agent, dry_run=True)
            if status != "unchanged":
                write_paths.append(path)
            desired[harness].append(
                ManifestEntry(agent=selection.agent.name, path=str(path))
            )

    tprompt_bin = tprompt_executable()
    tprompt_selections = resolve_selection(agents, filters, HARNESS_KEYWORDS)
    for selection in tprompt_selections:
        agent = selection.agent
        if not agent.tprompt.enabled:
            continue
        tprompt_path = tprompt_output_path(agent)
        if "tprompt" not in selection.harnesses:
            if agent.export != "agent":
                continue
        elif tprompt_bin is None:
            pass
        else:
            status = write_tprompt_agent(
                tprompt_path, agent, executable=tprompt_bin, dry_run=True
            )
            if status != "unchanged":
                write_paths.append(tprompt_path)
            desired["tprompt"].append(
                ManifestEntry(agent=agent.name, path=str(tprompt_path))
            )
            continue
        if tprompt_path.exists():
            desired["tprompt"].append(
                ManifestEntry(agent=agent.name, path=str(tprompt_path))
            )

    scope = (
        _build_scope(filters, {agent.name for agent in agents})
        if filters.is_active()
        else None
    )
    return SyncPreview(
        write_paths=tuple(write_paths),
        remove_paths=tuple(
            path
            for path, _consumer in _stale_generated_paths(
                manifest, desired, scope=scope
            )
        ),
        link_messages=tuple(_preview_link_messages(manifest)),
    )


def _preview_link_messages(manifest: Manifest) -> list[str]:
    _link_summary, link_messages = prune_stale_links(
        manifest.linked_targets,
        dry_run=True,
    )
    return [
        message
        for message in link_messages
        if message.startswith("remove managed") or message.startswith("warn")
    ]


def _format_sync_summary(
    counters: dict[str, dict[str, int]],
    removed: int,
    link_summary: LinkSummary,
    always_on: list[str],
) -> str:
    parts = ["sync:"]
    for harness in always_on:
        c = counters[harness]
        if harness in SKILL_HARNESS_KEYWORDS:
            parts.append(
                f" {harness} written={c['written']} unchanged={c['unchanged']}"
                f" skipped={c['skipped']};"
            )
        else:
            parts.append(f" {harness} written={c['written']} unchanged={c['unchanged']};")
    t = counters["tprompt"]
    parts.append(
        f" tprompt written={t['written']} unchanged={t['unchanged']}"
        f" skipped={t['skipped']} excluded={t['excluded']};"
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
    summary_verb = "would copy" if dry_run else "copied"
    if not agents_dir.exists():
        print(f"warn: no agents/ directory under {source_root}", file=sys.stderr)
        print(f"init: {summary_verb} 0, skipped 0")
        return 0
    pending = iter_example_only_directories(source_root)
    skipped = len(list(agents_dir.rglob("agent.yaml.example"))) - len(pending)
    if dry_run:
        for source_dir in pending:
            print(
                f"init: would copy {source_dir / 'agent.yaml.example'} "
                f"-> {source_dir / 'agent.yaml'}"
            )
        print(f"init: would copy {len(pending)}, skipped {skipped}")
        return 0
    created = materialize_example_configs(source_root)
    for target in created:
        print(f"init: copy {target.with_name('agent.yaml.example')} -> {target}")
    print(f"init: copied {len(created)}, skipped {skipped}")
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
        _validate_clean_filters(
            filters, manifest, source_root, materialize=not dry_run
        )
        agent_universe = _manifest_agents(manifest)
        try:
            discovered = discover_agents(source_root, materialize=not dry_run)
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
    filters: CLIFilters,
    manifest: Manifest,
    source_root: Path,
    *,
    materialize: bool,
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
        universe.update(
            agent.name
            for agent in discover_agents(source_root, materialize=materialize)
        )
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

    selected_harnesses = cli_harness_set(HARNESS_KEYWORDS, filters)

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
    paths = _stale_generated_paths(
        manifest,
        desired,
        scope=scope,
        remove_all=remove_all,
    )
    for path, consumer in paths:
        if not dry_run:
            path.unlink()
            _prune_empty_generated_parent(path, consumer)
        print(f"remove generated {path}")
    return len(paths)


def _stale_generated_paths(
    manifest: Manifest,
    desired: dict[str, list[ManifestEntry]],
    *,
    scope: _Scope | None = None,
    remove_all: bool = False,
) -> list[tuple[Path, str]]:
    paths: list[tuple[Path, str]] = []
    seen_paths: set[str] = set()
    for consumer, entries in manifest.generated_files.items():
        desired_paths = {entry.path for entry in desired.get(consumer, [])}
        for entry in entries:
            if scope is not None and not scope.covers(entry, consumer):
                continue
            if not remove_all and entry.path in desired_paths:
                continue
            path = Path(entry.path)
            if path.exists() or path.is_symlink():
                if entry.path in seen_paths:
                    continue
                seen_paths.add(entry.path)
                paths.append((path, consumer))
    return paths


def _prune_empty_generated_parent(path: Path, consumer: str) -> None:
    if consumer not in SKILL_HARNESS_KEYWORDS:
        return
    roots = {
        "agent-skills": resolve_agent_skills_dir,
        "claude-skills": resolve_claude_skills_dir,
        "hermes-skills": resolve_hermes_skills_dir,
    }
    root = roots[consumer]()
    try:
        path.parent.relative_to(root)
    except ValueError:
        return
    for directory in (path.parent, root):
        try:
            directory.rmdir()
        except OSError:
            break


def _check_skill_path_collisions(
    agents: list[AgentDefinition], filters: CLIFilters
) -> None:
    selections = resolve_selection(agents, CLIFilters(), HARNESS_KEYWORDS)
    if filters.is_active():
        selections.extend(resolve_selection(agents, filters, HARNESS_KEYWORDS))
    _check_skill_selection_path_collisions(selections)


def _check_skill_selection_path_collisions(selections: list[AgentSelection]) -> None:
    seen: dict[str, str] = {}
    checked: set[tuple[str, str, str]] = set()
    for selection in selections:
        for harness in SKILL_HARNESS_KEYWORDS:
            if harness not in selection.harnesses:
                continue
            path = str(_skill_path_for_harness(harness, selection.agent))
            observation = (selection.agent.name, harness, path)
            if observation in checked:
                continue
            checked.add(observation)
            if path in seen:
                raise DiscoveryError(
                    f"Duplicate skill output path {path!r} for agents "
                    f"{seen[path]!r} and {selection.agent.name!r}; set a unique skill.name."
                )
            seen[path] = selection.agent.name


def _skill_path_for_harness(harness: str, agent: AgentDefinition) -> Path:
    if harness == "claude-skills":
        return claude_skill_output_path(agent)
    if harness == "hermes-skills":
        return hermes_skill_output_path(agent)
    return skill_output_path(agent)


def _check_tprompt_path_collisions(agents: list[AgentDefinition]) -> None:
    seen: dict[str, str] = {}
    for agent in agents:
        if agent.export != "agent":
            continue
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
