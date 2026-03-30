import csv
import html
import re
from io import BytesIO, StringIO

from django.http import HttpResponse

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False


def sanitize_filename_stem(value, fallback):
    candidate = (value or "").strip()
    if not candidate:
        candidate = fallback

    candidate = re.sub(r"[\\/:*?\"<>|]+", "_", candidate)
    candidate = re.sub(r"\s+", " ", candidate).strip(" .")
    return candidate or fallback


def build_csv_response(headers, rows, filename):
    output = StringIO()
    output.write("\ufeff")
    writer = csv.writer(output)
    writer.writerow([normalize_export_cell(header) for header in headers])
    for row in rows:
        writer.writerow([normalize_export_cell(value) for value in row])

    response = HttpResponse(output.getvalue(), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def normalize_export_cell(value, *, multiline=False):
    text = "" if value is None else str(value)
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    if not lines:
        return "-"
    if multiline:
        return "\n".join(lines)
    return " | ".join(lines)


def normalize_pdf_export_cell(value):
    text = normalize_export_cell(value, multiline=True)
    escaped = html.escape(text).replace("\n", "<br/>")
    return escaped.replace(" &quot;", "<br/>&quot;")


def build_table_pdf_response(
    *,
    headers,
    rows,
    filename,
    title_text="",
    empty_message="Sin datos",
):
    if not REPORTLAB_AVAILABLE:
        raise RuntimeError("reportlab is not installed")

    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=24,
        rightMargin=24,
        topMargin=24,
        bottomMargin=24,
    )

    styles = getSampleStyleSheet()
    cell_style = ParagraphStyle(
        "ExportCell",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=8,
        leading=10,
        wordWrap="CJK",
        spaceAfter=0,
        spaceBefore=0,
    )
    header_style = ParagraphStyle(
        "ExportHeader",
        parent=styles["BodyText"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        wordWrap="CJK",
        textColor=colors.black,
        spaceAfter=0,
        spaceBefore=0,
    )
    story = []
    if title_text:
        story.extend(
            [
                Paragraph(f"<b>{title_text}</b>", styles["Title"]),
                Spacer(1, 10),
            ]
        )

    normalized_rows = rows or [[empty_message] + ([""] * (len(headers) - 1))]
    table_rows = [
        [Paragraph(normalize_pdf_export_cell(value), header_style) for value in headers],
        *[
            [
                Paragraph(
                    normalize_pdf_export_cell(value),
                    cell_style,
                )
                for value in row
            ]
            for row in normalized_rows
        ],
    ]
    available_width = document.width
    col_width = available_width / max(len(headers), 1)
    table = Table(table_rows, repeatRows=1, colWidths=[col_width] * len(headers))
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e7ecfb")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#b7bfd4")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(table)
    document.build(story)

    response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
