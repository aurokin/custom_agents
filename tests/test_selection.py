from __future__ import annotations

from pathlib import Path

import pytest

from shared_agents.discover import discover_agents
from shared_agents.harnesses import HARNESS_KEYWORDS
from shared_agents.selection import AgentSelection, CLIFilters, resolve_selection
from tests.conftest import write_agent


def _all_harnesses() -> tuple[str, ...]:
    return HARNESS_KEYWORDS


def _make_agent(agents_home: Path, name: str, yaml_extra: str = "") -> None:
    body = f"name: {name}\ndescription: {name} agent\n"
    if yaml_extra:
        body += yaml_extra
    write_agent(agents_home, name, body)


def test_resolve_selection_default_returns_all(agents_home: Path) -> None:
    _make_agent(agents_home, "alpha")
    _make_agent(agents_home, "beta")
    agents = discover_agents(agents_home)

    selections = resolve_selection(agents, CLIFilters(), _all_harnesses())

    assert [s.agent.name for s in selections] == ["alpha", "beta"]
    expected = frozenset({"claude", "codex", "copilot", "cursor", "gemini"})
    for selection in selections:
        assert selection.harnesses == expected


def test_resolve_selection_include_agents_filters_list(agents_home: Path) -> None:
    _make_agent(agents_home, "alpha")
    _make_agent(agents_home, "beta")
    _make_agent(agents_home, "gamma")
    agents = discover_agents(agents_home)

    selections = resolve_selection(
        agents,
        CLIFilters(include_agents=frozenset({"alpha", "gamma"})),
        _all_harnesses(),
    )

    assert [s.agent.name for s in selections] == ["alpha", "gamma"]


def test_resolve_selection_exclude_agents_filters_list(agents_home: Path) -> None:
    _make_agent(agents_home, "alpha")
    _make_agent(agents_home, "beta")
    agents = discover_agents(agents_home)

    selections = resolve_selection(
        agents,
        CLIFilters(exclude_agents=frozenset({"beta"})),
        _all_harnesses(),
    )

    assert [s.agent.name for s in selections] == ["alpha"]


def test_resolve_selection_cli_harness_include_narrows(agents_home: Path) -> None:
    _make_agent(agents_home, "alpha")
    agents = discover_agents(agents_home)

    selections = resolve_selection(
        agents,
        CLIFilters(include_harness=frozenset({"claude", "codex"})),
        _all_harnesses(),
    )

    assert selections[0].harnesses == frozenset({"claude", "codex"})


def test_resolve_selection_cli_harness_exclude_removes(agents_home: Path) -> None:
    _make_agent(agents_home, "alpha")
    agents = discover_agents(agents_home)

    selections = resolve_selection(
        agents,
        CLIFilters(exclude_harness=frozenset({"gemini"})),
        _all_harnesses(),
    )

    assert "gemini" not in selections[0].harnesses
    assert "claude" in selections[0].harnesses


def test_resolve_selection_schema_include_narrows(agents_home: Path) -> None:
    _make_agent(
        agents_home,
        "alpha",
        "harness:\n  include: [claude, codex]\n",
    )
    agents = discover_agents(agents_home)

    selections = resolve_selection(agents, CLIFilters(), _all_harnesses())

    assert selections[0].harnesses == frozenset({"claude", "codex"})


def test_resolve_selection_schema_exclude_removes(agents_home: Path) -> None:
    _make_agent(
        agents_home,
        "alpha",
        "harness:\n  exclude: [gemini, cursor]\n",
    )
    agents = discover_agents(agents_home)

    selections = resolve_selection(agents, CLIFilters(), _all_harnesses())

    assert "gemini" not in selections[0].harnesses
    assert "cursor" not in selections[0].harnesses
    assert "claude" in selections[0].harnesses


