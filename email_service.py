"""
Production email via Resend API.
Free: 3,000 emails/month. Setup: pip install resend | Set RESEND_API_KEY in .env
No RESEND_API_KEY = dev mode (prints to terminal).
"""
import os, random, string, base64
from datetime import datetime

RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
FROM_EMAIL = os.environ.get("FROM_EMAIL", "onboarding@resend.dev")  # Use resend test domain until yours is verified
FROM_NAME = os.environ.get("FROM_NAME", "Redboard")

def generate_otp(length=6) -> str:
    return ''.join(random.choices(string.digits, k=length))

def _send(to_email: str, subject: str, html: str, attachments: list = None) -> bool:
    if not RESEND_API_KEY:
        print(f"\n{'='*60}\n[EMAIL DEV] To: {to_email}\nSubject: {subject}")
        import re
        for otp in re.findall(r'\b\d{6}\b', html):
            print(f"OTP CODE: {otp}")
        for url in re.findall(r'href="([^"]*verify[^"]*)"', html):
            print(f"VERIFY: {url}")
        print('='*60 + '\n')
        return True
    try:
        import resend as r
        r.api_key = RESEND_API_KEY
        params = {"from": f"{FROM_NAME} <{FROM_EMAIL}>", "to": [to_email], "subject": subject, "html": html}
        if attachments:
            att = []
            for path, filename in attachments:
                with open(path, 'rb') as f:
                    att.append({"filename": filename, "content": base64.b64encode(f.read()).decode()})
            params["attachments"] = att
        email = r.Emails.send(params)
        print(f"[EMAIL SENT] {to_email} | {email.get('id','?')}")
        return True
    except Exception as e:
        print(f"[EMAIL ERROR] {e}")
        return False

def send_verification_email(to_email: str, name: str, token: str, base_url: str = "http://localhost:8000") -> bool:
    verify_url = f"{base_url}/auth/verify-email/{token}"
    html = f"""<!DOCTYPE html><html><body style="margin:0;padding:0;background:#0C0C0C;font-family:Helvetica,Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#0C0C0C;padding:40px 20px;"><tr><td align="center">
<table width="520" cellpadding="0" cellspacing="0" style="background:#141414;border:1px solid rgba(255,255,255,0.08);border-top:3px solid #C0392B;">
<tr><td style="padding:36px 40px;">
<div style="font-size:24px;font-weight:900;color:#F8F6F1;margin-bottom:4px;">Red<span style="color:#C0392B;">board</span></div>
<div style="font-size:11px;letter-spacing:2px;text-transform:uppercase;color:#888;margin-bottom:32px;">Email Verification</div>
<div style="font-size:16px;color:#F8F6F1;margin-bottom:10px;">Hi {name},</div>
<div style="font-size:14px;color:#888;line-height:1.7;margin-bottom:28px;">Welcome to Redboard. Click below to verify your email and activate your account. This link expires in <strong style="color:#F8F6F1;">24 hours</strong>.</div>
<div style="text-align:center;margin-bottom:28px;"><a href="{verify_url}" style="display:inline-block;background:#C0392B;color:#fff;padding:16px 40px;font-weight:700;font-size:13px;letter-spacing:1px;text-decoration:none;text-transform:uppercase;">VERIFY MY EMAIL &rarr;</a></div>
<div style="background:#1C1C1C;border:1px solid rgba(255,255,255,0.06);padding:14px 18px;margin-bottom:20px;"><div style="font-size:11px;color:#555;margin-bottom:4px;text-transform:uppercase;letter-spacing:1px;">Or copy this link</div><div style="font-size:11px;color:#777;word-break:break-all;font-family:monospace;">{verify_url}</div></div>
<div style="font-size:12px;color:#555;">If you did not create a Redboard account, ignore this email.</div>
</td></tr><tr><td style="padding:14px 40px;border-top:1px solid rgba(255,255,255,0.05);"><div style="font-size:11px;color:#444;">&copy; {datetime.utcnow().year} Redboard</div></td></tr></table></td></tr></table></body></html>"""
    return _send(to_email, f"Verify your Redboard account", html)

def send_otp_email(to_email: str, name: str, otp: str) -> bool:
    html = f"""<!DOCTYPE html><html><body style="margin:0;padding:0;background:#0C0C0C;font-family:Helvetica,Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#0C0C0C;padding:40px 20px;"><tr><td align="center">
<table width="520" cellpadding="0" cellspacing="0" style="background:#141414;border:1px solid rgba(255,255,255,0.08);border-top:3px solid #C0392B;">
<tr><td style="padding:36px 40px;">
<div style="font-size:24px;font-weight:900;color:#F8F6F1;margin-bottom:32px;">Red<span style="color:#C0392B;">board</span></div>
<div style="font-size:16px;color:#F8F6F1;margin-bottom:10px;">Hi {name},</div>
<div style="font-size:14px;color:#888;line-height:1.7;margin-bottom:28px;">Your password reset code. Expires in <strong style="color:#F8F6F1;">15 minutes</strong>.</div>
<div style="background:#0C0C0C;border:1px solid rgba(255,255,255,0.06);padding:32px;text-align:center;margin-bottom:28px;">
<div style="font-size:11px;color:#666;letter-spacing:2px;text-transform:uppercase;margin-bottom:16px;">Reset Code</div>
<div style="font-size:48px;font-weight:900;letter-spacing:14px;color:#C0392B;font-family:monospace;">{otp}</div></div>
<div style="font-size:12px;color:#555;">Never share this code. If you did not request this, ignore it.</div>
</td></tr><tr><td style="padding:14px 40px;border-top:1px solid rgba(255,255,255,0.05);"><div style="font-size:11px;color:#444;">&copy; {datetime.utcnow().year} Redboard</div></td></tr></table></td></tr></table></body></html>"""
    return _send(to_email, "Your Redboard password reset code", html)

