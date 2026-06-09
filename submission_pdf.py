"""
Generates a clean PDF of the submitted brief — all form fields + file list.
This becomes the "source document" sent alongside the review memo.
"""
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.pdfgen import canvas as pdfcanvas
from datetime import datetime
import re, os

PW, PH = A4
LM = RM = 22*mm
TM = BM = 22*mm
CW = PW - LM - RM

RED    = HexColor("#C0392B")
NAVY   = HexColor("#1A2744")
SLATE  = HexColor("#2C3E50")
GRAY   = HexColor("#5D6D7E")
LGRAY  = HexColor("#95A5A6")
RULE   = HexColor("#BDC3C7")
BGLT   = HexColor("#F8F9FA")
WHITE  = HexColor("#FFFFFF")

def clean(t):
    if not t: return ""
    t = str(t).replace('&lt;','<').replace('&gt;','>').replace('&amp;','&')
    t = re.sub(r'<[^>]+>', '', t)
    return t.strip()

def S(name, **kw):
    base = dict(fontName='Helvetica', fontSize=10, textColor=SLATE, leading=15,
                spaceAfter=3, spaceBefore=0, alignment=TA_LEFT)
    base.update(kw)
    return ParagraphStyle(name, **base)

class BriefCanvas(pdfcanvas.Canvas):
    def __init__(self, *args, project_name="", **kwargs):
        super().__init__(*args, **kwargs)
        self._pages = []
        self._project = project_name

    def showPage(self):
        self._pages.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        n = len(self._pages)
        for i, state in enumerate(self._pages):
            self.__dict__.update(state)
            self._draw_header()
            self._draw_footer(i+1, n)
            super().showPage()
        super().save()

    def _draw_header(self):
        self.saveState()
        self.setFont("Helvetica-Bold", 9)
        self.setFillColor(RED)
        self.drawString(LM, PH - 14*mm, "REDBOARD")
        self.setFont("Helvetica", 8)
        self.setFillColor(LGRAY)
        x_after_red = LM + self.stringWidth("REDBOARD", "Helvetica-Bold", 9) + 4
        self.drawString(x_after_red, PH - 14*mm, "  |  Submission Brief")
        self.setFont("Helvetica", 7)
        self.drawRightString(PW - RM, PH - 14*mm, "CONFIDENTIAL")
        self.setStrokeColor(RULE)
        self.setLineWidth(0.5)
        self.line(LM, PH - 16*mm, PW - RM, PH - 16*mm)
        self.restoreState()

    def _draw_footer(self, num, total):
        self.saveState()
        self.setStrokeColor(RULE)
        self.setLineWidth(0.5)
        self.line(LM, 16*mm, PW - RM, 16*mm)
        self.setFont("Helvetica", 7)
        self.setFillColor(LGRAY)
        self.drawString(LM, 12*mm, f"Redboard Submission Brief  |  {self._project}  |  Confidential")
        self.drawRightString(PW - RM, 12*mm, f"Page {num} of {total}")
        self.restoreState()


def field_row(label, value, styles):
    """Render a label + value pair."""
    if not value or not str(value).strip(): return []
    rows = [[
        Paragraph(label.upper(), S('lbl', fontName='Helvetica-Bold', fontSize=8,
                                    textColor=RED, leading=12)),
        Paragraph(clean(str(value)), S('val', fontSize=10, textColor=SLATE,
                                        leading=15, alignment=TA_JUSTIFY)),
    ]]
    t = Table(rows, colWidths=[42*mm, CW - 42*mm])
    t.setStyle(TableStyle([
        ('VALIGN',(0,0),(-1,-1),'TOP'),
        ('TOPPADDING',(0,0),(-1,-1),6),
        ('BOTTOMPADDING',(0,0),(-1,-1),6),
        ('LEFTPADDING',(0,0),(-1,-1),0),
        ('RIGHTPADDING',(0,0),(-1,-1),0),
        ('LINEBELOW',(0,0),(-1,0),0.3,RULE),
    ]))
    return [t]


