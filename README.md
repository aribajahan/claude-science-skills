# Example Claude Science skills

Reusable skills built on Anthropic's Claude Science workbench, in two families: **research-evidence tools** for assembling and checking a literature corpus (`corpus-integrity`, `schema-extraction`, `fulltext-acquisition`), and **session-workflow tools** for the work that produces it (`archive-recall`, `wrap`). Each came out of one real project — a source-verified review of the research on AI and adult cognition — and each is here because it caught a real error or removed a real friction along the way.

**These are Claude Science skills, not Claude Code skills.** They depend on the Claude Science platform (the `host.*` SDK, `kernel.py` sidecars, and its connectors). They're readable as examples of the pattern, but they won't run unchanged in Claude Code.

By Ariba Jahan · [aribajahan.com](https://aribajahan.com)

## The skills

### Research-evidence tools

- **corpus-integrity** — check a corpus and a draft written from it against reality: every number traces to its source record, DOIs are checked for retraction, correction, and preprint status, and citation-linked-but-missing papers are surfaced with a reproducibility log. It reports and ranks; you decide what's relevant.
- **schema-extraction** — design a project's evidence schema (a fixed integrity floor plus a question- and corpus-driven layer) and extract studies to it, instead of forcing every study into one fixed column set.
- **fulltext-acquisition** — before extraction, locate open-access full text via OpenAlex and fetch it from arXiv, PubMed Central, or an OA PDF; every failure states its reason.

### Session-workflow tools

- **archive-recall** — recover verbatim content from a folded or compacted conversation archive, avoiding the two accessor mistakes that return confident wrong answers.
- **wrap** — close out a working session: draft a dated session-log entry, propose a plan update as a diff for approval, and report where a project's own documents have drifted — broken links, the same figure carrying different numbers, stale next-actions.

## Using them

Each skill is a folder with a `SKILL.md` (the instructions the model follows) and, where it needs one, a `kernel.py` helper. `corpus-integrity` and `fulltext-acquisition` query OpenAlex — set your own key in the `OPENALEX_API_KEY` environment variable. Nothing here carries an API key or a private path.

## Posture

The integrity skills report and rank by objective signals; they never decide what's relevant, credible, or true. That judgment stays with the person. See `SECURITY.md` for how they treat retrieved content.
