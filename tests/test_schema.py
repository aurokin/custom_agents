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
    assert agent.model_strategy == "pinned-defaults"
    assert agent.should_emit_model_defaults() is True
    assert agent.skills == []
    assert agent.claude.model is None
    assert agent.claude.effort is None
    assert agent.resolved_claude_model() == "opus-4.7"
    assert agent.resolved_claude_effort() == "high"
    assert agent.codex.model is None
    assert agent.codex.model_reasoning_effort is None
    assert agent.resolved_codex_model() == "gpt-5.5"
    assert agent.resolved_codex_reasoning_effort() == "high"
    assert agent.codex.sandbox_mode is None
    assert agent.copilot.model is None
    assert agent.resolved_copilot_model() == "gpt-5.5-high"
    assert agent.gemini.model is None


def test_schema_explicit_floating_model_strategy(agents_home: Path) -> None:
    source_dir = write_agent(
        agents_home,
        "floating-reviewer",
        "\n".join(
            [
                "name: floating-reviewer",
                "description: Uses downstream model defaults",
                "defaults:",
                "  model_strategy: floating",
            ]
        ),
    )

    agent = load_agent_definition(source_dir)

    assert agent.model_strategy == "floating"
    assert agent.should_emit_model_defaults() is False


def test_schema_rejects_invalid_model_strategy(agents_home: Path) -> None:
    source_dir = write_agent(
        agents_home,
        "invalid-model-strategy",
        "\n".join(
            [
                "name: invalid-model-strategy",
                "description: Invalid model strategy",
                "defaults:",
                "  model_strategy: drift",
            ]
        ),
    )

    with pytest.raises(SchemaError, match="Invalid defaults.model_strategy"):
        load_agent_definition(source_dir)


def test_schema_rejects_unknown_defaults_keys(agents_home: Path) -> None:
    source_dir = write_agent(
        agents_home,
        "unknown-defaults",
        "\n".join(
            [
                "name: unknown-defaults",
                "description: Unknown defaults key",
                "defaults:",
                "  sandbox: read-only",
                "  model_mode: floating",
            ]
        ),
    )

    with pytest.raises(SchemaError, match="Unknown defaults keys"):
        load_agent_definition(source_dir)


def test_schema_rejects_unknown_gemini_keys(agents_home: Path) -> None:
    source_dir = write_agent(
        agents_home,
        "bad-gemini",
        "\n".join(
            [
                "name: bad-gemini",
                "description: Invalid gemini config",
                "gemini:",
                "  unsupported: true",
            ]
        ),
    )

    with pytest.raises(SchemaError, match="Unknown gemini keys"):
        load_agent_definition(source_dir)


def test_schema_rejects_invalid_gemini_temperature(agents_home: Path) -> None:
    source_dir = write_agent(
        agents_home,
        "invalid-gemini-temperature",
        "\n".join(
            [
                "name: invalid-gemini-temperature",
                "description: Invalid gemini temperature",
                "gemini:",
                "  temperature: 3",
            ]
        ),
    )

    with pytest.raises(SchemaError, match="Invalid gemini.temperature"):
        load_agent_definition(source_dir)


def test_schema_full(agents_home: Path) -> None:
    source_dir = install_fixture(agents_home, "full-agent")

    agent = load_agent_definition(source_dir)

    assert agent.sandbox == "workspace-write"
    assert agent.skills == ["web-design-guidelines", "plan-reviewer"]
    assert agent.claude.model == "opus-4.6"
    assert agent.claude.extra == {"background": True}
    assert agent.copilot.target == "github-copilot"
    assert agent.copilot.tools == ["read", "search", "edit", "github/*"]
    assert agent.copilot.model == "gpt-5.4-high"
    assert agent.copilot.disable_model_invocation is True
    assert agent.copilot.user_invocable is True
    assert agent.copilot.metadata == {
        "owner": "frontend-platform",
        "tier": "primary",
    }
    assert agent.codex.model == "gpt-5.4"
    assert agent.codex.model_reasoning_effort == "high"
    assert agent.codex.nickname_candidates == ["Atlas", "Echo"]
    assert agent.codex.skills_config == [
        {"name": "web-design-guidelines", "enabled": False}
    ]
    assert agent.gemini.tools == ["read_file", "grep_search", "mcp_github_*"]
    assert agent.gemini.model == "gemini-2.5-flash"
    assert agent.gemini.temperature == 0.2
    assert agent.gemini.max_turns == 12
    assert agent.gemini.timeout_mins == 10
    assert agent.gemini.mcp_servers == {
        "github": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-github"],
        }
    }


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