def send_welcome_email(to_email: str, name: str, company: str) -> bool:
    html = f"""<!DOCTYPE html><html><body style="margin:0;padding:0;background:#0C0C0C;font-family:Helvetica,Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#0C0C0C;padding:40px 20px;"><tr><td align="center">
<table width="520" cellpadding="0" cellspacing="0" style="background:#141414;border:1px solid rgba(255,255,255,0.08);border-top:3px solid #C0392B;">
<tr><td style="padding:36px 40px;">
<div style="font-size:24px;font-weight:900;color:#F8F6F1;margin-bottom:32px;">Red<span style="color:#C0392B;">board</span></div>
<div style="font-size:20px;color:#F8F6F1;font-weight:600;margin-bottom:12px;">Welcome, {name}.</div>
<div style="font-size:14px;color:#888;line-height:1.8;margin-bottom:28px;">Your Redboard workspace is ready{(' for ' + company) if company else ''}. Five adversarial agents are ready to debate every AI decision your team ships.</div>
<div style="background:#1C1C1C;border:1px solid rgba(255,255,255,0.06);padding:20px;margin-bottom:20px;font-size:13px;color:#F8F6F1;line-height:2.2;">
&#127697;&#65039; Safety Agent &nbsp;&bull;&nbsp; &#128188; Business Agent &nbsp;&bull;&nbsp; &#128202; Data Agent<br>
&#9878;&#65039; Compliance Agent &nbsp;&bull;&nbsp; &#128293; Contrarian Agent</div>
<div style="font-size:12px;color:#555;">Sign in to start your first adversarial review.</div>
</td></tr><tr><td style="padding:14px 40px;border-top:1px solid rgba(255,255,255,0.05);"><div style="font-size:11px;color:#444;">&copy; {datetime.utcnow().year} Redboard</div></td></tr></table></td></tr></table></body></html>"""
    return _send(to_email, "Welcome to Redboard", html)

def send_review_report(to_email: str, name: str, project_name: str, proposal: str, verdict: str, confidence: str, pdf_path: str, submission_pdf: str = None, zip_path: str = None) -> bool:
    vc = "#34D399" if "SHIP" in verdict and "NOT" not in verdict and "CONDITION" not in verdict else "#F87171" if "NOT" in verdict else "#FBB040"
    sp = proposal[:160] + ("..." if len(proposal) > 160 else "")
    html = f"""<!DOCTYPE html><html><body style="margin:0;padding:0;background:#0C0C0C;font-family:Helvetica,Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#0C0C0C;padding:40px 20px;"><tr><td align="center">
<table width="580" cellpadding="0" cellspacing="0" style="background:#141414;border:1px solid rgba(255,255,255,0.08);border-top:3px solid #C0392B;">
<tr><td style="padding:36px 40px;">
<div style="font-size:24px;font-weight:900;color:#F8F6F1;margin-bottom:4px;">Red<span style="color:#C0392B;">board</span></div>
<div style="font-size:11px;letter-spacing:2px;text-transform:uppercase;color:#888;margin-bottom:32px;">Decision Memo</div>
<div style="font-size:14px;color:#888;margin-bottom:24px;">Hi {name}, your adversarial review panel has completed its analysis. The full memo is attached as PDF.</div>
<div style="background:#0C0C0C;border:1px solid rgba(255,255,255,0.06);padding:24px;margin-bottom:20px;">
<div style="font-size:11px;letter-spacing:1px;text-transform:uppercase;color:#555;margin-bottom:6px;">Project</div>
<div style="font-size:16px;font-weight:700;color:#F8F6F1;margin-bottom:12px;">{project_name}</div>
<div style="font-size:11px;letter-spacing:1px;text-transform:uppercase;color:#555;margin-bottom:6px;">Panel Verdict</div>
<div style="font-size:28px;font-weight:900;color:{vc};margin-bottom:8px;">{verdict}</div>
<div style="font-size:13px;color:#888;">Confidence: {confidence}</div></div>
<div style="background:#1C1C1C;border-left:3px solid #C0392B;padding:14px 18px;margin-bottom:20px;font-size:13px;color:#888;line-height:1.7;">
Attached to this email:<br>
<b style="color:#F8F6F1;">1. Decision Memo PDF</b> — full adversarial analysis with all agent reports and minority dissent.<br>
<b style="color:#F8F6F1;">2. Submission Brief PDF</b> — all form fields as a structured document.<br>
<b style="color:#F8F6F1;">3. Sources ZIP</b> — brief and all uploaded documents.
</div>
<div style="font-size:11px;color:#444;">Confidential &mdash; internal use only &mdash; {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</div>
</td></tr><tr><td style="padding:14px 40px;border-top:1px solid rgba(255,255,255,0.05);"><div style="font-size:11px;color:#444;">&copy; {datetime.utcnow().year} Redboard</div></td></tr></table></td></tr></table></body></html>"""
    dt = datetime.utcnow().strftime('%Y%m%d_%H%M')
    att = []
    if pdf_path and os.path.exists(pdf_path):
        att.append((pdf_path, f"Decision Memo_{dt}.pdf"))
    if submission_pdf and os.path.exists(submission_pdf):
        att.append((submission_pdf, f"Submission Brief_{dt}.pdf"))
    if zip_path and os.path.exists(zip_path):
        att.append((zip_path, f"Submission Details_{dt}.zip"))
    clean_proj = (project_name or proposal[:50]).replace('\n','').replace('\r','').strip()
    subject = f"Redboard: {clean_proj} - {verdict}"
    return _send(to_email, subject, html, att)