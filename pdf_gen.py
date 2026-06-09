"""
Redboard PDF v4 — Prestigious, coloured, human-written feel.
Clean layout inspired by McKinsey/BCG reports and legal memos.
"""
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor, white, black
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether
)
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.pdfgen import canvas as pdfcanvas
from datetime import datetime
import re, os

# ── Page geometry ──────────────────────────────────────────────────────────────
PW, PH = A4
LM, RM = 22*mm, 22*mm
TM, BM = 22*mm, 24*mm
CW = PW - LM - RM   # ~166 mm

# ── Brand palette ──────────────────────────────────────────────────────────────
RED       = HexColor("#C0392B")   # Redboard red
DARKRED   = HexColor("#922B21")
NAVY      = HexColor("#1A2744")   # Deep navy for headings
SLATE     = HexColor("#2C3E50")   # Dark slate for body
MIDGRAY   = HexColor("#5D6D7E")   # Mid gray
LIGHTGRAY = HexColor("#95A5A6")   # Light gray
RULELINE  = HexColor("#BDC3C7")   # Thin rule
BGLIGHT   = HexColor("#F8F9FA")   # Very light background for boxes
BGYELLOW  = HexColor("#FFFBF0")   # Warm tint for important boxes
BGSALMON  = HexColor("#FFF5F5")   # Light red tint
BGGREEN   = HexColor("#F0FFF4")   # Light green tint
BGORANGE  = HexColor("#FFFAF0")   # Light orange tint
WHITE     = HexColor("#FFFFFF")
BLACK     = HexColor("#000000")

RISK_COLOR = {
    "CRITICAL": HexColor("#C0392B"),
    "HIGH":     HexColor("#D35400"),
    "MEDIUM":   HexColor("#B7950B"),
    "LOW":      HexColor("#1E8449"),
    "UNKNOWN":  MIDGRAY,
}

VERDICT_COLOR = {
    "SHIP":         HexColor("#1E8449"),
    "DO NOT SHIP":  HexColor("#C0392B"),
    "CONDITIONS":   HexColor("#D35400"),
}


# ── Utilities ──────────────────────────────────────────────────────────────────
def clean(t):
    if not t: return ""
    t = str(t)
    t = t.replace('&lt;','<').replace('&gt;','>').replace('&amp;','&')
    t = t.replace('\u2014', ' - ').replace('\u2013', '-').replace('\u2012', '-')
    # Strip all markdown — do NOT convert to tags because Gemini output has
    # filenames like sample_brief.txt and nested patterns that break ReportLab XML parsing
    t = re.sub(r'\*\*\*(.+?)\*\*\*', r'\1', t, flags=re.DOTALL)
    t = re.sub(r'\*\*(.+?)\*\*', r'\1', t, flags=re.DOTALL)
    t = re.sub(r'\*([^*\n]+?)\*', r'\1', t)
    t = re.sub(r'__(.+?)__', r'\1', t, flags=re.DOTALL)
    t = re.sub(r'_([^_\n]+?)_', r'\1', t)
    # Strip any HTML tags ReportLab doesn't support
    t = re.sub(r'<(?!/?(b|i|u|font|br)\b)[^>]+>', '', t)
    return t.strip()

def get_risk(text):
    t = str(text).upper()
    for r in ["CRITICAL","HIGH","MEDIUM","LOW"]:
        if r in t: return r
    return "UNKNOWN"

def get_verdict_key(verdict):
    v = str(verdict).upper()
    if "DO NOT" in v or "NOT SHIP" in v: return "DO NOT SHIP"
    if "CONDITION" in v: return "CONDITIONS"
    if "SHIP" in v: return "SHIP"
    return "DO NOT SHIP"

def extract_line(s, key):
    for l in s.split('\n'):
        if key+':' in l: return clean(l.split(':',1)[1])
    return ''

def extract_risks(s):
    lines = s.split('\n'); items = []; in_s = False
    for l in lines:
        if 'RISK SUMMARY:' in l: in_s = True; continue
        if in_s:
            if l.strip().startswith('- '): items.append(l.strip()[2:])
            elif l.strip() and not l.strip().startswith('-') and items: break
    return [clean(i) for i in items]

