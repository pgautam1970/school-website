"""Daily analysis pipeline (spec section 5, stages 1-6 + insights of section 6).

Collection -> Normalization (done at ingest) -> Classification -> Priority ->
Deduplication/cross-source matching -> Evidence validation -> Insights ->
Report data structure. Fully deterministic and testable; the optional LLM only
refines summary prose (see summarizer.py).
"""
from __future__ import annotations

import logging
import re
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import CLASS_LEVELS, get_settings
from ..models import (ActionItem, DailyReport, FacebookComment, FacebookPage,
                      FacebookPost, Message, SyncLog, WhatsAppGroup)
from .classify import contains_answer
from .dedupe import Cluster, cluster_items
from .nepali_calendar import nepali_date_str
from .redact import redact_text
from .summarizer import summarize

log = logging.getLogger("kvi.pipeline")
NPT = ZoneInfo("Asia/Kathmandu")

TEACHER_GROUP_CATEGORIES = {"Subject Teachers", "Academic Coordination",
                            "Administration & Management", "Examination & Assessment"}
MONTHS = ["january", "february", "march", "april", "may", "june", "july",
          "august", "september", "october", "november", "december"]


# ------------------------------------------------------------------ window
def day_window_utc(report_date: str) -> tuple[datetime, datetime]:
    """NPT day window as UTC datetimes."""
    d = date.fromisoformat(report_date)
    start = datetime(d.year, d.month, d.day, 0, 0, 0, tzinfo=NPT)
    end = start + timedelta(days=1)
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)


def npt_iso(dt: datetime) -> str:
    return dt.astimezone(NPT).strftime("%Y-%m-%d %H:%M")


# ------------------------------------------------- question/answer marking
def mark_question_answers(db: Session, group_id: int) -> None:
    """A parent question is 'answered' if a teacher message with an answer
    marker follows it in the same group within 6 hours. Otherwise unanswered."""
    msgs = list(db.scalars(
        select(Message).where(Message.group_id == group_id)
        .order_by(Message.ts_original)))
    for i, m in enumerate(msgs):
        if not (m.is_question and m.sender_kind == "parent"):
            continue
        answered = None
        for later in msgs[i + 1:]:
            if later.ts_original > m.ts_original + timedelta(hours=6):
                break
            if later.sender_kind == "teacher" and contains_answer(later.text_normalized):
                answered = True
                break
            if later.sender_kind == "teacher":
                answered = answered if answered is not None else False
        m.question_answered = bool(answered)
    db.commit()


# ------------------------------------------------------- deadline extraction
_ISO_RE = re.compile(r"\b(20\d{2}-\d{2}-\d{2})\b")
_DMY_RE = re.compile(r"\b(\d{1,2})\s*(?:/|-)\s*(\d{1,2})(?:\s*(?:/|-)\s*(20\d{2}))?\b")
_MONTH_RE = re.compile(r"(?<![a-z])\b(\d{1,2})(?:st|nd|rd|th)?\s+(" + "|".join(MONTHS) + r")\b|"
                       r"\b(" + "|".join(MONTHS) + r")\s+(\d{1,2})(?:st|nd|rd|th)?\b")
_TOMORROW = re.compile(r"(?<![a-z])\b(tomorrow|bholi|भोलि)\b|भोलि")
_TODAY = re.compile(r"(?<![a-z])\b(today|tonight|aaja|आज)\b|आज")


def extract_deadline_date(text: str, report_d: date) -> str:
    """Best-effort explicit date extraction. Returns '' when nothing reliable."""
    m = _ISO_RE.search(text)
    if m:
        try:
            return date.fromisoformat(m.group(1)).isoformat()
        except ValueError:
            pass
    m = _MONTH_RE.search(text.lower())
    if m:
        day, mon = (m.group(1), m.group(2)) if m.group(1) else (m.group(4), m.group(3))
        try:
            mon_i = MONTHS.index(mon.lower()) + 1
            cand = date(report_d.year, mon_i, int(day))
            if cand < report_d - timedelta(days=1):
                cand = cand.replace(year=report_d.year + 1)
            return cand.isoformat()
        except ValueError:
            pass
    if _TOMORROW.search(text):
        return (report_d + timedelta(days=1)).isoformat()
    if _TODAY.search(text):
        return report_d.isoformat()
    return ""


