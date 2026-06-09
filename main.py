from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, List
import asyncio, os, shutil, uuid, json, re, zipfile
from datetime import datetime, timedelta

from database import init_db, get_db, User, Review, AuditLog, OTPStore
from auth import hash_password, verify_password, create_token, decode_token, validate_password, validate_phone, validate_email
from orchestrator import run_panel, get_panel_manifest
from submission_pdf import generate_submission_pdf
from pdf_gen import generate_pdf
from email_service import send_otp_email, send_welcome_email, send_review_report, generate_otp, send_verification_email
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy.orm import Session

app = FastAPI(title="Redboard API", version="3.1")

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        return response

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

UPLOAD_DIR = "uploads"; OUTPUT_DIR = "outputs"
ALLOWED_EXTENSIONS = {'.pdf','.txt','.md','.py','.js','.ts','.json','.csv','.yaml','.yml'}
MAX_FILE_MB = 10
os.makedirs(UPLOAD_DIR, exist_ok=True); os.makedirs(OUTPUT_DIR, exist_ok=True)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

@app.on_event("startup")
def startup():
    init_db()
    db = next(get_db())
    try:
        admin = db.query(User).filter(User.email == "admin@redboard.ai").first()
        if not admin:
            db.add(User(id=str(uuid.uuid4()), name="Redboard Admin", email="admin@redboard.ai",
                phone="+10000000000", company="Redboard", role="Administrator",
                password_hash=hash_password("Admin@Redboard2026!"), is_admin=True, is_active=True,
                consent_given=True, consent_at=datetime.utcnow(), created_at=datetime.utcnow(), review_count=0))
            db.commit()
            print("Admin created: admin@redboard.ai / Admin@Redboard2026!")
    finally: db.close()

def get_ip(r: Request):
    fwd = r.headers.get("X-Forwarded-For")
    return fwd.split(",")[0] if fwd else (r.client.host if r.client else "unknown")

def log_action(db, uid, action, detail="", ip=""):
    db.add(AuditLog(id=str(uuid.uuid4()), user_id=uid, action=action, detail=detail, ip_address=ip, created_at=datetime.utcnow()))
    db.commit()

def sanitize(t: str) -> str: return t.replace('<','&lt;').replace('>','&gt;').strip()

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    payload = decode_token(token)
    if not payload: raise HTTPException(401, "Invalid token")
    user = db.query(User).filter(User.email == payload["sub"]).first()
    if not user or not user.is_active: raise HTTPException(401, "User not found")
    return user

def get_admin(u: User = Depends(get_current_user)):
    if not u.is_admin: raise HTTPException(403, "Admin only")
    return u

def exline(s, k):
    for l in s.split("\n"):
        if k+":" in l: return l.replace(k+":","").strip()
    return ""

def _ud(u):
    return {"id":u.id,"name":u.name,"email":u.email,"phone":u.phone,"company":u.company,
            "role":u.role,"is_admin":bool(u.is_admin),"is_active":bool(u.is_active),
            "email_verified":bool(u.email_verified),
            "created_at":u.created_at.isoformat() if u.created_at else None,
            "last_login":u.last_login.isoformat() if u.last_login else None,
            "review_count":u.review_count or 0}

class RegReq(BaseModel):
    name:str; email:str; phone:str; company:Optional[str]=""; role:Optional[str]=""; password:str; consent:bool

class ProfileReq(BaseModel):
    name:str; company:Optional[str]=""; role:Optional[str]=""; current_password:str

class PwReq(BaseModel):
    current_password:str; new_password:str

class ForgotReq(BaseModel):
    email:str

class OTPReq(BaseModel):
    email:str; otp:str; new_password:str