def test_resolve_selection_cli_intersects_schema(agents_home: Path) -> None:
    _make_agent(
        agents_home,
        "alpha",
        "harness:\n  include: [claude, codex, gemini]\n",
    )
    agents = discover_agents(agents_home)

    selections = resolve_selection(
        agents,
        CLIFilters(include_harness=frozenset({"claude", "gemini", "cursor"})),
        _all_harnesses(),
    )

    assert selections[0].harnesses == frozenset({"claude", "gemini"})


def test_resolve_selection_no_tprompt_overrides_schema_include(
    agents_home: Path,
) -> None:
    _make_agent(
        agents_home,
        "alpha",
        "\n".join(
            [
                "harness:",
                "  include: [claude, tprompt]",
                "tprompt:",
                "  title: Alpha",
                "",
            ]
        ),
    )
    agents = discover_agents(agents_home)

    selections = resolve_selection(
        agents,
        CLIFilters(no_tprompt=True),
        _all_harnesses(),
    )

    assert "tprompt" not in selections[0].harnesses
    assert "claude" in selections[0].harnesses


def test_resolve_selection_drops_tprompt_when_agent_did_not_opt_in(
    agents_home: Path,
) -> None:
    _make_agent(agents_home, "alpha")
    agents = discover_agents(agents_home)

    selections = resolve_selection(agents, CLIFilters(), _all_harnesses())

    assert "tprompt" not in selections[0].harnesses


def test_resolve_selection_keeps_tprompt_when_opted_in_and_available(
    agents_home: Path,
) -> None:
    _make_agent(
        agents_home,
        "alpha",
        "tprompt:\n  title: Alpha\n",
    )
    agents = discover_agents(agents_home)

    selections = resolve_selection(agents, CLIFilters(), _all_harnesses())

    assert "tprompt" in selections[0].harnesses


def test_resolve_selection_drops_tprompt_when_not_in_available(
    agents_home: Path,
) -> None:
    _make_agent(
        agents_home,
        "alpha",
        "tprompt:\n  title: Alpha\n",
    )
    agents = discover_agents(agents_home)
    available = tuple(h for h in HARNESS_KEYWORDS if h != "tprompt")

    selections = resolve_selection(agents, CLIFilters(), available)

    assert "tprompt" not in selections[0].harnesses


def test_resolve_selection_rejects_unknown_agent_name(agents_home: Path) -> None:
    _make_agent(agents_home, "alpha")
    agents = discover_agents(agents_home)

    with pytest.raises(ValueError, match="Unknown agent name"):
        resolve_selection(
            agents,
            CLIFilters(include_agents=frozenset({"nope"})),
            _all_harnesses(),
        )


def test_resolve_selection_rejects_unknown_exclude_agent(agents_home: Path) -> None:
    _make_agent(agents_home, "alpha")
    agents = discover_agents(agents_home)

    with pytest.raises(ValueError, match="Unknown agent name"):
        resolve_selection(
            agents,
            CLIFilters(exclude_agents=frozenset({"nope"})),
            _all_harnesses(),
        )


def test_resolve_selection_rejects_unknown_harness_keyword(
    agents_home: Path,
) -> None:
    _make_agent(agents_home, "alpha")
    agents = discover_agents(agents_home)

    with pytest.raises(ValueError, match="Unknown harness keyword"):
        resolve_selection(
            agents,
            CLIFilters(include_harness=frozenset({"hermes"})),
            _all_harnesses(),
        )


def test_resolve_selection_rejects_unknown_harness_in_available(
    agents_home: Path,
) -> None:
    _make_agent(agents_home, "alpha")
    agents = discover_agents(agents_home)

    with pytest.raises(ValueError, match="Unknown harness keyword"):
        resolve_selection(agents, CLIFilters(), ("hermes",))


def test_resolve_selection_schema_exclude_drops_into_empty_set(
    agents_home: Path,
) -> None:
    _make_agent(
        agents_home,
        "alpha",
        "harness:\n  exclude: [claude, codex, copilot, cursor, gemini]\n",
    )
    agents = discover_agents(agents_home)

    selections = resolve_selection(agents, CLIFilters(), _all_harnesses())

    assert selections[0].harnesses == frozenset()