def test_schema_unknown_copilot_keys_fail(agents_home: Path) -> None:
    source_dir = write_agent(
        agents_home,
        "bad-copilot",
        "\n".join(
            [
                "name: reviewer",
                "description: Invalid copilot config",
                "copilot:",
                "  unsupported: true",
            ]
        ),
    )

    with pytest.raises(SchemaError, match="Unknown copilot keys"):
        load_agent_definition(source_dir)


def test_schema_vscode_copilot_supports_model_list_and_mcp_server_list(
    agents_home: Path,
) -> None:
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
                "      send: true",
                "      model:",
                "        - gpt-5.4-high",
                "        - gpt-5.4",
                "  hooks:",
                "    post-edit:",
                "      command: npm test",
            ]
        ),
    )

    agent = load_agent_definition(source_dir)

    assert agent.copilot.target == "vscode"
    assert agent.copilot.agents == "*"
    assert agent.copilot.model == ["gpt-5.4-high", "gpt-5.4"]
    assert agent.copilot.mcp_servers == [
        {
            "id": "github",
            "command": {"name": "npx", "args": ["-y", "github-mcp"]},
        }
    ]
    assert agent.copilot.argument_hint == "repo:path"
    assert agent.copilot.disable_model_invocation is True
    assert agent.copilot.user_invocable is True
    assert agent.copilot.handoffs == [
        {
            "label": "Code Review",
            "agent": "code-review",
            "send": True,
            "model": ["gpt-5.4-high", "gpt-5.4"],
        }
    ]
    assert agent.copilot.hooks == {"post-edit": {"command": "npm test"}}


def test_schema_vscode_copilot_rejects_github_only_metadata(agents_home: Path) -> None:
    source_dir = write_agent(
        agents_home,
        "vscode-invalid",
        "\n".join(
            [
                "name: vscode-invalid",
                "description: Invalid VS Code config",
                "copilot:",
                "  target: vscode",
                "  metadata:",
                "    team: editor",
            ]
        ),
    )

    with pytest.raises(SchemaError, match="only supported for target 'github-copilot'"):
        load_agent_definition(source_dir)


def test_schema_copilot_model_list_requires_vscode_target(agents_home: Path) -> None:
    source_dir = write_agent(
        agents_home,
        "copilot-model-list",
        "\n".join(
            [
                "name: ambiguous-copilot",
                "description: Missing explicit target",
                "copilot:",
                "  model:",
                "    - gpt-5.4-high",
                "    - gpt-5.4",
            ]
        ),
    )

    with pytest.raises(SchemaError, match="Set copilot.target to 'vscode'"):
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


def test_schema_cursor_block_parses(agents_home: Path) -> None:
    source_dir = install_fixture(agents_home, "full-agent")

    agent = load_agent_definition(source_dir)

    assert agent.cursor.model == "gpt-5.4-cursor"
    assert agent.cursor.readonly is False
    assert agent.cursor.description == "Cursor-specific frontend reviewer blurb"
    assert agent.resolved_cursor_readonly() is False


def test_schema_cursor_readonly_derives_from_sandbox(agents_home: Path) -> None:
    source_dir = install_fixture(agents_home, "minimal-agent")

    agent = load_agent_definition(source_dir)

    assert agent.cursor.model is None
    assert agent.cursor.readonly is None
    assert agent.cursor.description is None
    assert agent.resolved_cursor_readonly() is True


def test_schema_cursor_readonly_omitted_for_workspace_write(agents_home: Path) -> None:
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

    assert agent.resolved_cursor_readonly() is None


def test_schema_cursor_rejects_unknown_keys(agents_home: Path) -> None:
    source_dir = write_agent(
        agents_home,
        "bad-cursor",
        "\n".join(
            [
                "name: bad-cursor",
                "description: Invalid cursor config",
                "cursor:",
                "  scope: project",
            ]
        ),
    )

    with pytest.raises(SchemaError, match="Unknown cursor keys"):
        load_agent_definition(source_dir)


