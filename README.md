# Custom Agents

`custom_agents` is a small Python CLI for generating consumer-native agent
definitions for Claude Code, GitHub Copilot, Codex, and Gemini CLI from a shared source tree.

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
- Gemini CLI: `~/.gemini/agents/<name>.md`
- Optional compatibility link: `<source-root>/agents` symlinked to `~/.agents/agents` only when `--link-canonical` is used

## Notes

- Codex output is generated as standalone discovered role files under
  `~/.codex/agents/`.
- Gemini CLI output is generated as local markdown subagent files under
  `~/.gemini/agents/`.
- This generator omits Gemini `tools` unless `gemini.tools` is set explicitly
  in `agent.yaml`. Use `gemini.tools: []` to lock an agent down. Current
  Gemini CLI docs describe omitted `tools` as inheriting the parent session
  toolset.
- This generator omits Gemini `model` unless `gemini.model` is set explicitly
  in `agent.yaml`. Current Gemini CLI docs describe omitted `model` as
  inheriting the parent session model. This is Gemini-specific and does not
  use the shared pinned/floating default-model strategy.
- Gemini subagents are enabled by default in current Gemini CLI docs. Set
  `experimental.enableAgents` to `false` in `~/.gemini/settings.json` to
  disable them.
- Model and reasoning/effort settings default to shared pinned defaults when
  omitted. Set `defaults.model_strategy: floating` in `agent.yaml` to omit
  those generated fields and let the downstream tool select defaults instead.
- GitHub Copilot output is generated as custom agent markdown files under
  `~/.copilot/agents/` by default, or under `$COPILOT_HOME/agents/` when
  `COPILOT_HOME` is set.
- Claude output is generated as markdown files with YAML frontmatter under
  `~/.claude/agents/`.
- Source root resolution order is: `--source-root`, current working directory
  when it contains `agents/`, `AGENTS_HOME`, then legacy fallback `~/.agents`.
- The canonical `~/.agents/agents` linker is opt-in via `--link-canonical`.
- Cleanup is manifest-based so the tool only removes files it owns.
