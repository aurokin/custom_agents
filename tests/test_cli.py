from __future__ import annotations

from pathlib import Path

from shared_agents.main import main
from shared_agents.manifest import load_manifest
from tests.conftest import install_fixture, write_agent


def test_sync_dry_run(agents_home: Path, fake_home: Path) -> None:
    install_fixture(agents_home, "minimal-agent")
    before = sorted(path.relative_to(fake_home) for path in fake_home.rglob("*"))

    assert main(["sync", "--dry-run", "--source-root", str(agents_home)]) == 0

    after = sorted(path.relative_to(fake_home) for path in fake_home.rglob("*"))
    assert before == after


def test_sync_end_to_end(agents_home: Path, fake_home: Path) -> None:
    install_fixture(agents_home, "minimal-agent")

    assert main(["sync", "--source-root", str(agents_home)]) == 0

    assert (fake_home / ".claude" / "agents" / "code-reviewer.md").exists()
    assert (fake_home / ".copilot" / "agents" / "code-reviewer.agent.md").exists()
    assert (fake_home / ".codex" / "agents" / "code-reviewer.toml").exists()
    assert not (fake_home / ".agents" / "agents").exists()
    manifest = load_manifest(agents_home)
    assert manifest.generated_files["claude"]
    assert manifest.linked_targets == {}
    assert not (agents_home / ".shared-agents-manifest.json").exists()


def test_clean_removes_manifest_owned_files(agents_home: Path, fake_home: Path) -> None:
    install_fixture(agents_home, "minimal-agent")
    assert main(["sync", "--source-root", str(agents_home)]) == 0

    assert main(["clean", "--source-root", str(agents_home)]) == 0

    assert not (fake_home / ".claude" / "agents" / "code-reviewer.md").exists()
    assert not (fake_home / ".copilot" / "agents" / "code-reviewer.agent.md").exists()
    assert not (fake_home / ".codex" / "agents" / "code-reviewer.toml").exists()
    assert load_manifest(agents_home) == load_manifest(agents_home).empty()


def test_sync_switches_source_root_and_removes_previous_outputs(
    tmp_path: Path, fake_home: Path
) -> None:
    first_home = tmp_path / "first-agents-home"
    second_home = tmp_path / "second-agents-home"
    first_home.mkdir()
    second_home.mkdir()

    write_agent(first_home, "alpha", "name: alpha\ndescription: Alpha agent\n")
    write_agent(second_home, "beta", "name: beta\ndescription: Beta agent\n")

    assert main(["sync", "--source-root", str(first_home)]) == 0
    assert (fake_home / ".claude" / "agents" / "alpha.md").exists()
    assert (fake_home / ".copilot" / "agents" / "alpha.agent.md").exists()
    assert (fake_home / ".codex" / "agents" / "alpha.toml").exists()

    assert main(["sync", "--source-root", str(second_home)]) == 0

    assert not (fake_home / ".claude" / "agents" / "alpha.md").exists()
    assert not (fake_home / ".copilot" / "agents" / "alpha.agent.md").exists()
    assert not (fake_home / ".codex" / "agents" / "alpha.toml").exists()
    assert (fake_home / ".claude" / "agents" / "beta.md").exists()
    assert (fake_home / ".copilot" / "agents" / "beta.agent.md").exists()
    assert (fake_home / ".codex" / "agents" / "beta.toml").exists()


def test_sync_can_optionally_link_canonical_agents_dir(
    agents_home: Path, fake_home: Path
) -> None:
    install_fixture(agents_home, "minimal-agent")

    assert (
        main(
            [
                "sync",
                "--source-root",
                str(agents_home),
                "--link-canonical",
            ]
        )
        == 0
    )

    assert (fake_home / ".agents" / "agents").is_symlink()
    assert (fake_home / ".agents" / "agents").resolve() == (agents_home / "agents").resolve()
    manifest = load_manifest(agents_home)
    assert str(fake_home / ".agents" / "agents") in manifest.linked_targets


def test_sync_uses_copilot_home_override(
    agents_home: Path, fake_home: Path, monkeypatch
) -> None:
    install_fixture(agents_home, "minimal-agent")
    copilot_home = fake_home / ".config" / "copilot-work"
    monkeypatch.setenv("COPILOT_HOME", str(copilot_home))

    assert main(["sync", "--source-root", str(agents_home)]) == 0

    assert (copilot_home / "agents" / "code-reviewer.agent.md").exists()
    assert not (fake_home / ".copilot" / "agents" / "code-reviewer.agent.md").exists()
    manifest = load_manifest(agents_home)
    assert str(copilot_home / "agents" / "code-reviewer.agent.md") in manifest.generated_files["copilot"]

    assert main(["clean", "--source-root", str(agents_home)]) == 0
    assert not (copilot_home / "agents" / "code-reviewer.agent.md").exists()
