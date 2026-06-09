# Redboard — Adversarial AI Review Panel

> Five specialist agents debate your AI shipping decision in parallel. One synthesizer produces a structured decision memo with minority dissent preserved.

Built for the **Google for Startups AI Agents Challenge 2026** — Track: Build (Net-New Agents), Region: APAC.

---

## What it does

Redboard is an adversarial review system for AI shipping decisions. When an engineering team is about to deploy an AI feature, they submit a decision brief to Redboard. Five specialist agents independently attack the proposal from different angles:

| Agent | Role |
|---|---|
|  Safety Agent | Failure modes, harm vectors, edge cases, adversarial vulnerability |
|  Business Agent | ROI assumptions, adoption risk, opportunity cost, hidden costs |
|  Data Quality Agent | Evaluation validity, distribution shift, label quality, bias |
|  Compliance Agent | GDPR, HIPAA, EU AI Act, sector-specific regulation, governance |
|  Contrarian Agent | Hidden assumptions, normalised blindspots, uncomfortable truths |

A sixth **Synthesizer** aggregates all five reports into a final decision memo: **SHIP**, **DO NOT SHIP**, or **SHIP WITH CONDITIONS** — with minority dissent preserved and conditions that are specific and testable.

Every agent has access to **Google Search grounding** to cite current regulations, recent incidents, and live benchmarks.

The full review is delivered as:
- A branded **Decision Memo PDF** (with risk summary, key findings, agent reports, and recommended next steps)
- A **Submission Brief PDF** (all form fields as a structured document)
- A **Sources ZIP** (brief + all uploaded files)

All three are emailed automatically when the review completes.

---

## Architecture

```
User (browser)
    │  HTTPS · JWT auth
    ▼
FastAPI backend (Python 3.12 · Uvicorn · Google Cloud Run)
    │  Input validation · file handling · audit log
    ▼
Orchestrator (Google ADK 2.2 · A2A protocol)
    │  asyncio.gather — 5 agents in parallel
    ├── Safety Agent      ──┐
    ├── Business Agent    ──┤
    ├── Data Agent        ──┤──► Gemini 2.5 Flash + Google Search grounding
    ├── Compliance Agent  ──┤
    └── Contrarian Agent  ──┘
    │  Results collected
    ▼
Synthesizer Agent  ──► Gemini 2.5 Flash
    │  Final verdict + memo
    ▼
┌─────────────────────────────────────────┐
│  Decision Memo PDF  (ReportLab)         │
│  Submission Brief PDF                   │
│  Sources ZIP                            │
└─────────────────────────────────────────┘
    │
    ├── Stored in SQLite + filesystem
    └── Emailed via Resend API (3 attachments)

Infrastructure: Google Cloud Run · GCP project project-id
A2A manifest:  GET /.well-known/agent.json
```

---

## Project structure

```
redboard/
├── main.py               # FastAPI app — all routes, auth, review endpoints, admin
├── orchestrator.py       # Panel orchestration — A2A manifest, run_panel(), file reading
├── database.py           # SQLAlchemy models — User, Review, AuditLog, OTPStore
├── auth.py               # JWT tokens, bcrypt, password validation, phone validation
├── email_service.py      # Resend API — verification, OTP, welcome, review report
├── pdf_gen.py            # ReportLab — branded decision memo PDF
├── submission_pdf.py     # ReportLab — submission brief PDF (all form fields)
├── requirements.txt
├── .env.example
├── .gitignore
│
├── agents/
│   ├── _base.py              # Shared AGENT_BASE prompt + GEMINI_MODEL constant
│   ├── __init__.py           # Exports all 6 agents
│   ├── safety_agent.py
│   ├── business_agent.py
│   ├── data_agent.py
│   ├── compliance_agent.py
│   ├── contrarian_agent.py
│   └── synthesizer_agent.py
│
├── static/
│   └── index.html            # Full SPA — landing, auth, review form, results, admin
│
├── sample_inputs/
│   ├── HOW_TO_USE.txt
│   ├── sample_brief.txt          # ClaimsIQ v1.0 — full realistic insurance AI brief
│   ├── eval_report.csv           # Model evaluation with deliberate gaps
│   ├── architecture_risks.txt    # Engineering doc with 8 known issues
│   ├── sample_HIGH_risk.txt      # AI hiring system — expect DO NOT SHIP
│   ├── sample_MEDIUM_risk.txt    # Internal knowledge assistant — expect CONDITIONS
│   └── sample_LOW_risk.txt       # Sprint planning assistant — expect SHIP
│
├── uploads/                  # Per-review uploaded source files (gitignored)
└── outputs/                  # Generated PDFs and ZIPs (gitignored)
```

---

