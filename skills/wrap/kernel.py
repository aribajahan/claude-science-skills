"""wrap — session close-out and staleness checks for a project's own documents.

Pure filesystem and text logic. No repo, no git, no network. Point it at the folders that
make up a project; it reports what has gone stale and drafts the log entry.
"""

DOC_EXT = (".md", ".markdown", ".txt")
# Aggregate dumps contain every number and phrase in the project, so they match every
# text-similarity check. Excluded by default; pass exclude=[] to include them.
AGGREGATE_HINTS = ("transcript", "-run-", "_run_", "conversation", "export")
# Directories holding RECORDS rather than documents. A record is raw evidence you keep
# verbatim (a transcript, a tool run, an export); a document is something you maintain.
# Checks that compare documents to each other must not read records, because a record
# contains a copy of everything and therefore matches everything.
RECORD_DIRS = ("runs", "raw", "exports", "archive", "transcripts")
NEXT_MARKERS = ("next action", "next step", "next decision", "to do", "todo", "next:")
DONE_MARKERS = ("done", "complete", "completed", "fixed", "built", "shipped", "resolved")
WORD_NUMBERS = {"ten": "10", "eleven": "11", "twelve": "12", "thirteen": "13",
                "fourteen": "14", "fifteen": "15", "sixteen": "16", "seventeen": "17",
                "eighteen": "18", "nineteen": "19", "twenty": "20", "thirty": "30",
                "forty": "40", "fifty": "50"}


def collect_docs(paths, exclude=None):
    """Every document file under the given folders. paths: str or list of str.

    exclude: filename substrings to skip. Defaults to AGGREGATE_HINTS.
    """
    import os
    hints = AGGREGATE_HINTS if exclude is None else tuple(exclude)
    if isinstance(paths, str):
        paths = [paths]
    out, unreadable = [], []
    for root_dir in paths:
        if not os.path.isdir(root_dir):
            unreadable.append(root_dir); continue
        try:
            os.listdir(root_dir)
        except OSError as e:
            unreadable.append("%s (%s)" % (root_dir, type(e).__name__)); continue
        for dirpath, dirnames, filenames in os.walk(root_dir):
            dirnames[:] = [d for d in dirnames if not d.startswith((".", "_"))
                           and d not in ("node_modules", "__pycache__")
                           and d.lower() not in RECORD_DIRS]
            for fn in filenames:
                if fn.lower().endswith(DOC_EXT) and not any(h in fn.lower() for h in hints):
                    out.append(os.path.join(dirpath, fn))
    if unreadable:
        raise RuntimeError(
            "wrap: these paths are missing or unreadable from this kernel, so a clean "
            "report would be a false negative: %s" % "; ".join(unreadable))
    return sorted(out)


def collect_all_files(paths):
    """Every non-hidden file under the given folders, for orphan detection."""
    import os
    if isinstance(paths, str):
        paths = [paths]
    out = []
    for root_dir in paths:
        for dirpath, dirnames, filenames in os.walk(root_dir):
            dirnames[:] = [d for d in dirnames if not d.startswith((".", "_"))
                           and d not in ("node_modules", "__pycache__")]
            for fn in filenames:
                if not fn.startswith("."):
                    out.append(os.path.join(dirpath, fn))
    return sorted(out)


def check_links(paths):
    """Markdown links pointing at relative paths that do not exist.

    Catches the classic breakage: files get reorganised into subfolders and every
    cross-reference written before the move silently points at nothing.
    """
    import os, re
    link_re = re.compile(r'\[[^\]]*\]\(([^)\s]+)\)')
    bad = []
    for doc in collect_docs(paths):
        base = os.path.dirname(doc)
        try:
            text = open(doc, encoding="utf-8", errors="ignore").read()
        except OSError:
            continue
        for target in link_re.findall(text):
            if target.startswith(("http://", "https://", "#", "mailto:", "{{")):
                continue
            clean = target.split("#")[0].strip()
            if not clean:
                continue
            if not os.path.exists(os.path.normpath(os.path.join(base, clean))):
                bad.append({"doc": doc, "link": target})
    return bad


def check_orphans(paths):
    """Files promised by a document but absent, and files present that no document names."""
    import os
    docs = collect_docs(paths)
    every = collect_all_files(paths)
    corpus = ""
    for doc in docs:
        try:
            corpus += open(doc, encoding="utf-8", errors="ignore").read() + "\n"
        except OSError:
            pass
    unmentioned = [f for f in every
                   if os.path.basename(f) not in corpus and f not in docs]
    return {"present_but_unmentioned": unmentioned}


