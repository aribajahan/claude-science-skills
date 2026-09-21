"""corpus-integrity — mechanical checks for an evidence corpus and a draft written from it.

Three jobs, none of which decides what is relevant, credible, or in-scope. Every function
REPORTS and RANKS by objective signals; the inclusion, relevance and credibility calls stay
with you. That report-not-gate line is what keeps this a mechanical integrity skill.

Functions:
    check_claims(draft_path, source_csv_paths)      -> {"unmatched":[...], "label_mismatches":[...]}
    check_provenance(dois, api_key=None)            -> [ {doi, retracted, is_preprint, venue, citations, note} ]
    audit_coverage(corpus_dois, api_key=None, ...)  -> [ {corpus_refs, cited_by_count, year, title, doi} ]
    reproducibility_log(search_terms, databases, date_cutoff, counts) -> markdown str

Data sources: OpenAlex (retraction flag, citation count, citation graph) and Crossref (open).
OpenAlex requires an API key. It is read from the OPENALEX_API_KEY environment variable; never
hardcode it. In Claude Science, declare the credential on the calling cell so the variable is
present. Set your own key in your environment before use.
"""

# ---- top-level literals only (sidecar rule: no calls, no underscore-prefixed names) ----
YEAR_RE = r'^(19|20)\d{2}$'
NUM_PATTERNS = [
    r"(?:Cohen'?s?\s*d|Hedges'?\s*g|\u03b2|beta|OR|RR|\bd\b|\bg\b|\br\b)\s*=\s*(-?\d+\.?\d*)",
    r'(-?\d+\.?\d*)\s*%',
    r'\b[nN]\s*=\s*(\d[\d,]*)',
    r'(-?\d+\.\d+)',
    r'\b(\d{2,}(?:,\d{3})*)\b',
]
EFFECT_LABEL_RE = r"(cohen'?s?\s*d|hedges'?\s*g|\bd\b|\bg\b)\s*=\s*(-?\d+\.?\d*)"
OPENALEX_WORKS = "https://api.openalex.org/works"


def norm_num(s):
    """Normalise a numeric token to a rounded float, or None if it isn't one."""
    try:
        return round(float(str(s).replace(',', '')), 3)
    except Exception:
        return None


def strip_refs(text):
    """Remove markdown link targets, bare URLs, inline DOIs and arXiv ids so their digits
    are not mistaken for quantitative claims."""
    import re
    text = re.sub(r'\]\([^)]*\)', '] ', text)
    text = re.sub(r'https?://\S+', ' ', text)
    text = re.sub(r'10\.\d{4,9}/\S+', ' ', text)
    text = re.sub(r'\b\d{4}\.\d{4,5}\b', ' ', text)
    return text


def split_sentences(text):
    import re
    return re.split(r'(?<=[.!?])\s+', text)


def extract_numbers(text):
    """Return the set of normalised values that look like quantitative claims
    (labelled stats, percentages, n=counts, decimals, integers >= 10). Years are excluded."""
    import re
    vals = set()
    for pat in NUM_PATTERNS:
        for m in re.finditer(pat, text, re.I):
            raw = m.group(m.lastindex)
            if re.match(YEAR_RE, raw.replace(',', '')):
                continue
            v = norm_num(raw)
            if v is not None:
                vals.add(v)
    return vals


def csv_all_text(path):
    """Concatenate every cell of a CSV into one searchable string (stdlib only)."""
    import csv
    parts = []
    with open(path, newline='', encoding='utf-8', errors='ignore') as f:
        for row in csv.reader(f):
            parts.extend(row)
    return " ".join(parts)


def effectsize_label_flags(draft_text, source_text):
    """Best-effort: flag a value the draft attaches to one effect-size label (d/g) while the
    source records the same value under the other label. Bounded by what the source text stores."""
    import re

    def pairs(t):
        res = {}
        for m in re.finditer(EFFECT_LABEL_RE, t, re.I):
            lab = m.group(1).lower()
            lab = 'd' if lab.endswith('d') else 'g'
            v = norm_num(m.group(2))
            if v is not None:
                res.setdefault(v, set()).add(lab)
        return res

    dp, sp = pairs(draft_text), pairs(source_text)
    flags = []
    for val, labs in dp.items():
        if val in sp and not (labs & sp[val]):
            flags.append({"value": val,
                          "draft_label": sorted(labs),
                          "source_label": sorted(sp[val])})
    return flags


