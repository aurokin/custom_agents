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


def sync_links(agents_home: Path, dry_run: bool = False) -> tuple[LinkSummary, list[str]]:
    summary = LinkSummary()
    messages: list[str] = []
    home = Path.home()

    claude_dir = home / ".claude"
    codex_dir = home / ".codex"
    skill_targets = [claude_dir / "skills", codex_dir / "skills"]
    for directory in [claude_dir, codex_dir, *skill_targets]:
        if not dry_run:
            directory.mkdir(parents=True, exist_ok=True)

    source_agents_md = agents_home / "AGENTS.md"
    if source_agents_md.exists():
        for target in [claude_dir / "CLAUDE.md", codex_dir / "AGENTS.md"]:
            outcome = _ensure_symlink(source_agents_md, target, dry_run)
            summary.merge(outcome[0])
            messages.extend(outcome[1])

    skills_dir = agents_home / "skills"
    if skills_dir.exists():
        for source_skill in sorted(
            path for path in skills_dir.iterdir() if path.is_dir()
        ):
            for target_dir in skill_targets:
                outcome = _ensure_symlink(
                    source_skill, target_dir / source_skill.name, dry_run
                )
                summary.merge(outcome[0])
                messages.extend(outcome[1])

    stale_summary, stale_messages = prune_stale_links(agents_home, dry_run=dry_run)
    summary.merge(stale_summary)
    messages.extend(stale_messages)

    return summary, messages


def prune_stale_links(agents_home: Path, dry_run: bool = False) -> tuple[LinkSummary, list[str]]:
    summary = LinkSummary()
    messages: list[str] = []
    home = Path.home()
    claude_dir = home / ".claude"
    codex_dir = home / ".codex"
    skill_targets = [claude_dir / "skills", codex_dir / "skills"]

    for target in [claude_dir / "CLAUDE.md", codex_dir / "AGENTS.md"]:
        result = _remove_stale_symlink(target, dry_run)
        summary.merge(result[0])
        messages.extend(result[1])
    for target_dir in skill_targets:
        result = _remove_stale_symlinks_in_dir(target_dir, dry_run)
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


def _remove_stale_symlink(path: Path, dry_run: bool) -> tuple[LinkSummary, list[str]]:
    summary = LinkSummary()
    messages: list[str] = []
    if path.is_symlink() and not path.exists():
        if not dry_run:
            path.unlink()
        summary.removed += 1
        messages.append(f"remove stale {path}")
    return summary, messages


def _remove_stale_symlinks_in_dir(
    directory: Path, dry_run: bool
) -> tuple[LinkSummary, list[str]]:
    summary = LinkSummary()
    messages: list[str] = []
    if not directory.exists():
        return summary, messages
    for path in sorted(directory.iterdir()):
        if path.is_symlink() and not path.exists():
            if not dry_run:
                path.unlink()
            summary.removed += 1
            messages.append(f"remove stale {path}")
    return summary, messages
