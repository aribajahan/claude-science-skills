---
name: schema-extraction
description: "Design the extraction schema for an evidence-review project, then extract papers to it. The schema is two layers: a fixed integrity floor (provenance, resolvable links, full-text-vs-abstract basis, the study's own hedges) that every project keeps, plus a variable layer driven by the research question and by what the corpus can actually fill. Provides a corpus field-availability check, conditional fields by record type (empirical/synthesis/survey/perspective/correction), a not-applicable-vs-not-reported validator, and an LLM extraction step. Use when starting or standardising a literature-review table and you need the right columns for the question, not a fixed template."
---

# schema-extraction

The 26-column table this skill grew from is not a template — it is what one project's question and
corpus produced. This skill helps you arrive at the right schema for a **new** project, then
extract to it. Two layers:

- **Integrity floor (fixed, every project).** The columns that let you trust and trace a record:
  `study_id, citation, title, authors, year, venue, pub_status, text_basis, doi, url,
  open_access_pdf, record_type, key_finding, caveat_flags`. Dropping one damages the project's
  integrity regardless of topic.
- **Variable layer (question- and corpus-driven).** The columns a particular question warrants —
  `duration_class` and `unassisted_outcome_flag` for a durability question, `population_type` for a
  "who benefits" question — minus the ones the corpus would leave mostly empty.

Choosing the variable layer is judgment; the floor and the availability check that informs the
choice are mechanical. Every function **reports; it does not gate** — it proposes a schema, flags
inconsistencies, surfaces low-availability fields, and you decide.

## Setup

`suggest_schema` and `extract_study` use the platform LLM (`host.llm`) and only work inside Claude
Science. The other functions are offline. No API key needed.

## Functions

Loaded into the kernel when the skill loads.

- `integrity_floor() -> dict` — the fixed columns and why each is non-negotiable.
- `field_availability(corpus_csv_path, candidate_fields=None) -> list` — for each field, the
  fraction of records that populate it (non-empty, non-sentinel), least-fillable first;
  `mostly_empty` flags fields under ~1/3. This is "what the corpus can fill," in code.
- `fields_for(record_type) -> dict` — `{"required", "optional", "na"}` for one of
  `empirical | synthesis | survey | perspective | correction`. Only the experiment-specific fields
  (`unassisted_outcome_flag`, `randomised`, and for non-primary types `participants_n`/`effect_size`/
  `design`/`measures`) are ever N/A — a survey keeps its design and sample size.
- `validate_row(row, record_type=None) -> (record_type, issues)` — checks required floor fields,
  n/a-for-type fields that carry a value, controlled-vocab legality, and links. `error` =
  missing floor field / wrong link / an n/a field carrying a substantive value; `warn` = no OA
  link / a value outside the controlled vocabulary.
- `suggest_schema(question, corpus_csv_path=None) -> dict` — floor + the variable menu, annotated
  with availability when a corpus is given, plus an LLM recommendation of which variable fields the
  question warrants (`recommended_for_question` is `None` when `host.llm` is unavailable — choose
  from the menu).
- `extract_study(text, metadata, fields) -> row` — LLM step: read a paper and fill the schema,
  using the sentinel discipline (`not reported in retrieved text` vs `n/a (<record_type>)`) and the
  controlled vocabulary. Always `validate_row` the result before appending.
- `append_row(row, csv_path) -> dict` — validate then append; refuses on any error-severity issue.

## Usage

```python
skill({"skill": "schema-extraction"})

# 1. what schema does THIS project need?
prop = suggest_schema("Does AI use cause lasting change after the tool is removed?", "corpus.csv")
#   -> floor + recommended variable fields (duration_class, unassisted_outcome_flag, ...) + availability

# 2. audit an existing table (also validates it for free)
import csv
for row in csv.DictReader(open("corpus.csv")):
    rt, issues = validate_row(row)
    if any(i["severity"] == "error" for i in issues): print(row["citation"], issues)

# 3. extract a new paper, then validate before adding
row = extract_study(paper_text, {"doi": doi, "url": url, "title": title}, prop["recommended_for_question"])
append_row(row, "corpus.csv")
```

## Limitations (state these honestly)

- The variable-layer recommendation is a judgment aid, not an authority. `suggest_schema` proposes;
  you decide which columns are in.
- `field_availability` measures whether a cell is *filled*, not whether it is *correct*.
- `validate_row`'s controlled-vocabulary check will warn on any table using different vocabulary
  conventions (e.g. "single session" vs "single-session"). That is drift from *this* schema's
  vocabulary, not necessarily an error — it tells you what to normalise if you adopt it.
- `extract_study` reads only the text you give it. A field the text omits comes back as
  `not reported in retrieved text`; abstract-only inputs will leave many fields at that sentinel.
- Record-type detection from a free-text hint (`derive_record_type`) is best-effort; pass
  `record_type` explicitly when you know it.