def check_claims(draft_path, source_csv_paths):
    """Trace every quantitative claim in a prose draft back to the source corpus.

    draft_path: path to the prose draft (markdown/text).
    source_csv_paths: list of CSV paths that make up the corpus (pass ALL of them — a number
                      is 'unmatched' only if it is absent from every source table).

    Returns {"unmatched": [{value, sentence}], "label_mismatches": [{value, draft_label, source_label}]}.
    Reports; it does not decide. A number in 'unmatched' may be a legitimate prose aggregate
    (a total, a computed percentage) rather than an error — you judge.
    """
    import re
    draft_raw = open(draft_path, encoding='utf-8', errors='ignore').read()
    draft = strip_refs(draft_raw)
    source_text = " ".join(csv_all_text(p) for p in source_csv_paths)
    known = extract_numbers(source_text)

    findings, seen = [], set()
    for sent in split_sentences(draft):
        for pat in NUM_PATTERNS:
            for m in re.finditer(pat, sent, re.I):
                raw = m.group(m.lastindex)
                if re.match(YEAR_RE, raw.replace(',', '')):
                    continue
                v = norm_num(raw)
                if v is None:
                    continue
                if v in known or round(v) in known or norm_num(round(v, 1)) in known:
                    continue
                key = (raw, sent[:80])
                if key in seen:
                    continue
                seen.add(key)
                findings.append({"value": raw,
                                 "sentence": re.sub(r'\s+', ' ', sent).strip()[:180]})
    return {"unmatched": findings,
            "label_mismatches": effectsize_label_flags(draft, source_text)}


def check_provenance(dois, api_key=None):
    """Look up retraction status, preprint status, venue and citation count for a list of DOIs.

    Uses OpenAlex (primary; carries the retraction flag) and reports what it finds. A clean
    result means 'no retraction found', not a guarantee that none exists. DOIs absent from
    OpenAlex are returned with note='not found in OpenAlex' — verify those by hand.
    """
    import os
    import requests
    api_key = api_key or os.environ.get("OPENALEX_API_KEY")
    clean = [d.strip().lower() for d in dois if isinstance(d, str) and d.strip()]
    rows = {}
    for i in range(0, len(clean), 50):
        chunk = clean[i:i + 50]
        r = requests.get(OPENALEX_WORKS,
                         params={"filter": "doi:" + "|".join(chunk),
                                 "per_page": 50, "api_key": api_key}, timeout=60)
        r.raise_for_status()
        for w in r.json().get("results", []):
            d = (w.get("doi") or "").replace("https://doi.org/", "").lower()
            src = (w.get("primary_location") or {}).get("source") or {}
            rows[d] = {"retracted": w.get("is_retracted"),
                       "type": w.get("type"),
                       "is_preprint": (src.get("type") == "repository") or (w.get("type") == "preprint"),
                       "venue": src.get("display_name"),
                       "citations": w.get("cited_by_count"),
                       "note": ""}
    out = []
    for d in clean:
        out.append({"doi": d, **rows.get(d, {"retracted": None, "type": None,
                    "is_preprint": None, "venue": None, "citations": None,
                    "note": "not found in OpenAlex"})})
    return out