# --------------------------------------------------------------- clustering
def build_clusters(db: Session, start: datetime, end: datetime,
                   redact: bool) -> tuple[list[Cluster], list[dict], dict]:
    """Collect + cluster the reporting window across all sources (stages 5-6)."""
    items: list[dict] = []
    groups = {g.id: g for g in db.scalars(select(WhatsAppGroup).where(WhatsAppGroup.is_active == True))}  # noqa: E712

    msgs = list(db.scalars(
        select(Message).where(Message.ts_original >= start, Message.ts_original < end)))
    for m in msgs:
        g = groups.get(m.group_id)
        if g is None or not g.include_in_reporting:
            continue
        text_for_report = m.text_redacted if redact else m.text_original
        items.append({
            "platform": "whatsapp", "source_name": g.name, "ts": m.ts_original,
            "sender": m.sender_label, "sender_kind": m.sender_kind,
            "text_normalized": m.text_normalized,
            "excerpt": (text_for_report or "")[:280],
            "categories": m.categories, "priority": m.priority,
            "priority_reason": m.priority_reason, "confidence": m.confidence,
            "ref_id": f"msg-{m.id}", "is_question": m.is_question,
            "question_answered": m.question_answered, "group": g,
            "activity_status": m.activity_status,
        })

    page = db.scalar(select(FacebookPage).where(FacebookPage.is_active == True))  # noqa: E712
    posts = []
    if page and page.include_in_reporting:
        posts = list(db.scalars(select(FacebookPost).where(
            FacebookPost.page_id == page.id,
            FacebookPost.published_at >= start, FacebookPost.published_at < end)))
    for p in posts:
        items.append({
            "platform": "facebook", "source_name": (page.name if page else "Facebook Page"),
            "ts": p.published_at, "sender": "Page",
            "text_normalized": re.sub(r"\s+", " ", (p.message or "").lower()),
            "excerpt": (redact_text(p.message) if redact else p.message or "")[:280],
            "categories": p.categories or [], "priority": p.priority or "LOW",
            "priority_reason": "", "confidence": 0.6,
            "ref_id": p.permalink or p.fb_post_id, "is_question": False,
            "question_answered": None, "group": None, "activity_status": "",
            "post": p,
        })

    clusters = cluster_items(items)
    return clusters, items, {"groups": groups, "posts": posts, "messages": msgs}


# ------------------------------------------------------------- coverage
def build_coverage(db: Session, groups: dict, items: list[dict], start, end,
                   fb_status: dict) -> dict:
    per_group = defaultdict(int)
    for it in items:
        if it["platform"] == "whatsapp":
            per_group[it["group"].id] += 1
    included = [g for g in groups.values() if g.include_in_reporting and not g.archived]
    with_data, missing = [], []
    for g in included:
        (with_data if per_group[g.id] else missing).append(g)
    return {
        "groups_total": len(included),
        "groups_with_data": len(with_data),
        "groups_missing_today": [g.name for g in missing],
        "group_detail": [
            {"name": g.name, "category": g.category, "class_level": g.class_level,
             "messages_today": per_group[g.id],
             "last_sync_at": npt_iso(g.last_sync_at) if g.last_sync_at else None,
             "last_message_at": npt_iso(g.last_message_at) if g.last_message_at else None,
             "method": g.collection_method,
             "state": "data-received" if per_group[g.id] else "no-data-today"}
            for g in sorted(included, key=lambda x: x.name)
        ],
        "whatsapp_mode": ("authorized exports / uploads — no live WhatsApp API access "
                          "is used or claimed"),
        "facebook": fb_status,
        "window_npt": f"{start.astimezone(NPT):%Y-%m-%d %H:%M} — {end.astimezone(NPT):%Y-%m-%d %H:%M} NPT",
    }


# --------------------------------------------------------------- insights
_LEVEL_PATTERNS = [(lv, re.compile(r"(?<![a-z0-9])" + re.escape(lv.lower()) + r"(?![0-9])"))
                   for lv in CLASS_LEVELS]


def level_of_group(g: WhatsAppGroup) -> str:
    """Exact class level: explicit field first, then whole-token match in the name.
    'Class 1' must never match 'Class 10' (word-boundary aware)."""
    if g.class_level in CLASS_LEVELS:
        return g.class_level
    nm = g.name.lower()
    for lv, pat in _LEVEL_PATTERNS:
        if pat.search(nm):
            return lv
    return ""