## Setup

### Prerequisites

- Python 3.12
- A Gemini API key from [aistudio.google.com](https://aistudio.google.com)
- A Resend API key from [resend.com](https://resend.com) (free — 3,000 emails/month)
- Google Cloud SDK (`gcloud`) authenticated

### 1. Clone and install

```bash
git clone https://github.com/pujaankithauta-svg/redboard.git
cd redboard
pip install -r requirements.txt
pip install resend bcrypt==4.0.1
```

### 2. Configure environment

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

```env
# Gemini
GEMINI_API_KEY=your-gemini-api-key

# Google Cloud
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=us-central1

# Security — generate a random 32+ char string
SECRET_KEY=your-random-secret-key

# Database
DATABASE_URL=sqlite:///./redboard.db

# Email via Resend (resend.com)
# Leave blank to print emails to terminal in dev mode
RESEND_API_KEY=re_xxxxxxxxxxxxxxxxxxxx
FROM_EMAIL=onboarding@resend.dev
FROM_NAME=Redboard
```

### 3. Run locally

```bash
uvicorn main:app --reload
```

Open [http://localhost:8000](http://localhost:8000)

### 4. Default admin account

Created automatically on first startup:

```
Email:    admin@redboard.ai
Password: Admin@Redboard2026!
```

Change this immediately after first login via the Admin Panel.

---

## Running a review

### Option A — Fill the 4-step form

1. Sign in and click **New Review**
2. **Step 1** — Project name (mandatory), proposal, context, objectives
3. **Step 2** — Team, timeline, user base, domain, geographies, tech stack, stakeholders
4. **Step 3** — Known risks, regulatory environment, data sensitivity, human oversight, rollback plan, success metrics
5. **Step 4** — Upload supporting documents (optional but strongly recommended), review the summary, submit

### Option B — Upload a complete project brief

On the New Review page, use the **"Skip the form"** upload zone. Drop a single document (PDF, TXT, or MD) that describes your project. The agents will extract all context from it automatically.

For best results, your document should include: proposal, model architecture, training data details, evaluation metrics, team, timeline, known risks, tech stack, stakeholders, regulatory context, and deployment plan.

### Sample inputs

Three ready-to-use examples are in `sample_inputs/`:

| File | Scenario | Expected verdict |
|---|---|---|
| `sample_HIGH_risk.txt` | AI hiring system with no bias testing, no EEOC review | DO NOT SHIP |
| `sample_MEDIUM_risk.txt` | Internal knowledge assistant with PII leak in knowledge base | SHIP WITH CONDITIONS |
| `sample_LOW_risk.txt` | Sprint planning assistant — advisory only, pilot done | SHIP |

Upload any of these directly to the skip-the-form zone to see a full review.

---

## What you receive

After a review completes:

1. **On-screen** — verdict, risk summary table, key findings, conditions, minority dissent, recommended next steps, and full agent reports in tabbed view
2. **Email** (3 attachments sent to your registered address):
   - `Decision Memo_datetime.pdf` — full adversarial analysis
   - `Submission Brief_datetime.pdf` — all submitted form fields as a document
   - `Submission Details_datetime.zip` — brief PDF + all uploaded source files
3. **History** — all past reviews stored and downloadable from the Review History page

---

## Security

- Passwords: bcrypt hashing, minimum 10 characters with uppercase, lowercase, number, and symbol required
- Sessions: JWT tokens, 24-hour expiry
- Email verification: account pending until email link clicked, token expires in 24 hours
- Forgot password: 6-digit OTP emailed, expires in 15 minutes, stored hashed
- One account per phone number enforced
- Input sanitization on all text fields (XSS prevention)
- Security headers: `X-Content-Type-Options`, `X-Frame-Options`, `X-XSS-Protection`
- Full audit log: every login, review creation, profile change, and admin action recorded
- Admin panel: only visible to accounts with `is_admin=True`
- Data isolation: users can only access their own reviews

---

## API reference

### Auth

| Method | Endpoint | Description |
|---|---|---|
| POST | `/auth/register` | Register new account |
| POST | `/auth/login` | Sign in, returns JWT |
| GET | `/auth/me` | Get current user |
| PUT | `/auth/profile` | Update profile (password required) |
| PUT | `/auth/password` | Change password |
| POST | `/auth/forgot-password` | Send OTP reset code |
| POST | `/auth/verify-otp` | Verify OTP and set new password |
| GET | `/auth/verify-email/{token}` | Email verification link handler |
| POST | `/auth/resend-verification` | Resend verification email |

### Reviews

| Method | Endpoint | Description |
|---|---|---|
| POST | `/review` | Submit a new review (multipart form + files) |
| GET | `/reviews` | List all reviews for current user |
| GET | `/reviews/{id}` | Get full review with agent outputs |
| DELETE | `/reviews/{id}` | Soft-delete a review |
| GET | `/review/{id}/pdf` | Download decision memo PDF |

### Admin

| Method | Endpoint | Description |
|---|---|---|
| GET | `/admin/stats` | Total users, reviews, verdict breakdown |
| GET | `/admin/users` | List all users |
| PUT | `/admin/users/{id}/toggle` | Suspend or activate a user |
| GET | `/admin/reviews` | List all reviews across all users |
| GET | `/admin/audit` | Full audit log |

### A2A

| Method | Endpoint | Description |
|---|---|---|
| GET | `/.well-known/agent.json` | A2A protocol manifest — 6 agent cards |

---

## Agent-to-Agent (A2A) protocol

Redboard exposes a standard A2A manifest at `/.well-known/agent.json`. This enables enterprise orchestration platforms and external agents to discover and invoke the Redboard panel programmatically.

Each of the six agents has a published Agent Card with:
- `name`, `version`, `description`
- `capabilities` array
- `input_schema` and `output_schema`

The manifest also declares the panel's orchestration mode (`parallel_with_synthesis`) and top-level capabilities (`ai_shipping_review`, `multi_agent_debate`, `minority_dissent_preservation`).

---

## Google Search grounding

All five specialist agents have access to Google Search via `google.adk.tools.google_search`. They are instructed to search for:
- Current regulatory requirements (EU AI Act obligations, HIPAA BAA rules, GDPR Article 22)
- Recent incidents involving similar AI systems
- Current industry benchmarks for the technology described
- Regulatory updates that affect the specific proposal

This means the compliance agent, for example, will search for the latest EU AI Act implementing acts before issuing its verdict — not rely on training data alone.

---

## Deploying to Google Cloud Run

```bash
# Build and push container
gcloud builds submit --tag gcr.io/project-id/redboard

# Deploy
gcloud run deploy redboard \
  --image gcr.io/project-id/redboard \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars GEMINI_API_KEY=your-key,SECRET_KEY=your-secret,RESEND_API_KEY=your-resend-key
```

For persistent storage on Cloud Run, mount a Cloud Storage FUSE bucket or use Cloud SQL instead of SQLite.

---

## Tech stack

| Layer | Technology |
|---|---|
| Language | Python 3.12 |
| API framework | FastAPI + Uvicorn |
| AI agents | Google ADK 2.2 |
| LLM | Gemini 2.5 Flash (Google AI Studio) |
| Search grounding | Google Search (via ADK tools) |
| Agent protocol | A2A / 1.0 |
| PDF generation | ReportLab 4 |
| Database | SQLAlchemy + SQLite |
| Authentication | JWT (python-jose) + bcrypt (passlib) |
| Email | Resend API |
| Frontend | Vanilla JS SPA (single `index.html`) |
| Infrastructure | Google Cloud Run |
| Container registry | Google Artifact Registry |

---

## Environment variables reference

| Variable | Required | Description |
|---|---|---|
| `GEMINI_API_KEY` | Yes | From aistudio.google.com |
| `GOOGLE_CLOUD_PROJECT` | Yes | Your GCP project ID |
| `GOOGLE_CLOUD_LOCATION` | Yes | e.g. `us-central1` |
| `SECRET_KEY` | Yes | Random string, min 32 chars, for JWT signing |
| `DATABASE_URL` | No | Defaults to `sqlite:///./redboard.db` |
| `RESEND_API_KEY` | No | Leave blank to print emails to terminal |
| `FROM_EMAIL` | No | Defaults to `onboarding@resend.dev` |
| `FROM_NAME` | No | Defaults to `Redboard` |
| `ALLOWED_ORIGINS` | No | CORS origins, defaults to `http://localhost:8000` |

---

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Commit your changes: `git commit -m "Add your feature"`
4. Push and open a pull request

When modifying agent prompts, edit only the relevant file in `agents/`. The `_base.py` file contains shared instructions used by all five specialist agents — changes there affect every agent.

---

## Hackathon context

Built for the **Google for Startups AI Agents Challenge 2026**.

- Track: Build — Net-New Agents
- Region: APAC
- Submission deadline: June 11, 2026
- Prize: $60,000 cash + $37,500 Google Cloud credits

The problem Redboard solves is one YC explicitly named as underserved in their 2024 request for startups: "Company Brain / adversarial review". Investment committees, clinical trial boards, and supreme courts all use adversarial review by design. AI shipping decisions do not. Redboard is the fix.

---

## License

MIT

---

*Redboard — Adversarial AI Review Panel · Built by Puja Ankitha Ivaturi · 2026*