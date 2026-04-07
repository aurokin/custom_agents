# Custom Agents

`custom_agents` is a small Python CLI for generating consumer-native agent
definitions for Claude Code, GitHub Copilot, and Codex from a shared canonical source under
`~/.agents/`.

## Install

```bash
python3 -m pip install -e '.[dev]'
```

## Canonical Source Layout

```text
~/.agents/
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
shared-agents list
shared-agents validate
shared-agents clean
```

## Outputs

- Claude Code: `~/.claude/agents/<name>.md`
- GitHub Copilot: `~/.copilot/agents/<name>.agent.md`
- Codex: `~/.codex/agents/<name>.toml`
- Canonical source: `<agents-home>/agents` symlinked to `~/.agents/agents` when the source lives outside the host's canonical agents home

## Notes

- Codex output is generated as standalone discovered role files under
  `~/.codex/agents/`.
- GitHub Copilot output is generated as custom agent markdown files under
  `~/.copilot/agents/` by default, or under `$COPILOT_HOME/agents/` when
  `COPILOT_HOME` is set.
- Claude output is generated as markdown files with YAML frontmatter under
  `~/.claude/agents/`.
- The linker only manages the canonical `~/.agents/agents` symlink and skips
  linking when the source is already `~/.agents`.
- Cleanup is manifest-based so the tool only removes files it owns.
