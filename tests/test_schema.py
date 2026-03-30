from __future__ import annotations

from pathlib import Path

import pytest

from shared_agents.schema import SchemaError, load_agent_definition
from tests.conftest import install_fixture, write_agent


def test_schema_minimal(agents_home: Path) -> None:
    source_dir = install_fixture(agents_home, "minimal-agent", "reviewer")

    agent = load_agent_definition(source_dir)

    assert agent.name == "code-reviewer"
    assert agent.description == "Reviews code for correctness and risk."
    assert agent.sandbox == "read-only"
    assert agent.skills == []
    assert agent.claude.model is None
    assert agent.codex.sandbox_mode is None


def test_schema_full(agents_home: Path) -> None:
    source_dir = install_fixture(agents_home, "full-agent")

    agent = load_agent_definition(source_dir)

    assert agent.sandbox == "workspace-write"
    assert agent.skills == ["web-design-guidelines", "plan-reviewer"]
    assert agent.claude.model == "sonnet"
    assert agent.claude.extra == {"background": True}
    assert agent.codex.model == "gpt-5.4"
    assert agent.codex.model_reasoning_effort == "high"
    assert agent.codex.nickname_candidates == ["Atlas", "Echo"]
    assert agent.codex.skills_config == [
        {"name": "web-design-guidelines", "enabled": False}
    ]


def test_schema_missing_name(agents_home: Path) -> None:
    source_dir = write_agent(
        agents_home,
        "broken",
        "description: Missing the required name\n",
    )

    with pytest.raises(SchemaError, match="Missing required field 'name'"):
        load_agent_definition(source_dir)


def test_schema_missing_instructions(agents_home: Path) -> None:
    source_dir = agents_home / "agents" / "broken"
    source_dir.mkdir(parents=True)
    (source_dir / "agent.yaml").write_text(
        "name: missing-instructions\ndescription: Missing instructions\n",
        encoding="utf-8",
    )

    with pytest.raises(SchemaError, match="Missing instructions.md"):
        load_agent_definition(source_dir)


def test_schema_unknown_claude_keys_preserved(agents_home: Path) -> None:
    source_dir = write_agent(
        agents_home,
        "extra",
        "\n".join(
            [
                "name: reviewer",
                "description: Keeps extra Claude frontmatter",
                "claude:",
                "  memory: user",
                "  background: true",
            ]
        ),
    )

    agent = load_agent_definition(source_dir)

    assert agent.claude.extra == {"memory": "user", "background": True}


def test_schema_unknown_codex_keys_fail(agents_home: Path) -> None:
    source_dir = write_agent(
        agents_home,
        "bad-codex",
        "\n".join(
            [
                "name: reviewer",
                "description: Invalid codex passthrough",
                "codex:",
                "  unsupported: true",
            ]
        ),
    )

    with pytest.raises(SchemaError, match="Unknown codex keys"):
        load_agent_definition(source_dir)


def test_schema_allows_underscore_agent_name(agents_home: Path) -> None:
    source_dir = write_agent(
        agents_home,
        "underscore-agent",
        "\n".join(
            [
                "name: retrorabbit_code_reviewer",
                "description: Reviews hunks for correctness",
                "codex:",
                "  nickname_candidates:",
                "    - RetroRabbit",
            ]
        ),
    )

    agent = load_agent_definition(source_dir)

    assert agent.name == "retrorabbit_code_reviewer"


def test_repo_retrorabbit_code_reviewer_definition() -> None:
    source_dir = Path(__file__).resolve().parents[1] / "agents" / "retrorabbit_code_reviewer"

    agent = load_agent_definition(source_dir)

    assert agent.name == "retrorabbit_code_reviewer"
    assert agent.description == "Reviews code hunks for correctness, risk, and maintainability."
    assert agent.sandbox == "read-only"
    assert agent.claude.tools == ["Read", "Grep", "Glob"]
    assert agent.claude.disallowed_tools == ["Write"]
    assert agent.codex.model == "gpt-5.4"
    assert agent.codex.nickname_candidates == ["RetroRabbit", "Rabbit Reviewer"]