def generate_submission_pdf(output_path, project_name, review_id, submitter, company,
                             proposal, context, team, timeline, objectives, risks_known,
                             stakeholders, tech_stack, userbase="", domain="", geographies="",
                             regulatory="", data_sensitivity="", human_oversight="",
                             rollback_plan="", success_metrics="", file_names=None):
    """Generate a clean PDF of all submitted brief data."""

    doc = SimpleDocTemplate(
        output_path, pagesize=A4,
        rightMargin=RM, leftMargin=LM,
        topMargin=TM + 6*mm, bottomMargin=BM,
        title=f"Redboard Submission Brief - {project_name}",
        author=submitter or "Redboard",
    )

    styles_ref = {}  # not used beyond helpers

    story = []

    # ── Cover header ──
    left = [
        Paragraph('<font color="#C0392B" size="24"><b>Red</b></font><font color="#1A2744" size="24"><b>board</b></font>',
                  S('logo')),
        Paragraph('Submission Brief', S('sub', fontSize=9, textColor=LGRAY, spaceAfter=0)),
    ]
    right = [
        Paragraph(
            f'<b>{clean(project_name)}</b><br/>'
            f'Review ID: {review_id[:8].upper()}<br/>'
            f'{datetime.utcnow().strftime("%d %B %Y, %H:%M UTC")}<br/>'
            f'<b>CONFIDENTIAL</b>',
            S('meta', fontSize=8, textColor=GRAY, alignment=TA_RIGHT, leading=14)
        )
    ]
    mast = Table([[left, right]], colWidths=[90*mm, 76*mm])
    mast.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),
                               ('TOPPADDING',(0,0),(-1,-1),0),
                               ('BOTTOMPADDING',(0,0),(-1,-1),0),
                               ('LEFTPADDING',(0,0),(-1,-1),0),
                               ('RIGHTPADDING',(0,0),(-1,-1),0)]))
    story.append(mast)
    story.append(HRFlowable(width=CW, thickness=3, color=RED, spaceAfter=10))

    # Submitted by
    if submitter or company:
        parts = []
        if submitter: parts.append(f'<b>{clean(submitter)}</b>')
        if company:   parts.append(f'<b>{clean(company)}</b>')
        story.append(Paragraph('Submitted by: ' + '  |  '.join(parts),
                               S('by', fontSize=8, textColor=GRAY)))
        story.append(Spacer(1, 5*mm))

    # ── Section: Project Overview ──
    story.append(Paragraph('PROJECT OVERVIEW', S('sh', fontName='Helvetica-Bold',
                                                   fontSize=11, textColor=NAVY,
                                                   spaceBefore=6, spaceAfter=5)))
    story.append(HRFlowable(width=CW, thickness=0.5, color=RULE, spaceAfter=6))

    for label, value in [
        ('Project Name',   project_name),
        ('Team',           team),
        ('Timeline',       timeline),
        ('Tech Stack',     tech_stack),
    ]:
        story.extend(field_row(label, value, styles_ref))

    story.append(Spacer(1, 4*mm))

    # ── Section: Proposal ──
    story.append(Paragraph('PROPOSAL', S('sh', fontName='Helvetica-Bold',
                                          fontSize=11, textColor=NAVY,
                                          spaceBefore=6, spaceAfter=5)))
    story.append(HRFlowable(width=CW, thickness=0.5, color=RULE, spaceAfter=6))
    story.append(Paragraph(clean(proposal), S('body', fontSize=10, textColor=SLATE,
                                               leading=15, alignment=TA_JUSTIFY)))
    story.append(Spacer(1, 4*mm))

    # ── Section: Context ──
    story.append(Paragraph('CONTEXT AND TECHNICAL DETAILS', S('sh', fontName='Helvetica-Bold',
                                                                fontSize=11, textColor=NAVY,
                                                                spaceBefore=6, spaceAfter=5)))
    story.append(HRFlowable(width=CW, thickness=0.5, color=RULE, spaceAfter=6))
    story.append(Paragraph(clean(context), S('body', fontSize=10, textColor=SLATE,
                                              leading=15, alignment=TA_JUSTIFY)))
    story.append(Spacer(1, 4*mm))

    # ── Section: Objectives ──
    if objectives:
        story.append(Paragraph('OBJECTIVES', S('sh', fontName='Helvetica-Bold',
                                                fontSize=11, textColor=NAVY,
                                                spaceBefore=6, spaceAfter=5)))
        story.append(HRFlowable(width=CW, thickness=0.5, color=RULE, spaceAfter=6))
        story.append(Paragraph(clean(objectives), S('body', fontSize=10, textColor=SLATE,
                                                    leading=15, alignment=TA_JUSTIFY)))
        story.append(Spacer(1, 4*mm))

    # ── Section: Company and User Context ──
    has_context = any([userbase, domain, geographies, stakeholders])
    if has_context:
        story.append(Paragraph('COMPANY AND USER CONTEXT', S('sh', fontName='Helvetica-Bold',
                                                               fontSize=11, textColor=NAVY,
                                                               spaceBefore=6, spaceAfter=5)))
        story.append(HRFlowable(width=CW, thickness=0.5, color=RULE, spaceAfter=6))
        for label, value in [
            ('User Base',    userbase),
            ('Domain',       domain),
            ('Geographies',  geographies),
            ('Stakeholders', stakeholders),
        ]:
            story.extend(field_row(label, value, styles_ref))
        story.append(Spacer(1, 4*mm))

    # ── Section: Risk and Governance ──
    has_risk = any([risks_known, regulatory, data_sensitivity, human_oversight,
                    rollback_plan, success_metrics])
    if has_risk:
        story.append(Paragraph('RISK AND GOVERNANCE', S('sh', fontName='Helvetica-Bold',
                                                          fontSize=11, textColor=NAVY,
                                                          spaceBefore=6, spaceAfter=5)))
        story.append(HRFlowable(width=CW, thickness=0.5, color=RULE, spaceAfter=6))
        for label, value in [
            ('Known Risks',       risks_known),
            ('Regulatory',        regulatory),
            ('Data Sensitivity',  data_sensitivity),
            ('Human Oversight',   human_oversight),
            ('Rollback Plan',     rollback_plan),
            ('Success Metrics',   success_metrics),
        ]:
            story.extend(field_row(label, value, styles_ref))
        story.append(Spacer(1, 4*mm))

    # ── Section: Attached Documents ──
    if file_names and any(f.strip() for f in file_names):
        story.append(Paragraph('ATTACHED DOCUMENTS', S('sh', fontName='Helvetica-Bold',
                                                         fontSize=11, textColor=NAVY,
                                                         spaceBefore=6, spaceAfter=5)))
        story.append(HRFlowable(width=CW, thickness=0.5, color=RULE, spaceAfter=6))
        story.append(Paragraph(
            f'{len([f for f in file_names if f.strip()])} document(s) were attached to this review submission and are included in the accompanying source files archive.',
            S('body', fontSize=10, textColor=SLATE, leading=15)
        ))
        story.append(Spacer(1, 3*mm))
        for i, fname in enumerate([f for f in file_names if f.strip()], 1):
            story.append(Paragraph(
                f'<font color="#C0392B">{i}.</font>  {clean(fname)}',
                S('fl', fontSize=10, textColor=SLATE, leading=15, leftIndent=10)
            ))
        story.append(Spacer(1, 4*mm))

    # ── Closing ──
    story.append(HRFlowable(width=CW, thickness=0.5, color=RULE, spaceBefore=8, spaceAfter=6))
    story.append(Paragraph(
        f'This submission brief documents the information provided to the Redboard '
        f'Adversarial Review Panel for Review ID {review_id}. '
        f'It should be read alongside the accompanying decision memo. '
        f'Generated: {datetime.utcnow().strftime("%d %B %Y at %H:%M UTC")}.',
        S('sm', fontSize=8, textColor=LGRAY, leading=12)
    ))

    def make_canvas(*args, **kwargs):
        return BriefCanvas(*args, project_name=clean(project_name), **kwargs)

    doc.build(story, canvasmaker=make_canvas)
    return output_path