def class_insights(items: list[dict], groups: dict) -> list[dict]:
    active = [g for g in groups.values() if g.include_in_reporting]
    group_level = {g.id: level_of_group(g) for g in active}
    rows = []
    for level in CLASS_LEVELS:
        level_groups = [g for g in active if group_level[g.id] == level]
        if not level_groups:
            rows.append({"class": level, "data_status": "not_configured", "messages": 0,
                         "academic_updates": [], "homework": [], "exams": [],
                         "parent_concerns": [], "unanswered": [], "positives": [],
                         "pending_actions": [], "priority": "-"})
            continue
        ids = {g.id for g in level_groups}
        lvl_items = [it for it in items if it["platform"] == "whatsapp" and it["group"].id in ids]
        if not lvl_items:
            rows.append({"class": level, "data_status": "no_data", "messages": 0,
                         "academic_updates": [], "homework": [], "exams": [],
                         "parent_concerns": [], "unanswered": [], "positives": [],
                         "pending_actions": ["Import today's export for this class group"],
                         "priority": "UNKNOWN"})
            continue
        hw = [it for it in lvl_items if "Homework & assignments" in it["categories"]]
        ex = [it for it in lvl_items if "Examinations & assessments" in it["categories"]]
        pq = [it for it in lvl_items if it.get("is_question") and it["sender_kind"] == "parent"]
        un = [it for it in pq if it.get("question_answered") is False]
        pos = [it for it in lvl_items if it["priority"] == "POSITIVE"]
        comp = [it for it in lvl_items if "Complaints & unresolved concerns" in it["categories"]]
        crit = any(it["priority"] == "CRITICAL" for it in lvl_items)
        high = crit or any(it["priority"] == "HIGH" for it in lvl_items)
        rows.append({
            "class": level, "data_status": "available", "messages": len(lvl_items),
            "academic_updates": _dedup_excerpts([it["excerpt"] for it in lvl_items
                                                 if set(it["categories"]) & {"Academic planning", "Teaching & learning"}])[:3],
            "homework": _dedup_excerpts([it["excerpt"] for it in hw])[:4],
            "exams": _dedup_excerpts([it["excerpt"] for it in ex])[:3],
            "parent_concerns": _dedup_excerpts([it["excerpt"] for it in comp + pq])[:4],
            "unanswered": [{"excerpt": it["excerpt"], "sender": it["sender"],
                            "source": it["source_name"], "ts": npt_iso(it["ts"])} for it in un][:5],
            "positives": _dedup_excerpts([it["excerpt"] for it in pos])[:3],
            "pending_actions": ([f"{len(un)} parent question(s) awaiting response"] if un else []) +
                               ([f"{len(comp)} concern(s) to review"] if comp else []),
            "priority": "CRITICAL" if crit else ("HIGH" if high else
                         ("MEDIUM" if (un or comp or ex) else "LOW")),
        })
    return rows


def _dedup_excerpts(excerpts: list[str]) -> list[str]:
    seen, out = set(), []
    for e in excerpts:
        key = e[:60].lower()
        if key not in seen:
            seen.add(key)
            out.append(e)
    return out


def educator_insights(items: list[dict], groups: dict) -> dict:
    teacher_items = [it for it in items if it["platform"] == "whatsapp"
                     and (it["group"].category in TEACHER_GROUP_CATEGORIES
                          or it["sender_kind"] == "teacher")]
    def pick(cats):
        return [{"excerpt": it["excerpt"], "source": it["source_name"],
                 "ts": npt_iso(it["ts"]), "sender": it["sender"]}
                for it in teacher_items if set(it["categories"]) & cats][:6]
    planning = pick({"Academic planning", "Teaching & learning"})
    meetings = pick({"Teacher coordination"})
    admin = pick({"Administrative instructions"})
    exams = pick({"Examinations & assessments"})
    support = [it for it in teacher_items if "?" in it["excerpt"] or "support" in it["text_normalized"]]
    return {
        "messages": len(teacher_items),
        "groups_active": sorted({it["source_name"] for it in teacher_items}),
        "planning_resources": planning,
        "meetings_coordination": meetings + admin,
        "assessment_updates": exams,
        "support_requested": [{"excerpt": it["excerpt"], "source": it["source_name"]} for it in support][:5],
        "note": ("Shared messages are evidence of COMMUNICATION, not proof an activity was "
                 "completed. No teacher rankings are produced from message counts."),
        "activity_status_breakdown": _status_breakdown(teacher_items),
    }


