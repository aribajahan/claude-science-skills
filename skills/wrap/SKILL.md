---
name: wrap
description: "Close out a working session on a project: draft a dated session-log entry, propose the plan update for approval, and report what has gone stale across the project's own documents — broken cross-references, the same figure carrying different values in different files, a prose total that does not match the table above it, and next-actions naming work already logged as done. Point it at folders; no repo or git required. Use at the end of a session, or when a project's documents have drifted out of sync with each other."
---

# wrap

A session produces work in two places: the artifacts, and the documents that say what the
artifacts mean and what happens next. The second set rots quietly. Files move and every
cross-reference breaks; a number gets corrected in one document and not the other; a plan keeps
recommending work that was finished two sessions ago.

`wrap` closes a session by writing the log, proposing the plan update, and reporting the rot.

## Scope: folders, not repos

Pass the folders that make up the project. There is no git dependency and no assumption that the
project is a repository — most aren't. Pass **every** folder the project spans: cross-folder
drift is the kind a single-folder check structurally cannot see, and that is exactly how two
copies of one log ended up diverging in the project this came from.

## What writes, what proposes, what only reports

| Function | Touches disk |
|---|---|
| `draft_entry(...)` | no — returns text |
| `append_entry(log, text)` | **yes** — append-only, never edits existing content |
| `propose_plan_update(...)` | no — returns a unified diff for you to approve |
| `stale_report(paths)` | no — report only |

The asymmetry is deliberate. Appending to a log cannot destroy anything. Rewriting a plan's
"where it stands" is a replace, and an unattended wrong edit becomes permanent — so the plan
change comes back as a diff and a human accepts it.

## Usage

```python
paths = ["~/projects/thing", "~/projects/thing-notes"]   # every folder the project spans

r = stale_report(paths)                                   # validated checks only
x = stale_report(paths, terms=["Melumad", "Kestin"],      # candidates to eyeball
                 experimental=True)

entry = draft_entry(
    title="Dissociation test",
    tool="Claude Science",
    done=["Re-coded 50 studies on outcome type, direction, and AI veracity"],
    decisions=["Added a third axis unprompted; without it the test confirms itself"],
    learned=["Hypothesis fails (OR 1.20, p = 1.000); the only predictor is sabotage design"],
    open_items=["Causal-identification ledger still unrun"])
print(entry)
append_entry("~/projects/thing/SESSION-LOG.md", entry)

p = propose_plan_update("~/projects/thing/PLAN.md",
                        status_lines=["Dissociation test done — hypothesis fails"],
                        next_action="Run the causal-identification ledger.")
print(p["diff"])       # nothing has been written
```

## Two checks by default, three opt-in

`stale_report(paths)` runs only the checks that fire on planted controls **and** stay quiet on
real prose: broken links and orphans. On the project this was built in they return 0 and 1.

`stale_report(paths, terms=[...], experimental=True)` adds three more. They detect real defects
but carry a high false-positive rate, so their output is a list of candidates to eyeball, never a
defect list. `check_number_conflicts` is only usable with explicit `terms`; its automatic term
selection produced 384 junk rows on real data.

Aggregate files — transcripts, full-run exports — are excluded by default (`AGGREGATE_HINTS`).
They contain every number and phrase in the project, so they match every similarity check and
poison all three experimental ones. Pass `exclude=[]` to include them.

## The five checks

**`check_links`** — markdown links to relative paths that do not exist. Catches the breakage that
follows any reorganisation.

**`check_orphans`** — files no document mentions. Read it as a prompt, not a verdict: data files
legitimately go unmentioned.

**`check_number_conflicts(paths, terms=None)`** — the same entity carrying different numbers in
different documents. Default terms are capitalised tokens appearing in at least two files; pass
`terms=[...]` to target specific ones and cut noise. URLs and DOIs are stripped first so their
digits do not register.

**`check_table_sums`** — a prose total near a markdown table whose numeric column sums to
something else. Number words up to fifty are matched as well as digits, because the error usually
appears as "Thirteen of the twenty", not "13".

**`check_stale_next_actions`** — a next-action section in a plan naming work that a log elsewhere
records as done. Reads the whole section body, not the heading.

## Validate before you trust a clean report

Every check here failed silently at least once during construction, and the real project looked
clean while three of five were broken. Before trusting an empty report, plant a positive control:
a markdown file with a link to a nonexistent path, a four-row count table followed by a wrong
total in prose, the same name with two different numbers in two files, and a plan whose next
action a log calls complete. Confirm each check fires, then run for real.

`collect_docs` raises if a path is missing or unreadable rather than returning an empty list —
a clean report from a folder the kernel cannot see is the worst output this could produce.

## What it does not do

No interpretation. It will not tell you which of two conflicting numbers is right, whether an
orphan should be deleted, or whether a stale next-action is actually still wanted. It surfaces
the candidates; you decide.
