from __future__ import annotations

import pytest

from shared_agents import harnesses


def test_harness_keywords_contents() -> None:
    assert harnesses.HARNESS_KEYWORDS == (
        "claude",
        "claude-skills",
        "codex",
        "copilot",
        "cursor",
        "gemini",
        "agent-skills",
        "tprompt",
    )


def test_available_harnesses_includes_always_on(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(harnesses.AVAILABILITY_PROBES, "tprompt", lambda: False)

    available = harnesses.available_harnesses()

    assert available == (
        "claude",
        "claude-skills",
        "codex",
        "copilot",
        "cursor",
        "gemini",
        "agent-skills",
    )


def test_available_harnesses_includes_tprompt_when_probe_passes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(harnesses.AVAILABILITY_PROBES, "tprompt", lambda: True)

    available = harnesses.available_harnesses()

    assert "tprompt" in available
    assert available == tuple(
        keyword for keyword in harnesses.HARNESS_KEYWORDS if keyword in available
    )


def test_availability_probes_cover_all_keywords() -> None:
    assert set(harnesses.AVAILABILITY_PROBES) == set(harnesses.HARNESS_KEYWORDS)
