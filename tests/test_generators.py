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
from shared_agents.generators.cursor import build_cursor_frontmatter, render_cursor_agent
from shared_agents.generators.gemini import build_gemini_frontmatter, render_gemini_agent
from shared_agents.generators.opencode import (
    build_opencode_frontmatter,
    render_opencode_agent,
)
from shared_agents.generators.skills import (
    build_skill_frontmatter,
    normalize_skill_name,
    render_skill,
    skill_name,
)
from shared_agents.generators.tprompt import (
    SUBAGENT_FOOTER,
    build_tprompt_frontmatter,
    render_tprompt_agent,
    tprompt_prompt_id,
)
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
        "model": "opus-4.7",
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
    assert parsed["model"] == "gpt-5.5"
    assert parsed["model_reasoning_effort"] == "high"
    assert parsed["sandbox_mode"] == "read-only"
    assert "developer_instructions" in parsed


def test_gemini_generator_minimal_omits_tools_and_model(agents_home: Path) -> None:
    agent = load_agent_definition(install_fixture(agents_home, "minimal-agent"))

    rendered = render_gemini_agent(agent)
    frontmatter = _parse_frontmatter(rendered)

    assert frontmatter == {
        "name": "code-reviewer",
        "description": "Reviews code for correctness and risk.",
    }
    assert "tools" not in frontmatter
    assert "model" not in frontmatter
    assert "focused code reviewer" in rendered


def test_copilot_generator_minimal(agents_home: Path) -> None:
    agent = load_agent_definition(install_fixture(agents_home, "minimal-agent"))

    rendered = render_copilot_agent(agent)
    frontmatter = _parse_frontmatter(rendered)

    assert frontmatter == {
        "name": "code-reviewer",
        "description": "Reviews code for correctness and risk.",
        "model": "gpt-5.5-high",
    }
    assert "focused code reviewer" in rendered


def test_copilot_generator_minimal_without_defaults(agents_home: Path) -> None:
    agent = load_agent_definition(install_fixture(agents_home, "minimal-agent"))

    frontmatter = _parse_frontmatter(render_copilot_agent(agent, emit_defaults=False))

    assert frontmatter == {
        "name": "code-reviewer",
        "description": "Reviews code for correctness and risk.",
    }


def test_skill_name_normalization() -> None:
    assert normalize_skill_name("Review_Helper") == "review-helper"
    assert normalize_skill_name("review--helper") == "review-helper"


def test_skill_generator_minimal(agents_home: Path) -> None:
    write_agent(
        agents_home,
        "reviewer",
        "\n".join(
            [
                "name: code_reviewer",
                "description: Use when reviewing code changes.",
                "export: skill",
            ]
        ),
        instructions="Review the patch carefully.\n",
    )
    agent = load_agent_definition(agents_home / "agents" / "reviewer")

    rendered = render_skill(agent)
    frontmatter = _parse_frontmatter(rendered)

    assert skill_name(agent) == "code-reviewer"
    assert frontmatter["name"] == "code-reviewer"
    assert frontmatter["description"] == "Use when reviewing code changes."
    assert frontmatter["metadata"] == {
        "source": "custom_agents",
        "original_name": "code_reviewer",
    }
    assert "# Code Reviewer" in rendered
    assert "## Instructions" in rendered
    assert "Review the patch carefully." in rendered


def test_skill_generator_full_overrides(agents_home: Path) -> None:
    write_agent(
        agents_home,
        "reviewer",
        "\n".join(
            [
                "name: code-reviewer",
                "description: Native agent description",
                "export: skill",
                "skill:",
                "  name: review-helper",
                "  title: Review Helper",
                "  description: Use when reviewing a patch before merge.",
                "  tags: [review, code]",
                "  license: MIT",
                "  compatibility: [agent-skills]",
                "  metadata:",
                "    owner: platform",
            ]
        ),
    )
    agent = load_agent_definition(agents_home / "agents" / "reviewer")

    frontmatter = build_skill_frontmatter(agent)
    rendered = render_skill(agent)

    assert frontmatter["name"] == "review-helper"
    assert frontmatter["description"] == "Use when reviewing a patch before merge."
    assert frontmatter["tags"] == ["review", "code"]
    assert frontmatter["license"] == "MIT"
    assert frontmatter["compatibility"] == ["agent-skills"]
    assert frontmatter["metadata"]["owner"] == "platform"
    assert "# Review Helper" in rendered


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


