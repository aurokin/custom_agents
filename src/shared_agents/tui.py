from __future__ import annotations

from pathlib import Path
import sys
from types import ModuleType

from .discover import discover_agents
from .harnesses import SKILL_HARNESS_KEYWORDS, available_harnesses
from .main import _cmd_sync, build_sync_preview
from .selection import AgentSelection, CLIFilters, resolve_selection


INSTALL_MESSAGE = "Install TUI support with: python3 -m pip install -e '.[tui]'"


def _load_questionary() -> ModuleType | None:
    try:
        import questionary
    except ImportError:
        return None
    return questionary


def _cmd_tui(source_root: Path) -> int:
    questionary = _load_questionary()
    if questionary is None:
        print(INSTALL_MESSAGE, file=sys.stderr)
        return 1

    agents = discover_agents(source_root, materialize=False)
    available = available_harnesses()
    if not agents:
        print(f"tui: no agents found under {source_root}", file=sys.stderr)
        return 1
    if not available:
        print("tui: no harnesses are available", file=sys.stderr)
        return 1

    agent_names = [agent.name for agent in agents]
    selected_agents = _ask(
        _checkbox_prompt(
            questionary,
            "Select agents",
            choices=[
                _choice(questionary, title=agent.name, value=agent.name, checked=True)
                for agent in agents
            ],
            instruction=(
                "(Use arrows to move, space to select, enter to continue, "
                "q/Esc to abort)"
            ),
        )
    )
    if not selected_agents:
        print("tui: aborted")
        return 1

    selected_harnesses = _ask(
        _checkbox_prompt(
            questionary,
            "Select harnesses",
            choices=_harness_choices(questionary, available),
            instruction=(
                "(Use arrows to move, space to select, enter to continue, "
                "q/Esc to abort)"
            ),
        )
    )
    if not selected_harnesses:
        print("tui: aborted")
        return 1

    filters = CLIFilters(
        include_agents=(
            None
            if set(selected_agents) == set(agent_names)
            else frozenset(selected_agents)
        ),
        exclude_harness=frozenset(set(available) - set(selected_harnesses)),
    )
    selections = resolve_selection(agents, filters, available)
    _print_selection_summary(selections)
    preview = build_sync_preview(source_root, filters)
    _print_preview(preview.write_paths, preview.remove_paths, preview.link_messages)

    confirmed = _ask(questionary.confirm("Apply these changes?", default=False))
    if confirmed is not True:
        print("tui: aborted")
        return 1

    return _cmd_sync(
        source_root,
        dry_run=False,
        link_canonical=False,
        filters=filters,
    )


def _checkbox_prompt(questionary: ModuleType, message: str, **kwargs):
    return _trim_checkbox_indicator_spacing(
        questionary.checkbox(message, **kwargs)
    )


def _choice(questionary: ModuleType, *, title: str, value: str, checked: bool):
    return questionary.Choice(
        title=[("class:text", f" {title}")],
        value=value,
        checked=checked,
    )


def _harness_choices(questionary: ModuleType, available: tuple[str, ...]) -> list:
    skill_harnesses = set(SKILL_HARNESS_KEYWORDS)
    agent_harnesses = sorted(
        harness for harness in available if harness not in skill_harnesses
    )
    skills = sorted(harness for harness in available if harness in skill_harnesses)
    choices = [
        _choice(questionary, title=harness, value=harness, checked=True)
        for harness in agent_harnesses
    ]
    if skills:
        choices.append(questionary.Separator("Skills"))
        choices.extend(
            _choice(questionary, title=harness, value=harness, checked=False)
            for harness in skills
        )
    return choices


def _trim_checkbox_indicator_spacing(prompt):
    control = _find_inquirer_control(getattr(prompt, "application", None))
    if control is None:
        return prompt
    original = control._get_choice_tokens

    def get_choice_tokens():
        return [
            (style, _trim_indicator_token(style, text))
            for style, text in original()
        ]

    control._get_choice_tokens = get_choice_tokens
    control.text = get_choice_tokens
    return prompt


def _find_inquirer_control(root):
    seen: set[int] = set()

    def walk(node):
        if node is None or id(node) in seen:
            return None
        seen.add(id(node))
        if type(node).__name__ == "InquirerControl":
            return node
        for attr in (
            "layout",
            "container",
            "children",
            "body",
            "content",
            "window",
            "control",
        ):
            try:
                child = getattr(node, attr)
            except Exception:
                continue
            if isinstance(child, list):
                for item in child:
                    found = walk(item)
                    if found is not None:
                        return found
            else:
                found = walk(child)
                if found is not None:
                    return found
        return None

    return walk(root)


def _trim_indicator_token(style: str, text: str) -> str:
    if style in {"class:selected", "class:text"} and text in {"● ", "○ "}:
        return text.rstrip()
    return text


def _ask(prompt):
    try:
        return _with_abort_keys(prompt).ask()
    except KeyboardInterrupt:
        return None


def _with_abort_keys(prompt):
    application = getattr(prompt, "application", None)
    bindings = getattr(application, "key_bindings", None)
    if bindings is None or not hasattr(bindings, "add"):
        return prompt
    try:
        from prompt_toolkit.keys import Keys
    except ImportError:
        return prompt

    def abort(event) -> None:
        event.app.exit(exception=KeyboardInterrupt, style="class:aborting")

    try:
        bindings.add("q", eager=True)(abort)
        bindings.add(Keys.Escape, eager=True)(abort)
    except ValueError:
        pass
    return prompt


def _print_selection_summary(selections: list[AgentSelection]) -> None:
    print("Selection:")
    for selection in selections:
        harnesses = ", ".join(sorted(selection.harnesses)) or "<none>"
        print(f"  {selection.agent.name}: {harnesses}")


def _print_preview(
    write_paths: tuple[Path, ...],
    remove_paths: tuple[Path, ...],
    link_messages: tuple[str, ...],
) -> None:
    print("Preview:")
    if write_paths:
        print("  write:")
        for path in write_paths:
            print(f"    {path}")
    else:
        print("  write: <none>")
    if remove_paths:
        print("  remove:")
        for path in remove_paths:
            print(f"    {path}")
        for message in link_messages:
            print(f"    {message}")
    elif link_messages:
        print("  remove:")
        for message in link_messages:
            print(f"    {message}")
    else:
        print("  remove: <none>")
