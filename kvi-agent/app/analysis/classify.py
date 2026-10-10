"""Stage 3 — Classification.

Deterministic, transparent keyword+pattern classifier assigning one or more of
the 17 spec categories. Supports English, Nepali (Devanagari) and Romanized
Nepali. Every assignment records WHICH terms matched, so priorities always
carry explainable evidence. A hosted LLM (when configured) may refine
summaries, but classification evidence stays rule-based and auditable.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

CATEGORIES = [
    "Academic planning",
    "Teaching & learning",
    "Homework & assignments",
    "Examinations & assessments",
    "Student attendance & welfare",
    "Parent communication",
    "Teacher coordination",
    "Administrative instructions",
    "Events & extracurricular",
    "Fees & financial",
    "Transport & logistics",
    "School announcements",
    "Public relations & social media",
    "Complaints & unresolved concerns",
    "Urgent operational matters",
    "Positive achievements & recognition",
    "Other school matters",
]

# term lists: english + devanagari + romanized nepali
LEXICON: dict[str, list[str]] = {
    "Academic planning": [
        "lesson plan", "syllabus", "curriculum", "unit plan", "teaching plan", "scheme of work",
        "पाठ योजना", "पाठ्यक्रम", "योजना",
    ],
    "Teaching & learning": [
        "worksheet", "teaching material", "textbook", "chapter", "revision", "classwork",
        "project work", "lab", "practical", "study", "padhaune", "padhai", "sikaune",
        "कक्षा", "पढाइ", "अध्याय", "शिक्षण",
    ],
    "Homework & assignments": [
        "homework", "home work", "assignment", "notebook", "copy", "submit", "deadline",
        "गृहकार्य", "काज", "गृहकार्य जम्मा", "नोटबुक",
        "grihakarya", "kaam gharma",
    ],
    "Examinations & assessments": [
        "exam", "examination", "test", "assessment", "marks", "result", "grade", "routine",
        "terminal", "pre-board", "preboard", "model question", "गुणस्तर",
        "परीक्षा", "परीक्षण", "अङ्क", "नतिजा", "तालिका", "मूल्याङ्कन",
        "pariksha", "nati ja", "result", "prashna",
    ],
    "Student attendance & welfare": [
        "attendance", "absent", "leave", "sick", "fever", "health", "counselling", "welfare",
        "lunch", "tiffin", "उपस्थिति", "हाजिरी", "बिदा", "बिरामी", "ज्वरो", "स्वास्थ्य",
        "hajiri", "upasthiti", "birami", "chutti",
    ],
    "Parent communication": [
        "parent", "guardian", "abhibhavak", "आमाबुवा", "अभिभावक", "ptm", "parents meeting",
    ],
    "Teacher coordination": [
        "staff meeting", "teachers meeting", "teacher", "coordination", "department", "subject committee",
        "शिक्षक", "गुरु", "बैठक", "समन्वय",
        "baithak", "shikshak", "samannaya", "meeting",
    ],
    "Administrative instructions": [
        "notice", "instruction", "circular", "administration", "office", "principal", "directive",
        "सूचना", "निर्देशन", "प्रशासन", "प्रधानाध्यापक",
        "suchana", "nirdeshan", "hukam",
    ],
    "Events & extracurricular": [
        "event", "program", "programme", "competition", "sports", "debate", "dance", "singing",
        "annual function", "celebration", "festival", "dashain", "tihaar", "tihar", "saraswati",
        "कार्यक्रम", "उत्सव", "प्रतियोगिता", "खेलकुद", "दशैँ", "तिहार",
        "karyakram", "utsav", "khel",
    ],
    "Fees & financial": [
        "fee", "fees", "payment", "scholarship", "dues", "bill", "शुल्क", "किस्ता", "छुट",
        "shulka", "kista", "payment",
    ],
    "Transport & logistics": [
        "bus", "vehicle", "route", "driver", "transport", "hostel", "गाडी", "बस", "रुट", "चालक",
        "gadi", "bas", "route",
    ],
    "School announcements": [
        "announcement", "announced", "notice", "information", "सूचना", "घोषणा", "सूचित",
        "suchana", "ghoshana", "inform",
    ],
    "Public relations & social media": [
        "facebook", "page post", "social media", "website", "photo", "photograph", "reel",
        "फेसबुक", "पेज", "फोटो",
    ],
    "Complaints & unresolved concerns": [
        "complaint", "problem", "issue", "concern", "not satisfied", "unfair", "refuse",
        "unacceptable", "disappointed", "unhappy", "not happy", "please fix", "poor service", "complain",
        "गुनासो", "समस्या", "आपत्ति", "गुनासो छ",
        "gunaso", "samasya", "problem cha",
    ],
    "Urgent operational matters": [
        "urgent", "immediately", "asap", "emergency", "right now", "जरुरी", "तत्काल", "आकस्मिक",
        "jharo", "tatakal", "turuntai", "aapatkalin",
    ],
    "Positive achievements & recognition": [
        "congratulations", "congrats", "proud", "excellent", "well done", "winner", "prize",
        "medal", "achievement", "first position", "appreciate", "thank you", "thanks", "great job",
        "बधाई", "शुभकामना", "गर्व", "उत्कृष्ट", "पुरस्कार", "धन्यवाद",
        "badhai", "shubhakamana", "dhanyabad", "utkrishtha", "ramro",
    ],
}

# Precompile: devanagari terms match literally, latin terms as word-ish patterns.
_COMPILED: dict[str, list[tuple[str, re.Pattern]]] = {}
for cat, terms in LEXICON.items():
    pats = []
    for term in terms:
        if re.search(r"[\u0900-\u097F]", term):
            pats.append((term, re.compile(re.escape(term))))
        else:
            pats.append((term, re.compile(r"(?<![a-z])" + re.escape(term.lower()) + r"(?![a-z])")))
    _COMPILED[cat] = pats

QUESTION_WORDS = re.compile(
    r"(?<![a-z])\b(what|when|why|how|who|whom|whose|which|where|whether|can you|could you|"
    r"please tell|kina|kahile|kasari|ko ho|ke ho|ke garne|how to)\b(?![a-z])")
QUESTION_WORDS_NE = re.compile(r"(किन|कहिले|कसरी|के|को|कहाँ|कति)")
ANSWER_MARKERS = re.compile(
    r"(?<![a-z])\b(yes|done|noted|ok|okay|sure|will do|received|ji|thank|answered)\b(?![a-z])")
ANSWER_MARKERS_NE = re.compile(r"(हो|भयो|गरियो|ठिक|छ|जी|हुन्छ|धन्यवाद)")

STATUS_PATTERNS = {
    "planned": re.compile(r"(?<![a-z])\b(plan|planned|planning|going to|will be)\b(?![a-z])|योजना|गर्ने तयारी"),
    "announced": re.compile(r"(?<![a-z])\b(announce|announced|notice|circular)\b(?![a-z])|सूचना|घोषणा"),
    "in_progress": re.compile(r"(?<![a-z])\b(ongoing|in progress|continuing|running)\b(?![a-z])|भइरहेको|सुरु भयो"),
    "completed": re.compile(r"(?<![a-z])\b(completed|finished|concluded)\b(?![a-z])|सम्पन्न|पूरा भयो"),
    "delayed": re.compile(r"(?<![a-z])\b(postponed|delayed|rescheduled|cancelled|deferred)\b(?![a-z])|स्थगित|सरेको|रद्द"),
}


@dataclass
class Classification:
    categories: list[str] = field(default_factory=list)
    matched_terms: dict[str, list[str]] = field(default_factory=dict)
    is_question: bool = False
    activity_status: str = ""
    confidence: float = 0.5


def classify(normalized_text: str, *, sender_kind: str = "unknown",
             group_category: str = "") -> Classification:
    """Classify an analysis-normalized (lowercased) text copy."""
    text = normalized_text or ""
    result = Classification()
    matched_any = 0
    for cat, pats in _COMPILED.items():
        hits = [term for term, pat in pats if pat.search(text)]
        if hits:
            result.categories.append(cat)
            result.matched_terms[cat] = sorted(set(hits))[:6]
            matched_any += len(hits)

    # Context-based boosts (not keyword-only):
    if sender_kind == "parent" and ("Parent communication" not in result.categories):
        result.categories.append("Parent communication")
    if group_category in ("Administration & Management",) and not result.categories:
        result.categories.append("Administrative instructions")

    if not result.categories:
        result.categories.append("Other school matters")

    # Question detection (Devanagari, romanized or English interrogatives)
    if ("?" in text or QUESTION_WORDS.search(text) or QUESTION_WORDS_NE.search(text)) and len(text) > 8:
        # exclude rhetorical/positive patterns like "thank you?"
        result.is_question = True

    for status, pat in STATUS_PATTERNS.items():
        if pat.search(text):
            result.activity_status = status
            break

    # Confidence: more distinct evidence -> higher, capped.
    result.confidence = round(min(0.95, 0.35 + 0.15 * min(matched_any, 4)), 2)
    return result


def contains_answer(text: str) -> bool:
    t = (text or "").lower()
    return bool(ANSWER_MARKERS.search(t) or ANSWER_MARKERS_NE.search(text or ""))
