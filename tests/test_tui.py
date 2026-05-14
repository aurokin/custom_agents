from __future__ import annotations

import os
from pathlib import Path
import stat

import pytest

from shared_agents import harnesses
from shared_agents.main import main
from shared_agents.manifest import load_manifest, manifest_path
from shared_agents.tui import _checkbox_prompt, _cmd_tui, _choice, _find_inquirer_control
from tests.conftest import write_agent


class FakeChoice:
    def __init__(self, *, title, value: str, checked: bool = False) -> None:
        self.title = title
        self.value = value
        self.checked = checked


class FakeSeparator:
    def __init__(self, line: str | None = None) -> None:
        self.line = line


class FakePrompt:
    def __init__(self, answer):
        self.answer = answer

    def ask(self):
        return self.answer


class FakeQuestionary:
    Choice = FakeChoice
    Separator = FakeSeparator

    def __init__(self, answers: list) -> None:
        self.answers = list(answers)
        self.checkbox_calls: list[dict] = []

    def checkbox(self, message: str, choices: list[FakeChoice], **_kwargs) -> FakePrompt:
        self.checkbox_calls.append({"message": message, "choices": choices})
        return FakePrompt(self.answers.pop(0))

    def confirm(self, message: str, default: bool = False) -> FakePrompt:
        return FakePrompt(self.answers.pop(0))


def _write_pair(root: Path) -> None:
    write_agent(root, "alpha", "name: alpha\ndescription: Alpha\n")
    write_agent(root, "beta", "name: beta\ndescription: Beta\n")


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