def section_items(s, key):
    lines = s.split('\n'); items = []; in_s = False
    for l in lines:
        if key+':' in l: in_s = True; continue
        if in_s:
            st = l.strip()
            if re.match(r'^\d+\.\s', st): items.append(re.sub(r'^\d+\.\s','',st))
            elif st.startswith('- '): items.append(st[2:])
            elif st and not st.startswith('-') and not re.match(r'^\d+', st) and items: in_s = False
    return [clean(i) for i in items if i.strip()]

def extract_dissent(s):
    lines = s.split('\n'); c = []; in_s = False
    for l in lines:
        if 'MINORITY DISSENT:' in l: in_s = True; continue
        if in_s:
            if any(x in l for x in ['RECOMMENDED NEXT','MEMO GENERATED','CLASSIFICATION']): break
            if l.strip(): c.append(l.strip())
    return clean(' '.join(c))


# ── Numbered canvas with header/footer ────────────────────────────────────────
class RedboardCanvas(pdfcanvas.Canvas):
    def __init__(self, *args, review_id="", **kwargs):
        super().__init__(*args, **kwargs)
        self._pages = []
        self._review_id = review_id

    def showPage(self):
        self._pages.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        n = len(self._pages)
        for i, state in enumerate(self._pages):
            self.__dict__.update(state)
            if i > 0:  # Skip header on page 1 (we draw it manually)
                self._draw_running_header()
            self._draw_footer(i+1, n)
            super().showPage()
        super().save()

    def _draw_running_header(self):
        self.saveState()
        # Left: Redboard mark — Red in red, gap, board in navy
        self.setFont("Helvetica-Bold", 9)
        self.setFillColor(RED)
        self.drawString(LM, PH - 14*mm, "RED")
        red_w = self.stringWidth("RED", "Helvetica-Bold", 9)
        self.setFillColor(NAVY)
        self.drawString(LM + red_w + 1, PH - 14*mm, "BOARD")
        board_w = self.stringWidth("BOARD", "Helvetica-Bold", 9)
        self.setFont("Helvetica", 8)
        self.setFillColor(MIDGRAY)
        self.drawString(LM + red_w + board_w + 8, PH - 14*mm, "Adversarial AI Review Panel")
        # Right: Confidential
        self.setFont("Helvetica", 7)
        self.setFillColor(LIGHTGRAY)
        self.drawRightString(PW - RM, PH - 14*mm, "CONFIDENTIAL")
        # Rule
        self.setStrokeColor(RULELINE)
        self.setLineWidth(0.5)
        self.line(LM, PH - 16*mm, PW-RM, PH - 16*mm)
        self.restoreState()

    def _draw_footer(self, num, total):
        self.saveState()
        self.setStrokeColor(RULELINE)
        self.setLineWidth(0.5)
        self.line(LM, 16*mm, PW-RM, 16*mm)
        self.setFont("Helvetica", 7)
        self.setFillColor(LIGHTGRAY)
        y = 12*mm
        self.drawString(LM, y, f"Redboard Decision Memo  |  Review ID: {self._review_id[:8].upper()}  |  Confidential  |  Internal Use Only")
        self.drawRightString(PW-RM, y, f"Page {num} of {total}")
        self.restoreState()