def _status_breakdown(items: list[dict]) -> dict:
    counts = defaultdict(int)
    for it in items:
        counts[it.get("activity_status") or "unverified"] += 1
    return dict(counts)


def parent_insights(items: list[dict], clusters: list[Cluster]) -> dict:
    pq = [it for it in items if it["platform"] == "whatsapp" and it["sender_kind"] == "parent"
          and it.get("is_question")]
    unanswered = [it for it in pq if it.get("question_answered") is False]
    complaints = [it for it in items if it["platform"] == "whatsapp"
                  and it["sender_kind"] == "parent"
                  and "Complaints & unresolved concerns" in it["categories"]]
    positives = [it for it in items if it["platform"] == "whatsapp"
                 and it["sender_kind"] == "parent" and it["priority"] == "POSITIVE"]
    # cluster the questions to group similar concerns
    q_clusters = cluster_items([
        {"platform": "whatsapp", "source_name": it["source_name"], "ts": it["ts"],
         "sender": it["sender"], "text_normalized": it["text_normalized"],
         "excerpt": it["excerpt"], "categories": it["categories"],
         "priority": it["priority"], "confidence": it["confidence"],
         "ref_id": it["ref_id"], "priority_reason": ""}
        for it in pq], threshold=0.6)
    return {
        "questions_total": len(pq),
        "answered": sum(1 for it in pq if it.get("question_answered") is True),
        "unanswered_count": len(unanswered),
        "unanswered": [{"excerpt": it["excerpt"], "sender": it["sender"],
                        "source": it["source_name"], "ts": npt_iso(it["ts"]),
                        "status": "unresolved — no teacher reply found in imported data"}
                       for it in unanswered][:10],
        "question_clusters": [{"question": c.evidence[0].excerpt, "occurrences": c.source_count,
                               "sources": sorted({e.source_name for e in c.evidence})}
                              for c in sorted(q_clusters, key=lambda x: -x.source_count)[:8]],
        "concerns": [{"excerpt": it["excerpt"], "source": it["source_name"], "ts": npt_iso(it["ts"])}
                     for it in complaints][:8],
        "positive_feedback": [{"excerpt": it["excerpt"], "source": it["source_name"]}
                              for it in positives][:6],
        "gaps": ([f"{len(unanswered)} parent question(s) without a visible teacher response"]
                 if unanswered else []) +
                ([f"{len(complaints)} concern(s) raised — acknowledge and follow up"] if complaints else []),
        "tone_note": "Concerns are grouped and reported in neutral, respectful language; no parent is labelled.",
    }


def facebook_insights(posts: list, db: Session, fb_status: dict) -> dict:
    engagement_available = any(p.reactions is not None or p.comments_count is not None for p in posts)
    q_comments = []
    for p in posts:
        for c in p.comments:
            if c.is_question or "?" in (c.message or ""):
                q_comments.append({"post": (p.message or "")[:80], "comment": (c.message or "")[:200],
                                   "from": c.from_name, "permalink": p.permalink})
    delayed = [p for p in posts if re.search(r"postpone|delay|cancel|स्थगित|सरेको", (p.message or "").lower())]
    return {
        "connected": fb_status.get("connected", False),
        "status_detail": fb_status.get("detail", ""),
        "posts_today": len(posts),
        "posts": [{"excerpt": (p.message or "")[:300], "permalink": p.permalink,
                   "published": npt_iso(p.published_at) if p.published_at else "",
                   "reactions": p.reactions, "comments": p.comments_count,
                   "shares": p.shares, "source_kind": p.source_kind,
                   "categories": p.categories or []} for p in posts],
        "engagement_available": engagement_available,
        "questions_needing_response": q_comments[:8],
        "positive_feedback": [{"excerpt": (c.message or "")[:200], "from": c.from_name}
                              for p in posts for c in p.comments
                              if re.search(r"good|great|nice|बधाई|राम्रो|धन्यवाद", (c.message or "").lower())][:6],
        "posts_needing_clarification": [{"excerpt": (p.message or "")[:200], "permalink": p.permalink}
                                        for p in delayed],
        "suggested_content": (["Post a clarification/update about the rescheduled activity"] if delayed else []) +
                             (["Respond publicly or via admin to pending comment questions"] if q_comments else []),
        "honesty_note": ("Metrics shown are only what Meta provided or staff entered via manual import; "
                         "reach/impressions/follower-growth are never estimated."
                         if posts else "No posts recorded for this window."),
    }