def test_schema_cursor_rejects_non_bool_readonly(agents_home: Path) -> None:
    source_dir = write_agent(
        agents_home,
        "bad-cursor-readonly",
        "\n".join(
            [
                "name: bad-cursor-readonly",
                "description: Invalid readonly type",
                "cursor:",
                "  readonly: yes-please",
            ]
        ),
    )

    with pytest.raises(SchemaError, match="readonly"):
        load_agent_definition(source_dir)


def test_schema_tprompt_block_enables_export(agents_home: Path) -> None:
    source_dir = install_fixture(agents_home, "tprompt-agent")

    agent = load_agent_definition(source_dir)

    assert agent.tprompt.enabled is True
    assert agent.tprompt.title == "Skill Reviewer"
    assert agent.tprompt.tags == ["review", "skill"]
    assert agent.tprompt.key == "r"
    assert agent.tprompt.description is None
    assert agent.tprompt.filename is None


def test_schema_tprompt_absent_block_disables_export(agents_home: Path) -> None:
    source_dir = install_fixture(agents_home, "minimal-agent")

    agent = load_agent_definition(source_dir)

    assert agent.tprompt.enabled is False
    assert agent.tprompt.title is None


def test_schema_tprompt_empty_block_enables_export(agents_home: Path) -> None:
    source_dir = write_agent(
        agents_home,
        "tprompt-empty",
        "\n".join(
            [
                "name: tprompt-empty",
                "description: Tprompt opt-in with defaults",
                "tprompt: {}",
            ]
        ),
    )

    agent = load_agent_definition(source_dir)

    assert agent.tprompt.enabled is True
    assert agent.tprompt.title is None


def test_schema_tprompt_bare_key_enables_export(agents_home: Path) -> None:
    source_dir = write_agent(
        agents_home,
        "tprompt-bare",
        "\n".join(
            [
                "name: tprompt-bare",
                "description: Bare tprompt key parses as null but still opts in",
                "tprompt:",
            ]
        ),
    )

    agent = load_agent_definition(source_dir)

    assert agent.tprompt.enabled is True
    assert agent.tprompt.title is None


def test_schema_tprompt_rejects_unknown_keys(agents_home: Path) -> None:
    source_dir = write_agent(
        agents_home,
        "tprompt-unknown",
        "\n".join(
            [
                "name: tprompt-unknown",
                "description: Invalid tprompt config",
                "tprompt:",
                "  title: Bad",
                "  shortcut: x",
            ]
        ),
    )

    with pytest.raises(SchemaError, match="Unknown tprompt keys"):
        load_agent_definition(source_dir)


def test_schema_tprompt_rejects_invalid_filename(agents_home: Path) -> None:
    source_dir = write_agent(
        agents_home,
        "tprompt-bad-filename",
        "\n".join(
            [
                "name: tprompt-bad-filename",
                "description: Invalid tprompt filename",
                "tprompt:",
                "  filename: 'Bad Name'",
            ]
        ),
    )

    with pytest.raises(SchemaError, match="Invalid tprompt.filename"):
        load_agent_definition(source_dir)


def test_schema_harness_defaults_to_empty(agents_home: Path) -> None:
    source_dir = install_fixture(agents_home, "minimal-agent", "reviewer")

    agent = load_agent_definition(source_dir)

    assert agent.harness.include is None
    assert agent.harness.exclude is None


def test_schema_harness_include_parses(agents_home: Path) -> None:
    source_dir = write_agent(
        agents_home,
        "with-include",
        "\n".join(
            [
                "name: with-include",
                "description: Has harness.include",
                "harness:",
                "  include: [claude, codex]",
            ]
        ),
    )

    agent = load_agent_definition(source_dir)

    assert agent.harness.include == ["claude", "codex"]
    assert agent.harness.exclude is None


def test_schema_harness_exclude_parses(agents_home: Path) -> None:
    source_dir = write_agent(
        agents_home,
        "with-exclude",
        "\n".join(
            [
                "name: with-exclude",
                "description: Has harness.exclude",
                "harness:",
                "  exclude: [tprompt, gemini]",
            ]
        ),
    )

    agent = load_agent_definition(source_dir)

    assert agent.harness.exclude == ["tprompt", "gemini"]
    assert agent.harness.include is None


