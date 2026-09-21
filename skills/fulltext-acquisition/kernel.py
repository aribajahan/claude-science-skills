"""fulltext-acquisition — locate an open-access full-text copy for a list of DOIs, and fetch it.

The problem it fixes: in the review this skill came from, 28 of 50 studies were read from the
abstract only because publisher PDFs are blocked. This skill finds the OPEN-ACCESS route
(arXiv, PubMed Central, an OA repository) that is actually reachable, reports where each paper's
full text is, and fetches the text where a route exists.

It reports; it does not gate. When a fetch fails it says WHY — blocked/paywalled domain, no OA
copy, or a parse error — rather than silently returning nothing.

Functions:
    find_fulltext(dois, api_key=None)        -> [ {doi, is_oa, oa_status, host_type, pdf_url,
                                                   landing_url, arxiv_id, pmcid, route, note} ]
    fetch_text(entry_or_url)                 -> {ok, route, source, chars, text} | {ok:False, route, error}
    coverage_summary(results, corpus_csv=None, text_basis_col="text_basis") -> dict

Routes: OpenAlex locates the best OA copy (it aggregates Unpaywall data and needs no email, only
the OPENALEX_API_KEY env var); arXiv and PubMed Central are the reachable fetch routes; a generic
OA pdf_url is attempted but publisher domains are usually blocked in a sandbox (reported as such).
"""

OPENALEX_WORKS = "https://api.openalex.org/works"
IDCONV = "https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/"
EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
FETCH_ROUTES = ["arxiv", "pmc", "oa_pdf"]


def resolve_pmcids(dois):
    """Map DOIs -> PMCID via NCBI idconv (batched). Missing/closed DOIs simply absent from the map."""
    import requests
    out = {}
    for i in range(0, len(dois), 150):
        chunk = dois[i:i + 150]
        try:
            r = requests.get(IDCONV, params={"ids": ",".join(chunk), "format": "json",
                                             "tool": "fulltext-acquisition"}, timeout=60)
            for rec in r.json().get("records", []):
                d = (rec.get("doi") or "").lower()
                if rec.get("pmcid"):
                    out[d] = rec["pmcid"]
        except Exception:
            pass  # idconv is best-effort; a failure just means no PMC route for these
    return out


def pdf_to_text(content):
    """Extract text from PDF bytes with pypdfium2 (all pages)."""
    import io
    import pypdfium2 as pdfium
    doc = pdfium.PdfDocument(io.BytesIO(content))
    parts = []
    for i in range(len(doc)):
        parts.append(doc[i].get_textpage().get_text_range())
    return "\n".join(parts)


def classify_fetch_error(e):
    """Turn an exception into a plain-language reason, distinguishing a sandbox block from a real error."""
    s = str(e).lower()
    if any(k in s for k in ("proxy", "403", "blocked", "max retries", "connection", "timed out", "timeout")):
        return "blocked or unreachable in this sandbox (likely a paywalled publisher domain)"
    return "fetch/parse failed: " + type(e).__name__


def find_fulltext(dois, api_key=None):
    """Locate the best open-access copy for each DOI (OpenAlex + PMC id resolution). Reports a
    route per DOI: 'arxiv' | 'pmc' | 'oa_pdf' | 'none'. Does not download — that is fetch_text."""
    import os
    import re
    import requests
    api_key = api_key or os.environ.get("OPENALEX_API_KEY")
    clean = [d.strip().lower() for d in dois if isinstance(d, str) and d.strip()]
    oa = {}
    for i in range(0, len(clean), 50):
        r = requests.get(OPENALEX_WORKS,
                         params={"filter": "doi:" + "|".join(clean[i:i + 50]), "per_page": 50,
                                 "api_key": api_key,
                                 "select": "id,doi,open_access,best_oa_location"}, timeout=60)
        r.raise_for_status()
        for w in r.json().get("results", []):
            d = (w.get("doi") or "").replace("https://doi.org/", "").lower()
            oa[d] = w
    pmc = resolve_pmcids(clean)
    out = []
    for d in clean:
        entry = {"doi": d, "is_oa": None, "oa_status": None, "host_type": None,
                 "pdf_url": None, "landing_url": None, "arxiv_id": None,
                 "pmcid": pmc.get(d), "route": "none", "note": ""}
        w = oa.get(d)
        if not w:
            entry["note"] = "not found in OpenAlex"
            out.append(entry)
            continue
        oad = w.get("open_access") or {}
        best = w.get("best_oa_location") or {}
        entry["is_oa"] = oad.get("is_oa")
        entry["oa_status"] = oad.get("oa_status")
        entry["host_type"] = (best.get("source") or {}).get("type")
        entry["pdf_url"] = best.get("pdf_url")
        entry["landing_url"] = best.get("landing_page_url")
        blob = (entry["pdf_url"] or "") + " " + (entry["landing_url"] or "")
        m = re.search(r'arxiv\.org/(?:abs|pdf)/([0-9]+\.[0-9]+)', blob)
        if d.startswith("10.48550/arxiv."):
            entry["arxiv_id"] = d.split("arxiv.")[-1]
        elif m:
            entry["arxiv_id"] = m.group(1)
        if entry["arxiv_id"]:
            entry["route"] = "arxiv"
        elif entry["pmcid"]:
            entry["route"] = "pmc"
        elif entry["pdf_url"]:
            entry["route"] = "oa_pdf"
            entry["note"] = "OA pdf on a " + str(entry["host_type"]) + " host; may be blocked in a sandbox"
        else:
            entry["route"] = "none"
            entry["note"] = "no open-access copy found" if not entry["is_oa"] else "OA but no direct link"
        out.append(entry)
    return out


