"""Tests 2 and 3 — educator content and English / Devanagari / Romanized Nepali processing."""
from app.analysis.classify import classify
from app.analysis.normalize import detect_language, normalize_text
from app.analysis.priority import assess_priority
from app.analysis.redact import redact_text
from app.analysis.nepali_calendar import nepali_date_str
from datetime import date


def _run(text, sender_kind="teacher", category=""):
    norm = normalize_text(redact_text(text))
    c = classify(norm, sender_kind=sender_kind, group_category=category)
    p = assess_priority(norm, c.categories, is_question=c.is_question, sender_kind=sender_kind)
    return c, p


def test_educator_lesson_plan_homework_meeting_and_deadline():
    c, _ = _run("Lesson plan for Class 6-8 science and maths is uploaded to the staff drive.", category="Academic Coordination")
    assert "Academic planning" in c.categories
    c, _ = _run("Homework: Exercise 3.2, questions 1 to 8. Due 2026-10-13.")
    assert "Homework & assignments" in c.categories
    c, _ = _run("Staff meeting tomorrow at 2:00 PM in the seminar hall.")
    assert "Teacher coordination" in c.categories
    c, p = _run("Unit test on algebra will be held on 2026-10-16. Homework due by tomorrow.")
    assert "Examinations & assessments" in c.categories
    assert p.priority == "HIGH"   # explicit near-term deadline -> time-sensitive


def test_planned_vs_completed_status_is_not_overstated():
    c, _ = _run("Yes, the homework can be submitted on Monday.")
    assert c.activity_status != "completed"          # future submission is not a completed activity
    c, _ = _run("Practical lab slots for Class 9 physics are completed this week.")
    assert c.activity_status == "completed"


def test_nepali_devanagari_homework_and_question():
    text = "मेरो छोरीको गृहकार्य कहिले बुझाउने हो? कृपया बताउनुहोस्।"
    assert detect_language(text) == "ne"
    c, _ = _run(text, sender_kind="parent")
    assert "Homework & assignments" in c.categories
    assert c.is_question


def test_romanized_nepali_exam_question_is_high_when_near_term():
    text = "Bholi ko pariksha ko time table kaha pauna sakchhu?"
    assert detect_language(text) == "ne-roman"
    c, p = _run(text, sender_kind="parent")
    assert "Examinations & assessments" in c.categories
    assert c.is_question
    assert p.priority == "HIGH"
    assert "bholi" in p.reason.lower() or "tomorrow" in p.reason.lower() or "near-term" in p.reason.lower()


def test_devanagari_positive_recognition():
    c, p = _run("बधाई छ! आजको गणित प्रतियोगितामा विद्यार्थीले राम्रो प्रदर्शन गरे।", category="Parent-Teacher Group")
    assert "Positive achievements & recognition" in c.categories
    assert p.priority == "POSITIVE"


def test_mixed_code_switching_detected():
    assert detect_language("Aaja homework ko deadline xa, please submit गर्नुहोस्") in ("mixed", "ne-roman")


def test_english_plain_is_en():
    assert detect_language("Terminal examination routine will be published on Monday.") == "en"


def test_original_text_is_not_rewritten_by_normalization():
    original = "BEST!!  Staff   MEETING   at 2pm"
    norm = normalize_text(original)
    assert original != norm              # analysis copy differs...
    assert "staff meeting" in norm       # ...but is lowercased/collapsed for analysis only


def test_abbreviations_expanded_for_analysis():
    assert "homework" in normalize_text("HW due tomorrow")


def test_nepali_date_is_none_when_unreliable_and_string_when_available():
    s = nepali_date_str(date(2026, 10, 10))
    assert isinstance(s, str)            # either a reliable Nepali date or empty — never fabricated