def test_schema_harness_rejects_both_include_and_exclude(agents_home: Path) -> None:
    source_dir = write_agent(
        agents_home,
        "both",
        "\n".join(
            [
                "name: both",
                "description: Sets both",
                "harness:",
                "  include: [claude]",
                "  exclude: [tprompt]",
            ]
        ),
    )

    with pytest.raises(SchemaError, match="only one of 'include' or 'exclude'"):
        load_agent_definition(source_dir)


def test_schema_harness_rejects_unknown_keyword(agents_home: Path) -> None:
    source_dir = write_agent(
        agents_home,
        "bad-keyword",
        "\n".join(
            [
                "name: bad-keyword",
                "description: Unknown keyword",
                "harness:",
                "  include: [claude, hermes]",
            ]
        ),
    )

    with pytest.raises(SchemaError, match="Unknown harness keyword"):
        load_agent_definition(source_dir)


def test_schema_harness_rejects_empty_include(agents_home: Path) -> None:
    source_dir = write_agent(
        agents_home,
        "empty-include",
        "\n".join(
            [
                "name: empty-include",
                "description: Empty include",
                "harness:",
                "  include: []",
            ]
        ),
    )

    with pytest.raises(SchemaError, match="harness.include .* must not be empty"):
        load_agent_definition(source_dir)


def test_schema_harness_rejects_empty_exclude(agents_home: Path) -> None:
    source_dir = write_agent(
        agents_home,
        "empty-exclude",
        "\n".join(
            [
                "name: empty-exclude",
                "description: Empty exclude",
                "harness:",
                "  exclude: []",
            ]
        ),
    )

    with pytest.raises(SchemaError, match="harness.exclude .* must not be empty"):
        load_agent_definition(source_dir)


def test_schema_harness_rejects_unknown_subkey(agents_home: Path) -> None:
    source_dir = write_agent(
        agents_home,
        "weird-key",
        "\n".join(
            [
                "name: weird-key",
                "description: Has bad key",
                "harness:",
                "  forbid: [claude]",
            ]
        ),
    )

    with pytest.raises(SchemaError, match="Unknown harness keys"):
        load_agent_definition(source_dir)


def test_schema_harness_rejects_duplicate_keyword(agents_home: Path) -> None:
    source_dir = write_agent(
        agents_home,
        "dup-keyword",
        "\n".join(
            [
                "name: dup-keyword",
                "description: Duplicate keyword",
                "harness:",
                "  include: [claude, claude]",
            ]
        ),
    )

    with pytest.raises(SchemaError, match="Duplicate harness keyword"):
        load_agent_definition(source_dir)


def test_repo_retrorabbit_code_reviewer_definition(initialized_repo: Path) -> None:
    source_dir = initialized_repo / "agents" / "retrorabbit-code-reviewer"

    agent = load_agent_definition(source_dir)

    assert agent.name == "retrorabbit-code-reviewer"
    assert agent.description == "Reviews code hunks for correctness, risk, and maintainability."
    assert agent.sandbox == "read-only"
    assert agent.model_strategy == "floating"
    assert agent.should_emit_model_defaults() is False
    assert agent.claude.tools == ["Read", "Grep", "Glob"]
    assert agent.claude.disallowed_tools == ["Write"]
    assert agent.claude.model is None
    assert agent.claude.effort is None
    assert agent.codex.model is None
    assert agent.codex.model_reasoning_effort is None
    assert agent.codex.nickname_candidates == ["RetroRabbit"]
    assert agent.gemini.tools == ["read_file", "grep_search"]
    assert agent.gemini.max_turns == 16
    assert agent.gemini.model is None


def test_repo_codexrabbit_code_reviewer_definition(initialized_repo: Path) -> None:
    source_dir = initialized_repo / "agents" / "codexrabbit-code-reviewer"

    agent = load_agent_definition(source_dir)

    assert agent.name == "codexrabbit-code-reviewer"
    assert agent.sandbox == "read-only"
    assert agent.model_strategy == "floating"
    assert agent.should_emit_model_defaults() is False
    assert agent.harness.include is None
    assert agent.harness.exclude is None
    assert agent.claude.tools == ["Read", "Grep", "Glob"]
    assert agent.claude.disallowed_tools == ["Write"]
    assert agent.claude.max_turns == 16
    assert agent.codex.model is None
    assert agent.codex.nickname_candidates == ["CodexRabbit"]
    assert agent.gemini.tools == ["read_file", "grep_search"]
    assert agent.gemini.max_turns == 16
