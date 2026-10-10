"""Stage 4 — Priority assessment.

Levels: CRITICAL / HIGH / MEDIUM / LOW / POSITIVE.

HARD RULE (spec): a message is never escalated because of emotional language,
capital letters or repeated punctuation. Evaluation runs on a *de-hyped* copy
(lowercased, punctuation collapsed, exclamation/caps ignored); only content
keywords, timing and context may drive the priority. Every result carries a
human-readable reason and the matched evidence terms.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# --- content signal sets (english / devanagari / romanized) -----------------
SAFETY_TERMS = [
    "accident", "fire", "flood", "earthquake", "snake", "dog bite", "injury",
    "injured", "hospital", "ambulance", "unconscious", "missing", "abuse",
    "violence", "fight", "bullying", "harass", "unsafe", "collapse", "electric shock",
    "दुर्घटना", "आगलागी", "आगो", "बाढी", "भूकम्प", "सर्प", "घाइते", "अस्पताल",
    "बेहोस", "हराएको", "दुर्व्यवहार", "झगडा", "असुरक्षित",
    "durghatana", "aago", "baadhi", "bhukampa", "sarpa", "ghaite", "aspatal", "jhgada",
]
URGENT_TERMS = [
    "urgent", "immediately", "asap", "emergency", "today itself", "right now", "तत्काल",
    "जरुरी", "आकस्मिक", "aapatkalin", "turuntai", "jharo",
]
DEADLINE_TERMS = [
    "deadline", "due", "submit by", "last date", "within", "before", "समयसीमा",
    "म्याद", "अन्तिम मिति", "भित्र", "samaya", "myaad", "bhitra",
]
EXAM_TERMS = [
    "exam", "examination", "test", "pre-board", "preboard", "board exam", "assessment",
    "परीक्षा", "pariksha",
]
NEAR_TERM_TERMS = [
    "today", "tonight", "tomorrow", "आज", "भोलि", "aaja", "bholi", "अभि", "यसै हप्ता",
    "this week", "आउँदो", "aaune", "next",
]
COMPLAINT_TERMS = [
    "complaint", "problem", "issue", "not good", "unfair", "dissatisf", "concern",
    "unacceptable", "disappointed", "unhappy", "not happy", "please fix", "poor service", "complain",
    "गुनासो", "समस्या", "gunaso", "samasya",
]
POSITIVE_TERMS = [
    "congratulations", "congrats", "proud", "winner", "prize", "medal", "first position",
    "excellent", "well done", "great job", "achievement", "appreciate",
    "बधाई", "शुभकामना", "पुरस्कार", "उत्कृष्ट", "गर्व", "badhai", "shubhakamana",
]


@dataclass
class PriorityResult:
    priority: str = "LOW"
    reason: str = ""
    evidence_terms: list[str] = field(default_factory=list)


def _dehype(text: str) -> str:
    """Strip shouting signals so caps/punctuation can never drive escalation."""
    t = text.lower()
    t = re.sub(r"[!?]+", " ", t)          # collapse repeated punctuation
    t = re.sub(r"(\w)\1{2,}", r"\1\1", t)  # collapse elongated words (soooo -> soo)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _hits(text: str, terms: list[str]) -> list[str]:
    found = []
    for term in terms:
        if re.search(r"[\u0900-\u097F]", term):
            if term in text:
                found.append(term)
        else:
            if re.search(r"(?<![a-z])" + re.escape(term) + r"(?![a-z])", text):
                found.append(term)
    return found


def assess_priority(normalized_text: str, categories: list[str], *,
                    is_question: bool = False, sender_kind: str = "unknown",
                    unanswered: bool = False) -> PriorityResult:
    """Content-only priority assessment. Input: normalized (lowercase) analysis text."""
    text = _dehype(normalized_text or "")
    res = PriorityResult()

    safety = _hits(text, SAFETY_TERMS)
    # CRITICAL requires a safety/security term AND a school-context anchor
    # (student/child/bus/school/building...) — avoids false positives like
    # "the accident chapter in our social studies book".
    context_anchor = _hits(text, [
        "student", "child", "children", "bus", "school", "class", "hostel", "campus",
        "विद्यार्थी", "बालबालिका", "विद्यालय", "कक्षा", "hostel",
        "bidyarthi", "balbalika", "vidyalaya",
    ]) or sender_kind == "parent"

    if safety and context_anchor:
        res.priority = "CRITICAL"
        res.reason = ("Safety/security terms present in a school context: "
                      + ", ".join(f"'{t}'" for t in safety[:4])
                      + ". Requires immediate verification with the concerned staff.")
        res.evidence_terms = safety[:6]
        return res

    urgent = _hits(text, URGENT_TERMS)
    exam = _hits(text, EXAM_TERMS)
    near = _hits(text, NEAR_TERM_TERMS)
    deadline = _hits(text, DEADLINE_TERMS)
    complaint = _hits(text, COMPLAINT_TERMS)
    positive = _hits(text, POSITIVE_TERMS)

    # HIGH: time-sensitive matters -----------------------------------------
    if urgent:
        res.priority = "HIGH"
        res.reason = "Explicit urgency language: " + ", ".join(f"'{t}'" for t in urgent[:3]) + "."
        res.evidence_terms = urgent
        return res
    if exam and near:
        res.priority = "HIGH"
        res.reason = ("Examination/assessment mentioned with a near-term time reference ("
                      + ", ".join(f"'{t}'" for t in near[:3]) + ").")
        res.evidence_terms = exam + near
        return res
    if deadline and near:
        res.priority = "HIGH"
        res.reason = "A deadline falls within the near term: " + ", ".join(f"'{t}'" for t in deadline + near[:3]) + "."
        res.evidence_terms = deadline + near
        return res
    if unanswered and is_question and sender_kind == "parent":
        res.priority = "HIGH"
        res.reason = "Parent question flagged as still unanswered in the imported conversation."
        res.evidence_terms = ["unanswered-question"]
        return res

    # POSITIVE ---------------------------------------------------------------
    if "Positive achievements & recognition" in categories and positive:
        res.priority = "POSITIVE"
        res.reason = "Recognition/appreciation content: " + ", ".join(f"'{t}'" for t in positive[:3]) + "."
        res.evidence_terms = positive
        return res

    # MEDIUM -----------------------------------------------------------------
    if is_question and sender_kind == "parent":
        res.priority = "MEDIUM"
        res.reason = "Parent question — confirm it received a response."
        res.evidence_terms = ["question"]
        return res
    if complaint:
        # complaints are MEDIUM (follow-up), never HIGH on wording alone
        res.priority = "MEDIUM"
        res.reason = "A concern/problem was mentioned (" + ("parent-raised" if sender_kind == "parent" else "reported") + "): " + ", ".join(f"'{t}'" for t in complaint[:3]) + "."
        res.evidence_terms = complaint
        return res
    if "Homework & assignments" in categories or "Examinations & assessments" in categories \
            or "Administrative instructions" in categories or "School announcements" in categories \
            or "Teacher coordination" in categories:
        res.priority = "MEDIUM"
        res.reason = "Operationally relevant school communication (" + ", ".join(categories[:2]) + ")."
        res.evidence_terms = categories[:3]
        return res

    # LOW ---------------------------------------------------------------------
    res.priority = "LOW"
    res.reason = "Routine information; no time-sensitive or safety content detected."
    res.evidence_terms = categories[:2]
    return res
