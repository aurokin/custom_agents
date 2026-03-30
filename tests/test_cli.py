from __future__ import annotations

from pathlib import Path

from shared_agents.main import main
from shared_agents.manifest import load_manifest
from tests.conftest import install_fixture, write_agent


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
    manifest = load_manifest(agents_home)
    assert manifest.generated_files["claude"]
    assert str(fake_home / ".claude" / "CLAUDE.md") in manifest.linked_targets
    assert str(fake_home / ".codex" / "AGENTS.md") in manifest.linked_targets
    assert not (agents_home / ".shared-agents-manifest.json").exists()


def test_clean_removes_manifest_owned_files(agents_home: Path, fake_home: Path) -> None:
    install_fixture(agents_home, "minimal-agent")
    (agents_home / "AGENTS.md").write_text("Shared instructions\n", encoding="utf-8")
    skill_dir = agents_home / "skills" / "demo"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nname: demo\ndescription: demo\n---\n", encoding="utf-8")
    assert main(["sync", "--agents-home", str(agents_home)]) == 0

    assert main(["clean", "--agents-home", str(agents_home)]) == 0

    assert not (fake_home / ".claude" / "agents" / "code-reviewer.md").exists()
    assert not (fake_home / ".codex" / "agents" / "code-reviewer.toml").exists()
    assert not (fake_home / ".claude" / "CLAUDE.md").exists()
    assert not (fake_home / ".codex" / "AGENTS.md").exists()
    assert not (fake_home / ".claude" / "skills" / "demo").exists()
    assert not (fake_home / ".codex" / "skills" / "demo").exists()
    assert load_manifest(agents_home) == load_manifest(agents_home).empty()


def test_sync_switches_agents_home_and_removes_previous_outputs(
    tmp_path: Path, fake_home: Path
) -> None:
    first_home = tmp_path / "first-agents-home"
    second_home = tmp_path / "second-agents-home"
    first_home.mkdir()
    second_home.mkdir()

    write_agent(first_home, "alpha", "name: alpha\ndescription: Alpha agent\n")
    (first_home / "AGENTS.md").write_text("First shared instructions\n", encoding="utf-8")
    first_skill = first_home / "skills" / "alpha-skill"
    first_skill.mkdir(parents=True)
    (first_skill / "SKILL.md").write_text(
        "---\nname: alpha\ndescription: alpha\n---\n", encoding="utf-8"
    )

    write_agent(second_home, "beta", "name: beta\ndescription: Beta agent\n")
    (second_home / "AGENTS.md").write_text("Second shared instructions\n", encoding="utf-8")
    second_skill = second_home / "skills" / "beta-skill"
    second_skill.mkdir(parents=True)
    (second_skill / "SKILL.md").write_text(
        "---\nname: beta\ndescription: beta\n---\n", encoding="utf-8"
    )

    assert main(["sync", "--agents-home", str(first_home)]) == 0
    assert (fake_home / ".claude" / "agents" / "alpha.md").exists()
    assert (fake_home / ".codex" / "agents" / "alpha.toml").exists()
    assert (fake_home / ".claude" / "skills" / "alpha-skill").is_symlink()
    assert (fake_home / ".codex" / "skills" / "alpha-skill").is_symlink()

    assert main(["sync", "--agents-home", str(second_home)]) == 0

    assert not (fake_home / ".claude" / "agents" / "alpha.md").exists()
    assert not (fake_home / ".codex" / "agents" / "alpha.toml").exists()
    assert not (fake_home / ".claude" / "skills" / "alpha-skill").exists()
    assert not (fake_home / ".codex" / "skills" / "alpha-skill").exists()
    assert (fake_home / ".claude" / "agents" / "beta.md").exists()
    assert (fake_home / ".codex" / "agents" / "beta.toml").exists()
    assert (fake_home / ".claude" / "skills" / "beta-skill").is_symlink()
    assert (fake_home / ".codex" / "skills" / "beta-skill").is_symlink()
