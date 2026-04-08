from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
from pathlib import Path


MANIFEST_VERSION = 1
MANIFEST_FILENAME = ".shared-agents-manifest.json"


@dataclass
class Manifest:
    generated_files: dict[str, list[str]]
    linked_targets: dict[str, str] = field(default_factory=dict)

    @classmethod
    def empty(cls) -> "Manifest":
        return cls(
            generated_files={"claude": [], "copilot": [], "codex": [], "gemini": []},
            linked_targets={},
        )


def manifest_path(agents_home: Path) -> Path:
    state_home = os.environ.get("XDG_STATE_HOME")
    if state_home:
        root = Path(state_home).expanduser()
    else:
        root = Path.home() / ".local" / "state"
    return root / "custom_agents" / MANIFEST_FILENAME


def legacy_manifest_path(agents_home: Path) -> Path:
    return agents_home / MANIFEST_FILENAME


def load_manifest(agents_home: Path) -> Manifest:
    seen: set[Path] = set()
    for path in [manifest_path(agents_home), legacy_manifest_path(agents_home)]:
        if path in seen or not path.exists():
            continue
        seen.add(path)
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("version") != MANIFEST_VERSION:
            continue
        generated_files = data.get("generated_files", {})
        return Manifest(
            generated_files={
                "claude": list(generated_files.get("claude", [])),
                "copilot": list(generated_files.get("copilot", [])),
                "codex": list(generated_files.get("codex", [])),
                "gemini": list(generated_files.get("gemini", [])),
            },
            linked_targets={
                str(target): str(source)
                for target, source in (data.get("linked_targets", {}) or {}).items()
                if isinstance(target, str) and isinstance(source, str)
            },
        )
    return Manifest.empty()


def save_manifest(agents_home: Path, manifest: Manifest) -> None:
    path = manifest_path(agents_home)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": MANIFEST_VERSION,
        "generated_files": manifest.generated_files,
        "linked_targets": manifest.linked_targets,
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def remove_legacy_manifest(agents_home: Path) -> None:
    legacy_path = legacy_manifest_path(agents_home)
    primary_path = manifest_path(agents_home)
    if legacy_path == primary_path:
        return
    if legacy_path.exists():
        legacy_path.unlink()
