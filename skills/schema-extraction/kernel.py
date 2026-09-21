"""schema-extraction — design an evidence-review schema for a project, then extract to it.

The 26-column table this skill grew out of is not a template — it is what one project's question
and corpus produced. This skill helps arrive at the right schema for a NEW project, in two layers:

  * an INTEGRITY FLOOR (fixed, every project keeps it) — the columns that let you trust and trace
    a record: provenance, resolvable links, full-text-vs-abstract basis, the study's own hedges.
  * a VARIABLE LAYER (driven by the question and by what the corpus can actually fill) — the
    columns a particular question warrants, minus the ones the corpus would leave mostly empty.

Choosing the variable layer is judgment; the floor and the availability check that informs the
choice are mechanical. Extraction (reading a paper to fill fields) is an LLM/judgment step.

Functions:
    integrity_floor()                                   -> {field: why_it_is_non_negotiable}
    field_availability(corpus_csv_path, candidate_fields=None) -> [ {field, filled, total, frac, mostly_empty} ]
    fields_for(record_type)                             -> {"required":[...], "optional":[...], "na":[...]}
    validate_row(row, record_type=None)                 -> (record_type, [ {field, issue, severity} ])
    suggest_schema(question, corpus_csv_path=None)       -> {"floor":[...], "variable":[...], "availability":[...]}
    extract_study(text, metadata, fields)               -> row dict  (LLM step; needs host.llm)
    append_row(row, csv_path)                            -> {"appended":bool, "issues":[...]}

record_type is one of: empirical | synthesis | survey | perspective | correction.
"""

# ---- top-level literals only (sidecar rule: no calls, no underscore-prefixed names) ----
FLOOR = {
    "study_id": "stable key so rows join and dedup reliably",
    "citation": "human-readable identifier",
    "title": "what the paper is",
    "authors": "attribution",
    "year": "when",
    "venue": "where published (journal/conference/repository)",
    "pub_status": "peer-reviewed / preprint / conference — the credibility signal",
    "text_basis": "full-text vs abstract-only — makes a blank field interpretable",
    "doi": "canonical identifier",
    "url": "a resolvable link, not just a bare DOI",
    "open_access_pdf": "a readable copy where one exists",
    "record_type": "empirical/synthesis/survey/perspective/correction — drives conditional fields",
    "key_finding": "what the study reports, in its own terms",
    "caveat_flags": "the study's own hedges and limitations, preserved",
}

VARIABLE_MENU = {
    "design": "relevant for any study that has a method (empirical, survey, synthesis)",
    "participants_n": "relevant when the unit is people and the question is about sample size",
    "sample_description": "free-text sample detail (arms, per-condition n)",
    "population": "who was studied",
    "population_type": "student / general-adult / professional / clinical / mixed — needed to ask 'who'",
    "ai_exposure": "what AI tool/condition — needed for any AI-effect question",
    "measures": "what was measured and how",
    "effect_size": "relevant when the corpus reports quantitative effects",
    "duration_class": "single-session / days-weeks / months — needed for durability questions",
    "comparison_condition": "none / within / between / pre-post — the backbone of a causal read",
    "unassisted_outcome_flag": "was the AI present at measurement — needed for learning-vs-assisted questions",
    "randomised": "was the comparison randomised",
    "causal_language": "the inference the design licenses (cause/association/description/pooled)",
}

# fields genuinely N/A for a record_type (validated against a real corpus: NOT design/n/effect_size
# for surveys — surveys have those; only the experiment-specific fields are truly n/a)
NA_BY_TYPE = {
    "empirical": [],
    "survey": ["unassisted_outcome_flag", "randomised"],
    "synthesis": ["unassisted_outcome_flag", "randomised", "participants_n"],
    "perspective": ["unassisted_outcome_flag", "randomised", "participants_n",
                    "effect_size", "design", "measures"],
    "correction": ["unassisted_outcome_flag", "randomised", "participants_n",
                   "effect_size", "design", "measures"],
}

