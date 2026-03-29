from __future__ import annotations

from pathlib import Path

import pytest

from shared_agents.discover import DiscoveryError, discover_agents, resolve_agents_home
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


def test_discover_uses_agents_home_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    agents_home = tmp_path / "custom-home"
    write_agent(agents_home, "env-agent", "name: env-agent\ndescription: From env\n")
    monkeypatch.setenv("AGENTS_HOME", str(agents_home))

    assert resolve_agents_home() == agents_home.resolve()
    assert [agent.name for agent in discover_agents()] == ["env-agent"]
