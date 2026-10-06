"""Stable evidence markers and one bibliography shared by every export."""
import hashlib
import re

CITATION = re.compile(r"\[@([A-Za-z0-9_-]+)\]")


def content_hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def evidence_index(sources):
    return {e["id"]: (s, e) for s in sources if s["status"] != "excluded"
            for e in s.get("evidence", [])}


def validate_citations(text, sources):
    known = evidence_index(sources)
    ids = CITATION.findall(text)
    missing = sorted(set(ids) - known.keys())
    if missing:
        raise ValueError("Citazioni senza un estratto registrato: " + ", ".join(missing))
    if "[@" in CITATION.sub("", text):
        raise ValueError("Riferimento incompleto: usa un identificativo di evidenza registrato.")
    return ids


def citation_map(chapters, sources, style):
    evidence = evidence_index(sources)
    order = []
    for chapter in chapters:
        for eid in validate_citations(chapter["content"], sources):
            sid = evidence[eid][0]["id"]
            if sid not in order:
                order.append(sid)
    selected = {s["id"]: s for s in sources if s["id"] in order}
    groups = {}
    for sid in order:
        s = selected[sid]
        label = (s.get("author") or s["title"]).strip()
        year = re.search(r"\b(?:19|20)\d{2}\b", s.get("published", ""))
        key = (label, year.group() if year else "s.d.")
        groups.setdefault(key, []).append(sid)
    labels = {}
    for index, sid in enumerate(order, 1):
        s = selected[sid]
        author = s.get("author") or s["title"]
        year = re.search(r"\b(?:19|20)\d{2}\b", s.get("published", ""))
        key = (author.strip(), year.group() if year else "s.d.")
        suffix = chr(97 + groups[key].index(sid)) if len(groups[key]) > 1 else ""
        labels[sid] = str(index) if style == "numeric" else author + ", " + key[1] + suffix
    return evidence, order, selected, labels


def rendered_manuscript(session, *, linked=False):
    evidence, order, selected, labels = citation_map(session.book_chapters, session.sources,
                                                    session.form_data.citation_style)
    result = []
    for chapter in session.book_chapters:
        def replace(match):
            source, _ = evidence[match.group(1)]
            label = labels[source["id"]]
            value = "[" + label + "]" if session.form_data.citation_style == "numeric" else "(" + label + ")"
            if linked:
                # Escape brackets inside the link label.
                return "[" + value.replace("[", r"\[").replace("]", r"\]") + "](#source-" + source["id"] + ")"
            return value
        result.append(chapter | {"display_content": CITATION.sub(replace, chapter["content"])})
    bibliography = []
    for sid in order:
        s = selected[sid]
        metadata = [s.get("author"), s.get("published"), s["title"], s.get("url")]
        entry = ". ".join(x for x in metadata if x)
        if s.get("acquired_at"):
            entry += ". Consultato: " + s["acquired_at"][:10]
        if s["kind"] == "author_notes":
            entry += ". Materiale dichiarato dall'autore"
        bibliography.append({"id": sid, "label": labels[sid], "text": entry})
    return result, bibliography


def reference_checks(session):
    evidence = evidence_index(session.sources)
    issues = []
    count = 0
    for chapter in session.book_chapters:
        for eid in CITATION.findall(chapter["content"]):
            count += 1
            if eid not in evidence:
                issues.append({"section_id": chapter.get("section_id", ""), "quote": "[@" + eid + "]",
                    "category": "evidence", "severity": "blocking",
                    "explanation": "La citazione non ha un estratto disponibile.", "suggestion": "Ripristina la fonte o modifica il riferimento."})
    return {"citations": count, "evidence": len(evidence), "issues": issues}
