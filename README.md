# Custom Agents

`custom_agents` is a small Python CLI for generating consumer-native agent
definitions for Claude Code, GitHub Copilot, and Codex from a shared source tree.

## Install

```bash
python3 -m pip install -e '.[dev]'
```

## Canonical Source Layout

```text
<source-root>/
├── AGENTS.md
├── agents/
│   └── code-reviewer/
│       ├── agent.yaml
│       └── instructions.md
└── skills/
```

## Commands

```bash
shared-agents sync
shared-agents sync --link-canonical
shared-agents list
shared-agents validate
shared-agents clean
```

## Outputs

- Claude Code: `~/.claude/agents/<name>.md`
- GitHub Copilot: `~/.copilot/agents/<name>.agent.md`
- Codex: `~/.codex/agents/<name>.toml`
- Optional compatibility link: `<source-root>/agents` symlinked to `~/.agents/agents` only when `--link-canonical` is used

## Notes

- Codex output is generated as standalone discovered role files under
  `~/.codex/agents/`.
- GitHub Copilot output is generated as custom agent markdown files under
  `~/.copilot/agents/` by default, or under `$COPILOT_HOME/agents/` when
  `COPILOT_HOME` is set.
- Claude output is generated as markdown files with YAML frontmatter under
  `~/.claude/agents/`.
- Source root resolution order is: `--source-root`, current working directory
  when it contains `agents/`, `AGENTS_HOME`, then legacy fallback `~/.agents`.
- The canonical `~/.agents/agents` linker is opt-in via `--link-canonical`.
- Cleanup is manifest-based so the tool only removes files it owns.
