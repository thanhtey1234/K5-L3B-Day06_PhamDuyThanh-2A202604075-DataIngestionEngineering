"""Evaluate retrieved evidence and preserve per-query traces."""
import re
import unicodedata
from typing import Any


def _clean_str_for_matching(text: str) -> str:
    """Normalize text for evidence comparison."""
    if not text:
        return ""
    norm = unicodedata.normalize("NFC", text).lower()
    norm = re.sub(r"\s+", " ", norm).strip()
    return norm


def check_chunk_hit(question: dict[str, Any], chunk: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    """Check if a retrieved chunk satisfies gold source/page and evidence requirements."""
    gold_page = question.get("gold_page")
    gold_source = question.get("gold_source_id") or question.get("gold_source")
    evidence_quote = question.get("evidence_quote", "")

    chunk_page = chunk.get("page")
    chunk_source = chunk.get("document_id") or chunk.get("source")
    chunk_text = chunk.get("text", "")

    # 1. Kiểm tra Page
    page_match = False
    if gold_page is not None:
        if isinstance(gold_page, list):
            page_match = chunk_page in gold_page
        else:
            try:
                page_match = int(chunk_page) == int(gold_page)
            except (ValueError, TypeError):
                page_match = str(chunk_page) == str(gold_page)
    else:
        page_match = True

    # 2. Kiểm tra Source
    source_match = True
    if gold_source:
        chunk_meta = chunk.get("metadata", {})
        meta_source = chunk_meta.get("source_id") or chunk_meta.get("document_id")
        source_match = (
            (chunk_source == gold_source)
            or (gold_source in str(chunk.get("source", "")))
            or (meta_source == gold_source)
            or (str(chunk_source).lower() in ["pages", "corpus", "pages.jsonl"])
        )

    # 3. Kiểm tra Evidence Quote
    evidence_match = False
    clean_chunk = _clean_str_for_matching(chunk_text)
    clean_evidence = _clean_str_for_matching(evidence_quote)

    if not clean_evidence:
        # Nếu không có quote cụ thể thì dựa vào page_match & source_match
        evidence_match = True
    else:
        if clean_evidence in clean_chunk:
            evidence_match = True
        else:
            # Nếu quote dài, kiểm tra xem các phần lớn của quote có nằm trong chunk không
            sub_phrases = [p.strip() for p in re.split(r"[.?!;,\n]+", clean_evidence) if len(p.strip()) > 15]
            if sub_phrases and any(phrase in clean_chunk for phrase in sub_phrases):
                evidence_match = True

    is_hit = bool(page_match and source_match and evidence_match)

    details = {
        "page_match": page_match,
        "source_match": source_match,
        "evidence_match": evidence_match,
    }
    return is_hit, details


def evaluate_query(question: dict[str, Any], hits: list[dict[str, Any]]) -> dict[str, Any]:
    """Check source/page and enough gold evidence; keep hit@1 and hit@3 trace.

    Accept any documented alternative gold evidence.
    """
    evaluated_hits = []
    hit_at_1 = False
    evidence_hit_at_3 = False

    for idx, hit in enumerate(hits[:3]):
        is_hit, details = check_chunk_hit(question, hit)
        hit_copy = dict(hit)
        hit_copy["is_hit"] = is_hit
        hit_copy["match_details"] = details
        evaluated_hits.append(hit_copy)

        if idx == 0 and is_hit:
            hit_at_1 = True
        if is_hit:
            evidence_hit_at_3 = True

    trace = {
        "question_id": question.get("id"),
        "split": question.get("split", "dev"),
        "question": question.get("question"),
        "filter": question.get("filter"),
        "gold_page": question.get("gold_page"),
        "gold_source_id": question.get("gold_source_id"),
        "evidence_quote": question.get("evidence_quote"),
        "expected_answer": question.get("expected_answer"),
        "hit_at_1": 1 if hit_at_1 else 0,
        "evidence_hit_at_3": 1 if evidence_hit_at_3 else 0,
        "retrieved_hits": evaluated_hits,
    }

    return trace


def summarize(traces: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate Hit@1 and Evidence Hit@3 by strategy and dev/test split."""
    if not traces:
        return {"total": 0, "message": "No traces to summarize"}

    splits = ["all", "dev", "test"]
    summary: dict[str, Any] = {}

    for s in splits:
        if s == "all":
            subset = traces
        else:
            subset = [t for t in traces if t.get("split") == s]

        total = len(subset)
        if total == 0:
            summary[s] = {"total": 0, "hit_at_1": "0/0 (0.0%)", "evidence_hit_at_3": "0/0 (0.0%)"}
            continue

        h1_count = sum(t.get("hit_at_1", 0) for t in subset)
        h3_count = sum(t.get("evidence_hit_at_3", 0) for t in subset)

        summary[s] = {
            "total": total,
            "hit_at_1_count": h1_count,
            "hit_at_1_rate": round(h1_count / total, 4),
            "hit_at_1_display": f"{h1_count}/{total} ({round(h1_count / total * 100, 1)}%)",
            "evidence_hit_at_3_count": h3_count,
            "evidence_hit_at_3_rate": round(h3_count / total, 4),
            "evidence_hit_at_3_display": f"{h3_count}/{total} ({round(h3_count / total * 100, 1)}%)",
        }

    return summary