def test_gemini_generator_full(agents_home: Path) -> None:
    agent = load_agent_definition(install_fixture(agents_home, "full-agent"))

    rendered = render_gemini_agent(agent)
    frontmatter = _parse_frontmatter(rendered)

    assert frontmatter["tools"] == ["read_file", "grep_search", "mcp_github_*"]
    assert frontmatter["model"] == "gemini-2.5-flash"
    assert frontmatter["temperature"] == 0.2
    assert frontmatter["max_turns"] == 12
    assert frontmatter["timeout_mins"] == 10
    assert frontmatter["mcpServers"] == {
        "github": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-github"],
        }
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


def test_gemini_generator_preserves_empty_tools_list(agents_home: Path) -> None:
    source_dir = write_agent(
        agents_home,
        "gemini-no-tools",
        "\n".join(
            [
                "name: locked-down-gemini-reviewer",
                "description: Gemini agent with no tools",
                "gemini:",
                "  tools: []",
            ]
        ),
    )

    frontmatter = _parse_frontmatter(
        render_gemini_agent(load_agent_definition(source_dir))
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


def test_gemini_generator_roundtrip(agents_home: Path) -> None:
    agent = load_agent_definition(install_fixture(agents_home, "full-agent"))

    assert build_gemini_frontmatter(agent) == _parse_frontmatter(
        render_gemini_agent(agent)
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
        "model": "opus-4.7",
        "effort": "high",
    }


def test_codex_generator_minimal_with_defaults(agents_home: Path) -> None:
    agent = load_agent_definition(install_fixture(agents_home, "minimal-agent"))

    parsed = tomllib.loads(render_codex_agent(agent, emit_defaults=True))

    assert parsed["name"] == "code-reviewer"
    assert parsed["description"] == "Reviews code for correctness and risk."
    assert parsed["model"] == "gpt-5.5"
    assert parsed["model_reasoning_effort"] == "high"
    assert parsed["sandbox_mode"] == "read-only"


def test_copilot_generator_minimal_with_defaults(agents_home: Path) -> None:
    agent = load_agent_definition(install_fixture(agents_home, "minimal-agent"))

    frontmatter = _parse_frontmatter(render_copilot_agent(agent, emit_defaults=True))

    assert frontmatter == {
        "name": "code-reviewer",
        "description": "Reviews code for correctness and risk.",
        "model": "gpt-5.5-high",
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


def test_cursor_generator_minimal_emits_derived_readonly(agents_home: Path) -> None:
    agent = load_agent_definition(install_fixture(agents_home, "minimal-agent"))

    rendered = render_cursor_agent(agent)
    frontmatter = _parse_frontmatter(rendered)

    assert frontmatter == {
        "name": "code-reviewer",
        "description": "Reviews code for correctness and risk.",
        "readonly": True,
    }
    assert "model" not in frontmatter
    assert "focused code reviewer" in rendered


def test_opencode_generator_minimal_emits_subagent_and_readonly_permissions(
    agents_home: Path,
) -> None:
    agent = load_agent_definition(install_fixture(agents_home, "minimal-agent"))

    rendered = render_opencode_agent(agent)
    frontmatter = _parse_frontmatter(rendered)

    assert frontmatter == {
        "description": "Reviews code for correctness and risk.",
        "mode": "subagent",
        "permission": {
            "edit": "deny",
            "bash": "deny",
        },
    }
    assert "focused code reviewer" in rendered


def test_opencode_generator_full(agents_home: Path) -> None:
    agent = load_agent_definition(install_fixture(agents_home, "full-agent"))

    rendered = render_opencode_agent(agent)
    frontmatter = _parse_frontmatter(rendered)

    assert frontmatter == {
        "description": "OpenCode-specific frontend reviewer blurb",
        "mode": "subagent",
        "model": "opencode/gpt-5.1-codex",
        "variant": "reasoning",
        "temperature": 0.1,
        "top_p": 0.9,
        "disable": True,
        "hidden": True,
        "color": "accent",
        "steps": 8,
        "permission": {
            "edit": "ask",
            "bash": {
                "*": "ask",
                "git diff*": "allow",
            },
        },
        "reasoningEffort": "high",
    }


def test_opencode_generator_workspace_write_omits_permissions(
    agents_home: Path,
) -> None:
    source_dir = write_agent(
        agents_home,
        "opencode-workspace-write",
        "\n".join(
            [
                "name: workspace-opencode",
                "description: Workspace-write agent",
                "defaults:",
                "  sandbox: workspace-write",
            ]
        ),
    )

    frontmatter = _parse_frontmatter(
        render_opencode_agent(load_agent_definition(source_dir))
    )

    assert frontmatter == {
        "description": "Workspace-write agent",
        "mode": "subagent",
    }


def test_cursor_generator_full(agents_home: Path) -> None:
    agent = load_agent_definition(install_fixture(agents_home, "full-agent"))

    rendered = render_cursor_agent(agent)
    frontmatter = _parse_frontmatter(rendered)

    assert frontmatter == {
        "name": "frontend-reviewer",
        "description": "Cursor-specific frontend reviewer blurb",
        "model": "gpt-5.4-cursor",
        "readonly": False,
    }


def test_cursor_generator_omits_readonly_for_workspace_write(agents_home: Path) -> None:
    source_dir = write_agent(
        agents_home,
        "cursor-workspace-write",
        "\n".join(
            [
                "name: workspace-cursor",
                "description: Workspace-write agent",
                "defaults:",
                "  sandbox: workspace-write",
            ]
        ),
    )
    agent = load_agent_definition(source_dir)

    frontmatter = _parse_frontmatter(render_cursor_agent(agent))

    assert frontmatter == {
        "name": "workspace-cursor",
        "description": "Workspace-write agent",
    }


def test_cursor_generator_roundtrip(agents_home: Path) -> None:
    agent = load_agent_definition(install_fixture(agents_home, "full-agent"))

    assert build_cursor_frontmatter(agent) == _parse_frontmatter(
        render_cursor_agent(agent)
    )


def test_opencode_generator_roundtrip(agents_home: Path) -> None:
    agent = load_agent_definition(install_fixture(agents_home, "full-agent"))

    assert build_opencode_frontmatter(agent) == _parse_frontmatter(
        render_opencode_agent(agent)
    )


def test_tprompt_generator_renders_explicit_fields(agents_home: Path) -> None:
    agent = load_agent_definition(install_fixture(agents_home, "tprompt-agent"))

    rendered = render_tprompt_agent(agent)
    frontmatter = _parse_frontmatter(rendered)

    assert frontmatter == {
        "title": "Skill Reviewer",
        "description": "Acts like a skill that reviews changes in the main thread.",
        "tags": ["review", "skill"],
        "key": "r",
    }
    assert "Review the staged diff" in rendered
    assert rendered.rstrip("\n").endswith(SUBAGENT_FOOTER)
    assert tprompt_prompt_id(agent) == "skill-reviewer-ca"


def test_tprompt_generator_defaults_title_from_name(agents_home: Path) -> None:
    source_dir = write_agent(
        agents_home,
        "tprompt-defaults",
        "\n".join(
            [
                "name: plan-reviewer",
                "description: Skeptical plan review.",
                "tprompt: {}",
            ]
        ),
    )
    agent = load_agent_definition(source_dir)

    frontmatter = _parse_frontmatter(render_tprompt_agent(agent))

    assert frontmatter == {
        "title": "Plan Reviewer",
        "description": "Skeptical plan review.",
        "tags": [],
    }
    assert tprompt_prompt_id(agent) == "plan-reviewer-ca"


def test_tprompt_generator_filename_overrides_prompt_id(agents_home: Path) -> None:
    source_dir = write_agent(
        agents_home,
        "tprompt-filename-override",
        "\n".join(
            [
                "name: retrorabbit_code_reviewer",
                "description: Review hunks.",
                "tprompt:",
                "  filename: rabbit-review",
            ]
        ),
    )
    agent = load_agent_definition(source_dir)

    assert tprompt_prompt_id(agent) == "rabbit-review-ca"


def test_tprompt_generator_roundtrip(agents_home: Path) -> None:
    agent = load_agent_definition(install_fixture(agents_home, "tprompt-agent"))

    assert build_tprompt_frontmatter(agent) == _parse_frontmatter(
        render_tprompt_agent(agent)
    )


def test_repo_retrorabbit_renders_as_floating_agent(initialized_repo: Path) -> None:
    source_dir = initialized_repo / "agents" / "retrorabbit-code-reviewer"
    agent = load_agent_definition(source_dir)

    claude_frontmatter = _parse_frontmatter(render_claude_agent(agent))
    copilot_frontmatter = _parse_frontmatter(render_copilot_agent(agent))
    codex_document = tomllib.loads(render_codex_agent(agent))
    cursor_frontmatter = _parse_frontmatter(render_cursor_agent(agent))
    opencode_frontmatter = _parse_frontmatter(render_opencode_agent(agent))
    gemini_frontmatter = _parse_frontmatter(render_gemini_agent(agent))

    assert "model" not in claude_frontmatter
    assert "effort" not in claude_frontmatter
    assert "model" not in copilot_frontmatter
    assert "model" not in codex_document
    assert "model_reasoning_effort" not in codex_document
    assert "model" not in cursor_frontmatter
    assert cursor_frontmatter["readonly"] is True
    assert "model" not in opencode_frontmatter
    assert opencode_frontmatter["permission"] == {"edit": "deny", "bash": "deny"}
    assert gemini_frontmatter["tools"] == ["read_file", "grep_search"]
    assert gemini_frontmatter["max_turns"] == 16
    assert "model" not in gemini_frontmatter
