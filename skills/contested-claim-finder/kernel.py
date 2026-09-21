"""contested-claim-finder — given a claim and a corpus, code which studies support it and which
contradict it, and report the split. It never collapses to a verdict, and it never lets a
sign-correct count become a claim it does not support.

Two things it exists to prevent, both of which happened in one real session:
  * writing a contested result up as consensus (four creativity studies called "four independent
    replications" when they were 3-to-1);
  * counting a study whose effect is in the MODEL's output — not in the person — as evidence about
    human cognition (the Padmakumar case: diversity loss was in the model's contributed text, "the
    user-contributed text remain[ing] unaffected").

Functions:
    code_direction(claim, records, id_field="doi", findings_field="key_finding",
                   model=None, max_concurrency=8)
        -> {"coded": [ {id, direction, sign, quote, mechanism_locus, rationale} ], "unrecovered": [ids]}
    contest_report(coded, claim=None) -> dict  (tally, quotes side by side, mechanism caveats)
    mechanism_caveats(coded) -> list  (studies whose effect is not located in the person)

SPEC DETAIL, load-bearing: direction is coded from the FINDINGS field only, never from design or
measures. Both real failures came from reading design-level fields, where studies pointing opposite
ways look identical.
"""

DIRECTION = ["supports", "contradicts", "mixed", "not_applicable"]
MECHANISM_LOCUS = ["person", "model_output", "unclear"]


def direction_instruction(claim):
    return ("You are checking one study against a specific CLAIM, using ONLY the study's findings "
            "text (ignore its design and its methods — the direction of a result lives in the "
            "findings). CLAIM: \"" + str(claim) + "\". Code these fields as JSON: "
            "direction (one of: " + ", ".join(DIRECTION) + " — does the finding support, contradict, "
            "partly-both (mixed), or not bear on the claim); "
            "sign (the direction of the specific quantity in dispute, e.g. increase / decrease / "
            "no_change / n/a); "
            "quote (a verbatim span, <=30 words, copied from the findings, that decides the call); "
            "mechanism_locus (one of: person = the change is in the human's cognition or output; "
            "model_output = the measured change is in the model's own contributed text, not the "
            "person; unclear); "
            "rationale (<=20 words). Do not infer beyond the findings text. Return ONLY the JSON object.")


def build_prompt(record, instruction, findings_field):
    import json
    ctx = {}
    for k in [findings_field, "citation", "cite", "title", "effect_size", "n"]:
        v = record.get(k)
        if v is not None and str(v).strip() and str(v).lower() != "nan":
            ctx[k] = str(v)[:600]
    return instruction + " STUDY: " + json.dumps(ctx)


def parse_obj(text):
    import json
    s, e = text.find("{"), text.rfind("}")
    if s < 0 or e < 0:
        return None
    try:
        return json.loads(text[s:e + 1])
    except Exception:
        return None


def code_direction(claim, records, id_field="doi", findings_field="key_finding",
                   model=None, max_concurrency=8):
    """Code each study's direction relative to `claim`, reading only the findings field. Returns
    coded rows + unrecovered ids. Retries unparsed rows once and reports what never parsed."""
    model = model or host.reasoning_model()
    instr = direction_instruction(claim)

    def make_reqs(idxs):
        return [{"prompt": build_prompt(records[i], instr, findings_field),
                 "model": model, "max_tokens": 1000,
                 "thinking": {"type": "disabled"}} for i in idxs]

    coded = [None] * len(records)
    order = list(range(len(records)))
    results = host.llm(make_reqs(order), max_concurrency=max_concurrency)
    retry = []
    for i, res in zip(order, results):
        obj = parse_obj(res.get("text", "")) if isinstance(res, dict) and "error" not in res else None
        (retry.append(i) if obj is None else coded.__setitem__(i, obj))
    if retry:
        results2 = host.llm(make_reqs(retry), max_concurrency=max_concurrency)
        for i, res in zip(retry, results2):
            obj = parse_obj(res.get("text", "")) if isinstance(res, dict) and "error" not in res else None
            if obj is not None:
                coded[i] = obj

    out = []
    for i, obj in enumerate(coded):
        if obj is None:
            continue
        obj["id"] = records[i].get(id_field) or records[i].get("citation") or records[i].get("cite")
        out.append(obj)
    unrecovered = [(records[i].get(id_field) or records[i].get("citation"))
                   for i in range(len(records)) if coded[i] is None]
    return {"coded": out, "unrecovered": unrecovered}


def mechanism_caveats(coded):
    """Studies whose measured effect is NOT located in the person — a sign-correct study that is not
    evidence about human cognition. Surfaced so a direction tally is never read as a cognition claim."""
    rows = coded["coded"] if isinstance(coded, dict) else coded
    return [{"id": r.get("id"), "mechanism_locus": r.get("mechanism_locus"),
             "quote": r.get("quote"), "rationale": r.get("rationale")}
            for r in rows if str(r.get("mechanism_locus")) != "person"
            and str(r.get("direction")) in ("supports", "contradicts", "mixed")]


def contest_report(coded, claim=None):
    """Tally of directions, the deciding quotes side by side, and the mechanism caveats. Reports the
    split; never returns a verdict. A `contested` flag is True when both supports and contradicts
    are present — a prompt to write it up as contested, not a resolution of which side is right."""
    rows = coded["coded"] if isinstance(coded, dict) else coded
    tally = {d: 0 for d in DIRECTION}
    for r in rows:
        d = str(r.get("direction"))
        tally[d] = tally.get(d, 0) + 1
    quotes = [{"id": r.get("id"), "direction": r.get("direction"), "sign": r.get("sign"),
               "quote": r.get("quote")} for r in rows]
    caveats = mechanism_caveats(rows)
    return {"claim": claim,
            "tally": tally,
            "contested": tally.get("supports", 0) > 0 and tally.get("contradicts", 0) > 0,
            "n_coded": len(rows),
            "quotes": quotes,
            "mechanism_caveats": caveats,
            "note": ("{} support / {} contradict / {} mixed — {} study(ies) have an effect not "
                     "located in the person (see mechanism_caveats); report the split, not a verdict."
                     .format(tally.get("supports", 0), tally.get("contradicts", 0),
                             tally.get("mixed", 0), len(caveats)))}