def check_number_conflicts(paths, terms=None, window=70, min_docs=2):
    """The same entity carrying different numbers in different documents.

    terms: entities to watch. Default: capitalised tokens appearing in >= min_docs files.
    Returns one row per term that has more than one distinct nearby number.
    """
    import os, re
    docs = collect_docs(paths)
    texts = {}
    for doc in docs:
        try:
            texts[doc] = open(doc, encoding="utf-8", errors="ignore").read()
        except OSError:
            pass
    if terms is None:
        # Default to author-like tokens only: a capitalised word immediately before
        # "et al." or "&". Any-capitalised-word defaults produce hundreds of junk rows
        # ("Study", "Sample", "Claude") and make the check unusable.
        auth_re = re.compile(r'\b([A-Z][a-z]{3,})(?=\s+(?:et al\.|&|and)\s)')
        seen = {}
        for doc, t in texts.items():
            for w in set(auth_re.findall(t)):
                seen.setdefault(w, set()).add(doc)
        terms = [w for w, ds in seen.items() if len(ds) >= min_docs]
    num_re = re.compile(r'\b\d[\d,]*(?:\.\d+)?\b')
    url_re = re.compile(r'(https?://\S+|10\.\d{4,}/\S+)')
    rows = []
    for term in terms:
        found = {}
        for doc, t in texts.items():
            clean = url_re.sub(" ", t)
            for m in re.finditer(re.escape(term), clean):
                seg = clean[max(0, m.start() - window): m.start() + window]
                # only quantities explicitly reported as a sample size — a bare year or
                # page number sitting near a name is not a conflict
                for qm in re.finditer(r'(?:\b[Nn]\s*=\s*)(\d[\d,]*)', seg):
                    val = qm.group(1).replace(",", "")
                    if len(val) > 1:
                        found.setdefault(val, set()).add(os.path.basename(doc))
        docs_hit = set()
        for ds in found.values():
            docs_hit |= ds
        if len(found) > 1 and len(docs_hit) >= min_docs:
            rows.append({"term": term,
                         "values": {v: sorted(ds) for v, ds in found.items()}})
    return rows


def check_table_sums(paths, tolerance=0):
    """A prose total near a markdown table whose numeric column does not sum to it.

    Catches a table of counts followed by a sentence naming a different total.
    """
    import os, re
    num_re = re.compile(r'\b\d[\d,]*\b')
    rows = []
    for doc in collect_docs(paths):
        try:
            lines = open(doc, encoding="utf-8", errors="ignore").read().splitlines()
        except OSError:
            continue
        i = 0
        while i < len(lines):
            if lines[i].strip().startswith("|") and "|" in lines[i][1:]:
                start = i
                while i < len(lines) and lines[i].strip().startswith("|"):
                    i += 1
                block = lines[start:i]
                cells = []
                for ln in block:
                    parts = [c.strip() for c in ln.strip().strip("|").split("|")]
                    if len(parts) >= 2 and not set(ln) <= set("|- :"):
                        cells.append(parts)
                col_sums = {}
                for ci in range(1, max((len(c) for c in cells), default=0)):
                    vals = []
                    for row in cells:
                        if ci < len(row):
                            hits = num_re.findall(row[ci].replace("**", ""))
                            if len(hits) == 1 and row[ci].replace("**", "").strip() == hits[0]:
                                vals.append(int(hits[0].replace(",", "")))
                    if len(vals) >= 3:
                        col_sums[ci] = (sum(vals), vals)
                tail = " ".join(lines[i:i + 4])
                for word, digit in WORD_NUMBERS.items():
                    tail = re.sub(r'(?i)\b%s\b' % word, digit, tail)
                for ci, (total, vals) in col_sums.items():
                    for n in num_re.findall(tail):
                        v = int(n.replace(",", ""))
                        if v in vals or v < 3:
                            continue
                        if abs(v - total) <= tolerance:
                            continue
                        cue = re.search(
                            r'(?i)(total|in all|altogether|combined|sum|of (?:the|these)\s*$|'
                            r'went to these|across (?:the|these)|add(?:s|ed)? up)',
                            tail[:max(0, tail.find(n)) + 30])
                        if cue and 0.4 * total <= v <= 2.5 * total:
                            rows.append({"doc": os.path.basename(doc), "table_line": start + 1,
                                         "column_sums_to": total, "prose_says": v,
                                         "column_values": vals})
            i += 1
    return rows


