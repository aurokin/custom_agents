from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
import sys
from pathlib import Path

from .harnesses import HARNESS_KEYWORDS


MANIFEST_VERSION = 2
MANIFEST_FILENAME = ".shared-agents-manifest.json"


@dataclass(frozen=True)
class ManifestEntry:
    agent: str
    path: str


@dataclass
class Manifest:
    generated_files: dict[str, list[ManifestEntry]]
    linked_targets: dict[str, str] = field(default_factory=dict)

    @classmethod
    def empty(cls) -> "Manifest":
        return cls(
            generated_files={harness: [] for harness in HARNESS_KEYWORDS},
            linked_targets={},
        )

    def paths(self, harness: str) -> list[str]:
        return [entry.path for entry in self.generated_files.get(harness, [])]


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
        version = data.get("version")
        if version not in (1, 2):
            continue
        generated_raw = data.get("generated_files", {}) or {}
        if version == 1:
            print(
                f"note: upgrading manifest at {path} from v1 to v2",
                file=sys.stderr,
            )
            # Migrated v1 entries have no agent attribution; next sync repopulates it.
            generated_files = {
                harness: [
                    ManifestEntry(agent="", path=str(raw_path))
                    for raw_path in generated_raw.get(harness, [])
                    if isinstance(raw_path, str)
                ]
                for harness in HARNESS_KEYWORDS
            }
        else:
            generated_files = {
                harness: list(_iter_v2_entries(generated_raw.get(harness, [])))
                for harness in HARNESS_KEYWORDS
            }
        return Manifest(
            generated_files=generated_files,
            linked_targets={
                str(target): str(source)
                for target, source in (data.get("linked_targets", {}) or {}).items()
                if isinstance(target, str) and isinstance(source, str)
            },
        )
    return Manifest.empty()


def _iter_v2_entries(raw_entries):
    for entry in raw_entries or []:
        if not isinstance(entry, dict):
            continue
        path = entry.get("path")
        if not isinstance(path, str) or not path:
            continue
        agent = entry.get("agent", "")
        if not isinstance(agent, str):
            agent = ""
        yield ManifestEntry(agent=agent, path=path)


def save_manifest(agents_home: Path, manifest: Manifest) -> None:
    path = manifest_path(agents_home)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": MANIFEST_VERSION,
        "generated_files": {
            harness: [
                {"agent": entry.agent, "path": entry.path}
                for entry in entries
            ]
            for harness, entries in manifest.generated_files.items()
        },
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
