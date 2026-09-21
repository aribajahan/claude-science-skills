# contested-claim-finder — why this exists

An example [Claude Science](https://www.anthropic.com) skill. Built from a review of AI's effect on
adult cognition, after a contested result was twice written up as settled in one session.

> **Portability note.** A *Claude Science* skill: `code_direction` uses the platform reasoning model
> (`host.llm`); the report functions are plain Python. It depends on the `host.*` runtime and will
> not drop into Claude Code unchanged.

## What it caught

**The agent's own synthesis.** Asked about the creativity literature, the agent called four studies
"four independent replications of one directional pattern" and named it the corpus's most-replicated
finding. It was not. Reading each study's *findings* field on the claim *"AI reduces the diversity of
collective ideas"*:

| Study | n | Direction of collective diversity | Coded |
|---|---|---|---|
| Doshi & Hauser 2024 | 293 | down (stories "more similar to each other") | supports |
| Anderson et al. 2024 | 36 | down ("less semantically distinct ideas") | supports |
| Padmakumar & He 2023 | 38 | down ("significant reduction in diversity") | **mixed** — see below |
| Ashkinaze et al. 2025 | 800+ | **up** ("did increase … collective idea diversity") | contradicts |

**Contested, not consensus.** Normalised to the direction of collective diversity, three point down
and one up; the skill returns `contested = True` with the deciding quotes side by side. (The raw
`sign` field is *not* a clean cross-study tally — each study reports its own quantity, so Doshi's
rising *similarity* and Anderson's falling *distinctness* both mean "diversity down" but carry
opposite `sign` values. That mismatch is exactly why `direction` — normalised to the claim — is the
coded axis, not raw sign.) Ashkinaze is the single dissenter, and also found *no* individual-creativity
effect, against Doshi's positive one.

**The mechanism caveat.** Padmakumar's diversity loss is "mainly attributable to InstructGPT
contributing" — the model's own text, "the user-contributed text remain[ing] unaffected." So it is
not evidence of a change in the person. The skill surfaces it in `mechanism_caveats` (locus =
`model_output`) and, reading that, codes its *direction* as `mixed` rather than clean support — a
sign-correct study that should not be counted as a claim about human cognition. This is the whole
reason `mechanism_locus` is a first-class field and not a footnote.

## The limitation to keep in view

It codes the direction of studies **already in the corpus**. It does not find contradictors the
corpus never collected — a one-sided corpus reads as consensus because the dissent was never there.
It protects against mis-reading what you have, not against what you are missing.

## Functions

`code_direction(claim, records)`, `contest_report(coded)`, `mechanism_caveats(coded)`. See
`SKILL.md` for signatures and the one load-bearing rule (code from findings, never design).
