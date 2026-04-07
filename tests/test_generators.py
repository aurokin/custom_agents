from __future__ import annotations

from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib

import yaml

from shared_agents.generators.claude import build_claude_frontmatter, render_claude_agent
from shared_agents.generators.copilot import build_copilot_frontmatter, render_copilot_agent
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
        "model": "opus-4.6",
        "effort": "high",
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
    assert build_claude_frontmatter(agent, emit_defaults=False) == _parse_frontmatter(
        render_claude_agent(agent, emit_defaults=False)
    )


def test_codex_generator_minimal(agents_home: Path) -> None:
    agent = load_agent_definition(install_fixture(agents_home, "minimal-agent"))

    rendered = render_codex_agent(agent)
    parsed = tomllib.loads(rendered)

    assert parsed["name"] == "code-reviewer"
    assert parsed["description"] == "Reviews code for correctness and risk."
    assert parsed["model"] == "gpt-5.4"
    assert parsed["model_reasoning_effort"] == "high"
    assert parsed["sandbox_mode"] == "read-only"
    assert "developer_instructions" in parsed


def test_copilot_generator_minimal(agents_home: Path) -> None:
    agent = load_agent_definition(install_fixture(agents_home, "minimal-agent"))

    rendered = render_copilot_agent(agent)
    frontmatter = _parse_frontmatter(rendered)

    assert frontmatter == {
        "name": "code-reviewer",
        "description": "Reviews code for correctness and risk.",
        "model": "gpt-5.4-high",
    }
    assert "focused code reviewer" in rendered


def test_copilot_generator_minimal_without_defaults(agents_home: Path) -> None:
    agent = load_agent_definition(install_fixture(agents_home, "minimal-agent"))

    frontmatter = _parse_frontmatter(render_copilot_agent(agent, emit_defaults=False))

    assert frontmatter == {
        "name": "code-reviewer",
        "description": "Reviews code for correctness and risk.",
    }


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


def test_copilot_generator_full(agents_home: Path) -> None:
    agent = load_agent_definition(install_fixture(agents_home, "full-agent"))

    rendered = render_copilot_agent(agent)
    frontmatter = _parse_frontmatter(rendered)

    assert frontmatter["target"] == "github-copilot"
    assert frontmatter["tools"] == ["read", "search", "edit", "github/*"]
    assert frontmatter["model"] == "gpt-5.4-high"
    assert frontmatter["disable-model-invocation"] is True
    assert frontmatter["user-invocable"] is True
    assert frontmatter["metadata"] == {
        "owner": "frontend-platform",
        "tier": "primary",
    }


def test_copilot_generator_preserves_empty_tools_list(agents_home: Path) -> None:
    source_dir = write_agent(
        agents_home,
        "copilot-no-tools",
        "\n".join(
            [
                "name: locked-down-reviewer",
                "description: Copilot agent with no tools",
                "copilot:",
                "  tools: []",
            ]
        ),
    )

    frontmatter = _parse_frontmatter(
        render_copilot_agent(load_agent_definition(source_dir))
    )

    assert frontmatter["tools"] == []


def test_codex_generator_roundtrip(agents_home: Path) -> None:
    agent = load_agent_definition(install_fixture(agents_home, "full-agent"))

    assert build_codex_document(agent) == tomllib.loads(render_codex_agent(agent))


def test_copilot_generator_roundtrip(agents_home: Path) -> None:
    agent = load_agent_definition(install_fixture(agents_home, "full-agent"))

    assert build_copilot_frontmatter(agent) == _parse_frontmatter(
        render_copilot_agent(agent)
    )


