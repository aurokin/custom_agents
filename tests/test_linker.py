from __future__ import annotations

from pathlib import Path

from shared_agents.linker import prune_stale_links, sync_links
from tests.conftest import write_agent


def test_linker_creates_symlinks(agents_home: Path, fake_home: Path) -> None:
    write_agent(agents_home, "demo", "name: demo\ndescription: Demo\n")

    summary, _, linked_targets = sync_links(agents_home)

    assert summary.created == 1
    assert len(linked_targets) == 1
    assert (fake_home / ".agents" / "agents").is_symlink()


def test_linker_idempotent(agents_home: Path, fake_home: Path) -> None:
    write_agent(agents_home, "demo", "name: demo\ndescription: Demo\n")

    _, _, linked_targets = sync_links(agents_home)
    summary, _, _ = sync_links(agents_home, managed_links=linked_targets)

    assert summary.created == 0
    assert summary.updated == 0
    assert summary.skipped == 1


def test_linker_warns_on_regular_file(agents_home: Path, fake_home: Path) -> None:
    write_agent(agents_home, "demo", "name: demo\ndescription: Demo\n")
    target = fake_home / ".agents"
    target.mkdir(parents=True)
    (target / "agents").write_text("manual file\n", encoding="utf-8")

    summary, messages, _ = sync_links(agents_home)

    assert summary.warned == 1
    assert any("warn" in message for message in messages)


def test_linker_prunes_manifest_owned_symlink(agents_home: Path, fake_home: Path) -> None:
    target_dir = fake_home / ".agents"
    target_dir.mkdir(parents=True)
    broken = target_dir / "agents"
    broken.symlink_to(agents_home / "agents")

    summary, _ = prune_stale_links(
        {str(broken): str(agents_home / "agents")}
    )

    assert summary.removed == 1
    assert not broken.exists()


def test_linker_does_not_remove_unmanaged_broken_symlink(agents_home: Path, fake_home: Path) -> None:
    target_dir = fake_home / ".agents"
    target_dir.mkdir(parents=True)
    broken = target_dir / "agents"
    broken.symlink_to(agents_home / "agents")

    summary, _ = prune_stale_links({})

    assert summary.removed == 0
    assert broken.is_symlink()


def test_linker_removes_links_no_longer_desired_on_sync(agents_home: Path, fake_home: Path) -> None:
    source_dir = write_agent(agents_home, "demo", "name: demo\ndescription: Demo\n")

    _, _, linked_targets = sync_links(agents_home)

    for path in sorted(source_dir.rglob("*"), reverse=True):
        if path.is_file():
            path.unlink()
    source_dir.rmdir()
    (agents_home / "agents").rmdir()

    summary, _, next_links = sync_links(agents_home, managed_links=linked_targets)

    assert summary.removed == 1
    assert next_links == {}
    assert not (fake_home / ".agents" / "agents").exists()


def test_linker_skips_canonical_agents_home(agents_home: Path, fake_home: Path) -> None:
    canonical_home = fake_home / ".agents"
    write_agent(canonical_home, "demo", "name: demo\ndescription: Demo\n")

    summary, _, linked_targets = sync_links(canonical_home)

    assert summary.created == 0
    assert summary.skipped == 0
    assert linked_targets == {}