def alerts_and_actions(clusters: list[Cluster], coverage: dict, parent: dict,
                       fb: dict, report_d: date) -> tuple[list[dict], list[dict]]:
    alerts = []
    actions = []
    order = {"CRITICAL": 0, "HIGH": 1}
    for c in sorted(clusters, key=lambda x: (order.get(x.priority, 9), -x.source_count)):
        if c.priority not in ("CRITICAL", "HIGH"):
            continue
        if c.priority == "POSITIVE":
            continue
        srcs = [{"platform": e.platform, "source": e.source_name,
                 "ts": npt_iso(e.ts) if e.ts else "", "sender": e.sender,
                 "excerpt": e.excerpt, "ref": e.ref_id} for e in c.evidence[:5]]
        alerts.append({
            "priority": c.priority, "issue": c.evidence[0].excerpt,
            "reason": c.priority_reason, "sources": srcs,
            "status": "verified — direct source evidence attached" if c.source_count else "inferred",
            "cross_source_count": c.source_count,
            "next_step": ("Verify immediately with concerned staff and inform Principal"
                          if c.priority == "CRITICAL" else
                          "Assign follow-up today; confirm resolution"),
        })

    role_for = lambda pr: "Principal" if pr == "CRITICAL" else (
        "Coordinator" if pr == "HIGH" else "Class Teacher")
    for a in alerts:
        actions.append({
            "title": ("Verify critical safety signal" if a["priority"] == "CRITICAL"
                      else "Follow up high-priority matter"),
            "detail": a["issue"], "priority": a["priority"],
            "role": role_for(a["priority"]),
            "deadline": (report_d + timedelta(days=1)).isoformat() if a["priority"] == "CRITICAL"
                        else (report_d + timedelta(days=2)).isoformat(),
            "evidence": a["sources"],
        })
    if parent["unanswered_count"]:
        actions.append({
            "title": f"Respond to {parent['unanswered_count']} unanswered parent question(s)",
            "detail": "; ".join(u["excerpt"][:80] for u in parent["unanswered"][:3]),
            "priority": "HIGH", "role": "Class Teacher",
            "deadline": (report_d + timedelta(days=1)).isoformat(),
            "evidence": [{"platform": "whatsapp", "source": u["source"], "excerpt": u["excerpt"],
                          "ts": u["ts"]} for u in parent["unanswered"][:3]],
        })
    missing = coverage["groups_missing_today"]
    if missing:
        actions.append({
            "title": f"Collect chat exports from {len(missing)} group(s) with no data today",
            "detail": ", ".join(missing[:8]), "priority": "MEDIUM",
            "role": "Administrative Staff",
            "deadline": (report_d + timedelta(days=1)).isoformat(),
            "evidence": [{"platform": "registry", "source": "source coverage",
                          "excerpt": f"no data received from: {', '.join(missing[:8])}"}],
        })
    if fb["questions_needing_response"]:
        actions.append({
            "title": f"Answer {len(fb['questions_needing_response'])} Facebook comment question(s)",
            "detail": fb["questions_needing_response"][0]["comment"][:120],
            "priority": "MEDIUM", "role": "Administrative Staff",
            "deadline": (report_d + timedelta(days=2)).isoformat(),
            "evidence": [{"platform": "facebook", "source": "page comments",
                          "excerpt": fb["questions_needing_response"][0]["comment"],
                          "ref": fb["questions_needing_response"][0]["permalink"]}],
        })
    return alerts, actions


def deadline_insights(clusters: list[Cluster], report_d: date) -> list[dict]:
    out = []
    for c in clusters:
        cats = set(c.categories)
        if not (cats & {"Examinations & assessments", "Homework & assignments",
                        "Events & extracurricular", "Teacher coordination",
                        "Administrative instructions"}):
            continue
        d = extract_deadline_date(c.primary_text, report_d)
        if not d:
            continue
        try:
            dd = date.fromisoformat(d)
        except ValueError:
            continue
        if dd < report_d or dd > report_d + timedelta(days=30):
            continue
        out.append({"date": d, "what": c.evidence[0].excerpt[:160],
                    "source": c.evidence[0].source_name,
                    "platform": c.evidence[0].platform,
                    "status": "verified — date stated in source text"})
    out.sort(key=lambda x: x["date"])
    return out[:15]


