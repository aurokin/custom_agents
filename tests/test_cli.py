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

    assert main(["sync", "--agents-home", str(agents_home)]) == 0

    assert (fake_home / ".claude" / "agents" / "code-reviewer.md").exists()
    assert (fake_home / ".codex" / "agents" / "code-reviewer.toml").exists()
    assert (fake_home / ".agents" / "agents").is_symlink()
    manifest = load_manifest(agents_home)
    assert manifest.generated_files["claude"]
    assert str(fake_home / ".agents" / "agents") in manifest.linked_targets
    assert not (agents_home / ".shared-agents-manifest.json").exists()


def test_clean_removes_manifest_owned_files(agents_home: Path, fake_home: Path) -> None:
    install_fixture(agents_home, "minimal-agent")
    assert main(["sync", "--agents-home", str(agents_home)]) == 0

    assert main(["clean", "--agents-home", str(agents_home)]) == 0

    assert not (fake_home / ".claude" / "agents" / "code-reviewer.md").exists()
    assert not (fake_home / ".codex" / "agents" / "code-reviewer.toml").exists()
    assert not (fake_home / ".agents" / "agents").exists()
    assert load_manifest(agents_home) == load_manifest(agents_home).empty()


def test_sync_switches_agents_home_and_removes_previous_outputs(
    tmp_path: Path, fake_home: Path
) -> None:
    first_home = tmp_path / "first-agents-home"
    second_home = tmp_path / "second-agents-home"
    first_home.mkdir()
    second_home.mkdir()

    write_agent(first_home, "alpha", "name: alpha\ndescription: Alpha agent\n")
    write_agent(second_home, "beta", "name: beta\ndescription: Beta agent\n")

    assert main(["sync", "--agents-home", str(first_home)]) == 0
    assert (fake_home / ".claude" / "agents" / "alpha.md").exists()
    assert (fake_home / ".codex" / "agents" / "alpha.toml").exists()
    assert (fake_home / ".agents" / "agents").is_symlink()
    assert (fake_home / ".agents" / "agents").resolve() == (first_home / "agents").resolve()

    assert main(["sync", "--agents-home", str(second_home)]) == 0

    assert not (fake_home / ".claude" / "agents" / "alpha.md").exists()
    assert not (fake_home / ".codex" / "agents" / "alpha.toml").exists()
    assert (fake_home / ".claude" / "agents" / "beta.md").exists()
    assert (fake_home / ".codex" / "agents" / "beta.toml").exists()
    assert (fake_home / ".agents" / "agents").is_symlink()
    assert (fake_home / ".agents" / "agents").resolve() == (second_home / "agents").resolve()
