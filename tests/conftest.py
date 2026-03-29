from __future__ import annotations

from pathlib import Path
import shutil

import pytest


@pytest.fixture
def fake_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    return home


@pytest.fixture
def agents_home(tmp_path: Path) -> Path:
    path = tmp_path / "agents-home"
    path.mkdir()
    return path


def install_fixture(agents_home: Path, fixture_name: str, target_name: str | None = None) -> Path:
    fixtures_dir = Path(__file__).parent / "fixtures"
    source = fixtures_dir / fixture_name
    target = agents_home / "agents" / (target_name or fixture_name)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, target)
    return target


def write_agent(
    agents_home: Path,
    relpath: str,
    agent_yaml: str,
    instructions: str = "Be useful.\n",
) -> Path:
    source_dir = agents_home / "agents" / relpath
    source_dir.mkdir(parents=True, exist_ok=True)
    (source_dir / "agent.yaml").write_text(agent_yaml, encoding="utf-8")
    if instructions is not None:
        (source_dir / "instructions.md").write_text(instructions, encoding="utf-8")
    return source_dir
