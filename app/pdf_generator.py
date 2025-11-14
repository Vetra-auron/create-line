"""PDF 생성과 인쇄 유틸리티."""
from __future__ import annotations

import os
import platform
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Iterable

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

from .models import QuoteDocument, QuoteItem


def _build_items_table(items: Iterable[QuoteItem]):
    header = ["품명", "Model No.", "수량", "단위", "단가", "금액"]
    data = [header] + [item.to_row() for item in items]

    table = Table(data, colWidths=[60 * mm, 40 * mm, 20 * mm, 20 * mm, 25 * mm, 25 * mm])
    table_style = TableStyle(
        [
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
            ("ALIGN", (2, 1), (-1, -1), "CENTER"),
            ("ALIGN", (4, 1), (-1, -1), "RIGHT"),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 11),
            ("FONTSIZE", (0, 1), (-1, -1), 10),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
        ]
    )
    table.setStyle(table_style)
    return table


def generate_pdf(document: QuoteDocument, output_path: Path) -> Path:
    """QuoteDocument 데이터를 기반으로 PDF를 생성한다."""

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(str(output_path), pagesize=A4, rightMargin=20 * mm, leftMargin=20 * mm)
    styles = getSampleStyleSheet()
    normal = styles["Normal"]
    bold = ParagraphStyle("Bold", parent=normal, fontName="Helvetica-Bold", fontSize=14)

    elements = []
    elements.append(Paragraph("견적서", ParagraphStyle("Title", parent=bold, alignment=1, fontSize=18)))
    elements.append(Spacer(1, 6 * mm))

    info_style = ParagraphStyle("Info", parent=normal, fontSize=11, leading=16)
    info_text = (
        f"<b>업체명:</b> {document.company_name}<br/>"
        f"<b>날짜:</b> {document.quotation_date.strftime('%Y-%m-%d')}"
    )
    elements.append(Paragraph(info_text, info_style))
    elements.append(Spacer(1, 4 * mm))

    elements.append(_build_items_table(document.items))
    elements.append(Spacer(1, 6 * mm))

    total_style = ParagraphStyle("Total", parent=normal, fontSize=12, alignment=2)
    elements.append(Paragraph(f"합계: {document.total_amount:,.0f} 원", total_style))
    elements.append(Spacer(1, 6 * mm))

    if document.cause:
        elements.append(Paragraph(f"<b>원인:</b> {document.cause}", info_style))
    if document.repair_detail:
        elements.append(Paragraph(f"<b>수리 내역:</b> {document.repair_detail}", info_style))

    doc.build(elements)
    return output_path


def print_pdf(pdf_path: Path) -> None:
    """플랫폼에 맞게 PDF를 인쇄한다."""

    pdf_path = Path(pdf_path)
    system = platform.system()

    if system == "Windows":
        os.startfile(str(pdf_path), "print")  # type: ignore[attr-defined]
    elif system == "Darwin":
        subprocess.run(["lp", str(pdf_path)], check=False)
    else:
        subprocess.run(["lp", str(pdf_path)], check=False)


def default_filename(base: str = "quotation") -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{base}_{timestamp}.pdf"
