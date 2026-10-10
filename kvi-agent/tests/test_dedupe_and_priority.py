"""Test 5 (repeated announcements keep source references), Test 6 (urgent issue explained with evidence)."""
from datetime import datetime, timezone

from app.analysis.classify import classify
from app.analysis.dedupe import cluster_items
from app.analysis.normalize import normalize_text
from app.analysis.priority import assess_priority
from app.analysis.redact import redact_text

NOTICE = "Terminal examination routine for Class 5 to 8 will be published on 2026-10-20. Please prepare accordingly."
TS = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)


def _item(platform, source, text, ts=TS, ref=""):
    norm = normalize_text(redact_text(text))
    c = classify(norm)
    p = assess_priority(norm, c.categories)
    return {"platform": platform, "source_name": source, "ts": ts, "sender": "x",
            "text_normalized": norm, "excerpt": text, "categories": c.categories,
            "priority": p.priority, "priority_reason": p.reason, "confidence": c.confidence,
            "ref_id": ref or f"{source}-ref"}


def test_repeated_exam_notice_merges_across_groups_and_facebook_without_losing_refs():
    items = [
        _item("whatsapp", "Class 5 Science", NOTICE, ref="msg-1"),
        _item("whatsapp", "Class 5 Parents Notice", NOTICE, ref="msg-2"),
        _item("whatsapp", "Teachers Academic Coordination", NOTICE, ref="msg-3"),
        _item("whatsapp", "Class 8 Parents", NOTICE, ref="msg-4"),
        _item("facebook", "Kashyap Vidyapeeth Inaruwa", NOTICE, ref="https://facebook.com/post/1"),
    ]
    clusters = cluster_items(items)
    assert len(clusters) == 1
    c = clusters[0]
    assert c.source_count == 5
    assert {e.source_name for e in c.evidence} >= {"Class 5 Science", "Kashyap Vidyapeeth Inaruwa"}
    assert {e.ref_id for e in c.evidence} == {"msg-1", "msg-2", "msg-3", "msg-4", "https://facebook.com/post/1"}


def test_unrelated_message_with_shared_keywords_is_not_merged():
    other = "Terminal examination for Class 9 physics practical is postponed to 2026-10-25 due to lab maintenance."
    clusters = cluster_items([_item("whatsapp", "Class 5 Science", NOTICE),
                              _item("whatsapp", "Class 9 Parents", other)])
    assert len(clusters) == 2


def test_different_day_repeat_is_not_merged():
    later = datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc)
    clusters = cluster_items([_item("whatsapp", "A", NOTICE), _item("whatsapp", "B", NOTICE, ts=later)])
    assert len(clusters) == 2   # same wording on another day is a separate event


def test_urgent_safety_issue_is_critical_with_explained_evidence():
    text = "URGENT!!!! Student injured in the school bus accident near the main gate. Please come to school immediately!!!"
    norm = normalize_text(redact_text(text))
    c = classify(norm, sender_kind="parent")
    p = assess_priority(norm, c.categories, sender_kind="parent")
    assert p.priority == "CRITICAL"
    assert "injured" in p.evidence_terms or "accident" in p.evidence_terms
    assert "school context" in p.reason.lower() or "safety" in p.reason.lower()
    assert "verification" in p.reason.lower() or "verify" in p.reason.lower()


def test_safety_word_without_school_context_is_not_critical():
    norm = normalize_text("The accident chapter in our general knowledge book is interesting.")
    c = classify(norm)
    assert assess_priority(norm, c.categories).priority != "CRITICAL"


def test_capitals_and_punctuation_alone_do_not_escalate():
    text = "PLEASE SEND THE PICNIC PHOTOS!!!!!!! WHY NOT??????"
    norm = normalize_text(text)
    c = classify(norm, sender_kind="parent")
    p = assess_priority(norm, c.categories, is_question=c.is_question, sender_kind="parent")
    assert p.priority in ("LOW", "MEDIUM")
    assert p.priority != "CRITICAL"


def test_every_priority_carries_an_explanation():
    for text in ["Good morning all.", "Homework due 2026-10-13", "Congratulations to Class 8 winners!"]:
        norm = normalize_text(text)
        c = classify(norm)
        p = assess_priority(norm, c.categories)
        assert p.reason and p.priority in {"CRITICAL", "HIGH", "MEDIUM", "LOW", "POSITIVE"}