def positives_insights(clusters: list[Cluster]) -> list[dict]:
    out = []
    for c in clusters:
        if c.priority == "POSITIVE":
            out.append({"text": c.evidence[0].excerpt,
                        "sources": [{"platform": e.platform, "source": e.source_name,
                                     "ts": npt_iso(e.ts) if e.ts else ""} for e in c.evidence[:3]],
                        "cross_source_count": c.source_count})
    return out[:10]


def tomorrow_focus(actions: list[dict], deadlines: list[dict], alerts: list[dict]) -> list[str]:
    focus = []
    crit = [a for a in alerts if a["priority"] == "CRITICAL"]
    if crit:
        focus.append(f"Resolve/verify {len(crit)} critical alert(s) first thing in the morning.")
    un = [a for a in actions if "unanswered" in a["title"]]
    if un:
        focus.append(un[0]["title"] + " through the concerned class teachers.")
    soon = [d for d in deadlines if d["date"]]
    if soon:
        focus.append(f"Prepare for the nearest announced item: {soon[0]['what'][:80]} ({soon[0]['date']}).")
    high = [a for a in actions if a["priority"] == "HIGH" and "unanswered" not in a["title"]]
    if high:
        focus.append(f"Assign and track {len(high)} high-priority follow-up(s) in the action tracker.")
    focus.append("Review data coverage — ensure tomorrow's report receives exports from all registered groups.")
    return focus[:5]


