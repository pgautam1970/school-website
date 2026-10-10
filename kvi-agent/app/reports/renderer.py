"""Report rendering: structured report data -> HTML email + plain-text version."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from jinja2 import Environment, FileSystemLoader, select_autoescape

from ..config import Settings

TEMPLATE_DIR = Path(__file__).parent / "templates"
_env = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=select_autoescape(["html", "xml", "j2"]),  # untrusted content escaped
)
_env_txt = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)), autoescape=False)


def render_report(data: dict, settings: Settings) -> tuple[str, str]:
    """Return (html, text). All message excerpts inside `data` are untrusted
    content and are HTML-escaped by Jinja autoescaping."""
    npt = ZoneInfo(settings.timezone)
    ctx = {
        "d": data,
        "school": settings.school_name,
        "address": settings.school_address,
        "report_uid": data.get("report_uid", ""),
        "generated_at_npt": datetime.now(npt).strftime("%Y-%m-%d %H:%M"),
        "dashboard_url": settings.public_dashboard_url,
    }
    html = _env.get_template("email.html.j2").render(**ctx)
    text = _env_txt.get_template("email.txt.j2").render(**ctx)
    return html, text
