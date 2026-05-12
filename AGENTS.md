# Agent Instructions

## Package Manager
- Use `python3 -m pip install -e '.[dev]'` for local setup.
- `agent.yaml` is gitignored under `/agents/**/`; the committed
  `agent.yaml.example` sibling is canonical. `discover_agents`
  auto-materializes a missing `agent.yaml` from its `.example` on read,
  and `shared-agents init` does the same copy explicitly. Edit the
  materialized `agent.yaml` for personal harness overrides.

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
  `src/shared_agents/selection.py`. CLI commands and any future TUI must
  route through `resolve_selection`; the scoped-clean path shares the
  CLI-filter precedence via `cli_harness_set`. Don't re-derive the
  `--harness` / `--exclude-harness` / `--no-tprompt` rules anywhere else.
- Keep Codex generation aligned with standalone `~/.codex/agents/*.toml` role files.
- Keep cleanup manifest-based; do not remove unmanaged files by name alone.
- Add or update tests in `tests/` for every schema or generator change.
