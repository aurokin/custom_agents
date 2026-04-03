# Custom Agents

`custom_agents` is a small Python CLI for generating consumer-native agent
definitions for Claude Code and Codex from a shared canonical source under
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
- Codex: `~/.codex/agents/<name>.toml`
- Canonical source: `<agents-home>/agents` symlinked to `~/.agents/agents` when the source lives outside the host's canonical agents home

## Notes

- Codex output is generated as standalone discovered role files under
  `~/.codex/agents/`.
- Claude output is generated as markdown files with YAML frontmatter under
  `~/.claude/agents/`.
- The linker only manages the canonical `~/.agents/agents` symlink and skips
  linking when the source is already `~/.agents`.
- Cleanup is manifest-based so the tool only removes files it owns.
