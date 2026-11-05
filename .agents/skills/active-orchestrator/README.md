# active-orchestrator

Thin orchestrator skill for the SDD/OpenSpec project foundation flow.

## What it does

`active-orchestrator` is a **thin** orchestrator. It does not generate any artifact itself — it dispatches each foundation phase to its dedicated sub-skill in order:

1. `openspec init` — scaffold the OpenSpec workspace
2. *(optional)* `discovery-research` — investigate the problem, users and competitors **before** documenting — only runs if you say yes to the Discovery gate right after `openspec init`
3. `kb-creator` — build `knowledge-base/` (discovery + canonical docs)
4. `design-system` — record the project visual policy; if chosen, create and approve a reusable visual system
5. `roadmap-generator` — build `CHANGES.md` from the KB
6. `find-skill` — recommend agent skills for the detected stack
7. `skill-registry` — index installed skills
8. `agent-instruction` — generate `CLAUDE.md` / `AGENTS.md`

**Checkpoints between phases.** The full flow never runs phases back-to-back: it stops at every phase boundary so you can review what was produced and choose **continue / adjust / stop**. Where a phase depends on your judgment (the roadmap), it first asks if there's anything to take into account. And `find-skill` only *recommends* — nothing is installed into your global skills until you pick it at the install gate.

State is shared across phases via `.active-orchestrator-state.json` (schema v5). The visual choice is `system-and-mockups`, `system-only`, `off`, or `deferred`. An explicit `off` persists, so later changes do not request mockups. Older completed foundations keep their progress and can add the policy via `/active-orchestrator:design` or at their first visual change.

## Triggers

| Command | Effect |
|---|---|
| `/active-orchestrator:init` | Full foundation flow |
| `/active-orchestrator:discovery` | Only `discovery-research` phase (standalone, skips the gate) |
| `/active-orchestrator:kb` | Only `kb-creator` phase |
| `/active-orchestrator:design` | Set or revise the visual policy without replaying completed foundation phases |
| `/active-orchestrator:rules` | Only `agent-instruction` phase |
| `/active-orchestrator:openspec` | Only `openspec init` |
| `/active-orchestrator:find-skill` | Only `find-skill` phase |
| `/active-orchestrator:devops` | Optional devops scaffolding (full mode) |

## Install

```bash
npx skills add https://github.com/Group-Active-IA/active-orchestrator
```

## Architecture

This skill is part of the **Active Stack** foundation. `design-system` is bundled in Active Stack Full and selectable in Custom. The other sub-skills are installed separately. `active-orchestrator` dispatches the available skills and falls back gracefully if one is missing.

For the full architecture and frozen state contract, see [SKILL.md](SKILL.md).

## License

MIT