def audit_coverage(corpus_dois, api_key=None, top_n=15, min_refs=2):
    """Surface papers the corpus CITES frequently but does not INCLUDE (a co-citation gap),
    ranked by how many corpus papers reference each. Objective signal only — it ranks
    candidates; you decide which are in scope. Pass ALL corpus CSVs' DOIs as corpus_dois.
    """
    import os
    import requests
    api_key = api_key or os.environ.get("OPENALEX_API_KEY")
    clean = [d.strip().lower() for d in corpus_dois if isinstance(d, str) and d.strip()]
    corpus_ids, refs = set(), {}
    for i in range(0, len(clean), 50):
        r = requests.get(OPENALEX_WORKS,
                         params={"filter": "doi:" + "|".join(clean[i:i + 50]),
                                 "per_page": 50, "select": "id,doi,referenced_works",
                                 "api_key": api_key}, timeout=60)
        r.raise_for_status()
        for w in r.json().get("results", []):
            corpus_ids.add(w["id"])
            for rid in (w.get("referenced_works") or []):
                refs[rid] = refs.get(rid, 0) + 1
    gaps = sorted(((rid, c) for rid, c in refs.items()
                   if rid not in corpus_ids and c >= min_refs),
                  key=lambda x: -x[1])[:top_n]
    meta = {}
    ids = [g[0].split("/")[-1] for g in gaps]
    for i in range(0, len(ids), 50):
        if not ids[i:i + 50]:
            continue
        r = requests.get(OPENALEX_WORKS,
                         params={"filter": "openalex:" + "|".join(ids[i:i + 50]),
                                 "per_page": 50,
                                 "select": "id,title,publication_year,cited_by_count,doi",
                                 "api_key": api_key}, timeout=60)
        r.raise_for_status()
        meta.update({w["id"]: w for w in r.json().get("results", [])})
    out = []
    for rid, c in gaps:
        m = meta.get(rid, {})
        out.append({"corpus_refs": c,
                    "cited_by_count": m.get("cited_by_count"),
                    "year": m.get("publication_year"),
                    "title": (m.get("title") or "[metadata unavailable in OpenAlex]")[:90],
                    "doi": (m.get("doi") or "").replace("https://doi.org/", ""),
                    "openalex_id": rid.split("/")[-1]})
    return out


def reproducibility_log(search_terms, databases, date_cutoff, counts):
    """Format a plain-text reproducibility record so a corpus's boundaries are explicit.

    search_terms: list[str]; databases: list[str]; date_cutoff: str; counts: dict.
    """
    lines = ["## Corpus reproducibility log", "",
             "**Date cutoff:** " + str(date_cutoff),
             "**Databases queried:** " + ", ".join(databases), "",
             "**Search terms:**"]
    lines += ["  - " + str(t) for t in search_terms]
    lines += ["", "**Counts:**"]
    lines += ["  - {}: {}".format(k, v) for k, v in counts.items()]
    return "\n".join(lines)


def check_denominators(draft_path, source_csv_paths):
    """Resolve every 'N of M' denominator in a draft against the row counts of the source tables.

    Catches the failure where N and M come from different sets — e.g. "24 of 50", with the
    numerator from a 46-row table and the denominator from a 50-study set. For each construction it
    reports which source table(s) have exactly M rows, flags an M that matches no table, and flags an
    impossible N > M. Reports candidates; does not gate — a legitimate M may be a subset defined in
    prose rather than a whole table.
    """
    import re
    import csv
    draft = strip_refs(open(draft_path, encoding='utf-8', errors='ignore').read())
    counts = {}
    for p in source_csv_paths:
        rows = list(csv.reader(open(p, newline='', encoding='utf-8', errors='ignore')))
        counts[p.split("/")[-1]] = max(0, len(rows) - 1)  # minus header row
    pat = re.compile(r'(\d[\d,]*)\s*(?:of|/|out of)\s*(?:the\s+)?(\d[\d,]*)', re.I)
    out, seen = [], set()
    for m in pat.finditer(draft):
        n, big = norm_num(m.group(1)), norm_num(m.group(2))
        if n is None or big is None or big < 2:
            continue
        if 1900 <= big <= 2100:          # a year, not a denominator
            continue
        key = (m.group(1), m.group(2))
        if key in seen:
            continue
        seen.add(key)
        matching = sorted(fn for fn, c in counts.items() if c == int(big))
        near = ""
        if not matching and counts:
            fn_close = min(counts, key=lambda f: abs(counts[f] - int(big)))
            c_close = counts[fn_close]
            if c_close and abs(c_close - int(big)) / c_close <= 0.15:
                near = " — CLOSE to {} ({} rows): possible denominator confusion".format(fn_close, c_close)
        if n > big:
            status = "impossible: N > M"
        elif matching:
            status = "M matches source table(s): " + ", ".join(matching)
        else:
            status = "M matches NO source table" + near
        ctx = re.sub(r'\s+', ' ', draft[max(0, m.start() - 55):m.end() + 55]).strip()
        out.append({"claim": "{} of {}".format(m.group(1), m.group(2)),
                    "n": int(n), "m": int(big), "matching_tables": matching,
                    "status": status, "context": ctx[:140],
                    "source_table_rows": dict(counts)})
    return out
