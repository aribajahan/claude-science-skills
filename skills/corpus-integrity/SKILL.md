---
name: corpus-integrity
description: "Mechanical integrity checks for a literature corpus and a draft written from it: trace every number in the draft back to a source record, look up retraction/preprint/venue/citation status for a list of DOIs, and surface papers the corpus cites often but does not include. Every function reports and ranks by objective signals; none decides what is relevant, credible, or in-scope. Use when assembling, verifying, or writing up an evidence review and you want to catch drifted numbers, retracted or preprint sources, and coverage gaps."
---

# corpus-integrity

Three mechanical checks for evidence-synthesis work. Each one **reports and ranks by objective
signals and never gates** — it surfaces candidates and you decide what is relevant, credible, or
in. That line is deliberate: it keeps this a mechanical integrity skill, usable in any field,
rather than a judgment skill that encodes one way of reading evidence.

The three checks each fix an error that actually occurred while building the review this skill
came from — see `README.md` for the specific catches.

## Setup

`check_provenance` and `audit_coverage` call the OpenAlex API, which requires a key. The skill
reads it from the `OPENALEX_API_KEY` environment variable and never hardcodes it.

- **In Claude Science:** store an OpenAlex credential, then declare it on the cell that calls the
  function (e.g. `credentials=["OpenAlex"]`), so `OPENALEX_API_KEY` is present. Never send
  `mailto=` to OpenAlex and never call it anonymously.
- **Anywhere else:** `export OPENALEX_API_KEY=...` (get a free key from OpenAlex) before running.

`check_claims` is offline — no key needed.

## Functions

The kernel sidecar loads these into your Python kernel when the skill loads.

### `check_claims(draft_path, source_csv_paths) -> dict`
Traces every quantitative claim in a prose draft back to the source corpus.
- `draft_path` — the prose draft (markdown/text).
- `source_csv_paths` — **list** of every CSV that makes up the corpus. Pass all of them: a number
  counts as unmatched only if it is absent from every source table.
- Returns `{"unmatched": [{value, sentence}], "label_mismatches": [{value, draft_label, source_label}]}`.
  `unmatched` = numbers in the draft with no match in any source table (may be a legitimate prose
  aggregate — you judge). `label_mismatches` = a value the draft attaches to one effect-size label
  (Cohen's *d* / Hedges' *g*) while the source records it under the other.

### `check_provenance(dois, api_key=None) -> list[dict]`
Looks up retraction, preprint status, venue and citation count for a list of DOIs (OpenAlex).
- Returns one dict per DOI: `{doi, retracted, type, is_preprint, venue, citations, note}`.
- A clean result means **"no retraction found," not a guarantee**. DOIs absent from OpenAlex come
  back with `note="not found in OpenAlex"` — verify those by hand.

### `audit_coverage(corpus_dois, api_key=None, top_n=15, min_refs=2) -> list[dict]`
Surfaces papers the corpus **cites frequently but does not include** — a co-citation gap — ranked
by how many corpus papers reference each.
- Pass **all** corpus DOIs (every table). Returns `{corpus_refs, cited_by_count, year, title, doi,
  openalex_id}`, ranked by `corpus_refs`. It ranks candidates; you decide which are in scope.

### `reproducibility_log(search_terms, databases, date_cutoff, counts) -> str`
Formats a plain-text record of how the corpus was assembled, so its boundaries are explicit and
someone could rebuild it.

## Usage

```python
skill({"skill": "corpus-integrity"})   # loads the functions into the kernel

# 1. trace numbers in the draft (offline)
res = check_claims("review.md", ["main_table.csv", "benefit_table.csv"])
print(res["unmatched"], res["label_mismatches"])

# 2. provenance (needs OPENALEX_API_KEY on the cell)
import csv
dois = [r["doi"] for r in csv.DictReader(open("main_table.csv")) if r["doi"]]
prov = check_provenance(dois)
retracted = [r for r in prov if r["retracted"]]

# 3. coverage gap
gaps = audit_coverage(dois, top_n=15)
```

## Limitations (state these honestly)

- `check_claims` flags any number absent from the tables, including legitimate prose aggregates
  (totals, computed percentages). It surfaces; it does not judge. Numbers inside URLs/DOIs/arXiv
  ids are stripped before matching.
- `label_mismatches` is bounded by what the source records. If the source stores effect sizes as
  free text without the statistic name, a mislabelled statistic can't always be detected.
- `check_provenance` retraction coverage is only as complete as OpenAlex's `is_retracted` flag;
  treat a clean result as "none found."
- `audit_coverage` uses the citation graph as an objective proximity signal. Some referenced-work
  IDs have no resolvable metadata in OpenAlex (merged/deleted) — those still rank, shown by
  `openalex_id`.
