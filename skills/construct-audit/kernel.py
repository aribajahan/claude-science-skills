"""construct-audit — for a claimed cognitive outcome, extract how each study actually operationalised
it, and report where one label ("critical thinking", "learning") covers different constructs.

The mechanical core pulls the measures and codes each study on a controlled vocabulary; the
interpretation stays with you. Every code ships with a `gap_note` quoting the record, so it is
checkable. The audit is SINGLE-RATER (model-assisted, human-reviewed, no inter-rater statistic) —
its aggregate is a candidate finding, never a settled classification.

Functions:
    code_constructs(records, id_field="doi", text_fields=None, model=None, max_concurrency=8)
        -> {"coded": [ {id, task, signal, measure, domain, measure_type, instrument_named, gap, gap_note} ],
            "unrecovered": [ids], "vocab_flags": [ ... ]}
    construct_report(coded) -> dict  (domain x gap crosstab, term counts, headline)
    exemplars(coded, n=2)  -> {domain: [ {task, signal, measure, gap, gap_note} ]}

The recode loop (`run_recode`) is a separate function so a future general `corpus-recode` skill can
reuse it with a different axis definition. `code_constructs` is one packaged axis.

Reads the FINDINGS field, not only design/measures: designs can agree where results diverge, so a
construct audit that reads only design reports false convergence.
"""

DOMAIN = ["memory", "learning_transfer", "reasoning_critical", "metacognition",
          "decision_judgment", "attention_effort", "creativity", "domain_skill",
          "brain_physiology", "self_reported_habit", "unclear"]
MEASURE_TYPE = ["performance_with_tool", "performance_without_tool", "product_quality",
                "self_report", "physiological", "behavioural_trace", "synthesis", "unclear"]
GAP = ["none", "product_for_process", "assisted_for_durable", "self_for_actual",
       "proxy_construct", "unclear"]
CONSTRUCT_FIELDS = ["task", "signal", "measure", "domain", "measure_type",
                    "instrument_named", "gap", "gap_note"]
CONSTRUCT_VOCABS = {"domain": DOMAIN, "measure_type": MEASURE_TYPE, "gap": GAP}
DEFAULT_TEXT_FIELDS = ["citation", "cite", "title", "design", "measures",
                       "key_finding", "effect_size", "population"]
GAP_DEFINITIONS = ("gap codes: none; product_for_process (an output was scored, a thinking process "
                   "is claimed); assisted_for_durable (measured with the tool present, a durable "
                   "capacity is claimed); self_for_actual (self-report measured, actual capacity "
                   "claimed); proxy_construct (instrument measures a related but different thing); "
                   "unclear.")


def construct_instruction():
    """The construct-audit coding instruction (built here, not at module top — sidecar rule)."""
    return ("You are auditing how a study operationalises a cognitive-outcome claim. Read the record "
            "INCLUDING ITS FINDINGS and code eight fields. Base the coding on what was actually "
            "MEASURED, not on what the study claims. Fields: "
            "task (what the participant actually did, concrete, <=12 words); "
            "signal (the capacity the study treats that task as evidence about, in its own framing); "
            "measure (what was actually scored; name the instrument if one is given); "
            "domain (one of: " + ", ".join(DOMAIN) + "); "
            "measure_type (one of: " + ", ".join(MEASURE_TYPE) + "); "
            "instrument_named (true or false: is a validated instrument identified); "
            "gap (one of: " + ", ".join(GAP) + "); "
            "gap_note (<=22 words justifying the gap code, quoting the record). " + GAP_DEFINITIONS)


def build_prompt(record, instruction, text_fields):
    import json
    ctx = {}
    for k in text_fields:
        v = record.get(k)
        if v is not None and str(v).strip() and str(v).lower() != "nan":
            ctx[k] = str(v)[:500]
    return instruction + " Return ONLY a JSON object with the coded keys. RECORD: " + json.dumps(ctx)


def parse_obj(text):
    import json
    s, e = text.find("{"), text.rfind("}")
    if s < 0 or e < 0:
        return None
    try:
        return json.loads(text[s:e + 1])
    except Exception:
        return None


