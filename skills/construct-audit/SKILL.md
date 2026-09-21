---
name: construct-audit
description: "For a claimed cognitive outcome across a corpus, extract how each study actually operationalised it and report where one label — 'critical thinking', 'learning', 'memory' — covers different constructs. Codes each study on a controlled vocabulary (domain, measure type, and the gap between what was measured and what was claimed), with every code carrying a short justification quoting the record. Reports a domain-by-gap crosstab and how many studies measure the capacity they claim; it counts and surfaces, it does not decide. Single-rater by design — the aggregate is a candidate finding, not a settled classification. Use when a corpus rests on a construct that may not be measured the same way twice."
---

# construct-audit

A label like "critical thinking" or "learning" can hide the fact that ten studies measured ten
different things. This skill pulls what each study *actually did and scored*, codes it on a fixed
vocabulary, and reports where the construct fractures — and how often the thing measured is not the
thing claimed.

The mechanical core is the extraction and the tally. The interpretation — whether a coded gap is a
real threat to a claim — stays with you. This is the judgment tier of the toolkit, made **opt-in
and checkable** rather than baked in.

## Load

```python
skill({"skill": "construct-audit"})   # loads the functions into the kernel
```

Coding uses the platform reasoning model (`host.llm`), so run it in a kernel where `host` is
available. No API key needed.

## Functions

### `code_constructs(records, id_field="doi", text_fields=None, model=None, max_concurrency=8) -> dict`
Codes every study. `records` is a list of dicts, each with at least a findings field (and ideally
`design`, `measures`, `citation`). Returns:
- `coded` — one dict per study: `id, task, signal, measure, domain, measure_type, instrument_named,
  gap, gap_note`. `gap_note` (≤22 words, quoting the record) is why the gap was coded as it was —
  **always keep it; it is what makes a code checkable.**
- `unrecovered` — ids that never parsed after one retry. **Report this count**; do not silently
  audit fewer studies than you were given.
- `vocab_flags` — values the model returned outside the controlled vocabulary. Surfaced, not
  corrected.

It reads the **findings** field, not only design/measures: designs can agree where results diverge,
so reading design alone reports false convergence.

### `construct_report(coded) -> dict`
`total`, a `headline` ("N of M studies measure the capacity they claim" = gap `none`),
`measured_tool_removed`, `instrument_named`, per-term counts for domain / measure_type / gap, and a
`domain_x_gap` crosstab. It counts; it does not conclude.

### `exemplars(coded, n=2) -> dict`
Up to `n` `task → signal → measure → gap → gap_note` rows per domain, so every aggregate traces to
the studies under it.

## Controlled vocabularies (validated on 63 studies — do not extend without re-validating)

- **domain**: memory, learning_transfer, reasoning_critical, metacognition, decision_judgment,
  attention_effort, creativity, domain_skill, brain_physiology, self_reported_habit, unclear
- **measure_type**: performance_with_tool, performance_without_tool, product_quality, self_report,
  physiological, behavioural_trace, synthesis, unclear
- **gap**: none · product_for_process (scored an output, claimed a process) · assisted_for_durable
  (measured with the tool present, claimed a durable capacity) · self_for_actual (self-report
  measured, actual capacity claimed) · proxy_construct (instrument measures a related but different
  thing) · unclear

## Limitations — read before quoting a number

- **Single-rater.** The coding is one model-assisted pass with human review and **no inter-rater
  reliability statistic**. The `product_for_process` / `none` boundary in particular is arguable.
  Report the aggregate *with* the single-rater flag and the `gap_note`s attached — never the bare
  "N of M" alone, or the audit becomes the kind of over-read it exists to catch.
- **Report, don't gate.** It classifies; it does not decide a study is invalid. A coded gap is a
  question to weigh, not a verdict.
- **Corpus-bounded.** It audits the studies you give it. It says nothing about studies missing from
  the corpus.
- `run_recode` is a separable engine; a future general recode skill can reuse it with a different
  axis. `code_constructs` is the packaged construct axis.
