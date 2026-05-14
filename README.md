# Custom Agents

`custom_agents` is a small Python CLI for generating consumer-native agent
definitions for Claude Code, GitHub Copilot, Codex, Cursor, and Gemini CLI from a shared source tree.

## Install

```bash
python3 -m pip install -e '.[dev]'
```

Each agent's `agent.yaml` is gitignored; the committed `agent.yaml.example`
sibling is the canonical source. Any command that reads agents (`sync`,
`list`, `validate`, `clean`) auto-creates a missing `agent.yaml` from its
`.example` on first run — the materialized file is then yours to edit for
personal harness overrides. `shared-agents init` performs the same copy
explicitly (and `init --dry-run` previews it); it never overwrites an
`agent.yaml` that already exists, so local edits are never clobbered.

## Canonical Source Layout

```text
<source-root>/
├── AGENTS.md
├── agents/
│   └── code-reviewer/
│       ├── agent.yaml.example   # canonical, committed
│       ├── agent.yaml            # gitignored, auto-created from the .example
│       └── instructions.md
└── skills/                       # optional source material for future bundles
```

## Agent Inventory

The repository currently ships these canonical shared agents:

| Agent | Purpose |
|-------|---------|
| `plan-reviewer` | Skeptical review of implementation plans, design docs, or technical proposals. |
| `retrorabbit-code-reviewer` | Reviews code hunks for correctness, risk, and maintainability. |
| `codexrabbit-code-reviewer` | Lightweight code reviewer that emits prioritized, structured findings based on Codex's built-in review rubric. |

## Commands

```bash
shared-agents init                              # explicitly materialize agent.yaml from .example (also auto-run by the others)
shared-agents sync                              # all agents × all available harnesses
shared-agents sync --link-canonical
shared-agents tui                               # interactive agent + harness selection
shared-agents list
shared-agents validate
shared-agents clean
```

### Interactive TUI

Install the optional TUI extra before using the interactive selector:

```bash
python3 -m pip install -e '.[tui]'
shared-agents tui
```

The TUI presents separate multi-select prompts for agents and harnesses, then
shows a dry-run preview of files that will be written or removed before asking
for confirmation. `q`, Esc, empty selections, or declining confirmation abort
without writing generated files. The TUI is only launched by the explicit
`tui` subcommand; `sync` remains scriptable and never auto-launches it.

### Selection flags (on `sync`, `list`, `clean`)

All four list flags accept comma-separated values and may also be
repeated; the values accumulate.

| Flag | Effect |
|------|--------|
| `--agents A,B` | Only operate on the listed agents. |
| `--exclude-agents A,B` | Skip the listed agents. |
| `--harness H,...` | Only operate on the listed harnesses. Keywords: `claude`, `claude-skills`, `codex`, `copilot`, `cursor`, `opencode`, `gemini`, `agent-skills`, `hermes-skills`, `tprompt`. |
| `--exclude-harness H,...` | Skip the listed harnesses. |
| `--no-tprompt` | Exclude tprompt entirely. On `sync` this means don't write tprompt outputs; on `clean` it means leave existing tprompt entries in place. |

Examples:

```bash
shared-agents sync --agents code-reviewer       # one agent, all harnesses
shared-agents sync --harness claude,codex       # all agents, two harnesses
shared-agents sync --harness claude-skills      # only Claude Skills bundles
shared-agents sync --harness agent-skills       # only neutral Agent Skills bundles
shared-agents sync --harness hermes-skills      # install skills for Hermes
shared-agents sync --exclude-harness gemini     # skip gemini for everyone
shared-agents sync --agents code-reviewer --harness claude
shared-agents clean --agents code-reviewer      # remove only this agent's outputs
shared-agents clean --harness gemini            # remove only gemini outputs
```

### Export mode

Each shared definition has one export mode:

| Mode | Effect |
|------|--------|
| `export: agent` | Default. Generate native agent/subagent files for selected agent harnesses. |
| `export: skill` | Generate skill bundles and skip native agent files. |
| `export: none` | Do not generate anything for this definition. |

This keeps similarly named native agents and skills from being deployed at
the same time. For example:

```yaml
name: code-reviewer
description: Use when reviewing code changes before merge.
export: skill
skill:
  name: code-reviewer
  title: Code Reviewer
  description: Use when reviewing code for correctness, security, maintainability, and test coverage.
  tags: [review, code]
```

The `skill:` block is optional and only customizes the rendered skill. If it
is omitted, the skill name is normalized from `name`, the description comes
from the agent description, and the body comes from `instructions.md`.

`defaults.skills` is different: it references skills that a downstream
consumer may load. `export: skill` creates an actual Agent Skills bundle.

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

Then the definition's `export` mode is applied: `agent` drops skill harnesses,
`skill` keeps only skill harnesses, and `none` drops everything.

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
- Claude Skills bundle: `~/.claude/skills/<skill-name>/SKILL.md`
- Agent Skills neutral bundle: `~/.agents/skills/<skill-name>/SKILL.md`
- Hermes Skills install bundle: `$HERMES_HOME/skills/<skill-name>/SKILL.md` or `~/.hermes/skills/<skill-name>/SKILL.md`
- Optional compatibility link: `<source-root>/agents` symlinked to `~/.agents/agents` only when `--link-canonical` is used

`claude-skills` is the Claude-native skill target. `agent-skills` is the
neutral skill target for Agent Skills-compatible consumers. `hermes-skills`
installs the same generated `SKILL.md` bundle into Hermes' user skill
directory. Hermes does not load `~/.agents/skills` by default; use
`hermes-skills` for direct availability in a new Hermes session, or configure
Hermes `skills.external_dirs` yourself to scan neutral exports. The other
supported harnesses continue to use native agent exports.

## Manifest

State is tracked in `~/.local/state/custom_agents/.shared-agents-manifest.json`
(or `$XDG_STATE_HOME/custom_agents/...`). Cleanup is manifest-based so the
tool only removes files it owns. The manifest is v2: each entry is
`{agent, path}` per harness, including generated `claude-skills`,
`agent-skills`, and `hermes-skills` `SKILL.md` files. Skill cleanup removes only manifest-owned
files and prunes empty generated skill directories; unmanaged files in a
skill directory are preserved. v1 manifests are auto-migrated on first load with a one-time stderr line of the form
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
  and other sandboxes leave `readonly` unset. Cursor-specific Skills and
  Cursor Rules are not in scope here; use the neutral `agent-skills` export
  when a reusable skill bundle is desired.
- Hermes skill output is generated under `$HERMES_HOME/skills/` when
  `HERMES_HOME` is set, otherwise under `~/.hermes/skills/`. Start a fresh
  Hermes session or run `/reset` after syncing so Hermes refreshes its skill
  index and prompt context. Cleanup is manifest-scoped and will not remove
  hand-authored files in generated Hermes skill directories.
- Source root resolution order is: `--source-root`, current working directory
  when it contains `agents/`, `AGENTS_HOME`, then legacy fallback `~/.agents`.
- The canonical `~/.agents/agents` linker is opt-in via `--link-canonical`.
- Cleanup is manifest-based so the tool only removes files it owns.