def fetch_text(entry_or_url):
    """Fetch and extract full text for one find_fulltext entry (or a raw pdf/xml URL).
    Returns {ok:True, route, source, chars, text} or {ok:False, route, error} with a plain reason."""
    import re
    import requests
    entry = {"route": "oa_pdf", "pdf_url": entry_or_url} if isinstance(entry_or_url, str) else dict(entry_or_url)
    route = entry.get("route")
    try:
        if route == "arxiv" and entry.get("arxiv_id"):
            url = "https://arxiv.org/pdf/" + entry["arxiv_id"]
            r = requests.get(url, timeout=90)
            r.raise_for_status()
            txt = pdf_to_text(r.content)
            return {"ok": True, "route": "arxiv", "source": url, "chars": len(txt), "text": txt}
        if route == "pmc" and entry.get("pmcid"):
            pid = str(entry["pmcid"]).replace("PMC", "")
            r = requests.get(EFETCH, params={"db": "pmc", "id": pid, "rettype": "xml"}, timeout=90)
            r.raise_for_status()
            body = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", r.text)).strip()
            if len(body) < 500:
                return {"ok": False, "route": "pmc",
                        "error": "PMC has no full-text XML for this id (not in the OA subset)"}
            return {"ok": True, "route": "pmc", "source": "PMC:" + str(entry["pmcid"]),
                    "chars": len(body), "text": body}
        if route == "oa_pdf" and entry.get("pdf_url"):
            r = requests.get(entry["pdf_url"], timeout=90)
            r.raise_for_status()
            txt = pdf_to_text(r.content)
            return {"ok": True, "route": "oa_pdf", "source": entry["pdf_url"],
                    "chars": len(txt), "text": txt}
        return {"ok": False, "route": route,
                "error": "no fetchable open-access route (publisher-only or closed access)"}
    except Exception as e:
        return {"ok": False, "route": route, "error": classify_fetch_error(e)}


def coverage_summary(results, corpus_csv=None, text_basis_col="text_basis"):
    """Summarise how much of a corpus is open-access reachable. If a corpus CSV is given, also report
    how many of its abstract-only rows now have a reachable full text — what this skill would recover."""
    import csv
    by_route = {}
    for r in results:
        by_route[r.get("route")] = by_route.get(r.get("route"), 0) + 1
    reliable_routes = ["arxiv", "pmc"]  # fetch reliably in-sandbox; oa_pdf depends on the host domain
    summ = {"total": len(results),
            "is_oa": sum(1 for r in results if r.get("is_oa")),
            "reachable_any_oa": sum(1 for r in results if r.get("route") in FETCH_ROUTES),
            "reliably_fetchable": sum(1 for r in results if r.get("route") in reliable_routes),
            "by_route": by_route}
    if corpus_csv:
        rows = list(csv.DictReader(open(corpus_csv, newline='', encoding='utf-8', errors='ignore')))
        abstract_only = {(r.get("doi") or "").lower() for r in rows
                         if "abstract" in str(r.get(text_basis_col, "")).lower()}
        res = {r["doi"]: r for r in results}
        reliable = sorted(d for d in abstract_only if res.get(d, {}).get("route") in reliable_routes)
        via_pdf = sorted(d for d in abstract_only if res.get(d, {}).get("route") == "oa_pdf")
        summ["abstract_only_total"] = len(abstract_only)
        summ["abstract_only_reliably_fetchable"] = len(reliable)
        summ["abstract_only_via_oa_pdf_maybe_blocked"] = len(via_pdf)
        summ["abstract_only_reliably_fetchable_dois"] = reliable
    return summ
