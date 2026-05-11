# Custom Agents

`custom_agents` is a small Python CLI for generating consumer-native agent
definitions for Claude Code, GitHub Copilot, Codex, Cursor, and Gemini CLI from a shared source tree.

## Install

```bash
python3 -m pip install -e '.[dev]'
shared-agents init
```

`shared-agents init` materializes each agent's `agent.yaml.example` into a
sibling `agent.yaml`. The `.example` files are the canonical committed
source; the materialized `agent.yaml` is gitignored so personal harness
overrides stay local. `init` is idempotent — re-running it skips any
`agent.yaml` that already exists, so local edits are never clobbered.

## Canonical Source Layout

```text
<source-root>/
├── AGENTS.md
├── agents/
│   └── code-reviewer/
│       ├── agent.yaml.example   # canonical, committed
│       ├── agent.yaml            # gitignored, created by `shared-agents init`
│       └── instructions.md
└── skills/
```

## Commands

```bash
shared-agents init                              # bootstrap agent.yaml from .example
shared-agents sync                              # all agents × all available harnesses
shared-agents sync --link-canonical
shared-agents list
shared-agents validate
shared-agents clean
```

### Selection flags (on `sync`, `list`, `clean`)

All four list flags accept comma-separated values and may also be
repeated; the values accumulate.

| Flag | Effect |
|------|--------|
| `--agents A,B` | Only operate on the listed agents. |
| `--exclude-agents A,B` | Skip the listed agents. |
| `--harness H,...` | Only operate on the listed harnesses. Keywords: `claude`, `codex`, `copilot`, `cursor`, `gemini`, `tprompt`. |
| `--exclude-harness H,...` | Skip the listed harnesses. |
| `--no-tprompt` | Exclude tprompt entirely. On `sync` this means don't write tprompt outputs; on `clean` it means leave existing tprompt entries in place. |

Examples:

```bash
shared-agents sync --agents code-reviewer       # one agent, all harnesses
shared-agents sync --harness claude,codex       # all agents, two harnesses
shared-agents sync --exclude-harness gemini     # skip gemini for everyone
shared-agents sync --agents code-reviewer --harness claude
shared-agents clean --agents code-reviewer      # remove only this agent's outputs
shared-agents clean --harness gemini            # remove only gemini outputs
```

### Per-agent harness preferences

Each `agent.yaml` may declare a top-level `harness:` block with either
`include` *or* `exclude` (setting both is a schema error):

```yaml
name: code-reviewer
harness:
  exclude: [tprompt, gemini]
  # or:
  # include: [claude, codex]
```

Because `agent.yaml` is gitignored, this is the right place to encode
personal harness preferences for an agent without changing the canonical
`.example` definition.

### Selection precedence

The final per-agent harness set is:

```
base = available harnesses (excludes tprompt when its binary is not on PATH)
if --harness given:           base ∩= --harness
base −= --exclude-harness
if agent has harness.include: base ∩= agent.harness.include
base −= agent.harness.exclude
if --no-tprompt:              base.discard("tprompt")
if agent did not opt in:      base.discard("tprompt")
```

Scoped operations only touch the in-scope subset of the manifest:

* `sync --harness claude` leaves codex/copilot/cursor/gemini files and
  manifest entries untouched.
* `clean --agents X` removes only X's outputs and preserves every other
  agent's manifest entries and on-disk files.
* The canonical `~/.agents/agents` symlink is only pruned by an unscoped
  `clean`.

## Outputs

- Claude Code: `~/.claude/agents/<name>.md`
- GitHub Copilot: `~/.copilot/agents/<name>.agent.md`
- Codex: `~/.codex/agents/<name>.toml`
- Cursor: `~/.cursor/agents/<name>.md`
- Gemini CLI: `~/.gemini/agents/<name>.md`
- Optional compatibility link: `<source-root>/agents` symlinked to `~/.agents/agents` only when `--link-canonical` is used

## Manifest

State is tracked in `~/.local/state/custom_agents/.shared-agents-manifest.json`
(or `$XDG_STATE_HOME/custom_agents/...`). Cleanup is manifest-based so the
tool only removes files it owns. The manifest is v2: each entry is
`{agent, path}` per harness. v1 manifests are auto-migrated on first load
with a one-time stderr line of the form
`note: upgrading manifest at <path> from v1 to v2`.

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
- Cursor output is generated as markdown subagent files under
  `~/.cursor/agents/`. This generator omits Cursor `model` unless
  `cursor.model` is set explicitly in `agent.yaml`; Cursor handles its
  own model defaults. `cursor.readonly` overrides the derived value;
  otherwise a shared sandbox of `read-only` maps to `readonly: true`
  and other sandboxes leave `readonly` unset. Cursor Skills and Cursor
  Rules are not in scope here; only native subagent export is supported.
- Source root resolution order is: `--source-root`, current working directory
  when it contains `agents/`, `AGENTS_HOME`, then legacy fallback `~/.agents`.
- The canonical `~/.agents/agents` linker is opt-in via `--link-canonical`.
- Cleanup is manifest-based so the tool only removes files it owns.
