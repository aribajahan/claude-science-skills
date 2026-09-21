# wrap — why this exists

Built 2026-09-20. Replaces a rejected proposal called `deliverable-sync`, which checked whether
three copies of a file were byte-identical. The useful half of that idea was never file identity
— it was **staleness**, which belongs to the documents, not the copies.

## What each check is here to catch

Every one corresponds to something that actually went wrong in the project it came from.

**Broken links.** Files were reorganised into `data/` and `figures/`; every exhibit reference in
ten analysis files kept pointing at the old flat paths. Nothing errored.

**Number conflicts.** One study's participant count was corrected in one document and left wrong
in another (10,426 against 10,462). The positive-control run reproduces exactly this.

**Table sums.** A four-row table of counts summing to 16 was introduced by a sentence saying
"Thirteen of the twenty prompts". The number had been typed rather than summed. This is why the
check matches number *words* — the error is nearly always written out.

**Stale next-actions.** A plan recommended an investigation the session log already recorded as
complete, with its result.

**Cross-folder scope.** Two `SESSION-LOG.md` files in two folders of the same project diverged for
three entries. A check scoped to one folder cannot see that, which is why `stale_report` takes a
list.

## The build lesson

The first version ran clean against real data. Positive controls showed **three of five checks
were broken** and a fourth was returning nothing because the folder was unreadable from that
kernel — a false negative that looked exactly like a clean bill of health.

`collect_docs` now raises on an unreadable path rather than returning an empty list. A checking
tool that cannot distinguish "nothing wrong" from "nothing read" is worse than no tool, because
it converts an unknown into a reassurance.

## Validation result — read this before trusting a clean report

Positive controls were planted for all five checks. All five fired. **On real data, only two are
usable.**

| Check | Planted control | Real data | Shipped as |
|---|---|---|---|
| broken links | fires | 0, no false positives | default |
| orphans | fires | 1, correct | default |
| number conflicts | fires | 384 junk rows on auto-terms; 2 reviewable rows with explicit terms | opt-in, `terms` required |
| table sums | fires | 3 rows, all false positives on one table | opt-in |
| stale next-actions | fires | 7 rows, mostly common-word coincidences | opt-in |

Two things caused most of the noise, and both are worth remembering for the next checker:

1. **An aggregate file poisons every similarity check.** A 440 KB conversation transcript contains
   every number and phrase in the project, so each check matched it against everything. Excluding
   transcripts and run exports cut the number-conflict rows from 384 to 17 before any other change.
2. **Automatic term selection was the wrong default.** Capitalised tokens include "Study",
   "Sample" and "Claude". Restricting to author-like tokens (a name before "et al.") and requiring
   an explicit `N =` cut it to 2 rows — one of which is a genuine cross-document inconsistency.

The honest summary: the precise half works and is on by default; the fuzzy half is real but noisy
and is off until it earns its place. Shipping all five as if equal would have produced a tool that
gets ignored after its first run.