# ── Style factory ──────────────────────────────────────────────────────────────
def make_styles():
    def S(name, **kw):
        base = dict(fontName='Helvetica', fontSize=10, textColor=SLATE,
                    leading=15, spaceAfter=3, spaceBefore=0, alignment=TA_LEFT)
        base.update(kw)
        return ParagraphStyle(name, **base)

    return {
        # Cover
        'cover_logo_red':  S('clr', fontName='Helvetica-Bold', fontSize=28, textColor=RED, leading=32),
        'cover_logo_dark': S('cld', fontName='Helvetica-Bold', fontSize=28, textColor=NAVY, leading=32),
        'cover_sub':       S('cs',  fontSize=9, textColor=MIDGRAY, leading=13, spaceAfter=0),
        'cover_meta':      S('cm',  fontSize=8, textColor=MIDGRAY, leading=13, alignment=TA_RIGHT),

        # Proposal
        'proposal_label':  S('pl',  fontName='Helvetica-Bold', fontSize=8, textColor=RED,
                              leading=11, letterSpacing=1, spaceAfter=5),
        'proposal_text':   S('pt',  fontName='Helvetica-Bold', fontSize=13, textColor=NAVY,
                              leading=18, spaceAfter=0),

        # Verdict
        'verdict_label':   S('vl',  fontName='Helvetica-Bold', fontSize=8, textColor=MIDGRAY,
                              leading=11, letterSpacing=1),
        'verdict_ship':    S('vs',  fontName='Helvetica-Bold', fontSize=30, textColor=HexColor("#1E8449"),
                              leading=34, spaceAfter=3),
        'verdict_noship':  S('vn',  fontName='Helvetica-Bold', fontSize=30, textColor=RED,
                              leading=34, spaceAfter=3),
        'verdict_cond':    S('vc',  fontName='Helvetica-Bold', fontSize=28, textColor=HexColor("#D35400"),
                              leading=32, spaceAfter=3),
        'verdict_meta':    S('vm',  fontSize=10, textColor=SLATE, leading=15),
        'verdict_meta_b':  S('vmb', fontName='Helvetica-Bold', fontSize=10, textColor=NAVY, leading=15),

        # Section headings
        'h_section':       S('hs',  fontName='Helvetica-Bold', fontSize=12, textColor=NAVY,
                              leading=16, spaceBefore=14, spaceAfter=6),
        'h_agent':         S('ha',  fontName='Helvetica-Bold', fontSize=11, textColor=NAVY,
                              leading=15, spaceBefore=12, spaceAfter=3),
        'h_sub':           S('hsb', fontName='Helvetica-Bold', fontSize=9, textColor=RED,
                              leading=13, spaceBefore=8, spaceAfter=2),

        # Body text
        'body':            S('b',   fontSize=10, textColor=SLATE, leading=15, spaceAfter=4,
                              alignment=TA_JUSTIFY),
        'body_bold':       S('bb',  fontName='Helvetica-Bold', fontSize=10, textColor=NAVY,
                              leading=15, spaceAfter=4),
        'bullet':          S('bul', fontSize=10, textColor=SLATE, leading=15, spaceAfter=3,
                              leftIndent=14, firstLineIndent=0),
        'numbered':        S('num', fontSize=10, textColor=SLATE, leading=15, spaceAfter=4,
                              leftIndent=18, firstLineIndent=-18),
        'italic':          S('it',  fontName='Helvetica-Oblique', fontSize=10, textColor=MIDGRAY,
                              leading=15, spaceAfter=4, alignment=TA_JUSTIFY),
        'small':           S('sm',  fontSize=8, textColor=LIGHTGRAY, leading=12),
        'small_dark':      S('smd', fontSize=8, textColor=MIDGRAY, leading=12),
        'caption':         S('cap', fontName='Helvetica-Oblique', fontSize=8, textColor=MIDGRAY,
                              leading=12, spaceAfter=0),
        'mono':            S('mon', fontName='Courier', fontSize=8.5, textColor=SLATE, leading=13),

        # Risk table
        'risk_agent':      S('ra',  fontName='Helvetica-Bold', fontSize=9, textColor=NAVY, leading=13),
        'risk_level':      S('rl',  fontName='Helvetica-Bold', fontSize=9, textColor=SLATE, leading=13),
        'risk_detail':     S('rd',  fontSize=9, textColor=SLATE, leading=13),

        # Callout
        'callout':         S('co',  fontSize=10, textColor=SLATE, leading=15, spaceAfter=4,
                              leftIndent=12, alignment=TA_JUSTIFY),
        'callout_label':   S('col', fontName='Helvetica-Bold', fontSize=8, textColor=RED,
                              leading=11, letterSpacing=1, spaceAfter=4),
    }


