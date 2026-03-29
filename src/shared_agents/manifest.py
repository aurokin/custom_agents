from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path


MANIFEST_VERSION = 1
MANIFEST_FILENAME = ".shared-agents-manifest.json"


@dataclass
class Manifest:
    generated_files: dict[str, list[str]]

    @classmethod
    def empty(cls) -> "Manifest":
        return cls(generated_files={"claude": [], "codex": []})


def manifest_path(agents_home: Path) -> Path:
    return agents_home / MANIFEST_FILENAME


def load_manifest(agents_home: Path) -> Manifest:
    path = manifest_path(agents_home)
    if not path.exists():
        return Manifest.empty()
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("version") != MANIFEST_VERSION:
        return Manifest.empty()
    generated_files = data.get("generated_files", {})
    return Manifest(
        generated_files={
            "claude": list(generated_files.get("claude", [])),
            "codex": list(generated_files.get("codex", [])),
        }
    )


def save_manifest(agents_home: Path, manifest: Manifest) -> None:
    path = manifest_path(agents_home)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": MANIFEST_VERSION,
        "generated_files": manifest.generated_files,
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

