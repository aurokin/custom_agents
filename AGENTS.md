# Agent Instructions

## Package Manager
- Use `python3 -m pip install -e '.[dev]'` for local setup.
- Run `shared-agents init` once after install to materialize `agent.yaml`
  from the committed `agent.yaml.example` files. `agent.yaml` is
  gitignored under `/agents/**/`; the `.example` is the canonical source.

## File-Scoped Commands
| Task | Command |
|------|---------|
| Test file | `pytest -q tests/test_schema.py` |
| Test selection | `pytest -q tests/test_generators.py -k codex` |
| Full test suite | `pytest -q` |

## Key Conventions
- Shared agent logic lives in `src/shared_agents/`.
- Harness keywords live in `src/shared_agents/harnesses.py`; treat that
  tuple as the single source of truth and extend it when adding a new
  target consumer.
- Selection logic (CLI filters + per-agent `harness:` schema) lives in
  `src/shared_agents/selection.py`. CLI commands, scoped clean, and any
  future TUI must route through `resolve_selection` instead of
  duplicating the precedence rules.
- Keep Codex generation aligned with standalone `~/.codex/agents/*.toml` role files.
- Keep cleanup manifest-based; do not remove unmanaged files by name alone.
- Add or update tests in `tests/` for every schema or generator change.