# ── Cover page builder ─────────────────────────────────────────────────────────
def build_cover(review_id, proposal, submitter, company,
                verdict, confidence, risk_score, styles):
    story = []

    # ── Masthead bar ──
    # Red stripe drawn via table background + logo text
    logo_text = Paragraph(
        '<font color="#C0392B">Red</font><font color="#1A2744">board</font>',
        styles['cover_logo_red']  # we'll handle inline
    )
    # Use a simpler approach: two separate paragraphs in a table
    # Logo: Red in red, board in navy — use separate paragraphs with tight spacing
    logo_red_style   = ParagraphStyle('lr2', fontName='Helvetica-Bold', fontSize=28,
                                       textColor=RED, leading=32, spaceAfter=0)
    logo_dark_style  = ParagraphStyle('ld2', fontName='Helvetica-Bold', fontSize=28,
                                       textColor=NAVY, leading=32, spaceAfter=0)
    # Use a table with no spacing to join Red + board
    logo_table = Table([[
        Paragraph('<b>Red</b>', logo_red_style),
        Paragraph('<b>board</b>', logo_dark_style),
    ]], colWidths=[24*mm, 54*mm], hAlign='LEFT')
    logo_table.setStyle(TableStyle([
        ('TOPPADDING',(0,0),(-1,-1),0), ('BOTTOMPADDING',(0,0),(-1,-1),0),
        ('LEFTPADDING',(0,0),(-1,-1),0), ('RIGHTPADDING',(0,0),(-1,-1),0),
        ('VALIGN',(0,0),(-1,-1),'BOTTOM'),
    ]))
    left_top = [
        logo_table,
        Paragraph('Adversarial AI Review Panel', styles['cover_sub']),
    ]
    right_top = [
        Paragraph(
            f'Review ID: <b>{review_id[:8].upper()}</b><br/>'
            f'<br/>'
            f'{datetime.utcnow().strftime("%d %B %Y")}<br/>'
            f'{datetime.utcnow().strftime("%H:%M UTC")}<br/>'
            f'<br/>'
            f'<b>CONFIDENTIAL</b>',
            styles['cover_meta']
        )
    ]

    mast = Table([[left_top, right_top]], colWidths=[100*mm, 66*mm])
    mast.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('TOPPADDING', (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
    ]))
    story.append(mast)

    # Thick red rule under masthead
    story.append(HRFlowable(width=CW, thickness=3, color=RED, spaceAfter=16))

    # ── Submitter line ──
    if submitter or company:
        parts = []
        if submitter: parts.append(f'<b>{clean(submitter)}</b>')
        if company:   parts.append(f'<b>{clean(company)}</b>')
        story.append(Paragraph(
            'Submitted by: ' + '   |   '.join(parts),
            styles['small_dark']
        ))
        story.append(Spacer(1, 4*mm))

    # ── No proposal block - full details in the submission brief PDF ──
    story.append(Spacer(1, 4*mm))
    story.append(HRFlowable(width=CW, thickness=0.5, color=RULELINE, spaceAfter=10))

    # ── Verdict block ──
    vkey = get_verdict_key(verdict)
    vcolor = VERDICT_COLOR.get(vkey, RED)
    vstyle_key = {'SHIP':'verdict_ship','DO NOT SHIP':'verdict_noship','CONDITIONS':'verdict_cond'}.get(vkey,'verdict_noship')

    story.append(Paragraph('PANEL VERDICT', styles['verdict_label']))
    story.append(Spacer(1, 2*mm))
    story.append(Paragraph(verdict or 'PENDING', styles[vstyle_key]))
    story.append(Spacer(1, 4*mm))

    # Confidence + Risk score side by side
    meta_rows = [[
        Paragraph('Confidence Level', styles['verdict_label']),
        Paragraph('', styles['verdict_label']),
        Paragraph('Overall Risk Score', styles['verdict_label']),
    ],[
        Paragraph(f'<b>{confidence or "—"}</b>', styles['verdict_meta_b']),
        Paragraph('', styles['body']),
        Paragraph(f'<b>{risk_score or "—"}</b>', styles['verdict_meta_b']),
    ]]
    meta_t = Table(meta_rows, colWidths=[55*mm, 10*mm, 55*mm])
    meta_t.setStyle(TableStyle([
        ('TOPPADDING',(0,0),(-1,-1),2), ('BOTTOMPADDING',(0,0),(-1,-1),2),
        ('LEFTPADDING',(0,0),(-1,-1),0), ('RIGHTPADDING',(0,0),(-1,-1),0),
    ]))
    story.append(meta_t)
    story.append(Spacer(1, 8*mm))
    story.append(HRFlowable(width=CW, thickness=0.5, color=RULELINE, spaceAfter=4))

    return story


