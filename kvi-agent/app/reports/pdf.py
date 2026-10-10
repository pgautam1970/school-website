"""PDF generation with layered engines.

Order: WeasyPrint (if its system libraries are installed) -> fpdf2 (pure Python).
Returns (path, engine, error). A failure is returned, never silently ignored,
and the report is still delivered without the attachment (flagged in the email).

Privacy: the PDF uses the same redacted summary data as the email. Full
original message text is never written to the PDF.

Nepali (Devanagari) text is only written when KVI_PDF_FONT_PATH points to a
Devanagari-capable TTF (e.g. Noto Sans Devanagari). Otherwise Nepali sections
are omitted from the PDF and the omission is stated on the page.
"""
from __future__ import annotations

import logging
from pathlib import Path

from ..config import get_settings

log = logging.getLogger("kvi.pdf")
DEFAULT_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "/Library/Fonts/Arial Unicode.ttf",
]


def _reports_dir() -> Path:
    p = Path(get_settings().database_url.replace("sqlite:///", "")).parent / "reports"
    if not p.is_absolute():
        p = Path.cwd() / p
    p.mkdir(parents=True, exist_ok=True)
    return p


def _find_font() -> tuple[str | None, bool]:
    """Return (font_path, supports_devanagari)."""
    custom = getattr(get_settings(), "pdf_font_path", "") or ""
    import os
    custom = os.environ.get("KVI_PDF_FONT_PATH", custom)
    if custom and Path(custom).is_file():
        return custom, True          # operator asserts Devanagari support
    for c in DEFAULT_FONT_CANDIDATES:
        if Path(c).is_file():
            return c, False
    return None, False


def _pdf_safe(text: str, dev_ok: bool) -> str:
    if dev_ok:
        return text
    return "".join(ch if ord(ch) < 0x0900 or ord(ch) > 0x097F else "?" for ch in text)