@app.post("/auth/register")
def register(req: RegReq, request: Request, bg: BackgroundTasks, db: Session = Depends(get_db)):
    if not req.consent: raise HTTPException(400,"Consent required")
    if not validate_email(req.email): raise HTTPException(400,"Invalid email")
    if not validate_phone(req.phone): raise HTTPException(400,"Invalid phone — include country code e.g. +91 98765 43210")
    errs = validate_password(req.password)
    if errs: raise HTTPException(400,"; ".join(errs))
    if db.query(User).filter(User.email==req.email.lower()).first(): raise HTTPException(400,"Email already registered")
    phone = re.sub(r'[\s\-\(\)]','',req.phone)
    if db.query(User).filter(User.phone==phone).first(): raise HTTPException(400,"Phone already registered")
    import secrets
    verification_token = secrets.token_urlsafe(32)
    u = User(id=str(uuid.uuid4()), name=sanitize(req.name), email=req.email.lower().strip(),
             phone=phone, company=sanitize(req.company or ""), role=sanitize(req.role or ""),
             password_hash=hash_password(req.password), is_admin=False, is_active=True,
             email_verified=False, verification_token=verification_token,
             verification_sent_at=datetime.utcnow(),
             consent_given=True, consent_at=datetime.utcnow(), created_at=datetime.utcnow(), review_count=0)
    db.add(u); db.commit()
    log_action(db, u.id, "REGISTER", u.email, get_ip(request))
    base_url = str(request.base_url).rstrip('/')
    bg.add_task(send_verification_email, u.email, u.name, verification_token, base_url)
    # Return token but mark as unverified — frontend shows verification pending screen
    return {"access_token":create_token({"sub":u.email}),"token_type":"bearer","user":_ud(u),"email_verified":False,"message":"verification_sent"}

@app.post("/auth/login")
def login(form: OAuth2PasswordRequestForm = Depends(), request: Request = None, db: Session = Depends(get_db)):
    u = db.query(User).filter(User.email==form.username.lower()).first()
    if not u or not verify_password(form.password, u.password_hash): raise HTTPException(401,"Invalid credentials")
    if not u.is_active: raise HTTPException(403,"Account suspended. Contact support.")
    if not bool(u.email_verified) and not bool(u.is_admin):
        raise HTTPException(403,"Email not verified. Please check your inbox and verify your email before signing in.")
    u.last_login = datetime.utcnow(); db.commit()
    log_action(db, u.id, "LOGIN", "", get_ip(request) if request else "")
    return {"access_token":create_token({"sub":u.email}),"token_type":"bearer","user":_ud(u)}

@app.get("/auth/me")
def me(u: User = Depends(get_current_user)): return _ud(u)

