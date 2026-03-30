from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class LinkSummary:
    created: int = 0
    updated: int = 0
    skipped: int = 0
    warned: int = 0
    removed: int = 0

    def merge(self, other: "LinkSummary") -> None:
        self.created += other.created
        self.updated += other.updated
        self.skipped += other.skipped
        self.warned += other.warned
        self.removed += other.removed


def sync_links(
    agents_home: Path,
    managed_links: dict[str, str] | None = None,
    dry_run: bool = False,
) -> tuple[LinkSummary, list[str], dict[str, str]]:
    summary = LinkSummary()
    messages: list[str] = []
    desired_links = build_desired_links(agents_home)
    parent_dirs = sorted({target.parent for _, target in desired_links})
    for directory in parent_dirs:
        if not dry_run:
            directory.mkdir(parents=True, exist_ok=True)

    for source, target in desired_links:
        outcome = _ensure_symlink(source, target, dry_run)
        summary.merge(outcome[0])
        messages.extend(outcome[1])

    stale_summary, stale_messages = prune_stale_links(
        managed_links or {},
        desired_targets={str(target): str(source) for source, target in desired_links},
        dry_run=dry_run,
    )
    summary.merge(stale_summary)
    messages.extend(stale_messages)

    return (
        summary,
        messages,
        {str(target): str(source) for source, target in desired_links},
    )


def build_desired_links(agents_home: Path) -> list[tuple[Path, Path]]:
    home = Path.home()
    claude_dir = home / ".claude"
    codex_dir = home / ".codex"
    desired: list[tuple[Path, Path]] = []

    source_agents_md = agents_home / "AGENTS.md"
    if source_agents_md.exists():
        desired.extend(
            [
                (source_agents_md, claude_dir / "CLAUDE.md"),
                (source_agents_md, codex_dir / "AGENTS.md"),
            ]
        )

    skills_dir = agents_home / "skills"
    if skills_dir.exists():
        for source_skill in sorted(path for path in skills_dir.iterdir() if path.is_dir()):
            desired.extend(
                [
                    (source_skill, claude_dir / "skills" / source_skill.name),
                    (source_skill, codex_dir / "skills" / source_skill.name),
                ]
            )

    return desired


def prune_stale_links(
    managed_links: dict[str, str],
    desired_targets: dict[str, str] | None = None,
    dry_run: bool = False,
) -> tuple[LinkSummary, list[str]]:
    summary = LinkSummary()
    messages: list[str] = []
    desired_targets = desired_targets or {}

    for target_str, source_str in managed_links.items():
        if target_str in desired_targets:
            continue
        result = _remove_owned_symlink(Path(target_str), Path(source_str), dry_run)
        summary.merge(result[0])
        messages.extend(result[1])

    return summary, messages


def _ensure_symlink(source: Path, target: Path, dry_run: bool) -> tuple[LinkSummary, list[str]]:
    summary = LinkSummary()
    messages: list[str] = []

    if target.is_symlink():
        current_target = target.resolve(strict=False)
        if current_target == source.resolve():
            summary.skipped += 1
            messages.append(f"skip {target} -> {source}")
            return summary, messages
        if not dry_run:
            target.unlink()
        summary.updated += 1
        messages.append(f"update {target} -> {source}")
    elif target.exists():
        summary.warned += 1
        messages.append(f"warn {target} exists and is not a symlink")
        return summary, messages
    else:
        summary.created += 1
        messages.append(f"create {target} -> {source}")

    if not dry_run:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.symlink_to(source)
    return summary, messages


def _remove_owned_symlink(
    path: Path, expected_source: Path, dry_run: bool
) -> tuple[LinkSummary, list[str]]:
    summary = LinkSummary()
    messages: list[str] = []
    if not path.exists() and not path.is_symlink():
        return summary, messages
    if not path.is_symlink():
        summary.warned += 1
        messages.append(f"warn {path} exists and is not a symlink")
        return summary, messages
    current_target = path.resolve(strict=False)
    if current_target != expected_source.resolve(strict=False):
        summary.warned += 1
        messages.append(
            f"warn {path} points to {current_target} instead of {expected_source}"
        )
        return summary, messages
    if path.is_symlink():
        if not dry_run:
            path.unlink()
        summary.removed += 1
        messages.append(f"remove managed {path}")
    return summary, messages