def test_tui_missing_extra_exits_nonzero(
    agents_home: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    write_agent(agents_home, "alpha", "name: alpha\ndescription: Alpha\n")
    import shared_agents.tui as tui

    monkeypatch.setattr(tui, "_load_questionary", lambda: None)

    assert main(["tui", "--source-root", str(agents_home)]) == 1

    assert "python3 -m pip install -e '.[tui]'" in capsys.readouterr().err


def test_tui_confirmed_selection_matches_cli_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cli_root = tmp_path / "cli-root"
    tui_root = tmp_path / "tui-root"
    cli_root.mkdir()
    tui_root.mkdir()
    _write_pair(cli_root)
    _write_pair(tui_root)

    cli_home = tmp_path / "cli-home"
    tui_home = tmp_path / "tui-home"
    monkeypatch.setenv("HOME", str(cli_home))
    assert (
        main(
            [
                "sync",
                "--source-root",
                str(cli_root),
                "--agents",
                "alpha",
                "--harness",
                "claude,codex",
            ]
        )
        == 0
    )

    fake = FakeQuestionary([["alpha"], ["claude", "codex"], True])
    import shared_agents.tui as tui

    monkeypatch.setattr(tui, "_load_questionary", lambda: fake)
    monkeypatch.setenv("HOME", str(tui_home))

    assert _cmd_tui(tui_root) == 0

    assert (
        cli_home / ".claude" / "agents" / "alpha.md"
    ).read_bytes() == (tui_home / ".claude" / "agents" / "alpha.md").read_bytes()
    assert (
        cli_home / ".codex" / "agents" / "alpha.toml"
    ).read_bytes() == (tui_home / ".codex" / "agents" / "alpha.toml").read_bytes()
    assert not (tui_home / ".claude" / "agents" / "beta.md").exists()


def test_tui_abort_at_prompt_writes_nothing(
    agents_home: Path,
    fake_home: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    write_agent(agents_home, "alpha", "name: alpha\ndescription: Alpha\n")
    fake = FakeQuestionary([None])
    import shared_agents.tui as tui

    monkeypatch.setattr(tui, "_load_questionary", lambda: fake)

    assert _cmd_tui(agents_home) == 1

    assert not (fake_home / ".claude").exists()
    assert not manifest_path(agents_home).exists()


def test_tui_abort_at_confirm_writes_nothing(
    agents_home: Path,
    fake_home: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    write_agent(agents_home, "alpha", "name: alpha\ndescription: Alpha\n")
    fake = FakeQuestionary([["alpha"], ["claude"], False])
    import shared_agents.tui as tui

    monkeypatch.setattr(tui, "_load_questionary", lambda: fake)

    assert _cmd_tui(agents_home) == 1

    out = capsys.readouterr().out
    assert "Preview:" in out
    assert str(fake_home / ".claude" / "agents" / "alpha.md") in out
    assert not (fake_home / ".claude").exists()
    assert not manifest_path(agents_home).exists()


def test_tui_can_disable_tprompt_when_available(
    agents_home: Path,
    fake_home: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    write_agent(
        agents_home,
        "alpha",
        "name: alpha\ndescription: Alpha\ntprompt:\n  title: Alpha\n",
    )
    fake = FakeQuestionary([["alpha"], ["claude"], True])
    import shared_agents.main as main_module
    import shared_agents.tui as tui

    available = tuple(harnesses.HARNESS_KEYWORDS)
    monkeypatch.setattr(tui, "_load_questionary", lambda: fake)
    monkeypatch.setattr(tui, "available_harnesses", lambda: available)
    monkeypatch.setattr(main_module, "available_harnesses", lambda: available)

    assert _cmd_tui(agents_home) == 0

    harness_choices = fake.checkbox_calls[1]["choices"]
    assert "tprompt" in [
        choice.value for choice in harness_choices if isinstance(choice, FakeChoice)
    ]
    assert (fake_home / ".claude" / "agents" / "alpha.md").exists()
    tprompt_target = fake_home / ".config" / "tprompt" / "prompts" / "alpha-ca.md"
    assert not tprompt_target.exists()
    assert str(tprompt_target) not in load_manifest(agents_home).paths("tprompt")


def test_tui_preview_includes_managed_link_removal(
    agents_home: Path,
    fake_home: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    write_agent(agents_home, "alpha", "name: alpha\ndescription: Alpha\n")
    assert (
        main(["sync", "--source-root", str(agents_home), "--link-canonical"]) == 0
    )
    canonical_link = fake_home / ".agents" / "agents"
    assert canonical_link.is_symlink()

    fake = FakeQuestionary([["alpha"], ["claude"], False])
    import shared_agents.tui as tui

    monkeypatch.setattr(tui, "_load_questionary", lambda: fake)

    assert _cmd_tui(agents_home) == 1

    out = capsys.readouterr().out
    assert "remove managed" in out
    assert str(canonical_link) in out
    assert canonical_link.is_symlink()


def test_tui_preview_includes_stale_tprompt_after_export_change(
    agents_home: Path,
    fake_home: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source_dir = write_agent(
        agents_home,
        "reviewer",
        "\n".join(
            [
                "name: reviewer",
                "description: Reviewer",
                "tprompt:",
                "  filename: reviewer-prompt",
            ]
        ),
    )
    prompts_dir = _install_fake_tprompt(fake_home, monkeypatch)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(fake_home / ".config"))
    assert main(["sync", "--source-root", str(agents_home)]) == 0
    target = prompts_dir / "reviewer-prompt-ca.md"
    assert target.exists()

    (source_dir / "agent.yaml").write_text(
        "\n".join(
            [
                "name: reviewer",
                "description: Reviewer",
                "export: skill",
                "tprompt:",
                "  filename: reviewer-prompt",
            ]
        ),
        encoding="utf-8",
    )

    fake = FakeQuestionary([["reviewer"], ["tprompt"], False])
    import shared_agents.tui as tui

    monkeypatch.setattr(tui, "_load_questionary", lambda: fake)

    assert _cmd_tui(agents_home) == 1

    out = capsys.readouterr().out
    assert "remove:" in out
    assert str(target) in out
    assert target.exists()


def test_tui_harness_choices_group_and_sort_skills(
    agents_home: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    write_agent(agents_home, "alpha", "name: alpha\ndescription: Alpha\n")
    available = (
        "tprompt",
        "agent-skills",
        "gemini",
        "claude",
        "hermes-skills",
        "codex",
        "claude-skills",
    )
    fake = FakeQuestionary([["alpha"], ["claude"], False])
    import shared_agents.tui as tui

    monkeypatch.setattr(tui, "_load_questionary", lambda: fake)
    monkeypatch.setattr(tui, "available_harnesses", lambda: available)

    assert _cmd_tui(agents_home) == 1

    choices = fake.checkbox_calls[1]["choices"]
    agent_choices = choices[:4]
    separator = choices[4]
    skill_choices = choices[5:]
    assert [choice.value for choice in agent_choices] == [
        "claude",
        "codex",
        "gemini",
        "tprompt",
    ]
    assert isinstance(separator, FakeSeparator)
    assert separator.line == "Skills"
    assert [choice.value for choice in skill_choices] == [
        "agent-skills",
        "claude-skills",
        "hermes-skills",
    ]
    assert all(choice.checked for choice in agent_choices)
    assert not any(choice.checked for choice in skill_choices)


def test_checkbox_prompt_trims_indicator_spacing() -> None:
    import questionary

    prompt = _checkbox_prompt(
        questionary,
        "Select",
        choices=[
            _choice(questionary, title="alpha", value="alpha", checked=True),
            _choice(questionary, title="beta", value="beta", checked=False),
        ],
    )
    control = _find_inquirer_control(prompt.application)

    assert control is not None
    tokens = control._get_choice_tokens()
    assert ("class:selected", "●") in tokens
    assert ("class:selected", "● ") not in tokens
    assert ("class:text", "○") in tokens
    assert ("class:text", "○ ") not in tokens
    assert ("class:text", " alpha") in tokens
    assert ("class:text", " beta") in tokens


def test_confirm_prompt_abort_key_hook_is_optional() -> None:
    import questionary
    import shared_agents.tui as tui

    prompt = questionary.confirm("Apply these changes?", default=False)

    assert tui._with_abort_keys(prompt) is prompt


def test_tui_default_harness_selection_keeps_unfiltered_cleanup(
    agents_home: Path,
    fake_home: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source_dir = write_agent(
        agents_home,
        "reviewer",
        "\n".join(
            [
                "name: reviewer",
                "description: Reviewer",
                "tprompt:",
                "  filename: reviewer-prompt",
            ]
        ),
    )
    prompts_dir = _install_fake_tprompt(fake_home, monkeypatch)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(fake_home / ".config"))
    assert main(["sync", "--source-root", str(agents_home)]) == 0
    target = prompts_dir / "reviewer-prompt-ca.md"
    assert target.exists()

    (source_dir / "agent.yaml").write_text(
        "\n".join(
            [
                "name: reviewer",
                "description: Reviewer",
                "export: skill",
                "tprompt:",
                "  filename: reviewer-prompt",
            ]
        ),
        encoding="utf-8",
    )

    import shared_agents.main as main_module
    import shared_agents.tui as tui

    visible_harnesses = tuple(
        harness for harness in harnesses.HARNESS_KEYWORDS if harness != "tprompt"
    )
    monkeypatch.setattr(tui, "available_harnesses", lambda: visible_harnesses)
    monkeypatch.setattr(main_module, "available_harnesses", lambda: visible_harnesses)
    fake = FakeQuestionary([["reviewer"], list(visible_harnesses), False])
    monkeypatch.setattr(tui, "_load_questionary", lambda: fake)

    assert _cmd_tui(agents_home) == 1

    out = capsys.readouterr().out
    assert "remove:" in out
    assert str(target) in out
    assert target.exists()