# ── Risk summary table ─────────────────────────────────────────────────────────
def build_risk_table(risks, styles):
    if not risks: return []
    story = []
    story.append(Paragraph('RISK SUMMARY', styles['h_section']))

    # Table header
    hdr = [
        Paragraph('Agent', styles['proposal_label']),
        Paragraph('Level', styles['proposal_label']),
        Paragraph('Assessment', styles['proposal_label']),
    ]
    rows = [hdr]
    for r in risks:
        if ':' in r:
            parts = r.split(':',1)
            agent_raw = parts[0].strip()
            rest = parts[1].strip()
            # further split on em-dash or double-dash
            if ' -- ' in rest or ' - ' in rest:
                lvl, detail = re.split(r' ?-- ?| - ', rest, 1)
            else:
                lvl = get_risk(rest)
                detail = rest
        else:
            agent_raw = r
            lvl = get_risk(r)
            detail = r
        lvl = lvl.strip().upper()
        agent = agent_raw.replace(' Agent','').replace(':','').strip()
        rc = RISK_COLOR.get(lvl, MIDGRAY)
        rows.append([
            Paragraph(f'<b>{agent}</b>', styles['risk_agent']),
            Paragraph(f'<font color="#{"%02X%02X%02X" % (int(rc.red*255), int(rc.green*255), int(rc.blue*255))}"><b>{lvl}</b></font>', styles['risk_level']),
            Paragraph(clean(detail), styles['risk_detail']),
        ])

    t = Table(rows, colWidths=[38*mm, 22*mm, CW-60*mm])
    style_cmds = [
        ('BACKGROUND',(0,0),(-1,0), NAVY),
        ('TEXTCOLOR',(0,0),(-1,0), WHITE),
        ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),
        ('FONTSIZE',(0,0),(-1,0),8),
        ('TOPPADDING',(0,0),(-1,-1),7),
        ('BOTTOMPADDING',(0,0),(-1,-1),7),
        ('LEFTPADDING',(0,0),(-1,-1),8),
        ('RIGHTPADDING',(0,0),(-1,-1),8),
        ('LINEBELOW',(0,0),(-1,-1),0.5,RULELINE),
        ('VALIGN',(0,0),(-1,-1),'TOP'),
        ('ROWBACKGROUNDS',(0,1),(-1,-1),[WHITE, BGLIGHT]),
    ]
    t.setStyle(TableStyle(style_cmds))
    story.append(t)
    story.append(Spacer(1, 6*mm))
    return story


# ── Findings section ───────────────────────────────────────────────────────────
def build_findings(items, title, styles, bg=BGLIGHT, label_color=NAVY):
    if not items: return []
    story = []
    story.append(Paragraph(title, styles['h_section']))
    for i, item in enumerate(items, 1):
        text = clean(item)
        rows = [[
            Paragraph(f'<b>{i}</b>', ParagraphStyle(
                'fn', fontName='Helvetica-Bold', fontSize=11,
                textColor=RED, leading=15, alignment=TA_CENTER
            )),
            Paragraph(text, styles['body']),
        ]]
        t = Table(rows, colWidths=[10*mm, CW-10*mm])
        t.setStyle(TableStyle([
            ('VALIGN',(0,0),(-1,-1),'TOP'),
            ('TOPPADDING',(0,0),(-1,-1),5),
            ('BOTTOMPADDING',(0,0),(-1,-1),5),
            ('LEFTPADDING',(0,0),(-1,-1),0),
            ('RIGHTPADDING',(0,0),(-1,-1),0),
            ('LINEBELOW',(0,0),(-1,0),0.3,RULELINE),
        ]))
        story.append(t)
    story.append(Spacer(1, 5*mm))
    return story


# ── Callout box ───────────────────────────────────────────────────────────────
def build_callout(text, label, styles, bg=BGSALMON, line_color=RED):
    if not text: return []
    story = []
    inner = [
        Paragraph(label, styles['callout_label']),
        Paragraph(clean(text), styles['callout']),
    ]
    t = Table([[inner]], colWidths=[CW])
    t.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,-1), bg),
        ('LINEBEFORE',(0,0),(0,-1), 3, line_color),
        ('TOPPADDING',(0,0),(-1,-1),10),
        ('BOTTOMPADDING',(0,0),(-1,-1),10),
        ('LEFTPADDING',(0,0),(-1,-1),14),
        ('RIGHTPADDING',(0,0),(-1,-1),12),
    ]))
    story.append(t)
    story.append(Spacer(1, 5*mm))
    return story