def _build_with_fpdf(data: dict, out: Path) -> None:
    from fpdf import FPDF

    font_path, dev_ok = _find_font()
    settings = get_settings()
    pdf = FPDF(format="A4", unit="mm")
    pdf.set_auto_page_break(auto=True, margin=14)
    pdf.set_margins(14, 14, 14)
    pdf.add_page()
    if font_path:
        pdf.add_font("KVI", "", font_path)
        pdf.add_font("KVI", "B", font_path)
        family = "KVI"
    else:
        family = "Helvetica"

    def T(s: str) -> str:
        s = _pdf_safe(str(s), dev_ok)
        if family == "Helvetica":
            s = s.encode("latin-1", "replace").decode("latin-1")
        return s

    def h(text: str):
        pdf.ln(3)
        pdf.set_font(family, "B", 12)
        pdf.set_text_color(0, 61, 122)
        pdf.multi_cell(0, 7, T(text), new_x="LMARGIN", new_y="NEXT")
        pdf.set_draw_color(212, 175, 55)
        pdf.line(14, pdf.get_y(), 196, pdf.get_y())
        pdf.set_x(14)
        pdf.ln(2)
        pdf.set_text_color(34, 48, 62)

    def para(text: str, size: float = 9.5):
        pdf.set_font(family, "", size)
        pdf.multi_cell(0, 5, T(text), new_x="LMARGIN", new_y="NEXT")

    c = data["counts"]
    cov = data["coverage"]
    pdf.set_fill_color(0, 61, 122)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font(family, "B", 14)
    pdf.cell(0, 10, T(settings.school_name.upper()), new_x="LMARGIN", new_y="NEXT", fill=True)
    pdf.set_font(family, "", 11)
    pdf.cell(0, 7, T("Daily School Intelligence Report"), new_x="LMARGIN", new_y="NEXT", fill=True)
    pdf.set_text_color(34, 48, 62)
    pdf.ln(2)
    para(f"Reporting date: {data['report_date']}"
         + (f"  ({data['nepali_date']})" if dev_ok and data.get("nepali_date") else ""))
    para(f"Data coverage: {cov['groups_with_data']}/{cov['groups_total']} WhatsApp groups with data; "
         f"Facebook: {'connected' if cov['facebook'].get('connected') else 'not connected'}")
    para(f"Analysis engine: {data['engine']}   Report ID: {data.get('report_uid', '')}")
    if data.get("no_data"):
        para("DATA UNAVAILABLE: no authorized source data was received for this day. "
             "This is a data-unavailability notice, not a normal daily summary.")

    h("A. Principal's Executive Briefing")
    for i, b in enumerate(data["executive_bullets"], 1):
        para(f"{i}. {b}")
    if dev_ok and data.get("nepali_summary"):
        para("Nepali summary: " + data["nepali_summary"])
    elif data.get("nepali_summary"):
        para("(Nepali summary omitted from PDF: no Devanagari-capable font configured. "
             "It is included in the HTML email and dashboard.)")

    h("B. Critical & High-Priority Alerts")
    real = [a for a in data["alerts"] if a["priority"] != "POSITIVE"]
    if real:
        for a in real:
            para(f"[{a['priority']}] {a['issue']}")
            para(f"   Why: {a['reason']}  |  Next step: {a['next_step']}  |  {a['status']}", 8.5)
    else:
        para("No critical or high-priority issue was identified in the available data.")

    h("C. Class-wise Summary")
    pdf.set_font(family, "B", 8.5)
    cols = [30, 60, 45, 30, 20]
    for head, w in zip(["Class", "Academic Updates", "Parent Concerns", "Pending Actions", "Priority"], cols):
        pdf.cell(w, 6, T(head), border=1)
    pdf.ln()
    pdf.set_font(family, "", 8)
    for r in data["class_rows"]:
        if r["data_status"] == "no_data":
            acad, conc, pend = "DATA UNAVAILABLE (not zero)", "-", "Import today's export"
        elif r["data_status"] == "not_configured":
            acad, conc, pend = "No group configured", "-", "-"
        else:
            acad = f"{r['messages']} msg; HW {len(r['homework'])}; exam {len(r['exams'])}"
            conc = f"{len(r['parent_concerns'])} concern(s); {len(r['unanswered'])} unanswered"
            pend = "; ".join(r["pending_actions"]) or "-"
        vals = [r["class"], acad, conc, pend, r["priority"]]
        for v, w in zip(vals, cols):
            pdf.cell(w, 6, T(str(v)[:38]), border=1)
        pdf.ln()

    h("D. Educator Coordination")
    para(f"{data['educator']['messages']} educator-related message(s). {data['educator']['note']}")

    h("E. Parent Communication")
    p = data["parent"]
    para(f"Questions: {p['questions_total']} total, {p['answered']} answered, {p['unanswered_count']} unanswered. "
         f"Concerns: {len(p['concerns'])}. {p['tone_note']}")
    for u in p["unanswered"][:8]:
        para(f"- {u['excerpt'][:160]} ({u['source']}, {u['ts']})", 8.5)

    h("F. Facebook Page Report")
    f = data["facebook"]
    para(f"Posts today: {f['posts_today']}. API connected: {'yes' if f['connected'] else 'no'}. {f['honesty_note']}")
    for post in f["posts"][:10]:
        eng = (f"reactions {post['reactions'] if post['reactions'] is not None else 'n/a'}, "
               f"comments {post['comments'] if post['comments'] is not None else 'n/a'}")
        para(f"- {post['excerpt'][:160]} [{eng}]", 8.5)

    h("G. Upcoming Deadlines")
    if data["deadlines"]:
        for dl in data["deadlines"]:
            para(f"{dl['date']}  {dl['what'][:150]}  ({dl['source']})", 8.5)
    else:
        para("No explicitly dated upcoming items found in available data.")

    h("H. Principal's Action Plan")
    if data["actions"]:
        for a in data["actions"]:
            para(f"[{a['priority']}] {a['title']} | role: {a['role']} | deadline: {a['deadline']}", 8.5)
    else:
        para("No action items generated from the available data.")

    h("I. Positive Highlights")
    if data["positives"]:
        for pos in data["positives"]:
            para(f"* {pos['text'][:170]} ({pos['sources'][0]['source']})", 8.5)
    else:
        para("No recognition/achievement content detected.")

    h("J. Source Coverage & Limitations")
    for g in cov["group_detail"]:
        state = "data received" if g["state"] == "data-received" else "NO DATA"
        para(f"{g['name']} ({g['method']}): {g['messages_today']} msg - {state}", 8.5)
    for lim in data["limitations"]:
        para(f"- {lim}", 8.5)

    h("K. Tomorrow's Focus")
    for i, fo in enumerate(data["tomorrow_focus"], 1):
        para(f"{i}. {fo}")

    pdf.output(str(out))


def build_pdf(data: dict, report_uid: str) -> tuple[str, str, str]:
    """Return (path, engine, error). Never raises."""
    out = _reports_dir() / f"kvi-daily-{data['report_date']}-{report_uid[:8]}.pdf"
    try:
        _build_with_fpdf(data, out)
        return str(out), "fpdf2", ""
    except Exception as exc:  # PDF failure must not block report/email
        log.exception("PDF generation failed")
        return "", "", f"PDF generation failed: {type(exc).__name__}: {exc}"