# ------------------------------------------------------------------ main
def run_pipeline(db: Session, report_date: str, *, regenerate: bool = False) -> DailyReport:
    settings = get_settings()
    report_d = date.fromisoformat(report_date)
    start, end = day_window_utc(report_date)

    # 1) mark question answers for all active groups with data
    for g in db.scalars(select(WhatsAppGroup).where(WhatsAppGroup.is_active == True)):  # noqa: E712
        mark_question_answers(db, g.id)

    # 2) facebook connection status (honest, never assumed)
    from ..connectors.facebook_graph import FacebookGraphClient
    fb_st = FacebookGraphClient().status(timeout=8)
    fb_status = {"configured": fb_st.configured, "connected": fb_st.connected,
                 "page_name": fb_st.page_name, "page_url": fb_st.page_url,
                 "detail": fb_st.detail, "checked_at": fb_st.checked_at}

    # 3) collect + cluster
    clusters, items, refs = build_clusters(db, start, end, settings.redact_in_summaries)
    groups, posts, msgs = refs["groups"], refs["posts"], refs["messages"]
    coverage = build_coverage(db, groups, items, start, end, fb_status)

    # 4) insights
    class_rows = class_insights(items, groups)
    educator = educator_insights(items, groups)
    parent = parent_insights(items, clusters)
    facebook = facebook_insights(posts, db, fb_status)
    alerts, actions = alerts_and_actions(clusters, coverage, parent, facebook, report_d)
    deadlines = deadline_insights(clusters, report_d)
    positives = positives_insights(clusters)
    focus = tomorrow_focus(actions, deadlines, alerts)

    counts = {
        "messages": len([it for it in items if it["platform"] == "whatsapp"]),
        "fb_posts": len(posts),
        "groups_total": coverage["groups_total"],
        "groups_with_data": coverage["groups_with_data"],
        "critical": len([c for c in clusters if c.priority == "CRITICAL"]),
        "high": len([c for c in clusters if c.priority == "HIGH"]),
        "medium": len([c for c in clusters if c.priority == "MEDIUM"]),
        "positive": len([c for c in clusters if c.priority == "POSITIVE"]),
        "homework": len([it for it in items if "Homework & assignments" in it["categories"]]),
        "exam": len([it for it in items if "Examinations & assessments" in it["categories"]]),
        "meetings": len([it for it in items if "Teacher coordination" in it["categories"]]),
        "complaints": len([it for it in items if "Complaints & unresolved concerns" in it["categories"]]),
        "parent_questions": parent["questions_total"],
        "parent_unanswered": parent["unanswered_count"],
        "clusters": len(clusters),
        "languages": _lang_breakdown(msgs),
    }

    digest = {"counts": counts, "coverage": coverage,
              "alerts": [{k: v for k, v in a.items() if k != "sources"} for a in alerts],
              "class_rows": [{k: v for k, v in r.items()} for r in class_rows],
              "educator_groups": educator["groups_active"],
              "parent_gaps": parent["gaps"], "deadlines": deadlines,
              "facebook": {"posts_today": facebook["posts_today"],
                           "connected": facebook["connected"],
                           "questions": len(facebook["questions_needing_response"])}}
    summary = summarize(digest)

    # 5) limitations — always explicit
    limitations = list(summary.notes)
    limitations.append("WhatsApp data comes only from authorized exports/uploads; "
                       "the system has no live WhatsApp API connection and does not claim one.")
    if not fb_status["connected"]:
        limitations.append("Facebook Page API is not connected — "
                           + (fb_status["detail"] or "manual imports only."))
    if coverage["groups_missing_today"]:
        limitations.append(f"{len(coverage['groups_missing_today'])} registered group(s) provided no data "
                           f"for this reporting day: {', '.join(coverage['groups_missing_today'][:10])}.")
    if not items:
        limitations.append("NO source data at all was received for this reporting day. "
                           "This report is a data-unavailability notice, not a normal daily summary.")
    limitations.append("Findings labelled 'verified' quote real imported content; 'inferred' items are "
                       "interpretations; recommendations are suggestions only.")

    data = {
        "report_date": report_date,
        "nepali_date": nepali_date_str(report_d),
        "engine": summary.engine,
        "counts": counts,
        "executive_bullets": summary.executive_bullets,
        "nepali_summary": summary.nepali_summary,
        "alerts": alerts,
        "class_rows": class_rows,
        "educator": educator,
        "parent": parent,
        "facebook": facebook,
        "deadlines": deadlines,
        "actions": actions,
        "positives": positives,
        "coverage": coverage,
        "limitations": limitations,
        "tomorrow_focus": focus,
        "no_data": len(items) == 0,
    }

    # 6) persist report + actions (report_date UNIQUE => duplicate prevention)
    report = db.scalar(select(DailyReport).where(DailyReport.report_date == report_date))
    is_regen = report is not None
    if report is None:
        report = DailyReport(report_date=report_date)
        db.add(report)
    if report.id is None:
        db.add(report)
        db.flush()  # assigns report_uid default
    data["report_uid"] = report.report_uid
    report.nepali_date = data["nepali_date"]
    report.engine = summary.engine
    report.data = data
    report.coverage = coverage
    report.generated_at = datetime.now(timezone.utc)
    report.is_regeneration = regenerate or is_regen
    # Delivery status is NOT reset on regeneration: 'sent' means the provider accepted an email.

    # actions for this report date (refresh open ones)
    db.query(ActionItem).filter(ActionItem.report_date == report_date,
                                ActionItem.status == "open").delete()
    for a in actions:
        db.add(ActionItem(report_date=report_date, title=a["title"], detail=a["detail"],
                          priority=a["priority"], suggested_role=a["role"],
                          deadline=a["deadline"], evidence=a["evidence"], status="open"))

    # 7) render HTML/text + PDF
    from ..reports.renderer import render_report
    report.html, report.text = render_report(data, settings)
    from ..reports.pdf import build_pdf
    pdf_path, pdf_engine, pdf_err = build_pdf(data, report.report_uid)
    report.pdf_path = pdf_path
    report.pdf_engine = pdf_engine
    if pdf_err:
        report.data = {**report.data, "pdf_error": pdf_err}

    db.add(SyncLog(source_kind="pipeline", source_name=f"daily-report:{report_date}",
                   status="success", items_seen=len(items), items_new=len(clusters),
                   finished_at=datetime.now(timezone.utc)))
    db.commit()
    log.info("Report %s generated (engine=%s, items=%d, clusters=%d)",
             report_date, summary.engine, len(items), len(clusters))
    return report


def _lang_breakdown(msgs: list[Message]) -> dict:
    counts = defaultdict(int)
    for m in msgs:
        counts[m.language or "en"] += 1
    return dict(counts)
