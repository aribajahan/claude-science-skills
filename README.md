# Example Claude Science skills

Reusable skills built on Anthropic's Claude Science workbench, in two families: **research-evidence tools** for assembling and checking a literature corpus (`corpus-integrity`, `schema-extraction`, `fulltext-acquisition`, `construct-audit`, `contested-claim-finder`), and **session-workflow tools** for the work that produces it (`archive-recall`, `wrap`). Each came out of one real project — a source-verified review of the research on AI and adult cognition — and each is here because it caught a real error or removed a real friction along the way.

**These are Claude Science skills, not Claude Code skills.** They depend on the Claude Science platform (the `host.*` SDK, `kernel.py` sidecars, and its connectors). They're readable as examples of the pattern, but they won't run unchanged in Claude Code.

By Ariba Jahan · [aribajahan.com](https://aribajahan.com)

## The skills

### Research-evidence tools

- **corpus-integrity** — check a corpus and a draft written from it against reality: every number traces to its source record, DOIs are checked for retraction, correction, and preprint status, citation-linked-but-missing papers are surfaced, and every "N of M" denominator is resolved against the source tables. It reports and ranks; you decide what's relevant.
- **schema-extraction** — design a project's evidence schema (a fixed integrity floor plus a question- and corpus-driven layer) and extract studies to it, instead of forcing every study into one fixed column set.
- **fulltext-acquisition** — before extraction, locate open-access full text via OpenAlex and fetch it from arXiv, PubMed Central, or an OA PDF; every failure states its reason.
- **construct-audit** — for a claimed cognitive outcome, extract how each study actually operationalised it and report where one label ("critical thinking", "learning") covers different constructs. Single-rater by design; every code carries a justifying quote, so the classification is checkable.
- **contested-claim-finder** — given a claim and a corpus, code which studies support it and which contradict it (reading the findings, not the design), and report the split without collapsing to a verdict — with a mechanism flag that stops a sign-correct count from becoming a claim about human cognition.

### Session-workflow tools

- **archive-recall** — recover verbatim content from a folded or compacted conversation archive. Leads with the durable recovery method and keeps the platform's current accessor shapes in one verify-before-trusting block, so it degrades loudly rather than silently if those internals change.
- **wrap** — close out a working session: draft a dated session-log entry, propose a plan update as a diff for approval, and report where a project's own documents have drifted. Two checks are reliable and on by default; three more are experimental and opt-in.

## Using them

Each skill is a folder with a `SKILL.md` (the instructions the model follows) and, where it needs one, a `kernel.py` helper. `corpus-integrity`, `fulltext-acquisition`, `construct-audit`, and `contested-claim-finder` use OpenAlex or the platform reasoning model — set your own key in the `OPENALEX_API_KEY` environment variable where OpenAlex is used. Nothing here carries an API key or a private path.

## Posture

The integrity skills report and rank by objective signals; they never decide what's relevant, credible, or true. The judgment skills (`construct-audit`, `contested-claim-finder`) classify and surface, and ship every call with a quote so it is checkable — they do not return a verdict. That judgment stays with the person. See `SECURITY.md` for how they treat retrieved content.