def check_stale_next_actions(paths):
    """A 'next action' line naming work that a log elsewhere records as done."""
    import os, re
    docs = collect_docs(paths)
    logs, plans = [], []
    for d in docs:
        name = os.path.basename(d).lower()
        (logs if "log" in name else plans).append(d)
    log_text = ""
    for d in logs:
        try:
            log_text += open(d, encoding="utf-8", errors="ignore").read().lower() + "\n"
        except OSError:
            pass
    rows = []
    word_re = re.compile(r'[a-z]{5,}')
    for d in plans:
        try:
            lines = open(d, encoding="utf-8", errors="ignore").read().splitlines()
        except OSError:
            continue
        for li, ln in enumerate(lines):
            low = ln.lower()
            if not any(mk in low for mk in NEXT_MARKERS):
                continue
            body = ln
            if ln.strip().startswith("#"):
                j = li + 1
                while j < len(lines) and not lines[j].strip().startswith("#"):
                    body += " " + lines[j]
                    j += 1
            low = body.lower()
            words = set(word_re.findall(low)) - {"action", "decision", "next", "these",
                                                 "which", "pending", "recommended"}
            if not words:
                continue
            words = {w for w in words if len(w) >= 6 and log_text.count(w) <= 40}
            for w in words:
                for m in re.finditer(re.escape(w), log_text):
                    seg = log_text[max(0, m.start() - 120): m.start() + 120]
                    others = [o for o in words if o != w and o in seg]
                    if others and any(dm in seg for dm in DONE_MARKERS):
                        rows.append({"doc": os.path.basename(d), "line": body.strip()[:140],
                                     "matched_term": w + "+" + others[0]})
                        break
                else:
                    continue
                break
    return rows


def stale_report(paths, terms=None, experimental=False):
    """Report-only — nothing is written or repaired.

    By default runs only the two checks validated to fire on positive controls AND stay
    quiet on real data: broken links and orphans.

    experimental=True adds three checks that fire correctly on planted controls but have a
    high false-positive rate on real prose (see README). Treat their output as candidates to
    eyeball, never as a defect list. `number_conflicts` is only usable with explicit `terms`.
    """
    out = {"broken_links": check_links(paths),
           "orphans": check_orphans(paths)}
    if experimental:
        out["number_conflicts"] = check_number_conflicts(paths, terms=terms)
        out["table_sum_mismatches"] = check_table_sums(paths)
        out["stale_next_actions"] = check_stale_next_actions(paths)
    return out


def draft_entry(title, tool, done, decisions=None, learned=None, open_items=None, date=None):
    """Format a dated, tool-tagged session-log entry. Returns text; writes nothing."""
    import datetime
    d = date or datetime.date.today().isoformat()
    parts = ["## %s — [%s] %s" % (d, tool, title), ""]
    def block(head, items):
        if not items:
            return
        parts.append("### " + head)
        parts.append("")
        for it in items:
            parts.append("- " + str(it))
        parts.append("")
    block("What was done", done)
    block("Decisions", decisions)
    block("What we learned", learned)
    block("Open", open_items)
    return "\n".join(parts).rstrip() + "\n"


def append_entry(log_path, entry_text):
    """Append-only write to the session log. Never edits existing content."""
    import os
    existing = ""
    if os.path.exists(log_path):
        existing = open(log_path, encoding="utf-8").read().rstrip()
    body = existing + "\n\n---\n\n" + entry_text if existing else entry_text
    open(log_path, "w", encoding="utf-8").write(body)
    return {"path": log_path, "appended_chars": len(entry_text)}


def propose_plan_update(plan_path, status_lines=None, next_action=None):
    """Return a PROPOSED replacement for a plan's status and next-action sections.

    Writes nothing. Returns the current text, the proposed text, and a unified diff
    for the user to approve. Rewriting a plan unattended is how a wrong edit becomes
    permanent, so the decision stays with the user.
    """
    import difflib, os
    if not os.path.exists(plan_path):
        return {"error": "no such file: %s" % plan_path}
    current = open(plan_path, encoding="utf-8").read()
    lines = current.splitlines()
    proposed = list(lines)
    edits = []
    for idx, ln in enumerate(lines):
        low = ln.lower()
        if low.startswith("#") and "where it stands" in low and status_lines:
            end = idx + 1
            while end < len(lines) and not lines[end].startswith("#"):
                end += 1
            proposed = proposed[:idx + 1] + [""] + ["- " + s for s in status_lines] + [""] + proposed[end:]
            edits.append("replaced 'where it stands'")
            break
    if next_action:
        for idx, ln in enumerate(proposed):
            if any(mk in ln.lower() for mk in NEXT_MARKERS) and ln.startswith("#"):
                end = idx + 1
                while end < len(proposed) and not proposed[end].startswith("#"):
                    end += 1
                proposed = proposed[:idx + 1] + ["", next_action, ""] + proposed[end:]
                edits.append("replaced next-action section")
                break
    new_text = "\n".join(proposed)
    diff = "\n".join(difflib.unified_diff(lines, proposed, "current", "proposed", lineterm="", n=2))
    return {"path": plan_path, "edits": edits, "proposed_text": new_text,
            "diff": diff, "written": False}
