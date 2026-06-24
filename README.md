# .gekyume — Agent Operating System

`.gekyume` is a structured AI agent workspace. It organizes skills, configuration, and session memory into a portable, extensible system that any compatible AI agent (Antigravity, Gemini CLI, etc.) can load and operate from.

## Folder Structure

| Path | Purpose |
|---|---|
| `.gemini.md` | Global agent instructions and behavioral rules |
| `skills/` | One `.md` file per skill — each is a standalone system prompt |
| `config/skills.json` | Registry mapping skill names to their files and trigger phrases |
| `memory/context.json` | Persistent session history and state |

## How to Add a New Skill

1. **Write the skill** — Author a focused system prompt and save it as `skills/<skill_name>.md`
2. **Register it** — Add a new entry to `config/skills.json` with `name`, `description`, `trigger_phrases`, and `file`
3. **Test it** — Say one of the trigger phrases to the agent and confirm the skill activates correctly

## How to Run a Skill in Antigravity

Load the contents of the relevant `skills/<skill_name>.md` file into your active system prompt or paste it into the Antigravity system prompt field.

## Skills in This System

| Skill | File | Purpose |
|---|---|---|
| `skill_builder` | `skills/skill_builder.md` | Creates and registers new skills |
| `orchestrator` | `skills/orchestrator.md` | Coordinates multi-agent task delegation |
| `brand_kit` | `skills/brand_kit.md` | Applies brand identity and design tokens |
| `brand-kit-builder` | `skills/brand-kit-builder.md` | Interactive brand kit builder (CRISP-DM) |
| `carousel` | `skills/carousel.md` | Builds interactive content carousels |
| `transcript-to-script` | `skills/transcript-to-script.md` | Converts video transcripts to scripts, captions, and SEO assets |
| `hindsight-memory` | `skills/hindsight-memory.md` | Manages long-term memory, fact extraction, and system reflection |
| `autoresearch` | `skills/autoresearch.md` | Runs autonomous ML research experiments in a Propose-Train-Evaluate-Ratchet loop |