REQUIRED_EXTRA = {
    "empirical": ["design", "participants_n", "population", "ai_exposure", "measures", "causal_language"],
    "survey": ["population", "measures", "participants_n"],
    "synthesis": ["design", "causal_language"],
    "perspective": [],
    "correction": [],
}

CONTROLLED_VOCAB = {
    "record_type": ["empirical", "synthesis", "survey", "perspective", "correction"],
    "population_type": ["student", "general-adult", "professional", "clinical", "mixed", "not-reported"],
    "comparison_condition": ["none", "within-subject", "between-subject", "pre-post", "not-reported"],
    "causal_language": ["causal", "associational", "descriptive", "pooled"],
    "duration_class": ["single-session", "days-weeks", "months", "not-determinable", "n/a"],
    "text_basis": ["full-text", "abstract-only"],
}

NOT_REPORTED = "not reported in retrieved text"


def is_empty(v):
    import math
    return v is None or (isinstance(v, float) and math.isnan(v)) or str(v).strip() == ""


def is_na_sentinel(v):
    s = str(v).strip().lower()
    return s.startswith("n/a") or "not applicable" in s


def is_not_reported(v):
    return "not reported" in str(v).lower()


def is_substantive(v):
    s = str(v).strip().lower()
    if is_empty(v) or is_na_sentinel(v) or is_not_reported(v):
        return False
    return s not in ("false", "0", "0.0", "no", "nan")


def integrity_floor():
    """The fixed columns every evidence project keeps, with why each is non-negotiable."""
    return dict(FLOOR)


def derive_record_type(hint):
    """Best-effort record_type from a free-text hint (e.g. a legacy duration_class)."""
    h = str(hint).lower()
    for k, t in [("synthesis", "synthesis"), ("meta-analysis", "synthesis"),
                 ("survey", "survey"), ("correction", "correction"),
                 ("perspective", "perspective"), ("conceptual", "perspective")]:
        if k in h:
            return t
    return "empirical"


def fields_for(record_type):
    """Return the required / optional / n-a field split for a record_type."""
    rt = record_type if record_type in NA_BY_TYPE else "empirical"
    na = NA_BY_TYPE[rt]
    required = list(FLOOR.keys()) + [f for f in REQUIRED_EXTRA[rt] if f not in na]
    optional = [f for f in VARIABLE_MENU if f not in required and f not in na]
    return {"required": required, "optional": optional, "na": na}


def field_availability(corpus_csv_path, candidate_fields=None):
    """Mechanical: for each candidate field, the fraction of records that actually populate it
    (non-empty, non-sentinel). This is what 'depends on what the corpus can fill' becomes in code.
    A field with a low fraction is one to reconsider before committing to the schema."""
    import csv
    rows = list(csv.DictReader(open(corpus_csv_path, newline='', encoding='utf-8', errors='ignore')))
    total = len(rows) or 1
    cols = candidate_fields or (list(rows[0].keys()) if rows else [])
    out = []
    for f in cols:
        filled = sum(1 for r in rows if is_substantive(r.get(f)))
        frac = round(filled / total, 3)
        out.append({"field": f, "filled": filled, "total": len(rows),
                    "frac": frac, "mostly_empty": frac < 0.34})
    return sorted(out, key=lambda x: x["frac"])


def validate_row(row, record_type=None):
    """Check a filled row against the schema. Reports; does not fix.
    Severity: 'error' = missing required floor field, wrong link, or an n/a-for-type field carrying
    a substantive value; 'warn' = missing OA link or a controlled-vocab value outside the set."""
    rt = record_type or derive_record_type(row.get("record_type") or row.get("duration_class", ""))
    spec = fields_for(rt)
    issues = []
    for f in ["citation", "title", "authors", "year", "venue", "pub_status",
              "text_basis", "doi", "url", "key_finding"]:
        if f not in row or is_empty(row.get(f)):
            issues.append({"field": f, "issue": "missing required floor field", "severity": "error"})
    if "open_access_pdf" in row and is_empty(row.get("open_access_pdf")):
        issues.append({"field": "open_access_pdf", "issue": "no open-access link", "severity": "warn"})
    for f in spec["na"]:
        if is_substantive(row.get(f)):
            issues.append({"field": f,
                           "issue": "n/a for {} but carries {!r}".format(rt, str(row.get(f))[:40]),
                           "severity": "error"})
    for f, allowed in CONTROLLED_VOCAB.items():
        v = row.get(f)
        if not is_empty(v) and not is_na_sentinel(v) and str(v).strip().lower() not in allowed:
            issues.append({"field": f, "issue": "value {!r} not in controlled vocab".format(str(v)[:40]),
                           "severity": "warn"})
    return rt, issues


