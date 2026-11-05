"""Patient-scoped retrieval shared by the dashboard and clinical evidence preparation."""

import math
import re
from collections import Counter

from sqlalchemy import select

from .db import DocumentChunk, Record

STOP = {
    "the",
    "a",
    "an",
    "is",
    "are",
    "of",
    "to",
    "for",
    "in",
    "on",
    "and",
    "what",
    "which",
    "does",
    "do",
    "my",
    "patient",
    "please",
    "show",
    "me",
    "with",
}


def terms(text):
    return Counter(t for t in re.findall(r"[^\W_]+", text.casefold()) if t not in STOP)


def split_unit(text, limit=1000):
    # Keep units independent; never cross pages/sheets/tables. Overlap long text only.
    start = 0
    while start < len(text):
        end = min(start + limit, len(text))
        if end < len(text):
            boundary = text.rfind(" ", start + limit // 2, end)
            if boundary > start:
                end = boundary
        part = text[start:end].strip()
        if part:
            yield part
        if end == len(text):
            break
        start = max(start + 1, end - 120)


def search(
    db, pid, query, document_id=None, kind=None, limit=6, query_vector=None, model=None
):
    stmt = (
        select(DocumentChunk, Record)
        .join(Record, Record.id == DocumentChunk.document_id)
        .where(
            Record.patient_id == pid,
            Record.kind == "document",
            Record.status != "deleted",
        )
    )
    if document_id:
        stmt = stmt.where(Record.id == document_id)
    if kind:
        stmt = stmt.where(DocumentChunk.kind == kind)
    # Hard ceiling gives an honest bounded service rather than an unbounded corpus scan.
    pairs = db.execute(stmt.order_by(DocumentChunk.id).limit(4001)).all()
    if len(pairs) > 4000:
        raise ValueError("corpus_limit")
    pairs = [
        (c, r)
        for c, r in pairs
        if c.generation == r.payload.get("generation")
        and r.payload.get("processing_status") in ["processed", "partial"]
    ]
    q = terms(query)
    N = len(pairs)
    avg = sum(sum(c.terms.values()) for c, _ in pairs) / max(N, 1)
    freq = Counter()
    for c, _ in pairs:
        for t in q:
            if t in c.terms:
                freq[t] += 1
    lex = []
    semantic = []
    for c, r in pairs:
        score = 0
        length = sum(c.terms.values())
        for t in q:
            tf = c.terms.get(t, 0)
            if tf:
                score += (
                    math.log(1 + (N - freq[t] + 0.5) / (freq[t] + 0.5))
                    * tf
                    * 2.2
                    / (tf + 1.2 * (0.25 + 0.75 * length / max(avg, 1)))
                )
        if score:
            lex.append((c.id, score))
        if (
            query_vector
            and c.embedding
            and c.embedding_model == model
            and len(c.embedding) == len(query_vector)
        ):
            norm = math.sqrt(sum(x * x for x in c.embedding)) * math.sqrt(
                sum(x * x for x in query_vector)
            )
            sim = (
                sum(a * b for a, b in zip(c.embedding, query_vector)) / norm
                if norm
                else 0
            )
            if sim > 0.25:
                semantic.append((c.id, sim))
    lex.sort(key=lambda x: (-x[1], x[0]))
    semantic.sort(key=lambda x: (-x[1], x[0]))
    scores = Counter()
    for ranked in [lex, semantic]:
        for rank, (key, _) in enumerate(ranked[:40], 1):
            scores[key] += 1 / (60 + rank)
    byid = {c.id: (c, r) for c, r in pairs}
    results = []
    budget = 6000
    for key, score in sorted(scores.items(), key=lambda x: (-x[1], x[0]))[:limit]:
        c, r = byid[key]
        text = c.text[: min(1200, budget)]
        budget -= len(text)
        if not text:
            break
        results.append(
            {
                "chunk_id": c.id,
                "document_id": r.id,
                "document_title": r.payload["title"],
                "document_version": r.version,
                "generation": c.generation,
                "source": c.source,
                "kind": c.kind,
                "text": text,
                "score": round(score, 6),
                "warnings": r.payload.get("warnings", []),
                "interpretation": c.kind == "visual_description",
                "verified": False,
            }
        )
    return {
        "mode": "hybrid_rrf" if semantic else "keyword_bm25",
        "results": results,
        "clinical_use": False,
        "context_characters": sum(len(x["text"]) for x in results),
    }


def verified_context(db, pid, query, max_docs=3):
    """AI drafting consumes human-verified facts only, ranked by query relevance."""
    docs = (
        db.query(Record)
        .filter_by(patient_id=pid, kind="document", status="reviewed")
        .all()
    )
    q = terms(query)
    try:
        retrieved = search(db, pid, query, limit=10)["results"]
    except ValueError:
        retrieved = []
    rank = {}
    for hit in retrieved:
        rank.setdefault(hit["document_id"], len(rank))
    docs.sort(
        key=lambda d: (
            rank.get(d.id, 100),
            -sum((q & terms(d.payload.get("text", ""))).values()),
            d.created_at,
        )
    )
    facts = []
    versions = {}
    for d in docs[:max_docs]:
        for f in d.payload.get("candidates", []):
            if f["status"] == "verified":
                versions[d.id] = d.version
                facts.append(
                    {
                        "source_id": d.id + ":" + f["id"],
                        "text": f["label"] + ": " + f["value"] + " " + f["unit"],
                        "quote": f["quote"],
                        "source": f.get("source_references", f.get("page_numbers", [])),
                    }
                )
    return facts[:12], versions
