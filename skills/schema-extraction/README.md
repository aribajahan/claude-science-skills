# schema-extraction

An example [Claude Science](https://www.anthropic.com) skill: design the extraction schema for an
evidence-review project, then extract papers to it. Built from a real 64-study review of AI's
effect on adult cognition.

> **Portability note.** This is a *Claude Science* skill. `suggest_schema` and `extract_study` use
> the platform LLM (`host.llm`); the schema/validation functions are plain Python. It demonstrates
> the pattern; it is not a drop-in Claude Code skill.

## The idea

A review table's columns are not a fixed template — they are what a project's **question** and
**corpus** produce. This skill separates the schema into two layers:

- an **integrity floor** — fixed columns that let you trust and trace any record (provenance,
  resolvable links, full-text-vs-abstract basis, the study's own hedges); and
- a **variable layer** — the columns a specific question warrants, minus the ones the corpus would
  leave mostly empty.

Every function **reports and never gates**: it proposes a schema, flags inconsistencies, and
surfaces low-availability fields. You decide.

## What it does, and what it caught

- **`validate_row`** — checks each row against the schema: required floor fields present,
  controlled vocabulary, resolvable links, and — the useful one — fields that are *not applicable*
  to a record type but carry a value. *On the source project it flagged 10 real issues in the
  existing 46-row table (10 error-level flags):* three records tagged with an
  `unassisted_outcome_flag` they can't have — two perspective pieces (Bauer, Yan) and one synthesis
  (Gilbert); four more where the two perspective rows carry `design`/`measures`/`effect_size` values
  that are n/a for an opinion piece — including Yan's **borrowed** `Hedge's g = 0.7`, cited from a
  meta-analysis (a classic misread risk); and three rows missing a venue.
- **`field_availability`** — the mechanical half of "what should the columns be": for each candidate
  field, the fraction of the corpus that can actually fill it. *On the source project* it showed
  `population_type`, `comparison_condition` and `sample_description` at 0% (fields worth adding only
  if you'll backfill them) and `unassisted_outcome_flag` at 37%.
- **`suggest_schema`** — proposes the floor plus the variable fields a question warrants. *For a
  durability question* it recommended `ai_exposure`, `measures`, `duration_class`,
  `unassisted_outcome_flag`, `comparison_condition`, and `causal_language` — the durability- and
  causal-read fields.
- **`extract_study`** — reads a paper and fills the schema, using `not reported in retrieved text`
  for absent-but-applicable values and `n/a (<record_type>)` for inapplicable ones, in the
  controlled vocabulary. Always paired with `validate_row`.

Plus `fields_for(record_type)` (the conditional-field logic) and `append_row` (validate-then-append).

See `SKILL.md` for signatures, usage and limitations.
