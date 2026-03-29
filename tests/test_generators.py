from __future__ import annotations

from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib

import yaml

from shared_agents.generators.claude import build_claude_frontmatter, render_claude_agent
from shared_agents.generators.codex import build_codex_document, render_codex_agent
from shared_agents.schema import load_agent_definition
from tests.conftest import install_fixture, write_agent


def _parse_frontmatter(document: str) -> dict:
    _, yaml_block, _ = document.split("---", 2)
    return yaml.safe_load(yaml_block)


def test_claude_generator_minimal(agents_home: Path) -> None:
    agent = load_agent_definition(install_fixture(agents_home, "minimal-agent"))

    rendered = render_claude_agent(agent)
    frontmatter = _parse_frontmatter(rendered)

    assert frontmatter == {
        "name": "code-reviewer",
        "description": "Reviews code for correctness and risk.",
    }
    assert "focused code reviewer" in rendered


def test_claude_generator_full(agents_home: Path) -> None:
    agent = load_agent_definition(install_fixture(agents_home, "full-agent"))

    rendered = render_claude_agent(agent)
    frontmatter = _parse_frontmatter(rendered)

    assert frontmatter["tools"] == ["Read", "Grep", "Glob"]
    assert frontmatter["disallowedTools"] == ["Write"]
    assert frontmatter["skills"] == ["web-design-guidelines", "plan-reviewer"]
    assert frontmatter["background"] is True
    assert frontmatter["mcpServers"] == ["github"]


def test_claude_generator_roundtrip(agents_home: Path) -> None:
    agent = load_agent_definition(install_fixture(agents_home, "full-agent"))

    assert build_claude_frontmatter(agent) == _parse_frontmatter(render_claude_agent(agent))


def test_codex_generator_minimal(agents_home: Path) -> None:
    agent = load_agent_definition(install_fixture(agents_home, "minimal-agent"))

    rendered = render_codex_agent(agent)
    parsed = tomllib.loads(rendered)

    assert parsed["name"] == "code-reviewer"
    assert parsed["description"] == "Reviews code for correctness and risk."
    assert parsed["sandbox_mode"] == "read-only"
    assert "developer_instructions" in parsed


def test_codex_generator_full(agents_home: Path) -> None:
    agent = load_agent_definition(install_fixture(agents_home, "full-agent"))

    rendered = render_codex_agent(agent)
    parsed = tomllib.loads(rendered)

    assert parsed["model"] == "gpt-5.4"
    assert parsed["model_reasoning_effort"] == "high"
    assert parsed["sandbox_mode"] == "workspace-write"
    assert parsed["nickname_candidates"] == ["Atlas", "Echo"]
    assert parsed["skills"]["config"] == [
        {"name": "web-design-guidelines", "enabled": False},
        {"name": "plan-reviewer", "enabled": True},
    ]


def test_codex_generator_roundtrip(agents_home: Path) -> None:
    agent = load_agent_definition(install_fixture(agents_home, "full-agent"))

    assert build_codex_document(agent) == tomllib.loads(render_codex_agent(agent))


def test_codex_sandbox_mapping(agents_home: Path) -> None:
    source_dir = write_agent(
        agents_home,
        "full-access-agent",
        "\n".join(
            [
                "name: escalated-reviewer",
                "description: Needs full access",
                "defaults:",
                "  sandbox: full-access",
            ]
        ),
    )

    parsed = tomllib.loads(render_codex_agent(load_agent_definition(source_dir)))
    assert parsed["sandbox_mode"] == "danger-full-access"
