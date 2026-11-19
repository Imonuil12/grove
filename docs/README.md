# Grove project docs

This folder is the source of truth for **what** Grove is, **why** each part exists, and **how** we build it.
Read it before changing the product. Update it in the same change as the code.

| File | What it holds |
|---|---|
| [VISION.md](VISION.md) | The agenda, who Grove is for, and the product principles |
| [ROADMAP.md](ROADMAP.md) | Milestones, their status, and what "done" means for each |
| [DECISIONS.md](DECISIONS.md) | Product and technical decisions, dated, with the reason |
| [research/EVIDENCE.md](research/EVIDENCE.md) | The evidence library: every study we rely on, with an ID and a grade |
| [features/](features/) | One spec per feature, each mechanic linked to evidence IDs |
| [../ARCHITECTURE.md](../ARCHITECTURE.md) | How the code is laid out (backend, frontend, data, deploy) |

## How we work

1. **Research first.** No user-facing mechanic ships without an entry in the evidence library,
   or an honest "product choice, no evidence claimed" label. See the `research-backed` skill.
2. **Spec, then build.** Each feature has a spec in `features/` before code is written.
   See the `grove-feature` skill for the full build checklist.
3. **Ship in milestones.** Every milestone leaves the live site working and better than before.
4. **Write it down.** New decisions go in `DECISIONS.md`; finished work is ticked in `ROADMAP.md`.

## Skills

Project skills live in [`../.claude/skills/`](../.claude/skills/). They are step-by-step playbooks
that Claude Code (and any contributor) follows when doing a recurring kind of work:

- `research-backed`: how to find, grade, cite and use evidence, and the rules for claims in marketing copy
- `grove-feature`: how to take a feature from spec to the live site
