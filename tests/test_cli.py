from __future__ import annotations

from pathlib import Path
import json
import os
import stat

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib

import pytest

import yaml

from shared_agents.main import main
from shared_agents.manifest import (
    MANIFEST_VERSION,
    legacy_manifest_path,
    load_manifest,
    manifest_path,
)
from tests.conftest import install_fixture, write_agent


def _install_fake_tprompt(
    fake_home: Path, monkeypatch: pytest.MonkeyPatch
) -> Path:
    bin_dir = fake_home / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    prompts_dir = fake_home / ".config" / "tprompt" / "prompts"
    script = bin_dir / "tprompt"
    script.write_text(
        "#!/bin/sh\n"
        "if [ \"$1\" = \"new\" ]; then\n"
        f'  dir="{prompts_dir}"\n'
        "  mkdir -p \"$dir\"\n"
        "  target=\"$dir/$2.md\"\n"
        "  if [ -e \"$target\" ]; then\n"
        "    echo \"file already exists: $target\" >&2\n"
        "    exit 1\n"
        "  fi\n"
        "  printf -- '---\\ntitle:\\ndescription:\\ntags: []\\nkey:\\nmode:\\nenter:\\n---\\n' > \"$target\"\n"
        "  echo \"$target\"\n"
        "  exit 0\n"
        "fi\n"
        "exit 0\n",
        encoding="utf-8",
    )
    script.chmod(script.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    return prompts_dir


def _parse_frontmatter(document: str) -> dict:
    _, yaml_block, _ = document.split("---", 2)
    return yaml.safe_load(yaml_block)


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
    assert (fake_home / ".cursor" / "agents" / "code-reviewer.md").exists()
    assert (fake_home / ".gemini" / "agents" / "code-reviewer.md").exists()
    assert not (fake_home / ".agents" / "agents").exists()
    manifest = load_manifest(agents_home)
    assert manifest.generated_files["claude"]
    assert manifest.linked_targets == {}
    assert not (agents_home / ".shared-agents-manifest.json").exists()

    claude_frontmatter = _parse_frontmatter(
        (fake_home / ".claude" / "agents" / "code-reviewer.md").read_text(
            encoding="utf-8"
        )
    )
    copilot_frontmatter = _parse_frontmatter(
        (fake_home / ".copilot" / "agents" / "code-reviewer.agent.md").read_text(
            encoding="utf-8"
        )
    )
    codex_document = tomllib.loads(
        (fake_home / ".codex" / "agents" / "code-reviewer.toml").read_text(
            encoding="utf-8"
        )
    )
    gemini_frontmatter = _parse_frontmatter(
        (fake_home / ".gemini" / "agents" / "code-reviewer.md").read_text(
            encoding="utf-8"
        )
    )
    cursor_frontmatter = _parse_frontmatter(
        (fake_home / ".cursor" / "agents" / "code-reviewer.md").read_text(
            encoding="utf-8"
        )
    )

    assert claude_frontmatter["model"] == "opus-4.7"
    assert claude_frontmatter["effort"] == "high"
    assert copilot_frontmatter["model"] == "gpt-5.5-high"
    assert codex_document["model"] == "gpt-5.5"
    assert codex_document["model_reasoning_effort"] == "high"
    assert "tools" not in gemini_frontmatter
    assert "model" not in gemini_frontmatter
    assert cursor_frontmatter["readonly"] is True
    assert "model" not in cursor_frontmatter


def test_sync_end_to_end_supports_explicit_floating_model_strategy(
    agents_home: Path, fake_home: Path
) -> None:
    write_agent(
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

    assert main(["sync", "--source-root", str(agents_home)]) == 0

    claude_frontmatter = _parse_frontmatter(
        (fake_home / ".claude" / "agents" / "floating-reviewer.md").read_text(
            encoding="utf-8"
        )
    )
    copilot_frontmatter = _parse_frontmatter(
        (fake_home / ".copilot" / "agents" / "floating-reviewer.agent.md").read_text(
            encoding="utf-8"
        )
    )
    codex_document = tomllib.loads(
        (fake_home / ".codex" / "agents" / "floating-reviewer.toml").read_text(
            encoding="utf-8"
        )
    )
    gemini_frontmatter = _parse_frontmatter(
        (fake_home / ".gemini" / "agents" / "floating-reviewer.md").read_text(
            encoding="utf-8"
        )
    )

    assert "model" not in claude_frontmatter
    assert "effort" not in claude_frontmatter
    assert "model" not in copilot_frontmatter
    assert "model" not in codex_document
    assert "model_reasoning_effort" not in codex_document
    assert "tools" not in gemini_frontmatter
    assert "model" not in gemini_frontmatter


def test_sync_floating_strategy_preserves_explicit_model_settings(
    agents_home: Path, fake_home: Path
) -> None:
    write_agent(
        agents_home,
        "floating-but-pinned",
        "\n".join(
            [
                "name: floating-but-pinned",
                "description: Floating fallback with explicit per-consumer pins",
                "defaults:",
                "  model_strategy: floating",
                "claude:",
                "  model: opus-4.6",
                "  effort: high",
                "copilot:",
                "  model: gpt-5.4-high",
                "codex:",
                "  model: gpt-5.4",
                "  model_reasoning_effort: high",
                "gemini:",
                "  model: gemini-2.5-flash",
                "  max_turns: 12",
            ]
        ),
    )

    assert main(["sync", "--source-root", str(agents_home)]) == 0

    claude_frontmatter = _parse_frontmatter(
        (fake_home / ".claude" / "agents" / "floating-but-pinned.md").read_text(
            encoding="utf-8"
        )
    )
    copilot_frontmatter = _parse_frontmatter(
        (
            fake_home / ".copilot" / "agents" / "floating-but-pinned.agent.md"
        ).read_text(encoding="utf-8")
    )
    codex_document = tomllib.loads(
        (fake_home / ".codex" / "agents" / "floating-but-pinned.toml").read_text(
            encoding="utf-8"
        )
    )
    gemini_frontmatter = _parse_frontmatter(
        (fake_home / ".gemini" / "agents" / "floating-but-pinned.md").read_text(
            encoding="utf-8"
        )
    )

    assert claude_frontmatter["model"] == "opus-4.6"
    assert claude_frontmatter["effort"] == "high"
    assert copilot_frontmatter["model"] == "gpt-5.4-high"
    assert codex_document["model"] == "gpt-5.4"
    assert codex_document["model_reasoning_effort"] == "high"
    assert gemini_frontmatter["model"] == "gemini-2.5-flash"
    assert gemini_frontmatter["max_turns"] == 12


def test_sync_end_to_end_preserves_explicit_model_settings(
    agents_home: Path, fake_home: Path
) -> None:
    install_fixture(agents_home, "full-agent")

    assert main(["sync", "--source-root", str(agents_home)]) == 0

    claude_frontmatter = _parse_frontmatter(
        (fake_home / ".claude" / "agents" / "frontend-reviewer.md").read_text(
            encoding="utf-8"
        )
    )
    copilot_frontmatter = _parse_frontmatter(
        (
            fake_home / ".copilot" / "agents" / "frontend-reviewer.agent.md"
        ).read_text(encoding="utf-8")
    )
    codex_document = tomllib.loads(
        (fake_home / ".codex" / "agents" / "frontend-reviewer.toml").read_text(
            encoding="utf-8"
        )
    )
    gemini_frontmatter = _parse_frontmatter(
        (fake_home / ".gemini" / "agents" / "frontend-reviewer.md").read_text(
            encoding="utf-8"
        )
    )

    assert claude_frontmatter["model"] == "opus-4.6"
    assert claude_frontmatter["effort"] == "high"
    assert copilot_frontmatter["model"] == "gpt-5.4-high"
    assert codex_document["model"] == "gpt-5.4"
    assert codex_document["model_reasoning_effort"] == "high"
    assert gemini_frontmatter["tools"] == ["read_file", "grep_search", "mcp_github_*"]
    assert gemini_frontmatter["model"] == "gemini-2.5-flash"
    assert gemini_frontmatter["temperature"] == 0.2


def test_clean_removes_manifest_owned_files(agents_home: Path, fake_home: Path) -> None:
    install_fixture(agents_home, "minimal-agent")
    assert main(["sync", "--source-root", str(agents_home)]) == 0

    assert main(["clean", "--source-root", str(agents_home)]) == 0

    assert not (fake_home / ".claude" / "agents" / "code-reviewer.md").exists()
    assert not (fake_home / ".copilot" / "agents" / "code-reviewer.agent.md").exists()
    assert not (fake_home / ".codex" / "agents" / "code-reviewer.toml").exists()
    assert not (fake_home / ".cursor" / "agents" / "code-reviewer.md").exists()
    assert not (fake_home / ".gemini" / "agents" / "code-reviewer.md").exists()
    assert load_manifest(agents_home) == load_manifest(agents_home).empty()


def test_sync_and_clean_support_legacy_manifest_without_gemini_key(
    agents_home: Path, fake_home: Path
) -> None:
    install_fixture(agents_home, "minimal-agent")
    legacy_path = legacy_manifest_path(agents_home)
    stale_codex_path = fake_home / ".codex" / "agents" / "stale-reviewer.toml"
    stale_codex_path.parent.mkdir(parents=True, exist_ok=True)
    stale_codex_path.write_text("name = 'stale-reviewer'\n", encoding="utf-8")
    legacy_path.write_text(
        json.dumps(
            {
                "version": 1,
                "generated_files": {
                    "claude": [],
                    "copilot": [],
                    "codex": [str(stale_codex_path)],
                },
                "linked_targets": {},
            }
        ),
        encoding="utf-8",
    )

    assert main(["sync", "--source-root", str(agents_home)]) == 0
    assert (fake_home / ".gemini" / "agents" / "code-reviewer.md").exists()
    assert not stale_codex_path.exists()
    assert not legacy_path.exists()

    assert main(["clean", "--source-root", str(agents_home)]) == 0
    assert not (fake_home / ".gemini" / "agents" / "code-reviewer.md").exists()


def test_clean_supports_legacy_manifest_without_gemini_key(
    agents_home: Path, fake_home: Path
) -> None:
    install_fixture(agents_home, "minimal-agent")
    legacy_path = legacy_manifest_path(agents_home)
    stale_codex_path = fake_home / ".codex" / "agents" / "stale-reviewer.toml"
    stale_codex_path.parent.mkdir(parents=True, exist_ok=True)
    stale_codex_path.write_text("name = 'stale-reviewer'\n", encoding="utf-8")
    legacy_path.write_text(
        json.dumps(
            {
                "version": 1,
                "generated_files": {
                    "claude": [],
                    "copilot": [],
                    "codex": [str(stale_codex_path)],
                },
                "linked_targets": {},
            }
        ),
        encoding="utf-8",
    )

    assert main(["clean", "--source-root", str(agents_home)]) == 0
    assert not stale_codex_path.exists()
    assert not legacy_path.exists()


def test_sync_supports_legacy_manifest_without_cursor_key(
    agents_home: Path, fake_home: Path
) -> None:
    install_fixture(agents_home, "minimal-agent")
    legacy_path = legacy_manifest_path(agents_home)
    stale_cursor_path = fake_home / ".cursor" / "agents" / "stale-reviewer.md"
    stale_cursor_path.parent.mkdir(parents=True, exist_ok=True)
    stale_cursor_path.write_text(
        "---\nname: stale\n---\n\nstale\n", encoding="utf-8"
    )
    legacy_path.write_text(
        json.dumps(
            {
                "version": 1,
                "generated_files": {
                    "claude": [],
                    "copilot": [],
                    "codex": [],
                    "gemini": [],
                },
                "linked_targets": {},
            }
        ),
        encoding="utf-8",
    )

    assert main(["sync", "--source-root", str(agents_home)]) == 0
    assert (fake_home / ".cursor" / "agents" / "code-reviewer.md").exists()
    assert stale_cursor_path.exists()
    assert not legacy_path.exists()


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
    assert (fake_home / ".cursor" / "agents" / "alpha.md").exists()
    assert (fake_home / ".gemini" / "agents" / "alpha.md").exists()

    assert main(["sync", "--source-root", str(second_home)]) == 0

    assert not (fake_home / ".claude" / "agents" / "alpha.md").exists()
    assert not (fake_home / ".copilot" / "agents" / "alpha.agent.md").exists()
    assert not (fake_home / ".codex" / "agents" / "alpha.toml").exists()
    assert not (fake_home / ".cursor" / "agents" / "alpha.md").exists()
    assert not (fake_home / ".gemini" / "agents" / "alpha.md").exists()
    assert (fake_home / ".claude" / "agents" / "beta.md").exists()
    assert (fake_home / ".copilot" / "agents" / "beta.agent.md").exists()
    assert (fake_home / ".codex" / "agents" / "beta.toml").exists()
    assert (fake_home / ".cursor" / "agents" / "beta.md").exists()
    assert (fake_home / ".gemini" / "agents" / "beta.md").exists()


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


def test_sync_writes_tprompt_when_executable_available(
    agents_home: Path, fake_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    install_fixture(agents_home, "tprompt-agent")
    prompts_dir = _install_fake_tprompt(fake_home, monkeypatch)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(fake_home / ".config"))

    assert main(["sync", "--source-root", str(agents_home)]) == 0

    target = prompts_dir / "skill-reviewer-ca.md"
    assert target.exists()
    rendered = target.read_text(encoding="utf-8")
    frontmatter = _parse_frontmatter(rendered)
    assert frontmatter["title"] == "Skill Reviewer"
    assert frontmatter["tags"] == ["review", "skill"]
    assert "Do not use subagents for this specific request." in rendered

    manifest = load_manifest(agents_home)
    assert str(target) in manifest.paths("tprompt")


def test_sync_resync_overwrites_existing_tprompt_in_place(
    agents_home: Path, fake_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    install_fixture(agents_home, "tprompt-agent")
    prompts_dir = _install_fake_tprompt(fake_home, monkeypatch)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(fake_home / ".config"))

    assert main(["sync", "--source-root", str(agents_home)]) == 0
    target = prompts_dir / "skill-reviewer-ca.md"
    assert target.exists()

    assert main(["sync", "--source-root", str(agents_home)]) == 0
    assert target.exists()


def test_sync_warns_and_skips_when_tprompt_missing(
    agents_home: Path,
    fake_home: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    install_fixture(agents_home, "tprompt-agent")
    monkeypatch.setenv("PATH", str(fake_home / "nonexistent-bin"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(fake_home / ".config"))

    assert main(["sync", "--source-root", str(agents_home)]) == 0

    target = fake_home / ".config" / "tprompt" / "prompts" / "skill-reviewer-ca.md"
    assert not target.exists()
    captured = capsys.readouterr()
    assert "tprompt not on PATH" in captured.err
    manifest = load_manifest(agents_home)
    assert str(target) not in manifest.paths("tprompt")


def test_first_sync_without_binary_does_not_claim_unwritten_path(
    agents_home: Path, fake_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    install_fixture(agents_home, "tprompt-agent")
    monkeypatch.setenv("PATH", str(fake_home / "nonexistent-bin"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(fake_home / ".config"))

    assert main(["sync", "--source-root", str(agents_home)]) == 0

    target = fake_home / ".config" / "tprompt" / "prompts" / "skill-reviewer-ca.md"
    manifest = load_manifest(agents_home)
    assert str(target) not in manifest.paths("tprompt")

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("hand-authored content\n", encoding="utf-8")

    assert main(["clean", "--source-root", str(agents_home)]) == 0
    assert target.exists()
    assert target.read_text(encoding="utf-8") == "hand-authored content\n"


def test_resync_preserves_tprompt_file_when_binary_disappears(
    agents_home: Path, fake_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    install_fixture(agents_home, "tprompt-agent")
    prompts_dir = _install_fake_tprompt(fake_home, monkeypatch)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(fake_home / ".config"))

    assert main(["sync", "--source-root", str(agents_home)]) == 0
    target = prompts_dir / "skill-reviewer-ca.md"
    assert target.exists()
    original_content = target.read_text(encoding="utf-8")

    monkeypatch.setenv("PATH", str(fake_home / "nonexistent-bin"))

    assert main(["sync", "--source-root", str(agents_home)]) == 0

    assert target.exists()
    assert target.read_text(encoding="utf-8") == original_content
    manifest = load_manifest(agents_home)
    assert str(target) in manifest.paths("tprompt")


def test_sync_rejects_duplicate_tprompt_filename(
    agents_home: Path,
    fake_home: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    write_agent(
        agents_home,
        "first-agent",
        "\n".join(
            [
                "name: first-agent",
                "description: First",
                "tprompt:",
                "  filename: shared-name",
            ]
        ),
    )
    write_agent(
        agents_home,
        "second-agent",
        "\n".join(
            [
                "name: second-agent",
                "description: Second",
                "tprompt:",
                "  filename: shared-name",
            ]
        ),
    )
    _install_fake_tprompt(fake_home, monkeypatch)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(fake_home / ".config"))

    assert main(["sync", "--source-root", str(agents_home)]) == 1
    captured = capsys.readouterr()
    assert "Duplicate tprompt output path" in captured.err


def test_clean_removes_tprompt_files(
    agents_home: Path, fake_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    install_fixture(agents_home, "tprompt-agent")
    prompts_dir = _install_fake_tprompt(fake_home, monkeypatch)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(fake_home / ".config"))

    assert main(["sync", "--source-root", str(agents_home)]) == 0
    target = prompts_dir / "skill-reviewer-ca.md"
    assert target.exists()

    assert main(["clean", "--source-root", str(agents_home)]) == 0
    assert not target.exists()


def test_sync_migrates_v1_manifest_with_notice(
    agents_home: Path,
    fake_home: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    install_fixture(agents_home, "minimal-agent")
    stale_path = fake_home / ".claude" / "agents" / "stale-reviewer.md"
    stale_path.parent.mkdir(parents=True, exist_ok=True)
    stale_path.write_text("stale\n", encoding="utf-8")
    primary = manifest_path(agents_home)
    primary.parent.mkdir(parents=True, exist_ok=True)
    primary.write_text(
        json.dumps(
            {
                "version": 1,
                "generated_files": {
                    "claude": [str(stale_path)],
                    "copilot": [],
                    "codex": [],
                    "cursor": [],
                    "gemini": [],
                    "tprompt": [],
                },
                "linked_targets": {},
            }
        ),
        encoding="utf-8",
    )

    assert main(["sync", "--source-root", str(agents_home)]) == 0
    captured = capsys.readouterr()
    assert captured.err.count("upgrading manifest") == 1
    assert "from v1 to v2" in captured.err
    assert not stale_path.exists()

    persisted = json.loads(primary.read_text(encoding="utf-8"))
    assert persisted["version"] == MANIFEST_VERSION
    assert persisted["generated_files"]["claude"] == [
        {
            "agent": "code-reviewer",
            "path": str(fake_home / ".claude" / "agents" / "code-reviewer.md"),
        }
    ]

    assert main(["sync", "--source-root", str(agents_home)]) == 0
    second = capsys.readouterr()
    assert "upgrading manifest" not in second.err


def test_sync_default_output_byte_stable_regression(
    agents_home: Path, fake_home: Path
) -> None:
    """Pin byte-identical default sync output against snapshot hashes.

    Regenerate with:
        cd /tmp && rm -rf snap && mkdir snap && cd snap && \
            PYTHONPATH=<repo>/src HOME=$PWD python3 -c '...' && \
            shasum -a 256 .claude/agents/code-reviewer.md ...
    """
    import hashlib

    install_fixture(agents_home, "minimal-agent")

    assert main(["sync", "--source-root", str(agents_home)]) == 0

    expected = {
        ".claude/agents/code-reviewer.md":
            "a13749e8dd2bcd36594ff1758388f660491deb32145ec4835a068cbb9d0ef22e",
        ".copilot/agents/code-reviewer.agent.md":
            "24e3bba8ef3f3ae3e2183540e734c51ecf9b09d0e6a4ebea448426fca819a136",
        ".codex/agents/code-reviewer.toml":
            "e08c0c88cd0fb937fd8b07610b61cd5ffe271b3af6ac73b69326fdb51248e5f9",
        ".cursor/agents/code-reviewer.md":
            "1580812c073609748a74d2b396c16e64728e7f575f530109e4ca6407e66a162b",
        ".gemini/agents/code-reviewer.md":
            "cf7c471e5b16ab93a1956ee72c3a09ff0c8edff82f42796258748be03cd30414",
    }
    for relpath, want_hash in expected.items():
        target = fake_home / relpath
        assert target.exists(), f"missing: {relpath}"
        got_hash = hashlib.sha256(target.read_bytes()).hexdigest()
        assert got_hash == want_hash, (
            f"{relpath} content changed: {got_hash[:12]} != {want_hash[:12]}"
        )


def test_clean_rejects_unknown_harness(
    agents_home: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    install_fixture(agents_home, "minimal-agent")

    assert (
        main(
            [
                "clean",
                "--source-root",
                str(agents_home),
                "--harness",
                "hermes",
            ]
        )
        == 1
    )
    err = capsys.readouterr().err
    assert "Unknown harness keyword" in err


def test_clean_rejects_unknown_agent_name(
    agents_home: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    install_fixture(agents_home, "minimal-agent")
    assert main(["sync", "--source-root", str(agents_home)]) == 0

    assert (
        main(
            [
                "clean",
                "--source-root",
                str(agents_home),
                "--agents",
                "ghost",
            ]
        )
        == 1
    )
    err = capsys.readouterr().err
    assert "Unknown agent name" in err


def test_scoped_clean_warns_on_v1_ghost_entries(
    agents_home: Path, fake_home: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    install_fixture(agents_home, "minimal-agent")
    ghost_path = fake_home / ".claude" / "agents" / "ghost.md"
    ghost_path.parent.mkdir(parents=True, exist_ok=True)
    ghost_path.write_text("ghost\n", encoding="utf-8")
    primary = manifest_path(agents_home)
    primary.parent.mkdir(parents=True, exist_ok=True)
    primary.write_text(
        json.dumps(
            {
                "version": 1,
                "generated_files": {"claude": [str(ghost_path)]},
                "linked_targets": {},
            }
        ),
        encoding="utf-8",
    )

    assert (
        main(
            [
                "clean",
                "--source-root",
                str(agents_home),
                "--agents",
                "code-reviewer",
            ]
        )
        == 0
    )

    err = capsys.readouterr().err
    assert "lack agent attribution" in err
    assert ghost_path.exists(), "ghost path with unknown attribution must survive scoped clean"


def test_scoped_clean_harness_preserves_other_harness_files(
    agents_home: Path, fake_home: Path
) -> None:
    install_fixture(agents_home, "minimal-agent")
    assert main(["sync", "--source-root", str(agents_home)]) == 0
    claude_target = fake_home / ".claude" / "agents" / "code-reviewer.md"
    gemini_target = fake_home / ".gemini" / "agents" / "code-reviewer.md"
    assert claude_target.exists() and gemini_target.exists()

    assert (
        main(
            [
                "clean",
                "--source-root",
                str(agents_home),
                "--harness",
                "gemini",
            ]
        )
        == 0
    )

    assert claude_target.exists(), "scoped clean must not remove out-of-scope files"
    assert not gemini_target.exists()
    manifest = load_manifest(agents_home)
    assert str(claude_target) in manifest.paths("claude")
    assert manifest.paths("gemini") == []


def test_scoped_clean_agents_preserves_other_agents(
    agents_home: Path, fake_home: Path
) -> None:
    write_agent(agents_home, "alpha", "name: alpha\ndescription: Alpha\n")
    write_agent(agents_home, "beta", "name: beta\ndescription: Beta\n")
    assert main(["sync", "--source-root", str(agents_home)]) == 0
    alpha_target = fake_home / ".claude" / "agents" / "alpha.md"
    beta_target = fake_home / ".claude" / "agents" / "beta.md"
    assert alpha_target.exists() and beta_target.exists()

    assert (
        main(
            [
                "clean",
                "--source-root",
                str(agents_home),
                "--agents",
                "alpha",
            ]
        )
        == 0
    )

    assert not alpha_target.exists()
    assert beta_target.exists()
    manifest = load_manifest(agents_home)
    assert str(beta_target) in manifest.paths("claude")
    assert str(alpha_target) not in manifest.paths("claude")


def test_scoped_clean_leaves_links_alone(
    agents_home: Path, fake_home: Path
) -> None:
    install_fixture(agents_home, "minimal-agent")
    assert (
        main(["sync", "--source-root", str(agents_home), "--link-canonical"])
        == 0
    )
    canonical_link = fake_home / ".agents" / "agents"
    assert canonical_link.is_symlink()

    assert (
        main(
            [
                "clean",
                "--source-root",
                str(agents_home),
                "--harness",
                "gemini",
            ]
        )
        == 0
    )

    assert canonical_link.is_symlink(), "scoped clean must not prune managed links"


def test_unscoped_clean_still_prunes_links(
    agents_home: Path, fake_home: Path
) -> None:
    install_fixture(agents_home, "minimal-agent")
    assert (
        main(["sync", "--source-root", str(agents_home), "--link-canonical"])
        == 0
    )
    canonical_link = fake_home / ".agents" / "agents"
    assert canonical_link.is_symlink()

    assert main(["clean", "--source-root", str(agents_home)]) == 0

    assert not canonical_link.is_symlink()


def test_scoped_sync_after_v1_migration_dedupes_manifest_entries(
    agents_home: Path, fake_home: Path
) -> None:
    install_fixture(agents_home, "minimal-agent")
    claude_target = fake_home / ".claude" / "agents" / "code-reviewer.md"
    claude_target.parent.mkdir(parents=True, exist_ok=True)
    claude_target.write_text("stale\n", encoding="utf-8")
    primary = manifest_path(agents_home)
    primary.parent.mkdir(parents=True, exist_ok=True)
    primary.write_text(
        json.dumps(
            {
                "version": 1,
                "generated_files": {
                    "claude": [str(claude_target)],
                    "copilot": [],
                    "codex": [],
                    "cursor": [],
                    "gemini": [],
                    "tprompt": [],
                },
                "linked_targets": {},
            }
        ),
        encoding="utf-8",
    )

    assert (
        main(
            [
                "sync",
                "--source-root",
                str(agents_home),
                "--agents",
                "code-reviewer",
            ]
        )
        == 0
    )

    persisted = json.loads(primary.read_text(encoding="utf-8"))
    claude_entries = persisted["generated_files"]["claude"]
    same_path = [e for e in claude_entries if e["path"] == str(claude_target)]
    assert len(same_path) == 1, f"expected single entry, got {claude_entries}"
    assert same_path[0]["agent"] == "code-reviewer"


def test_sync_agents_home_alias_still_routes_to_source_root(
    agents_home: Path, fake_home: Path
) -> None:
    install_fixture(agents_home, "minimal-agent")

    assert main(["sync", "--agents-home", str(agents_home)]) == 0

    assert (fake_home / ".claude" / "agents" / "code-reviewer.md").exists()


def test_sync_rejects_empty_csv_value(
    agents_home: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    install_fixture(agents_home, "minimal-agent")

    with pytest.raises(SystemExit):
        main(["sync", "--source-root", str(agents_home), "--agents", ""])

    err = capsys.readouterr().err
    assert "requires at least one non-empty value" in err


def test_scoped_sync_preserves_out_of_scope_outputs(
    agents_home: Path, fake_home: Path
) -> None:
    install_fixture(agents_home, "minimal-agent")
    assert main(["sync", "--source-root", str(agents_home)]) == 0
    codex_target = fake_home / ".codex" / "agents" / "code-reviewer.toml"
    gemini_target = fake_home / ".gemini" / "agents" / "code-reviewer.md"
    assert codex_target.exists()
    assert gemini_target.exists()

    assert (
        main(
            [
                "sync",
                "--source-root",
                str(agents_home),
                "--harness",
                "claude",
            ]
        )
        == 0
    )

    assert codex_target.exists(), "scoped sync must not delete out-of-scope output"
    assert gemini_target.exists(), "scoped sync must not delete out-of-scope output"
    manifest = load_manifest(agents_home)
    assert str(codex_target) in manifest.paths("codex")
    assert str(gemini_target) in manifest.paths("gemini")


def test_scoped_sync_by_agent_preserves_other_agents_outputs(
    agents_home: Path, fake_home: Path
) -> None:
    write_agent(agents_home, "alpha", "name: alpha\ndescription: Alpha\n")
    write_agent(agents_home, "beta", "name: beta\ndescription: Beta\n")
    assert main(["sync", "--source-root", str(agents_home)]) == 0
    alpha_target = fake_home / ".claude" / "agents" / "alpha.md"
    beta_target = fake_home / ".claude" / "agents" / "beta.md"
    assert alpha_target.exists() and beta_target.exists()

    assert (
        main(
            [
                "sync",
                "--source-root",
                str(agents_home),
                "--agents",
                "alpha",
            ]
        )
        == 0
    )

    assert alpha_target.exists()
    assert beta_target.exists(), "scoped sync must not delete other agents' outputs"


def test_sync_with_include_agents_writes_only_selected(
    agents_home: Path, fake_home: Path
) -> None:
    write_agent(agents_home, "alpha", "name: alpha\ndescription: Alpha\n")
    write_agent(agents_home, "beta", "name: beta\ndescription: Beta\n")

    assert main(["sync", "--source-root", str(agents_home), "--agents", "alpha"]) == 0

    assert (fake_home / ".claude" / "agents" / "alpha.md").exists()
    assert not (fake_home / ".claude" / "agents" / "beta.md").exists()


def test_sync_with_include_harness_writes_only_selected(
    agents_home: Path, fake_home: Path
) -> None:
    install_fixture(agents_home, "minimal-agent")

    assert (
        main(
            [
                "sync",
                "--source-root",
                str(agents_home),
                "--harness",
                "claude,codex",
            ]
        )
        == 0
    )

    assert (fake_home / ".claude" / "agents" / "code-reviewer.md").exists()
    assert (fake_home / ".codex" / "agents" / "code-reviewer.toml").exists()
    assert not (fake_home / ".copilot" / "agents" / "code-reviewer.agent.md").exists()
    assert not (fake_home / ".cursor" / "agents" / "code-reviewer.md").exists()
    assert not (fake_home / ".gemini" / "agents" / "code-reviewer.md").exists()


def test_sync_harness_flag_repeatable(agents_home: Path, fake_home: Path) -> None:
    install_fixture(agents_home, "minimal-agent")

    assert (
        main(
            [
                "sync",
                "--source-root",
                str(agents_home),
                "--harness",
                "claude",
                "--harness",
                "codex",
            ]
        )
        == 0
    )

    assert (fake_home / ".claude" / "agents" / "code-reviewer.md").exists()
    assert (fake_home / ".codex" / "agents" / "code-reviewer.toml").exists()
    assert not (fake_home / ".gemini" / "agents" / "code-reviewer.md").exists()


def test_sync_exclude_harness_skips_target(
    agents_home: Path, fake_home: Path
) -> None:
    install_fixture(agents_home, "minimal-agent")

    assert (
        main(
            [
                "sync",
                "--source-root",
                str(agents_home),
                "--exclude-harness",
                "gemini",
            ]
        )
        == 0
    )

    assert (fake_home / ".claude" / "agents" / "code-reviewer.md").exists()
    assert not (fake_home / ".gemini" / "agents" / "code-reviewer.md").exists()


def test_sync_no_tprompt_forces_skip_even_when_bin_available(
    agents_home: Path, fake_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    install_fixture(agents_home, "tprompt-agent")
    prompts_dir = _install_fake_tprompt(fake_home, monkeypatch)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(fake_home / ".config"))

    assert (
        main(["sync", "--source-root", str(agents_home), "--no-tprompt"]) == 0
    )

    target = prompts_dir / "skill-reviewer-ca.md"
    assert not target.exists()
    manifest = load_manifest(agents_home)
    assert str(target) not in manifest.paths("tprompt")


def test_sync_summary_reports_tprompt_excluded_not_skipped(
    agents_home: Path,
    fake_home: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    install_fixture(agents_home, "tprompt-agent")
    _install_fake_tprompt(fake_home, monkeypatch)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(fake_home / ".config"))

    assert main(["sync", "--source-root", str(agents_home), "--no-tprompt"]) == 0

    captured = capsys.readouterr()
    assert "tprompt written=0 unchanged=0 skipped=0 excluded=1" in captured.out
    assert "tprompt not on PATH" not in captured.err


def test_sync_summary_reports_tprompt_skipped_when_bin_missing(
    agents_home: Path,
    fake_home: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    install_fixture(agents_home, "tprompt-agent")
    monkeypatch.setenv("PATH", str(fake_home / "nonexistent-bin"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(fake_home / ".config"))

    assert main(["sync", "--source-root", str(agents_home)]) == 0

    captured = capsys.readouterr()
    assert "tprompt written=0 unchanged=0 skipped=1 excluded=0" in captured.out
    assert "tprompt not on PATH" in captured.err


def test_sync_summary_reports_tprompt_excluded_when_bin_missing_and_deselected(
    agents_home: Path,
    fake_home: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    install_fixture(agents_home, "tprompt-agent")
    monkeypatch.setenv("PATH", str(fake_home / "nonexistent-bin"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(fake_home / ".config"))

    assert main(["sync", "--source-root", str(agents_home), "--no-tprompt"]) == 0

    captured = capsys.readouterr()
    assert "tprompt written=0 unchanged=0 skipped=0 excluded=1" in captured.out
    assert "tprompt not on PATH" not in captured.err


def test_sync_rejects_unknown_harness_flag(
    agents_home: Path, fake_home: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    install_fixture(agents_home, "minimal-agent")

    assert (
        main(["sync", "--source-root", str(agents_home), "--harness", "hermes"]) == 1
    )
    err = capsys.readouterr().err
    assert "Unknown harness keyword" in err


def test_sync_rejects_unknown_agent_flag(
    agents_home: Path, fake_home: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    install_fixture(agents_home, "minimal-agent")

    assert (
        main(["sync", "--source-root", str(agents_home), "--agents", "nope"]) == 1
    )
    err = capsys.readouterr().err
    assert "Unknown agent name" in err


def test_list_no_filter_prints_default(
    agents_home: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    install_fixture(agents_home, "minimal-agent")

    assert main(["list", "--source-root", str(agents_home)]) == 0
    out = capsys.readouterr().out
    assert "code-reviewer:" in out
    assert "[" not in out  # no harness annotation when no filter


def test_list_with_filter_annotates_harnesses(
    agents_home: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    install_fixture(agents_home, "minimal-agent")

    assert (
        main(
            [
                "list",
                "--source-root",
                str(agents_home),
                "--harness",
                "claude,codex",
            ]
        )
        == 0
    )
    out = capsys.readouterr().out
    assert "code-reviewer:" in out
    assert "[claude, codex]" in out


def test_init_copies_example_when_agent_yaml_absent(agents_home: Path) -> None:
    example_dir = agents_home / "agents" / "needs-init"
    example_dir.mkdir(parents=True)
    (example_dir / "agent.yaml.example").write_text(
        "name: needs-init\ndescription: Needs init\n", encoding="utf-8"
    )
    (example_dir / "instructions.md").write_text("Be useful.\n", encoding="utf-8")

    assert main(["init", "--source-root", str(agents_home)]) == 0

    target = example_dir / "agent.yaml"
    assert target.exists()
    assert target.read_text(encoding="utf-8") == (
        example_dir / "agent.yaml.example"
    ).read_text(encoding="utf-8")


def test_init_is_idempotent(
    agents_home: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    example_dir = agents_home / "agents" / "needs-init"
    example_dir.mkdir(parents=True)
    (example_dir / "agent.yaml.example").write_text(
        "name: needs-init\ndescription: Needs init\n", encoding="utf-8"
    )
    (example_dir / "instructions.md").write_text("Be useful.\n", encoding="utf-8")

    assert main(["init", "--source-root", str(agents_home)]) == 0
    capsys.readouterr()
    assert main(["init", "--source-root", str(agents_home)]) == 0
    out = capsys.readouterr().out
    assert "copied 0, skipped 1" in out


def test_init_never_overwrites_existing_agent_yaml(agents_home: Path) -> None:
    example_dir = agents_home / "agents" / "has-yaml"
    example_dir.mkdir(parents=True)
    (example_dir / "agent.yaml.example").write_text(
        "name: from-example\ndescription: From example\n", encoding="utf-8"
    )
    target = example_dir / "agent.yaml"
    target.write_text(
        "name: from-user\ndescription: Hand-edited\n", encoding="utf-8"
    )
    (example_dir / "instructions.md").write_text("Be useful.\n", encoding="utf-8")

    assert main(["init", "--source-root", str(agents_home)]) == 0

    assert "from-user" in target.read_text(encoding="utf-8")


def test_init_dry_run_does_not_copy(agents_home: Path) -> None:
    example_dir = agents_home / "agents" / "needs-init"
    example_dir.mkdir(parents=True)
    (example_dir / "agent.yaml.example").write_text(
        "name: needs-init\ndescription: Needs init\n", encoding="utf-8"
    )
    (example_dir / "instructions.md").write_text("Be useful.\n", encoding="utf-8")

    assert main(["init", "--source-root", str(agents_home), "--dry-run"]) == 0

    assert not (example_dir / "agent.yaml").exists()


def test_sync_auto_materializes_example(
    agents_home: Path, fake_home: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    example_dir = agents_home / "agents" / "needs-init"
    example_dir.mkdir(parents=True)
    (example_dir / "agent.yaml.example").write_text(
        "name: needs-init\ndescription: Needs init\n", encoding="utf-8"
    )
    (example_dir / "instructions.md").write_text("Be useful.\n", encoding="utf-8")

    assert main(["sync", "--source-root", str(agents_home)]) == 0

    assert (example_dir / "agent.yaml").exists()
    assert (fake_home / ".claude" / "agents" / "needs-init.md").exists()
    assert "created agent.yaml from agent.yaml.example" in capsys.readouterr().err


def test_sync_dry_run_does_not_materialize_example(
    agents_home: Path, fake_home: Path
) -> None:
    example_dir = agents_home / "agents" / "needs-init"
    example_dir.mkdir(parents=True)
    (example_dir / "agent.yaml.example").write_text(
        "name: needs-init\ndescription: Needs init\n", encoding="utf-8"
    )
    (example_dir / "instructions.md").write_text("Be useful.\n", encoding="utf-8")

    assert main(["sync", "--source-root", str(agents_home), "--dry-run"]) == 0

    assert not (example_dir / "agent.yaml").exists()
    assert not (fake_home / ".claude" / "agents" / "needs-init.md").exists()


def test_scoped_clean_dry_run_does_not_materialize_example(
    agents_home: Path,
) -> None:
    example_dir = agents_home / "agents" / "needs-init"
    example_dir.mkdir(parents=True)
    (example_dir / "agent.yaml.example").write_text(
        "name: needs-init\ndescription: Needs init\n", encoding="utf-8"
    )
    (example_dir / "instructions.md").write_text("Be useful.\n", encoding="utf-8")

    assert (
        main(
            [
                "clean",
                "--source-root",
                str(agents_home),
                "--dry-run",
                "--agents",
                "needs-init",
            ]
        )
        == 0
    )

    assert not (example_dir / "agent.yaml").exists()


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
    assert str(copilot_home / "agents" / "code-reviewer.agent.md") in manifest.paths("copilot")

    assert main(["clean", "--source-root", str(agents_home)]) == 0
    assert not (copilot_home / "agents" / "code-reviewer.agent.md").exists()