def suggest_schema(question, corpus_csv_path=None):
    """Propose a schema = fixed integrity floor + the variable fields a question warrants, annotated
    with corpus availability where a sample is given. The floor and availability are mechanical; the
    'which variable fields' recommendation uses host.llm when available and otherwise returns the full
    menu for you to choose from. It proposes; you decide."""
    proposal = {"floor": list(FLOOR.keys()),
                "variable": [{"field": f, "relevant_when": why} for f, why in VARIABLE_MENU.items()],
                "availability": []}
    if corpus_csv_path:
        proposal["availability"] = field_availability(corpus_csv_path, list(VARIABLE_MENU.keys()))
    try:
        prompt = ("A research question and a menu of candidate evidence-table columns follow. "
                  "Return ONLY the column names (comma-separated) whose presence the question "
                  "genuinely warrants. Question: " + str(question) + " || Menu: "
                  + "; ".join("{}={}".format(f, w) for f, w in VARIABLE_MENU.items()))
        rec = host.llm(prompt)["text"]  # noqa: F821  (host is injected in the Claude Science kernel)
        picks = [p.strip() for p in rec.replace("\n", ",").split(",") if p.strip() in VARIABLE_MENU]
        if picks:
            proposal["recommended_for_question"] = picks
    except Exception:
        proposal["recommended_for_question"] = None  # no host.llm here — choose from the menu
    return proposal


def extract_study(text, metadata, fields):
    """LLM step: read a paper's text and fill `fields` into a row, enforcing the sentinel discipline
    ('not reported in retrieved text' for applicable-but-missing; 'n/a (<record_type>)' for
    inapplicable). Requires host.llm (Claude Science). metadata seeds the floor fields you already
    know (doi, url, title, ...). Validate the returned row with validate_row before appending."""
    import json
    schema_fields = list(dict.fromkeys(list(FLOOR.keys()) + list(fields)))
    vocab = "; ".join("{} one of [{}]".format(k, ", ".join(v)) for k, v in CONTROLLED_VOCAB.items())
    prompt = ("Extract one evidence-table row from the study text. Fill exactly these fields as a "
              "JSON object: " + ", ".join(schema_fields) + ". "
              "For these fields use only the allowed values: " + vocab + ". "
              "Use the literal string '" + NOT_REPORTED + "' for a field that applies but the text "
              "does not state. Use 'n/a (<record_type>)' for a field that does not apply to this "
              "record type. Do not invent numbers. Known metadata: " + json.dumps(metadata)
              + " || STUDY TEXT: " + str(text)[:12000])
    resp = host.llm(prompt)["text"]  # noqa: F821
    start, end = resp.find("{"), resp.rfind("}")
    row = json.loads(resp[start:end + 1]) if start >= 0 else {}
    row.update({k: v for k, v in metadata.items() if v})
    return row


def append_row(row, csv_path):
    """Validate then append a row to a corpus CSV. Refuses on any error-severity issue; returns the
    issue list either way."""
    import csv
    import os
    rt, issues = validate_row(row)
    if any(i["severity"] == "error" for i in issues):
        return {"appended": False, "issues": issues, "record_type": rt}
    exists = os.path.exists(csv_path)
    with open(csv_path, "a", newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(row.keys()))
        if not exists:
            w.writeheader()
        w.writerow(row)
    return {"appended": True, "issues": issues, "record_type": rt}
