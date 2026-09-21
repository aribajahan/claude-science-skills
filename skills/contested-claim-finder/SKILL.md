---
name: contested-claim-finder
description: "Given a claim and a corpus, code which studies support it and which contradict it, reading each study's findings field, and report the split without collapsing to a verdict. Emits a direction (supports/contradicts/mixed/not_applicable), the sign of the disputed quantity, and a verbatim justifying quote per study, plus a mechanism-locus flag that surfaces studies whose effect is in the model's output rather than in the person — so a sign-correct count is never mistaken for a claim about human cognition. Use before writing up a result as settled, and whenever a 'most studies find…' statement is about to go in a draft."
---

# contested-claim-finder

A corpus can look like consensus at the design level and be a 3-to-1 split at the findings level.
This skill codes each study's stance on a specific claim **from its findings text**, reports the
tally with the deciding quotes side by side, and flags studies whose effect is not actually located
in the person. It reports the split; it never tells you which side is right.

## Load

```python
skill({"skill": "contested-claim-finder"})   # loads the functions into the kernel
```

Coding uses the platform reasoning model (`host.llm`); no API key needed.

## Functions

### `code_direction(claim, records, id_field="doi", findings_field="key_finding", model=None, max_concurrency=8) -> dict`
Codes each study against `claim`. `records` is a list of dicts each carrying a findings field.
Returns `coded` (one dict per study: `id, direction, sign, quote, mechanism_locus, rationale`) and
`unrecovered` (ids that never parsed after one retry — report this count).
- `direction`: supports · contradicts · mixed · not_applicable
- `sign`: the direction of the disputed quantity (increase / decrease / no_change / n/a)
- `quote`: a verbatim span from the findings that decides the call
- `mechanism_locus`: `person` (change in the human), `model_output` (measured change is in the
  model's contributed text, not the person), or `unclear`

### `contest_report(coded, claim=None) -> dict`
`tally`, a `contested` flag (True when both supports and contradicts are present — a prompt to write
it up as contested, **not** a resolution), the deciding `quotes`, and `mechanism_caveats`.

### `mechanism_caveats(coded) -> list`
Studies whose effect is not located in the person. A study can be sign-correct for a claim about
human cognition and still be surfaced here, because the effect is in what the model wrote.

## The one load-bearing rule

**Direction is coded from the findings field, never from design or measures.** In the session this
came from, two failures — one in a planning doc, one in the agent's own synthesis — both came from
reading design-level fields, where studies pointing opposite ways look identical. Pass the findings
field; do not substitute a design or methods field.

## Limitations

- **Corpus-bounded.** It codes the direction of the studies you give it; it does **not** search for
  contradictors the corpus is missing. A one-sided corpus (e.g. from publication bias) will read as
  consensus because the dissent was never collected. Pair it with a coverage check for what is
  absent — this skill only judges what is present.
- **Report, don't gate.** `contested=True` means "write this up as contested," not "resolved."
- One coding pass with a retry; single-rater, no inter-rater statistic. The quotes are attached so
  every call is checkable.
