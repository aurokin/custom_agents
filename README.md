# Custom Subagents

`custom_subagents` is a small Python CLI for generating consumer-native agent
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
- Shared docs: `~/.agents/AGENTS.md` symlinked into Claude/Codex
- Shared skills: `~/.agents/skills/*` symlinked into Claude/Codex

## Notes

- Codex output is generated as standalone discovered role files under
  `~/.codex/agents/`.
- Claude output is generated as markdown files with YAML frontmatter under
  `~/.claude/agents/`.
- Cleanup is manifest-based so the tool only removes files it owns.
