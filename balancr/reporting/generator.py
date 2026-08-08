import os
from datetime import datetime
from typing import List, Tuple
from balancr.canonical import CanonicalTransaction, DiscrepancyCase, ReconciliationStatus
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

class ReconciliationReportGenerator:
    """
    Generates human-readable reconciliation reports in both Markdown and PDF formats.
    Updated for three-way (Gateway vs Bank vs Ledger) reconciliation runs.
    """
    @staticmethod
    def generate_markdown_report(
        matched_pairs: List[Tuple[CanonicalTransaction, CanonicalTransaction, CanonicalTransaction]],
        resolved_cases: List[DiscrepancyCase]
    ) -> str:
        """
        Creates a clean Markdown document summarizing the reconciliation run metrics and findings.
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        total_matched = len(matched_pairs)
        total_anomalies = len(resolved_cases)
        total_processed = total_matched * 3 + sum(
            1 for c in resolved_cases if (c.transaction_gateway is not None) or (c.transaction_bank is not None)
        )
        
        # Calculate rates
        resolved_ok = sum(1 for c in resolved_cases if c.status == ReconciliationStatus.MATCHED)
        effective_matches = total_matched + resolved_ok
        match_rate = (effective_matches / (total_matched + total_anomalies)) * 100 if (total_matched + total_anomalies) > 0 else 100.0

        md = []
        md.append("# Balancr — Reconciliation Run Report")
        md.append(f"**Execution Timestamp:** {timestamp}")
        md.append("")
        md.append("## Executive Summary")
        md.append(f"- **Total Input Records Evaluated:** {total_processed}")
        md.append(f"- **Deterministic Exact Matches:** {total_matched} groups (3-way)")
        md.append(f"- **Anomalies Investigated by LLM:** {total_anomalies}")
        md.append(f"  - *Timing Mismatches Cleared:* {resolved_ok}")
        md.append(f"  - *Outstanding Discrepancies:* {total_anomalies - resolved_ok}")
        md.append(f"- **Effective Match Rate:** **{match_rate:.2f}%**")
        md.append("")
        
        md.append("## 1. Resolved Timing Mismatches & Matches")
        if total_matched > 0 or resolved_ok > 0:
            md.append("| Reference | Source Gateway ID | Bank TX ID | Ledger TX ID | Amount | Status | Details |")
            md.append("|---|---|---|---|---|---|---|")
            # Exact matches
            for g_tx, b_tx, l_tx in matched_pairs:
                md.append(f"| {g_tx.reference} | {g_tx.id} | {b_tx.id} | {l_tx.id} | {g_tx.amount} {g_tx.currency} | MATCHED | Deterministic 3-way match |")
            # LLM cleared timing mismatches
            for c in resolved_cases:
                if c.status == ReconciliationStatus.MATCHED:
                    g_id = c.transaction_gateway.id if c.transaction_gateway else "N/A"
                    b_id = c.transaction_bank.id if c.transaction_bank else "N/A"
                    ref = c.transaction_gateway.reference if c.transaction_gateway else (c.transaction_bank.reference if c.transaction_bank else "N/A")
                    amount = c.transaction_gateway.amount if c.transaction_gateway else (c.transaction_bank.amount if c.transaction_bank else 0.0)
                    currency = c.transaction_gateway.currency if c.transaction_gateway else (c.transaction_bank.currency if c.transaction_bank else "USD")
                    md.append(f"| {ref} | {g_id} | {b_id} | N/A | {amount} {currency} | CLEARED | {c.explanation} |")
        else:
            md.append("*No successful matches recorded in this run.*")
        md.append("")
        
        md.append("## 2. Unresolved / Critical Discrepancies")
        outstanding = [c for c in resolved_cases if c.status != ReconciliationStatus.MATCHED]
        if outstanding:
            md.append("| Reference | Category | Gateway Amount | Bank Amount | Explanation / Action Item |")
            md.append("|---|---|---|---|---|")
            for c in outstanding:
                g_ref = c.transaction_gateway.reference if c.transaction_gateway else "N/A"
                b_ref = c.transaction_bank.reference if c.transaction_bank else "N/A"
                ref = g_ref if g_ref != "N/A" else b_ref
                g_amt = f"{c.transaction_gateway.amount} {c.transaction_gateway.currency}" if c.transaction_gateway else "N/A"
                b_amt = f"{c.transaction_bank.amount} {c.transaction_bank.currency}" if c.transaction_bank else "N/A"
                cat = c.discrepancy_type.value if c.discrepancy_type else "UNKNOWN"
                md.append(f"| {ref} | {cat} | {g_amt} | {b_amt} | {c.explanation} |")
        else:
            md.append("*No outstanding anomalies detected. All balances reconcile successfully!*")
        md.append("")
        
        return "\n".join(md)

    @staticmethod
    def generate_pdf_report(
        matched_pairs: List[Tuple[CanonicalTransaction, CanonicalTransaction, CanonicalTransaction]],
        resolved_cases: List[DiscrepancyCase],
        output_path: str
    ) -> None:
        """
        Generates a premium styled PDF summary document using ReportLab.
        """
        # Create directories if missing
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

        doc = SimpleDocTemplate(
            output_path, 
            pagesize=letter,
            rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36
        )
        
        styles = getSampleStyleSheet()
        
        # Define clean, premium colors
        primary_color = colors.HexColor("#1A365D")   # Navy Dark
        secondary_color = colors.HexColor("#2B6CB0") # Blue Accent
        neutral_dark = colors.HexColor("#2D3748")    # Slate Charcoal
        neutral_light = colors.HexColor("#EDF2F7")   # Light Gray
        alert_red = colors.HexColor("#C53030")       # Warning Red

        title_style = ParagraphStyle(
            'DocTitle',
            parent=styles['Heading1'],
            fontName='Helvetica-Bold',
            fontSize=22,
            textColor=primary_color,
            spaceAfter=15
        )
        
        section_style = ParagraphStyle(
            'SectionHeader',
            parent=styles['Heading2'],
            fontName='Helvetica-Bold',
            fontSize=14,
            textColor=secondary_color,
            spaceBefore=15,
            spaceAfter=8
        )

        body_style = ParagraphStyle(
            'BodyTextCustom',
            parent=styles['BodyText'],
            fontName='Helvetica',
            fontSize=10,
            textColor=neutral_dark,
            spaceAfter=6
        )

        table_header_style = ParagraphStyle(
            'TableHeader',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=9,
            textColor=colors.white
        )

        table_cell_style = ParagraphStyle(
            'TableCell',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=8,
            textColor=neutral_dark
        )

        story = []

        # Document Header
        story.append(Paragraph("BALANCR — RECONCILIATION SUMMARY REPORT", title_style))
        story.append(Paragraph(f"<b>Generated At:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", body_style))
        story.append(Spacer(1, 10))

        # Metrics Block
        total_matched = len(matched_pairs)
        total_anomalies = len(resolved_cases)
        resolved_ok = sum(1 for c in resolved_cases if c.status == ReconciliationStatus.MATCHED)
        match_rate = ((total_matched + resolved_ok) / (total_matched + total_anomalies)) * 100 if (total_matched + total_anomalies) > 0 else 100.0

        metrics_data = [
            [
                Paragraph("<b>Deterministic Matches</b>", body_style),
                Paragraph(f"{total_matched} groups", body_style),
                Paragraph("<b>LLM Anomalies Analyzed</b>", body_style),
                Paragraph(f"{total_anomalies}", body_style),
            ],
            [
                Paragraph("<b>Timing Matches Cleared</b>", body_style),
                Paragraph(f"{resolved_ok}", body_style),
                Paragraph("<b>Effective Match Rate</b>", body_style),
                Paragraph(f"<b>{match_rate:.2f}%</b>", body_style),
            ]
        ]
        
        metrics_table = Table(metrics_data, colWidths=[130, 130, 130, 130])
        metrics_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), neutral_light),
            ('BOX', (0,0), (-1,-1), 1, secondary_color),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('PADDING', (0,0), (-1,-1), 8),
        ]))
        story.append(metrics_table)
        story.append(Spacer(1, 15))

        # Section 1: Resolved Records
        story.append(Paragraph("1. Reconciled and Cleared Transactions", section_style))
        
        resolved_headers = ["Reference", "Gateway ID", "Bank ID", "Ledger ID", "Amount", "Cleared Details"]
        resolved_rows = [[Paragraph(h, table_header_style) for h in resolved_headers]]
        
        # Populate exact matches
        for g_tx, b_tx, l_tx in matched_pairs:
            resolved_rows.append([
                Paragraph(g_tx.reference or "N/A", table_cell_style),
                Paragraph(g_tx.id, table_cell_style),
                Paragraph(b_tx.id, table_cell_style),
                Paragraph(l_tx.id, table_cell_style),
                Paragraph(f"{g_tx.amount} {g_tx.currency}", table_cell_style),
                Paragraph("Exact 3-way match confirmed.", table_cell_style),
            ])
            
        # Populate timing matches
        for c in resolved_cases:
            if c.status == ReconciliationStatus.MATCHED:
                ref = c.transaction_gateway.reference if c.transaction_gateway else (c.transaction_bank.reference if c.transaction_bank else "N/A")
                g_id = c.transaction_gateway.id if c.transaction_gateway else "N/A"
                b_id = c.transaction_bank.id if c.transaction_bank else "N/A"
                amount = c.transaction_gateway.amount if c.transaction_gateway else (c.transaction_bank.amount if c.transaction_bank else 0.0)
                currency = c.transaction_gateway.currency if c.transaction_gateway else (c.transaction_bank.currency if c.transaction_bank else "USD")
                resolved_rows.append([
                    Paragraph(ref, table_cell_style),
                    Paragraph(g_id, table_cell_style),
                    Paragraph(b_id, table_cell_style),
                    Paragraph("N/A", table_cell_style),
                    Paragraph(f"{amount} {currency}", table_cell_style),
                    Paragraph(c.explanation or "", table_cell_style),
                ])
                
        if len(resolved_rows) > 1:
            resolved_table = Table(resolved_rows, colWidths=[65, 65, 65, 65, 75, 185])
            resolved_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), primary_color),
                ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
                ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, neutral_light]),
                ('PADDING', (0,0), (-1,-1), 5),
                ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ]))
            story.append(resolved_table)
        else:
            story.append(Paragraph("<i>No records reconciled in this block.</i>", body_style))
            
        story.append(Spacer(1, 15))

        # Section 2: Unresolved / Discrepancies
        story.append(Paragraph("2. Outstanding / Critical Discrepancies", section_style))
        
        disc_headers = ["Reference", "Category", "Gateway Amount", "Bank Amount", "Reasoning & Action Item"]
        disc_rows = [[Paragraph(h, table_header_style) for h in disc_headers]]
        
        outstanding = [c for c in resolved_cases if c.status != ReconciliationStatus.MATCHED]
        for c in outstanding:
            g_ref = c.transaction_gateway.reference if c.transaction_gateway else "N/A"
            b_ref = c.transaction_bank.reference if c.transaction_bank else "N/A"
            ref = g_ref if g_ref != "N/A" else b_ref
            g_amt = f"{c.transaction_gateway.amount} {c.transaction_gateway.currency}" if c.transaction_gateway else "N/A"
            b_amt = f"{c.transaction_bank.amount} {c.transaction_bank.currency}" if c.transaction_bank else "N/A"
            cat = c.discrepancy_type.value if c.discrepancy_type else "UNKNOWN"
            
            disc_rows.append([
                Paragraph(ref, table_cell_style),
                Paragraph(cat, table_cell_style),
                Paragraph(g_amt, table_cell_style),
                Paragraph(b_amt, table_cell_style),
                Paragraph(c.explanation or "", table_cell_style),
            ])
            
        if len(disc_rows) > 1:
            disc_table = Table(disc_rows, colWidths=[75, 75, 75, 75, 220])
            disc_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), alert_red),
                ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
                ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, neutral_light]),
                ('PADDING', (0,0), (-1,-1), 5),
                ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ]))
            story.append(disc_table)
        else:
            story.append(Paragraph("<i>No outstanding discrepancies detected. All balances reconcile successfully!</i>", body_style))

        # Build Document
        doc.build(story)
