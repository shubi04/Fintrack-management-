"""
FinTrack AI - Institutional Financial Statement PDF Generator
Built using ReportLab with clean typography, tables, and brand theme.
"""

from io import BytesIO
from decimal import Decimal
from django.utils import timezone
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from .templatetags.money import format_inr
from .models import Transaction, Category


def generate_financial_pdf(user, start_date=None, end_date=None):
    """
    Generates a professional financial account statement PDF in a BytesIO buffer.
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#6C5CE7")
    )
    sub_style = ParagraphStyle(
        "SubText",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#6B7280")
    )
    h2_style = ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#1F2937")
    )
    cell_style = ParagraphStyle(
        "CellText",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=11
    )
    cell_bold = ParagraphStyle(
        "CellBold",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=11
    )

    story = []

    # Header section
    today = timezone.localdate()
    period_str = f"{start_date.strftime('%d %b %Y')} to {end_date.strftime('%d %b %Y')}" if start_date and end_date else "All Time"

    header_data = [
        [
            Paragraph("<b>FinTrack AI</b><br/><font size=8 color='#6B7280'>Smart Expense &amp; Financial Management</font>", title_style),
            Paragraph(f"<b>STATEMENT OF ACCOUNT</b><br/><font size=8 color='#6B7280'>Generated: {today.strftime('%d %b %Y')}<br/>Period: {period_str}</font>", sub_style)
        ]
    ]
    t_header = Table(header_data, colWidths=[300, 240])
    t_header.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
    ]))
    story.append(t_header)
    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#E5E7EB"), spaceBefore=5, spaceAfter=15))

    # Account Holder Info
    user_name = user.get_full_name() or user.username
    user_info = [
        [Paragraph(f"<b>Account Holder:</b> {user_name}", cell_style), Paragraph(f"<b>Email:</b> {user.email}", cell_style)],
        [Paragraph(f"<b>Account Status:</b> Active", cell_style), Paragraph(f"<b>Currency:</b> INR (₹)", cell_style)],
    ]
    t_user = Table(user_info, colWidths=[270, 270])
    t_user.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F9FAFB")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(t_user)
    story.append(Spacer(1, 15))

    # Query Transactions
    tx_qs = Transaction.objects.filter(user=user).select_related("category")
    if start_date:
        tx_qs = tx_qs.filter(date__gte=start_date)
    if end_date:
        tx_qs = tx_qs.filter(date__lte=end_date)
    tx_qs = tx_qs.order_by("-date", "-id")

    inc_total = sum(t.amount for t in tx_qs if t.kind == "income") or Decimal(0)
    exp_total = sum(t.amount for t in tx_qs if t.kind == "expense") or Decimal(0)
    net_savings = inc_total - exp_total
    savings_rate = f"{int((net_savings / inc_total) * 100)}%" if inc_total > 0 else "0%"

    # Summary Cards Table
    story.append(Paragraph("Financial Summary", h2_style))
    story.append(Spacer(1, 6))

    summary_data = [
        ["Total Income", "Total Expenses", "Net Savings", "Savings Rate"],
        [format_inr(inc_total, 2), format_inr(exp_total, 2), format_inr(net_savings, 2), savings_rate]
    ]
    t_summary = Table(summary_data, colWidths=[135, 135, 135, 135])
    t_summary.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F3F4F6")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#374151")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("PADDING", (0, 0), (-1, -1), 8),
        ("TEXTCOLOR", (0, 1), (0, 1), colors.HexColor("#10B981")),
        ("TEXTCOLOR", (1, 1), (1, 1), colors.HexColor("#F43F5E")),
        ("TEXTCOLOR", (2, 1), (2, 1), colors.HexColor("#6C5CE7")),
        ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
    ]))
    story.append(t_summary)
    story.append(Spacer(1, 15))

    # Category Spend Breakdown
    cat_totals = {}
    for t in tx_qs:
        if t.kind == "expense":
            cname = t.category.name if t.category else "Uncategorised"
            cat_totals[cname] = cat_totals.get(cname, Decimal(0)) + t.amount

    if cat_totals:
        story.append(Paragraph("Category Spending Breakdown", h2_style))
        story.append(Spacer(1, 6))
        cat_rows = [["Category", "Total Spent", "% of Total Expenses"]]
        for cname, camt in sorted(cat_totals.items(), key=lambda x: x[1], reverse=True)[:6]:
            pct = f"{(camt / exp_total * 100):.1f}%" if exp_total > 0 else "0%"
            cat_rows.append([cname, format_inr(camt, 2), pct])

        t_cats = Table(cat_rows, colWidths=[240, 150, 150])
        t_cats.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F9FAFB")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8.5),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
            ("PADDING", (0, 0), (-1, -1), 5),
            ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ]))
        story.append(t_cats)
        story.append(Spacer(1, 15))

    # Itemized Transactions Ledger
    story.append(Paragraph(f"Transaction History ({tx_qs.count()} entries)", h2_style))
    story.append(Spacer(1, 6))

    tx_table_data = [["Date", "Type", "Category", "Description", "Amount"]]
    for t in tx_qs[:60]:
        t_type = "Income" if t.kind == "income" else "Expense"
        cname = t.category.name if t.category else "—"
        note = t.note or "—"
        sign = "+" if t.kind == "income" else "-"
        amt_str = f"{sign}{format_inr(t.amount, 2)}"
        tx_table_data.append([
            t.date.strftime("%d %b %Y"),
            t_type,
            cname[:20],
            Paragraph(note[:35], cell_style),
            amt_str
        ])

    if len(tx_table_data) == 1:
        tx_table_data.append(["—", "—", "—", "No transactions found in this period.", "—"])

    t_tx = Table(tx_table_data, colWidths=[75, 55, 90, 210, 110])
    t_tx.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#6C5CE7")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
        ("PADDING", (0, 0), (-1, -1), 4),
        ("ALIGN", (4, 0), (4, -1), "RIGHT"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F9FAFB")]),
    ]))
    story.append(t_tx)
    story.append(Spacer(1, 20))

    # Footer
    story.append(Paragraph(
        "This is a computer-generated financial statement and requires no physical signature.<br/>"
        "FinTrack AI Platform · Powered by Django, Scikit-Learn &amp; ReportLab",
        sub_style
    ))

    doc.build(story)
    buffer.seek(0)
    return buffer
