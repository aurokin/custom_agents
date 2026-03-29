from __future__ import annotations

from pathlib import Path

from shared_agents.linker import prune_stale_links, sync_links


def test_linker_creates_symlinks(agents_home: Path, fake_home: Path) -> None:
    (agents_home / "AGENTS.md").write_text("Shared instructions\n", encoding="utf-8")
    skill_dir = agents_home / "skills" / "demo"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nname: demo\ndescription: demo\n---\n", encoding="utf-8")

    summary, _ = sync_links(agents_home)

    assert summary.created == 4
    assert (fake_home / ".claude" / "CLAUDE.md").is_symlink()
    assert (fake_home / ".codex" / "AGENTS.md").is_symlink()
    assert (fake_home / ".claude" / "skills" / "demo").is_symlink()
    assert (fake_home / ".codex" / "skills" / "demo").is_symlink()


def test_linker_idempotent(agents_home: Path, fake_home: Path) -> None:
    (agents_home / "AGENTS.md").write_text("Shared instructions\n", encoding="utf-8")
    skill_dir = agents_home / "skills" / "demo"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nname: demo\ndescription: demo\n---\n", encoding="utf-8")

    sync_links(agents_home)
    summary, _ = sync_links(agents_home)

    assert summary.created == 0
    assert summary.updated == 0
    assert summary.skipped >= 4


def test_linker_warns_on_regular_file(agents_home: Path, fake_home: Path) -> None:
    (agents_home / "AGENTS.md").write_text("Shared instructions\n", encoding="utf-8")
    target = fake_home / ".codex"
    target.mkdir(parents=True)
    (target / "AGENTS.md").write_text("manual file\n", encoding="utf-8")

    summary, messages = sync_links(agents_home)

    assert summary.warned == 1
    assert any("warn" in message for message in messages)


def test_linker_cleans_stale(agents_home: Path, fake_home: Path) -> None:
    target_dir = fake_home / ".codex" / "skills"
    target_dir.mkdir(parents=True)
    broken = target_dir / "ghost"
    broken.symlink_to(agents_home / "skills" / "ghost")

    summary, _ = prune_stale_links(agents_home)

    assert summary.removed == 1
    assert not broken.exists()