# ── Agent report section ───────────────────────────────────────────────────────
def build_agent_report(key, output, styles):
    agent_labels = {
        'safety':    ('Safety Agent',      'Analysis of failure modes, edge cases, harm vectors, and user risk'),
        'business':  ('Business Agent',    'Stress-test of ROI assumptions, adoption risk, and opportunity cost'),
        'data':      ('Data Quality Agent','Review of evaluation methodology, training data, and distribution shift'),
        'compliance':('Compliance Agent',  'Regulatory exposure, governance gaps, and legal risk assessment'),
        'contrarian':('Contrarian Agent',  'Hidden assumptions, normalised blindspots, and uncomfortable truths'),
    }
    label, desc = agent_labels.get(key.lower(), (key.title()+' Agent', ''))
    level = get_risk(output)
    lc = RISK_COLOR.get(level, MIDGRAY)

    story = []

    # Agent heading row
    story.append(HRFlowable(width=CW, thickness=0.5, color=RULELINE, spaceBefore=10, spaceAfter=8))
    heading_left = [
        Paragraph(f'<b>{label}</b>', styles['h_agent']),
        Paragraph(desc, styles['small_dark']),
    ]
    lc_hex = '#%02X%02X%02X' % (int(lc.red*255), int(lc.green*255), int(lc.blue*255))
    heading_right = [
        Paragraph('RISK LEVEL', styles['small_dark']),
        Paragraph(f'<font color="{lc_hex}"><b>{level}</b></font>',
                  ParagraphStyle('al', fontName='Helvetica-Bold', fontSize=14,
                                 textColor=lc, leading=18)),
    ]
    ht = Table([[heading_left, heading_right]], colWidths=[130*mm, 36*mm])
    ht.setStyle(TableStyle([
        ('VALIGN',(0,0),(-1,-1),'TOP'),
        ('TOPPADDING',(0,0),(-1,-1),0),
        ('BOTTOMPADDING',(0,0),(-1,-1),6),
        ('LEFTPADDING',(0,0),(-1,-1),0),
        ('RIGHTPADDING',(0,0),(-1,-1),0),
        ('ALIGN',(1,0),(1,-1),'RIGHT'),
    ]))
    story.append(ht)

    # Parse the agent output
    lines = str(output).split('\n')
    for line in lines:
        s = line.strip()
        if not s:
            story.append(Spacer(1, 2*mm))
        elif re.match(r'^(RISK LEVEL|DATA RISK|BUSINESS RISK|COMPLIANCE RISK|CONTRARIAN RISK).*:', s):
            # Skip — already shown in heading
            pass
        elif re.match(r'^([A-Z][A-Z\s&]+):$', s) and len(s) < 65:
            # Section sub-heading inside agent
            story.append(Paragraph(s.rstrip(':'), styles['h_sub']))
        elif s.startswith('- ') or s.startswith('* '):
            story.append(Paragraph(
                '<font color="#C0392B">&#8226;</font>  ' + clean(s[2:]),
                styles['bullet']
            ))
        elif re.match(r'^\d+\.\s', s):
            num, rest = s.split('.', 1)
            story.append(Paragraph(f'<b>{num}.</b>  {clean(rest.strip())}', styles['numbered']))
        elif any(s.upper().startswith(x) for x in ['SAFETY VERDICT','BUSINESS VERDICT','DATA VERDICT','COMPLIANCE VERDICT','CONTRARIAN VERDICT','RECOMMENDATION']):
            # Verdict line — callout style
            story.append(Spacer(1, 2*mm))
            inner = [Paragraph(clean(s), styles['body_bold'])]
            bt = Table([[inner]], colWidths=[CW])
            bt.setStyle(TableStyle([
                ('BACKGROUND',(0,0),(-1,-1), BGLIGHT),
                ('LINEBEFORE',(0,0),(0,-1), 2, NAVY),
                ('TOPPADDING',(0,0),(-1,-1),6),
                ('BOTTOMPADDING',(0,0),(-1,-1),6),
                ('LEFTPADDING',(0,0),(-1,-1),10),
                ('RIGHTPADDING',(0,0),(-1,-1),8),
            ]))
            story.append(bt)
            story.append(Spacer(1, 2*mm))
        else:
            story.append(Paragraph(clean(s), styles['body']))

    return story


