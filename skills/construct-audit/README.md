# construct-audit — why this exists

An example [Claude Science](https://www.anthropic.com) skill. Built from a review of AI's effect on
adult cognition, where the same word covered very different measurements across studies.

> **Portability note.** A *Claude Science* skill: `code_constructs` uses the platform reasoning model
> (`host.llm`); the report functions are plain Python. It demonstrates the pattern; it depends on the
> `host.*` runtime and will not drop into Claude Code unchanged.

## What it found

Run across the corpus's 63 studies, the audit produced one number that reframes the whole field:

> **Only 5 of 63 studies measure the capacity they claim.** Of the rest, 24 measured performance
> *with the AI still present* while claiming a durable capacity, 13 measured *self-report* while
> claiming an actual one, 11 scored an *output* while claiming a thinking *process*, and 4 used a
> proxy instrument.

And the fracture the label hides: studies coded to the same *domain* land in different *gap*
categories — the crosstab shows that "reasoning/critical thinking" work splits between scoring an
essay's quality (`product_for_process`) and scoring reasoning during tool use
(`assisted_for_durable`). One label, two different constructs.

Every one of those codes ships with a `gap_note` quoting the study, so the classification is
checkable rather than asserted.

## The honest caveat

This is a **single-rater** audit — one model-assisted pass, human-reviewed, with no inter-rater
reliability statistic, and some boundaries (notably `product_for_process` vs `none`) are arguable.
The "5 of 63" is a candidate finding that reorganises how to read the corpus, not a settled
classification. The skill is built to be quoted *with* that caveat and with the per-study notes
attached — a construct audit that gets over-read is the exact failure it exists to prevent.

## Functions

`code_constructs(records)` (extract + code), `construct_report(coded)` (crosstab + headline),
`exemplars(coded, n)` (traceable rows per domain). The recode loop is a separable engine
(`run_recode`) so a future general recode skill can reuse it. See `SKILL.md` for signatures,
vocabularies, and limitations.
