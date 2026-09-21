# corpus-integrity

An example [Claude Science](https://www.anthropic.com) skill: three mechanical integrity checks
for evidence-synthesis work. It was built from a real literature review (the effects of AI on
adult cognition, 64 studies) and each check fixes an error that actually happened while building
that review.

> **Note on portability.** This is a *Claude Science* skill. Its `kernel.py` helpers load into the
> Claude Science Python kernel and it uses the OpenAlex API. It demonstrates the pattern; it is not
> a drop-in Claude Code skill.

## The one principle

Every function **reports and ranks by objective signals and never gates.** It surfaces
candidates — unmatched numbers, retracted DOIs, frequently-cited-but-absent papers — and the
inclusion, relevance and credibility calls stay with you. That is what keeps `corpus-integrity` a
mechanical integrity skill (works in any field) rather than a judgment skill that encodes one way
of reading evidence.

## What it does, and what it caught

### 1. `check_claims` — trace every number in a draft back to a source record
Reads a prose draft and confirms each quantitative claim (sample sizes, effect sizes,
percentages) appears in the corpus tables; flags numbers with no match and effect-size labels
(Cohen's *d* vs Hedges' *g*) that don't match the source.

*On the source project:* an earlier draft had introduced unsupported numbers during
plain-language rewriting and mislabelled a Hedges *g* as *d*. On the corrected draft the check
returns three unmatched numbers — all legitimate prose aggregates (a "152 records" search count,
a study detail, "~300 citations"). Positive controls confirm sensitivity: an injected `77,000`
(for a real `76,977`) is flagged, and an injected `d = 0.7` is caught as a label mismatch against
the source's `g = 0.7`.

### 2. `check_provenance` — retraction / preprint / venue / citations for a DOI list
*On the source project:* re-flags the Wang & Fan meta-analysis
(`10.1057/s41599-025-04787-y`) as **retracted despite 302 citations** — a paper that had to be
kept out of the corpus for exactly that reason — and identifies the 5 preprints. OpenAlex carries
the retraction flag; a clean result means "none found," not a guarantee.

### 3. `audit_coverage` — papers the corpus cites often but does not include
Follows the citation graph and ranks co-citation gaps by how many corpus papers reference each.
*On the source project:* surfaced *Cognitive Offloading* (Risko & Gilbert, cited by 7 corpus
papers) and "Measuring actual learning versus feeling of learning" (Deslauriers 2019, cited by 6)
— both directly on-theme and both absent from the corpus. It ranks; you decide which belong.

Plus `reproducibility_log(...)` to record search terms, databases and date cutoff so a corpus's
boundaries are explicit.

## Setup

`check_provenance` and `audit_coverage` need an OpenAlex API key, read from `OPENALEX_API_KEY`.
Get a free key from OpenAlex and set it in your environment; the skill never hardcodes it.
`check_claims` needs no key.

See `SKILL.md` for full signatures, usage, and limitations.