def run_recode(records, instruction, out_fields, vocabs, id_field="doi",
               text_fields=None, model=None, max_concurrency=8):
    """Generic recode engine: map an instruction over records, parse a JSON object per record, retry
    the failures once, and report which records never parsed. Returns coded rows + unrecovered ids +
    vocab_flags (values outside a controlled vocabulary — reported, never corrected).

    Kept separate from any one axis so a general corpus-recode skill can reuse it.
    """
    text_fields = text_fields or DEFAULT_TEXT_FIELDS
    model = model or host.reasoning_model()

    def make_reqs(idxs):
        return [{"prompt": build_prompt(records[i], instruction, text_fields),
                 "model": model, "max_tokens": 1200,
                 "thinking": {"type": "disabled"}} for i in idxs]

    coded = [None] * len(records)
    order = list(range(len(records)))
    results = host.llm(make_reqs(order), max_concurrency=max_concurrency)
    retry = []
    for i, res in zip(order, results):
        obj = parse_obj(res.get("text", "")) if isinstance(res, dict) and "error" not in res else None
        if obj is None:
            retry.append(i)
        else:
            coded[i] = obj
    if retry:
        results2 = host.llm(make_reqs(retry), max_concurrency=max_concurrency)
        for i, res in zip(retry, results2):
            obj = parse_obj(res.get("text", "")) if isinstance(res, dict) and "error" not in res else None
            if obj is not None:
                coded[i] = obj

    out, vocab_flags = [], []
    for i, obj in enumerate(coded):
        if obj is None:
            continue
        obj["id"] = records[i].get(id_field) or records[i].get("citation") or records[i].get("cite")
        for f, allowed in vocabs.items():
            val = obj.get(f)
            if val is not None and str(val) not in allowed:
                vocab_flags.append({"id": obj["id"], "field": f, "value": val})
        out.append(obj)
    unrecovered = [(records[i].get(id_field) or records[i].get("citation"))
                   for i in range(len(records)) if coded[i] is None]
    return {"coded": out, "unrecovered": unrecovered, "vocab_flags": vocab_flags}


def code_constructs(records, id_field="doi", text_fields=None, model=None, max_concurrency=8):
    """Code every study on the construct axis (task/signal/measure/domain/measure_type/
    instrument_named/gap/gap_note). records: list of dicts with at least a findings field.
    Returns {coded, unrecovered, vocab_flags}; report `unrecovered` rather than silently coding fewer.
    """
    return run_recode(records, construct_instruction(), CONSTRUCT_FIELDS, CONSTRUCT_VOCABS,
                      id_field=id_field, text_fields=text_fields, model=model,
                      max_concurrency=max_concurrency)


def construct_report(coded):
    """Crosstab domain x gap, per-term counts, and the headline. `coded` is the list of coded dicts
    (pass the `coded` value from code_constructs). Report only — it counts, it does not conclude."""
    rows = coded["coded"] if isinstance(coded, dict) else coded
    n = len(rows)

    def tally(field):
        out = {}
        for r in rows:
            out[r.get(field)] = out.get(r.get(field), 0) + 1
        return dict(sorted(out.items(), key=lambda kv: -kv[1]))

    crosstab = {}
    for r in rows:
        d, g = r.get("domain"), r.get("gap")
        crosstab.setdefault(d, {})
        crosstab[d][g] = crosstab[d].get(g, 0) + 1
    measure_the_claim = sum(1 for r in rows if r.get("gap") == "none")
    without_tool = sum(1 for r in rows if r.get("measure_type") == "performance_without_tool")
    named = sum(1 for r in rows if str(r.get("instrument_named")).lower() == "true")
    return {"total": n,
            "headline": "{} of {} studies measure the capacity they claim (gap = none)".format(measure_the_claim, n),
            "measured_tool_removed": without_tool,
            "instrument_named": named,
            "domain_counts": tally("domain"),
            "measure_type_counts": tally("measure_type"),
            "gap_counts": tally("gap"),
            "domain_x_gap": crosstab}


def exemplars(coded, n=2):
    """Up to n task -> signal -> measure -> gap rows per domain, so every code is checkable against
    the record it came from."""
    rows = coded["coded"] if isinstance(coded, dict) else coded
    by_domain = {}
    for r in rows:
        d = r.get("domain")
        if len(by_domain.setdefault(d, [])) < n:
            by_domain[d].append({k: r.get(k) for k in ["id", "task", "signal", "measure", "gap", "gap_note"]})
    return by_domain
