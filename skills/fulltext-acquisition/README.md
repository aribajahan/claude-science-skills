# fulltext-acquisition

An example [Claude Science](https://www.anthropic.com) skill: for a list of DOIs, locate an
open-access full-text copy and fetch it — turning "abstract-only" into full text where an OA route
exists. Built from a real review of AI's effect on adult cognition, where many studies had been
read from the abstract only because publisher PDFs are blocked.

> **Portability note.** A *Claude Science* skill: `find_fulltext` uses the OpenAlex API and
> `fetch_text` uses `pypdfium2`. It demonstrates the pattern; it is not a drop-in Claude Code skill.

## The idea, and the honest part

It finds the **open-access** copy that is actually reachable (arXiv, PubMed Central, or an OA
repository) rather than scraping paywalls, and it is explicit about failure. When a fetch fails it
says *why* — a blocked/paywalled domain, no OA copy, or a parse error — instead of silently
returning nothing.

The honesty that matters most: **"an OA copy exists" is not "I can fetch it from here."** OpenAlex
often reports an OA PDF whose host is a publisher domain that a sandbox blocks. The skill separates
what is *reliably fetchable* (arXiv + PMC) from OA PDFs that may be blocked, so the coverage number
never overstates what you'll actually get.

## What it did on the source project (46 DOIs)

- **43** flagged open-access; **37** had a usable OA route (18 PubMed Central, 7 arXiv, 12 OA-PDF).
- **25 reliably fetchable in-sandbox** (arXiv + PMC). arXiv and PMC fetched cleanly — e.g. 66K
  characters from one arXiv preprint, 91K from one PMC article.
- Of the **22 abstract-only rows**: **13 have an OA copy** — but only **1** is reliably fetchable
  from inside the sandbox; the other **12** are OA PDFs on publisher domains blocked here (fetchable
  outside the sandbox or once the domain is allowed), and **9** have no OA copy at all. So the
  abstract-only gap is mostly a *network* limitation, not an OA-availability one — a finding the
  skill surfaces rather than hides.
- The blocked-domain case returned exactly:
  `"blocked or unreachable in this sandbox (likely a paywalled publisher domain)"`.

## Functions

`find_fulltext(dois)` (locate), `fetch_text(entry)` (fetch + extract, honest failure),
`coverage_summary(results, corpus_csv)` (reachable vs. reliably-fetchable, and how much of an
abstract-only set is recoverable). See `SKILL.md` for signatures and limitations.