def test_vscode_copilot_generator_supports_vscode_fields(agents_home: Path) -> None:
    source_dir = write_agent(
        agents_home,
        "vscode-copilot",
        "\n".join(
            [
                "name: vscode-reviewer",
                "description: VS Code Copilot agent",
                "copilot:",
                "  target: vscode",
                "  agents: '*'",
                "  model:",
                "    - gpt-5.4-high",
                "    - gpt-5.4",
                "  mcp_servers:",
                "    - id: github",
                "      command:",
                "        name: npx",
                "        args:",
                "          - -y",
                "          - github-mcp",
                "  argument_hint: repo:path",
                "  disable_model_invocation: true",
                "  user_invocable: true",
                "  handoffs:",
                "    - label: Code Review",
                "      agent: code-review",
                "      prompt: Review the diff",
                "  hooks:",
                "    post-edit:",
                "      command: npm test",
            ]
        ),
    )

    frontmatter = _parse_frontmatter(
        render_copilot_agent(load_agent_definition(source_dir))
    )

    assert frontmatter["target"] == "vscode"
    assert frontmatter["agents"] == "*"
    assert frontmatter["model"] == ["gpt-5.4-high", "gpt-5.4"]
    assert frontmatter["disable-model-invocation"] is True
    assert frontmatter["user-invocable"] is True
    assert frontmatter["mcp-servers"] == [
        {
            "id": "github",
            "command": {"name": "npx", "args": ["-y", "github-mcp"]},
        }
    ]
    assert frontmatter["argument-hint"] == "repo:path"
    assert frontmatter["handoffs"] == [
        {
            "label": "Code Review",
            "agent": "code-review",
            "prompt": "Review the diff",
        }
    ]
    assert frontmatter["hooks"] == {"post-edit": {"command": "npm test"}}


def test_claude_generator_minimal_without_defaults(agents_home: Path) -> None:
    agent = load_agent_definition(install_fixture(agents_home, "minimal-agent"))

    frontmatter = _parse_frontmatter(render_claude_agent(agent, emit_defaults=False))

    assert frontmatter == {
        "name": "code-reviewer",
        "description": "Reviews code for correctness and risk.",
    }


def test_codex_generator_minimal_without_defaults(agents_home: Path) -> None:
    agent = load_agent_definition(install_fixture(agents_home, "minimal-agent"))

    parsed = tomllib.loads(render_codex_agent(agent, emit_defaults=False))

    assert parsed["name"] == "code-reviewer"
    assert parsed["description"] == "Reviews code for correctness and risk."
    assert parsed["sandbox_mode"] == "read-only"
    assert "model" not in parsed
    assert "model_reasoning_effort" not in parsed


def test_claude_generator_minimal_with_defaults(agents_home: Path) -> None:
    agent = load_agent_definition(install_fixture(agents_home, "minimal-agent"))

    frontmatter = _parse_frontmatter(render_claude_agent(agent, emit_defaults=True))

    assert frontmatter == {
        "name": "code-reviewer",
        "description": "Reviews code for correctness and risk.",
        "model": "opus-4.6",
        "effort": "high",
    }


def test_codex_generator_minimal_with_defaults(agents_home: Path) -> None:
    agent = load_agent_definition(install_fixture(agents_home, "minimal-agent"))

    parsed = tomllib.loads(render_codex_agent(agent, emit_defaults=True))

    assert parsed["name"] == "code-reviewer"
    assert parsed["description"] == "Reviews code for correctness and risk."
    assert parsed["model"] == "gpt-5.4"
    assert parsed["model_reasoning_effort"] == "high"
    assert parsed["sandbox_mode"] == "read-only"


def test_copilot_generator_minimal_with_defaults(agents_home: Path) -> None:
    agent = load_agent_definition(install_fixture(agents_home, "minimal-agent"))

    frontmatter = _parse_frontmatter(render_copilot_agent(agent, emit_defaults=True))

    assert frontmatter == {
        "name": "code-reviewer",
        "description": "Reviews code for correctness and risk.",
        "model": "gpt-5.4-high",
    }


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


def test_repo_retrorabbit_renders_as_floating_agent() -> None:
    source_dir = Path(__file__).resolve().parents[1] / "agents" / "retrorabbit_code_reviewer"
    agent = load_agent_definition(source_dir)

    claude_frontmatter = _parse_frontmatter(render_claude_agent(agent))
    copilot_frontmatter = _parse_frontmatter(render_copilot_agent(agent))
    codex_document = tomllib.loads(render_codex_agent(agent))

    assert "model" not in claude_frontmatter
    assert "effort" not in claude_frontmatter
    assert "model" not in copilot_frontmatter
    assert "model" not in codex_document
    assert "model_reasoning_effort" not in codex_document
