from __future__ import annotations

from pathlib import Path

from shared_agents.linker import prune_stale_links, sync_links


def test_linker_creates_symlinks(agents_home: Path, fake_home: Path) -> None:
    (agents_home / "AGENTS.md").write_text("Shared instructions\n", encoding="utf-8")
    skill_dir = agents_home / "skills" / "demo"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nname: demo\ndescription: demo\n---\n", encoding="utf-8")

    summary, _, linked_targets = sync_links(agents_home)

    assert summary.created == 4
    assert len(linked_targets) == 4
    assert (fake_home / ".claude" / "CLAUDE.md").is_symlink()
    assert (fake_home / ".codex" / "AGENTS.md").is_symlink()
    assert (fake_home / ".claude" / "skills" / "demo").is_symlink()
    assert (fake_home / ".codex" / "skills" / "demo").is_symlink()


def test_linker_idempotent(agents_home: Path, fake_home: Path) -> None:
    (agents_home / "AGENTS.md").write_text("Shared instructions\n", encoding="utf-8")
    skill_dir = agents_home / "skills" / "demo"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nname: demo\ndescription: demo\n---\n", encoding="utf-8")

    _, _, linked_targets = sync_links(agents_home)
    summary, _, _ = sync_links(agents_home, managed_links=linked_targets)

    assert summary.created == 0
    assert summary.updated == 0
    assert summary.skipped >= 4


def test_linker_warns_on_regular_file(agents_home: Path, fake_home: Path) -> None:
    (agents_home / "AGENTS.md").write_text("Shared instructions\n", encoding="utf-8")
    target = fake_home / ".codex"
    target.mkdir(parents=True)
    (target / "AGENTS.md").write_text("manual file\n", encoding="utf-8")

    summary, messages, _ = sync_links(agents_home)

    assert summary.warned == 1
    assert any("warn" in message for message in messages)


def test_linker_prunes_manifest_owned_symlink(agents_home: Path, fake_home: Path) -> None:
    target_dir = fake_home / ".codex" / "skills"
    target_dir.mkdir(parents=True)
    broken = target_dir / "ghost"
    broken.symlink_to(agents_home / "skills" / "ghost")

    summary, _ = prune_stale_links(
        {str(broken): str(agents_home / "skills" / "ghost")}
    )

    assert summary.removed == 1
    assert not broken.exists()


def test_linker_does_not_remove_unmanaged_broken_symlink(agents_home: Path, fake_home: Path) -> None:
    target_dir = fake_home / ".codex" / "skills"
    target_dir.mkdir(parents=True)
    broken = target_dir / "ghost"
    broken.symlink_to(agents_home / "skills" / "ghost")

    summary, _ = prune_stale_links({})

    assert summary.removed == 0
    assert broken.is_symlink()


def test_linker_removes_links_no_longer_desired_on_sync(agents_home: Path, fake_home: Path) -> None:
    (agents_home / "AGENTS.md").write_text("Shared instructions\n", encoding="utf-8")
    skill_dir = agents_home / "skills" / "demo"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nname: demo\ndescription: demo\n---\n", encoding="utf-8")

    _, _, linked_targets = sync_links(agents_home)

    (agents_home / "AGENTS.md").unlink()
    for path in sorted(skill_dir.rglob("*"), reverse=True):
        if path.is_file():
            path.unlink()
    skill_dir.rmdir()
    (agents_home / "skills").rmdir()

    summary, _, next_links = sync_links(agents_home, managed_links=linked_targets)

    assert summary.removed == 4
    assert next_links == {}
    assert not (fake_home / ".claude" / "CLAUDE.md").exists()
    assert not (fake_home / ".codex" / "AGENTS.md").exists()
    assert not (fake_home / ".claude" / "skills" / "demo").exists()
    assert not (fake_home / ".codex" / "skills" / "demo").exists()
