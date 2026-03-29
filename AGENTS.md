# Agent Instructions

## Package Manager
- Use `python3 -m pip install -e '.[dev]'` for local setup.

## File-Scoped Commands
| Task | Command |
|------|---------|
| Test file | `pytest -q tests/test_schema.py` |
| Test selection | `pytest -q tests/test_generators.py -k codex` |
| Full test suite | `pytest -q` |

## Key Conventions
- Shared agent logic lives in `src/shared_agents/`.
- Keep Codex generation aligned with standalone `~/.codex/agents/*.toml` role files.
- Keep cleanup manifest-based; do not remove unmanaged files by name alone.
- Add or update tests in `tests/` for every schema or generator change.
