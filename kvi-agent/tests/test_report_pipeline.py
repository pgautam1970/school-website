"""Tests 7 (every configured class + coverage indicators), 13 (injection cannot change config),
15 (facts vs inference vs recommendations), and the report-level redaction checks."""
from pathlib import Path

from sqlalchemy import func, select

from app.analysis.pipeline import run_pipeline
from app.config import CLASS_LEVELS, get_settings
from app.models import ActionItem, DailyReport
from conftest import TEST_DAY


def _report(db):
    return run_pipeline(db, TEST_DAY)


def test_report_contains_every_class_from_playgroup_to_class_12(seeded, db):
    rep = _report(db)
    levels = [r["class"] for r in rep.data["class_rows"]]
    assert levels == CLASS_LEVELS
    assert len(levels) == 16


def test_class_status_distinguishes_no_data_not_configured_and_available(seeded, db):
    rep = _report(db)
    rows = {r["class"]: r for r in rep.data["class_rows"]}
    assert rows["Class 1"]["data_status"] == "available" and rows["Class 1"]["messages"] == 2
    assert rows["Class 10"]["data_status"] == "available" and rows["Class 10"]["messages"] == 3   # not merged with Class 1
    assert rows["Class 4"]["data_status"] == "no_data"                       # registered, never imported
    assert rows["Class 4"]["priority"] == "UNKNOWN"
    assert rows["Class 2"]["data_status"] == "not_configured"
    html = rep.html
    assert "data unavailable (not zero activity)" in html


def test_coverage_is_explicit_about_missing_groups(seeded, db):
    rep = _report(db)
    cov = rep.data["coverage"]
    assert "Class 4 Parents" in cov["groups_missing_today"]
    assert cov["groups_with_data"] < cov["groups_total"]
    assert "provided no data" in " ".join(rep.data["limitations"])
    assert "groups with data" in rep.text or "WhatsApp groups" in rep.text


def test_critical_alert_has_evidence_source_and_status(seeded, db):
    rep = _report(db)
    crit = [a for a in rep.data["alerts"] if a["priority"] == "CRITICAL"]
    assert crit, "urgent fixture must produce a CRITICAL alert"
    a = crit[0]
    assert a["reason"] and a["sources"] and a["status"].startswith("verified")
    assert a["next_step"]


def test_unanswered_parent_question_is_listed_as_unresolved(seeded, db):
    rep = _report(db)
    unanswered = [u["excerpt"] for u in rep.data["parent"]["unanswered"]]
    assert any("terminal examination" in u.lower() for u in unanswered)
    assert rep.data["parent"]["unanswered_count"] >= 1


def test_answered_question_is_not_flagged_unanswered(seeded, db):
    rep = _report(db)
    # Parent 1 asked about homework; the teacher replied "Yes, ... Thank you" within 6 hours
    assert not any("is the homework for tomorrow" in u["excerpt"].lower() for u in rep.data["parent"]["unanswered"])


def test_no_personal_identifiers_in_report_or_pdf_text(seeded, db):
    rep = _report(db)
    for leak in ["9800000001", "parent.test@example.com", "attacker@example.com"]:
        assert leak not in rep.html and leak not in rep.text
    assert "[phone redacted]" in rep.html or "[email redacted]" in rep.html or "[phone redacted]" in rep.text


def test_injected_instructions_do_not_change_configuration_or_run_commands(seeded, db):
    before = (get_settings().report_recipient, get_settings().scheduler_enabled)
    rep = _report(db)
    assert (get_settings().report_recipient, get_settings().scheduler_enabled) == before
    assert not Path("/").joinpath("rm_was_run").exists()


def test_script_tags_from_messages_are_escaped_in_html(seeded, db):
    rep = _report(db)
    assert "<script>alert" not in rep.html
    # the injected <script> message is in the archive (escaped by Jinja/JS); the report body must never contain it raw
    assert "<script>" not in rep.html


def test_facts_inferences_and_recommendations_are_labelled(seeded, db):
    rep = _report(db)
    assert "verified" in rep.html.lower()
    assert "inferred" in rep.html.lower() or "inferred" in " ".join(rep.data["limitations"]).lower()
    assert "suggestions only" in " ".join(rep.data["limitations"]).lower()
    assert all(a.get("status") for a in rep.data["alerts"])
    assert all(a.get("role") for a in rep.data["actions"])


def test_report_is_stored_once_per_day_and_regeneration_updates_it(seeded, db):
    first = _report(db)
    second = _report(db)
    assert first.id == second.id                       # duplicate-safe: one row per report_date
    assert second.is_regeneration is True
    count = db.scalar(select(func.count()).select_from(DailyReport)
                      .where(DailyReport.report_date == TEST_DAY))
    assert count == 1


def test_action_register_is_created_with_roles_and_deadlines(seeded, db):
    _report(db)
    acts = list(db.scalars(select(ActionItem).where(ActionItem.report_date == TEST_DAY)))
    assert acts
    assert all(a.suggested_role and a.deadline and a.action_id.startswith("ACT-") for a in acts)
