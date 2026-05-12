from __future__ import annotations

from pathlib import Path

import pytest

from shared_agents.discover import (
    DiscoveryError,
    discover_agents,
    materialize_example_configs,
    resolve_source_root,
)
from tests.conftest import write_agent


def test_discover_finds_agents(agents_home: Path) -> None:
    write_agent(agents_home, "one", "name: one\ndescription: First\n")
    write_agent(agents_home, "nested/two", "name: two\ndescription: Second\n")

    agents = discover_agents(agents_home)

    assert [agent.name for agent in agents] == ["one", "two"]


def test_discover_ignores_non_agent_dirs(agents_home: Path) -> None:
    noise_dir = agents_home / "agents" / "noise"
    noise_dir.mkdir(parents=True)
    (noise_dir / "README.md").write_text("not an agent\n", encoding="utf-8")

    assert discover_agents(agents_home) == []


def test_discover_duplicate_error(agents_home: Path) -> None:
    write_agent(agents_home, "one", "name: dupe\ndescription: First\n")
    write_agent(agents_home, "two", "name: dupe\ndescription: Second\n")

    with pytest.raises(DiscoveryError, match="Duplicate agent name"):
        discover_agents(agents_home)


def test_discover_uses_repo_root_when_agents_dir_exists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = tmp_path / "repo"
    write_agent(repo_root, "local-agent", "name: local-agent\ndescription: From cwd\n")
    monkeypatch.chdir(repo_root)

    assert resolve_source_root() == repo_root.resolve()
    assert [agent.name for agent in discover_agents()] == ["local-agent"]


def test_discover_uses_agents_home_env_when_cwd_has_no_agents(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    agents_home = tmp_path / "custom-home"
    workdir = tmp_path / "workdir"
    workdir.mkdir()
    write_agent(agents_home, "env-agent", "name: env-agent\ndescription: From env\n")
    monkeypatch.chdir(workdir)
    monkeypatch.setenv("AGENTS_HOME", str(agents_home))

    assert resolve_source_root() == agents_home.resolve()
    assert [agent.name for agent in discover_agents()] == ["env-agent"]


def test_discover_materializes_example_only_directory(
    agents_home: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    example_dir = agents_home / "agents" / "needs-init"
    example_dir.mkdir(parents=True)
    (example_dir / "agent.yaml.example").write_text(
        "name: needs-init\ndescription: Needs init\n", encoding="utf-8"
    )
    (example_dir / "instructions.md").write_text("Be useful.\n", encoding="utf-8")

    agents = discover_agents(agents_home)

    assert [agent.name for agent in agents] == ["needs-init"]
    assert (example_dir / "agent.yaml").read_text(encoding="utf-8") == (
        example_dir / "agent.yaml.example"
    ).read_text(encoding="utf-8")
    assert "created agent.yaml from agent.yaml.example" in capsys.readouterr().err
    # Idempotent: a second pass copies nothing and stays quiet.
    discover_agents(agents_home)
    assert "created agent.yaml" not in capsys.readouterr().err


def test_discover_can_read_example_without_materializing(
    agents_home: Path,
) -> None:
    example_dir = agents_home / "agents" / "needs-init"
    example_dir.mkdir(parents=True)
    (example_dir / "agent.yaml.example").write_text(
        "name: needs-init\ndescription: Needs init\n", encoding="utf-8"
    )
    (example_dir / "instructions.md").write_text("Be useful.\n", encoding="utf-8")

    agents = discover_agents(agents_home, materialize=False)

    assert [agent.name for agent in agents] == ["needs-init"]
    assert not (example_dir / "agent.yaml").exists()


def test_discover_ignores_stale_materialized_agent_after_rename(
    agents_home: Path,
) -> None:
    new_dir = write_agent(
        agents_home,
        "retrorabbit-code-reviewer",
        "name: retrorabbit-code-reviewer\ndescription: Current agent\n",
    )
    old_dir = agents_home / "agents" / "retrorabbit_code_reviewer"
    old_dir.mkdir(parents=True)
    (old_dir / "agent.yaml").write_text(
        "name: retrorabbit_code_reviewer\ndescription: Old materialized config\n",
        encoding="utf-8",
    )

    agents = discover_agents(agents_home)

    assert [agent.name for agent in agents] == ["retrorabbit-code-reviewer"]
    assert agents[0].source_dir == new_dir


def test_materialize_example_configs_reports_copy_failures(
    agents_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    example_dir = agents_home / "agents" / "needs-init"
    example_dir.mkdir(parents=True)
    (example_dir / "agent.yaml.example").write_text(
        "name: needs-init\ndescription: Needs init\n", encoding="utf-8"
    )

    def boom(*_args: object, **_kwargs: object) -> None:
        raise PermissionError("read-only checkout")

    monkeypatch.setattr("shared_agents.discover.shutil.copy2", boom)

    with pytest.raises(DiscoveryError, match="shared-agents init"):
        materialize_example_configs(agents_home)


def test_repo_contains_expected_agents(initialized_repo: Path) -> None:
    agents = {agent.name: agent for agent in discover_agents(initialized_repo)}

    assert {
        "plan-reviewer",
        "retrorabbit-code-reviewer",
        "codexrabbit-code-reviewer",
    } <= set(agents)
    assert agents["plan-reviewer"].source_dir == initialized_repo / "agents" / "plan-reviewer"
    assert (
        agents["retrorabbit-code-reviewer"].source_dir
        == initialized_repo / "agents" / "retrorabbit-code-reviewer"
    )
    assert (
        agents["codexrabbit-code-reviewer"].source_dir
        == initialized_repo / "agents" / "codexrabbit-code-reviewer"
    )
