from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .harnesses import HARNESS_KEYWORDS
from .schema import AgentDefinition


@dataclass(frozen=True)
class CLIFilters:
    include_agents: frozenset[str] | None = None
    exclude_agents: frozenset[str] = frozenset()
    include_harness: frozenset[str] | None = None
    exclude_harness: frozenset[str] = frozenset()
    no_tprompt: bool = False

    def is_active(self) -> bool:
        return (
            self.include_agents is not None
            or bool(self.exclude_agents)
            or self.include_harness is not None
            or bool(self.exclude_harness)
            or self.no_tprompt
        )


@dataclass(frozen=True)
class AgentSelection:
    agent: AgentDefinition
    harnesses: frozenset[str]


def resolve_selection(
    agents: list[AgentDefinition],
    filters: CLIFilters,
    available: Iterable[str],
) -> list[AgentSelection]:
    _validate_harness_keywords(filters.include_harness, "harness filter include")
    _validate_harness_keywords(filters.exclude_harness, "harness filter exclude")

    available_set = frozenset(available)
    _validate_harness_keywords(available_set, "available harness set")

    agent_names = {agent.name for agent in agents}
    _validate_agent_names(filters.include_agents, agent_names)
    _validate_agent_names(filters.exclude_agents, agent_names)

    result: list[AgentSelection] = []
    for agent in agents:
        if filters.include_agents is not None and agent.name not in filters.include_agents:
            continue
        if agent.name in filters.exclude_agents:
            continue

        base = set(available_set)
        if filters.include_harness is not None:
            base &= filters.include_harness
        base -= filters.exclude_harness

        if agent.harness.include is not None:
            base &= set(agent.harness.include)
        if agent.harness.exclude:
            base -= set(agent.harness.exclude)

        if filters.no_tprompt:
            base.discard("tprompt")
        if "tprompt" in base and not agent.tprompt.enabled:
            base.discard("tprompt")

        result.append(AgentSelection(agent=agent, harnesses=frozenset(base)))
    return result


def _validate_harness_keywords(
    keywords: Iterable[str] | None, context: str
) -> None:
    if keywords is None:
        return
    unknown = sorted(set(keywords) - set(HARNESS_KEYWORDS))
    if unknown:
        allowed = ", ".join(HARNESS_KEYWORDS)
        raise ValueError(
            f"Unknown harness keyword(s) in {context}: {', '.join(unknown)} (allowed: {allowed})"
        )


def _validate_agent_names(
    requested: Iterable[str] | None, known: set[str]
) -> None:
    if requested is None:
        return
    unknown = sorted(set(requested) - known)
    if unknown:
        raise ValueError(
            f"Unknown agent name(s): {', '.join(unknown)}"
        )
