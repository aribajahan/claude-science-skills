---
name: fulltext-acquisition
description: "For a list of DOIs, locate an open-access full-text copy and fetch it. Uses OpenAlex to find the best OA location, resolves PubMed Central and arXiv routes, and extracts text (XML for PMC, PDF via pypdfium2 for arXiv and OA PDFs). Reports a route per DOI and, when a fetch fails, says why — blocked/paywalled domain, no OA copy, or parse error — rather than returning nothing silently. Use when building or upgrading an evidence corpus and you need full text instead of abstracts, and want an honest account of what is and isn't reachable."
---

# fulltext-acquisition

Turns "abstract-only" into "here is where each paper's full text is, and here is the text where a
route exists." It finds the **open-access** copy that is actually reachable rather than scraping
paywalled PDFs, and it is explicit about failure: a blocked domain, a closed-access paper, or a
parse error each come back with a stated reason.

## Setup

`find_fulltext` uses the OpenAlex API — set `OPENALEX_API_KEY` in the environment (in Claude
Science, declare the credential on the calling cell). No contact email is needed: OpenAlex
aggregates the OA-location data (including Unpaywall's) and is the single locator. `fetch_text`
uses `pypdfium2` for PDF extraction.

## Routes

| route | source | reliably fetchable in a sandbox? |
|---|---|---|
| `arxiv` | arXiv PDF | yes |
| `pmc` | PubMed Central full-text XML | yes |
| `oa_pdf` | an OA PDF on a repository/publisher host | **often no** — publisher domains are usually blocked |
| `none` | no OA copy located | — |

## Functions

- `find_fulltext(dois, api_key=None) -> list` — per DOI:
  `{doi, is_oa, oa_status, host_type, pdf_url, landing_url, arxiv_id, pmcid, route, note}`.
  Locates; does not download.
- `fetch_text(entry_or_url) -> dict` — fetch + extract for one `find_fulltext` entry (or a raw URL).
  `{ok:True, route, source, chars, text}` on success; `{ok:False, route, error}` with a plain reason
  on failure (e.g. `"blocked or unreachable in this sandbox (likely a paywalled publisher domain)"`).
- `coverage_summary(results, corpus_csv=None, text_basis_col="text_basis") -> dict` — how much of a
  corpus is OA-reachable, split into `reachable_any_oa` and `reliably_fetchable` (arXiv+PMC only).
  Given a corpus CSV, also reports how many `abstract-only` rows have a reliably-fetchable full text
  vs. an OA-PDF that may be blocked.

## Usage

```python
skill({"skill": "fulltext-acquisition"})

res = find_fulltext(my_dois)                       # needs OPENALEX_API_KEY on the cell
summary = coverage_summary(res, "corpus.csv")      # what could be upgraded from abstract-only

for e in res:
    if e["route"] in ("arxiv", "pmc"):             # the reliably-fetchable routes
        got = fetch_text(e)
        if got["ok"]:
            open(f"{e['pmcid'] or e['arxiv_id']}.txt", "w").write(got["text"])
        else:
            print(e["doi"], "->", got["error"])     # honest failure reason
```

## Limitations (state these honestly)

- **"Reachable" is not "fetchable here."** OpenAlex may report an OA PDF (`oa_pdf`) whose host is a
  publisher domain blocked in a sandbox. `coverage_summary` separates `reliably_fetchable`
  (arXiv+PMC) from the OA-PDF count for this reason; `fetch_text` reports the block plainly. An
  `oa_pdf` that fails here is usually fetchable outside the sandbox or once the domain is allowed.
- `find_fulltext` locates the *best* OA copy OpenAlex knows about; a paper with no OA copy returns
  `route="none"` — the skill does not defeat a paywall.
- PMC full text is available only for the OA subset; a resolvable PMCID outside it returns a stated
  "no full-text XML" error.
- Extracted PDF text is raw (headers, line breaks, reference numerals inline); clean before parsing
  numbers out of it.
