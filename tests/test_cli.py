from __future__ import annotations

from pathlib import Path

from shared_agents.main import main
from shared_agents.manifest import load_manifest
from tests.conftest import install_fixture


def test_sync_dry_run(agents_home: Path, fake_home: Path) -> None:
    install_fixture(agents_home, "minimal-agent")
    before = sorted(path.relative_to(fake_home) for path in fake_home.rglob("*"))

    assert main(["sync", "--dry-run", "--agents-home", str(agents_home)]) == 0

    after = sorted(path.relative_to(fake_home) for path in fake_home.rglob("*"))
    assert before == after


def test_sync_end_to_end(agents_home: Path, fake_home: Path) -> None:
    install_fixture(agents_home, "minimal-agent")
    (agents_home / "AGENTS.md").write_text("Shared instructions\n", encoding="utf-8")
    skill_dir = agents_home / "skills" / "demo"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nname: demo\ndescription: demo\n---\n", encoding="utf-8")

    assert main(["sync", "--agents-home", str(agents_home)]) == 0

    assert (fake_home / ".claude" / "agents" / "code-reviewer.md").exists()
    assert (fake_home / ".codex" / "agents" / "code-reviewer.toml").exists()
    assert (fake_home / ".claude" / "CLAUDE.md").is_symlink()
    assert (fake_home / ".codex" / "AGENTS.md").is_symlink()
    assert load_manifest(agents_home).generated_files["claude"]


def test_clean_removes_manifest_owned_files(agents_home: Path, fake_home: Path) -> None:
    install_fixture(agents_home, "minimal-agent")
    assert main(["sync", "--agents-home", str(agents_home)]) == 0

    assert main(["clean", "--agents-home", str(agents_home)]) == 0

    assert not (fake_home / ".claude" / "agents" / "code-reviewer.md").exists()
    assert not (fake_home / ".codex" / "agents" / "code-reviewer.toml").exists()
