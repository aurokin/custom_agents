from __future__ import annotations

from typing import Callable


HARNESS_KEYWORDS: tuple[str, ...] = (
    "claude",
    "claude-skills",
    "codex",
    "copilot",
    "cursor",
    "gemini",
    "agent-skills",
    "tprompt",
)

SKILL_HARNESS_KEYWORDS: tuple[str, ...] = ("claude-skills", "agent-skills")


def _always_available() -> bool:
    return True


def _tprompt_available() -> bool:
    # Lazy import: harnesses is imported by schema/manifest; tprompt depends on schema.
    from .generators.tprompt import tprompt_executable

    return tprompt_executable() is not None


AVAILABILITY_PROBES: dict[str, Callable[[], bool]] = {
    "claude": _always_available,
    "claude-skills": _always_available,
    "codex": _always_available,
    "copilot": _always_available,
    "cursor": _always_available,
    "gemini": _always_available,
    "agent-skills": _always_available,
    "tprompt": _tprompt_available,
}


def available_harnesses() -> tuple[str, ...]:
    return tuple(
        keyword for keyword in HARNESS_KEYWORDS if AVAILABILITY_PROBES[keyword]()
    )