# ── Main generate function ─────────────────────────────────────────────────────
def generate_pdf(review_id, proposal, synthesis, agent_outputs, output_path,
                  submitter="", company=""):

    # Build filename from proposal slug + datetime
    slug = re.sub(r'[^a-zA-Z0-9]+', '_', clean(proposal)[:45]).strip('_').lower()
    dt = datetime.utcnow().strftime('%Y%m%d_%H%M')
    dir_name = os.path.dirname(output_path) or '.'
    fname = f"{slug}_{dt}.pdf" if slug else f"redboard_{dt}.pdf"
    output_path = os.path.join(dir_name, fname)

    doc = SimpleDocTemplate(
        output_path, pagesize=A4,
        rightMargin=RM, leftMargin=LM,
        topMargin=TM+6*mm, bottomMargin=BM,
        title=f"Redboard Decision Memo - {review_id[:8].upper()}",
        author="Redboard Adversarial Review Panel",
        subject="AI Shipping Decision Memo - Confidential",
    )

    styles = make_styles()

    verdict    = extract_line(synthesis, 'PANEL VERDICT')
    confidence = extract_line(synthesis, 'CONFIDENCE')
    risk_score = extract_line(synthesis, 'OVERALL RISK SCORE')
    risks      = extract_risks(synthesis)
    findings   = section_items(synthesis, 'KEY FINDINGS')
    conditions = section_items(synthesis, 'CONDITIONS TO SHIP')
    next_steps = section_items(synthesis, 'RECOMMENDED NEXT STEPS')
    dissent    = extract_dissent(synthesis)

    story = []

    # Cover
    # Strip [ProjectName] prefix if present (added by main.py)
    import re as _re
    display_proposal = _re.sub(r'^\[.*?\]\s*', '', proposal, count=1)
    story.extend(build_cover(review_id, display_proposal, submitter, company,
                              verdict, confidence, risk_score, styles))

    # Risk table
    story.extend(build_risk_table(risks, styles))

    # Key findings
    story.extend(build_findings(findings, 'KEY FINDINGS', styles))

    # Conditions
    if conditions:
        story.append(Paragraph('CONDITIONS TO SHIP', styles['h_section']))
        for c in conditions:
            story.append(Paragraph(
                '<font color="#D35400">&#8594;</font>  ' + clean(c),
                styles['bullet']
            ))
        story.append(Spacer(1, 5*mm))

    # Minority dissent
    if dissent:
        story.extend(build_callout(
            f'"{dissent}"', 'MINORITY DISSENT', styles,
            bg=BGSALMON, line_color=RED
        ))

    # Next steps
    if next_steps:
        story.extend(build_findings(next_steps, 'RECOMMENDED NEXT STEPS', styles))

    # Agent reports divider
    story.append(Spacer(1, 6*mm))
    story.append(HRFlowable(width=CW, thickness=2, color=NAVY, spaceAfter=6))
    story.append(Paragraph('INDIVIDUAL AGENT REPORTS', styles['h_section']))
    story.append(Paragraph(
        'The following section contains the full analysis from each of the five specialist '
        'agents that participated in this review. Each agent independently examined the '
        'decision brief and produced its assessment without access to other agents\' findings. '
        'These reports informed the panel verdict above.',
        styles['italic']
    ))
    story.append(Spacer(1, 4*mm))

    # Agent reports
    for key, output in agent_outputs.items():
        if not output or 'Agent error' in str(output): continue
        story.extend(build_agent_report(key, str(output), styles))

    # Closing seal
    story.append(Spacer(1, 8*mm))
    story.append(HRFlowable(width=CW, thickness=0.5, color=RULELINE, spaceAfter=6))
    story.append(Paragraph(
        f'This memo was generated by the Redboard Adversarial Review Panel on '
        f'{datetime.utcnow().strftime("%d %B %Y at %H:%M UTC")}. '
        f'Review ID: {review_id}. '
        f'This document is confidential and intended solely for internal decision-making purposes. '
        f'Redboard\'s analysis constitutes structured decision support and does not constitute legal, '
        f'financial, or regulatory advice.',
        styles['small']
    ))

    def canvas_maker(*args, **kwargs):
        return RedboardCanvas(*args, review_id=review_id, **kwargs)

    doc.build(story, canvasmaker=canvas_maker)
    return output_path