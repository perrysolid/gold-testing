"""FR-11.3: PDF pre-approval letter generation via WeasyPrint."""
from __future__ import annotations

import structlog

from app.assess.schemas import DecisionResult

logger = structlog.get_logger()

_HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<style>
  body {{ font-family: sans-serif; margin: 40px; color: #1a1a1a; }}
  h1 {{ color: #D4AF37; }}
  .pill {{ display: inline-block; padding: 4px 16px; border-radius: 20px;
           background: {pill_color}; color: white; font-weight: bold; }}
  .row {{ margin: 8px 0; }}
  .label {{ color: #666; font-size: 13px; }}
</style>
</head>
<body>
  <h1>Aurum Pre-Assessment Letter</h1>
  <p>Assessment ID: <code>{assessment_id}</code></p>
  <div class="row"><span class="pill">{decision}</span></div>
  <div class="row"><span class="label">Headline:</span> {headline}</div>
  {loan_section}
  <h3>Why we said this</h3>
  <ul>
    {bullets}
  </ul>
  <p><em>{next_steps}</em></p>
  <p style="color:#999;font-size:11px;">This is a preliminary estimate only. Final valuation requires
  physical inspection at a branch. Valid for 14 days from assessment date.</p>
</body>
</html>"""


async def generate_pre_approval_pdf(result: DecisionResult) -> bytes:
    """FR-11.3: Generate PDF bytes for the pre-approval letter."""
    pill_colors = {"PRE_APPROVE": "#2E7D32", "NEEDS_VERIFICATION": "#F29D38", "REJECT": "#C62828"}
    color = pill_colors.get(result.decision, "#666")

    loan_section = ""
    if result.max_loan_inr and result.decision != "REJECT":
        loan_section = f'<div class="row"><span class="label">Maximum Loan:</span> ₹{result.max_loan_inr:,}</div>'

    bullets = "\n".join(f"<li>{b}</li>" for b in result.why)

    html = _HTML_TEMPLATE.format(
        assessment_id=result.assessment_id,
        decision=result.decision,
        headline=result.headline,
        loan_section=loan_section,
        bullets=bullets,
        next_steps=result.next_steps_md,
        pill_color=color,
    )

    try:
        from weasyprint import HTML  # type: ignore[import]
        return HTML(string=html).write_pdf()
    except ImportError:
        logger.warning("pdf.weasyprint_not_installed", fallback="html_bytes")
        return html.encode()