@app.put("/auth/profile")
def update_profile(req: ProfileReq, request: Request, u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not verify_password(req.current_password, u.password_hash): raise HTTPException(401,"Wrong password")
    u.name=sanitize(req.name); u.company=sanitize(req.company or ""); u.role=sanitize(req.role or "")
    db.commit(); log_action(db, u.id, "PROFILE_UPDATE", "", get_ip(request))
    return _ud(u)

@app.put("/auth/password")
def change_pw(req: PwReq, request: Request, u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not verify_password(req.current_password, u.password_hash): raise HTTPException(401,"Wrong password")
    errs = validate_password(req.new_password)
    if errs: raise HTTPException(400,"; ".join(errs))
    u.password_hash = hash_password(req.new_password); db.commit()
    log_action(db, u.id, "PW_CHANGE", "", get_ip(request))
    return {"message":"Password updated"}

@app.post("/auth/forgot-password")
def forgot_pw(req: ForgotReq, bg: BackgroundTasks, db: Session = Depends(get_db)):
    u = db.query(User).filter(User.email==req.email.lower()).first()
    if u:
        otp = generate_otp()
        db.query(OTPStore).filter(OTPStore.email==req.email.lower()).delete()
        db.add(OTPStore(id=str(uuid.uuid4()), email=req.email.lower(),
                        otp_hash=hash_password(otp), expires_at=datetime.utcnow()+timedelta(minutes=15),
                        created_at=datetime.utcnow()))
        db.commit()
        bg.add_task(send_otp_email, u.email, u.name, otp)
    return {"message":"If that email is registered, a reset code has been sent."}

@app.get("/auth/verify-email/{token}")
def verify_email(token: str, db: Session = Depends(get_db)):
    u = db.query(User).filter(User.verification_token == token).first()
    if not u:
        # Return HTML page with error
        return FileResponse("static/index.html") if os.path.exists("static/index.html") else {"error":"Invalid link"}
    
    from datetime import timedelta
    if u.verification_sent_at and (datetime.utcnow() - u.verification_sent_at).total_seconds() > 86400:
        return FileResponse("static/index.html")  # expired — frontend handles
    
    u.email_verified = True
    u.verification_token = None
    db.commit()
    log_action(db, u.id, "EMAIL_VERIFIED", u.email)
    # Redirect to app with success param
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/?verified=1")

@app.post("/auth/resend-verification")
def resend_verification(request: Request, bg: BackgroundTasks, u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if bool(u.email_verified):
        raise HTTPException(400, "Email already verified")
    import secrets
    u.verification_token = secrets.token_urlsafe(32)
    u.verification_sent_at = datetime.utcnow()
    db.commit()
    base_url = str(request.base_url).rstrip('/')
    bg.add_task(send_verification_email, u.email, u.name, u.verification_token, base_url)
    return {"message":"Verification email resent"}

@app.post("/auth/verify-otp")
def verify_otp(req: OTPReq, db: Session = Depends(get_db)):
    rec = db.query(OTPStore).filter(OTPStore.email==req.email.lower()).first()
    if not rec: raise HTTPException(400,"No reset code found. Request a new one.")
    if datetime.utcnow() > rec.expires_at:
        db.delete(rec); db.commit(); raise HTTPException(400,"Code expired. Request a new one.")
    if not verify_password(req.otp, rec.otp_hash): raise HTTPException(400,"Incorrect code.")
    errs = validate_password(req.new_password)
    if errs: raise HTTPException(400,"; ".join(errs))
    u = db.query(User).filter(User.email==req.email.lower()).first()
    if not u: raise HTTPException(404,"User not found")
    u.password_hash = hash_password(req.new_password)
    db.delete(rec); db.commit()
    log_action(db, u.id, "PW_RESET", u.email)
    return {"message":"Password reset successfully. You can now sign in."}

@app.post("/review")
async def create_review(
    request: Request, bg: BackgroundTasks,
    project_name: str = Form("Untitled Project"),
    proposal: str = Form(...), context: str = Form(...),
    team: str = Form(""), objectives: str = Form(""),
    risks_known: str = Form(""), timeline: str = Form(""),
    stakeholders: str = Form(""), tech_stack: str = Form(""),
    files: Optional[List[UploadFile]] = File(None),
    u: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    if not proposal.strip() or not context.strip(): raise HTTPException(400,"Proposal and context required")
    rid = str(uuid.uuid4()); saved=[]; names=[]
    if files:
        rd = os.path.join(UPLOAD_DIR, rid); os.makedirs(rd, exist_ok=True)
        for f in files:
            if not f.filename: continue
            ext = os.path.splitext(f.filename)[1].lower()
            if ext not in ALLOWED_EXTENSIONS: raise HTTPException(400,f"Type {ext} not allowed")
            content = await f.read()
            if len(content) > MAX_FILE_MB*1024*1024: raise HTTPException(400,f"{f.filename} too large")
            fp = os.path.join(rd, f.filename)
            with open(fp,"wb") as buf: buf.write(content)
            saved.append(fp); names.append(f.filename)
    brief = f"""
PROJECT NAME: {sanitize(project_name)}
PROPOSAL: {sanitize(proposal)}
CONTEXT: {sanitize(context)}
TEAM: {sanitize(team)}
OBJECTIVES: {sanitize(objectives)}
KNOWN RISKS: {sanitize(risks_known)}
TIMELINE: {sanitize(timeline)}
STAKEHOLDERS: {sanitize(stakeholders)}
TECH STACK: {sanitize(tech_stack)}
ORGANIZATION: {u.company or 'Not specified'}
SUBMITTER: {u.name} ({u.role or 'Team member'})
"""
    result = await run_panel(brief, saved)
    verdict = exline(result["synthesis"],"PANEL VERDICT")
    confidence = exline(result["synthesis"],"CONFIDENCE")
    # Clean project name for filenames
    import re as _re
    proj_slug = _re.sub(r'[^a-zA-Z0-9]+', '_', sanitize(project_name)[:40]).strip('_')
    dt_str = datetime.utcnow().strftime('%Y%m%d_%H%M')
    pdf_filename = f"{proj_slug}_{dt_str}.pdf"

    # Generate review memo PDF
    pdf_path_base = os.path.join(OUTPUT_DIR, pdf_filename)
    actual_pdf_path = generate_pdf(
        review_id=rid, proposal=f"[{sanitize(project_name)}] {proposal}",
        synthesis=result["synthesis"], agent_outputs=result["agent_outputs"],
        output_path=pdf_path_base, submitter=u.name, company=u.company or ""
    )
    pdf_path = actual_pdf_path or pdf_path_base

    # Generate submission brief PDF
    submission_pdf_path = os.path.join(OUTPUT_DIR, f"{proj_slug}_{dt_str}_brief.pdf")
    generate_submission_pdf(
        output_path=submission_pdf_path,
        project_name=sanitize(project_name),
        review_id=rid, submitter=u.name, company=u.company or "",
        proposal=proposal, context=context, team=team, timeline=timeline,
        objectives=objectives, risks_known=risks_known,
        stakeholders=stakeholders, tech_stack=tech_stack,
        file_names=names if names else []
    )

    # Create zip of submission brief + all source files
    zip_path = os.path.join(OUTPUT_DIR, f"{proj_slug}_{dt_str}_sources.zip")
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        if os.path.exists(submission_pdf_path):
            zf.write(submission_pdf_path, f"{proj_slug}_brief.pdf")
        for fp in saved:
            if os.path.exists(fp):
                zf.write(fp, os.path.basename(fp))
    db.add(Review(id=rid, user_id=u.id, project_name=sanitize(project_name),
                  proposal=sanitize(proposal),
                  context=sanitize(context), team=sanitize(team),
                  objectives=sanitize(objectives), risks_known=sanitize(risks_known),
                  timeline=sanitize(timeline), stakeholders=sanitize(stakeholders),
                  tech_stack=sanitize(tech_stack), synthesis=result["synthesis"],
                  agent_outputs=json.dumps(result["agent_outputs"]),
                  verdict=verdict, confidence=confidence, pdf_path=pdf_path,
                  files=",".join(saved), file_names=",".join(names),
                  created_at=datetime.utcnow(), is_deleted=False))
    u.review_count = (u.review_count or 0)+1; db.commit()
    log_action(db, u.id, "REVIEW", f"{rid}:{verdict}", get_ip(request))
    bg.add_task(send_review_report, u.email, u.name,
               sanitize(project_name), proposal, verdict, confidence,
               pdf_path, submission_pdf_path if os.path.exists(submission_pdf_path) else None,
               zip_path if os.path.exists(zip_path) else None)
    return {"review_id":rid,"project_name":sanitize(project_name),
            "synthesis":result["synthesis"],"agent_outputs":result["agent_outputs"],
            "verdict":verdict,"confidence":confidence,"pdf_url":f"/review/{rid}/pdf","file_count":len(saved)}

@app.get("/review/{rid}/pdf")
def get_pdf(rid: str, u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    r = db.query(Review).filter(Review.id==rid, Review.user_id==u.id, Review.is_deleted==False).first()
    if not r or not os.path.exists(r.pdf_path): raise HTTPException(404,"Not found")
    return FileResponse(r.pdf_path, media_type="application/pdf", filename=f"redboard-{rid[:8]}.pdf")

@app.get("/reviews")
def list_reviews(u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rs = db.query(Review).filter(Review.user_id==u.id, Review.is_deleted==False).order_by(Review.created_at.desc()).all()
    return [{"id":r.id,"proposal":r.proposal[:120]+("..."if len(r.proposal)>120 else ""),
             "verdict":r.verdict or "UNKNOWN","confidence":r.confidence or "MEDIUM",
             "created_at":r.created_at.isoformat() if r.created_at else None,
             "file_count":len(r.file_names.split(",")) if r.file_names else 0} for r in rs]

@app.get("/reviews/{rid}")
def get_review(rid: str, u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    r = db.query(Review).filter(Review.id==rid, Review.user_id==u.id, Review.is_deleted==False).first()
    if not r: raise HTTPException(404)
    try: ao = json.loads(r.agent_outputs) if r.agent_outputs else {}
    except: ao = {}
    return {"id":r.id,"proposal":r.proposal,"context":r.context,"team":r.team,
            "objectives":r.objectives,"risks_known":r.risks_known,"timeline":r.timeline,
            "stakeholders":r.stakeholders,"tech_stack":r.tech_stack,"synthesis":r.synthesis,
            "agent_outputs":ao,"verdict":r.verdict,"confidence":r.confidence,
            "created_at":r.created_at.isoformat() if r.created_at else None,
            "file_names":r.file_names.split(",") if r.file_names else [],"pdf_url":f"/review/{r.id}/pdf"}

@app.get("/admin/users")
def a_users(admin=Depends(get_admin), db: Session = Depends(get_db)):
    return [_ud(u) for u in db.query(User).order_by(User.created_at.desc()).all()]

@app.put("/admin/users/{uid}/toggle")
def a_toggle(uid: str, request: Request, admin=Depends(get_admin), db: Session = Depends(get_db)):
    u = db.query(User).filter(User.id==uid).first()
    if not u: raise HTTPException(404)
    if u.is_admin: raise HTTPException(400,"Cannot suspend admin")
    u.is_active = not u.is_active; db.commit()
    log_action(db, admin.id, "TOGGLE_USER", f"{u.email}={u.is_active}", get_ip(request))
    return _ud(u)

@app.get("/admin/reviews")
def a_reviews(admin=Depends(get_admin), db: Session = Depends(get_db)):
    rs = db.query(Review).order_by(Review.created_at.desc()).limit(200).all()
    return [{"id":r.id,"proposal":r.proposal[:100],"verdict":r.verdict,
             "created_at":r.created_at.isoformat() if r.created_at else None} for r in rs]

@app.get("/admin/stats")
def a_stats(admin=Depends(get_admin), db: Session = Depends(get_db)):
    vc = {}
    for (v,) in db.query(Review.verdict).filter(Review.is_deleted==False).all():
        k = "DO NOT SHIP" if v and "NOT" in v else "CONDITIONS" if v and "CONDITION" in v else "SHIP" if v and "SHIP" in v else "OTHER"
        vc[k] = vc.get(k,0)+1
    return {"total_users":db.query(User).count(),"active_users":db.query(User).filter(User.is_active==True).count(),
            "total_reviews":db.query(Review).filter(Review.is_deleted==False).count(),"verdicts":vc}

@app.get("/admin/audit")
def a_audit(admin=Depends(get_admin), db: Session = Depends(get_db)):
    return [{"action":l.action,"detail":l.detail,"ip":l.ip_address,
             "time":l.created_at.isoformat() if l.created_at else None}
            for l in db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(300).all()]

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/.well-known/agent.json")
def a2a_manifest():
    """A2A protocol agent discovery endpoint."""
    return get_panel_manifest()

@app.get("/")
def root(): return FileResponse("static/index.html")

@app.get("/{path:path}")
def spa(path: str):
    if any(path.startswith(p) for p in ["auth","review","admin","static",".well-known"]): raise HTTPException(404)
    return FileResponse("static/index.html")